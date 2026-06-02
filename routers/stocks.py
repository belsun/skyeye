import logging
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
from database import get_conn
from polygon_client import fetch_ohlc, fetch_news, search_tickers

router = APIRouter()

CURATED_SECURITIES = {
    "0100.HK": {
        "symbol": "0100.HK",
        "name": "MiniMax / 稀宇科技 (HKEX 00100, 行情源 0100.HK)",
        "sector": "AI应用/大模型",
        "type": "港股",
        "aliases": ["00100.HK", "00100", "0100", "MINIMAX", "稀宇科技", "M3", "海螺AI"],
    },
    "0700.HK": {
        "symbol": "0700.HK",
        "name": "腾讯控股 Tencent",
        "sector": "港股科技/游戏/云",
        "type": "港股",
        "aliases": ["00700", "700", "TENCENT", "腾讯"],
    },
    "9988.HK": {
        "symbol": "9988.HK",
        "name": "阿里巴巴 Alibaba",
        "sector": "港股科技/电商/云",
        "type": "港股",
        "aliases": ["09988", "BABA", "ALIBABA", "阿里"],
    },
    "1810.HK": {
        "symbol": "1810.HK",
        "name": "小米集团 Xiaomi",
        "sector": "港股科技/硬件/汽车",
        "type": "港股",
        "aliases": ["01810", "XIAOMI", "小米"],
    },
    "3690.HK": {
        "symbol": "3690.HK",
        "name": "美团 Meituan",
        "sector": "港股科技/本地生活",
        "type": "港股",
        "aliases": ["03690", "MEITUAN", "美团"],
    },
    "9618.HK": {
        "symbol": "9618.HK",
        "name": "京东集团 JD.com",
        "sector": "港股科技/电商",
        "type": "港股",
        "aliases": ["09618", "JD", "京东"],
    },
}

class AddTickerRequest(BaseModel):
    symbol: str
    name: Optional[str] = None

def normalize_symbol(symbol: str) -> str:
    sym = (symbol or "").strip().upper().replace(" ", "")
    sym = sym.replace("HKEX:", "").replace("SEHK:", "")
    if not sym:
        return ""
    if sym.endswith(".HK"):
        code = sym[:-3]
        if code.isdigit() and len(code) <= 5:
            return f"{str(int(code)).zfill(4)}.HK"
    if sym.isdigit():
        if len(sym) <= 5:
            return f"{str(int(sym)).zfill(4)}.HK"
        if len(sym) == 6:
            return f"{sym}.SS" if sym.startswith("6") else f"{sym}.SZ"
    return sym

def _matches_curated(query: str, normalized: str, item: dict) -> bool:
    q = (query or "").strip().upper().replace(" ", "")
    haystack = [
        item["symbol"].upper(),
        item["name"].upper(),
        item.get("sector", "").upper(),
        *[str(alias).upper() for alias in item.get("aliases", [])],
    ]
    return normalized == item["symbol"] or any(q and q in value for value in haystack)

def _curated_results(query: str, normalized: str) -> list[dict]:
    return [
        dict(item)
        for item in CURATED_SECURITIES.values()
        if _matches_curated(query, normalized, item)
    ]

def _enrich_result(row: dict) -> dict:
    symbol = normalize_symbol(row.get("symbol") or "")
    curated = CURATED_SECURITIES.get(symbol)
    if curated:
        merged = {**dict(row), **curated}
        merged["symbol"] = symbol
        return merged
    return dict(row)

def search_symbols(query: str, limit: int = 15, include_remote: bool = True) -> list[dict]:
    raw = (query or "").strip()
    normalized = normalize_symbol(raw) or raw.upper()
    results: list[dict] = []
    seen: set[str] = set()

    def add(item: dict):
        enriched = _enrich_result(item)
        symbol = normalize_symbol(enriched.get("symbol") or "")
        if not symbol or symbol in seen:
            return
        enriched["symbol"] = symbol
        seen.add(symbol)
        results.append(enriched)

    for item in _curated_results(raw, normalized):
        add(item)
    if results and not include_remote:
        return results[:limit]

    conn = get_conn()
    try:
        local = conn.execute(
            """SELECT symbol, name, sector
               FROM tickers
               WHERE symbol LIKE ? OR symbol LIKE ? OR name LIKE ? OR sector LIKE ?
               LIMIT ?""",
            (f"%{normalized}%", f"%{raw.upper()}%", f"%{raw}%", f"%{raw}%", limit),
        ).fetchall()
    finally:
        conn.close()
    for row in local:
        add(dict(row))

    if include_remote and len(results) < limit:
        try:
            for row in search_tickers(normalized, limit=limit):
                add(row)
                if len(results) >= limit:
                    break
        except Exception:
            pass

    return results[:limit]

@router.get("")
def list_tickers():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM tickers ORDER BY symbol").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/search")
def search(q: str = Query(..., min_length=1)):
    return search_symbols(q, limit=15)

@router.get("/{symbol}/ohlc")
def get_ohlc(symbol: str, start: Optional[str] = None, end: Optional[str] = None):
    normalized = normalize_symbol(symbol)
    conn = get_conn()
    query = "SELECT * FROM ohlc WHERE symbol = ?"
    params = [normalized]
    if start: query += " AND date >= ?"; params.append(start)
    if end: query += " AND date <= ?"; params.append(end)
    query += " ORDER BY date ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    if not rows:
        try:
            fallback_rows = _fetch_yfinance_ohlc(normalized, period="2y")
        except Exception:
            fallback_rows = []
        if fallback_rows:
            conn = get_conn()
            for row in fallback_rows:
                conn.execute(
                    "INSERT OR IGNORE INTO ohlc (symbol, date, open, high, low, close, volume, vwap, transactions) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (normalized, row["date"], row["open"], row["high"], row["low"], row["close"], row["volume"], row["vwap"], row["transactions"]),
                )
            conn.execute("UPDATE tickers SET last_ohlc_fetch = ? WHERE symbol = ?", (fallback_rows[-1]["date"], normalized))
            conn.commit()
            conn.close()
            return fallback_rows
        raise HTTPException(status_code=404, detail=f"No OHLC data for {normalized}. 该标的可能是新股或免费行情源暂未覆盖。")
    return [dict(r) for r in rows]

@router.post("")
def add_ticker(req: AddTickerRequest, background_tasks: BackgroundTasks):
    symbol = normalize_symbol(req.symbol)
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")
    curated = CURATED_SECURITIES.get(symbol)
    name = req.name or (curated or {}).get("name") or symbol
    sector = (curated or {}).get("sector")
    conn = get_conn()
    conn.execute(
        """INSERT INTO tickers (symbol, name, sector)
           VALUES (?, ?, ?)
           ON CONFLICT(symbol) DO UPDATE SET
             name = COALESCE(excluded.name, tickers.name),
             sector = COALESCE(excluded.sector, tickers.sector)""",
        (symbol, name, sector),
    )
    conn.commit(); conn.close()
    background_tasks.add_task(_fetch_ticker_data, symbol)
    return {"symbol": symbol, "name": name, "sector": sector, "status": "added", "message": "Data fetch started in background"}

def _fetch_ticker_data(symbol: str):
    today = datetime.now(timezone.utc).date()
    start = (today - timedelta(days=2*366)).isoformat()
    end = today.isoformat()
    try:
        try:
            ohlc_rows = fetch_ohlc(symbol, start, end)
        except Exception:
            ohlc_rows = _fetch_yfinance_ohlc(symbol, period="2y")
        conn = get_conn()
        for row in ohlc_rows:
            conn.execute("INSERT OR IGNORE INTO ohlc (symbol, date, open, high, low, close, volume, vwap, transactions) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (symbol, row["date"], row["open"], row["high"], row["low"], row["close"], row["volume"], row["vwap"], row["transactions"]))
        if ohlc_rows:
            conn.execute("UPDATE tickers SET last_ohlc_fetch = ? WHERE symbol = ?", (ohlc_rows[-1]["date"], symbol))
        conn.commit()
        import json
        try:
            articles = fetch_news(symbol, start, end)
        except Exception:
            articles = []
        for art in articles:
            news_id = art.get("id")
            if not news_id: continue
            tickers = art.get("tickers") or []
            conn.execute("INSERT OR IGNORE INTO news_raw (id, title, description, publisher, author, published_utc, article_url, amp_url, image_url, tickers_json, insights_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (news_id, art.get("title"), art.get("description"), art.get("publisher"), art.get("author"),
                 art.get("published_utc"), art.get("article_url"), art.get("amp_url"), art.get("image_url"), json.dumps(tickers),
                 json.dumps(art.get("insights")) if art.get("insights") else None))
            for tk in tickers:
                conn.execute("INSERT OR IGNORE INTO news_ticker (news_id, symbol) VALUES (?, ?)", (news_id, tk))
        if articles:
            conn.execute("UPDATE tickers SET last_news_fetch = ? WHERE symbol = ?", (end, symbol))
        conn.commit(); conn.close()
    except Exception as e:
        logger.exception("Error fetching data for %s", symbol)

def _fetch_yfinance_ohlc(symbol: str, period: str = "2y") -> list[dict]:
    import math
    import yfinance as yf

    hist = yf.Ticker(symbol).history(period=period, interval="1d")
    rows = []
    if hist.empty:
        return rows
    for date, row in hist.iterrows():
        open_, high, low, close = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
        volume = float(row.get("Volume", 0) or 0)
        if any(math.isnan(v) for v in [open_, high, low, close]):
            continue
        if math.isnan(volume):
            volume = 0
        rows.append({
            "date": date.strftime("%Y-%m-%d"),
            "open": round(open_, 4),
            "high": round(high, 4),
            "low": round(low, 4),
            "close": round(close, 4),
            "volume": volume,
            "vwap": None,
            "transactions": None,
        })
    return rows
