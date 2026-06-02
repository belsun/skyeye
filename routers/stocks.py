import logging
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

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
        "website": "https://www.minimax.io/",
        "summary_zh": "MiniMax / 稀宇科技是大模型与AI应用公司，产品方向包括文本、语音、视频、Agent和面向消费者的海螺AI。作为港股AI应用标的，适合重点跟踪产品发布、用户增长、商业化和大模型成本变化。",
    },
    "0700.HK": {
        "symbol": "0700.HK",
        "name": "腾讯控股 Tencent",
        "sector": "港股科技/游戏/云",
        "type": "港股",
        "aliases": ["00700", "700", "TENCENT", "腾讯"],
        "website": "https://www.tencent.com/",
        "summary_zh": "腾讯控股是中国大型互联网平台公司，业务覆盖社交、游戏、金融科技、云计算、广告和AI基础设施。跟踪重点包括游戏版号、广告恢复、云与AI投入、回购和利润率。",
    },
    "9988.HK": {
        "symbol": "9988.HK",
        "name": "阿里巴巴 Alibaba",
        "sector": "港股科技/电商/云",
        "type": "港股",
        "aliases": ["09988", "BABA", "ALIBABA", "阿里"],
        "website": "https://www.alibabagroup.com/",
        "summary_zh": "阿里巴巴是电商、云计算、物流和本地服务平台公司。跟踪重点包括中国消费、电商竞争、阿里云和AI商业化、国际业务增长及股东回报。",
    },
    "1810.HK": {
        "symbol": "1810.HK",
        "name": "小米集团 Xiaomi",
        "sector": "港股科技/硬件/汽车",
        "type": "港股",
        "aliases": ["01810", "XIAOMI", "小米"],
        "website": "https://www.mi.com/",
        "summary_zh": "小米集团覆盖智能手机、IoT、互联网服务和智能电动车。跟踪重点包括手机出货、汽车交付、毛利率、供应链和新品周期。",
    },
    "3690.HK": {
        "symbol": "3690.HK",
        "name": "美团 Meituan",
        "sector": "港股科技/本地生活",
        "type": "港股",
        "aliases": ["03690", "MEITUAN", "美团"],
        "website": "https://www.meituan.com/",
        "summary_zh": "美团是中国本地生活平台，业务包括外卖、到店酒旅、即时零售和新业务。跟踪重点包括竞争补贴、利润率、消费恢复和即时配送网络。",
    },
    "9618.HK": {
        "symbol": "9618.HK",
        "name": "京东集团 JD.com",
        "sector": "港股科技/电商",
        "type": "港股",
        "aliases": ["09618", "JD", "京东"],
        "website": "https://www.jd.com/",
        "summary_zh": "京东集团是中国电商和供应链平台，业务包括零售、物流和技术服务。跟踪重点包括消费电子需求、价格竞争、物流利润率和股东回报。",
    },
}

SECTOR_ZH = {
    "Technology": "科技",
    "Consumer Cyclical": "可选消费",
    "Communication Services": "通信服务",
    "Financial Services": "金融服务",
    "Healthcare": "医疗健康",
    "Industrials": "工业",
    "Energy": "能源",
    "Basic Materials": "原材料",
    "Real Estate": "房地产",
    "Utilities": "公用事业",
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

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def _market_for_symbol(symbol: str) -> str:
    if symbol.endswith(".HK"):
        return "港股"
    if symbol.endswith(".SS") or symbol.endswith(".SZ"):
        return "A股"
    if symbol.endswith(".T"):
        return "日股"
    if symbol.startswith("^"):
        return "指数"
    if symbol.endswith("-USD"):
        return "加密资产"
    if symbol.endswith("=F"):
        return "大宗商品"
    return "美股"

def _hkex_code(symbol: str) -> str:
    if symbol.endswith(".HK"):
        return symbol[:-3].zfill(5)
    return symbol

def _default_links(symbol: str, website: str | None = None) -> dict:
    sym = symbol.upper()
    if sym.endswith(".HK"):
        code = _hkex_code(sym)
        return {
            "website": website or "",
            "ir_url": website or f"https://www.hkexnews.hk/search/titlesearch.xhtml?lang=zh&market=SEHK&stockCode={code}",
            "filings_url": f"https://www.hkexnews.hk/search/titlesearch.xhtml?lang=zh&market=SEHK&stockCode={code}",
            "financials_url": f"https://finance.yahoo.com/quote/{quote_plus(sym)}/financials",
        }
    if "." not in sym and not sym.startswith("^") and not sym.endswith("-USD") and not sym.endswith("=F"):
        return {
            "website": website or "",
            "ir_url": website or f"https://finance.yahoo.com/quote/{quote_plus(sym)}/profile",
            "filings_url": f"https://www.sec.gov/edgar/search/#/q={quote_plus(sym)}",
            "financials_url": f"https://finance.yahoo.com/quote/{quote_plus(sym)}/financials",
        }
    return {
        "website": website or "",
        "ir_url": website or "",
        "filings_url": "",
        "financials_url": f"https://finance.yahoo.com/quote/{quote_plus(sym)}",
    }

def _summary_zh(name: str, sector: str | None, industry: str | None, summary: str | None) -> str:
    if summary:
        text = summary.strip()
        if any("\u4e00" <= ch <= "\u9fff" for ch in text):
            return text[:420]
    parts = []
    if name:
        parts.append(f"{name} 是一家上市公司")
    if sector:
        parts.append(f"所属板块：{SECTOR_ZH.get(sector, sector)}")
    if industry:
        parts.append(f"细分行业：{industry}")
    if not parts:
        return "暂未获取到完整公司简介。可以先从官网、投资者关系页面、财报和最近新闻确认主营业务、盈利模式、竞争格局和近期催化。"
    return "，".join(parts) + "。建议重点查看主营业务、收入结构、最近财报、管理层指引、上下游产业链和重大新闻。"

def _cached_profile(symbol: str, max_age_days: int = 7) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM company_profiles WHERE symbol = ?", (symbol,)).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    data = dict(row)
    fetched = data.get("fetched_at")
    if not fetched:
        return data
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(fetched.replace("Z", "+00:00"))
        if age.days <= max_age_days:
            data["cache_status"] = "fresh"
        else:
            data["cache_status"] = "stale"
    except Exception:
        data["cache_status"] = "unknown"
    return data

def _save_profile(profile: dict) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO company_profiles
               (symbol, name, name_zh, market, sector, industry, website, ir_url, filings_url,
                financials_url, country, currency, employees, summary, summary_zh, source, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(symbol) DO UPDATE SET
                 name = excluded.name,
                 name_zh = excluded.name_zh,
                 market = excluded.market,
                 sector = excluded.sector,
                 industry = excluded.industry,
                 website = excluded.website,
                 ir_url = excluded.ir_url,
                 filings_url = excluded.filings_url,
                 financials_url = excluded.financials_url,
                 country = excluded.country,
                 currency = excluded.currency,
                 employees = excluded.employees,
                 summary = excluded.summary,
                 summary_zh = excluded.summary_zh,
                 source = excluded.source,
                 fetched_at = excluded.fetched_at""",
            (
                profile.get("symbol"), profile.get("name"), profile.get("name_zh"), profile.get("market"),
                profile.get("sector"), profile.get("industry"), profile.get("website"), profile.get("ir_url"),
                profile.get("filings_url"), profile.get("financials_url"), profile.get("country"),
                profile.get("currency"), profile.get("employees"), profile.get("summary"),
                profile.get("summary_zh"), profile.get("source"), profile.get("fetched_at"),
            ),
        )
        conn.commit()
    finally:
        conn.close()

def _recent_news_snapshot(symbol: str, limit: int = 6) -> dict:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT nr.id, nr.title, nr.description, nr.publisher, nr.published_utc, nr.article_url, nr.image_url,
                      l1.sentiment, l1.chinese_summary
               FROM news_ticker nt
               JOIN news_raw nr ON nr.id = nt.news_id
               LEFT JOIN layer1_results l1 ON l1.news_id = nt.news_id AND l1.symbol = nt.symbol
               WHERE nt.symbol = ?
               ORDER BY nr.published_utc DESC
               LIMIT ?""",
            (symbol, limit),
        ).fetchall()
        meta = conn.execute(
            "SELECT last_news_fetch, last_ohlc_fetch FROM tickers WHERE symbol = ?",
            (symbol,),
        ).fetchone()
    finally:
        conn.close()
    return {
        "last_news_fetch": meta["last_news_fetch"] if meta else None,
        "last_ohlc_fetch": meta["last_ohlc_fetch"] if meta else None,
        "items": [dict(row) for row in rows],
    }

def _build_profile(symbol: str, refresh: bool = False) -> dict:
    normalized = normalize_symbol(symbol)
    cached = _cached_profile(normalized)
    if cached and cached.get("cache_status") == "fresh" and not refresh:
        profile = cached
    else:
        curated = CURATED_SECURITIES.get(normalized, {})
        info = {}
        source = "curated"
        try:
            import yfinance as yf
            info = yf.Ticker(normalized).info or {}
            if info:
                source = "yfinance"
        except Exception:
            info = {}
        name = curated.get("name") or info.get("longName") or info.get("shortName") or normalized
        sector = curated.get("sector") or info.get("sector")
        industry = info.get("industry")
        website = curated.get("website") or info.get("website") or ""
        summary = info.get("longBusinessSummary") or ""
        links = _default_links(normalized, website)
        profile = {
            "symbol": normalized,
            "name": name,
            "name_zh": curated.get("name") or name,
            "market": _market_for_symbol(normalized),
            "sector": sector,
            "industry": industry,
            "website": links["website"],
            "ir_url": links["ir_url"],
            "filings_url": links["filings_url"],
            "financials_url": links["financials_url"],
            "country": info.get("country"),
            "currency": info.get("currency"),
            "employees": info.get("fullTimeEmployees"),
            "summary": summary,
            "summary_zh": curated.get("summary_zh") or _summary_zh(name, sector, industry, summary),
            "source": source,
            "fetched_at": _now_iso(),
            "cache_status": "refreshed" if refresh else "fresh",
        }
        _save_profile(profile)
    news = _recent_news_snapshot(normalized)
    profile["links"] = {
        "官网": profile.get("website") or "",
        "投资者关系": profile.get("ir_url") or "",
        "公告/监管文件": profile.get("filings_url") or "",
        "财务报表": profile.get("financials_url") or "",
    }
    profile["recent_news"] = news["items"]
    profile["data_status"] = {
        "last_news_fetch": news["last_news_fetch"],
        "last_ohlc_fetch": news["last_ohlc_fetch"],
        "profile_cache": profile.get("cache_status"),
        "cache_policy": "公司资料缓存7天；新闻按标的按需抓取，只保存标题、摘要、链接、来源、时间和分析结果，不保存正文全文。",
        "refresh_hint": "新搜索或加入Tracking后会触发后台抓取；后续可做定期清理和手动刷新。",
    }
    return profile

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

@router.get("/{symbol}/profile")
def get_company_profile(symbol: str, refresh: bool = Query(False)):
    normalized = normalize_symbol(symbol)
    if not normalized:
        raise HTTPException(status_code=400, detail="Symbol is required")
    return _build_profile(normalized, refresh=refresh)

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
