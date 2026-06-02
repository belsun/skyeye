#!/usr/bin/env python3
"""Fetch fresh news from Polygon for all tracked stocks and align to OHLC dates."""

import json, time, sys
from datetime import datetime, timedelta, timezone
from database import get_conn
from polygon_client import fetch_news, fetch_ohlc

STOCKS = ["NVDA", "AAPL", "MSFT", "TSLA", "META", "AMZN", "GOOGL", "AMD", "AVGO", "PLTR"]

def get_latest_news_date(symbol):
    """Get the latest news date for a symbol from news_ticker + news_raw."""
    conn = get_conn()
    r = conn.execute(
        "SELECT MAX(nr.published_utc) as d FROM news_raw nr "
        "JOIN news_ticker nt ON nr.id = nt.news_id WHERE nt.symbol = ?",
        (symbol,)
    ).fetchone()
    conn.close()
    return r["d"] if r and r["d"] else None

def get_latest_ohlc_date(symbol):
    """Get the latest OHLC date for a symbol."""
    conn = get_conn()
    r = conn.execute("SELECT MAX(date) as d FROM ohlc WHERE symbol = ?", (symbol,)).fetchone()
    conn.close()
    return r["d"] if r and r["d"] else None

def fetch_and_store_news(symbol, start_date, end_date):
    """Fetch news from Polygon and store in DB."""
    print(f"  Fetching news for {symbol}: {start_date} to {end_date}")
    try:
        articles = fetch_news(symbol, start_date, end_date, per_page=50, max_pages=5)
    except Exception as e:
        print(f"    ERROR fetching news: {e}")
        return 0

    if not articles:
        print(f"    No articles found")
        return 0

    conn = get_conn()
    inserted = 0
    for art in articles:
        nid = art.get("id")
        if not nid:
            continue
        tickers = art.get("tickers") or []
        try:
            conn.execute(
                "INSERT OR IGNORE INTO news_raw "
                "(id, title, description, publisher, author, published_utc, article_url, amp_url, tickers_json, insights_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (nid, art.get("title"), art.get("description"), art.get("publisher"), art.get("author"),
                 art.get("published_utc"), art.get("article_url"), art.get("amp_url"),
                 json.dumps(tickers), json.dumps(art.get("insights")) if art.get("insights") else None)
            )
            for tk in tickers:
                conn.execute("INSERT OR IGNORE INTO news_ticker (news_id, symbol) VALUES (?, ?)", (nid, tk))
            inserted += 1
        except Exception as e:
            pass  # Skip duplicates or errors
    conn.commit()
    conn.close()
    print(f"    Inserted {inserted} articles")
    return inserted

def fetch_and_store_ohlc(symbol, start_date, end_date):
    """Fetch OHLC from Polygon and store in DB."""
    print(f"  Fetching OHLC for {symbol}: {start_date} to {end_date}")
    try:
        rows = fetch_ohlc(symbol, start_date, end_date)
    except Exception as e:
        print(f"    ERROR fetching OHLC: {e}")
        return 0

    if not rows:
        print(f"    No OHLC data found")
        return 0

    conn = get_conn()
    inserted = 0
    for row in rows:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO ohlc (symbol, date, open, high, low, close, volume, vwap, transactions) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (symbol, row["date"], row["open"], row["high"], row["low"],
                 row["close"], row["volume"], row["vwap"], row["transactions"])
            )
            inserted += 1
        except:
            pass
    conn.commit()
    conn.close()
    print(f"    Inserted {inserted} OHLC rows")
    return inserted

def align_all():
    """Run news alignment for all tracked stocks."""
    from pipeline.alignment import align_news_for_symbol
    print("\n=== Aligning news to OHLC dates ===")
    for sym in STOCKS:
        try:
            result = align_news_for_symbol(sym)
            print(f"  {sym}: aligned {result.get('aligned', 0)} (total news: {result.get('total_news', 0)})")
        except Exception as e:
            print(f"  {sym}: alignment error: {e}")

def main():
    today = datetime.now(timezone.utc).date()
    two_years_ago = today - timedelta(days=365*2)
    
    print("=== Mass News & OHLC Fetch ===")
    print(f"Date range: {two_years_ago} to {today}")
    print(f"Stocks: {', '.join(STOCKS)}")
    print()
    
    total_news = 0
    total_ohlc = 0
    
    for sym in STOCKS:
        print(f"\n--- {sym} ---")
        
        # Check latest OHLC date
        latest_ohlc = get_latest_ohlc_date(sym)
        if latest_ohlc:
            ohlc_start = latest_ohlc  # Only fetch missing dates
            print(f"  Latest OHLC: {latest_ohlc}")
        else:
            ohlc_start = two_years_ago.isoformat()
            print(f"  No OHLC data, fetching from {ohlc_start}")
        
        # Fetch OHLC if needed
        if ohlc_start < today.isoformat():
            n = fetch_and_store_ohlc(sym, ohlc_start, today.isoformat())
            total_ohlc += n
            time.sleep(1.0)
        
        # Fetch news - always fetch recent news (last 90 days minimum)
        news_start = max(two_years_ago.isoformat(), "2024-06-01")
        n = fetch_and_store_news(sym, news_start, today.isoformat())
        total_news += n
        time.sleep(1.2)
    
    print(f"\n=== Fetch Complete ===")
    print(f"Total news: {total_news}")
    print(f"Total OHLC: {total_ohlc}")
    
    # Align all
    align_all()
    
    # Final stats
    conn = get_conn()
    r = conn.execute("SELECT COUNT(*) as c FROM news_raw").fetchone()
    print(f"\nFinal news_raw count: {r['c']}")
    r = conn.execute("SELECT COUNT(*) as c FROM news_aligned").fetchone()
    print(f"Final news_aligned count: {r['c']}")
    r = conn.execute("SELECT MIN(published_utc) as mn, MAX(published_utc) as mx FROM news_raw").fetchone()
    print(f"News date range: {r['mn']} to {r['mx']}")
    conn.close()
    
    print("\nDone!")

if __name__ == "__main__":
    main()
