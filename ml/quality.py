"""Guardrails for interpreting SkyEye quant model metrics."""

from __future__ import annotations


def _number(value) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _lift(score, baseline) -> float | None:
    score_num = _number(score)
    baseline_num = _number(baseline)
    if score_num is None or baseline_num is None:
        return None
    return round(score_num - baseline_num, 4)


def _strategy_quality(backtest: dict | None) -> dict:
    if not isinstance(backtest, dict):
        return {
            "return": None,
            "benchmark_return": None,
            "excess_return": None,
            "sharpe": None,
            "max_drawdown": None,
            "strict_return": None,
            "strict_excess_return": None,
            "strict_sharpe": None,
        }
    long_cash = backtest.get("long_cash")
    strict = backtest.get("non_overlap_long_cash")
    if not isinstance(long_cash, dict):
        long_cash = {}
    if not isinstance(strict, dict):
        strict = {}
    return {
        "return": _number(long_cash.get("total_return")),
        "benchmark_return": _number(long_cash.get("benchmark_return")),
        "excess_return": _number(long_cash.get("excess_return")),
        "sharpe": _number(long_cash.get("sharpe")),
        "max_drawdown": _number(long_cash.get("max_drawdown")),
        "strict_return": _number(strict.get("total_return")),
        "strict_excess_return": _number(strict.get("excess_return")),
        "strict_sharpe": _number(strict.get("sharpe")),
    }


def score_model_quality(meta: dict | None, backtest: dict | None = None) -> dict:
    """Summarize whether a model has beaten its naive baseline."""
    if not isinstance(meta, dict) or "error" in meta:
        return {
            "status": "not-trained",
            "label": "No Model",
            "message": "Train this horizon before treating it as a signal.",
            "holdout_lift": None,
            "cv_lift": None,
            "strategy_excess_return": None,
            "strategy_return": None,
            "strategy_sharpe": None,
            "strict_strategy_excess_return": None,
            "strict_strategy_return": None,
            "strict_strategy_sharpe": None,
            "trade_ready": False,
        }

    holdout_lift = _lift(meta.get("accuracy"), meta.get("baseline"))
    cv_lift = None
    cv_predictions = None
    strategy = _strategy_quality(backtest)

    if isinstance(backtest, dict) and "error" not in backtest:
        cv_lift = _lift(backtest.get("overall_accuracy"), backtest.get("overall_baseline"))
        cv_predictions = _number(backtest.get("total_predictions"))

    if cv_lift is None:
        return {
            "status": "unverified",
            "label": "Unverified",
            "message": "Run cross-validation before using this model as a decision signal.",
            "holdout_lift": holdout_lift,
            "cv_lift": None,
            "strategy_excess_return": strategy["excess_return"],
            "strategy_return": strategy["return"],
            "strategy_sharpe": strategy["sharpe"],
            "strict_strategy_excess_return": strategy["strict_excess_return"],
            "strict_strategy_return": strategy["strict_return"],
            "strict_strategy_sharpe": strategy["strict_sharpe"],
            "trade_ready": False,
        }

    if cv_predictions is not None and cv_predictions < 100:
        return {
            "status": "thin-cv",
            "label": "Thin CV",
            "message": "Backtest coverage is too small to trust yet.",
            "holdout_lift": holdout_lift,
            "cv_lift": cv_lift,
            "strategy_excess_return": strategy["excess_return"],
            "strategy_return": strategy["return"],
            "strategy_sharpe": strategy["sharpe"],
            "strict_strategy_excess_return": strategy["strict_excess_return"],
            "strict_strategy_return": strategy["strict_return"],
            "strict_strategy_sharpe": strategy["strict_sharpe"],
            "trade_ready": False,
        }

    strict_ok = (
        strategy["strict_excess_return"] is None
        or (
            strategy["strict_excess_return"] > 0
            and (strategy["strict_sharpe"] is None or strategy["strict_sharpe"] > 0)
        )
    )
    strategy_ok = (
        strategy["excess_return"] is not None
        and strategy["excess_return"] > 0
        and (strategy["sharpe"] is None or strategy["sharpe"] > 0)
        and strict_ok
    )

    if cv_lift >= 0.02 and (holdout_lift is None or holdout_lift >= 0) and strategy_ok:
        return {
            "status": "validated",
            "label": "Validated",
            "message": "Holdout, cross-validation, and strategy backtest are above baseline.",
            "holdout_lift": holdout_lift,
            "cv_lift": cv_lift,
            "strategy_excess_return": strategy["excess_return"],
            "strategy_return": strategy["return"],
            "strategy_sharpe": strategy["sharpe"],
            "strict_strategy_excess_return": strategy["strict_excess_return"],
            "strict_strategy_return": strategy["strict_return"],
            "strict_strategy_sharpe": strategy["strict_sharpe"],
            "trade_ready": True,
        }

    if cv_lift > 0:
        message = "Cross-validation is above baseline, but the edge is still small."
        if strategy["excess_return"] is not None and strategy["excess_return"] <= 0:
            message = "Cross-validation is above baseline, but the long/cash strategy has not beaten buy-and-hold."
        elif strategy["strict_excess_return"] is not None and strategy["strict_excess_return"] <= 0:
            message = "Cross-validation is above baseline, but the non-overlap strategy check is not above benchmark."
        return {
            "status": "watch",
            "label": "Watch",
            "message": message,
            "holdout_lift": holdout_lift,
            "cv_lift": cv_lift,
            "strategy_excess_return": strategy["excess_return"],
            "strategy_return": strategy["return"],
            "strategy_sharpe": strategy["sharpe"],
            "strict_strategy_excess_return": strategy["strict_excess_return"],
            "strict_strategy_return": strategy["strict_return"],
            "strict_strategy_sharpe": strategy["strict_sharpe"],
            "trade_ready": False,
        }

    if holdout_lift is not None and holdout_lift > 0:
        return {
            "status": "overfit-risk",
            "label": "Overfit Risk",
            "message": "Holdout beats baseline, but cross-validation does not.",
            "holdout_lift": holdout_lift,
            "cv_lift": cv_lift,
            "strategy_excess_return": strategy["excess_return"],
            "strategy_return": strategy["return"],
            "strategy_sharpe": strategy["sharpe"],
            "strict_strategy_excess_return": strategy["strict_excess_return"],
            "strict_strategy_return": strategy["strict_return"],
            "strict_strategy_sharpe": strategy["strict_sharpe"],
            "trade_ready": False,
        }

    return {
        "status": "below-baseline",
        "label": "Below Baseline",
        "message": "This model has not beaten the naive baseline.",
        "holdout_lift": holdout_lift,
        "cv_lift": cv_lift,
        "strategy_excess_return": strategy["excess_return"],
        "strategy_return": strategy["return"],
        "strategy_sharpe": strategy["sharpe"],
        "strict_strategy_excess_return": strategy["strict_excess_return"],
        "strict_strategy_return": strategy["strict_return"],
        "strict_strategy_sharpe": strategy["strict_sharpe"],
        "trade_ready": False,
    }


def build_signal_gate(quality: dict, confidence: float | None = None, backtest: dict | None = None) -> dict:
    """Convert model diagnostics into an explicit research/trading readiness gate."""
    checks = []

    trade_ready = bool(quality.get("trade_ready"))
    checks.append({
        "key": "model_quality",
        "label": "Model Quality",
        "ok": trade_ready,
        "message": quality.get("message") or "Model quality has not been evaluated.",
    })

    strict_excess = _number(quality.get("strict_strategy_excess_return"))
    strict_ok = strict_excess is not None and strict_excess > 0
    checks.append({
        "key": "strict_strategy",
        "label": "Strict Strategy",
        "ok": strict_ok,
        "value": strict_excess,
        "message": "Non-overlap long/cash backtest is above benchmark." if strict_ok else "Non-overlap strategy check is not above benchmark.",
    })

    group_tests = []
    if isinstance(backtest, dict):
        raw_tests = backtest.get("feature_group_tests")
        if isinstance(raw_tests, list):
            group_tests = [item for item in raw_tests if isinstance(item, dict)]
    group_edges = [item for item in group_tests if _number(item.get("cv_lift")) is not None and _number(item.get("cv_lift")) > 0]
    group_ok = not group_tests or bool(group_edges)
    checks.append({
        "key": "driver_groups",
        "label": "Driver Groups",
        "ok": group_ok,
        "message": "At least one driver family has positive standalone CV lift." if group_ok else "No driver family beats baseline on its own.",
    })

    confidence_value = _number(confidence)
    confidence_ok = confidence_value is not None and confidence_value >= 0.55
    checks.append({
        "key": "confidence",
        "label": "Confidence",
        "ok": confidence_ok,
        "value": confidence_value,
        "message": "Prediction confidence is above the research threshold." if confidence_ok else "Prediction confidence is too close to neutral.",
    })

    failed = [check for check in checks if not check["ok"]]
    hard_failed = [check for check in failed if check["key"] in {"model_quality", "strict_strategy", "driver_groups"}]

    if hard_failed:
        status = "research-only"
        label = "Research Only"
        message = "Do not treat this as a trading signal yet."
    elif failed:
        status = "watch"
        label = "Watch"
        message = "Diagnostics are mostly acceptable, but confidence is not strong enough."
    else:
        status = "candidate"
        label = "Candidate"
        message = "Diagnostics pass the current research gate; still require human risk review."

    return {
        "status": status,
        "label": label,
        "message": message,
        "actionable": status == "candidate",
        "checks": checks,
    }
