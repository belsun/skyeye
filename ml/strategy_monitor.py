"""Strategy readiness monitor for SkyEye quant models."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ml.decision import DEFAULT_UNIVERSE, _coverage, _dedupe_symbols
from ml.quality import score_model_quality


MODELS_DIR = Path(__file__).resolve().parent / "models"
HORIZONS = ("t1", "t5")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        return {"error": f"Cannot read {path.name}: {exc}"}


def _round(value, digits: int = 4):
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _age_days(date_text: str | None) -> int | None:
    if not date_text:
        return None
    try:
        parsed = datetime.strptime(date_text[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return max(0, (datetime.now(timezone.utc).date() - parsed).days)


def _feature_group_edges(backtest: dict | None) -> list[dict]:
    tests = backtest.get("feature_group_tests") if isinstance(backtest, dict) else []
    if not isinstance(tests, list):
        return []
    rows = []
    for item in tests:
        if not isinstance(item, dict):
            continue
        cv_lift = _round(item.get("cv_lift"))
        if cv_lift is None or cv_lift <= 0:
            continue
        rows.append({
            "key": item.get("key"),
            "label": item.get("label") or item.get("key") or "Group",
            "cv_lift": cv_lift,
            "accuracy": _round(item.get("accuracy")),
            "baseline": _round(item.get("baseline")),
        })
    return sorted(rows, key=lambda row: row["cv_lift"], reverse=True)


def _per_ticker_diagnostic(backtest: dict | None, symbol: str) -> dict | None:
    if not isinstance(backtest, dict):
        return None
    per_ticker = backtest.get("per_ticker")
    if not isinstance(per_ticker, dict):
        return None
    item = per_ticker.get(symbol)
    if not isinstance(item, dict):
        return None

    long_cash = item.get("long_cash") if isinstance(item.get("long_cash"), dict) else {}
    strict = item.get("non_overlap_long_cash") if isinstance(item.get("non_overlap_long_cash"), dict) else {}
    accuracy = _round(item.get("accuracy"))
    baseline = _round(item.get("baseline"))
    cv_lift = _round((accuracy - baseline) if accuracy is not None and baseline is not None else None)
    strict_excess = _round(strict.get("excess_return"))
    strategy_excess = _round(long_cash.get("excess_return"))
    if cv_lift is not None and cv_lift > 0 and (strict_excess or strategy_excess or 0) > 0:
        verdict = "edge"
    elif (cv_lift is not None and cv_lift > 0) or (strict_excess or strategy_excess or 0) > 0:
        verdict = "watch"
    else:
        verdict = "weak"
    return {
        "n": int(item.get("n") or 0),
        "accuracy": accuracy,
        "baseline": baseline,
        "cv_lift": cv_lift,
        "strategy_excess_return": strategy_excess,
        "strict_strategy_excess_return": strict_excess,
        "strict_strategy_sharpe": _round(strict.get("sharpe")),
        "verdict": verdict,
    }


def _coverage_safe(symbol: str) -> dict:
    try:
        return _coverage(symbol)
    except Exception as exc:
        return {
            "status": "unknown",
            "label": "Unknown",
            "issues": [str(exc)],
            "ohlc_age_days": None,
            "label_coverage": None,
            "analyzed_news": 0,
        }


def _model_row(symbol: str, horizon: str) -> dict:
    own_model = MODELS_DIR / f"{symbol}_{horizon}.joblib"
    model_symbol = symbol if own_model.exists() else "UNIFIED"
    source = "symbol" if model_symbol == symbol else "unified-fallback"

    model_path = MODELS_DIR / f"{model_symbol}_{horizon}.joblib"
    meta = _read_json(MODELS_DIR / f"{model_symbol}_{horizon}_meta.json")
    backtest = _read_json(MODELS_DIR / f"{model_symbol}_{horizon}_backtest.json")
    trained = model_path.exists() and isinstance(meta, dict) and "error" not in meta
    quality = score_model_quality(meta, backtest)
    coverage = _coverage_safe(symbol) if symbol != "UNIFIED" else {
        "status": "universe",
        "label": "Universe",
        "issues": [],
        "ohlc_age_days": None,
        "label_coverage": None,
        "analyzed_news": None,
    }

    group_edges = _feature_group_edges(backtest)
    per_ticker = _per_ticker_diagnostic(backtest, symbol) if source == "unified-fallback" else None
    strict_excess = _round(quality.get("strict_strategy_excess_return"))
    cv_lift = _round(quality.get("cv_lift"))
    data_ok = coverage.get("status") in {"healthy", "watch", "universe"}
    driver_ok = bool(group_edges) or not (isinstance(backtest, dict) and backtest.get("feature_group_tests"))
    strict_ok = strict_excess is not None and strict_excess > 0
    ready = bool(quality.get("trade_ready")) and strict_ok and driver_ok and data_ok

    issues = []
    if not trained:
        issues.append("model missing")
    if not quality.get("trade_ready"):
        issues.append(quality.get("label") or "quality not ready")
    if not strict_ok:
        issues.append("strict strategy not above benchmark")
    if not driver_ok:
        issues.append("driver groups weak")
    if not data_ok:
        issues.append(coverage.get("label") or "data quality")
    if source == "unified-fallback":
        issues.append("using unified fallback")

    if not trained:
        status = "missing"
        label = "Missing"
        action = "Train this horizon before using it in a research workflow."
    elif ready:
        status = "ready"
        label = "Ready"
        action = "Eligible for paper tracking; still require manual risk review."
    elif quality.get("status") in {"watch", "validated"} or (
        per_ticker and per_ticker.get("verdict") in {"edge", "watch"}
    ):
        status = "watch"
        label = "Watch"
        action = "Keep in research rotation and rerun strict backtests after more data."
    else:
        status = "blocked"
        label = "Blocked"
        action = "Do not promote this horizon to live sizing until quality and strategy checks improve."

    return {
        "symbol": symbol,
        "horizon": horizon,
        "model_symbol": model_symbol,
        "source": source,
        "trained": trained,
        "status": status,
        "label": label,
        "action": action,
        "issues": issues[:5],
        "model_type": meta.get("model_type") if isinstance(meta, dict) else None,
        "model_package": meta.get("model_package") if isinstance(meta, dict) else None,
        "test_end": meta.get("test_end") if isinstance(meta, dict) else None,
        "model_age_days": _age_days(meta.get("test_end")) if isinstance(meta, dict) else None,
        "quality_status": quality.get("status"),
        "quality_label": quality.get("label"),
        "holdout_lift": _round(quality.get("holdout_lift")),
        "cv_lift": cv_lift,
        "strategy_excess_return": _round(quality.get("strategy_excess_return")),
        "strategy_sharpe": _round(quality.get("strategy_sharpe")),
        "strict_strategy_excess_return": strict_excess,
        "strict_strategy_sharpe": _round(quality.get("strict_strategy_sharpe")),
        "trade_ready": bool(quality.get("trade_ready")),
        "backtest_available": isinstance(backtest, dict) and "error" not in backtest,
        "total_predictions": int(backtest.get("total_predictions") or 0) if isinstance(backtest, dict) else 0,
        "feature_group_edges": group_edges[:3],
        "top_driver_group": group_edges[0]["label"] if group_edges else None,
        "coverage_status": coverage.get("status"),
        "coverage_label": coverage.get("label"),
        "ohlc_age_days": coverage.get("ohlc_age_days"),
        "label_coverage": coverage.get("label_coverage"),
        "analyzed_news": coverage.get("analyzed_news"),
        "per_ticker": per_ticker,
    }


def _summary(rows: list[dict]) -> dict:
    symbol_rows = [row for row in rows if row["symbol"] != "UNIFIED"]
    return {
        "rows": len(rows),
        "symbols": len({row["symbol"] for row in symbol_rows}),
        "ready": sum(1 for row in rows if row["status"] == "ready"),
        "watch": sum(1 for row in rows if row["status"] == "watch"),
        "blocked": sum(1 for row in rows if row["status"] == "blocked"),
        "missing": sum(1 for row in rows if row["status"] == "missing"),
        "unified_fallback": sum(1 for row in symbol_rows if row["source"] == "unified-fallback"),
        "trained": sum(1 for row in rows if row["trained"]),
        "best_cv_lift": max((row["cv_lift"] for row in rows if row["cv_lift"] is not None), default=None),
        "best_strict_excess_return": max(
            (row["strict_strategy_excess_return"] for row in rows if row["strict_strategy_excess_return"] is not None),
            default=None,
        ),
    }


def _actions(summary: dict, rows: list[dict]) -> list[dict]:
    actions = []
    if summary["ready"] == 0:
        actions.append({
            "priority": "high",
            "title": "No Live-Ready Model Horizon",
            "message": "Every monitored horizon is blocked or watch-only.",
            "action": "Keep allocations in research/paper mode until strict strategy checks turn positive.",
            "evidence": [f"{summary['blocked']} blocked", f"{summary['watch']} watch"],
        })
    if summary["unified_fallback"]:
        actions.append({
            "priority": "medium",
            "title": "Single-Symbol Models Missing",
            "message": "Several symbols still depend on the UNIFIED model fallback.",
            "action": "Train symbol-specific models only after each symbol has enough labeled news and OHLC coverage.",
            "evidence": [f"{summary['unified_fallback']} fallback horizons"],
        })
    weak_driver = sum(1 for row in rows if "driver groups weak" in row.get("issues", []))
    if weak_driver:
        actions.append({
            "priority": "medium",
            "title": "Driver Groups Need Proof",
            "message": "Backtests do not show standalone edge from any driver family on some horizons.",
            "action": "Compare technical, market-regime, and sentiment feature groups before trusting model outputs.",
            "evidence": [f"{weak_driver} weak driver rows"],
        })
    stale = [row for row in rows if row.get("ohlc_age_days") is not None and row["ohlc_age_days"] > 7]
    if stale:
        actions.append({
            "priority": "low",
            "title": "Refresh Market Data",
            "message": "Some monitored symbols have stale OHLC coverage.",
            "action": "Refresh market data before retraining or interpreting signal gates.",
            "evidence": sorted({row["symbol"] for row in stale})[:5],
        })
    return actions[:5]


def build_strategy_monitor(symbols: list[str] | None = None) -> dict:
    selected = _dedupe_symbols(symbols) or DEFAULT_UNIVERSE
    rows = [_model_row("UNIFIED", horizon) for horizon in HORIZONS]
    for symbol in selected:
        rows.extend(_model_row(symbol, horizon) for horizon in HORIZONS)
    summary = _summary(rows)

    if summary["ready"]:
        status = "candidate-review"
        label = "Candidate Review"
        message = "At least one model horizon passes monitor checks; keep it in paper tracking before live sizing."
    elif summary["watch"]:
        status = "watch"
        label = "Watch"
        message = "Some model horizons have partial edge, but none are ready for live allocation."
    elif summary["trained"]:
        status = "research-only"
        label = "Research Only"
        message = "Models exist, but quality, strict strategy, or driver checks block live usage."
    else:
        status = "setup"
        label = "Setup Needed"
        message = "Train quant models before using SkyEye as a strategy assistant."

    return {
        "generated_at": _now_iso(),
        "status": status,
        "label": label,
        "message": message,
        "horizons": list(HORIZONS),
        "summary": summary,
        "actions": _actions(summary, rows),
        "rows": rows,
    }
