"""Catalyst radar for SkyEye sentiment and event-driven research."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import log1p
from statistics import mean

from database import get_conn
from ml.decision import DEFAULT_UNIVERSE


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _round(value, digits: int = 4):
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _dedupe_symbols(symbols: list[str] | None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for symbol in symbols or []:
        sym = str(symbol or "").strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        result.append(sym)
    return result


def _db_universe(limit: int) -> list[str]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT na.symbol,
                      COUNT(DISTINCT na.news_id) AS aligned_news,
                      COUNT(DISTINCT l1.news_id) AS analyzed_news,
                      COUNT(DISTINCT o.date) AS ohlc_rows
               FROM news_aligned na
               JOIN ohlc o ON o.symbol = na.symbol
               LEFT JOIN layer1_results l1 ON l1.news_id = na.news_id AND l1.symbol = na.symbol
               GROUP BY na.symbol
               HAVING ohlc_rows >= 120
               ORDER BY analyzed_news DESC, aligned_news DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    symbols = [row["symbol"] for row in rows]
    return _dedupe_symbols(symbols) or DEFAULT_UNIVERSE[:limit]


def _latest_trade_date(symbols: list[str]) -> str | None:
    if not symbols:
        return None
    placeholders = ",".join("?" for _ in symbols)
    conn = get_conn()
    try:
        row = conn.execute(
            f"SELECT MAX(trade_date) AS latest_trade_date FROM news_aligned WHERE symbol IN ({placeholders})",
            tuple(symbols),
        ).fetchone()
    finally:
        conn.close()
    return row["latest_trade_date"] if row else None


def _date_floor(latest_trade_date: str | None, lookback_days: int) -> str:
    if not latest_trade_date:
        return "1900-01-01"
    latest = datetime.strptime(latest_trade_date[:10], "%Y-%m-%d").date()
    return (latest - timedelta(days=lookback_days)).strftime("%Y-%m-%d")


def _latest_close(symbol: str) -> dict:
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT date, close
               FROM ohlc
               WHERE symbol = ?
               ORDER BY date DESC
               LIMIT 1""",
            (symbol,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return {"date": None, "close": None}
    return {"date": row["date"], "close": _round(row["close"], 4)}


def _trend(symbol: str, days: int) -> float | None:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT close
               FROM ohlc
               WHERE symbol = ?
               ORDER BY date DESC
               LIMIT ?""",
            (symbol, days + 1),
        ).fetchall()
    finally:
        conn.close()
    if len(rows) <= days:
        return None
    latest = float(rows[0]["close"] or 0.0)
    start = float(rows[-1]["close"] or 0.0)
    if not start:
        return None
    return latest / start - 1.0


def _sentiment_counts(rows: list[dict]) -> dict:
    positive = sum(1 for row in rows if row.get("sentiment") == "positive")
    negative = sum(1 for row in rows if row.get("sentiment") == "negative")
    neutral = sum(1 for row in rows if row.get("sentiment") not in {"positive", "negative"})
    total = len(rows)
    ratio = (positive - negative) / total if total else 0.0
    return {
        "total": total,
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "ratio": ratio,
    }


def _bias(ratio: float, trend_5d: float | None, positive: int, negative: int) -> tuple[str, str]:
    if ratio >= 0.2 and (trend_5d is None or trend_5d >= -0.03):
        return "bullish", "Bullish"
    if ratio <= -0.15 or (negative >= 2 and trend_5d is not None and trend_5d < -0.03):
        return "bearish", "Bearish"
    if positive and negative:
        return "mixed", "Mixed"
    return "neutral", "Neutral"


def _catalyst_score(
    counts: dict,
    avg_abs_ret_t0: float | None,
    avg_abs_ret_t1: float | None,
    avg_abs_ret_t5: float | None,
    latest_age: int | None,
    pending: int,
) -> int:
    total = int(counts.get("total") or 0)
    ratio = abs(float(counts.get("ratio") or 0.0))
    volume_score = min(35.0, log1p(total) * 11.0)
    sentiment_score = min(25.0, ratio * 45.0)
    impact = avg_abs_ret_t1 if avg_abs_ret_t1 is not None else avg_abs_ret_t0 if avg_abs_ret_t0 is not None else avg_abs_ret_t5
    impact_score = min(25.0, float(impact or 0.0) * 260.0)
    freshness_score = 10.0 if latest_age is not None and latest_age <= 2 else 5.0 if latest_age is not None and latest_age <= 5 else 0.0
    pending_penalty = min(12.0, pending * 1.5)
    return int(max(0, min(100, round(volume_score + sentiment_score + impact_score + freshness_score - pending_penalty))))


def _status(score: int, pending: int, total: int) -> tuple[str, str, str]:
    if total == 0:
        return "quiet", "Quiet", "No recent aligned news catalyst is available."
    if pending >= max(3, total // 2):
        return "needs-labels", "Needs Labels", "Recent news needs Layer 1 sentiment labels before the catalyst read is reliable."
    if score >= 70:
        return "hot", "Hot Catalyst", "A high-volume or high-impact catalyst cluster needs active review."
    if score >= 45:
        return "watch", "Watch", "Recent catalysts are visible; inspect headlines and price reaction."
    return "quiet", "Quiet", "Recent catalyst activity is modest."


def _headline_rows(symbol: str, start_date: str, limit: int = 4) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT na.trade_date,
                      nr.title,
                      nr.publisher,
                      nr.article_url,
                      COALESCE(l1.sentiment, 'neutral') AS sentiment,
                      COALESCE(l1.relevance, '') AS relevance,
                      COALESCE(l1.key_discussion, l1.chinese_summary, '') AS summary,
                      na.ret_t0,
                      na.ret_t1,
                      na.ret_t5
               FROM news_aligned na
               JOIN news_raw nr ON nr.id = na.news_id
               LEFT JOIN layer1_results l1 ON l1.news_id = na.news_id AND l1.symbol = na.symbol
               WHERE na.symbol = ? AND na.trade_date >= ?
               ORDER BY na.trade_date DESC,
                        CASE COALESCE(l1.sentiment, 'neutral')
                            WHEN 'negative' THEN 0
                            WHEN 'positive' THEN 1
                            ELSE 2
                        END,
                        nr.published_utc DESC
               LIMIT ?""",
            (symbol, start_date, limit),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "date": row["trade_date"],
            "title": row["title"] or "",
            "publisher": row["publisher"] or "",
            "url": row["article_url"] or "",
            "sentiment": row["sentiment"] or "neutral",
            "relevance": row["relevance"] or "",
            "summary": row["summary"] or "",
            "ret_t0": _round(row["ret_t0"]),
            "ret_t1": _round(row["ret_t1"]),
            "ret_t5": _round(row["ret_t5"]),
        }
        for row in rows
    ]


def _symbol_row(symbol: str, start_date: str, latest_trade_date: str | None) -> dict:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT na.news_id,
                      na.trade_date,
                      COALESCE(l1.sentiment, 'neutral') AS sentiment,
                      na.ret_t0,
                      na.ret_t1,
                      na.ret_t5
               FROM news_aligned na
               LEFT JOIN layer1_results l1 ON l1.news_id = na.news_id AND l1.symbol = na.symbol
               WHERE na.symbol = ? AND na.trade_date >= ?""",
            (symbol, start_date),
        ).fetchall()
        pending = conn.execute(
            """SELECT COUNT(DISTINCT na.news_id)
               FROM news_aligned na
               LEFT JOIN layer0_results l0 ON l0.news_id = na.news_id AND l0.symbol = na.symbol
               WHERE na.symbol = ?
                 AND na.trade_date >= ?
                 AND COALESCE(l0.passed, 1) = 1
                 AND NOT EXISTS (
                     SELECT 1 FROM layer1_results l1
                     WHERE l1.news_id = na.news_id AND l1.symbol = na.symbol
                 )""",
            (symbol, start_date),
        ).fetchone()[0]
    finally:
        conn.close()

    dict_rows = [dict(row) for row in rows]
    counts = _sentiment_counts(dict_rows)
    ret_t0 = [abs(float(row["ret_t0"])) for row in rows if row["ret_t0"] is not None]
    ret_t1 = [abs(float(row["ret_t1"])) for row in rows if row["ret_t1"] is not None]
    ret_t5 = [abs(float(row["ret_t5"])) for row in rows if row["ret_t5"] is not None]
    signed_t0 = [float(row["ret_t0"]) for row in rows if row["ret_t0"] is not None]
    signed_t1 = [float(row["ret_t1"]) for row in rows if row["ret_t1"] is not None]
    signed_t5 = [float(row["ret_t5"]) for row in rows if row["ret_t5"] is not None]
    latest_date = max((row["trade_date"] for row in rows), default=None)
    latest_age = None
    if latest_date and latest_trade_date:
        latest_age = (
            datetime.strptime(latest_trade_date[:10], "%Y-%m-%d").date()
            - datetime.strptime(latest_date[:10], "%Y-%m-%d").date()
        ).days
    trend_5d = _trend(symbol, 5)
    trend_20d = _trend(symbol, 20)
    bias, bias_label = _bias(counts["ratio"], trend_5d, counts["positive"], counts["negative"])
    avg_abs_ret_t0 = mean(ret_t0) if ret_t0 else None
    avg_abs_ret_t1 = mean(ret_t1) if ret_t1 else None
    avg_abs_ret_t5 = mean(ret_t5) if ret_t5 else None
    score = _catalyst_score(counts, avg_abs_ret_t0, avg_abs_ret_t1, avg_abs_ret_t5, latest_age, int(pending or 0))
    status, label, message = _status(score, int(pending or 0), counts["total"])

    if status == "needs-labels":
        action = "Run Layer 1 sentiment labeling before using this catalyst in research decisions."
    elif bias == "bullish" and score >= 45:
        action = "Open the symbol, compare headline drivers with trend, risk brief, and paper sizing."
    elif bias == "bearish" and score >= 45:
        action = "Review downside headlines, current drawdown, and any real exposure before adding risk."
    elif bias == "mixed":
        action = "Read both positive and negative headlines; mixed catalysts can reverse quickly."
    else:
        action = "Keep on passive watch unless price or news volume expands."

    price = _latest_close(symbol)
    return {
        "symbol": symbol,
        "status": status,
        "label": label,
        "message": message,
        "action": action,
        "score": score,
        "bias": bias,
        "bias_label": bias_label,
        "latest_trade_date": latest_date,
        "latest_close": price["close"],
        "price_date": price["date"],
        "news_count": counts["total"],
        "positive": counts["positive"],
        "negative": counts["negative"],
        "neutral": counts["neutral"],
        "sentiment_ratio": _round(counts["ratio"]),
        "pending_labels": int(pending or 0),
        "avg_abs_ret_t0": _round(avg_abs_ret_t0),
        "avg_abs_ret_t1": _round(avg_abs_ret_t1),
        "avg_abs_ret_t5": _round(avg_abs_ret_t5),
        "avg_ret_t0": _round(mean(signed_t0)) if signed_t0 else None,
        "avg_ret_t1": _round(mean(signed_t1)) if signed_t1 else None,
        "avg_ret_t5": _round(mean(signed_t5)) if signed_t5 else None,
        "trend_5d": _round(trend_5d),
        "trend_20d": _round(trend_20d),
        "headlines": _headline_rows(symbol, start_date),
    }


def build_catalyst_radar(symbols: list[str] | None = None, lookback_days: int = 10, limit: int = 10) -> dict:
    limit = max(1, min(int(limit or 10), 25))
    lookback_days = max(3, min(int(lookback_days or 10), 45))
    selected = _dedupe_symbols(symbols)[:limit] if symbols else _db_universe(limit)
    latest_trade_date = _latest_trade_date(selected)
    start_date = _date_floor(latest_trade_date, lookback_days)
    rows = [_symbol_row(symbol, start_date, latest_trade_date) for symbol in selected]
    rows.sort(key=lambda row: (row["score"], row["news_count"], abs(row.get("sentiment_ratio") or 0.0)), reverse=True)
    for index, row in enumerate(rows, start=1):
        row["rank"] = index

    hot = sum(1 for row in rows if row["status"] == "hot")
    watch = sum(1 for row in rows if row["status"] == "watch")
    needs_labels = sum(1 for row in rows if row["status"] == "needs-labels")
    bullish = sum(1 for row in rows if row["bias"] == "bullish")
    bearish = sum(1 for row in rows if row["bias"] == "bearish")
    total_articles = sum(row["news_count"] for row in rows)
    pending_labels = sum(row["pending_labels"] for row in rows)
    top = rows[0] if rows else None

    if hot:
        status = "hot"
        label = "Hot Catalysts"
        message = "Several symbols have fresh catalyst clusters with meaningful sentiment or price reaction."
    elif needs_labels:
        status = "needs-labels"
        label = "Needs Labels"
        message = "Recent news exists, but sentiment labeling needs to catch up before readings are reliable."
    elif watch:
        status = "watch"
        label = "Watch"
        message = "Catalysts are visible, but none require urgent action yet."
    else:
        status = "quiet"
        label = "Quiet"
        message = "No strong catalyst cluster is active across the current research universe."

    return {
        "generated_at": _now_iso(),
        "lookback_days": lookback_days,
        "start_date": start_date,
        "latest_trade_date": latest_trade_date,
        "status": status,
        "label": label,
        "message": message,
        "summary": {
            "symbols": len(rows),
            "hot": hot,
            "watch": watch,
            "needs_labels": needs_labels,
            "bullish": bullish,
            "bearish": bearish,
            "total_articles": total_articles,
            "pending_labels": pending_labels,
            "top_symbol": top["symbol"] if top else None,
            "top_score": top["score"] if top else None,
        },
        "rows": rows,
    }
