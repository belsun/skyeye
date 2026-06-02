"""Layer 2: On-demand SkyEye deep analysis.

Triggered when user clicks a news article. Cached in layer2_results.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone

from database import get_conn


def get_cached(news_id: str, symbol: str) -> Optional[Dict[str, Any]]:
    """Check if a deep analysis is already cached."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM layer2_results WHERE news_id = ? AND symbol = ?",
        (news_id, symbol),
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def analyze_article(news_id: str, symbol: str) -> Dict[str, Any]:
    """Run deep SkyEye analysis on a single article. Returns cached if available."""
    cached = get_cached(news_id, symbol)
    if cached:
        return cached

    # Fetch article data
    conn = get_conn()
    article = conn.execute(
        "SELECT title, description, article_url FROM news_raw WHERE id = ?",
        (news_id,),
    ).fetchone()
    conn.close()

    if not article:
        return {"error": "Article not found"}

    from ai_analyzer import analyze_article_impact

    parsed = analyze_article_impact(article["title"], article["description"], symbol)

    # Cache result
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO layer2_results
           (news_id, symbol, discussion, growth_reasons, decrease_reasons, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            news_id,
            symbol,
            parsed.get("discussion", ""),
            parsed.get("growth_reasons", ""),
            parsed.get("decrease_reasons", ""),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()

    return {
        "news_id": news_id,
        "symbol": symbol,
        "discussion": parsed.get("discussion", ""),
        "growth_reasons": parsed.get("growth_reasons", ""),
        "decrease_reasons": parsed.get("decrease_reasons", ""),
    }


def generate_story(symbol: str, csv_content: str) -> str:
    """Generate an AI story about stock price movements. Port from app.py."""
    from ai_analyzer import generate_trend_story

    return generate_trend_story(symbol, csv_content)


def analyze_range(symbol: str, start_date: str, end_date: str, question: Optional[str] = None) -> Dict[str, Any]:
    """Analyze what drove price movement in a date range using SkyEye AI."""
    conn = get_conn()

    # Get OHLC data for range
    ohlc_rows = conn.execute(
        "SELECT date, open, high, low, close, volume FROM ohlc WHERE symbol = ? AND date >= ? AND date <= ? ORDER BY date ASC",
        (symbol, start_date, end_date),
    ).fetchall()

    if not ohlc_rows:
        conn.close()
        return {"error": "No OHLC data for this range"}

    open_price = ohlc_rows[0]["open"]
    close_price = ohlc_rows[-1]["close"]
    high_price = max(r["high"] for r in ohlc_rows)
    low_price = min(r["low"] for r in ohlc_rows)
    price_change_pct = round((close_price - open_price) / open_price * 100, 2)

    # Get news in range, prioritize by impact
    news_rows = conn.execute(
        """SELECT nr.title, l1.chinese_summary, l1.key_discussion,
                  l1.sentiment, l1.reason_growth, l1.reason_decrease,
                  na.trade_date, na.ret_t0
           FROM news_aligned na
           JOIN layer1_results l1 ON na.news_id = l1.news_id AND l1.symbol = na.symbol
           JOIN news_raw nr ON na.news_id = nr.id
           WHERE na.symbol = ? AND na.trade_date >= ? AND na.trade_date <= ?
             AND l1.relevance = 'relevant'
           ORDER BY ABS(COALESCE(na.ret_t0, 0)) DESC
           LIMIT 30""",
        (symbol, start_date, end_date),
    ).fetchall()
    conn.close()

    news_count = len(news_rows)

    # Build news context for prompt
    news_context = ""
    for i, row in enumerate(news_rows[:30], 1):
        ret = f"Same-day change: {row['ret_t0']*100:.2f}%" if row["ret_t0"] else ""
        news_context += f"\n{i}. [{row['trade_date']}] {row['title']}\n"
        if row["chinese_summary"]:
            news_context += f"   Summary: {row['chinese_summary']}\n"
        if ret:
            news_context += f"   {ret}\n"

    # Build OHLC summary
    ohlc_summary = f"Open: ${open_price:.2f}, Close: ${close_price:.2f}, High: ${high_price:.2f}, Low: ${low_price:.2f}, Change: {price_change_pct:+.2f}%, Trading days: {len(ohlc_rows)}"

    from ai_analyzer import analyze_price_range

    analysis = analyze_price_range(
        symbol,
        start_date,
        end_date,
        ohlc_summary,
        news_context if news_context else "No related news during this period",
        question or "",
    )

    return {
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "price_change_pct": price_change_pct,
        "open_price": open_price,
        "close_price": close_price,
        "high_price": high_price,
        "low_price": low_price,
        "news_count": news_count,
        "trading_days": len(ohlc_rows),
        "analysis": analysis,
    }
