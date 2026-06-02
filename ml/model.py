"""Model training and prediction for SkyEye quant signals."""

import json
from pathlib import Path
from datetime import datetime
import threading

import numpy as np
import joblib

from ml.features import build_features, build_features_multi, FEATURE_COLS, feature_group_importance

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)
MODEL_IMPORT_LOCK = threading.RLock()


def get_model_engine() -> dict:
    """Return the best available tree classifier engine."""
    with MODEL_IMPORT_LOCK:
        try:
            import xgboost  # noqa: F401
            return {"name": "XGBoost", "package": "xgboost", "available": True, "error": None}
        except Exception as xgb_error:
            try:
                from sklearn.ensemble import RandomForestClassifier  # noqa: F401
                return {
                    "name": "RandomForest",
                    "package": "sklearn",
                    "available": True,
                    "error": f"XGBoost unavailable, using sklearn fallback: {xgb_error}",
                }
            except Exception as sklearn_error:
                return {
                    "name": None,
                    "package": None,
                    "available": False,
                    "error": f"No quant model engine available: {sklearn_error}",
                }


def _load_model(path: Path):
    with MODEL_IMPORT_LOCK:
        return joblib.load(path)


def _save_model(model, path: Path) -> None:
    with MODEL_IMPORT_LOCK:
        joblib.dump(model, path)


def _make_classifier(n_estimators: int = 250):
    engine = get_model_engine()
    if not engine["available"]:
        raise RuntimeError(engine["error"])
    if engine["package"] == "xgboost":
        from xgboost import XGBClassifier

        model = XGBClassifier(
            max_depth=4,
            n_estimators=n_estimators,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=42,
        )
    else:
        from sklearn.ensemble import RandomForestClassifier

        model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=6,
            min_samples_leaf=4,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        )
    return model, engine


def _fit_classifier(model, X_train, y_train, X_test=None, y_test=None):
    if model.__class__.__module__.startswith("xgboost"):
        eval_set = [(X_test, y_test)] if X_test is not None and y_test is not None and len(y_test) else None
        model.fit(X_train, y_train, eval_set=eval_set, verbose=False)
    else:
        model.fit(X_train, y_train)


def _feature_importances(model, n_features: int) -> np.ndarray:
    importances = getattr(model, "feature_importances_", None)
    if importances is None:
        return np.zeros(n_features)
    return np.asarray(importances, dtype=float)


def _predicted_class_and_confidence(model, X: np.ndarray) -> tuple[int, float]:
    proba = model.predict_proba(X)[0]
    idx = int(np.argmax(proba))
    classes = getattr(model, "classes_", np.array([0, 1]))
    return int(classes[idx]), float(proba[idx])


def train(symbol: str, horizon: str = "t1") -> dict:
    """Train a tree classifier for a single symbol/horizon. Returns metrics dict."""
    target_col = f"target_{horizon}"

    df = build_features(symbol)
    if df.empty or len(df) < 60:
        return {"error": f"Not enough data for {symbol} ({len(df)} rows)"}

    # Drop rows where target is NaN (last few days)
    df = df.dropna(subset=[target_col]).reset_index(drop=True)

    X = df[FEATURE_COLS].values
    y = df[target_col].values
    dates = df["trade_date"].dt.strftime("%Y-%m-%d").tolist()

    # Time-series split: last 20% for test
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    if len(np.unique(y_train)) < 2:
        return {"error": f"Training split for {symbol}/{horizon} has only one class"}

    model, engine = _make_classifier(n_estimators=220)
    _fit_classifier(model, X_train, y_train, X_test, y_test)

    # Metrics
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    baseline = max(y_test.mean(), 1 - y_test.mean())

    # Feature importance
    importances = _feature_importances(model, len(FEATURE_COLS))
    top_features = sorted(
        zip(FEATURE_COLS, importances.tolist()),
        key=lambda x: x[1],
        reverse=True,
    )[:10]
    feature_groups = feature_group_importance(importances, FEATURE_COLS)

    meta = {
        "symbol": symbol,
        "horizon": horizon,
        "model_type": engine["name"],
        "model_package": engine["package"],
        "accuracy": round(accuracy, 4),
        "baseline": round(baseline, 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
        "train_size": split_idx,
        "test_size": len(y_test),
        "train_start": dates[0],
        "train_end": dates[split_idx - 1],
        "test_start": dates[split_idx],
        "test_end": dates[-1],
        "top_features": [{"name": n, "importance": round(v, 4)} for n, v in top_features],
        "feature_groups": feature_groups,
        "trained_at": datetime.now().isoformat(),
    }

    # Save
    model_path = MODELS_DIR / f"{symbol}_{horizon}.joblib"
    meta_path = MODELS_DIR / f"{symbol}_{horizon}_meta.json"
    _save_model(model, model_path)
    meta_path.write_text(json.dumps(meta, indent=2))

    return meta


def train_unified(horizon: str = "t1", symbols: list[str] | None = None) -> dict:
    """Train a single model on ALL tickers combined. Returns metrics dict."""
    target_col = f"target_{horizon}"

    df = build_features_multi(symbols)
    if df.empty or len(df) < 100:
        return {"error": f"Not enough combined data ({len(df)} rows)"}

    df = df.dropna(subset=[target_col]).reset_index(drop=True)

    X = df[FEATURE_COLS].values
    y = df[target_col].values
    dates = df["trade_date"].dt.strftime("%Y-%m-%d").tolist()
    syms = df["symbol"].tolist()

    # Time-series split: sort by date, last 20% for test
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    if len(np.unique(y_train)) < 2:
        return {"error": f"Unified training split for {horizon} has only one class"}

    model, engine = _make_classifier(n_estimators=320)
    _fit_classifier(model, X_train, y_train, X_test, y_test)

    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    baseline = max(y_test.mean(), 1 - y_test.mean())

    importances = _feature_importances(model, len(FEATURE_COLS))
    top_features = sorted(
        zip(FEATURE_COLS, importances.tolist()),
        key=lambda x: x[1],
        reverse=True,
    )[:10]
    feature_groups = feature_group_importance(importances, FEATURE_COLS)

    meta = {
        "symbol": "UNIFIED",
        "horizon": horizon,
        "model_type": engine["name"],
        "model_package": engine["package"],
        "accuracy": round(accuracy, 4),
        "baseline": round(baseline, 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
        "train_size": split_idx,
        "test_size": len(y_test),
        "train_start": dates[0],
        "train_end": dates[split_idx - 1],
        "test_start": dates[split_idx],
        "test_end": dates[-1],
        "tickers": sorted(set(syms)),
        "top_features": [{"name": n, "importance": round(v, 4)} for n, v in top_features],
        "feature_groups": feature_groups,
        "trained_at": datetime.now().isoformat(),
    }

    model_path = MODELS_DIR / f"UNIFIED_{horizon}.joblib"
    meta_path = MODELS_DIR / f"UNIFIED_{horizon}_meta.json"
    _save_model(model, model_path)
    meta_path.write_text(json.dumps(meta, indent=2))

    return meta


def predict(symbol: str, horizon: str = "t1") -> dict:
    """Load model and predict direction for the latest trading day."""
    model_path = MODELS_DIR / f"{symbol}_{horizon}.joblib"
    meta_path = MODELS_DIR / f"{symbol}_{horizon}_meta.json"
    model_symbol = symbol

    # Fall back to unified model if per-ticker model missing
    if not model_path.exists():
        model_path = MODELS_DIR / f"UNIFIED_{horizon}.joblib"
        meta_path = MODELS_DIR / f"UNIFIED_{horizon}_meta.json"
        model_symbol = "UNIFIED"
    if not model_path.exists():
        return {"error": f"No model for {symbol}/{horizon}. Run training first."}

    model = _load_model(model_path)
    meta = json.loads(meta_path.read_text())
    backtest_path = MODELS_DIR / f"{model_symbol}_{horizon}_backtest.json"
    backtest = json.loads(backtest_path.read_text()) if backtest_path.exists() else None
    from ml.quality import build_signal_gate, score_model_quality

    quality = score_model_quality(meta, backtest)

    df = build_features(symbol)
    if df.empty:
        return {"error": f"No feature data for {symbol}"}

    # Use the last row (most recent trading day with complete features)
    last_row = df.iloc[-1]
    X = last_row[FEATURE_COLS].values.reshape(1, -1).astype(np.float64)

    pred_class, confidence = _predicted_class_and_confidence(model, X)
    signal_gate = build_signal_gate(quality, confidence, backtest)

    # Top feature contributions for this prediction
    importances = _feature_importances(model, len(FEATURE_COLS))
    feature_values = {col: float(last_row[col]) for col in FEATURE_COLS}
    top = sorted(
        zip(FEATURE_COLS, importances.tolist()),
        key=lambda x: x[1],
        reverse=True,
    )[:5]

    return {
        "symbol": symbol,
        "horizon": horizon,
        "direction": "up" if pred_class == 1 else "down",
        "confidence": round(confidence, 4),
        "model_type": meta.get("model_type", "TreeModel"),
        "date": str(last_row["trade_date"].date()),
        "top_features": [
            {"name": n, "value": round(feature_values[n], 4), "importance": round(imp, 4)}
            for n, imp in top
        ],
        "feature_groups": feature_group_importance(importances, FEATURE_COLS),
        "model_accuracy": meta["accuracy"],
        "baseline_accuracy": meta["baseline"],
        "model_quality": quality["status"],
        "model_quality_label": quality["label"],
        "model_quality_message": quality["message"],
        "model_holdout_lift": quality["holdout_lift"],
        "model_cv_lift": quality["cv_lift"],
        "strict_strategy_excess_return": quality.get("strict_strategy_excess_return"),
        "strict_strategy_return": quality.get("strict_strategy_return"),
        "strict_strategy_sharpe": quality.get("strict_strategy_sharpe"),
        "trade_ready": quality["trade_ready"],
        "signal_gate": signal_gate,
    }
