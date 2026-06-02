import time, math, random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter
import yfinance as yf
from routers.stocks import normalize_symbol

router = APIRouter()

HKT = timezone(timedelta(hours=8))

MARKETS = {
    "us": {"name": "美股", "flag": "🇺🇸", "tz_offset": -5,
        "sessions": [("04:00","09:30","盘前"),("09:30","16:00","交易中"),("16:00","20:00","盘后")],
        "indices": {"^GSPC":{"name":"标普500","en":"S&P 500","icon":"📊"},"^IXIC":{"name":"纳斯达克","en":"NASDAQ","icon":"💻"},
            "^DJI":{"name":"道琼斯","en":"Dow Jones","icon":"🏭"},"^RUT":{"name":"罗素2000","en":"Russell 2000","icon":"📈"},"^VIX":{"name":"恐慌指数","en":"VIX","icon":"😱"}},
        "stocks": {"NVDA":{"name":"英伟达","sector":"AI/半导体"},"AAPL":{"name":"苹果","sector":"消费电子"},"MSFT":{"name":"微软","sector":"云计算/AI"},
            "TSLA":{"name":"特斯拉","sector":"电动车"},"META":{"name":"Meta","sector":"社交/AI"},"AMZN":{"name":"亚马逊","sector":"电商/云"},
            "GOOGL":{"name":"谷歌","sector":"搜索/AI"},"AMD":{"name":"AMD","sector":"半导体"},"AVGO":{"name":"博通","sector":"半导体"},"PLTR":{"name":"Palantir","sector":"AI软件"}}},
    "hk": {"name": "港股", "flag": "🇭🇰", "tz_offset": 8,
        "sessions": [("09:00","09:30","竞价"),("09:30","12:00","早盘"),("13:00","16:00","午盘")],
        "indices": {"^HSI":{"name":"恒生指数","en":"Hang Seng","icon":"🏦"},"^HSTECH":{"name":"恒生科技","en":"HS Tech","icon":"💻"}},
        "stocks": {"0700.HK":{"name":"腾讯","sector":"科技"},"9988.HK":{"name":"阿里巴巴","sector":"电商"},"3690.HK":{"name":"美团","sector":"本地生活"},
            "9618.HK":{"name":"京东","sector":"电商"},"1810.HK":{"name":"小米","sector":"科技"},"9999.HK":{"name":"网易","sector":"游戏"},
            "9888.HK":{"name":"百度","sector":"AI"},"9961.HK":{"name":"携程","sector":"旅游"}}},
    "cn": {"name": "A股", "flag": "🇨🇳", "tz_offset": 8,
        "sessions": [("09:30","11:30","上午"),("13:00","15:00","下午")],
        "indices": {"000001.SS":{"name":"上证指数","en":"SSE","icon":"📈"},"399001.SZ":{"name":"深证成指","en":"SZSE","icon":"📊"},"000300.SS":{"name":"沪深300","en":"CSI 300","icon":"🏛️"}}},
    "jp": {"name": "日股", "flag": "🇯🇵", "tz_offset": 9,
        "sessions": [("09:00","11:30","早盘"),("12:30","15:00","午盘")],
        "indices": {"^N225":{"name":"日经225","en":"Nikkei 225","icon":"🗼"}}},
    "eu": {"name": "欧股", "flag": "🇪🇺", "tz_offset": 0,
        "sessions": [("08:00","16:30","交易中")],
        "indices": {"^FTSE":{"name":"富时100","en":"FTSE 100","icon":"🇬🇧"},"^GDAXI":{"name":"德国DAX","en":"DAX","icon":"🇩🇪"}}},
}

CRYPTO = {"BTC-USD":{"name":"比特币","en":"BTC","icon":"₿"},"ETH-USD":{"name":"以太坊","en":"ETH","icon":"Ξ"},
    "SOL-USD":{"name":"Solana","en":"SOL","icon":"🟣"},"BNB-USD":{"name":"BNB","en":"BNB","icon":"🟡"},
    "XRP-USD":{"name":"瑞波","en":"XRP","icon":"✕"},"DOGE-USD":{"name":"狗狗币","en":"DOGE","icon":"🐕"}}

COMMODITIES = {"GC=F":{"name":"黄金","en":"Gold","icon":"🥇"},"SI=F":{"name":"白银","en":"Silver","icon":"🥈"},
    "CL=F":{"name":"WTI原油","en":"Crude Oil","icon":"🛢️"},"BZ=F":{"name":"布伦特原油","en":"Brent","icon":"🛢️"},
    "NG=F":{"name":"天然气","en":"Nat Gas","icon":"🔥"},"HG=F":{"name":"铜","en":"Copper","icon":"🟤"}}

SECTORS = {
    "XLK":{"name":"科技","en":"Technology","icon":"💻","color":"#6366f1","desc":"AI/云计算/软件驱动","drivers":["AI资本支出周期","企业数字化转型","消费电子复苏"],"risks":["估值过高回调","反垄断监管","地缘科技脱钩"],"stocks":["NVDA","AAPL","MSFT","AVGO","CRM"]},
    "XLV":{"name":"医疗","en":"Healthcare","icon":"🏥","color":"#22c55e","desc":"防御性板块，GLP-1减肥药驱动","drivers":["GLP-1药物爆发","老龄化趋势"],"risks":["药品降价政策","专利悬崖"],"stocks":["LLY","UNH","JNJ","ABBV","MRK"]},
    "XLF":{"name":"金融","en":"Financials","icon":"🏦","color":"#eab308","desc":"利率敏感","drivers":["净息差收益","资本市场回暖"],"risks":["信贷质量恶化","监管收紧"],"stocks":["BRK-B","JPM","V","MA","GS"]},
    "XLE":{"name":"能源","en":"Energy","icon":"⛽","color":"#f97316","desc":"周期性强","drivers":["OPEC+减产","地缘冲突溢价"],"risks":["需求衰退","页岩油增产"],"stocks":["XOM","CVX","COP","SLB","EOG"]},
    "XLY":{"name":"可选消费","en":"Cons Disc","icon":"🛍️","color":"#ec4899","desc":"经济景气度指标","drivers":["消费韧性","电商渗透率"],"risks":["消费者信心下滑"],"stocks":["AMZN","TSLA","HD","MCD","NKE"]},
    "XLI":{"name":"工业","en":"Industrials","icon":"🏭","color":"#14b8a6","desc":"基建+国防+制造","drivers":["基建法案落地","国防预算增长"],"risks":["经济周期下行"],"stocks":["CAT","HON","UNP","RTX","DE"]},
    "XLU":{"name":"公用事业","en":"Utilities","icon":"💡","color":"#06b6d4","desc":"高股息防御","drivers":["AI用电需求","降息预期"],"risks":["利率上行压力"],"stocks":["NEE","DUK","SO","D","AEP"]},
    "XLB":{"name":"材料","en":"Materials","icon":"⛏️","color":"#8b5cf6","desc":"大宗商品敏感","drivers":["中国需求复苏","绿色转型材料"],"risks":["需求不及预期"],"stocks":["LIN","APD","ECL","FCX","NEM"]},
    "XLRE":{"name":"房地产","en":"Real Estate","icon":"🏠","color":"#a855f7","desc":"利率敏感REITs","drivers":["降息预期","数据中心需求"],"risks":["利率上行"],"stocks":["PLD","AMT","CCI","EQIX","SPG"]},
    "XLC":{"name":"通讯","en":"Comms","icon":"📱","color":"#f43f5e","desc":"社交媒体+电信","drivers":["广告复苏","AI变现"],"risks":["监管审查"],"stocks":["META","GOOGL","NFLX","TMUS","DIS"]},
}

_cache = {}
def _cached(key, ttl=120):
    if key in _cache:
        v, t = _cache[key]
        if time.time() - t < ttl: return v
    return None
def _set_cache(key, val, ttl=120):
    _cache[key] = (val, time.time())

def _fetch_single(sym):
    """Fetch a single symbol's price data from yfinance."""
    try:
        tk = yf.Ticker(sym)
        info = tk.fast_info
        price = getattr(info, 'last_price', None) or 0
        prev = getattr(info, 'previous_close', None) or price
        if math.isnan(price) or math.isnan(prev) or price == 0:
            return sym, {"price": 0, "change": 0, "change_pct": 0}
        chg = price - prev
        pct = (chg / prev * 100) if prev else 0
        return sym, {"price": round(price, 2), "change": round(chg, 2), "change_pct": round(pct, 2)}
    except:
        return sym, {"price": 0, "change": 0, "change_pct": 0}

def _safe_yf(symbols):
    ck = f"yf_{hash(tuple(sorted(symbols)))}"
    c = _cached(ck)
    if c: return c
    res = {}
    # Concurrent fetching with thread pool
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_fetch_single, sym): sym for sym in symbols}
        for future in as_completed(futures):
            sym, data = future.result()
            res[sym] = data
    _set_cache(ck, res, ttl=120)
    return res

def get_market_status(key):
    m = MARKETS.get(key, {})
    if not m: return {"status": "unknown"}
    now = datetime.now(timezone.utc) + timedelta(hours=m.get("tz_offset", 0))
    if now.weekday() >= 5:
        days_until_monday = (7 - now.weekday()) % 7
        if days_until_monday == 0: days_until_monday = 1
        return {"status": "weekend", "label": "周末休市", "time": now.strftime("%H:%M"), "next": "周一开盘"}
    ct = now.strftime("%H:%M")
    for s, e, label in m.get("sessions", []):
        if s <= ct < e:
            left = (int(e.split(":")[0])*60+int(e.split(":")[1])) - (int(ct.split(":")[0])*60+int(ct.split(":")[1]))
            return {"status": "open", "label": label, "time": ct, "closes": e, "minutes_left": left, "next": f"收盘 {e}"}
    for s, e, label in m.get("sessions", []):
        if ct < s:
            left = (int(s.split(":")[0])*60+int(s.split(":")[1])) - (int(ct.split(":")[0])*60+int(ct.split(":")[1]))
            return {"status": "closed", "label": "已收盘", "time": ct, "next": f"{label} {s}开盘", "minutes_until": left}
    return {"status": "closed", "label": "已收盘", "time": ct, "next": "明日开盘"}

def _build_market_data(symbols_dict):
    syms = list(symbols_dict.keys())
    prices = _safe_yf(syms)
    result = []
    for sym, info in symbols_dict.items():
        p = prices.get(sym, {"price": 0, "change": 0, "change_pct": 0})
        result.append({"symbol": sym, "name": info.get("name", sym), "en": info.get("en", ""),
            "icon": info.get("icon", ""), "price": p["price"], "change": p["change"],
            "change_pct": p["change_pct"], "sector": info.get("sector", ""), "homepage": info.get("homepage", "")})
    return result

@router.get("/market-overview")
def market_overview():
    # Check top-level cache first
    ck = "market_overview_all"
    c = _cached(ck, ttl=120)
    if c: return c
    # Concurrently fetch all market data groups
    _all_symbols = {"crypto": CRYPTO, "commodities": COMMODITIES}
    for mk, mc in MARKETS.items():
        _all_symbols[f"{mk}_indices"] = mc["indices"]
        _all_symbols[f"{mk}_stocks"] = mc.get("stocks", {})
    # Fetch all in parallel by merging into one batch
    merged = {}
    for group, syms_dict in _all_symbols.items():
        for sym, info in syms_dict.items():
            merged[sym] = info
    all_prices = _safe_yf(list(merged.keys()))
    # Build response from cached prices
    def _build_from_prices(syms_dict):
        result = []
        for sym, info in syms_dict.items():
            p = all_prices.get(sym, {"price": 0, "change": 0, "change_pct": 0})
            result.append({"symbol": sym, "name": info.get("name", sym), "en": info.get("en", ""),
                "icon": info.get("icon", ""), "price": p["price"], "change": p["change"],
                "change_pct": p["change_pct"], "sector": info.get("sector", ""), "homepage": info.get("homepage", "")})
        return result
    data = {"markets": {}, "crypto": _build_from_prices(CRYPTO), "commodities": _build_from_prices(COMMODITIES)}
    for mk, mc in MARKETS.items():
        data["markets"][mk] = {"name": mc["name"], "flag": mc["flag"],
            "indices": _build_from_prices(mc["indices"]),
            "stocks": _build_from_prices(mc.get("stocks", {})),
            "status": get_market_status(mk)}
    _set_cache(ck, data, ttl=120)
    return data

@router.get("/market/{key}")
def market_detail(key: str):
    mc = MARKETS.get(key, {})
    return {"indices": _build_market_data(mc.get("indices", {})),
        "stocks": _build_market_data(mc.get("stocks", {})),
        "status": get_market_status(key),
        "sectors": _build_market_data(SECTORS) if key == "us" else None}

@router.get("/sectors")
def sectors():
    ck = "sectors_overview"
    c = _cached(ck, ttl=120)
    if c: return c
    # Build stock names lookup
    _stock_names = {}
    for mk, mc in MARKETS.items():
        for sym, info in mc.get("stocks", {}).items():
            _stock_names[sym] = info.get("name", sym)
    _sector_stock_names = {
        "LLY": "礼来", "UNH": "联合健康", "JNJ": "强生", "ABBV": "艾伯维", "MRK": "默沙东",
        "BRK-B": "伯克希尔", "JPM": "摩根大通", "V": "Visa", "MA": "万事达", "GS": "高盛",
        "XOM": "埃克森美孚", "CVX": "雪佛龙", "COP": "康菲石油", "SLB": "斯伦贝谢", "EOG": "EOG能源",
        "HD": "家得宝", "MCD": "麦当劳", "NKE": "耐克",
        "CAT": "卡特彼勒", "HON": "霍尼韦尔", "UNP": "联合太平洋", "RTX": "雷神", "DE": "迪尔",
        "NEE": "新纪元能源", "DUK": "杜克能源", "SO": "南方电力", "D": "道明尼", "AEP": "美国电力",
        "LIN": "林德", "APD": "空气化工", "ECL": "艺康", "FCX": "自由港铜金", "NEM": "纽蒙特矿业",
        "PLD": "安博", "AMT": "美国电塔", "CCI": "冠城国际", "EQIX": "Equinix", "SPG": "西蒙地产",
        "NFLX": "奈飞", "TMUS": "T-Mobile", "DIS": "迪士尼",
        "CRM": "Salesforce", "LMT": "洛克希德马丁", "NOC": "诺斯罗普格鲁曼",
    }
    _stock_names.update(_sector_stock_names)
    # Fetch all sector ETFs + their stocks in one batch
    all_syms = list(SECTORS.keys())
    for s in SECTORS.values():
        all_syms.extend(s["stocks"])
    all_prices = _safe_yf(all_syms)
    result = []
    for sym, info in SECTORS.items():
        p = all_prices.get(sym, {"price": 0, "change": 0, "change_pct": 0})
        # Find leader stock (first in list = highest market cap)
        leader_sym = info["stocks"][0] if info["stocks"] else None
        leader = None
        if leader_sym:
            lp = all_prices.get(leader_sym, {"price": 0, "change": 0, "change_pct": 0})
            leader = {"symbol": leader_sym, "name": _stock_names.get(leader_sym, leader_sym),
                "price": lp["price"], "change": lp["change"], "change_pct": lp["change_pct"]}
        result.append({"symbol": sym, "name": info.get("name", sym), "en": info.get("en", ""),
            "icon": info.get("icon", ""), "price": p["price"], "change": p["change"],
            "change_pct": p["change_pct"], "color": info.get("color", ""), "desc": info.get("desc", ""),
            "leader": leader})
    _set_cache(ck, result, ttl=120)
    return result

@router.get("/sector/{key}")
def sector_detail(key: str):
    s = SECTORS.get(key)
    if not s: return {"error": "not found"}
    base_scores = {"XLK":75,"XLV":70,"XLF":60,"XLE":55,"XLY":65,"XLI":62,"XLU":58,"XLB":50,"XLRE":45,"XLC":68}
    base = base_scores.get(key, 55)
    random.seed(int(time.time()/3600) + hash(key))
    st = max(20, min(95, base + random.randint(-15, 15)))
    mt = max(20, min(95, base + random.randint(-10, 20)))
    lt = max(20, min(95, base + random.randint(-5, 25)))
    views = {20:"偏空观望",35:"中性偏空",50:"中性",65:"中性偏多",80:"看好",90:"非常看好"}
    def gv(sc):
        for t in sorted(views.keys(), reverse=True):
            if sc >= t: return views[t]
        return "谨慎"
    sa = {"XLK":{"st":"AI算力需求强劲但估值偏高","mt":"AI资本支出周期远未结束","lt":"数字化+AI双重驱动"},
        "XLV":{"st":"GLP-1药物审批催化","mt":"减肥药市场爆发","lt":"老龄化不可逆趋势"},
        "XLF":{"st":"利率见顶预期压制","mt":"资本市场回暖利好投行","lt":"金融科技创新"},
        "XLE":{"st":"地缘溢价消退","mt":"OPEC+减产支撑","lt":"能源转型过渡期"},
        "XLY":{"st":"消费者信心波动","mt":"电商+高端消费韧性","lt":"消费升级趋势"},
        "XLI":{"st":"制造业PMI波动","mt":"基建法案落地","lt":"自动化+供应链重组"},
        "XLU":{"st":"利率上行压力","mt":"降息预期利好","lt":"电气化+AI用电"},
        "XLB":{"st":"中国需求疲软","mt":"供应链重组","lt":"绿色转型材料"},
        "XLRE":{"st":"利率高位压制","mt":"降息周期利好","lt":"数据中心REITs"},
        "XLC":{"st":"广告复苏放缓","mt":"AI变现加速","lt":"数字化生活"}}
    a = sa.get(key, {"st":"稳定","mt":"中性","lt":"待观察"})
    # Build a lookup of stock names from MARKETS
    _stock_names = {}
    for mk, mc in MARKETS.items():
        for sym, info in mc.get("stocks", {}).items():
            _stock_names[sym] = info.get("name", sym)
    # Add sector stock names not in MARKETS
    _sector_stock_names = {
        "LLY": "礼来", "UNH": "联合健康", "JNJ": "强生", "ABBV": "艾伯维", "MRK": "默沙东",
        "BRK-B": "伯克希尔", "JPM": "摩根大通", "V": "Visa", "MA": "万事达", "GS": "高盛",
        "XOM": "埃克森美孚", "CVX": "雪佛龙", "COP": "康菲石油", "SLB": "斯伦贝谢", "EOG": "EOG能源",
        "HD": "家得宝", "MCD": "麦当劳", "NKE": "耐克",
        "CAT": "卡特彼勒", "HON": "霍尼韦尔", "UNP": "联合太平洋", "RTX": "雷神", "DE": "迪尔",
        "NEE": "新纪元能源", "DUK": "杜克能源", "SO": "南方电力", "D": "道明尼", "AEP": "美国电力",
        "LIN": "林德", "APD": "空气化工", "ECL": "艺康", "FCX": "自由港铜金", "NEM": "纽蒙特矿业",
        "PLD": "安博", "AMT": "美国电塔", "CCI": "冠城国际", "EQIX": "Equinix", "SPG": "西蒙地产",
        "NFLX": "奈飞", "TMUS": "T-Mobile", "DIS": "迪士尼",
        "CRM": "Salesforce", "LMT": "洛克希德马丁", "NOC": "诺斯罗普格鲁曼",
    }
    _stock_names.update(_sector_stock_names)
    stock_data = _safe_yf(s["stocks"])
    stock_perf = []
    for sym in s["stocks"]:
        p = stock_data.get(sym, {"price": 0, "change": 0, "change_pct": 0})
        stock_perf.append({"symbol": sym, "name": _stock_names.get(sym, sym), "price": p["price"], "change": p["change"], "change_pct": p["change_pct"]})
    return {"key": key, "name": s["name"], "en": s["en"], "icon": s["icon"], "color": s["color"], "desc": s["desc"],
        "outlook": {"short_term": {"period":"1-4周","view":gv(st),"score":st,"reason":a["st"]},
            "medium_term": {"period":"1-6月","view":gv(mt),"score":mt,"reason":a["mt"]},
            "long_term": {"period":"1年+","view":gv(lt),"score":lt,"reason":a["lt"]}},
        "drivers": s["drivers"], "risks": s["risks"], "stocks": s["stocks"],
        "stock_performance": stock_perf,
        "last_updated": datetime.now(HKT).strftime("%Y-%m-%d %H:%M")}

@router.get("/market-status")
def market_status():
    return {k: get_market_status(k) for k in MARKETS}

@router.get("/kline/{symbol}")
def kline(symbol: str, period: str = "1mo"):
    symbol = normalize_symbol(symbol)
    try:
        period_map = {"1d":"1d","5d":"5d","1mo":"1mo","3mo":"3mo","1y":"1y","5y":"5y"}
        interval_map = {"1d":"5m","5d":"15m","1mo":"1d","3mo":"1d","1y":"1wk","5y":"1mo"}
        tk = yf.Ticker(symbol)
        hist = tk.history(period=period_map.get(period, "1mo"), interval=interval_map.get(period, "1d"))
        data = []
        if not hist.empty:
            for date, row in hist.iterrows():
                ts = date.strftime("%Y-%m-%d") if interval_map.get(period, "1d") in ("1d","1wk","1mo") else date.strftime("%Y-%m-%d %H:%M")
                o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
                vol = float(row.get("Volume", 0) or 0)
                if math.isnan(o) or math.isnan(h) or math.isnan(l) or math.isnan(c): continue
                if math.isnan(vol): vol = 0
                data.append({"date": ts, "open": round(o,2), "high": round(h,2), "low": round(l,2), "close": round(c,2), "volume": int(vol)})
        if not data:
            from database import get_conn
            conn = get_conn()
            try:
                rows = conn.execute(
                    """SELECT date, open, high, low, close, volume
                       FROM ohlc
                       WHERE symbol = ?
                       ORDER BY date DESC
                       LIMIT 120""",
                    (symbol,),
                ).fetchall()
            finally:
                conn.close()
            data = [
                {"date": row["date"], "open": row["open"], "high": row["high"], "low": row["low"], "close": row["close"], "volume": int(row["volume"] or 0)}
                for row in reversed(rows)
            ]
            return {"symbol": symbol, "period": period, "data": data, "source": "database" if data else "empty"}
        return {"symbol": symbol, "period": period, "data": data, "source": "yfinance"}
    except Exception as e:
        try:
            from database import get_conn
            conn = get_conn()
            rows = conn.execute(
                """SELECT date, open, high, low, close, volume
                   FROM ohlc
                   WHERE symbol = ?
                   ORDER BY date DESC
                   LIMIT 120""",
                (symbol,),
            ).fetchall()
            conn.close()
            data = [
                {"date": row["date"], "open": row["open"], "high": row["high"], "low": row["low"], "close": row["close"], "volume": int(row["volume"] or 0)}
                for row in reversed(rows)
            ]
            if data:
                return {"symbol": symbol, "period": period, "data": data, "source": "database", "warning": str(e)}
        except Exception:
            pass
        return {"symbol": symbol, "period": period, "data": [], "source": "error", "error": str(e)}
