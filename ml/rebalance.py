"""Rebalance comparison between actual holdings and SkyEye plan."""

from __future__ import annotations


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


def _status_for(actual: float, live_target: float, paper_target: float, allocation: dict | None) -> tuple[str, str, str]:
    tolerance = 0.0025
    allocation_status = (allocation or {}).get("allocation_status")
    blockers = (allocation or {}).get("blockers") or []

    if actual > 0 and live_target <= tolerance:
        if blockers:
            return "off-gate", "Off Gate", "Existing exposure has no live target because signal gates are blocked."
        return "research-hold", "Research Hold", "Existing exposure has no live target; review manually before adding."
    if live_target > actual + tolerance:
        return "add-candidate", "Add Candidate", "Live target is above actual exposure, subject to manual review."
    if actual > live_target + tolerance and live_target > 0:
        return "trim-candidate", "Trim Candidate", "Actual exposure is above the live target range."
    if actual > 0 and abs(actual - live_target) <= tolerance and live_target > 0:
        return "aligned", "Aligned", "Actual exposure is near the current live target."
    if actual == 0 and paper_target > 0:
        if allocation_status == "research-watch":
            return "research-watch", "Research Watch", "Paper plan has weight, but live sizing is locked."
        return "paper-only", "Paper Only", "Plan is research-only until signal gates clear."
    return "excluded", "Excluded", "No actual exposure and no plan weight."


def build_rebalance_plan(holdings: dict, plan: dict, capital: float) -> dict:
    capital = max(float(capital or plan.get("capital") or 0.0), 0.0)
    positions = {item["symbol"]: item for item in holdings.get("positions", [])}
    allocations = {item["symbol"]: item for item in plan.get("allocations", [])}
    symbols = sorted(set(positions) | set(allocations))

    rows = []
    live_gap = 0.0
    paper_gap = 0.0
    off_gate_count = 0
    add_count = 0
    trim_count = 0

    for symbol in symbols:
        position = positions.get(symbol)
        allocation = allocations.get(symbol)
        actual_notional = _num((position or {}).get("market_value"))
        live_target = _num((allocation or {}).get("live_notional"))
        paper_target = _num((allocation or {}).get("paper_notional"))
        live_delta = live_target - actual_notional
        paper_delta = paper_target - actual_notional
        actual_weight = actual_notional / capital if capital else 0.0
        live_target_weight = _num((allocation or {}).get("live_weight"))
        paper_target_weight = _num((allocation or {}).get("paper_weight"))
        status, label, message = _status_for(actual_weight, live_target_weight, paper_target_weight, allocation)

        live_gap += abs(live_delta)
        paper_gap += abs(paper_delta)
        off_gate_count += 1 if status == "off-gate" else 0
        add_count += 1 if status == "add-candidate" else 0
        trim_count += 1 if status == "trim-candidate" else 0

        rows.append({
            "symbol": symbol,
            "status": status,
            "label": label,
            "message": message,
            "actual_notional": round(actual_notional, 2),
            "actual_weight": _round(actual_weight),
            "live_target_notional": round(live_target, 2),
            "live_target_weight": _round(live_target_weight),
            "live_delta_notional": round(live_delta, 2),
            "live_delta_weight": _round(live_delta / capital if capital else 0.0),
            "paper_target_notional": round(paper_target, 2),
            "paper_target_weight": _round(paper_target_weight),
            "paper_delta_notional": round(paper_delta, 2),
            "paper_delta_weight": _round(paper_delta / capital if capital else 0.0),
            "latest_close": (position or allocation or {}).get("latest_close"),
            "shares": (position or {}).get("shares", 0.0),
            "allocation_status": (allocation or {}).get("allocation_status"),
            "decision_status": (allocation or {}).get("decision_status"),
            "score": (allocation or {}).get("score"),
            "blockers": (allocation or {}).get("blockers") or (position or {}).get("failed_checks") or [],
            "reasons": (allocation or {}).get("reasons") or [],
        })

    rows.sort(
        key=lambda row: (
            row["status"] == "off-gate",
            row["status"] == "add-candidate",
            abs(row["live_delta_notional"]),
            row["paper_target_notional"],
        ),
        reverse=True,
    )

    plan_summary = plan.get("summary") or {}
    holdings_summary = holdings.get("summary") or {}
    actual_market_value = _num(holdings_summary.get("total_market_value"))
    live_target_total = _num(plan_summary.get("live_notional"))
    paper_target_total = _num(plan_summary.get("paper_notional"))
    if actual_market_value == 0:
        live_gap = live_target_total
        paper_gap = paper_target_total

    if off_gate_count:
        status = "review"
        label = "Review Exposure"
        message = "Some actual holdings have no live target because signal gates are blocked."
    elif add_count or trim_count:
        status = "candidate-review"
        label = "Candidate Review"
        message = "Rebalance candidates exist, but every change still needs manual review."
    elif not holdings.get("positions"):
        status = "setup"
        label = "Setup Needed"
        message = "No actual holdings are saved, so rebalance comparison is research-only."
    else:
        status = "aligned"
        label = "Aligned"
        message = "Actual holdings are close to the current live plan."

    return {
        "generated_at": plan.get("generated_at") or holdings.get("generated_at"),
        "capital": round(capital, 2),
        "status": status,
        "label": label,
        "message": message,
        "summary": {
            "rows": len(rows),
            "off_gate": off_gate_count,
            "add_candidates": add_count,
            "trim_candidates": trim_count,
            "live_gap_notional": round(live_gap, 2),
            "paper_gap_notional": round(paper_gap, 2),
            "actual_market_value": actual_market_value,
            "live_target_notional": live_target_total,
            "paper_target_notional": paper_target_total,
        },
        "rows": rows,
    }
