"""Research trade setup planner for SkyEye.

The planner converts catalyst and risk context into conservative research-only
entry, invalidation, and target zones. It is not an order generator.
"""

from __future__ import annotations

from datetime import datetime, timezone

from database import get_conn
from ml.catalyst import build_catalyst_radar
from ml.decision import build_decision_board


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _round(value, digits: int = 4):
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _load_ohlc(symbol: str, limit: int = 90) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT date, open, high, low, close
               FROM ohlc
               WHERE symbol = ?
               ORDER BY date DESC
               LIMIT ?""",
            (symbol.upper(), limit),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in reversed(rows)]


def _atr(rows: list[dict], period: int = 14) -> float | None:
    if len(rows) < period + 1:
        return None
    ranges = []
    for prev, current in zip(rows, rows[1:]):
        high = float(current["high"] or current["close"] or 0.0)
        low = float(current["low"] or current["close"] or 0.0)
        prev_close = float(prev["close"] or 0.0)
        ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    if len(ranges) < period:
        return None
    return sum(ranges[-period:]) / period


def _levels(symbol: str) -> dict | None:
    rows = _load_ohlc(symbol)
    if len(rows) < 30:
        return None
    latest = rows[-1]
    close = float(latest["close"] or 0.0)
    if close <= 0:
        return None
    atr = _atr(rows) or close * 0.035
    recent_20 = rows[-20:]
    recent_60 = rows[-60:] if len(rows) >= 60 else rows
    support_20 = min(float(row["low"] or row["close"] or close) for row in recent_20)
    resistance_20 = max(float(row["high"] or row["close"] or close) for row in recent_20)
    support_60 = min(float(row["low"] or row["close"] or close) for row in recent_60)
    resistance_60 = max(float(row["high"] or row["close"] or close) for row in recent_60)
    return {
        "as_of": latest["date"],
        "latest_close": close,
        "atr_14": atr,
        "atr_pct": atr / close,
        "support_20d": support_20,
        "resistance_20d": resistance_20,
        "support_60d": support_60,
        "resistance_60d": resistance_60,
        "near_breakout": close >= resistance_20 - 0.35 * atr,
        "extended": close > support_20 + 3.2 * atr,
    }


def _risk_reward(entry: float | None, stop: float | None, target: float | None) -> float | None:
    if entry is None or stop is None or target is None or entry <= stop:
        return None
    risk = entry - stop
    if risk <= 0:
        return None
    return (target - entry) / risk


def _setup_for(catalyst: dict, decision: dict | None, capital: float) -> dict:
    symbol = catalyst["symbol"]
    levels = _levels(symbol)
    if not levels:
        return {
            "symbol": symbol,
            "status": "setup",
            "label": "No Levels",
            "message": "Not enough OHLC history to create a research setup.",
            "action": "Refresh OHLC data before planning levels.",
            "score": catalyst.get("score") or 0,
            "bias": catalyst.get("bias"),
            "levels": None,
        }

    close = levels["latest_close"]
    atr = levels["atr_14"]
    bullish = catalyst.get("bias") == "bullish"
    bearish = catalyst.get("bias") == "bearish"
    hot = catalyst.get("status") == "hot"
    decision_status = (decision or {}).get("decision_status")
    decision_score = int((decision or {}).get("score") or 0)
    live_ready = bool((decision or {}).get("actionable_horizons"))
    catalyst_score = int(catalyst.get("score") or 0)

    if bearish:
        entry_low = None
        entry_high = None
        stop_loss = None
        target_1 = None
        target_2 = None
        status = "avoid"
        label = "Avoid New Buy"
        message = "Catalyst bias is bearish; do not chase a long setup without a fresh thesis."
        action = "Use support breaks and Risk Brief to decide whether existing exposure should be reduced."
        setup_type = "risk-review"
    else:
        if levels["near_breakout"] and bullish:
            setup_type = "breakout"
            entry_low = max(close - 0.25 * atr, levels["resistance_20d"] - 0.45 * atr)
            entry_high = levels["resistance_20d"] + 0.2 * atr
        else:
            setup_type = "pullback"
            entry_low = max(levels["support_20d"], close - 1.15 * atr)
            entry_high = max(entry_low + 0.35 * atr, close - 0.35 * atr)

        stop_loss = min(levels["support_20d"] - 0.45 * atr, entry_low - 0.9 * atr)
        risk = max(entry_high - stop_loss, atr)
        resistance_anchor = max(levels["resistance_20d"], close)
        target_1 = max(resistance_anchor + 0.35 * atr, entry_high + 1.6 * risk)
        target_2 = max(levels["resistance_60d"] + 0.25 * atr, entry_high + 2.4 * risk)

        if live_ready and decision_status == "candidate" and catalyst_score >= 55:
            status = "candidate"
            label = "Review Candidate"
            message = "Catalyst and signal gates are aligned enough for manual review."
            action = "Check news drivers, position size, and trade journal before any live order."
        elif bullish and (hot or decision_score >= 55):
            status = "paper-watch"
            label = "Paper Watch"
            message = "Catalyst is constructive, but live sizing still depends on model and risk gates."
            action = "Track the entry zone in paper mode and wait for confirmation before live exposure."
        else:
            status = "wait"
            label = "Wait"
            message = "The catalyst is not strong enough to justify chasing price."
            action = "Keep it on watch; revisit if news, price reaction, or model gates improve."

    entry_mid = ((entry_low + entry_high) / 2) if entry_low is not None and entry_high is not None else None
    rr1 = _risk_reward(entry_mid, stop_loss, target_1)
    rr2 = _risk_reward(entry_mid, stop_loss, target_2)
    max_position_notional = None
    if entry_mid and stop_loss and entry_mid > stop_loss:
        risk_budget = capital * 0.005 if status == "candidate" else capital * 0.0025 if status == "paper-watch" else 0.0
        max_position_notional = risk_budget / ((entry_mid - stop_loss) / entry_mid) if risk_budget else 0.0

    return {
        "symbol": symbol,
        "status": status,
        "label": label,
        "message": message,
        "action": action,
        "setup_type": setup_type,
        "score": round(catalyst_score * 0.55 + decision_score * 0.45),
        "catalyst_score": catalyst_score,
        "decision_score": decision_score,
        "decision_status": decision_status,
        "bias": catalyst.get("bias"),
        "bias_label": catalyst.get("bias_label"),
        "latest_headline": (catalyst.get("headlines") or [{}])[0].get("title"),
        "news_count": catalyst.get("news_count"),
        "sentiment_ratio": catalyst.get("sentiment_ratio"),
        "trend_5d": catalyst.get("trend_5d"),
        "trend_20d": catalyst.get("trend_20d"),
        "entry_low": _round(entry_low, 2),
        "entry_high": _round(entry_high, 2),
        "stop_loss": _round(stop_loss, 2),
        "target_1": _round(target_1, 2),
        "target_2": _round(target_2, 2),
        "risk_reward_1": _round(rr1, 2),
        "risk_reward_2": _round(rr2, 2),
        "max_position_notional": round(max_position_notional, 2) if max_position_notional is not None else None,
        "levels": {
            "as_of": levels["as_of"],
            "latest_close": _round(close, 2),
            "atr_14": _round(atr, 2),
            "atr_pct": _round(levels["atr_pct"]),
            "support_20d": _round(levels["support_20d"], 2),
            "resistance_20d": _round(levels["resistance_20d"], 2),
            "support_60d": _round(levels["support_60d"], 2),
            "resistance_60d": _round(levels["resistance_60d"], 2),
            "near_breakout": levels["near_breakout"],
            "extended": levels["extended"],
        },
        "rationale": [
            f"Catalyst {catalyst.get('label')} / {catalyst.get('bias_label')}",
            f"Decision {decision_status or 'unscored'} / score {decision_score}",
            f"ATR {levels['atr_pct']:.1%}",
        ],
    }


def build_trade_setups(capital: float = 100000.0, lookback_days: int = 10, limit: int = 8) -> dict:
    capital = max(float(capital or 100000.0), 0.0)
    limit = max(1, min(int(limit or 8), 12))
    catalyst = build_catalyst_radar(lookback_days=lookback_days, limit=max(limit, 10))
    symbols = [row["symbol"] for row in catalyst.get("rows", [])[:limit]]
    board = build_decision_board(symbols=symbols, limit=limit, lookback_days=30)
    decisions = {row["symbol"]: row for row in board.get("rows", [])}
    rows = [_setup_for(row, decisions.get(row["symbol"]), capital) for row in catalyst.get("rows", [])[:limit]]
    rows.sort(key=lambda row: (
        row.get("status") == "candidate",
        row.get("status") == "paper-watch",
        row.get("score") or 0,
    ), reverse=True)
    for index, row in enumerate(rows, start=1):
        row["rank"] = index

    candidate = sum(1 for row in rows if row["status"] == "candidate")
    paper_watch = sum(1 for row in rows if row["status"] == "paper-watch")
    avoid = sum(1 for row in rows if row["status"] == "avoid")
    wait = sum(1 for row in rows if row["status"] == "wait")
    top = rows[0] if rows else None

    if candidate:
        status = "candidate-review"
        label = "Candidate Review"
        message = "At least one setup has catalyst and gate alignment; manual review is still required."
    elif paper_watch:
        status = "paper-watch"
        label = "Paper Watch"
        message = "Constructive setups exist, but live sizing remains locked behind research gates."
    elif avoid:
        status = "risk-review"
        label = "Risk Review"
        message = "Bearish or mixed catalysts dominate; avoid new longs until conditions improve."
    else:
        status = "wait"
        label = "Wait"
        message = "No setup currently clears the research threshold."

    return {
        "generated_at": _now_iso(),
        "capital": round(capital, 2),
        "lookback_days": lookback_days,
        "status": status,
        "label": label,
        "message": message,
        "summary": {
            "rows": len(rows),
            "candidates": candidate,
            "paper_watch": paper_watch,
            "avoid": avoid,
            "wait": wait,
            "top_symbol": top.get("symbol") if top else None,
            "top_status": top.get("status") if top else None,
        },
        "rows": rows,
        "sources": {
            "catalyst_status": catalyst.get("status"),
            "decision_board_status": (board.get("summary") or {}).get("best_symbol"),
            "mode": "research-only levels; not automated advice",
        },
    }
