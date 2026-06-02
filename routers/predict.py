import json, os, time
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

router = APIRouter()
MODELS_DIR = Path(__file__).resolve().parent.parent / "ml" / "models"
QUANT_JOBS: dict[str, dict] = {}
LAYER1_JOBS: dict[str, dict] = {}
CORE_UNIVERSE_SYMBOLS = ["NVDA", "MSFT", "AMZN", "GOOGL", "AAPL", "META", "TSLA", "AMD", "AVGO", "PLTR"]


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        return {"error": f"Cannot read {path.name}: {exc}"}


def _dependency_status(name: str) -> dict:
    try:
        __import__(name)
        return {"available": True, "error": None}
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def _engine_status() -> dict:
    try:
        from ml.model import get_model_engine

        return get_model_engine()
    except Exception as exc:
        return {"name": None, "package": None, "available": False, "error": str(exc)}


def _sentiment_engine_status() -> dict:
    try:
        from ai_analyzer import API_KEY, MODEL

        if API_KEY:
            return {"name": MODEL, "package": "openai-compatible", "available": True, "error": None}
        return {
            "name": "SkyEye Heuristic",
            "package": "local",
            "available": True,
            "error": "No AI API key configured; using local Polygon/text fallback.",
        }
    except Exception as exc:
        return {"name": "SkyEye Heuristic", "package": "local", "available": True, "error": str(exc)}


def _is_universe_symbol(symbol: str) -> bool:
    return symbol.upper() in {"UNIFIED", "UNIVERSE", "_UNIVERSE"}


def _universe_symbols() -> list[str]:
    try:
        from database import get_conn

        conn = get_conn()
        rows = conn.execute(
            """SELECT na.symbol,
                      COUNT(DISTINCT na.news_id) AS aligned_news,
                      COUNT(DISTINCT l1.news_id) AS analyzed_news,
                      COUNT(DISTINCT o.date) AS ohlc_rows
               FROM news_aligned na
               JOIN ohlc o ON o.symbol = na.symbol
               LEFT JOIN layer1_results l1 ON l1.news_id = na.news_id AND l1.symbol = na.symbol
               GROUP BY na.symbol
               HAVING ohlc_rows >= 200 AND analyzed_news >= 50
               ORDER BY analyzed_news DESC"""
        ).fetchall()
        conn.close()
        symbols = [row["symbol"] for row in rows]
        return symbols or CORE_UNIVERSE_SYMBOLS
    except Exception:
        return CORE_UNIVERSE_SYMBOLS


def _coverage_for_symbol(symbol: str) -> dict:
    from database import get_conn

    sym = symbol.upper()
    conn = get_conn()
    if _is_universe_symbol(sym):
        symbols = _universe_symbols()
        placeholders = ",".join("?" for _ in symbols)
        params = tuple(symbols)
        ohlc_rows = conn.execute(
            f"SELECT COUNT(*) FROM ohlc WHERE symbol IN ({placeholders})",
            params,
        ).fetchone()[0]
        aligned_news = conn.execute(
            f"SELECT COUNT(DISTINCT symbol || ':' || news_id) FROM news_aligned WHERE symbol IN ({placeholders})",
            params,
        ).fetchone()[0]
        analyzed_news = conn.execute(
            f"SELECT COUNT(*) FROM layer1_results WHERE symbol IN ({placeholders})",
            params,
        ).fetchone()[0]
        layer0_passed = conn.execute(
            f"SELECT COUNT(*) FROM layer0_results WHERE symbol IN ({placeholders}) AND passed = 1",
            params,
        ).fetchone()[0]
        layer0_filtered = conn.execute(
            f"SELECT COUNT(*) FROM layer0_results WHERE symbol IN ({placeholders}) AND passed = 0",
            params,
        ).fetchone()[0]
        pending_analysis = conn.execute(
            f"""SELECT COUNT(DISTINCT na.symbol || ':' || na.news_id)
                FROM news_aligned na
                LEFT JOIN layer0_results l0 ON l0.news_id = na.news_id AND l0.symbol = na.symbol
                WHERE na.symbol IN ({placeholders})
                  AND COALESCE(l0.passed, 1) = 1
                  AND NOT EXISTS (
                      SELECT 1 FROM layer1_results l1
                      WHERE l1.news_id = na.news_id AND l1.symbol = na.symbol
                  )""",
            params,
        ).fetchone()[0]
        sentiment_rows = conn.execute(
            f"SELECT sentiment, COUNT(*) AS cnt FROM layer1_results WHERE symbol IN ({placeholders}) GROUP BY sentiment",
            params,
        ).fetchall()
        conn.close()
        return {
            "ohlc_rows": ohlc_rows,
            "aligned_news": aligned_news,
            "analyzed_news": analyzed_news,
            "pending_analysis": pending_analysis,
            "layer0_passed": layer0_passed,
            "layer0_filtered": layer0_filtered,
            "sentiment": {row["sentiment"] or "unknown": row["cnt"] for row in sentiment_rows},
            "universe_symbols": symbols,
        }

    ohlc_rows = conn.execute("SELECT COUNT(*) FROM ohlc WHERE symbol = ?", (sym,)).fetchone()[0]
    aligned_news = conn.execute(
        "SELECT COUNT(DISTINCT news_id) FROM news_aligned WHERE symbol = ?", (sym,)
    ).fetchone()[0]
    analyzed_news = conn.execute(
        "SELECT COUNT(*) FROM layer1_results WHERE symbol = ?", (sym,)
    ).fetchone()[0]
    layer0_passed = conn.execute(
        "SELECT COUNT(*) FROM layer0_results WHERE symbol = ? AND passed = 1", (sym,)
    ).fetchone()[0]
    layer0_filtered = conn.execute(
        "SELECT COUNT(*) FROM layer0_results WHERE symbol = ? AND passed = 0", (sym,)
    ).fetchone()[0]
    pending_analysis = conn.execute(
        """SELECT COUNT(DISTINCT na.news_id)
           FROM news_aligned na
           LEFT JOIN layer0_results l0 ON l0.news_id = na.news_id AND l0.symbol = na.symbol
           WHERE na.symbol = ?
             AND COALESCE(l0.passed, 1) = 1
             AND NOT EXISTS (
                 SELECT 1 FROM layer1_results l1
                 WHERE l1.news_id = na.news_id AND l1.symbol = na.symbol
             )""",
        (sym,),
    ).fetchone()[0]
    sentiment_rows = conn.execute(
        "SELECT sentiment, COUNT(*) AS cnt FROM layer1_results WHERE symbol = ? GROUP BY sentiment",
        (sym,),
    ).fetchall()
    conn.close()
    return {
        "ohlc_rows": ohlc_rows,
        "aligned_news": aligned_news,
        "analyzed_news": analyzed_news,
        "pending_analysis": pending_analysis,
        "layer0_passed": layer0_passed,
        "layer0_filtered": layer0_filtered,
        "sentiment": {row["sentiment"] or "unknown": row["cnt"] for row in sentiment_rows},
    }


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _age_days(value: str | None) -> int | None:
    dt = _parse_date(value)
    if dt is None:
        return None
    return max(0, (datetime.now(timezone.utc).date() - dt.date()).days)


def _age_hours(value: str | None) -> float | None:
    dt = _parse_iso_datetime(value)
    if dt is None:
        return None
    return round(max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600), 1)


def _quality_dates(symbol: str) -> dict:
    from database import get_conn

    sym = symbol.upper()
    conn = get_conn()
    if _is_universe_symbol(sym):
        symbols = _universe_symbols()
        placeholders = ",".join("?" for _ in symbols)
        params = tuple(symbols)
        ohlc = conn.execute(
            f"""SELECT MIN(date) AS first_ohlc_date,
                       MAX(date) AS latest_ohlc_date,
                       COUNT(DISTINCT symbol) AS symbol_count
                FROM ohlc
                WHERE symbol IN ({placeholders})""",
            params,
        ).fetchone()
        news = conn.execute(
            f"""SELECT MAX(na.published_utc) AS latest_news_published_utc
                FROM news_aligned na
                WHERE na.symbol IN ({placeholders})""",
            params,
        ).fetchone()
        labels = conn.execute(
            f"""SELECT MAX(nr.published_utc) AS latest_labeled_news_published_utc
                FROM layer1_results l1
                JOIN news_raw nr ON nr.id = l1.news_id
                WHERE l1.symbol IN ({placeholders})""",
            params,
        ).fetchone()
        conn.close()
        return {
            "first_ohlc_date": ohlc["first_ohlc_date"],
            "latest_ohlc_date": ohlc["latest_ohlc_date"],
            "symbol_count": ohlc["symbol_count"],
            "latest_news_published_utc": news["latest_news_published_utc"],
            "latest_labeled_news_published_utc": labels["latest_labeled_news_published_utc"],
        }

    ohlc = conn.execute(
        """SELECT MIN(date) AS first_ohlc_date,
                  MAX(date) AS latest_ohlc_date,
                  COUNT(DISTINCT symbol) AS symbol_count
           FROM ohlc
           WHERE symbol = ?""",
        (sym,),
    ).fetchone()
    news = conn.execute(
        """SELECT MAX(published_utc) AS latest_news_published_utc
           FROM news_aligned
           WHERE symbol = ?""",
        (sym,),
    ).fetchone()
    labels = conn.execute(
        """SELECT MAX(nr.published_utc) AS latest_labeled_news_published_utc
           FROM layer1_results l1
           JOIN news_raw nr ON nr.id = l1.news_id
           WHERE l1.symbol = ?""",
        (sym,),
    ).fetchone()
    conn.close()
    return {
        "first_ohlc_date": ohlc["first_ohlc_date"],
        "latest_ohlc_date": ohlc["latest_ohlc_date"],
        "symbol_count": ohlc["symbol_count"],
        "latest_news_published_utc": news["latest_news_published_utc"],
        "latest_labeled_news_published_utc": labels["latest_labeled_news_published_utc"],
    }


def _data_quality_for_symbol(symbol: str, coverage: dict) -> dict:
    dates = _quality_dates(symbol)
    ohlc_rows = int(coverage.get("ohlc_rows") or 0)
    aligned_news = int(coverage.get("aligned_news") or 0)
    analyzed_news = int(coverage.get("analyzed_news") or 0)
    pending_analysis = int(coverage.get("pending_analysis") or 0)
    labelable_articles = analyzed_news + pending_analysis
    label_coverage = round(analyzed_news / labelable_articles, 4) if labelable_articles else None

    ohlc_age = _age_days(dates.get("latest_ohlc_date"))
    news_age = _age_hours(dates.get("latest_news_published_utc"))
    labeled_news_age = _age_hours(dates.get("latest_labeled_news_published_utc"))
    symbol_count = int(dates.get("symbol_count") or 0)

    issues: list[str] = []
    hard_issue = False
    stale_issue = False

    if ohlc_rows < 200:
        hard_issue = True
        issues.append("Need at least 200 OHLC rows before model backtests are meaningful.")
    elif ohlc_rows < 400:
        issues.append("OHLC history is usable but still thin for robust validation.")

    if analyzed_news < 50:
        hard_issue = True
        issues.append("Need at least 50 analyzed news labels for sentiment features.")
    elif analyzed_news < 100:
        issues.append("Sentiment label sample is usable but still thin.")

    if label_coverage is None:
        hard_issue = True
        issues.append("No labelable news coverage found.")
    elif label_coverage < 0.9:
        issues.append("News labels are incomplete; run Layer 1 analysis before trusting sentiment features.")

    if pending_analysis > 0:
        issues.append(f"{pending_analysis} aligned news items still need Layer 1 labels.")

    if ohlc_age is None:
        stale_issue = True
        issues.append("No latest OHLC date is available.")
    elif ohlc_age > 7:
        stale_issue = True
        issues.append("OHLC data is stale for live decision support.")
    elif ohlc_age > 4:
        issues.append("OHLC data is a few calendar days old; check market calendar before acting.")

    if news_age is not None and news_age > 168:
        issues.append("Latest aligned news is more than one week old.")

    if labeled_news_age is not None and news_age is not None and labeled_news_age + 24 < news_age:
        issues.append("Recent aligned news appears newer than the latest labeled article.")

    ready_for_modeling = (
        not hard_issue
        and not stale_issue
        and (label_coverage is not None and label_coverage >= 0.9)
        and pending_analysis == 0
    )
    usable_for_research = ohlc_rows >= 100 and analyzed_news >= 10 and not stale_issue

    if hard_issue:
        status = "insufficient"
        label = "Insufficient"
        message = "Data coverage is not yet deep enough for reliable quant research."
    elif stale_issue:
        status = "stale"
        label = "Stale"
        message = "Refresh market data before using this as a live decision input."
    elif issues:
        status = "watch"
        label = "Watch"
        message = "Data is usable for research, with caveats to check first."
    else:
        status = "healthy"
        label = "Healthy"
        message = "Data freshness and label coverage are suitable for research backtests."

    return {
        "status": status,
        "label": label,
        "message": message,
        "ready_for_modeling": ready_for_modeling,
        "usable_for_research": usable_for_research,
        "issues": issues,
        "first_ohlc_date": dates.get("first_ohlc_date"),
        "latest_ohlc_date": dates.get("latest_ohlc_date"),
        "ohlc_age_days": ohlc_age,
        "latest_news_published_utc": dates.get("latest_news_published_utc"),
        "news_age_hours": news_age,
        "latest_labeled_news_published_utc": dates.get("latest_labeled_news_published_utc"),
        "labeled_news_age_hours": labeled_news_age,
        "label_coverage": label_coverage,
        "labelable_articles": labelable_articles,
        "symbol_count": symbol_count,
        "aligned_news_per_symbol": round(aligned_news / symbol_count, 1) if symbol_count else None,
        "analyzed_news_per_symbol": round(analyzed_news / symbol_count, 1) if symbol_count else None,
    }


def _as_metric(value):
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _ticker_diagnostics(backtest: dict | None) -> list[dict]:
    if not isinstance(backtest, dict):
        return []
    per_ticker = backtest.get("per_ticker")
    if not isinstance(per_ticker, dict):
        return []

    rows = []
    for symbol, metrics in per_ticker.items():
        if not isinstance(metrics, dict):
            continue
        long_cash = metrics.get("long_cash")
        if not isinstance(long_cash, dict):
            long_cash = {}
        non_overlap = metrics.get("non_overlap_long_cash")
        if not isinstance(non_overlap, dict):
            non_overlap = {}

        accuracy = _as_metric(metrics.get("accuracy"))
        baseline = _as_metric(metrics.get("baseline"))
        classification_lift = (
            round(accuracy - baseline, 4)
            if accuracy is not None and baseline is not None
            else None
        )
        strategy_excess = _as_metric(long_cash.get("excess_return"))
        strict_strategy_excess = _as_metric(non_overlap.get("excess_return"))
        verdict_excess = strict_strategy_excess if strict_strategy_excess is not None else strategy_excess
        if classification_lift is not None and classification_lift > 0 and verdict_excess is not None and verdict_excess > 0:
            verdict = "edge"
        elif (classification_lift is not None and classification_lift > 0) or (verdict_excess is not None and verdict_excess > 0):
            verdict = "watch"
        else:
            verdict = "weak"

        rows.append({
            "symbol": str(symbol).upper(),
            "n": int(metrics.get("n") or 0),
            "accuracy": accuracy,
            "baseline": baseline,
            "classification_lift": classification_lift,
            "precision": _as_metric(metrics.get("precision")),
            "recall": _as_metric(metrics.get("recall")),
            "f1": _as_metric(metrics.get("f1")),
            "strategy_return": _as_metric(long_cash.get("total_return")),
            "benchmark_return": _as_metric(long_cash.get("benchmark_return")),
            "strategy_excess_return": strategy_excess,
            "strategy_sharpe": _as_metric(long_cash.get("sharpe")),
            "strict_strategy_return": _as_metric(non_overlap.get("total_return")),
            "strict_strategy_excess_return": strict_strategy_excess,
            "strict_strategy_sharpe": _as_metric(non_overlap.get("sharpe")),
            "max_drawdown": _as_metric(long_cash.get("max_drawdown")),
            "exposure": _as_metric(long_cash.get("exposure")),
            "trades": int(long_cash.get("trades") or 0),
            "verdict": verdict,
        })

    return sorted(
        rows,
        key=lambda row: (
            row.get("strategy_excess_return") is not None,
            row.get("strategy_excess_return") or -999,
            row.get("classification_lift") or -999,
            row.get("symbol") or "",
        ),
        reverse=True,
    )


def _model_state(symbol: str, horizon: str) -> dict:
    from ml.quality import score_model_quality

    model_path = MODELS_DIR / f"{symbol}_{horizon}.joblib"
    meta_path = MODELS_DIR / f"{symbol}_{horizon}_meta.json"
    backtest_path = MODELS_DIR / f"{symbol}_{horizon}_backtest.json"
    meta = _read_json(meta_path)
    backtest = _read_json(backtest_path)
    quality = score_model_quality(meta, backtest)
    return {
        "horizon": horizon,
        "trained": model_path.exists() and meta is not None and "error" not in meta,
        "model_file": model_path.name if model_path.exists() else None,
        "model_type": meta.get("model_type") if isinstance(meta, dict) else None,
        "model_package": meta.get("model_package") if isinstance(meta, dict) else None,
        "trained_at": meta.get("trained_at") if isinstance(meta, dict) else None,
        "accuracy": meta.get("accuracy") if isinstance(meta, dict) else None,
        "baseline": meta.get("baseline") if isinstance(meta, dict) else None,
        "precision": meta.get("precision") if isinstance(meta, dict) else None,
        "recall": meta.get("recall") if isinstance(meta, dict) else None,
        "f1": meta.get("f1") if isinstance(meta, dict) else None,
        "top_features": meta.get("top_features", []) if isinstance(meta, dict) else [],
        "feature_groups": meta.get("feature_groups", []) if isinstance(meta, dict) else [],
        "quality": quality,
        "backtest": {
            "available": backtest is not None and "error" not in backtest,
            "overall_accuracy": backtest.get("overall_accuracy") if isinstance(backtest, dict) else None,
            "overall_baseline": backtest.get("overall_baseline") if isinstance(backtest, dict) else None,
            "overall_precision": backtest.get("overall_precision") if isinstance(backtest, dict) else None,
            "overall_recall": backtest.get("overall_recall") if isinstance(backtest, dict) else None,
            "overall_f1": backtest.get("overall_f1") if isinstance(backtest, dict) else None,
            "n_folds": backtest.get("n_folds") if isinstance(backtest, dict) else None,
            "total_predictions": backtest.get("total_predictions") if isinstance(backtest, dict) else None,
            "long_cash": backtest.get("long_cash") if isinstance(backtest, dict) else None,
            "long_short": backtest.get("long_short") if isinstance(backtest, dict) else None,
            "non_overlap_long_cash": backtest.get("non_overlap_long_cash") if isinstance(backtest, dict) else None,
            "non_overlap_long_short": backtest.get("non_overlap_long_short") if isinstance(backtest, dict) else None,
            "feature_group_tests": backtest.get("feature_group_tests", []) if isinstance(backtest, dict) else [],
            "per_ticker": _ticker_diagnostics(backtest),
        },
    }


def _run_quant_training(symbol: str, horizon: str, run_backtest: bool, job_key: str):
    QUANT_JOBS[job_key] = {
        **QUANT_JOBS.get(job_key, {}),
        "status": "running",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": None,
        "error": None,
    }
    try:
        if _is_universe_symbol(symbol):
            from ml.model import train_unified

            symbols = _universe_symbols()
            train_result = train_unified(horizon, symbols=symbols)
        else:
            from ml.model import train

            train_result = train(symbol, horizon)
        result = {"train": train_result}
        if "error" in train_result:
            raise RuntimeError(train_result["error"])

        if run_backtest:
            if _is_universe_symbol(symbol):
                from ml.backtest import run_backtest_unified

                result["backtest"] = run_backtest_unified(
                    horizon,
                    min_train=1600,
                    symbols=train_result.get("tickers") or _universe_symbols(),
                )
            else:
                from ml.backtest import run_backtest as run_cv_backtest

                result["backtest"] = run_cv_backtest(symbol, horizon)

        QUANT_JOBS[job_key] = {
            **QUANT_JOBS[job_key],
            "status": "complete",
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "result": result,
        }
    except Exception as exc:
        QUANT_JOBS[job_key] = {
            **QUANT_JOBS.get(job_key, {}),
            "status": "failed",
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "error": str(exc),
        }


def _run_layer1_analysis(symbol: str, limit: int, engine: str, job_key: str):
    LAYER1_JOBS[job_key] = {
        **LAYER1_JOBS.get(job_key, {}),
        "status": "running",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": None,
        "error": None,
    }
    try:
        from pipeline.layer1 import run_layer1

        result = run_layer1(symbol, max_articles=limit, engine=engine)
        LAYER1_JOBS[job_key] = {
            **LAYER1_JOBS[job_key],
            "status": "complete",
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "result": result,
        }
    except Exception as exc:
        LAYER1_JOBS[job_key] = {
            **LAYER1_JOBS.get(job_key, {}),
            "status": "failed",
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "error": str(exc),
        }


@router.get("/decision-board")
def get_decision_board(
    symbols: str | None = Query(None),
    limit: int = Query(10, ge=1, le=25),
    lookback_days: int = Query(30, ge=7, le=120),
):
    try:
        from ml.decision import build_decision_board

        selected = None
        if symbols:
            selected = [part.strip().upper() for part in symbols.split(",") if part.strip()]
        return build_decision_board(selected, limit=limit, lookback_days=lookback_days)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/portfolio-plan")
def get_portfolio_plan(
    symbols: str | None = Query(None),
    capital: float = Query(100000.0, ge=0.0, le=1000000000.0),
    limit: int = Query(10, ge=1, le=25),
    lookback_days: int = Query(30, ge=7, le=120),
):
    try:
        from ml.portfolio import build_portfolio_plan

        selected = None
        if symbols:
            selected = [part.strip().upper() for part in symbols.split(",") if part.strip()]
        return build_portfolio_plan(
            symbols=selected,
            capital=capital,
            limit=limit,
            lookback_days=lookback_days,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/strategy-monitor")
def get_strategy_monitor(symbols: str | None = Query(None)):
    try:
        from ml.strategy_monitor import build_strategy_monitor

        selected = None
        if symbols:
            selected = [part.strip().upper() for part in symbols.split(",") if part.strip()]
        return build_strategy_monitor(selected)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/catalyst-radar")
def get_catalyst_radar(
    symbols: str | None = Query(None),
    lookback_days: int = Query(10, ge=3, le=45),
    limit: int = Query(10, ge=1, le=25),
):
    try:
        from ml.catalyst import build_catalyst_radar

        selected = None
        if symbols:
            selected = [part.strip().upper() for part in symbols.split(",") if part.strip()]
        return build_catalyst_radar(symbols=selected, lookback_days=lookback_days, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/trade-setups")
def get_trade_setups(
    capital: float = Query(100000.0, ge=0.0, le=1000000000.0),
    lookback_days: int = Query(10, ge=3, le=45),
    limit: int = Query(8, ge=1, le=12),
):
    try:
        from ml.trade_setup import build_trade_setups

        return build_trade_setups(capital=capital, lookback_days=lookback_days, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{symbol}")
def get_prediction(symbol: str, horizon: str = Query("t1")):
    # Try local ML model first
    try:
        from ml.model import predict
        result = predict(symbol.upper(), horizon)
        if "error" not in result:
            return result
    except Exception:
        pass
    # Try ai_analyzer
    try:
        from database import get_conn
        from ai_analyzer import predict_direction
        conn = get_conn()
        ohlc = conn.execute("SELECT date, close, volume FROM ohlc WHERE symbol = ? ORDER BY date DESC LIMIT 20",
            (symbol.upper(),)).fetchall()
        news = conn.execute(
            "SELECT l1.sentiment, COUNT(*) as cnt FROM layer1_results l1 WHERE l1.symbol = ? GROUP BY l1.sentiment",
            (symbol.upper(),)).fetchall()
        conn.close()
        context = ""
        if ohlc:
            prices = [dict(r) for r in ohlc]
            latest = prices[0]["close"]
            oldest = prices[-1]["close"]
            change = (latest - oldest) / oldest * 100
            context += "Recent price: $%.2f, 20-day change: %+.1f%%\n" % (latest, change)
        if news:
            for n in news:
                context += "News sentiment %s: %d articles\n" % (n["sentiment"], n["cnt"])
        if context:
            result = predict_direction(symbol.upper(), context)
            reasoning = str(result.get("reasoning") or result.get("error") or "")
            if reasoning.startswith("Error:") or reasoning.startswith("API error"):
                raise RuntimeError(reasoning)
            result["symbol"] = symbol.upper()
            result["model_type"] = "mimo-2.5-pro"
            return result
    except Exception:
        pass
    return {"symbol": symbol.upper(), "direction": "up", "confidence": 0.5, "model_type": "fallback",
            "top_drivers": [], "reasoning": "Insufficient data"}

@router.get("/{symbol}/backtest")
def get_backtest(symbol: str, horizon: str = Query("t1")):
    path = MODELS_DIR / f"{symbol.upper()}_{horizon}_backtest.json"
    if not path.exists():
        return {"error": "No backtest available", "symbol": symbol.upper()}
    return json.loads(path.read_text())


@router.get("/{symbol}/quant")
def get_quant_status(symbol: str):
    sym = "UNIFIED" if _is_universe_symbol(symbol) else symbol.upper()
    job_items = [job for job in QUANT_JOBS.values() if job.get("symbol") == sym]
    analysis_job_items = [job for job in LAYER1_JOBS.values() if job.get("symbol") == sym]
    try:
        coverage = _coverage_for_symbol(sym)
    except Exception:
        coverage = {
            "ohlc_rows": 0,
            "aligned_news": 0,
            "analyzed_news": 0,
            "pending_analysis": 0,
            "layer0_passed": 0,
            "layer0_filtered": 0,
            "sentiment": {},
        }
    try:
        data_quality = _data_quality_for_symbol(sym, coverage)
    except Exception as exc:
        data_quality = {
            "status": "unknown",
            "label": "Unknown",
            "message": "Data quality could not be calculated.",
            "ready_for_modeling": False,
            "usable_for_research": False,
            "issues": [str(exc)],
        }

    return {
        "symbol": sym,
        "coverage": coverage,
        "data_quality": data_quality,
        "dependencies": {
            "model_engine": _engine_status(),
            "sentiment_engine": _sentiment_engine_status(),
            "sklearn": _dependency_status("sklearn"),
            "xgboost": _dependency_status("xgboost"),
            "torch": _dependency_status("torch"),
        },
        "models": [_model_state(sym, horizon) for horizon in ("t1", "t5")],
        "jobs": sorted(job_items, key=lambda item: item.get("started_at") or "", reverse=True)[:5],
        "analysis_jobs": sorted(
            analysis_job_items,
            key=lambda item: item.get("started_at") or item.get("requested_at") or "",
            reverse=True,
        )[:5],
    }


@router.get("/{symbol}/risk-brief")
def get_risk_brief(symbol: str):
    try:
        from ml.risk import build_risk_brief

        result = build_risk_brief(symbol.upper())
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{symbol}/train")
def train_quant_model(
    symbol: str,
    background_tasks: BackgroundTasks,
    horizon: str = Query("t1", pattern="^t[15]$"),
    backtest: bool = Query(True),
):
    sym = "UNIFIED" if _is_universe_symbol(symbol) else symbol.upper()
    job_key = f"{sym}:{horizon}"
    current = QUANT_JOBS.get(job_key)
    if current and current.get("status") in {"queued", "running"}:
        return {"symbol": sym, "horizon": horizon, "job": current}

    job = {
        "symbol": sym,
        "horizon": horizon,
        "status": "queued",
        "backtest": backtest,
        "requested_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "started_at": None,
        "finished_at": None,
        "error": None,
    }
    QUANT_JOBS[job_key] = job
    background_tasks.add_task(_run_quant_training, sym, horizon, backtest, job_key)
    return {"symbol": sym, "horizon": horizon, "job": job}


@router.post("/{symbol}/analyze-news")
def analyze_news_layer1(
    symbol: str,
    background_tasks: BackgroundTasks,
    limit: int = Query(100, ge=1, le=1000),
    engine: str = Query("auto", pattern="^(auto|mimo|heuristic)$"),
):
    sym = symbol.upper()
    job_key = f"{sym}:layer1"
    current = LAYER1_JOBS.get(job_key)
    if current and current.get("status") in {"queued", "running"}:
        return {"symbol": sym, "job": current}

    job = {
        "symbol": sym,
        "kind": "layer1",
        "status": "queued",
        "limit": limit,
        "engine": engine,
        "requested_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "started_at": None,
        "finished_at": None,
        "error": None,
    }
    LAYER1_JOBS[job_key] = job
    background_tasks.add_task(_run_layer1_analysis, sym, limit, engine, job_key)
    return {"symbol": sym, "job": job}

@router.get("/{symbol}/forecast")
def get_forecast(symbol: str, window: int = Query(7, ge=3, le=60)):
    try:
        from ml.inference import generate_forecast
        result = generate_forecast(symbol.upper(), window)
        if "error" not in result:
            return result
    except Exception:
        pass
    # Build a compatible response from DB data
    try:
        from database import get_conn
        conn = get_conn()
        ohlc = conn.execute("SELECT date, close FROM ohlc WHERE symbol = ? ORDER BY date DESC LIMIT 30",
            (symbol.upper(),)).fetchall()
        news_rows = conn.execute(
            "SELECT nr.title, nr.description, nr.published_utc, l1.sentiment, l1.key_discussion, "
            "l1.relevance, na.trade_date, na.ret_t0, na.ret_t1 "
            "FROM news_aligned na "
            "JOIN news_raw nr ON na.news_id = nr.id "
            "LEFT JOIN layer1_results l1 ON na.news_id = l1.news_id AND l1.symbol = na.symbol "
            "WHERE na.symbol = ? ORDER BY na.trade_date DESC LIMIT 50",
            (symbol.upper(),)).fetchall()
        conn.close()
        # Build news_summary
        positive = sum(1 for r in news_rows if r["sentiment"] == "positive")
        negative = sum(1 for r in news_rows if r["sentiment"] == "negative")
        neutral = len(news_rows) - positive - negative
        top_headlines = [{"date": r["trade_date"] or "", "title": r["title"] or "", 
                         "sentiment": r["sentiment"] or "neutral", "summary": r["key_discussion"] or ""} 
                        for r in news_rows[:10]]
        top_impact = [{"news_id": "", "date": r["trade_date"] or "", "title": r["title"] or "",
                      "sentiment": r["sentiment"] or "neutral", "relevance": r["relevance"],
                      "key_discussion": r["key_discussion"] or "", "ret_t0": r["ret_t0"], "ret_t1": r["ret_t1"]}
                     for r in news_rows[:5] if r["relevance"] in ("relevant", "high", "medium")]
        # Simple direction prediction based on recent trend
        direction = "up"
        confidence = 0.5
        if len(ohlc) >= 5:
            recent = [r["close"] for r in ohlc[:5]]
            if recent[0] > recent[-1]:
                direction = "up"
                confidence = 0.55
            else:
                direction = "down"
                confidence = 0.55
        # Build conclusion
        price_now = ohlc[0]["close"] if ohlc else 0
        price_ago = ohlc[min(window, len(ohlc)-1)]["close"] if ohlc else 0
        pct = ((price_now - price_ago) / price_ago * 100) if price_ago else 0
        conclusion = f"{symbol.upper()} moved {pct:+.1f}% over the past {window} days. "
        if positive > negative:
            conclusion += f"Sentiment is bullish with {positive} positive vs {negative} negative articles."
        elif negative > positive:
            conclusion += f"Sentiment is bearish with {negative} negative vs {positive} positive articles."
        else:
            conclusion += f"Sentiment is neutral with balanced coverage."
        return {
            "symbol": symbol.upper(),
            "window_days": window,
            "forecast_date": time.strftime("%Y-%m-%d"),
            "news_summary": {
                "total": len(news_rows),
                "positive": positive,
                "negative": negative,
                "neutral": neutral,
                "sentiment_ratio": (positive - negative) / max(len(news_rows), 1),
                "top_headlines": top_headlines,
                "top_impact": top_impact,
            },
            "prediction": {
                "t1": {"direction": direction, "confidence": confidence, "model_type": "trend-heuristic",
                       "top_drivers": [], "model_accuracy": None, "baseline_accuracy": None},
            },
            "similar_periods": [],
            "similar_stats": {"count": 0, "up_ratio_5d": 0, "up_ratio_10d": 0, "avg_ret_5d": None, "avg_ret_10d": None},
            "conclusion": conclusion,
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol.upper(), "window_days": window,
                "news_summary": {"total": 0, "positive": 0, "negative": 0, "neutral": 0, "sentiment_ratio": 0,
                                "top_headlines": [], "top_impact": []},
                "prediction": {}, "similar_periods": [], "similar_stats": {"count": 0},
                "conclusion": "No data available"}

@router.get("/{symbol}/similar-days")
def get_similar_days(symbol: str, date: str = Query(...), top_k: int = Query(10, ge=1, le=30)):
    try:
        from ml.similar import find_similar_days
        result = find_similar_days(symbol.upper(), date, top_k)
        if "error" not in result:
            return result
    except Exception:
        pass
    return {"symbol": symbol.upper(), "target_date": date, "similar_days": [], 
            "stats": {"up_ratio_t1": None, "up_ratio_t5": None, "avg_ret_t1": None, "avg_ret_t5": None, "count": 0},
            "target_features": {}}
