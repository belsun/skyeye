"""Action Center aggregation for SkyEye."""

from __future__ import annotations

from ml.decision import build_decision_board
from ml.portfolio import build_portfolio_plan


def _pct(value) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _priority_rank(priority: str) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(priority, 0)


def _make_action(
    key: str,
    priority: str,
    category: str,
    title: str,
    message: str,
    action: str,
    symbol: str | None = None,
    metric: float | None = None,
    evidence: list[str] | None = None,
) -> dict:
    return {
        "key": key,
        "priority": priority,
        "category": category,
        "symbol": symbol,
        "title": title,
        "message": message,
        "action": action,
        "metric": round(metric, 4) if metric is not None else None,
        "evidence": evidence or [],
    }


def _portfolio_actions(holdings: dict) -> list[dict]:
    actions: list[dict] = []
    summary = holdings.get("summary") or {}
    positions = holdings.get("positions") or []

    if not positions:
        actions.append(_make_action(
            "portfolio-empty",
            "medium",
            "portfolio",
            "Add Real Holdings",
            "No actual positions are saved yet, so SkyEye cannot compare research signals with your real exposure.",
            "Add current positions in Holdings Monitor before using SkyEye as an account-level risk assistant.",
        ))
        return actions

    stop_risk = _pct(summary.get("estimated_stop_risk_pct"))
    if stop_risk >= 0.08:
        actions.append(_make_action(
            "portfolio-stop-risk-high",
            "high",
            "risk",
            "Portfolio Stop Risk Is Elevated",
            "Estimated stop-distance risk is high relative to current market value.",
            "Review position sizes, stops, and concentration before adding exposure.",
            metric=stop_risk,
            evidence=[f"Estimated stop risk {stop_risk:.1%}"],
        ))
    elif stop_risk >= 0.04:
        actions.append(_make_action(
            "portfolio-stop-risk-watch",
            "medium",
            "risk",
            "Portfolio Stop Risk Needs Review",
            "Estimated stop-distance risk is meaningful even before new trades.",
            "Check whether position sizes still match your intended risk budget.",
            metric=stop_risk,
            evidence=[f"Estimated stop risk {stop_risk:.1%}"],
        ))

    for position in positions:
        symbol = position.get("symbol")
        if not position.get("actionable_horizons"):
            actions.append(_make_action(
                f"{symbol}-gate-blocked",
                "medium",
                "gate",
                f"{symbol} Holding Is Gate-Blocked",
                "This holding is tracked, but no model horizon currently passes the live signal gate.",
                "Treat additions as research-only until model quality and strict strategy checks improve.",
                symbol=symbol,
                evidence=(position.get("failed_checks") or [])[:4],
            ))
        drawdown = _pct(position.get("drawdown_60d"))
        if drawdown <= -0.2:
            actions.append(_make_action(
                f"{symbol}-deep-drawdown",
                "high",
                "risk",
                f"{symbol} Has Deep 60D Drawdown",
                "Recent drawdown is deep enough to deserve a thesis and sizing review.",
                "Review whether the thesis has changed and avoid assuming quick mean reversion.",
                symbol=symbol,
                metric=drawdown,
                evidence=[f"60D drawdown {drawdown:.1%}"],
            ))
    return actions


def _decision_actions(board: dict) -> list[dict]:
    actions: list[dict] = []
    rows = board.get("rows") or []

    candidates = [row for row in rows if row.get("decision_status") == "candidate"]
    if candidates:
        top = candidates[0]
        actions.append(_make_action(
            f"{top.get('symbol')}-candidate-review",
            "high",
            "research",
            f"{top.get('symbol')} Passed Research Candidate Screen",
            "At least one horizon appears actionable, but the final decision still needs manual review.",
            "Open the symbol, inspect Risk Brief, Quant Lab, news drivers, and position sizing before acting.",
            symbol=top.get("symbol"),
            metric=_pct(top.get("score")),
            evidence=[f"Score {top.get('score')}", "Signal gate candidate"],
        ))

    watch = [row for row in rows if row.get("decision_status") == "watch"]
    if watch:
        top = watch[0]
        actions.append(_make_action(
            f"{top.get('symbol')}-watch-review",
            "low",
            "research",
            f"{top.get('symbol')} Leads Watchlist",
            "The highest-ranked symbol is still watch-only because live signal gates have not cleared.",
            "Review drivers for research, but do not treat it as a live trade signal.",
            symbol=top.get("symbol"),
            metric=_pct(top.get("score")),
            evidence=[f"Score {top.get('score')}", top.get("label") or "Watch"],
        ))

    for row in rows:
        symbol = row.get("symbol")
        coverage = row.get("coverage") or {}
        pending = int(coverage.get("pending_news") or 0)
        if pending > 0:
            actions.append(_make_action(
                f"{symbol}-pending-labels",
                "medium",
                "data",
                f"{symbol} Has Pending News Labels",
                "Aligned news exists without Layer 1 sentiment labels, weakening sentiment features.",
                "Run Layer 1 analysis from Quant Lab before trusting sentiment-driven signals.",
                symbol=symbol,
                metric=float(pending),
                evidence=[f"{pending} pending labels"],
            ))
        if row.get("data_quality_status") in {"stale", "insufficient"}:
            actions.append(_make_action(
                f"{symbol}-data-quality",
                "high",
                "data",
                f"{symbol} Data Quality Blocks Decisions",
                "This symbol has stale or insufficient data coverage.",
                "Refresh market/news data and rerun labels before using it in portfolio decisions.",
                symbol=symbol,
                evidence=coverage.get("issues") or [row.get("data_quality_label") or "Data issue"],
            ))
        vol = _pct(row.get("annualized_volatility_20d"))
        if vol >= 0.7:
            actions.append(_make_action(
                f"{symbol}-high-vol",
                "medium",
                "risk",
                f"{symbol} Volatility Is High",
                "Recent annualized volatility is high enough to make fixed-size entries risky.",
                "Use smaller sizing or require stronger evidence before any exposure.",
                symbol=symbol,
                metric=vol,
                evidence=[f"20D annualized volatility {vol:.1%}"],
            ))
    return actions


def _plan_actions(plan: dict) -> list[dict]:
    summary = plan.get("summary") or {}
    if _pct(summary.get("live_weight")) == 0 and int(summary.get("watch_count") or 0) > 0:
        return [_make_action(
            "portfolio-plan-research-only",
            "low",
            "gate",
            "Live Allocation Is Locked",
            "The research plan has watchlist weights, but live allocation is zero because signal gates have not cleared.",
            "Use paper weights for research tracking only; wait for validated model/strategy edge before live sizing.",
            metric=0.0,
            evidence=[f"{summary.get('watch_count')} watch symbols", "Live weight 0%"],
        )]
    return []


def build_action_center_from_parts(holdings: dict, board: dict, plan: dict) -> dict:
    actions = []
    actions.extend(_portfolio_actions(holdings))
    actions.extend(_decision_actions(board))
    actions.extend(_plan_actions(plan))
    actions.sort(key=lambda item: (_priority_rank(item["priority"]), item.get("symbol") or ""), reverse=True)

    summary = {
        "total": len(actions),
        "critical": sum(1 for item in actions if item["priority"] == "critical"),
        "high": sum(1 for item in actions if item["priority"] == "high"),
        "medium": sum(1 for item in actions if item["priority"] == "medium"),
        "low": sum(1 for item in actions if item["priority"] == "low"),
        "portfolio_status": holdings.get("status"),
        "decision_best_symbol": (board.get("summary") or {}).get("best_symbol"),
        "live_weight": (plan.get("summary") or {}).get("live_weight"),
    }
    if summary["critical"] or summary["high"]:
        status = "attention"
        label = "Needs Attention"
        message = "High-priority portfolio or data items need review before adding risk."
    elif summary["medium"]:
        status = "review"
        label = "Review"
        message = "There are research or setup tasks to handle before decisions improve."
    else:
        status = "calm"
        label = "Calm"
        message = "No urgent action items; continue monitoring research and holdings."

    return {
        "generated_at": board.get("generated_at"),
        "status": status,
        "label": label,
        "message": message,
        "summary": summary,
        "actions": actions[:20],
    }


def build_action_center(holdings: dict, capital: float = 100000.0, limit: int = 10) -> dict:
    board = build_decision_board(limit=limit)
    plan = build_portfolio_plan(capital=capital, limit=limit, board=board)
    return build_action_center_from_parts(holdings, board, plan)
