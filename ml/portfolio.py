"""Portfolio planning layer for SkyEye research workflows."""

from __future__ import annotations

from ml.decision import build_decision_board


def _num(value, fallback: float = 0.0) -> float:
    try:
        if value is None:
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _round(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _stop_distance(row: dict) -> float:
    atr_pct = _num(row.get("atr_pct"), 0.03)
    return _clamp(atr_pct * 2.0, 0.03, 0.18)


def _shares(notional: float, price: float | None) -> float:
    if notional <= 0 or not price:
        return 0.0
    return round(notional / price, 4)


def _research_raw(row: dict) -> float:
    status = row.get("decision_status")
    if status not in {"candidate", "watch", "research-only"}:
        return 0.0
    if row.get("data_quality_status") in {"stale", "insufficient"}:
        return 0.0

    score = _num(row.get("score"))
    annual_vol = max(_num(row.get("annualized_volatility_20d"), 0.35), 0.12)
    sentiment = _num(row.get("sentiment_ratio_30d"))
    drawdown = _num(row.get("drawdown_60d"))
    trend = _num(row.get("trend_20d"))

    score_component = max(score - 35.0, 0.0) / 65.0
    sentiment_component = 1.0 + _clamp(sentiment * 0.3, -0.18, 0.18)
    trend_component = 1.0 + _clamp(trend * 0.5, -0.12, 0.12)
    drawdown_component = 0.75 if drawdown < -0.2 else 0.88 if drawdown < -0.12 else 1.0
    return max(score_component * sentiment_component * trend_component * drawdown_component / annual_vol, 0.0)


def _live_raw(row: dict) -> float:
    if row.get("decision_status") != "candidate":
        return 0.0
    if not row.get("actionable_horizons"):
        return 0.0
    if row.get("data_quality_status") not in {"healthy", "watch"}:
        return 0.0
    return _research_raw(row)


def _allocation_status(row: dict, live_weight: float, paper_weight: float) -> tuple[str, str]:
    if live_weight > 0:
        return "live-candidate", "Sizing Candidate"
    if paper_weight > 0:
        if row.get("decision_status") == "watch":
            return "research-watch", "Research Watch"
        return "research-only", "Research Only"
    if row.get("decision_status") in {"blocked", "unavailable"}:
        return "blocked", "Blocked"
    return "excluded", "Excluded"


def _reason_list(row: dict, live_weight: float) -> list[str]:
    reasons: list[str] = []
    if live_weight > 0:
        reasons.append("Signal gate passed; still requires manual review.")
    else:
        reasons.append("Live sizing is disabled until a signal gate passes.")
    if row.get("data_quality_label"):
        reasons.append(f"Data: {row['data_quality_label']}.")
    blockers = row.get("blockers") or []
    if blockers:
        reasons.append("Blockers: " + ", ".join(blockers[:3]) + ".")
    return reasons[:3]


def build_portfolio_plan(
    symbols: list[str] | None = None,
    capital: float = 100000.0,
    limit: int = 10,
    lookback_days: int = 30,
    board: dict | None = None,
) -> dict:
    """Build conservative live and paper allocation plans from SkyEye signal gates."""
    capital = max(float(capital or 100000.0), 0.0)
    if board is None:
        board = build_decision_board(symbols=symbols, limit=limit, lookback_days=lookback_days)
    rows = board.get("rows", [])

    controls = {
        "max_live_gross_weight": 0.35,
        "max_single_live_weight": 0.08,
        "max_account_risk_pct": 0.02,
        "max_position_risk_pct": 0.005,
        "paper_gross_weight": 1.0,
        "min_stop_distance_pct": 0.03,
        "max_stop_distance_pct": 0.18,
    }

    research_raw = {row["symbol"]: _research_raw(row) for row in rows}
    live_raw = {row["symbol"]: _live_raw(row) for row in rows}
    total_research_raw = sum(research_raw.values())
    total_live_raw = sum(live_raw.values())

    allocations = []
    live_weight_total_raw = 0.0
    paper_weight_total_raw = 0.0
    for row in rows:
        symbol = row["symbol"]
        price = _num(row.get("latest_close"), 0.0)
        stop_pct = _stop_distance(row)
        risk_cap_weight = controls["max_position_risk_pct"] / stop_pct if stop_pct else 0.0
        live_weight = 0.0
        if total_live_raw > 0 and live_raw[symbol] > 0:
            proportional = live_raw[symbol] / total_live_raw * controls["max_live_gross_weight"]
            live_weight = min(proportional, controls["max_single_live_weight"], risk_cap_weight)

        paper_weight = 0.0
        if total_research_raw > 0 and research_raw[symbol] > 0:
            paper_weight = research_raw[symbol] / total_research_raw * controls["paper_gross_weight"]

        live_weight_total_raw += live_weight
        paper_weight_total_raw += paper_weight
        live_notional = capital * live_weight
        paper_notional = capital * paper_weight
        max_risk_pct = live_weight * stop_pct
        allocation_status, label = _allocation_status(row, live_weight, paper_weight)

        allocations.append({
            "symbol": symbol,
            "rank": row.get("rank"),
            "decision_status": row.get("decision_status"),
            "allocation_status": allocation_status,
            "label": label,
            "score": row.get("score"),
            "latest_close": row.get("latest_close"),
            "live_weight": _round(live_weight),
            "live_notional": round(live_notional, 2),
            "live_shares": _shares(live_notional, price),
            "paper_weight": _round(paper_weight),
            "paper_notional": round(paper_notional, 2),
            "paper_shares": _shares(paper_notional, price),
            "stop_distance_pct": _round(stop_pct),
            "max_risk_pct": _round(max_risk_pct),
            "annualized_volatility_20d": row.get("annualized_volatility_20d"),
            "drawdown_60d": row.get("drawdown_60d"),
            "trend_20d": row.get("trend_20d"),
            "sentiment_ratio_30d": row.get("sentiment_ratio_30d"),
            "actionable_horizons": row.get("actionable_horizons") or [],
            "blockers": row.get("blockers") or [],
            "reasons": _reason_list(row, live_weight),
        })

    candidate_count = sum(1 for item in allocations if item["allocation_status"] == "live-candidate")
    watch_count = sum(1 for item in allocations if item["allocation_status"] == "research-watch")
    blocked_count = sum(1 for item in allocations if item["allocation_status"] == "blocked")

    if candidate_count:
        plan_status = "candidate-review"
        label = "Candidate Review"
        message = "At least one symbol passed the signal gate; live sizing is capped by risk controls."
    else:
        plan_status = "research-only"
        label = "Research Only"
        message = "No symbol has passed the live signal gate; live allocation remains at zero."

    return {
        "generated_at": board.get("generated_at"),
        "capital": round(capital, 2),
        "lookback_days": board.get("lookback_days"),
        "status": plan_status,
        "label": label,
        "message": message,
        "universe": board.get("universe", []),
        "controls": controls,
        "summary": {
            "total": len(allocations),
            "candidate_count": candidate_count,
            "watch_count": watch_count,
            "blocked_count": blocked_count,
            "live_weight": _round(live_weight_total_raw),
            "live_notional": round(capital * live_weight_total_raw, 2),
            "paper_weight": _round(paper_weight_total_raw),
            "paper_notional": round(capital * paper_weight_total_raw, 2),
        },
        "allocations": allocations,
    }
