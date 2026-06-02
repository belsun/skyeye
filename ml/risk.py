"""Risk brief for research workflows."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from database import get_conn


def _pct(value) -> float | None:
    if value is None:
        return None
    try:
        if not np.isfinite(value):
            return None
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _load_ohlc(symbol: str) -> pd.DataFrame:
    conn = get_conn()
    rows = conn.execute(
        """SELECT date, open, high, low, close, volume
           FROM ohlc
           WHERE symbol = ?
           ORDER BY date""",
        (symbol.upper(),),
    ).fetchall()
    conn.close()
    df = pd.DataFrame([dict(row) for row in rows])
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df


def _prediction_summary(symbol: str) -> dict:
    from ml.model import predict

    items = {}
    for horizon in ("t1", "t5"):
        result = predict(symbol, horizon)
        if "error" in result:
            items[horizon] = {"error": result["error"]}
            continue
        gate = result.get("signal_gate") or {}
        items[horizon] = {
            "direction": result.get("direction"),
            "confidence": result.get("confidence"),
            "model_quality": result.get("model_quality"),
            "trade_ready": bool(result.get("trade_ready")),
            "gate_status": gate.get("status"),
            "gate_label": gate.get("label"),
            "actionable": bool(gate.get("actionable")),
            "failed_checks": [
                check.get("key")
                for check in gate.get("checks", [])
                if isinstance(check, dict) and not check.get("ok")
            ],
        }
    return items


def build_risk_brief(symbol: str) -> dict:
    """Build a conservative risk brief from price data and model gates."""
    sym = symbol.upper()
    df = _load_ohlc(sym)
    if df.empty or len(df) < 30:
        return {"symbol": sym, "error": f"Not enough OHLC data for {sym}"}

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    returns = close.pct_change()
    latest_close = float(close.iloc[-1])
    latest_date = df["date"].iloc[-1].strftime("%Y-%m-%d")

    prev_close = close.shift(1)
    true_range = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr_14 = float(true_range.rolling(14).mean().iloc[-1])
    atr_pct = atr_14 / latest_close if latest_close else None

    volatility_20d = float(returns.tail(20).std())
    volatility_60d = float(returns.tail(60).std()) if len(returns.dropna()) >= 60 else None
    annualized_volatility = volatility_20d * math.sqrt(252)

    trailing_60 = close.tail(60)
    drawdown_60d = float((trailing_60 / trailing_60.cummax() - 1).min())
    trend_20d = float(close.iloc[-1] / close.iloc[-21] - 1) if len(close) >= 21 else None
    trend_60d = float(close.iloc[-1] / close.iloc[-61] - 1) if len(close) >= 61 else None

    predictions = _prediction_summary(sym)
    actionable_horizons = [
        horizon for horizon, item in predictions.items()
        if isinstance(item, dict) and item.get("actionable")
    ]

    notes = []
    if not actionable_horizons:
        notes.append("No horizon passes the current signal gate; keep this in research mode.")
    if atr_pct is not None and atr_pct > 0.05:
        notes.append("ATR is elevated; price can move sharply against a thesis.")
    if annualized_volatility > 0.55:
        notes.append("Annualized volatility is high; any sizing model should be conservative.")
    if drawdown_60d < -0.2:
        notes.append("Recent drawdown is deep; avoid assuming a quick mean reversion.")
    if not notes:
        notes.append("Risk metrics are within normal research thresholds, but model gate still controls actionability.")

    if actionable_horizons:
        status = "candidate"
        label = "Sizing Candidate"
        max_risk = 0.005
        sizing_enabled = True
        message = "At least one horizon passed the signal gate; review risk manually before any action."
    else:
        status = "research-only"
        label = "Research Only"
        max_risk = 0.0
        sizing_enabled = False
        message = "Model gates block position sizing for this symbol."

    stop_distance_pct = None
    if atr_pct is not None:
        stop_distance_pct = min(max(atr_pct * 2, 0.03), 0.18)

    return {
        "symbol": sym,
        "as_of": latest_date,
        "status": status,
        "label": label,
        "message": message,
        "latest_close": round(latest_close, 4),
        "volatility_20d": _pct(volatility_20d),
        "volatility_60d": _pct(volatility_60d),
        "annualized_volatility_20d": _pct(annualized_volatility),
        "atr_14": round(atr_14, 4),
        "atr_pct": _pct(atr_pct),
        "drawdown_60d": _pct(drawdown_60d),
        "trend_20d": _pct(trend_20d),
        "trend_60d": _pct(trend_60d),
        "risk_budget": {
            "position_sizing_enabled": sizing_enabled,
            "max_portfolio_risk_pct": max_risk,
            "reference_stop_distance_pct": _pct(stop_distance_pct),
            "actionable_horizons": actionable_horizons,
        },
        "predictions": predictions,
        "notes": notes,
    }
