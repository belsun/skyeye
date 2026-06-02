"""Expanding-window cross-validation backtest."""

import json
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from ml.features import build_features, build_features_multi, FEATURE_COLS, FEATURE_GROUPS
from ml.model import _fit_classifier, _make_classifier

MODELS_DIR = Path(__file__).parent / "models"


def _horizon_days(horizon: str) -> int:
    try:
        return max(1, int(horizon.replace("t", "")))
    except ValueError:
        return 1


def _forward_returns(df, horizon: str) -> np.ndarray:
    days = _horizon_days(horizon)
    if "symbol" in df.columns:
        return (
            df.groupby("symbol")["close"]
            .transform(lambda close: close.shift(-days) / close - 1)
            .values
        )
    return (df["close"].shift(-days) / df["close"] - 1).values


def _max_drawdown(returns: np.ndarray) -> float:
    if len(returns) == 0:
        return 0.0
    equity = np.cumprod(1 + np.clip(returns, -0.99, None))
    peak = np.maximum.accumulate(equity)
    drawdown = equity / np.clip(peak, 1e-12, None) - 1
    return float(drawdown.min())


def _daily_equity_returns(raw_returns: np.ndarray, dates, horizon: str) -> np.ndarray:
    daily_equiv = raw_returns / _horizon_days(horizon)
    if dates is None:
        return daily_equiv

    buckets: dict[str, list[float]] = {}
    for date, value in zip(dates, daily_equiv):
        if np.isfinite(value):
            buckets.setdefault(str(date), []).append(float(value))
    return np.array([np.mean(buckets[date]) for date in sorted(buckets)], dtype=float)


def _strategy_metrics(preds, forward_returns, horizon: str, mode: str = "long_cash", dates=None) -> dict:
    """Convert directional predictions into simple out-of-sample trading metrics."""
    returns = np.asarray(forward_returns, dtype=float)
    predictions = np.asarray(preds, dtype=int)
    mask = np.isfinite(returns)
    returns = returns[mask]
    predictions = predictions[mask]
    if dates is not None:
        date_arr = np.asarray(dates, dtype=object)[mask]
    else:
        date_arr = None
    if len(returns) == 0:
        return {
            "mode": mode,
            "total_return": None,
            "benchmark_return": None,
            "excess_return": None,
            "average_return": None,
            "volatility": None,
            "sharpe": None,
            "max_drawdown": None,
            "exposure": None,
            "trades": 0,
        }

    if mode == "long_short":
        positions = np.where(predictions == 1, 1.0, -1.0)
    else:
        positions = np.where(predictions == 1, 1.0, 0.0)

    per_signal_strategy = positions * returns
    per_signal_benchmark = returns
    strategy_returns = _daily_equity_returns(per_signal_strategy, date_arr, horizon)
    benchmark_returns = _daily_equity_returns(per_signal_benchmark, date_arr, horizon)
    total_return = float(np.prod(1 + np.clip(strategy_returns, -0.99, None)) - 1)
    benchmark_return = float(np.prod(1 + np.clip(benchmark_returns, -0.99, None)) - 1)
    vol = float(np.std(strategy_returns, ddof=1)) if len(strategy_returns) > 1 else 0.0
    sharpe = float(np.mean(strategy_returns) / vol * np.sqrt(252)) if vol > 0 else 0.0
    trades = int(np.count_nonzero(np.diff(positions)) + (positions[0] != 0))

    return {
        "mode": mode,
        "total_return": round(total_return, 4),
        "benchmark_return": round(benchmark_return, 4),
        "excess_return": round(total_return - benchmark_return, 4),
        "average_return": round(float(np.mean(per_signal_strategy)), 4),
        "average_daily_return": round(float(np.mean(strategy_returns)), 4),
        "benchmark_average_return": round(float(np.mean(per_signal_benchmark)), 4),
        "volatility": round(vol, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(_max_drawdown(strategy_returns), 4),
        "exposure": round(float(np.mean(np.abs(positions))), 4),
        "trades": trades,
    }


def _non_overlap_strategy_metrics(preds, forward_returns, horizon: str, mode: str = "long_cash", dates=None) -> dict:
    """Sample one horizon-spaced signal per rebalance period to avoid overlapping returns."""
    days = _horizon_days(horizon)
    returns = np.asarray(forward_returns, dtype=float)
    predictions = np.asarray(preds, dtype=int)
    mask = np.isfinite(returns)
    returns = returns[mask]
    predictions = predictions[mask]
    if dates is not None:
        date_arr = np.asarray(dates, dtype=object)[mask]
    else:
        date_arr = None

    empty = {
        "mode": mode,
        "rebalance_period_days": days,
        "sampled_periods": 0,
        "total_return": None,
        "benchmark_return": None,
        "excess_return": None,
        "average_return": None,
        "average_daily_return": None,
        "benchmark_average_return": None,
        "volatility": None,
        "sharpe": None,
        "max_drawdown": None,
        "exposure": None,
        "trades": 0,
    }
    if len(returns) == 0:
        return empty

    if mode == "long_short":
        positions = np.where(predictions == 1, 1.0, -1.0)
    else:
        positions = np.where(predictions == 1, 1.0, 0.0)

    if date_arr is None:
        selected = np.arange(0, len(returns), days)
        period_strategy = positions[selected] * returns[selected]
        period_benchmark = returns[selected]
        period_exposure = np.abs(positions[selected])
        period_positions = positions[selected]
    else:
        buckets: dict[str, list[tuple[float, float]]] = {}
        for date, ret, pos in zip(date_arr, returns, positions):
            buckets.setdefault(str(date), []).append((float(ret), float(pos)))

        selected_dates = sorted(buckets)[::days]
        period_strategy = []
        period_benchmark = []
        period_exposure = []
        period_positions = []
        for date in selected_dates:
            values = buckets[date]
            bucket_returns = np.array([item[0] for item in values], dtype=float)
            bucket_positions = np.array([item[1] for item in values], dtype=float)
            period_strategy.append(float(np.mean(bucket_positions * bucket_returns)))
            period_benchmark.append(float(np.mean(bucket_returns)))
            period_exposure.append(float(np.mean(np.abs(bucket_positions))))
            period_positions.append(float(np.mean(bucket_positions)))

        period_strategy = np.array(period_strategy, dtype=float)
        period_benchmark = np.array(period_benchmark, dtype=float)
        period_exposure = np.array(period_exposure, dtype=float)
        period_positions = np.array(period_positions, dtype=float)

    if len(period_strategy) == 0:
        return empty

    total_return = float(np.prod(1 + np.clip(period_strategy, -0.99, None)) - 1)
    benchmark_return = float(np.prod(1 + np.clip(period_benchmark, -0.99, None)) - 1)
    vol = float(np.std(period_strategy, ddof=1)) if len(period_strategy) > 1 else 0.0
    periods_per_year = 252 / days
    sharpe = float(np.mean(period_strategy) / vol * np.sqrt(periods_per_year)) if vol > 0 else 0.0
    trades = int(np.count_nonzero(np.diff(period_positions)) + (period_positions[0] != 0))

    return {
        "mode": mode,
        "rebalance_period_days": days,
        "sampled_periods": int(len(period_strategy)),
        "total_return": round(total_return, 4),
        "benchmark_return": round(benchmark_return, 4),
        "excess_return": round(total_return - benchmark_return, 4),
        "average_return": round(float(np.mean(period_strategy)), 4),
        "average_daily_return": round(float(np.mean(period_strategy) / days), 4),
        "benchmark_average_return": round(float(np.mean(period_benchmark) / days), 4),
        "volatility": round(vol, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(_max_drawdown(period_strategy), 4),
        "exposure": round(float(np.mean(period_exposure)), 4),
        "trades": trades,
    }


def _run_cv(
    X,
    y,
    dates,
    n_folds,
    min_train,
    labels=None,
    returns=None,
    horizon="t1",
    n_estimators: int = 260,
):
    """Core expanding-window CV logic. Returns folds + aggregate."""
    n = len(X)
    test_size = (n - min_train) // n_folds
    if test_size < 10:
        n_folds = max(1, (n - min_train) // 10)
        test_size = (n - min_train) // n_folds

    folds = []
    all_preds = []
    all_true = []
    all_dates = []
    all_labels = []
    all_returns = []

    for fold in range(n_folds):
        train_end = min_train + fold * test_size
        test_end = train_end + test_size if fold < n_folds - 1 else n

        X_tr, y_tr = X[:train_end], y[:train_end]
        X_te, y_te = X[train_end:test_end], y[train_end:test_end]
        fold_returns = returns[train_end:test_end] if returns is not None else None

        if len(np.unique(y_tr)) < 2:
            continue

        model, engine = _make_classifier(n_estimators=n_estimators)
        _fit_classifier(model, X_tr, y_tr)

        y_pred = model.predict(X_te)

        acc = accuracy_score(y_te, y_pred)
        baseline = max(y_te.mean(), 1 - y_te.mean())
        fold_result = {
            "fold": fold + 1,
            "train_size": int(train_end),
            "test_size": int(test_end - train_end),
            "test_start": dates[train_end],
            "test_end": dates[test_end - 1],
            "model_type": engine["name"],
            "accuracy": round(acc, 4),
            "baseline": round(baseline, 4),
            "precision": round(precision_score(y_te, y_pred, zero_division=0), 4),
            "recall": round(recall_score(y_te, y_pred, zero_division=0), 4),
            "f1": round(f1_score(y_te, y_pred, zero_division=0), 4),
        }
        if fold_returns is not None:
            fold_result["long_cash"] = _strategy_metrics(
                y_pred, fold_returns, horizon, "long_cash", dates[train_end:test_end]
            )
            fold_result["non_overlap_long_cash"] = _non_overlap_strategy_metrics(
                y_pred, fold_returns, horizon, "long_cash", dates[train_end:test_end]
            )

        folds.append(fold_result)

        for i in range(len(y_te)):
            all_preds.append(int(y_pred[i]))
            all_true.append(int(y_te[i]))
            all_dates.append(dates[train_end + i])
            if returns is not None:
                all_returns.append(float(returns[train_end + i]))
            if labels is not None:
                all_labels.append(labels[train_end + i])

    all_true_arr = np.array(all_true)
    all_preds_arr = np.array(all_preds)

    return folds, all_preds, all_true, all_dates, all_labels, all_returns, all_true_arr, all_preds_arr


def _feature_group_tests(X, y, dates, n_folds, min_train) -> list[dict]:
    """Run lightweight group-only CV tests to show whether each driver family has standalone edge."""
    tests = []
    for key, spec in FEATURE_GROUPS.items():
        indices = [FEATURE_COLS.index(col) for col in spec["columns"] if col in FEATURE_COLS]
        if not indices:
            continue

        try:
            folds, _, all_true, _, _, _, all_true_arr, all_preds_arr = _run_cv(
                X[:, indices],
                y,
                dates,
                n_folds,
                min_train,
                n_estimators=120,
            )
        except Exception as exc:
            tests.append({
                "key": key,
                "label": spec["label"],
                "feature_count": len(indices),
                "status": "error",
                "error": str(exc),
            })
            continue

        if not all_true:
            tests.append({
                "key": key,
                "label": spec["label"],
                "feature_count": len(indices),
                "status": "insufficient",
                "accuracy": None,
                "baseline": None,
                "cv_lift": None,
                "n_folds": len(folds),
                "total_predictions": 0,
            })
            continue

        acc = float(accuracy_score(all_true_arr, all_preds_arr))
        baseline = float(max(all_true_arr.mean(), 1 - all_true_arr.mean()))
        lift = float(acc - baseline)
        if lift >= 0.02:
            status = "edge"
        elif lift > 0:
            status = "watch"
        else:
            status = "weak"

        tests.append({
            "key": key,
            "label": spec["label"],
            "feature_count": len(indices),
            "status": status,
            "accuracy": round(float(acc), 4),
            "baseline": round(float(baseline), 4),
            "cv_lift": round(float(lift), 4),
            "n_folds": len(folds),
            "total_predictions": len(all_true),
        })

    return sorted(tests, key=lambda item: item.get("cv_lift") if item.get("cv_lift") is not None else -999, reverse=True)


def run_backtest(symbol: str, horizon: str = "t1", n_folds: int = 5, min_train: int = 200) -> dict:
    """Expanding-window CV for a single ticker. Returns per-fold and aggregate metrics."""
    target_col = f"target_{horizon}"

    df = build_features(symbol)
    if df.empty:
        return {"error": f"No data for {symbol}"}

    df = df.dropna(subset=[target_col]).reset_index(drop=True)
    n = len(df)

    if n < min_train + 20:
        return {"error": f"Too few rows ({n}) for backtest"}

    X = df[FEATURE_COLS].values
    y = df[target_col].values
    dates = df["trade_date"].dt.strftime("%Y-%m-%d").tolist()
    returns = _forward_returns(df, horizon)

    folds, all_preds, all_true, all_dates, _, all_returns, all_true_arr, all_preds_arr = _run_cv(
        X, y, dates, n_folds, min_train, returns=returns, horizon=horizon
    )
    if not all_true:
        return {"error": "No valid backtest folds"}

    overall_acc = accuracy_score(all_true_arr, all_preds_arr)
    overall_baseline = max(all_true_arr.mean(), 1 - all_true_arr.mean())

    result = {
        "symbol": symbol,
        "horizon": horizon,
        "model_type": folds[0]["model_type"] if folds else None,
        "n_folds": len(folds),
        "total_predictions": len(all_true),
        "overall_accuracy": round(overall_acc, 4),
        "overall_baseline": round(overall_baseline, 4),
        "overall_precision": round(precision_score(all_true_arr, all_preds_arr, zero_division=0), 4),
        "overall_recall": round(recall_score(all_true_arr, all_preds_arr, zero_division=0), 4),
        "overall_f1": round(f1_score(all_true_arr, all_preds_arr, zero_division=0), 4),
        "long_cash": _strategy_metrics(all_preds, all_returns, horizon, "long_cash", all_dates),
        "long_short": _strategy_metrics(all_preds, all_returns, horizon, "long_short", all_dates),
        "non_overlap_long_cash": _non_overlap_strategy_metrics(all_preds, all_returns, horizon, "long_cash", all_dates),
        "non_overlap_long_short": _non_overlap_strategy_metrics(all_preds, all_returns, horizon, "long_short", all_dates),
        "feature_group_tests": _feature_group_tests(X, y, dates, n_folds, min_train),
        "folds": folds,
        "daily_predictions": [
            {"date": d, "predicted": p, "actual": a, "forward_return": round(r, 4) if np.isfinite(r) else None}
            for d, p, a, r in zip(all_dates, all_preds, all_true, all_returns)
        ],
    }

    MODELS_DIR.mkdir(exist_ok=True)
    out_path = MODELS_DIR / f"{symbol}_{horizon}_backtest.json"
    out_path.write_text(json.dumps(result, indent=2))

    return result


def run_backtest_unified(horizon: str = "t1", n_folds: int = 5, min_train: int = 800,
                         symbols: list[str] | None = None) -> dict:
    """Expanding-window CV on combined multi-ticker data."""
    target_col = f"target_{horizon}"

    df = build_features_multi(symbols)
    if df.empty:
        return {"error": "No combined data"}

    # Sort by date (mixing tickers chronologically)
    df = df.sort_values("trade_date").reset_index(drop=True)
    df = df.dropna(subset=[target_col]).reset_index(drop=True)
    n = len(df)

    if n < min_train + 50:
        return {"error": f"Too few rows ({n}) for unified backtest"}

    X = df[FEATURE_COLS].values
    y = df[target_col].values
    dates = df["trade_date"].dt.strftime("%Y-%m-%d").tolist()
    syms = df["symbol"].tolist()
    returns = _forward_returns(df, horizon)

    folds, all_preds, all_true, all_dates, all_labels, all_returns, all_true_arr, all_preds_arr = _run_cv(
        X, y, dates, n_folds, min_train, labels=syms, returns=returns, horizon=horizon
    )
    if not all_true:
        return {"error": "No valid unified backtest folds"}

    overall_acc = accuracy_score(all_true_arr, all_preds_arr)
    overall_baseline = max(all_true_arr.mean(), 1 - all_true_arr.mean())

    # Per-ticker breakdown
    per_ticker = {}
    for i in range(len(all_true)):
        sym = all_labels[i]
        if sym not in per_ticker:
            per_ticker[sym] = {"true": [], "pred": []}
        per_ticker[sym]["true"].append(all_true[i])
        per_ticker[sym]["pred"].append(all_preds[i])

    ticker_metrics = {}
    for sym, data in sorted(per_ticker.items()):
        t = np.array(data["true"])
        p = np.array(data["pred"])
        ticker_metrics[sym] = {
            "n": len(t),
            "accuracy": round(accuracy_score(t, p), 4),
            "baseline": round(max(t.mean(), 1 - t.mean()), 4),
            "precision": round(precision_score(t, p, zero_division=0), 4),
            "recall": round(recall_score(t, p, zero_division=0), 4),
            "f1": round(f1_score(t, p, zero_division=0), 4),
        }
        ticker_returns = [all_returns[i] for i in range(len(all_true)) if all_labels[i] == sym]
        ticker_dates = [all_dates[i] for i in range(len(all_true)) if all_labels[i] == sym]
        ticker_metrics[sym]["long_cash"] = _strategy_metrics(
            data["pred"], ticker_returns, horizon, "long_cash", ticker_dates
        )
        ticker_metrics[sym]["non_overlap_long_cash"] = _non_overlap_strategy_metrics(
            data["pred"], ticker_returns, horizon, "long_cash", ticker_dates
        )

    result = {
        "symbol": "UNIFIED",
        "horizon": horizon,
        "model_type": folds[0]["model_type"] if folds else None,
        "tickers": sorted(set(syms)),
        "n_folds": len(folds),
        "total_predictions": len(all_true),
        "overall_accuracy": round(overall_acc, 4),
        "overall_baseline": round(overall_baseline, 4),
        "overall_precision": round(precision_score(all_true_arr, all_preds_arr, zero_division=0), 4),
        "overall_recall": round(recall_score(all_true_arr, all_preds_arr, zero_division=0), 4),
        "overall_f1": round(f1_score(all_true_arr, all_preds_arr, zero_division=0), 4),
        "long_cash": _strategy_metrics(all_preds, all_returns, horizon, "long_cash", all_dates),
        "long_short": _strategy_metrics(all_preds, all_returns, horizon, "long_short", all_dates),
        "non_overlap_long_cash": _non_overlap_strategy_metrics(all_preds, all_returns, horizon, "long_cash", all_dates),
        "non_overlap_long_short": _non_overlap_strategy_metrics(all_preds, all_returns, horizon, "long_short", all_dates),
        "per_ticker": ticker_metrics,
        "feature_group_tests": _feature_group_tests(X, y, dates, n_folds, min_train),
        "folds": folds,
    }

    MODELS_DIR.mkdir(exist_ok=True)
    out_path = MODELS_DIR / f"UNIFIED_{horizon}_backtest.json"
    out_path.write_text(json.dumps(result, indent=2))

    return result
