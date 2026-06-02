"""Paper allocation performance monitor for SkyEye research portfolios."""

from __future__ import annotations

from datetime import datetime, timezone
from math import sqrt
from statistics import pstdev

from database import get_conn
from ml.portfolio import build_portfolio_plan


WINDOWS = (5, 20, 60)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _round(value, digits: int = 4):
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _load_history(symbols: list[str], rows: int = 90) -> dict[str, list[dict]]:
    if not symbols:
        return {}
    conn = get_conn()
    try:
        history: dict[str, list[dict]] = {}
        for symbol in symbols:
            raw_rows = conn.execute(
                """SELECT date, close
                   FROM ohlc
                   WHERE symbol = ?
                   ORDER BY date DESC
                   LIMIT ?""",
                (symbol, rows),
            ).fetchall()
            history[symbol] = [
                {"date": row["date"], "close": float(row["close"])}
                for row in reversed(raw_rows)
                if row["close"] is not None
            ]
    finally:
        conn.close()
    return history


def _window_return(rows: list[dict], window: int) -> float | None:
    if len(rows) <= window:
        return None
    start = rows[-(window + 1)]["close"]
    end = rows[-1]["close"]
    if not start:
        return None
    return end / start - 1.0


def _common_dates(history: dict[str, list[dict]]) -> list[str]:
    date_sets = []
    for rows in history.values():
        if len(rows) >= 2:
            date_sets.append({row["date"] for row in rows})
    if not date_sets:
        return []
    common = set.intersection(*date_sets)
    return sorted(common)


def _available_window(history: dict[str, list[dict]], requested: int) -> int:
    available = [len(rows) - 1 for rows in history.values() if len(rows) > 1]
    if not available:
        return 0
    return max(1, min(requested, min(available)))


def _weighted_window(
    history: dict[str, list[dict]],
    weights: dict[str, float],
    window: int,
    capital: float,
) -> dict:
    symbol_returns = {
        symbol: _window_return(history.get(symbol, []), window)
        for symbol in weights
    }
    valid = {symbol: ret for symbol, ret in symbol_returns.items() if ret is not None}
    if not valid:
        return {
            "window_days": window,
            "total_return": None,
            "benchmark_return": None,
            "active_return": None,
            "ending_value": None,
            "benchmark_value": None,
        }

    valid_weight_sum = sum(weights[symbol] for symbol in valid) or 1.0
    normalized = {symbol: weights[symbol] / valid_weight_sum for symbol in valid}
    total_return = sum(normalized[symbol] * ret for symbol, ret in valid.items())
    benchmark_return = sum(valid.values()) / len(valid)
    return {
        "window_days": window,
        "total_return": _round(total_return),
        "benchmark_return": _round(benchmark_return),
        "active_return": _round(total_return - benchmark_return),
        "ending_value": round(capital * (1.0 + total_return), 2),
        "benchmark_value": round(capital * (1.0 + benchmark_return), 2),
    }


def _daily_returns(
    history: dict[str, list[dict]],
    weights: dict[str, float],
    capital: float,
    max_points: int,
) -> tuple[list[dict], dict]:
    dates = _common_dates(history)
    if len(dates) < 2:
        return [], {
            "total_return": None,
            "benchmark_return": None,
            "active_return": None,
            "annualized_volatility": None,
            "max_drawdown": None,
            "ending_value": None,
            "benchmark_value": None,
        }
    dates = dates[-(max_points + 1):]
    active_weights = {symbol: weight for symbol, weight in weights.items() if len(history.get(symbol, [])) >= 2}
    close_by_symbol = {
        symbol: {row["date"]: row["close"] for row in rows}
        for symbol, rows in history.items()
    }
    weight_sum = sum(active_weights.values()) or 1.0
    normalized = {symbol: value / weight_sum for symbol, value in active_weights.items()}
    initial = {
        symbol: close_by_symbol.get(symbol, {}).get(dates[0])
        for symbol in normalized
    }
    normalized = {symbol: weight for symbol, weight in normalized.items() if initial.get(symbol)}
    if not normalized:
        return [], {
            "total_return": None,
            "benchmark_return": None,
            "active_return": None,
            "annualized_volatility": None,
            "max_drawdown": None,
            "ending_value": None,
            "benchmark_value": None,
        }
    weight_sum = sum(normalized.values()) or 1.0
    normalized = {symbol: value / weight_sum for symbol, value in normalized.items()}
    daily = []
    curve = []
    previous_equity: float | None = None
    for current_date in dates:
        equity = 0.0
        benchmark = 0.0
        valid_symbols = 0
        for symbol, weight in normalized.items():
            current = close_by_symbol.get(symbol, {}).get(current_date)
            start = initial.get(symbol)
            if not start or current is None:
                continue
            relative = current / start
            equity += weight * relative
            benchmark += relative
            valid_symbols += 1
        if not valid_symbols:
            continue
        benchmark /= valid_symbols
        if previous_equity is not None and previous_equity:
            daily.append(equity / previous_equity - 1.0)
        curve.append({
            "date": current_date,
            "paper_value": round(capital * equity, 2),
            "benchmark_value": round(capital * benchmark, 2),
            "paper_return": _round(equity - 1.0),
            "benchmark_return": _round(benchmark - 1.0),
        })
        previous_equity = equity
    if not curve:
        return [], {
            "total_return": None,
            "benchmark_return": None,
            "active_return": None,
            "annualized_volatility": None,
            "max_drawdown": None,
            "ending_value": None,
            "benchmark_value": None,
        }
    equity = (curve[-1]["paper_value"] / capital) if capital else 0.0
    benchmark = (curve[-1]["benchmark_value"] / capital) if capital else 0.0
    total_return = equity - 1.0
    benchmark_return = benchmark - 1.0
    max_drawdown = 0.0
    running_peak = 1.0
    for point in curve:
        value = float(point["paper_value"] or 0.0) / capital if capital else 0.0
        running_peak = max(running_peak, value)
        if running_peak:
            max_drawdown = min(max_drawdown, value / running_peak - 1.0)
    return curve[-45:], {
        "total_return": _round(total_return),
        "benchmark_return": _round(benchmark_return),
        "active_return": _round(total_return - benchmark_return),
        "ending_value": round(capital * equity, 2),
        "benchmark_value": round(capital * benchmark, 2),
        "annualized_volatility": _round(pstdev(daily) * sqrt(252)) if len(daily) > 1 else None,
        "max_drawdown": _round(max_drawdown),
    }


def build_paper_performance(capital: float = 100000.0, limit: int = 10, window_days: int = 60) -> dict:
    capital = max(float(capital or 100000.0), 0.0)
    window_days = max(5, min(int(window_days or 60), 120))
    plan = build_portfolio_plan(capital=capital, limit=limit)
    allocations = [
        item for item in plan.get("allocations", [])
        if float(item.get("paper_weight") or 0.0) > 0
    ]
    weights = {item["symbol"]: float(item.get("paper_weight") or 0.0) for item in allocations}
    weight_sum = sum(weights.values())
    if not allocations or not weight_sum:
        return {
            "generated_at": _now_iso(),
            "capital": round(capital, 2),
            "window_days": window_days,
            "status": "setup",
            "label": "No Paper Book",
            "message": "Build a paper allocation plan before monitoring research performance.",
            "plan_status": plan.get("status"),
            "summary": {
                "allocation_count": 0,
                "paper_weight": 0.0,
                "paper_notional": 0.0,
                "total_return": None,
                "benchmark_return": None,
                "active_return": None,
                "ending_value": None,
                "benchmark_value": None,
                "annualized_volatility": None,
                "max_drawdown": None,
                "best_contributor": None,
                "worst_contributor": None,
            },
            "windows": [],
            "contributions": [],
            "curve": [],
        }

    symbols = [item["symbol"] for item in allocations]
    max_window = max(max(WINDOWS), window_days)
    history = _load_history(symbols, rows=max_window + 8)
    actual_window = _available_window(history, window_days)
    normalized = {symbol: weight / weight_sum for symbol, weight in weights.items()}
    contributions = []
    for item in allocations:
        symbol = item["symbol"]
        rows = history.get(symbol, [])
        ret = _window_return(rows, actual_window) if actual_window else None
        contribution = normalized[symbol] * ret if ret is not None else None
        contributions.append({
            "symbol": symbol,
            "label": item.get("label"),
            "weight": _round(normalized[symbol]),
            "paper_notional": round(capital * normalized[symbol], 2),
            "latest_close": item.get("latest_close"),
            "total_return": _round(ret),
            "contribution": _round(contribution),
            "score": item.get("score"),
            "allocation_status": item.get("allocation_status"),
        })
    contributions.sort(key=lambda row: row["contribution"] if row["contribution"] is not None else -999, reverse=True)

    windows = []
    for window in WINDOWS:
        if _available_window(history, window) >= window:
            windows.append(_weighted_window(history, normalized, window, capital))

    curve, curve_stats = _daily_returns(history, normalized, capital, actual_window or window_days)
    best = next((row for row in contributions if row.get("contribution") is not None), None)
    worst = next((row for row in reversed(contributions) if row.get("contribution") is not None), None)
    active = curve_stats.get("active_return")
    drawdown = curve_stats.get("max_drawdown")
    if active is None:
        status = "setup"
        label = "Insufficient History"
        message = "Paper performance cannot be calculated until enough OHLC history is available."
    elif active > 0 and (drawdown is None or drawdown > -0.08):
        status = "outperforming"
        label = "Outperforming"
        message = "Current paper weights are ahead of an equal-weight research benchmark over the monitored window."
    elif active > 0:
        status = "tracking"
        label = "Tracking"
        message = "Paper weights are ahead of benchmark, but drawdown risk is visible."
    else:
        status = "lagging"
        label = "Lagging"
        message = "Paper weights are trailing the equal-weight research benchmark over the monitored window."

    return {
        "generated_at": _now_iso(),
        "capital": round(capital, 2),
        "window_days": actual_window or window_days,
        "status": status,
        "label": label,
        "message": message,
        "plan_status": plan.get("status"),
        "summary": {
            "allocation_count": len(symbols),
            "paper_weight": _round(weight_sum),
            "paper_notional": round(capital * weight_sum, 2),
            "total_return": curve_stats.get("total_return"),
            "benchmark_return": curve_stats.get("benchmark_return"),
            "active_return": curve_stats.get("active_return"),
            "ending_value": curve_stats.get("ending_value"),
            "benchmark_value": curve_stats.get("benchmark_value"),
            "annualized_volatility": curve_stats.get("annualized_volatility"),
            "max_drawdown": curve_stats.get("max_drawdown"),
            "best_contributor": best.get("symbol") if best else None,
            "worst_contributor": worst.get("symbol") if worst else None,
        },
        "windows": windows,
        "contributions": contributions[:10],
        "curve": curve,
    }
