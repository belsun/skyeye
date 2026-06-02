import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import get_conn

router = APIRouter()

INVESTMENT_BRIEF_CACHE: dict[float, tuple[float, dict]] = {}
INVESTMENT_BRIEF_TTL_SECONDS = 45.0


class PositionRequest(BaseModel):
    shares: float = Field(..., ge=0)
    avg_cost: float | None = Field(None, ge=0)
    thesis: str | None = None


class TradeRequest(BaseModel):
    symbol: str
    side: str
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    trade_date: str | None = None
    thesis: str | None = None
    setup: str | None = None
    review: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clear_investment_brief_cache() -> None:
    INVESTMENT_BRIEF_CACHE.clear()


def _round(value, digits: int = 4):
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _latest_price(symbol: str) -> dict:
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
        return {"latest_close": None, "price_date": None}
    return {"latest_close": row["close"], "price_date": row["date"]}


def _risk_snapshot(symbol: str) -> dict:
    try:
        from ml.risk import build_risk_brief

        risk = build_risk_brief(symbol)
        if "error" in risk:
            return {"risk_error": risk["error"]}
        failed_checks = []
        actionable_horizons = []
        for horizon, pred in (risk.get("predictions") or {}).items():
            if not isinstance(pred, dict):
                continue
            if pred.get("actionable"):
                actionable_horizons.append(horizon)
            failed_checks.extend(pred.get("failed_checks") or [])
        budget = risk.get("risk_budget") or {}
        return {
            "risk_status": risk.get("status"),
            "risk_label": risk.get("label"),
            "atr_pct": risk.get("atr_pct"),
            "drawdown_60d": risk.get("drawdown_60d"),
            "trend_20d": risk.get("trend_20d"),
            "stop_distance_pct": budget.get("reference_stop_distance_pct"),
            "actionable_horizons": actionable_horizons,
            "failed_checks": sorted(set(failed_checks)),
        }
    except Exception as exc:
        return {"risk_error": str(exc)}


def _load_positions() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT symbol, shares, avg_cost, thesis, created_at, updated_at
               FROM portfolio_positions
               WHERE shares > 0
               ORDER BY symbol"""
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def _build_portfolio() -> dict:
    raw_positions = _load_positions()
    positions = []
    total_market_value = 0.0
    total_cost_basis = 0.0
    total_stop_risk = 0.0

    for row in raw_positions:
        symbol = row["symbol"]
        shares = float(row["shares"] or 0.0)
        avg_cost = row.get("avg_cost")
        price = _latest_price(symbol)
        risk = _risk_snapshot(symbol)
        latest_close = price.get("latest_close")
        market_value = shares * float(latest_close) if latest_close is not None else 0.0
        cost_basis = shares * float(avg_cost) if avg_cost is not None else None
        pnl = market_value - cost_basis if cost_basis is not None else None
        pnl_pct = pnl / cost_basis if cost_basis else None
        stop_distance_pct = risk.get("stop_distance_pct") or risk.get("atr_pct")
        position_stop_risk = market_value * float(stop_distance_pct) if stop_distance_pct else 0.0

        total_market_value += market_value
        if cost_basis is not None:
            total_cost_basis += cost_basis
        total_stop_risk += position_stop_risk

        positions.append({
            "symbol": symbol,
            "shares": _round(shares, 4),
            "avg_cost": _round(avg_cost, 4),
            "thesis": row.get("thesis") or "",
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "latest_close": _round(latest_close, 4),
            "price_date": price.get("price_date"),
            "market_value": round(market_value, 2),
            "cost_basis": round(cost_basis, 2) if cost_basis is not None else None,
            "unrealized_pnl": round(pnl, 2) if pnl is not None else None,
            "unrealized_pnl_pct": _round(pnl_pct),
            "weight": 0.0,
            "risk_status": risk.get("risk_status"),
            "risk_label": risk.get("risk_label"),
            "atr_pct": _round(risk.get("atr_pct")),
            "drawdown_60d": _round(risk.get("drawdown_60d")),
            "trend_20d": _round(risk.get("trend_20d")),
            "stop_distance_pct": _round(stop_distance_pct),
            "estimated_stop_risk": round(position_stop_risk, 2),
            "actionable_horizons": risk.get("actionable_horizons") or [],
            "failed_checks": risk.get("failed_checks") or [],
            "risk_error": risk.get("risk_error"),
        })

    for position in positions:
        position["weight"] = _round(position["market_value"] / total_market_value) if total_market_value else 0.0

    total_pnl = total_market_value - total_cost_basis if total_cost_basis else None
    total_pnl_pct = total_pnl / total_cost_basis if total_cost_basis else None
    stop_risk_pct = total_stop_risk / total_market_value if total_market_value else 0.0
    gate_blocked = sum(1 for item in positions if not item.get("actionable_horizons"))

    if not positions:
        status = "empty"
        label = "No Holdings"
        message = "Add positions to monitor real portfolio risk against SkyEye signals."
    elif stop_risk_pct > 0.08:
        status = "elevated"
        label = "Elevated Risk"
        message = "Estimated stop risk is high; review sizing and concentration."
    elif gate_blocked:
        status = "research-only"
        label = "Research Only"
        message = "Some holdings do not pass live signal gates; monitor before adding exposure."
    else:
        status = "monitored"
        label = "Monitored"
        message = "Holdings are tracked with current price, risk, and signal gate context."

    positions.sort(key=lambda item: item["market_value"], reverse=True)
    return {
        "generated_at": _now(),
        "status": status,
        "label": label,
        "message": message,
        "summary": {
            "position_count": len(positions),
            "total_market_value": round(total_market_value, 2),
            "total_cost_basis": round(total_cost_basis, 2) if total_cost_basis else None,
            "total_unrealized_pnl": round(total_pnl, 2) if total_pnl is not None else None,
            "total_unrealized_pnl_pct": _round(total_pnl_pct),
            "estimated_stop_risk": round(total_stop_risk, 2),
            "estimated_stop_risk_pct": _round(stop_risk_pct),
            "gate_blocked_positions": gate_blocked,
            "largest_position": positions[0]["symbol"] if positions else None,
        },
        "positions": positions,
    }


def _clean_trade_payload(req: TradeRequest) -> dict:
    symbol = req.symbol.upper().strip()
    side = req.side.lower().strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")
    if side not in {"buy", "sell"}:
        raise HTTPException(status_code=400, detail="Side must be buy or sell")
    trade_date = (req.trade_date or _now()[:10])[:10]
    try:
        datetime.strptime(trade_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Trade date must use YYYY-MM-DD")
    return {
        "symbol": symbol,
        "side": side,
        "quantity": float(req.quantity),
        "price": float(req.price),
        "trade_date": trade_date,
        "thesis": (req.thesis or "").strip()[:1200],
        "setup": (req.setup or "").strip()[:400],
        "review": (req.review or "").strip()[:1200],
    }


def _trade_row(row: dict) -> dict:
    symbol = row["symbol"]
    latest = _latest_price(symbol)
    risk = _risk_snapshot(symbol)
    latest_close = latest.get("latest_close")
    quantity = float(row["quantity"] or 0.0)
    price = float(row["price"] or 0.0)
    entry_notional = quantity * price
    current_value = quantity * float(latest_close) if latest_close is not None else None
    if current_value is None:
        pnl = None
    elif row["side"] == "buy":
        pnl = current_value - entry_notional
    else:
        pnl = entry_notional - current_value
    pnl_pct = pnl / entry_notional if pnl is not None and entry_notional else None
    return {
        "id": row["id"],
        "symbol": symbol,
        "side": row["side"],
        "quantity": _round(quantity, 4),
        "price": _round(price, 4),
        "trade_date": row["trade_date"],
        "thesis": row.get("thesis") or "",
        "setup": row.get("setup") or "",
        "review": row.get("review") or "",
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "entry_notional": round(entry_notional, 2),
        "latest_close": _round(latest_close, 4),
        "price_date": latest.get("price_date"),
        "current_value": round(current_value, 2) if current_value is not None else None,
        "marked_pnl": round(pnl, 2) if pnl is not None else None,
        "marked_pnl_pct": _round(pnl_pct),
        "risk_status": risk.get("risk_status"),
        "risk_label": risk.get("risk_label"),
        "actionable_horizons": risk.get("actionable_horizons") or [],
        "failed_checks": risk.get("failed_checks") or [],
        "risk_error": risk.get("risk_error"),
    }


def _build_trade_journal(limit: int = 100) -> dict:
    limit = max(1, min(int(limit or 100), 500))
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT id, symbol, side, quantity, price, trade_date, thesis, setup, review, created_at, updated_at
               FROM trade_journal
               ORDER BY trade_date DESC, id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    trades = [_trade_row(dict(row)) for row in rows]
    buys = [trade for trade in trades if trade["side"] == "buy"]
    sells = [trade for trade in trades if trade["side"] == "sell"]
    total_notional = sum(float(trade.get("entry_notional") or 0.0) for trade in trades)
    marked = [float(trade["marked_pnl"]) for trade in trades if trade.get("marked_pnl") is not None]
    missing_review = sum(1 for trade in trades if not (trade.get("review") or "").strip())
    gate_blocked = sum(1 for trade in trades if not trade.get("actionable_horizons"))
    total_marked_pnl = sum(marked) if marked else None

    if not trades:
        status = "empty"
        label = "No Trades"
        message = "Log trades to connect decisions, signals, and later review."
    elif missing_review:
        status = "needs-review"
        label = "Needs Review"
        message = "Some logged trades do not have review notes yet."
    elif gate_blocked:
        status = "gate-review"
        label = "Gate Review"
        message = "Some trades are linked to symbols whose current signal gates are blocked."
    else:
        status = "reviewed"
        label = "Reviewed"
        message = "Trade journal is current."

    return {
        "generated_at": _now(),
        "status": status,
        "label": label,
        "message": message,
        "summary": {
            "trade_count": len(trades),
            "buy_count": len(buys),
            "sell_count": len(sells),
            "total_notional": round(total_notional, 2),
            "marked_pnl": round(total_marked_pnl, 2) if total_marked_pnl is not None else None,
            "missing_review": missing_review,
            "gate_blocked_trades": gate_blocked,
        },
        "trades": trades,
    }


def _days_since_trade(trade_date: str) -> int | None:
    try:
        parsed = datetime.strptime(trade_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return (datetime.now(timezone.utc).date() - parsed).days


def _setup_key(trade: dict) -> str:
    setup = (trade.get("setup") or "").strip()
    return setup if setup else "Unclassified"


def _review_priority(trade: dict) -> tuple[str, int, list[str], str]:
    reasons = []
    score = 0
    if not (trade.get("review") or "").strip():
        score += 35
        reasons.append("missing review")
    if not trade.get("actionable_horizons"):
        score += 25
        reasons.append("signal gate blocked")
    if not (trade.get("thesis") or "").strip():
        score += 12
        reasons.append("missing thesis")
    pnl_pct = trade.get("marked_pnl_pct")
    if pnl_pct is not None:
        abs_move = abs(float(pnl_pct))
        if abs_move >= 0.08:
            score += min(25, int(abs_move * 100))
            reasons.append("large marked move")
    days = _days_since_trade(trade.get("trade_date"))
    if days is not None and days >= 7:
        score += min(15, days // 3)
        reasons.append("aging trade")

    if score >= 55:
        priority = "high"
        action = "Write a post-trade review before adding exposure."
    elif score >= 30:
        priority = "medium"
        action = "Review thesis, gate blockers, and current marked P/L."
    else:
        priority = "low"
        action = "Keep as reference material for future pattern review."
    return priority, score, reasons, action


def _build_trade_review() -> dict:
    journal = _build_trade_journal(limit=500)
    trades = journal["trades"]
    total_notional = float(journal["summary"]["total_notional"] or 0.0)
    marked = [float(trade["marked_pnl"]) for trade in trades if trade.get("marked_pnl") is not None]
    marked_pnl = sum(marked) if marked else None
    marked_pnl_pct = (marked_pnl / total_notional) if marked_pnl is not None and total_notional else None
    reviewed = [trade for trade in trades if (trade.get("review") or "").strip()]
    gate_blocked = [trade for trade in trades if not trade.get("actionable_horizons")]
    positive = [trade for trade in trades if (trade.get("marked_pnl") or 0) > 0]
    negative = [trade for trade in trades if (trade.get("marked_pnl") or 0) < 0]
    ages = [age for age in (_days_since_trade(trade.get("trade_date")) for trade in trades) if age is not None]

    setups: dict[str, dict] = {}
    months: dict[str, dict] = {}
    priorities = []
    for trade in trades:
        setup = _setup_key(trade)
        setup_row = setups.setdefault(setup, {
            "setup": setup,
            "trade_count": 0,
            "reviewed_count": 0,
            "total_notional": 0.0,
            "marked_pnl": 0.0,
            "marked_pnl_known": 0,
            "gate_blocked_trades": 0,
            "symbols": set(),
        })
        setup_row["trade_count"] += 1
        setup_row["reviewed_count"] += 1 if (trade.get("review") or "").strip() else 0
        setup_row["total_notional"] += float(trade.get("entry_notional") or 0.0)
        if trade.get("marked_pnl") is not None:
            setup_row["marked_pnl"] += float(trade["marked_pnl"])
            setup_row["marked_pnl_known"] += 1
        setup_row["gate_blocked_trades"] += 0 if trade.get("actionable_horizons") else 1
        setup_row["symbols"].add(trade["symbol"])

        month = (trade.get("trade_date") or "")[:7] or "unknown"
        month_row = months.setdefault(month, {
            "month": month,
            "trade_count": 0,
            "reviewed_count": 0,
            "total_notional": 0.0,
            "marked_pnl": 0.0,
            "marked_pnl_known": 0,
        })
        month_row["trade_count"] += 1
        month_row["reviewed_count"] += 1 if (trade.get("review") or "").strip() else 0
        month_row["total_notional"] += float(trade.get("entry_notional") or 0.0)
        if trade.get("marked_pnl") is not None:
            month_row["marked_pnl"] += float(trade["marked_pnl"])
            month_row["marked_pnl_known"] += 1

        priority, score, reasons, action = _review_priority(trade)
        priorities.append({
            "id": trade["id"],
            "symbol": trade["symbol"],
            "trade_date": trade["trade_date"],
            "setup": setup,
            "side": trade["side"],
            "priority": priority,
            "priority_score": score,
            "reasons": reasons,
            "action": action,
            "marked_pnl": trade.get("marked_pnl"),
            "marked_pnl_pct": trade.get("marked_pnl_pct"),
            "review": trade.get("review") or "",
            "thesis": trade.get("thesis") or "",
        })

    setup_breakdown = []
    for row in setups.values():
        notional = row["total_notional"]
        pnl = row["marked_pnl"] if row["marked_pnl_known"] else None
        setup_breakdown.append({
            "setup": row["setup"],
            "trade_count": row["trade_count"],
            "reviewed_count": row["reviewed_count"],
            "review_rate": _round(row["reviewed_count"] / row["trade_count"]),
            "total_notional": round(notional, 2),
            "marked_pnl": round(pnl, 2) if pnl is not None else None,
            "marked_pnl_pct": _round(pnl / notional) if pnl is not None and notional else None,
            "gate_blocked_trades": row["gate_blocked_trades"],
            "symbols": sorted(row["symbols"]),
        })
    setup_breakdown.sort(key=lambda item: (item["trade_count"], abs(item.get("marked_pnl") or 0)), reverse=True)

    monthly = []
    for row in months.values():
        notional = row["total_notional"]
        pnl = row["marked_pnl"] if row["marked_pnl_known"] else None
        monthly.append({
            "month": row["month"],
            "trade_count": row["trade_count"],
            "review_rate": _round(row["reviewed_count"] / row["trade_count"]),
            "total_notional": round(notional, 2),
            "marked_pnl": round(pnl, 2) if pnl is not None else None,
            "marked_pnl_pct": _round(pnl / notional) if pnl is not None and notional else None,
        })
    monthly.sort(key=lambda item: item["month"], reverse=True)

    priorities.sort(key=lambda item: (item["priority_score"], item["trade_date"]), reverse=True)
    best_setup = max(
        (row for row in setup_breakdown if row.get("marked_pnl") is not None),
        key=lambda item: item["marked_pnl"],
        default=None,
    )
    worst_setup = min(
        (row for row in setup_breakdown if row.get("marked_pnl") is not None),
        key=lambda item: item["marked_pnl"],
        default=None,
    )

    if not trades:
        status = "empty"
        label = "No Sample"
        message = "Log trades first; review analytics will appear after the journal has entries."
    elif journal["summary"]["missing_review"]:
        status = "needs-review"
        label = "Needs Review"
        message = "Some trades are missing post-trade notes, so the learning loop is incomplete."
    elif gate_blocked:
        status = "gate-review"
        label = "Gate Review"
        message = "Some logged trades are currently outside live signal gates; study whether the setup still belongs in your playbook."
    elif len(trades) < 10:
        status = "learning"
        label = "Learning Sample"
        message = "The journal is reviewed, but the sample is still small."
    else:
        status = "disciplined"
        label = "Disciplined"
        message = "Trade review coverage is current enough to start comparing setups."

    return {
        "generated_at": _now(),
        "status": status,
        "label": label,
        "message": message,
        "summary": {
            "trade_count": len(trades),
            "reviewed_count": len(reviewed),
            "review_rate": _round(len(reviewed) / len(trades)) if trades else 0.0,
            "total_notional": round(total_notional, 2),
            "marked_pnl": round(marked_pnl, 2) if marked_pnl is not None else None,
            "marked_pnl_pct": _round(marked_pnl_pct),
            "positive_count": len(positive),
            "negative_count": len(negative),
            "missing_review": journal["summary"]["missing_review"],
            "gate_blocked_trades": len(gate_blocked),
            "setup_count": len(setup_breakdown),
            "best_setup": best_setup["setup"] if best_setup else None,
            "worst_setup": worst_setup["setup"] if worst_setup else None,
            "avg_days_since_trade": _round(sum(ages) / len(ages), 1) if ages else None,
        },
        "setup_breakdown": setup_breakdown,
        "priority_reviews": priorities[:8],
        "monthly": monthly[:6],
    }


def _priority_rank(priority: str | None) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(priority or "", 0)


def _brief_priority_items(action_center: dict, strategy: dict, trade_review: dict) -> list[dict]:
    items: list[dict] = []
    for action in (action_center.get("actions") or [])[:8]:
        items.append({
            "source": "action-center",
            "priority": action.get("priority") or "low",
            "category": action.get("category") or "workflow",
            "symbol": action.get("symbol"),
            "title": action.get("title") or "",
            "message": action.get("message") or "",
            "action": action.get("action") or "",
            "evidence": action.get("evidence") or [],
        })
    for action in (strategy.get("actions") or [])[:3]:
        items.append({
            "source": "strategy-monitor",
            "priority": action.get("priority") or "low",
            "category": "model",
            "symbol": None,
            "title": action.get("title") or "",
            "message": action.get("message") or "",
            "action": action.get("action") or "",
            "evidence": action.get("evidence") or [],
        })
    for review in (trade_review.get("priority_reviews") or [])[:3]:
        items.append({
            "source": "trade-review",
            "priority": review.get("priority") or "low",
            "category": "journal",
            "symbol": review.get("symbol"),
            "title": f"{review.get('symbol')} Trade Needs Review",
            "message": ", ".join(review.get("reasons") or []) or review.get("setup") or "Review logged trade.",
            "action": review.get("action") or "Write a trade review.",
            "evidence": [review.get("setup") or "Unclassified", f"P/L {review.get('marked_pnl')}"],
        })

    items.sort(key=lambda item: (_priority_rank(item["priority"]), item.get("symbol") or ""), reverse=True)
    return items[:8]


def _research_queue(board: dict, strategy: dict) -> list[dict]:
    watch_by_symbol = {}
    for row in strategy.get("rows") or []:
        if row.get("symbol") == "UNIFIED":
            continue
        if row.get("status") not in {"ready", "watch"}:
            continue
        current = watch_by_symbol.get(row["symbol"])
        if current is None or _priority_rank("high" if row.get("status") == "ready" else "medium") > current["rank"]:
            watch_by_symbol[row["symbol"]] = {
                "rank": 2 if row.get("status") == "ready" else 1,
                "status": row.get("status"),
                "horizon": row.get("horizon"),
                "reason": (row.get("per_ticker") or {}).get("verdict") or row.get("quality_label"),
            }

    queue = []
    for row in (board.get("rows") or [])[:8]:
        sym = row.get("symbol")
        strategy_hint = watch_by_symbol.get(sym)
        queue.append({
            "symbol": sym,
            "rank": row.get("rank"),
            "score": row.get("score"),
            "label": row.get("label"),
            "decision_status": row.get("decision_status"),
            "action": row.get("action"),
            "sentiment_ratio_30d": row.get("sentiment_ratio_30d"),
            "trend_20d": row.get("trend_20d"),
            "risk_label": row.get("risk_label"),
            "data_quality_label": row.get("data_quality_label"),
            "strategy_status": strategy_hint.get("status") if strategy_hint else "blocked",
            "strategy_horizon": strategy_hint.get("horizon") if strategy_hint else None,
            "strategy_reason": strategy_hint.get("reason") if strategy_hint else "No ready/watch horizon",
            "blockers": row.get("blockers") or [],
        })
    return queue


def _allocation_snapshot(plan: dict) -> list[dict]:
    rows = []
    for item in plan.get("allocations") or []:
        if item.get("paper_weight", 0) <= 0 and item.get("live_weight", 0) <= 0:
            continue
        rows.append({
            "symbol": item.get("symbol"),
            "label": item.get("label"),
            "allocation_status": item.get("allocation_status"),
            "live_weight": item.get("live_weight"),
            "live_notional": item.get("live_notional"),
            "paper_weight": item.get("paper_weight"),
            "paper_notional": item.get("paper_notional"),
            "score": item.get("score"),
            "reasons": item.get("reasons") or [],
        })
    rows.sort(key=lambda row: (row.get("live_weight") or 0, row.get("paper_weight") or 0), reverse=True)
    return rows[:6]


def _brief_notes(holdings: dict, strategy: dict, trade_review: dict, plan: dict) -> list[str]:
    notes = []
    holdings_summary = holdings.get("summary") or {}
    strategy_summary = strategy.get("summary") or {}
    trade_summary = trade_review.get("summary") or {}
    plan_summary = plan.get("summary") or {}

    if not holdings_summary.get("position_count"):
        notes.append("No real holdings are saved yet; account-level risk monitoring is incomplete.")
    if not strategy_summary.get("ready"):
        notes.append("No model horizon is live-ready; keep this in research or paper mode.")
    if strategy_summary.get("unified_fallback"):
        notes.append("Many symbols still depend on UNIFIED fallback rather than symbol-specific models.")
    if not plan_summary.get("live_weight"):
        notes.append("Live allocation remains locked at 0 until signal and strategy gates improve.")
    if trade_summary.get("missing_review"):
        notes.append("Some trade logs need post-trade reviews before the playbook can learn from them.")
    if not notes:
        notes.append("Workflow is calm; continue monitoring data freshness, risk, and model drift.")
    return notes[:5]


def _build_investment_brief(capital: float = 100000.0) -> dict:
    from ml.action_center import build_action_center_from_parts
    from ml.decision import build_decision_board
    from ml.portfolio import build_portfolio_plan
    from ml.strategy_monitor import build_strategy_monitor

    cache_key = round(float(capital or 100000.0), 2)
    now_ts = time.time()
    cached = INVESTMENT_BRIEF_CACHE.get(cache_key)
    if cached and now_ts - cached[0] < INVESTMENT_BRIEF_TTL_SECONDS:
        return cached[1]

    holdings = _build_portfolio()
    trade_review = _build_trade_review()
    board = build_decision_board(limit=10)
    plan = build_portfolio_plan(capital=capital, limit=10, board=board)
    action_center = build_action_center_from_parts(holdings, board, plan)
    strategy = build_strategy_monitor()

    summary = {
        "portfolio_status": holdings.get("status"),
        "position_count": (holdings.get("summary") or {}).get("position_count", 0),
        "action_items": (action_center.get("summary") or {}).get("total", 0),
        "high_priority_actions": (action_center.get("summary") or {}).get("critical", 0)
            + (action_center.get("summary") or {}).get("high", 0),
        "live_ready_horizons": (strategy.get("summary") or {}).get("ready", 0),
        "watch_horizons": (strategy.get("summary") or {}).get("watch", 0),
        "blocked_horizons": (strategy.get("summary") or {}).get("blocked", 0),
        "live_weight": (plan.get("summary") or {}).get("live_weight", 0.0),
        "paper_weight": (plan.get("summary") or {}).get("paper_weight", 0.0),
        "trade_review_rate": (trade_review.get("summary") or {}).get("review_rate", 0.0),
        "missing_trade_reviews": (trade_review.get("summary") or {}).get("missing_review", 0),
        "top_symbol": (board.get("summary") or {}).get("best_symbol"),
    }

    if summary["high_priority_actions"]:
        status = "attention"
        label = "Needs Attention"
        message = "High-priority items should be reviewed before adding risk."
    elif not summary["live_ready_horizons"]:
        status = "research-only"
        label = "Research Only"
        message = "SkyEye can rank and monitor, but live sizing remains locked by model and strategy gates."
    elif summary["live_weight"]:
        status = "candidate-review"
        label = "Candidate Review"
        message = "Some live allocation is available, still requiring manual review and risk controls."
    else:
        status = "paper-ready"
        label = "Paper Ready"
        message = "Some model horizons are improving; keep them in paper tracking until allocation gates clear."

    result = {
        "generated_at": _now(),
        "capital": round(float(capital or 0.0), 2),
        "status": status,
        "label": label,
        "message": message,
        "summary": summary,
        "mode": "Research / Paper Only" if not summary["live_weight"] else "Candidate Review",
        "priorities": _brief_priority_items(action_center, strategy, trade_review),
        "research_queue": _research_queue(board, strategy),
        "allocation_snapshot": _allocation_snapshot(plan),
        "notes": _brief_notes(holdings, strategy, trade_review, plan),
        "sources": {
            "action_center_status": action_center.get("status"),
            "strategy_status": strategy.get("status"),
            "portfolio_plan_status": plan.get("status"),
            "trade_review_status": trade_review.get("status"),
            "decision_board_best_symbol": summary.get("top_symbol"),
        },
    }
    INVESTMENT_BRIEF_CACHE[cache_key] = (now_ts, result)
    return result


@router.get("")
def get_portfolio():
    return _build_portfolio()


@router.get("/action-center")
def get_action_center(capital: float = 100000.0, limit: int = 10):
    from ml.action_center import build_action_center

    return build_action_center(_build_portfolio(), capital=capital, limit=limit)


@router.get("/investment-brief")
def get_investment_brief(capital: float = 100000.0):
    return _build_investment_brief(capital=capital)


@router.get("/paper-performance")
def get_paper_performance(capital: float = 100000.0, window_days: int = 60, limit: int = 10):
    from ml.paper_performance import build_paper_performance

    return build_paper_performance(capital=capital, window_days=window_days, limit=limit)


@router.get("/rebalance")
def get_rebalance(capital: float = 100000.0, limit: int = 10):
    from ml.portfolio import build_portfolio_plan
    from ml.rebalance import build_rebalance_plan

    holdings = _build_portfolio()
    plan = build_portfolio_plan(capital=capital, limit=limit)
    return build_rebalance_plan(holdings, plan, capital=capital)


@router.get("/trades")
def get_trades(limit: int = 100):
    return _build_trade_journal(limit=limit)


@router.get("/trade-review")
def get_trade_review():
    return _build_trade_review()


@router.post("/trades")
def create_trade(req: TradeRequest):
    payload = _clean_trade_payload(req)
    now = _now()
    conn = get_conn()
    try:
        conn.execute("INSERT OR IGNORE INTO tickers (symbol, name) VALUES (?, ?)", (payload["symbol"], payload["symbol"]))
        cur = conn.execute(
            """INSERT INTO trade_journal
               (symbol, side, quantity, price, trade_date, thesis, setup, review, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["symbol"], payload["side"], payload["quantity"], payload["price"],
                payload["trade_date"], payload["thesis"], payload["setup"], payload["review"], now, now,
            ),
        )
        conn.commit()
        trade_id = cur.lastrowid
    finally:
        conn.close()
    _clear_investment_brief_cache()
    journal = _build_trade_journal()
    journal["created_id"] = trade_id
    return journal


@router.put("/trades/{trade_id}")
def update_trade(trade_id: int, req: TradeRequest):
    payload = _clean_trade_payload(req)
    now = _now()
    conn = get_conn()
    try:
        existing = conn.execute("SELECT id FROM trade_journal WHERE id = ?", (trade_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Trade not found")
        conn.execute(
            """UPDATE trade_journal
               SET symbol = ?, side = ?, quantity = ?, price = ?, trade_date = ?,
                   thesis = ?, setup = ?, review = ?, updated_at = ?
               WHERE id = ?""",
            (
                payload["symbol"], payload["side"], payload["quantity"], payload["price"],
                payload["trade_date"], payload["thesis"], payload["setup"], payload["review"], now, trade_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    _clear_investment_brief_cache()
    return _build_trade_journal()


@router.delete("/trades/{trade_id}")
def delete_trade(trade_id: int):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM trade_journal WHERE id = ?", (trade_id,))
        conn.commit()
    finally:
        conn.close()
    _clear_investment_brief_cache()
    return _build_trade_journal()


@router.put("/positions/{symbol}")
def upsert_position(symbol: str, req: PositionRequest):
    sym = symbol.upper().strip()
    if not sym:
        raise HTTPException(status_code=400, detail="Symbol is required")
    now = _now()
    thesis = (req.thesis or "").strip()[:800]
    conn = get_conn()
    try:
        conn.execute("INSERT OR IGNORE INTO tickers (symbol, name) VALUES (?, ?)", (sym, sym))
        existing = conn.execute(
            "SELECT created_at FROM portfolio_positions WHERE symbol = ?",
            (sym,),
        ).fetchone()
        conn.execute(
            """INSERT INTO portfolio_positions (symbol, shares, avg_cost, thesis, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(symbol) DO UPDATE SET
                   shares = excluded.shares,
                   avg_cost = excluded.avg_cost,
                   thesis = excluded.thesis,
                   updated_at = excluded.updated_at""",
            (sym, req.shares, req.avg_cost, thesis, existing["created_at"] if existing else now, now),
        )
        conn.commit()
    finally:
        conn.close()
    _clear_investment_brief_cache()
    return _build_portfolio()


@router.delete("/positions/{symbol}")
def delete_position(symbol: str):
    sym = symbol.upper().strip()
    conn = get_conn()
    try:
        conn.execute("DELETE FROM portfolio_positions WHERE symbol = ?", (sym,))
        conn.commit()
    finally:
        conn.close()
    _clear_investment_brief_cache()
    return _build_portfolio()
