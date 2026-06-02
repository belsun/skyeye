"""Decision board aggregation for SkyEye research workflows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean

from database import get_conn
from ml.risk import build_risk_brief


DEFAULT_UNIVERSE = ["NVDA", "MSFT", "AMZN", "GOOGL", "AAPL", "META", "TSLA", "AMD", "AVGO", "PLTR"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _pct(value):
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _age_days(date_text: str | None) -> int | None:
    if not date_text:
        return None
    try:
        dt = datetime.strptime(date_text[:10], "%Y-%m-%d").date()
        return max(0, (datetime.now(timezone.utc).date() - dt).days)
    except Exception:
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


def _db_universe_symbols(limit: int) -> list[str]:
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
        symbols = [row["symbol"] for row in rows]
    finally:
        conn.close()
    return _dedupe_symbols(symbols) or DEFAULT_UNIVERSE[:limit]


def _coverage(symbol: str) -> dict:
    conn = get_conn()
    try:
        ohlc = conn.execute(
            """SELECT COUNT(*) AS rows_count,
                      MIN(date) AS first_ohlc_date,
                      MAX(date) AS latest_ohlc_date
               FROM ohlc
               WHERE symbol = ?""",
            (symbol,),
        ).fetchone()
        aligned_news = conn.execute(
            "SELECT COUNT(DISTINCT news_id) FROM news_aligned WHERE symbol = ?",
            (symbol,),
        ).fetchone()[0]
        analyzed_news = conn.execute(
            "SELECT COUNT(*) FROM layer1_results WHERE symbol = ?",
            (symbol,),
        ).fetchone()[0]
        pending_news = conn.execute(
            """SELECT COUNT(DISTINCT na.news_id)
               FROM news_aligned na
               LEFT JOIN layer0_results l0 ON l0.news_id = na.news_id AND l0.symbol = na.symbol
               WHERE na.symbol = ?
                 AND COALESCE(l0.passed, 1) = 1
                 AND NOT EXISTS (
                     SELECT 1 FROM layer1_results l1
                     WHERE l1.news_id = na.news_id AND l1.symbol = na.symbol
                 )""",
            (symbol,),
        ).fetchone()[0]
    finally:
        conn.close()

    labelable = int(analyzed_news or 0) + int(pending_news or 0)
    label_coverage = (analyzed_news / labelable) if labelable else None
    ohlc_age = _age_days(ohlc["latest_ohlc_date"] if ohlc else None)
    issues: list[str] = []

    if int(ohlc["rows_count"] or 0) < 200:
        issues.append("thin_ohlc")
    if int(analyzed_news or 0) < 50:
        issues.append("thin_sentiment")
    if pending_news:
        issues.append("pending_labels")
    if ohlc_age is None or ohlc_age > 7:
        issues.append("stale_ohlc")
    if label_coverage is not None and label_coverage < 0.9:
        issues.append("low_label_coverage")

    if "thin_ohlc" in issues or "thin_sentiment" in issues:
        status = "insufficient"
        label = "Insufficient"
    elif "stale_ohlc" in issues:
        status = "stale"
        label = "Stale"
    elif issues:
        status = "watch"
        label = "Watch"
    else:
        status = "healthy"
        label = "Healthy"

    return {
        "status": status,
        "label": label,
        "issues": issues,
        "ohlc_rows": int(ohlc["rows_count"] or 0) if ohlc else 0,
        "first_ohlc_date": ohlc["first_ohlc_date"] if ohlc else None,
        "latest_ohlc_date": ohlc["latest_ohlc_date"] if ohlc else None,
        "ohlc_age_days": ohlc_age,
        "aligned_news": int(aligned_news or 0),
        "analyzed_news": int(analyzed_news or 0),
        "pending_news": int(pending_news or 0),
        "label_coverage": _pct(label_coverage),
    }


def _recent_sentiment(symbol: str, lookback_days: int) -> dict:
    conn = get_conn()
    try:
        latest = conn.execute(
            "SELECT MAX(trade_date) AS latest_trade_date FROM news_aligned WHERE symbol = ?",
            (symbol,),
        ).fetchone()
        latest_trade_date = latest["latest_trade_date"] if latest else None
        if latest_trade_date:
            start_date = (
                datetime.strptime(latest_trade_date[:10], "%Y-%m-%d") - timedelta(days=lookback_days)
            ).strftime("%Y-%m-%d")
        else:
            start_date = "1900-01-01"

        row = conn.execute(
            """SELECT COUNT(DISTINCT na.news_id) AS total,
                      SUM(CASE WHEN l1.sentiment = 'positive' THEN 1 ELSE 0 END) AS positive,
                      SUM(CASE WHEN l1.sentiment = 'negative' THEN 1 ELSE 0 END) AS negative,
                      SUM(CASE WHEN COALESCE(l1.sentiment, 'neutral') NOT IN ('positive', 'negative') THEN 1 ELSE 0 END) AS neutral
               FROM news_aligned na
               LEFT JOIN layer1_results l1 ON l1.news_id = na.news_id AND l1.symbol = na.symbol
               WHERE na.symbol = ? AND na.trade_date >= ?""",
            (symbol, start_date),
        ).fetchone()
        headline_rows = conn.execute(
            """SELECT na.trade_date,
                      nr.title,
                      COALESCE(l1.sentiment, 'neutral') AS sentiment,
                      COALESCE(l1.key_discussion, '') AS summary
               FROM news_aligned na
               JOIN news_raw nr ON nr.id = na.news_id
               LEFT JOIN layer1_results l1 ON l1.news_id = na.news_id AND l1.symbol = na.symbol
               WHERE na.symbol = ?
               ORDER BY na.trade_date DESC, nr.published_utc DESC
               LIMIT 3""",
            (symbol,),
        ).fetchall()
    finally:
        conn.close()

    total = int(row["total"] or 0) if row else 0
    positive = int(row["positive"] or 0) if row else 0
    negative = int(row["negative"] or 0) if row else 0
    neutral = int(row["neutral"] or 0) if row else 0
    ratio = (positive - negative) / total if total else 0.0
    return {
        "latest_trade_date": latest_trade_date,
        "lookback_days": lookback_days,
        "total": total,
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "ratio": round(ratio, 4),
        "headlines": [
            {
                "date": row["trade_date"],
                "title": row["title"] or "",
                "sentiment": row["sentiment"] or "neutral",
                "summary": row["summary"] or "",
            }
            for row in headline_rows
        ],
    }


def _quality_weight(status: str | None) -> float:
    return {
        "validated": 20.0,
        "watch": 12.0,
        "thin-cv": 5.0,
        "unverified": 0.0,
        "overfit-risk": -4.0,
        "below-baseline": -8.0,
        "not-trained": -10.0,
    }.get(status or "", 0.0)


def _data_quality_weight(status: str | None) -> float:
    return {
        "healthy": 8.0,
        "watch": 2.0,
        "stale": -8.0,
        "insufficient": -10.0,
    }.get(status or "", -2.0)


def _gate_weight(status: str | None, actionable: bool) -> float:
    if actionable:
        return 30.0
    return {
        "candidate": 24.0,
        "watch": 14.0,
        "research-only": 4.0,
    }.get(status or "", 0.0)


def _score(row: dict) -> int:
    gates = row.get("gates", [])
    gate_scores = [_gate_weight(gate.get("gate_status"), gate.get("actionable")) for gate in gates]
    quality_scores = [_quality_weight(gate.get("model_quality")) for gate in gates]
    confidence_scores = [
        max(-5.0, min(8.0, (float(gate.get("confidence") or 0.5) - 0.5) * 35.0))
        for gate in gates
    ]
    trend = float(row.get("trend_20d") or 0.0)
    sentiment = float(row.get("sentiment_ratio_30d") or 0.0)
    annual_vol = float(row.get("annualized_volatility_20d") or 0.0)
    drawdown = float(row.get("drawdown_60d") or 0.0)

    value = 42.0
    value += max(gate_scores) if gate_scores else 0.0
    value += mean(quality_scores) if quality_scores else -4.0
    value += mean(confidence_scores) if confidence_scores else 0.0
    value += _data_quality_weight(row.get("data_quality_status"))
    value += max(-10.0, min(10.0, trend * 75.0))
    value += max(-10.0, min(10.0, sentiment * 18.0))
    if annual_vol > 0.65:
        value -= 8.0
    elif annual_vol > 0.5:
        value -= 4.0
    if drawdown < -0.2:
        value -= 8.0
    elif drawdown < -0.12:
        value -= 4.0
    return int(max(0, min(100, round(value))))


def _decision_status(row: dict) -> tuple[str, str, str]:
    score = int(row.get("score") or 0)
    actionable = bool(row.get("actionable_horizons"))
    data_status = row.get("data_quality_status")
    gates = row.get("gates", [])
    has_watch_gate = any(gate.get("gate_status") == "watch" for gate in gates)

    if row.get("error"):
        return "unavailable", "Unavailable", "Data is unavailable"
    if actionable and score >= 60:
        return "candidate", "Review Candidate", "Manual review before sizing"
    if data_status in {"stale", "insufficient"}:
        return "blocked", "Blocked", "Refresh data or labels first"
    if has_watch_gate or score >= 48:
        return "watch", "Watch", "Keep on active research list"
    return "research-only", "Research Only", "Research only"


def _risk_row(symbol: str, lookback_days: int) -> dict:
    coverage = _coverage(symbol)
    sentiment = _recent_sentiment(symbol, lookback_days)
    risk = build_risk_brief(symbol)
    if "error" in risk:
        return {
            "symbol": symbol,
            "decision_status": "unavailable",
            "label": "Unavailable",
            "score": 0,
            "action": "Data is unavailable",
            "error": risk["error"],
            "data_quality_status": coverage["status"],
            "data_quality_label": coverage["label"],
            "coverage": coverage,
            "gates": [],
            "blockers": ["risk_brief_unavailable"],
            "notes": [risk["error"]],
            "headlines": sentiment["headlines"],
        }

    gates = []
    failed_checks: set[str] = set()
    actionable_horizons = []
    for horizon, item in (risk.get("predictions") or {}).items():
        if not isinstance(item, dict):
            continue
        if item.get("actionable"):
            actionable_horizons.append(horizon)
        for check in item.get("failed_checks") or []:
            failed_checks.add(str(check))
        gates.append({
            "horizon": horizon,
            "direction": item.get("direction"),
            "confidence": _pct(item.get("confidence")),
            "model_quality": item.get("model_quality"),
            "trade_ready": bool(item.get("trade_ready")),
            "gate_status": item.get("gate_status"),
            "gate_label": item.get("gate_label"),
            "actionable": bool(item.get("actionable")),
            "failed_checks": item.get("failed_checks") or [],
        })

    blockers = sorted(failed_checks)
    if not actionable_horizons:
        blockers.append("no_actionable_horizon")
    blockers.extend(coverage["issues"])

    row = {
        "symbol": symbol,
        "as_of": risk.get("as_of"),
        "latest_close": risk.get("latest_close"),
        "trend_20d": risk.get("trend_20d"),
        "trend_60d": risk.get("trend_60d"),
        "drawdown_60d": risk.get("drawdown_60d"),
        "annualized_volatility_20d": risk.get("annualized_volatility_20d"),
        "atr_pct": risk.get("atr_pct"),
        "risk_status": risk.get("status"),
        "risk_label": risk.get("label"),
        "data_quality_status": coverage["status"],
        "data_quality_label": coverage["label"],
        "coverage": coverage,
        "sentiment_ratio_30d": sentiment["ratio"],
        "news_count_30d": sentiment["total"],
        "positive_news_30d": sentiment["positive"],
        "negative_news_30d": sentiment["negative"],
        "neutral_news_30d": sentiment["neutral"],
        "actionable_horizons": actionable_horizons,
        "gates": gates,
        "blockers": list(dict.fromkeys(blockers))[:8],
        "notes": (risk.get("notes") or [])[:3],
        "headlines": sentiment["headlines"],
    }
    row["score"] = _score(row)
    status, label, action = _decision_status(row)
    row["decision_status"] = status
    row["label"] = label
    row["action"] = action
    return row


def build_decision_board(symbols: list[str] | None = None, limit: int = 10, lookback_days: int = 30) -> dict:
    limit = max(1, min(int(limit or 10), 25))
    selected = _dedupe_symbols(symbols)[:limit] if symbols else _db_universe_symbols(limit)
    rows = [_risk_row(symbol, lookback_days) for symbol in selected]
    rows.sort(
        key=lambda row: (
            row.get("decision_status") == "candidate",
            row.get("decision_status") == "watch",
            row.get("score") or 0,
            row.get("sentiment_ratio_30d") or 0,
        ),
        reverse=True,
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index

    summary = {
        "total": len(rows),
        "candidates": sum(1 for row in rows if row.get("decision_status") == "candidate"),
        "watch": sum(1 for row in rows if row.get("decision_status") == "watch"),
        "research_only": sum(1 for row in rows if row.get("decision_status") == "research-only"),
        "blocked": sum(1 for row in rows if row.get("decision_status") == "blocked"),
        "unavailable": sum(1 for row in rows if row.get("decision_status") == "unavailable"),
        "best_symbol": rows[0]["symbol"] if rows else None,
    }
    return {
        "generated_at": _now_iso(),
        "lookback_days": lookback_days,
        "universe": selected,
        "summary": summary,
        "rows": rows,
    }
