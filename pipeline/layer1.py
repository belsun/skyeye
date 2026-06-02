"""Layer 1: SkyEye batch news relevance and sentiment labeling.

This layer writes normalized labels into layer1_results. It prefers the
configured OpenAI-compatible SkyEye model, then falls back to deterministic
Polygon/text heuristics so the sentiment pipeline remains usable offline.
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

from database import get_conn
from pipeline.layer0 import run_layer0

BATCH_SIZE = 20
MAX_OUTPUT_TOKENS = 4096
EXTRACT_THRESHOLD = 500

TICKER_KEYWORDS: dict[str, list[str]] = {
    "AAPL": ["apple", "iphone", "ipad", "mac", "tim cook", "app store"],
    "AMZN": ["amazon", "aws", "prime", "andy jassy"],
    "AMD": ["amd", "advanced micro", "radeon", "ryzen", "epyc", "instinct", "lisa su"],
    "BABA": ["alibaba", "taobao", "tmall", "alipay", "ant group", "alicloud"],
    "GOOGL": ["google", "alphabet", "youtube", "waymo", "gemini", "google cloud"],
    "META": ["meta", "facebook", "instagram", "whatsapp", "threads", "zuckerberg"],
    "MSFT": ["microsoft", "azure", "windows", "office", "copilot", "satya nadella"],
    "NVDA": ["nvidia", "jensen huang", "geforce", "rtx", "cuda", "h100", "h200", "blackwell", "dgx"],
    "TSLA": ["tesla", "elon musk", "model y", "model 3", "cybertruck", "fsd", "gigafactory"],
}

POSITIVE_TERMS = {
    "accelerate", "approval", "approved", "beat", "beats", "bullish", "buyback",
    "contract", "deal", "demand", "expand", "expanded", "gain", "gains",
    "growth", "higher", "launch", "leader", "outperform", "partnership",
    "profit", "record", "raise", "raised", "rebound", "rises", "strong",
    "upgrade", "upside", "win", "wins",
}

NEGATIVE_TERMS = {
    "antitrust", "bearish", "cut", "decline", "declines", "delay", "delayed",
    "downgrade", "drop", "falls", "fine", "investigation", "lawsuit", "loss",
    "miss", "misses", "probe", "recall", "risk", "risks", "selloff",
    "shortage", "slowdown", "slump", "tariff", "weak", "warning",
}


def _clip(text: str | None, limit: int) -> str:
    value = re.sub(r"\s+", " ", text or "").strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "..."


def _symbol_aliases(symbol: str) -> list[str]:
    aliases = {symbol.lower(), symbol.split(".")[0].lower()}
    aliases.update(TICKER_KEYWORDS.get(symbol.upper(), []))
    return sorted(aliases, key=len, reverse=True)


def _json_loads(value: str | None, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _extract_relevant_text(description: str | None, symbol: str) -> str:
    desc = (description or "").strip()
    if len(desc) < EXTRACT_THRESHOLD:
        return desc

    aliases = _symbol_aliases(symbol)
    sentences = re.split(r"(?<=[.!?])\s+", desc)
    keep: set[int] = set()
    for idx, sentence in enumerate(sentences):
        lower = sentence.lower()
        if any(alias in lower for alias in aliases):
            keep.update(range(max(0, idx - 1), min(len(sentences), idx + 2)))

    if not keep:
        return " ".join(sentences[:2])
    return " ".join(sentences[idx] for idx in sorted(keep))


def _normalize_sentiment(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in {"+", "positive", "bullish", "up", "slightly_positive"}:
        return "positive"
    if raw in {"-", "negative", "bearish", "down", "slightly_negative"}:
        return "negative"
    return "neutral"


def _normalize_relevance(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in {"y", "yes", "relevant", "high", "medium", "true", "1"}:
        return "relevant"
    return "irrelevant"


def _token_hits(text: str, terms: set[str]) -> list[str]:
    lower = text.lower()
    return sorted(term for term in terms if re.search(rf"\b{re.escape(term)}\b", lower))[:4]


def _polygon_insight(article: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    insights = _json_loads(article.get("insights_json"), [])
    aliases = {symbol.upper(), symbol.split(".")[0].upper()}
    if not isinstance(insights, list):
        return None
    for item in insights:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").upper()
        if ticker in aliases:
            return item
    return None


def _article_mentions_symbol(article: dict[str, Any], symbol: str) -> bool:
    tickers = _json_loads(article.get("tickers_json"), [])
    aliases_upper = {symbol.upper(), symbol.split(".")[0].upper()}
    if isinstance(tickers, list) and any(str(t).upper() in aliases_upper for t in tickers):
        return True

    text = f"{article.get('title') or ''} {article.get('description') or ''}".lower()
    return any(alias in text for alias in _symbol_aliases(symbol))


def _heuristic_label(symbol: str, article: dict[str, Any]) -> dict[str, Any]:
    title = article.get("title") or ""
    description = article.get("description") or ""
    text = f"{title} {description}"
    insight = _polygon_insight(article, symbol)

    relevant = bool(insight) or _article_mentions_symbol(article, symbol)
    if not relevant and article.get("trade_date"):
        relevant = True

    if insight:
        sentiment = _normalize_sentiment(str(insight.get("sentiment") or ""))
        insight_reason = str(insight.get("sentiment_reasoning") or "").strip()
        summary = _clip(insight_reason or title, 180)
        up_reason = summary if sentiment == "positive" else ""
        down_reason = summary if sentiment == "negative" else ""
    else:
        pos_hits = _token_hits(text, POSITIVE_TERMS)
        neg_hits = _token_hits(text, NEGATIVE_TERMS)
        if len(pos_hits) > len(neg_hits):
            sentiment = "positive"
        elif len(neg_hits) > len(pos_hits):
            sentiment = "negative"
        else:
            sentiment = "neutral"
        summary = _clip(title, 180)
        up_reason = f"Positive terms: {', '.join(pos_hits)}" if pos_hits else ""
        down_reason = f"Negative terms: {', '.join(neg_hits)}" if neg_hits else ""

    if not relevant:
        sentiment = "neutral"
        up_reason = ""
        down_reason = ""

    return {
        "news_id": article["id"],
        "symbol": symbol,
        "relevance": "relevant" if relevant else "irrelevant",
        "key_discussion": summary,
        "chinese_summary": summary,
        "sentiment": sentiment,
        "discussion": "SkyEye Layer 1 heuristic label.",
        "reason_growth": up_reason,
        "reason_decrease": down_reason,
        "engine": "heuristic",
    }


def _build_batch_prompt(symbol: str, articles: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for idx, article in enumerate(articles):
        extract = _extract_relevant_text(article.get("description"), symbol)
        lines.append(f"[{idx}] {article.get('title') or ''}")
        if extract:
            lines.append(f"  {extract}")

    return f"""You are SkyEye's financial news labeling engine.
Rate each article for {symbol}. Return a JSON array only.

{chr(10).join(lines)}

Schema:
[{{"i":0,"r":"y|n","s":"+|-|0","e":"short event summary","u":"bullish reason","d":"bearish reason"}}]

Rules:
- r=y only when the article materially discusses {symbol} or its business.
- s=+ for likely positive stock impact, s=- for likely negative stock impact, s=0 for neutral/mixed.
- Keep e/u/d concise. Use empty strings when irrelevant or no reason exists.
JSON:"""


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    start = text.find("[")
    end = text.rfind("]") + 1
    if start < 0 or end <= start:
        raise ValueError("No JSON array found in model response")
    data = json.loads(text[start:end])
    if not isinstance(data, list):
        raise ValueError("Model response is not a JSON array")
    return [item for item in data if isinstance(item, dict)]


def _call_skyeye_model(symbol: str, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from ai_analyzer import API_KEY, MODEL, _chat

    if not API_KEY:
        raise RuntimeError("No AI API key configured")

    text = _chat(
        "You are a precise financial news classifier. Return JSON only.",
        _build_batch_prompt(symbol, articles),
        max_tokens=MAX_OUTPUT_TOKENS,
    )
    if not text or text.startswith("Error:") or text.startswith("API error"):
        raise RuntimeError(f"{MODEL} request failed: {text[:180]}")
    return _extract_json_array(text)


def get_pending_articles(symbol: str, limit: int = 10000) -> list[dict[str, Any]]:
    """Return aligned, Layer-0-passed articles not yet labeled by Layer 1."""
    sym = symbol.upper()
    conn = get_conn()
    rows = conn.execute(
        """SELECT nr.id, nr.title, nr.description, nr.tickers_json, nr.insights_json,
                  na.trade_date, na.published_utc, l0.passed AS layer0_passed
           FROM news_aligned na
           JOIN news_raw nr ON nr.id = na.news_id
           LEFT JOIN layer0_results l0 ON l0.news_id = na.news_id AND l0.symbol = na.symbol
           WHERE na.symbol = ?
             AND COALESCE(l0.passed, 1) = 1
             AND NOT EXISTS (
                 SELECT 1 FROM layer1_results l1
                 WHERE l1.news_id = na.news_id AND l1.symbol = na.symbol
             )
           ORDER BY na.trade_date DESC, na.published_utc DESC
           LIMIT ?""",
        (sym, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def _save_labels(labels: list[dict[str, Any]]) -> dict[str, int]:
    stats = {"processed": 0, "relevant": 0, "irrelevant": 0, "positive": 0, "negative": 0, "neutral": 0}
    conn = get_conn()
    for label in labels:
        conn.execute(
            """INSERT OR REPLACE INTO layer1_results
               (news_id, symbol, relevance, key_discussion, chinese_summary,
                sentiment, discussion, reason_growth, reason_decrease)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                label["news_id"],
                label["symbol"],
                label["relevance"],
                label.get("key_discussion", ""),
                label.get("chinese_summary", ""),
                label["sentiment"],
                label.get("discussion", ""),
                label.get("reason_growth", ""),
                label.get("reason_decrease", ""),
            ),
        )
        stats["processed"] += 1
        if label["relevance"] == "relevant":
            stats["relevant"] += 1
        else:
            stats["irrelevant"] += 1
        stats[label["sentiment"]] += 1
    conn.commit()
    conn.close()
    return stats


def process_batch_group(symbol: str, articles: list[dict[str, Any]], engine: str = "auto") -> dict[str, int]:
    """Label and persist one batch. engine is auto, mimo, or heuristic."""
    sym = symbol.upper()
    stats = {
        "processed": 0,
        "relevant": 0,
        "irrelevant": 0,
        "positive": 0,
        "negative": 0,
        "neutral": 0,
        "errors": 0,
        "ai_batches": 0,
        "fallback_batches": 0,
    }

    labels: list[dict[str, Any]] = []
    if engine in {"auto", "mimo"}:
        try:
            results = _call_skyeye_model(sym, articles)
            by_index = {int(item.get("i")): item for item in results if item.get("i") is not None}
            for idx, article in enumerate(articles):
                item = by_index.get(idx)
                if not item:
                    labels.append(_heuristic_label(sym, article))
                    continue
                relevance = _normalize_relevance(str(item.get("r") or ""))
                sentiment = _normalize_sentiment(str(item.get("s") or ""))
                if relevance == "irrelevant":
                    sentiment = "neutral"
                labels.append(
                    {
                        "news_id": article["id"],
                        "symbol": sym,
                        "relevance": relevance,
                        "key_discussion": _clip(item.get("e"), 180),
                        "chinese_summary": _clip(item.get("e"), 180),
                        "sentiment": sentiment,
                        "discussion": "SkyEye Layer 1 model label.",
                        "reason_growth": _clip(item.get("u"), 220),
                        "reason_decrease": _clip(item.get("d"), 220),
                        "engine": "mimo",
                    }
                )
            stats["ai_batches"] = 1
        except Exception:
            if engine == "mimo":
                stats["errors"] = len(articles)
                return stats
            labels = [_heuristic_label(sym, article) for article in articles]
            stats["fallback_batches"] = 1
    else:
        labels = [_heuristic_label(sym, article) for article in articles]
        stats["fallback_batches"] = 1

    saved = _save_labels(labels)
    stats.update(saved)
    return stats


def run_layer1(
    symbol: str,
    max_articles: int = 10000,
    engine: str = "auto",
    batch_size: int = BATCH_SIZE,
    run_layer0_first: bool = True,
) -> dict[str, Any]:
    """Run SkyEye Layer 1 on pending articles for one symbol."""
    sym = symbol.upper()
    if engine not in {"auto", "mimo", "heuristic"}:
        raise ValueError("engine must be auto, mimo, or heuristic")
    if run_layer0_first:
        layer0_stats = run_layer0(sym)
    else:
        layer0_stats = None

    articles = get_pending_articles(sym, limit=max_articles)
    if not articles:
        return {"status": "no_pending", "symbol": sym, "total": 0, "layer0": layer0_stats}

    total = {
        "status": "complete",
        "symbol": sym,
        "total": len(articles),
        "processed": 0,
        "relevant": 0,
        "irrelevant": 0,
        "positive": 0,
        "negative": 0,
        "neutral": 0,
        "errors": 0,
        "api_calls": 0,
        "fallback_batches": 0,
        "engine": engine,
        "layer0": layer0_stats,
    }

    for start in range(0, len(articles), max(1, batch_size)):
        chunk = articles[start : start + batch_size]
        stats = process_batch_group(sym, chunk, engine=engine)
        for key in ("processed", "relevant", "irrelevant", "positive", "negative", "neutral", "errors"):
            total[key] += stats.get(key, 0)
        total["api_calls"] += stats.get("ai_batches", 0)
        total["fallback_batches"] += stats.get("fallback_batches", 0)
        print(
            f"[{sym}] Layer 1 {total['processed']}/{total['total']} "
            f"processed, {total['relevant']} relevant"
        )

    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SkyEye Layer 1 news sentiment labeling.")
    parser.add_argument("symbol", help="Ticker symbol, e.g. NVDA")
    parser.add_argument("--limit", type=int, default=100, help="Maximum pending articles to process")
    parser.add_argument("--engine", choices=["auto", "mimo", "heuristic"], default="auto")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args()
    result = run_layer1(args.symbol, args.limit, args.engine, args.batch_size)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
