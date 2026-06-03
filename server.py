#!/usr/bin/env python3
"""
天眼 SkyEye v5 - 全球财经洞察平台
Unified financial intelligence platform combining market overview, deep analysis, and ML pipeline
"""

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from pathlib import Path

from database import init_db

app = FastAPI(title="天眼 SkyEye", version="5.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=500)

LOCAL_CLIENTS = {"127.0.0.1", "::1", "localhost"}


@app.middleware("http")
async def local_only_guard(request: Request, call_next):
    if os.getenv("SKYEYE_ALLOW_REMOTE") == "1":
        return await call_next(request)

    client_host = request.client.host if request.client else ""
    if client_host not in LOCAL_CLIENTS:
        return PlainTextResponse(
            "SkyEye is running in local-only mode. Set SKYEYE_ALLOW_REMOTE=1 to allow remote clients.",
            status_code=403,
        )
    return await call_next(request)

# Import routers
from routers import market, stocks, news, analysis, predict, portfolio, geopolitical, events, market_sectors, opportunity, paper

app.include_router(market.router, prefix="/api", tags=["market"])
app.include_router(stocks.router, prefix="/api/stocks", tags=["stocks"])
app.include_router(news.router, prefix="/api/news", tags=["news"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(predict.router, prefix="/api/predict", tags=["predict"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(geopolitical.router, prefix="/api", tags=["geopolitical"])
app.include_router(events.router, prefix="/api", tags=["events"])
app.include_router(market_sectors.router, prefix="/api", tags=["market_sectors"])
app.include_router(opportunity.router, prefix="/api", tags=["opportunity"])
app.include_router(paper.router, prefix="/api/paper", tags=["paper"])

@app.on_event("startup")
def startup():
    init_db()
    # Auto-seed popular tickers and trigger background data fetch
    import threading
    from database import get_conn
    DEFAULT_TICKERS = [
        "NVDA","AAPL","MSFT","TSLA","META","AMZN","GOOGL","AMD","AVGO","PLTR",
        "0700.HK","9988.HK","3690.HK","9618.HK","1810.HK",
        "^GSPC","^IXIC","^DJI","^HSI",
        "BTC-USD","ETH-USD","SOL-USD","GC=F","CL=F",
    ]
    conn = get_conn()
    for sym in DEFAULT_TICKERS:
        conn.execute("INSERT OR IGNORE INTO tickers (symbol, name) VALUES (?, ?)", (sym, sym))
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM ohlc").fetchone()[0]
    conn.close()
    if count < 100:
        def seed_data():
            from polygon_client import fetch_ohlc, fetch_news
            from datetime import datetime, timedelta, timezone
            import time, json
            today = datetime.now(timezone.utc).date()
            start = (today - timedelta(days=365*2)).isoformat()
            end = today.isoformat()
            for sym in DEFAULT_TICKERS:
                if sym.startswith("^") or "-" in sym:
                    continue
                try:
                    ohlc_rows = fetch_ohlc(sym, start, end)
                    conn = get_conn()
                    for row in ohlc_rows:
                        conn.execute("INSERT OR IGNORE INTO ohlc (symbol, date, open, high, low, close, volume, vwap, transactions) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (sym, row["date"], row["open"], row["high"], row["low"], row["close"], row["volume"], row["vwap"], row["transactions"]))
                    conn.execute("UPDATE tickers SET last_ohlc_fetch = ? WHERE symbol = ?", (end, sym))
                    conn.commit()
                    articles = fetch_news(sym, start, end, max_pages=2)
                    for art in articles:
                        nid = art.get("id")
                        if not nid: continue
                        tickers = art.get("tickers") or []
                        conn.execute("INSERT OR IGNORE INTO news_raw (id, title, description, publisher, author, published_utc, article_url, amp_url, tickers_json, insights_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (nid, art.get("title"), art.get("description"), art.get("publisher"), art.get("author"),
                             art.get("published_utc"), art.get("article_url"), art.get("amp_url"), json.dumps(tickers),
                             json.dumps(art.get("insights")) if art.get("insights") else None))
                        for tk in tickers:
                            conn.execute("INSERT OR IGNORE INTO news_ticker (news_id, symbol) VALUES (?, ?)", (nid, tk))
                    conn.execute("UPDATE tickers SET last_news_fetch = ? WHERE symbol = ?", (end, sym))
                    conn.commit(); conn.close()
                    print(f"  {sym}: {len(ohlc_rows)} candles, {len(articles)} news")
                    time.sleep(1.5)
                except Exception as e:
                    print(f"  {sym}: {e}")
            # Align news to OHLC
            try:
                from pipeline.alignment import align_news_for_symbol
                for sym in DEFAULT_TICKERS:
                    if not sym.startswith("^") and "-" not in sym:
                        try:
                            align_news_for_symbol(sym)
                        except: pass
            except: pass
            print("Data seeding complete")
        threading.Thread(target=seed_data, daemon=True).start()
        print("Background data seeding started...")

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "5.0.0"}

# Search endpoint combining local + Polygon
@app.get("/api/search/{query}")
def search(query: str):
    import urllib.parse
    from routers.stocks import search_symbols

    raw_q = urllib.parse.unquote(query).strip()
    return {"results": search_symbols(raw_q, limit=15)}

# Company details
@app.get("/api/company/{symbol}")
def company_details(symbol: str):
    from polygon_client import polygon_stock_details
    from routers.market import MARKETS
    details = polygon_stock_details(symbol)
    if details: return details
    for mk, mc in MARKETS.items():
        if symbol in mc.get("stocks", {}):
            info = mc["stocks"][symbol]
            return {"symbol":symbol,"name":info.get("name"),"description":"","homepage":"","news":[],"financials":[]}
    return {"error": "Company not found"}

# Serve frontend
dist_dir = Path(__file__).parent / "frontend" / "dist"
static_dir = dist_dir if dist_dir.exists() else Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets") if (static_dir / "assets").exists() else None

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = static_dir / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(static_dir / "index.html"))

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("SKYEYE_HOST", "127.0.0.1")
    port = int(os.getenv("SKYEYE_PORT", "8888"))
    print(f"🚀 天眼 SkyEye v5: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
