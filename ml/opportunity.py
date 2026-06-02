"""Opportunity radar aggregation for SkyEye.

This layer turns existing news, events, supply-chain themes, catalysts, and
trade setups into research alerts that can feed paper trading. It does not
create live trading instructions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha1
from statistics import mean

from database import get_conn


AUTHORITY_SOURCES = {
    "bloomberg",
    "hkex",
    "federal reserve",
    "sec",
    "cnbc",
    "marketwatch",
    "yahoo finance",
}

THEME_CONFIGS = [
    {
        "key": "hk_ipo",
        "label": "港股打新 / New Economy IPO",
        "market": "hk",
        "keywords": ["港股", "打新", "ipo", "招股", "聆讯", "港交所", "hkex", "listing"],
        "fallback_symbols": ["0100.HK", "0700.HK", "9988.HK", "3690.HK", "9618.HK", "1810.HK"],
        "base_risks": ["上市前后利好可能快速兑现", "孖展热度过高时首日波动会放大"],
    },
    {
        "key": "ai_apps",
        "label": "AI应用与新模型发布 / AI Apps",
        "market": "hk",
        "keywords": ["minimax", "m3", "ai agent", "新模型", "模型发布", "产品发布", "海螺", "大模型应用"],
        "fallback_symbols": ["0100.HK", "0700.HK", "9988.HK", "1810.HK"],
        "base_risks": ["产品发布前预期可能已反映在股价里", "发布后口碑不及预期会触发止盈"],
    },
    {
        "key": "ai_hbm",
        "label": "AI算力与HBM / AI Compute",
        "market": "us",
        "keywords": ["ai", "hbm", "gpu", "semiconductor", "chip", "算力", "大模型", "芯片"],
        "fallback_symbols": ["NVDA", "AMD", "AVGO", "MSFT", "AMZN"],
        "base_risks": ["AI 预期拥挤，财报兑现不及预期会放大回撤", "供应链瓶颈可能改变受益顺序"],
    },
    {
        "key": "robotics_auto",
        "label": "机器人与自动驾驶 / Robotics",
        "market": "us",
        "keywords": ["robotaxi", "robot", "autonomous", "自动驾驶", "机器人", "fsd", "lidar"],
        "fallback_symbols": ["TSLA", "NVDA", "MBLY", "LAZR"],
        "base_risks": ["技术演示到商业交付可能存在时间差", "监管牌照和安全事件会改变节奏"],
    },
    {
        "key": "crypto_infra",
        "label": "加密与稳定币基础设施 / Crypto Infra",
        "market": "us",
        "keywords": ["crypto", "bitcoin", "stablecoin", "blockchain", "btc", "加密", "稳定币"],
        "fallback_symbols": ["COIN", "MSTR", "HOOD", "SQ"],
        "base_risks": ["监管标题和币价波动会直接影响估值", "链上活跃度回落会削弱基础设施叙事"],
    },
    {
        "key": "macro_liquidity",
        "label": "宏观流动性 / Macro Liquidity",
        "market": "all",
        "keywords": ["fed", "rate", "liquidity", "treasury", "yield", "inflation", "央行", "降息", "流动性"],
        "fallback_symbols": ["MSFT", "AAPL", "0700.HK", "9988.HK"],
        "base_risks": ["宏观方向对成长股估值影响大", "数据发布日前后容易出现反向波动"],
    },
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _round(value, digits: int = 4):
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _market_for_symbol(symbol: str) -> str:
    sym = (symbol or "").upper()
    if sym.endswith(".HK"):
        return "hk"
    if sym.startswith("^") or sym.endswith("=F") or sym.endswith("-USD"):
        return "observe"
    if "." in sym:
        return "observe"
    return "us"


def _latest_close(symbol: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT date, close
               FROM ohlc
               WHERE symbol = ?
               ORDER BY date DESC
               LIMIT 1""",
            (symbol.upper(),),
        ).fetchone()
    finally:
        conn.close()
    if not row or row["close"] is None:
        return _latest_close_from_yfinance(symbol)
    return {"date": row["date"], "close": float(row["close"])}


@lru_cache(maxsize=128)
def _latest_close_from_yfinance(symbol: str) -> dict | None:
    try:
        import yfinance as yf

        hist = yf.Ticker(symbol).history(period="10d", interval="1d", auto_adjust=False)
        if hist is None or hist.empty or "Close" not in hist:
            return None
        closes = hist["Close"].dropna()
        if closes.empty:
            return None
        idx = closes.index[-1]
        date = idx.date().isoformat() if hasattr(idx, "date") else str(idx)[:10]
        return {"date": date, "close": float(closes.iloc[-1])}
    except Exception:
        return None


def _age_days(value: str | None) -> int | None:
    if not value:
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except Exception:
        try:
            d = datetime.strptime(value[:10], "%Y-%m-%d").date()
        except Exception:
            return None
    return max(0, (datetime.now(timezone.utc).date() - d).days)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = str(item or "").strip().upper()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _dedupe_text(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = str(item or "").strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _symbol_allowed_for_paper(symbol: str) -> bool:
    market = _market_for_symbol(symbol)
    return market in {"hk", "us"} and _latest_close(symbol) is not None


def _suggested_action(symbols: list[str], alert_id: str, score: int) -> dict:
    for symbol in symbols:
        market = _market_for_symbol(symbol)
        if market not in {"hk", "us"}:
            continue
        if not _latest_close(symbol):
            continue
        book_id = "hkd" if market == "hk" else "usd"
        notional = 50000.0 if book_id == "hkd" else 2000.0
        if score >= 75:
            notional *= 1.5
        return {
            "allowed": True,
            "book_id": book_id,
            "symbol": symbol,
            "side": "buy",
            "notional": round(notional, 2),
            "reason": f"Paper test from opportunity alert {alert_id}",
        }
    return {
        "allowed": False,
        "book_id": None,
        "symbol": None,
        "side": "observe",
        "notional": 0.0,
        "reason": "No eligible HK/US equity with current OHLC price is available.",
    }


def _news_for_theme(news: list[dict], keywords: list[str], limit: int = 5) -> list[dict]:
    matches = []
    lowered = [kw.lower() for kw in keywords]
    for article in news:
        text = f"{article.get('title', '')} {article.get('summary', '')} {article.get('feed_category', '')}".lower()
        tags = " ".join(str(tag.get("key") or tag.get("value") or "").lower() for tag in article.get("tags", []))
        if any(kw in text or kw in tags for kw in lowered):
            matches.append(article)
    return matches[:limit]


def _event_for_theme(events: list[dict], keywords: list[str], limit: int = 3) -> list[dict]:
    lowered = [kw.lower() for kw in keywords]
    result = []
    for item in events:
        text = f"{item.get('title', '')} {item.get('summary', '')} {item.get('category', '')}".lower()
        if any(kw in text for kw in lowered):
            result.append(item)
    return result[:limit]


def _chain_for_theme(key: str, supply_chains: list[dict]) -> dict | None:
    mapping = {
        "hk_ipo": "港股打新",
        "ai_apps": "AI应用",
        "ai_hbm": "AI算力",
        "robotics_auto": "机器人",
        "crypto_infra": "加密",
    }
    needle = mapping.get(key)
    if not needle:
        return None
    return next((chain for chain in supply_chains if needle in chain.get("theme", "")), None)


def _score_alert(news_items: list[dict], events: list[dict], catalysts: list[dict], chain: dict | None) -> dict:
    sources = {str(item.get("source") or "").lower() for item in news_items}
    source_quality = 12 + min(8, sum(1 for src in sources if any(auth in src for auth in AUTHORITY_SOURCES)) * 3)
    ages = [_age_days(item.get("published")) for item in news_items] + [_age_days(item.get("date")) for item in events]
    ages = [age for age in ages if age is not None]
    freshest = min(ages) if ages else None
    freshness = 20 if freshest is not None and freshest <= 1 else 15 if freshest is not None and freshest <= 3 else 9 if freshest is not None and freshest <= 10 else 4
    sentiment_bias = sum(1 for item in news_items if item.get("sentiment") in {"positive", "slightly_positive"}) - sum(1 for item in news_items if item.get("sentiment") in {"negative", "slightly_negative"})
    news_strength = min(20, len(news_items) * 3 + len(events) * 4 + max(0, sentiment_bias) * 2)
    catalyst_scores = [float(row.get("score") or 0.0) for row in catalysts]
    catalyst_trends = [abs(float(row.get("trend_5d") or 0.0)) for row in catalysts if row.get("trend_5d") is not None]
    price_reaction = min(20, (mean(catalyst_scores) / 5 if catalyst_scores else 0) + (mean(catalyst_trends) * 180 if catalyst_trends else 0))
    chain_relevance = 18 if chain else 10
    crowding_penalty = min(12, max(0, len(news_items) - 6) * 1.5 + sum(1 for row in catalysts if int(row.get("news_count") or 0) > 35) * 3)
    risk_penalty = min(12, sum(1 for item in news_items if item.get("sentiment") in {"negative", "slightly_negative"}) * 2)
    score = round(source_quality + freshness + news_strength + price_reaction + chain_relevance - crowding_penalty - risk_penalty)
    return {
        "score": int(max(0, min(100, score))),
        "score_components": {
            "source_quality": _round(source_quality, 2),
            "freshness": _round(freshness, 2),
            "news_strength": _round(news_strength, 2),
            "price_reaction": _round(price_reaction, 2),
            "chain_relevance": _round(chain_relevance, 2),
            "crowding_penalty": _round(crowding_penalty, 2),
            "risk_penalty": _round(risk_penalty, 2),
        },
    }


def _alert_id(theme_key: str, symbols: list[str], title: str) -> str:
    digest = sha1(f"{theme_key}:{','.join(symbols)}:{title}".encode("utf-8")).hexdigest()[:10]
    return f"{theme_key}-{digest}"


def _build_alert(config: dict, news_items: list[dict], events: list[dict], catalyst_rows: list[dict], setup_rows: list[dict], chain: dict | None) -> dict:
    chain_symbols = []
    if chain:
        chain_symbols.extend(chain.get("hk_tickers") or [])
        chain_symbols.extend(chain.get("us_tickers") or [])
    catalyst_symbols = [row.get("symbol") for row in catalyst_rows]
    setup_symbols = [row.get("symbol") for row in setup_rows if row.get("status") in {"candidate", "paper-watch"}]
    primary_symbols = _dedupe(setup_symbols + catalyst_symbols + chain_symbols + config.get("fallback_symbols", []))[:8]
    market = config["market"]
    if market == "hk":
        primary_symbols = [s for s in primary_symbols if _market_for_symbol(s) == "hk"] or config["fallback_symbols"]
    elif market == "us":
        primary_symbols = [s for s in primary_symbols if _market_for_symbol(s) == "us"] or config["fallback_symbols"]
    related_symbols = _dedupe(chain_symbols + config.get("fallback_symbols", []))[:12]
    headline = (news_items[0].get("title") if news_items else None) or (events[0].get("title") if events else None) or config["label"]
    score_data = _score_alert(news_items, events, catalyst_rows, chain)
    score = score_data["score"]
    signal_level = "strong" if score >= 72 else "watch"
    alert_id = _alert_id(config["key"], primary_symbols, headline)
    evidence = []
    for item in news_items[:4]:
        evidence.append({
            "type": "news",
            "title": item.get("title") or "",
            "source": item.get("source") or "",
            "published": item.get("published") or "",
            "url": item.get("url") or "",
            "sentiment": item.get("sentiment") or "neutral",
        })
    for item in events[:2]:
        evidence.append({
            "type": "event",
            "title": item.get("title") or "",
            "source": item.get("source") or item.get("category") or "",
            "published": item.get("date") or "",
            "url": "",
            "sentiment": item.get("impact") or "neutral",
        })
    for row in catalyst_rows[:3]:
        evidence.append({
            "type": "catalyst",
            "title": f"{row.get('symbol')} {row.get('label')} score {row.get('score')}",
            "source": "Catalyst Radar",
            "published": row.get("latest_trade_date") or "",
            "url": "",
            "sentiment": row.get("bias") or "neutral",
        })
    risks = list(config.get("base_risks", []))
    if chain and chain.get("risk"):
        risks.append(chain["risk"])
    if any(row.get("bias") == "bearish" for row in catalyst_rows):
        risks.append("部分核心标的近期催化偏空，模拟交易前先确认个股风险。")
    return {
        "id": alert_id,
        "theme": config["key"],
        "theme_label": config["label"],
        "market": market,
        "signal_level": signal_level,
        "score": score,
        "score_components": score_data["score_components"],
        "title": headline,
        "thesis": f"{config['label']} 出现新闻/事件/价格反应共振，适合进入 paper 观察队列。",
        "evidence": evidence,
        "primary_symbols": primary_symbols,
        "related_symbols": related_symbols,
        "risks": _dedupe_text(risks)[:5],
        "suggested_paper_action": _suggested_action(primary_symbols, alert_id, score),
        "eligible_paper_symbols": [
            {
                "symbol": symbol,
                "book_id": "hkd" if _market_for_symbol(symbol) == "hk" else "usd",
                "notional": 50000.0 if _market_for_symbol(symbol) == "hk" else 2000.0,
            }
            for symbol in primary_symbols
            if _symbol_allowed_for_paper(symbol)
        ][:6],
    }


def _filter_market_alerts(alerts: list[dict], market: str) -> list[dict]:
    if market == "all":
        return alerts
    return [
        alert for alert in alerts
        if alert.get("market") == market or any(_market_for_symbol(sym) == market for sym in alert.get("primary_symbols", []))
    ]


def build_opportunity_radar(market: str = "all", lookback_days: int = 10, mode: str = "balanced") -> dict:
    market = market if market in {"all", "hk", "us"} else "all"
    lookback_days = max(3, min(int(lookback_days or 10), 45))
    try:
        from routers.geopolitical import fetch_all_news
        news = fetch_all_news()
        news_error = None
    except Exception as exc:
        news = []
        news_error = str(exc)

    try:
        from routers.events import SUPPLY_CHAIN_THEMES, UPCOMING_IPOS, _generate_events
        events = _generate_events()
        ipos = UPCOMING_IPOS
        chains = SUPPLY_CHAIN_THEMES
        event_error = None
    except Exception as exc:
        events, ipos, chains = [], [], []
        event_error = str(exc)

    try:
        from ml.catalyst import build_catalyst_radar
        catalyst = build_catalyst_radar(lookback_days=lookback_days, limit=12)
        catalyst_rows = catalyst.get("rows", [])
        catalyst_error = None
    except Exception as exc:
        catalyst = {}
        catalyst_rows = []
        catalyst_error = str(exc)

    try:
        from ml.trade_setup import build_trade_setups
        trade = build_trade_setups(capital=100000.0, lookback_days=lookback_days, limit=8)
        setup_rows = trade.get("rows", [])
        trade_error = None
    except Exception as exc:
        trade = {}
        setup_rows = []
        trade_error = str(exc)

    alerts = []
    themes = []
    for config in THEME_CONFIGS:
        chain = _chain_for_theme(config["key"], chains)
        theme_news = _news_for_theme(news, config["keywords"])
        theme_events = _event_for_theme(events, config["keywords"])
        if config["key"] == "hk_ipo":
            theme_events = theme_events + [
                {"title": f"{ipo['name']} IPO", "summary": ipo.get("description", ""), "date": ipo.get("expected_date"), "category": ipo.get("sector"), "related_stocks": ipo.get("related_tickers", [])}
                for ipo in ipos[:3]
            ]
        theme_symbols = set(config.get("fallback_symbols", []))
        if chain:
            theme_symbols.update(chain.get("hk_tickers") or [])
            theme_symbols.update(chain.get("us_tickers") or [])
        related_catalysts = [row for row in catalyst_rows if row.get("symbol") in theme_symbols]
        related_setups = [row for row in setup_rows if row.get("symbol") in theme_symbols]
        alert = _build_alert(config, theme_news, theme_events, related_catalysts, related_setups, chain)
        alerts.append(alert)
        themes.append({
            "key": config["key"],
            "label": config["label"],
            "market": config["market"],
            "alert_count": 1,
            "strong_count": 1 if alert["signal_level"] == "strong" else 0,
            "watch_count": 1 if alert["signal_level"] == "watch" else 0,
            "top_score": alert["score"],
            "primary_symbols": alert["primary_symbols"][:5],
        })

    alerts = _filter_market_alerts(alerts, market)
    alerts.sort(key=lambda item: (item["signal_level"] == "strong", item["score"]), reverse=True)
    strong = sum(1 for item in alerts if item["signal_level"] == "strong")
    watch = sum(1 for item in alerts if item["signal_level"] == "watch")
    eligible = sum(len(item.get("eligible_paper_symbols") or []) for item in alerts)
    return {
        "generated_at": _now_iso(),
        "market": market,
        "lookback_days": lookback_days,
        "mode": mode,
        "summary": {
            "themes": len(themes),
            "alerts": len(alerts),
            "strong": strong,
            "watch": watch,
            "paper_eligible_symbols": eligible,
            "top_theme": alerts[0]["theme"] if alerts else None,
            "top_score": alerts[0]["score"] if alerts else None,
        },
        "themes": themes,
        "alerts": alerts,
        "data_quality": {
            "news_count": len(news),
            "event_count": len(events),
            "ipo_count": len(ipos),
            "catalyst_rows": len(catalyst_rows),
            "trade_setup_rows": len(setup_rows),
            "rss_error": news_error,
            "event_error": event_error,
            "catalyst_error": catalyst_error,
            "trade_setup_error": trade_error,
            "notes": [
                "Radar is research and paper-trading only.",
                "HKD and USD paper books are not FX-converted.",
            ],
        },
        "sources": {
            "catalyst_status": catalyst.get("status"),
            "trade_setup_status": trade.get("status"),
        },
    }
