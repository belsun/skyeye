import time, requests
from typing import Dict, List, Any, Optional
from config import POLYGON_API_KEY

BASE = "https://api.polygon.io"

def _headers():
    return {"Authorization": f"Bearer {POLYGON_API_KEY}"}

def http_get(url, params=None, max_retries=8, backoff=2.0):
    for i in range(max_retries):
        try:
            resp = requests.get(url, params=params or {}, headers=_headers(), timeout=30)
        except requests.RequestException:
            time.sleep((backoff**i) + 0.5)
            if i == max_retries - 1: raise
            continue
        if resp.status_code == 429:
            ra = resp.headers.get("Retry-After")
            wait = float(ra) if (ra and ra.isdigit()) else min((backoff**i) + 1.0, 60.0)
            time.sleep(wait)
            if i == max_retries - 1: resp.raise_for_status()
            continue
        if 500 <= resp.status_code < 600:
            time.sleep(min((backoff**i) + 1.0, 60.0))
            if i == max_retries - 1: resp.raise_for_status()
            continue
        resp.raise_for_status()
        return resp
    raise RuntimeError("Unreachable")

def fetch_ohlc(ticker, start, end):
    url = f"{BASE}/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}"
    params = {"adjusted": "true", "sort": "asc", "limit": 50000}
    resp = http_get(url, params=params)
    results = resp.json().get("results") or []
    from datetime import datetime, timezone
    rows = []
    for r in results:
        d = datetime.fromtimestamp(int(r["t"]) / 1000, tz=timezone.utc).date().isoformat()
        rows.append({"date": d, "open": r.get("o"), "high": r.get("h"), "low": r.get("l"),
                     "close": r.get("c"), "volume": r.get("v"), "vwap": r.get("vw"), "transactions": r.get("n")})
    return rows

def fetch_news(ticker, start, end, per_page=50, max_pages=None):
    url = f"{BASE}/v2/reference/news"
    params = {"ticker": ticker, "published_utc.gte": start, "published_utc.lte": end, "limit": per_page, "order": "asc"}
    all_articles, seen_ids, pages, next_url = [], set(), 0, None
    while True:
        resp = http_get(next_url or url, params=None if next_url else params)
        data = resp.json()
        for r in data.get("results", []) or []:
            rid = r.get("id")
            if rid and rid in seen_ids: continue
            all_articles.append({"id": rid, "publisher": (r.get("publisher") or {}).get("name"),
                "title": r.get("title"), "author": r.get("author"), "published_utc": r.get("published_utc"),
                "amp_url": r.get("amp_url"), "article_url": r.get("article_url"),
                "image_url": r.get("image_url"), "tickers": r.get("tickers"),
                "description": r.get("description"), "insights": r.get("insights")})
            if rid: seen_ids.add(rid)
        next_url = data.get("next_url")
        pages += 1
        if max_pages and pages >= max_pages: break
        if not next_url: break
        time.sleep(1.2)
    return all_articles

def search_tickers(query, limit=20):
    url = f"{BASE}/v3/reference/tickers"
    params = {"search": query, "active": "true", "limit": limit, "market": "stocks"}
    resp = http_get(url, params=params)
    results = resp.json().get("results") or []
    return [{"symbol": r.get("ticker", ""), "name": r.get("name", ""), "sector": r.get("sic_description", "")} for r in results]

def polygon_stock_details(symbol):
    try:
        details = http_get(f"{BASE}/v3/reference/tickers/{symbol}").json()
        if "results" not in details: return None
        r = details["results"]
        news_data = http_get(f"{BASE}/v2/reference/news", {"ticker": symbol, "limit": 10, "sort": "published_utc", "order": "desc"}).json()
        news = []
        for n in news_data.get("results", []):
            news.append({"title": n.get("title", ""), "description": (n.get("description") or "")[:200],
                "url": n.get("article_url", ""), "published": n.get("published_utc", ""),
                "source": (n.get("publisher") or {}).get("name", ""), "tickers": n.get("tickers", [])})
        return {"symbol": symbol, "name": r.get("name", ""), "description": r.get("description", ""),
            "homepage": r.get("homepage_url", ""), "logo": (r.get("branding") or {}).get("logo_url", ""),
            "exchange": r.get("primary_exchange", ""), "market_cap": r.get("market_cap", 0),
            "employees": r.get("total_employees", 0), "news": news}
    except: return None
