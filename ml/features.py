"""Feature engineering: one row per trading day per ticker."""

import json
import pandas as pd
import numpy as np
from database import get_conn


POS_WORDS = {
    "beat", "beats", "bullish", "buy", "upgrade", "surge", "rally", "record",
    "growth", "strong", "soar", "gain", "higher", "profit", "positive",
    "outperform", "breakthrough", "demand", "partnership",
}
NEG_WORDS = {
    "miss", "misses", "bearish", "sell", "downgrade", "plunge", "drop",
    "lawsuit", "probe", "weak", "loss", "lower", "negative", "risk",
    "recession", "warning", "cut", "decline", "concern",
}


MARKET_FEATURE_COLS = [
    "mkt_ret_1d", "mkt_ret_5d", "mkt_volatility_10d", "mkt_momentum_5_20",
    "mkt_breadth_1d", "rel_ret_1d", "rel_ret_5d", "rel_volatility_10d", "beta_60d",
    "mkt_sentiment", "mkt_positive_ratio", "mkt_negative_ratio",
    "mkt_sentiment_3d", "mkt_sentiment_5d", "mkt_sentiment_momentum",
]


def _normalize_sentiment(value: str | None) -> str:
    if not value:
        return "neutral"
    val = value.lower().strip()
    if val in {"positive", "bullish", "very_positive", "slightly_positive"}:
        return "positive"
    if val in {"negative", "bearish", "very_negative", "slightly_negative"}:
        return "negative"
    return "neutral"


def _symbol_aliases(symbol: str) -> set[str]:
    root = symbol.split(".")[0].split("-")[0].split("=")[0].upper()
    return {symbol.upper(), root}


def _infer_sentiment(row: dict, symbol: str) -> tuple[str, int]:
    """Infer sentiment and relevance from AI labels, Polygon insights, or text."""
    if row.get("sentiment"):
        relevance = 1 if row.get("relevance") in {"high", "medium", "relevant"} else 0
        return _normalize_sentiment(row.get("sentiment")), relevance

    aliases = _symbol_aliases(symbol)
    insights_raw = row.get("insights_json")
    if insights_raw:
        try:
            insights = json.loads(insights_raw)
            if isinstance(insights, list):
                for item in insights:
                    ticker = str(item.get("ticker", "")).upper()
                    if ticker in aliases:
                        return _normalize_sentiment(item.get("sentiment")), 1
        except Exception:
            pass

    text = f"{row.get('title') or ''} {row.get('description') or ''}".lower()
    pos = sum(1 for word in POS_WORDS if word in text)
    neg = sum(1 for word in NEG_WORDS if word in text)
    if pos > neg:
        return "positive", 1
    if neg > pos:
        return "negative", 1
    return "neutral", 0


def _load_news_features(symbol: str) -> pd.DataFrame:
    """Aggregate aligned news per trade date with AI, Polygon, and text sentiment."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT na.trade_date, nr.title, nr.description, nr.insights_json,
               l1.relevance, l1.sentiment
        FROM news_aligned na
        JOIN news_raw nr ON na.news_id = nr.id
        LEFT JOIN layer1_results l1 ON na.news_id = l1.news_id AND na.symbol = l1.symbol
        WHERE na.symbol = ?
        ORDER BY na.trade_date
        """,
        (symbol,),
    ).fetchall()
    conn.close()

    if not rows:
        return pd.DataFrame()

    daily: dict[str, dict] = {}
    for raw in rows:
        row = dict(raw)
        day = row["trade_date"]
        bucket = daily.setdefault(day, {
            "trade_date": day,
            "n_articles": 0,
            "n_relevant": 0,
            "n_positive": 0,
            "n_negative": 0,
            "n_neutral": 0,
        })
        sentiment, relevant = _infer_sentiment(row, symbol)
        bucket["n_articles"] += 1
        bucket["n_relevant"] += relevant
        if sentiment == "positive":
            bucket["n_positive"] += 1
        elif sentiment == "negative":
            bucket["n_negative"] += 1
        else:
            bucket["n_neutral"] += 1

    df = pd.DataFrame(daily.values())
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    total = df["n_articles"].clip(lower=1)
    df["sentiment_score"] = (df["n_positive"] - df["n_negative"]) / total
    df["relevance_ratio"] = df["n_relevant"] / total
    df["positive_ratio"] = df["n_positive"] / total
    df["negative_ratio"] = df["n_negative"] / total
    df["has_news"] = 1
    return df


def _load_market_sentiment_features() -> pd.DataFrame:
    """Aggregate cross-ticker Layer 1 sentiment by trading date."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT na.trade_date,
               COUNT(*) AS mkt_articles,
               SUM(CASE WHEN l1.sentiment = 'positive' THEN 1 ELSE 0 END) AS mkt_positive,
               SUM(CASE WHEN l1.sentiment = 'negative' THEN 1 ELSE 0 END) AS mkt_negative,
               COUNT(DISTINCT na.symbol) AS mkt_tickers_active
        FROM news_aligned na
        JOIN layer1_results l1 ON l1.news_id = na.news_id AND l1.symbol = na.symbol
        GROUP BY na.trade_date
        ORDER BY na.trade_date
        """
    ).fetchall()
    conn.close()
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([dict(row) for row in rows])
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    total = df["mkt_articles"].clip(lower=1)
    df["mkt_sentiment"] = (df["mkt_positive"] - df["mkt_negative"]) / total
    df["mkt_positive_ratio"] = df["mkt_positive"] / total
    df["mkt_negative_ratio"] = df["mkt_negative"] / total
    df["mkt_sentiment_3d"] = df["mkt_sentiment"].rolling(3, min_periods=1).mean().shift(1)
    df["mkt_sentiment_5d"] = df["mkt_sentiment"].rolling(5, min_periods=1).mean().shift(1)
    df["mkt_sentiment_momentum"] = df["mkt_sentiment_3d"] - df["mkt_sentiment_5d"]
    df[["mkt_sentiment", "mkt_positive_ratio", "mkt_negative_ratio"]] = (
        df[["mkt_sentiment", "mkt_positive_ratio", "mkt_negative_ratio"]].shift(1)
    )
    return df[[
        "trade_date", "mkt_sentiment", "mkt_positive_ratio", "mkt_negative_ratio",
        "mkt_sentiment_3d", "mkt_sentiment_5d", "mkt_sentiment_momentum",
    ]]


def _load_market_price_features(symbol: str) -> pd.DataFrame:
    """Build equal-weight market regime and symbol-relative features."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT symbol, date, close FROM ohlc ORDER BY date, symbol"
    ).fetchall()
    conn.close()
    if not rows:
        return pd.DataFrame()

    raw = pd.DataFrame([dict(row) for row in rows])
    raw["date"] = pd.to_datetime(raw["date"])
    close = raw.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index()
    returns = close.pct_change()
    market_return = returns.mean(axis=1, skipna=True)
    breadth = (returns > 0).mean(axis=1)

    result = pd.DataFrame({"trade_date": close.index})
    result["mkt_ret_1d"] = market_return.shift(1).values
    result["mkt_ret_5d"] = market_return.rolling(5).sum().shift(1).values
    result["mkt_volatility_10d"] = market_return.rolling(10).std().shift(1).values
    result["mkt_momentum_5_20"] = (
        market_return.rolling(5).sum() - market_return.rolling(20).sum()
    ).shift(1).values
    result["mkt_breadth_1d"] = breadth.shift(1).values

    sym = symbol.upper()
    if sym in returns.columns:
        stock_return = returns[sym]
        result["rel_ret_1d"] = (stock_return - market_return).shift(1).values
        result["rel_ret_5d"] = (
            stock_return.rolling(5).sum() - market_return.rolling(5).sum()
        ).shift(1).values
        result["rel_volatility_10d"] = (
            stock_return.rolling(10).std() - market_return.rolling(10).std()
        ).shift(1).values
        cov = stock_return.rolling(60).cov(market_return)
        var = market_return.rolling(60).var().replace(0, np.nan)
        result["beta_60d"] = (cov / var).shift(1).values
    else:
        result["rel_ret_1d"] = 0
        result["rel_ret_5d"] = 0
        result["rel_volatility_10d"] = 0
        result["beta_60d"] = 1

    return result


def _load_ohlc(symbol: str) -> pd.DataFrame:
    conn = get_conn()
    rows = conn.execute(
        "SELECT date, open, high, low, close, volume FROM ohlc WHERE symbol = ? ORDER BY date",
        (symbol,),
    ).fetchall()
    conn.close()
    df = pd.DataFrame([dict(r) for r in rows])
    df["date"] = pd.to_datetime(df["date"])
    return df


def build_features(symbol: str) -> pd.DataFrame:
    """Build feature matrix: one row per trading day.

    All features use shift(1) or past windows to prevent look-ahead leakage.
    Target: whether close > previous close (binary up/down).
    """
    ohlc = _load_ohlc(symbol)
    if ohlc.empty or len(ohlc) < 30:
        return pd.DataFrame()

    news = _load_news_features(symbol)

    # Merge news onto OHLC dates
    df = ohlc.rename(columns={"date": "trade_date"})
    if not news.empty:
        df = df.merge(news, on="trade_date", how="left")
    else:
        for col in ["n_articles", "n_relevant", "n_positive", "n_negative",
                     "n_neutral", "sentiment_score", "relevance_ratio",
                     "positive_ratio", "negative_ratio", "has_news"]:
            df[col] = 0

    # Fill missing news days
    news_cols = ["n_articles", "n_relevant", "n_positive", "n_negative",
                 "n_neutral", "sentiment_score", "relevance_ratio",
                 "positive_ratio", "negative_ratio", "has_news"]
    df[news_cols] = df[news_cols].fillna(0)

    # --- Market regime and cross-ticker sentiment features ---
    market_price = _load_market_price_features(symbol)
    if not market_price.empty:
        df = df.merge(market_price, on="trade_date", how="left")
    market_sentiment = _load_market_sentiment_features()
    if not market_sentiment.empty:
        df = df.merge(market_sentiment, on="trade_date", how="left")

    for col in MARKET_FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0
    df[MARKET_FEATURE_COLS] = df[MARKET_FEATURE_COLS].fillna({
        "beta_60d": 1,
    }).fillna(0)

    # --- Rolling news features (use current + past, no shift needed since news is pre-market/same day) ---
    for w in [3, 5, 10]:
        df[f"sentiment_score_{w}d"] = df["sentiment_score"].rolling(w, min_periods=1).mean()
        df[f"positive_ratio_{w}d"] = df["positive_ratio"].rolling(w, min_periods=1).mean()
        df[f"negative_ratio_{w}d"] = df["negative_ratio"].rolling(w, min_periods=1).mean()
        df[f"news_count_{w}d"] = df["n_articles"].rolling(w, min_periods=1).sum()
    # Sentiment momentum: 3d mean - 10d mean
    df["sentiment_momentum_3d"] = df["sentiment_score_3d"] - df["sentiment_score_10d"]

    # --- Price / technical features (shifted by 1 to prevent leakage) ---
    close = df["close"]
    df["ret_1d"] = close.pct_change(1).shift(1)
    df["ret_3d"] = close.pct_change(3).shift(1)
    df["ret_5d"] = close.pct_change(5).shift(1)
    df["ret_10d"] = close.pct_change(10).shift(1)

    df["volatility_5d"] = close.pct_change().rolling(5).std().shift(1)
    df["volatility_10d"] = close.pct_change().rolling(10).std().shift(1)

    avg_vol_5 = df["volume"].rolling(5).mean().shift(1)
    df["volume_ratio_5d"] = (df["volume"].shift(1) / avg_vol_5.clip(lower=1))

    df["gap"] = (df["open"] / close.shift(1) - 1).shift(1)

    ma5 = close.rolling(5).mean().shift(1)
    ma20 = close.rolling(20).mean().shift(1)
    df["ma5_vs_ma20"] = (ma5 / ma20.clip(lower=0.01) - 1)

    # RSI 14
    delta = close.diff().shift(1)
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.clip(lower=1e-10)
    df["rsi_14"] = 100 - 100 / (1 + rs)

    df["day_of_week"] = df["trade_date"].dt.dayofweek

    # --- Targets: next-N-day direction ---
    df["target_t1"] = (close.shift(-1) > close).astype(int)
    df["target_t2"] = (close.shift(-2) > close).astype(int)
    df["target_t3"] = (close.shift(-3) > close).astype(int)
    df["target_t5"] = (close.shift(-5) > close).astype(int)

    # Drop rows without enough history
    df = df.dropna(subset=["ret_10d", "rsi_14"]).reset_index(drop=True)
    feature_cols = [col for col in FEATURE_COLS if col in df.columns]
    df[feature_cols] = df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0)

    return df


def build_features_multi(symbols: list[str] | None = None) -> pd.DataFrame:
    """Build combined feature matrix for multiple tickers.

    Adds a 'symbol' column. All price features are already returns/ratios
    so they are comparable across tickers.
    """
    if symbols is None:
        from database import get_conn
        conn = get_conn()
        rows = conn.execute(
            "SELECT DISTINCT symbol FROM ohlc"
        ).fetchall()
        conn.close()
        symbols = [r["symbol"] for r in rows]

    frames = []
    for sym in symbols:
        df = build_features(sym)
        if df.empty:
            continue
        df["symbol"] = sym
        frames.append(df)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


FEATURE_COLS = [
    # News
    "n_articles", "n_relevant", "n_positive", "n_negative", "n_neutral",
    "sentiment_score", "relevance_ratio", "positive_ratio", "negative_ratio", "has_news",
    # Rolling news
    "sentiment_score_3d", "sentiment_score_5d", "sentiment_score_10d",
    "positive_ratio_3d", "positive_ratio_5d", "positive_ratio_10d",
    "negative_ratio_3d", "negative_ratio_5d", "negative_ratio_10d",
    "news_count_3d", "news_count_5d", "news_count_10d",
    "sentiment_momentum_3d",
    # Market regime / relative strength
    "mkt_ret_1d", "mkt_ret_5d", "mkt_volatility_10d", "mkt_momentum_5_20",
    "mkt_breadth_1d", "rel_ret_1d", "rel_ret_5d", "rel_volatility_10d", "beta_60d",
    "mkt_sentiment", "mkt_positive_ratio", "mkt_negative_ratio",
    "mkt_sentiment_3d", "mkt_sentiment_5d", "mkt_sentiment_momentum",
    # Price / tech
    "ret_1d", "ret_3d", "ret_5d", "ret_10d",
    "volatility_5d", "volatility_10d",
    "volume_ratio_5d", "gap", "ma5_vs_ma20", "rsi_14", "day_of_week",
]


FEATURE_GROUPS = {
    "news_sentiment": {
        "label": "News",
        "columns": [
            "n_articles", "n_relevant", "n_positive", "n_negative", "n_neutral",
            "sentiment_score", "relevance_ratio", "positive_ratio", "negative_ratio", "has_news",
            "sentiment_score_3d", "sentiment_score_5d", "sentiment_score_10d",
            "positive_ratio_3d", "positive_ratio_5d", "positive_ratio_10d",
            "negative_ratio_3d", "negative_ratio_5d", "negative_ratio_10d",
            "news_count_3d", "news_count_5d", "news_count_10d",
            "sentiment_momentum_3d",
        ],
    },
    "market_regime": {
        "label": "Market",
        "columns": MARKET_FEATURE_COLS,
    },
    "technical_price": {
        "label": "Technical",
        "columns": [
            "ret_1d", "ret_3d", "ret_5d", "ret_10d",
            "volatility_5d", "volatility_10d",
            "volume_ratio_5d", "gap", "ma5_vs_ma20", "rsi_14", "day_of_week",
        ],
    },
}


def feature_group_importance(importances, feature_cols: list[str] | None = None) -> list[dict]:
    """Aggregate model feature importances into human-readable driver groups."""
    cols = feature_cols or FEATURE_COLS
    values = np.asarray(importances, dtype=float)
    total = float(np.abs(values).sum())
    if total <= 0:
        total = 1.0

    by_name = {name: abs(float(values[i])) for i, name in enumerate(cols) if i < len(values)}
    groups = []
    for key, spec in FEATURE_GROUPS.items():
        members = [name for name in spec["columns"] if name in by_name]
        group_total = sum(by_name[name] for name in members)
        top_feature = max(members, key=lambda name: by_name[name]) if members else None
        groups.append({
            "key": key,
            "label": spec["label"],
            "importance": round(group_total / total, 4),
            "feature_count": len(members),
            "top_feature": top_feature,
        })

    covered = {name for spec in FEATURE_GROUPS.values() for name in spec["columns"]}
    other_members = [name for name in cols if name not in covered and name in by_name]
    if other_members:
        other_total = sum(by_name[name] for name in other_members)
        top_feature = max(other_members, key=lambda name: by_name[name])
        groups.append({
            "key": "other",
            "label": "Other",
            "importance": round(other_total / total, 4),
            "feature_count": len(other_members),
            "top_feature": top_feature,
        })

    return sorted(groups, key=lambda item: item["importance"], reverse=True)
