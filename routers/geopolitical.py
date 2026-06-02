import re, threading, time
from datetime import datetime, timedelta, timezone
from calendar import timegm
from collections import defaultdict
from fastapi import APIRouter
import feedparser

router = APIRouter()

NEWS_FEEDS = [
    {"url":"https://news.google.com/rss/search?q=%E8%82%A1%E5%B8%82&hl=zh-CN&gl=CN&ceid=CN:zh-Hans","source":"Google(股市)","lang":"zh","category":"breaking"},
    {"url":"https://news.google.com/rss/search?q=%E6%B8%AF%E8%82%A1+IPO+%E6%89%93%E6%96%B0&hl=zh-HK&gl=HK&ceid=HK:zh-Hant","source":"Google(港股IPO)","lang":"zh","category":"hk_ipo"},
    {"url":"https://news.google.com/rss/search?q=%E6%B8%AF%E8%82%A1+%E7%A7%91%E6%8A%80%E8%82%A1&hl=zh-HK&gl=HK&ceid=HK:zh-Hant","source":"Google(港股科技)","lang":"zh","category":"hk_stock"},
    {"url":"https://news.google.com/rss/search?q=AI+semiconductor+supply+chain+stocks&hl=en-US&gl=US&ceid=US:en","source":"Google(AI供应链)","lang":"en","category":"ai_supply_chain"},
    {"url":"https://feeds.bloomberg.com/markets/news.rss","source":"Bloomberg Markets","lang":"en","category":"market_authority"},
    {"url":"https://www.hkex.com.hk/Services/RSS-Feeds/News-Releases?sc_lang=zh-HK","source":"HKEX News","lang":"zh","category":"hk"},
    {"url":"https://www.federalreserve.gov/feeds/press_all.xml","source":"Federal Reserve","lang":"en","category":"central_bank"},
    {"url":"https://feeds.bbci.co.uk/news/business/rss.xml","source":"BBC Business","lang":"en","category":"global"},
    {"url":"https://www.cnbc.com/id/100003114/device/rss/rss.html","source":"CNBC","lang":"en","category":"us_stock"},
    {"url":"https://rss.nytimes.com/services/xml/rss/nyt/Business.xml","source":"NYT Business","lang":"en","category":"finance"},
    {"url":"https://finance.yahoo.com/news/rssindex","source":"Yahoo Finance","lang":"en","category":"us_stock"},
    {"url":"https://www.marketwatch.com/rss/marketpulse","source":"MarketWatch","lang":"en","category":"market_pulse"},
    {"url":"https://www.sec.gov/news/pressreleases.rss","source":"SEC","lang":"en","category":"policy_regulation"},
    {"url":"https://www.investing.com/rss/news.rss","source":"Investing.com","lang":"en","category":"global"},
    {"url":"https://cointelegraph.com/rss","source":"CoinTelegraph","lang":"en","category":"crypto"},
    {"url":"https://seekingalpha.com/market_currents.xml","source":"SeekingAlpha","lang":"en","category":"us_stock"},
    {"url":"https://36kr.com/feed","source":"36氪","lang":"zh","category":"tech"},
    {"url":"https://www.infoq.cn/feed","source":"InfoQ","lang":"zh","category":"tech"},
]

GEO_KW = {"贸易战":{"w":3,"cat":"trade"},"tariff":{"w":2,"cat":"trade"},"制裁":{"w":3,"cat":"sanctions"},"sanction":{"w":3,"cat":"sanctions"},
    "台海":{"w":4,"cat":"taiwan"},"Taiwan":{"w":4,"cat":"taiwan"},"乌克兰":{"w":3,"cat":"conflict"},"Ukraine":{"w":3,"cat":"conflict"},
    "美联储":{"w":3,"cat":"monetary"},"Fed":{"w":3,"cat":"monetary"},"加息":{"w":2,"cat":"monetary"},"降息":{"w":2,"cat":"monetary"},
    "recession":{"w":3,"cat":"economy"},"衰退":{"w":3,"cat":"economy"},"AI":{"w":2,"cat":"tech"},"人工智能":{"w":2,"cat":"tech"},
    "芯片":{"w":2,"cat":"tech"},"GPU":{"w":2,"cat":"tech"},"war":{"w":3,"cat":"danger"},"战争":{"w":3,"cat":"danger"}}

POS_WORDS = ["涨","利好","上涨","暴涨","突破","增长","复苏","强劲","创新高","新高","涨停","超预期","反弹","牛市","bull","bullish","surge","rally","gain","high","record","upgrade","beat","soar","optimistic","利多","走强","飙升","大涨"]
NEG_WORDS = ["跌","下跌","暴跌","崩盘","危机","泡沫","跌停","熊市","利空","跌破","新低","抛售","暴雷","不及预期","下滑","衰退","bear","bearish","crash","plunge","drop","downgrade","sell","recession","crisis","pessimistic","利空","走弱","大跌","重挫"]

NEWS_TAXONOMY = {
    "us": {"label": "美股", "terms": ["us stock", "nasdaq", "s&p", "dow jones", "wall street", "美股"]},
    "hk": {"label": "港股", "terms": ["港股", "恒生", "hang seng", "hk stock", "h shares", "h-share"]},
    "hk_ipo": {"label": "港股打新", "terms": ["港股ipo", "香港ipo", "港股打新", "打新", "招股", "聆讯", "通过聆讯", "港交所", "hkex", "hong kong ipo", "hong kong listing"]},
    "ipo": {"label": "IPO", "terms": ["ipo", "initial public offering", "上市", "招股"]},
    "macro": {"label": "宏观", "terms": ["gdp", "cpi", "inflation", "pmi", "unemployment", "recession", "通胀", "衰退", "失业", "经济"]},
    "central_bank": {"label": "央行政策", "terms": ["fed", "fomc", "美联储", "央行", "interest rate", "rate cut", "rate hike", "降息", "加息"]},
    "policy_regulation": {"label": "监管政策", "terms": ["sec", "regulation", "监管", "政策", "法案", "antitrust", "反垄断"]},
    "geopolitics": {"label": "地缘风险", "terms": ["war", "conflict", "sanction", "tariff", "台海", "制裁", "关税", "冲突"]},
    "ai": {"label": "AI", "terms": ["ai", "artificial intelligence", "人工智能", "大模型", "openai", "anthropic"]},
    "semiconductor": {"label": "半导体", "terms": ["semiconductor", "chip", "gpu", "hbm", "晶圆", "芯片", "光刻", "foundry"]},
    "supply_chain": {"label": "产业链", "terms": ["supply chain", "capacity", "bottleneck", "chokepoint", "订单", "产能", "瓶颈", "上游", "下游"]},
    "earnings": {"label": "财报", "terms": ["earnings", "revenue", "profit", "eps", "guidance", "财报", "业绩"]},
    "liquidity": {"label": "流动性", "terms": ["liquidity", "treasury", "yield", "美元", "汇率", "债券", "资金流"]},
    "crypto": {"label": "加密", "terms": ["bitcoin", "btc", "crypto", "ethereum", "加密", "区块链"]},
    "commodities": {"label": "大宗商品", "terms": ["oil", "gold", "copper", "crude", "原油", "黄金", "铜"]},
}

_cache: dict = {}
def _cached(key, ttl=300):
    if key in _cache:
        v, t = _cache[key]
        if time.time() - t < ttl: return v
    return None

def analyze_sentiment(text):
    t = text.lower()
    pos = sum(1 for w in POS_WORDS if w.lower() in t)
    neg = sum(1 for w in NEG_WORDS if w.lower() in t)
    if pos > neg+1: return "positive"
    elif neg > pos+1: return "negative"
    elif pos > neg: return "slightly_positive"
    elif neg > pos: return "slightly_negative"
    return "neutral"

def _append_tag(tags, key, value=None, typ="topic"):
    if any(t.get("key") == key for t in tags):
        return
    tags.append({"type": typ, "key": key, "value": value or NEWS_TAXONOMY.get(key, {}).get("label", key)})

def _taxonomy_tags(title: str, summary: str, feed_category: str = "") -> list:
    text = f"{title} {summary} {feed_category}".lower()
    tags = []
    for key, meta in NEWS_TAXONOMY.items():
        if key == feed_category or any(term.lower() in text for term in meta["terms"]):
            _append_tag(tags, key, meta["label"])
    if feed_category in {"us_stock", "market_authority", "market_pulse"}:
        _append_tag(tags, "us", "美股", "market")
    if feed_category in {"hk_stock", "hk_ipo"}:
        _append_tag(tags, "hk", "港股", "market")
    if feed_category == "crypto":
        _append_tag(tags, "crypto", "加密", "market")
    return tags

def _get_impact_tags(title: str, summary: str) -> list:
    """Classify news into impact types and tag affected sectors/assets."""
    text = f"{title} {summary}".lower()
    tags = []
    simple_tags = []
    # War/military → gold, defense stocks bullish
    if any(k in text for k in ["war", "战争", "军事", "military", "missile", "导弹", "troops", "武装", "冲突", "conflict", "invasion", "入侵"]):
        tags.append({"type": "war/military", "impact": "bullish", "sectors": ["gold", "defense"], "assets": ["GC=F", "LMT", "NOC", "RTX"]})
        if "conflict" not in simple_tags: simple_tags.append("conflict")
    # Trade/tariff → import/export bearish, domestic may benefit
    if any(k in text for k in ["tariff", "关税", "trade war", "贸易战", "制裁", "sanction", "import tax", "出口管制"]):
        tags.append({"type": "trade/tariff", "impact": "bearish", "sectors": ["import/export", "semiconductors", "tech"], "assets": ["NVDA", "AAPL", "AVGO"]})
        if "trade" not in simple_tags: simple_tags.append("trade")
        if any(k in text for k in ["制裁", "sanction"]) and "sanctions" not in simple_tags:
            simple_tags.append("sanctions")
    # Interest rate → bonds, banks, real estate
    if any(k in text for k in ["interest rate", "利率", "fed", "美联储", "加息", "降息", "rate cut", "rate hike", "fomc", "monetary policy"]):
        tags.append({"type": "interest_rate", "impact": "mixed", "sectors": ["bonds", "banks", "real_estate"], "assets": ["XLF", "XLRE", "TLT"]})
        if "monetary" not in simple_tags: simple_tags.append("monetary")
    # Oil/energy → energy stocks bullish, airlines bearish
    if any(k in text for k in ["oil", "原油", "opec", "crude", "petroleum", "天然气", "natural gas", "energy crisis"]):
        tags.append({"type": "oil/energy", "impact": "bullish", "sectors": ["energy"], "assets": ["XLE", "XOM", "CVX", "CL=F"]})
        tags.append({"type": "oil/energy", "impact": "bearish", "sectors": ["airlines", "transport"], "assets": ["DAL", "UAL", "AAL"]})
        if "economy" not in simple_tags: simple_tags.append("economy")
    # Technology → tech stocks
    if any(k in text for k in ["ai", "人工智能", "chip", "芯片", "gpu", "semiconductor", "nvidia", "openai", "anthropic", "cloud", "quantum"]):
        tags.append({"type": "technology", "impact": "bullish", "sectors": ["tech", "semiconductors", "ai"], "assets": ["XLK", "NVDA", "AMD", "MSFT"]})
        if "tech" not in simple_tags: simple_tags.append("tech")
    # Earnings
    if any(k in text for k in ["earnings", "财报", "revenue", "profit", "eps", "guidance", "beat", "miss"]):
        tags.append({"type": "earnings", "impact": "neutral", "sectors": ["individual_stock"], "assets": []})
    # Crypto
    if any(k in text for k in ["bitcoin", "btc", "crypto", "ethereum", "加密", "blockchain", "web3"]):
        tags.append({"type": "crypto", "impact": "neutral", "sectors": ["crypto"], "assets": ["BTC-USD", "ETH-USD"]})
    # Gold/precious metals
    if any(k in text for k in ["gold", "黄金", "silver", "白银", "precious metal", "贵金属"]):
        tags.append({"type": "precious_metals", "impact": "bullish", "sectors": ["precious_metals"], "assets": ["GC=F", "SI=F"]})
    # Taiwan
    if any(k in text for k in ["taiwan", "台海", "台湾", "tsmc", "台积电"]):
        if "taiwan" not in simple_tags: simple_tags.append("taiwan")
    # Danger/war escalation
    if any(k in text for k in ["war", "战争", "nuclear", "核", "escalation", "升级"]):
        if "danger" not in simple_tags: simple_tags.append("danger")
    # Recession/economy
    if any(k in text for k in ["recession", "衰退", "gdp", "unemployment", "失业", "inflation", "通胀"]):
        if "economy" not in simple_tags: simple_tags.append("economy")
    return {"detailed": tags, "simple": simple_tags}


def fetch_news_for_symbol(symbol: str) -> list:
    """Fetch news for any symbol using Google News RSS. Works for indices, crypto, commodities."""
    import urllib.parse
    # Create a search-friendly name for the symbol
    symbol_names = {
        "^GSPC": "S&P 500", "^IXIC": "NASDAQ", "^DJI": "Dow Jones",
        "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "SOL-USD": "Solana",
        "GC=F": "Gold price", "CL=F": "crude oil price", "SI=F": "silver price",
    }
    query = symbol_names.get(symbol, symbol)
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        articles = []
        for e in feed.entries[:20]:
            title = e.get("title", "")
            desc = re.sub(r'<[^>]+>', '', e.get("summary", e.get("description", "")))[:300]
            link = e.get("link", "")
            pub_dt = None
            pub_parsed = e.get("published_parsed") or e.get("updated_parsed")
            if pub_parsed:
                try: pub_dt = datetime.fromtimestamp(timegm(pub_parsed), tz=timezone.utc)
                except: pass
            if not pub_dt: pub_dt = datetime.now(timezone.utc)
            sentiment = analyze_sentiment(f"{title} {desc}")
            impact_tags = _get_impact_tags(title, desc)
            articles.append({
                "title": title, "summary": desc, "source": "Google News",
                "url": link, "published": pub_dt.isoformat(),
                "sentiment": sentiment, "impact_tags": impact_tags["simple"],
                "impact_details": impact_tags["detailed"],
                "symbol": symbol
            })
        return articles
    except:
        return []


def _fetch_rss(fc):
    try:
        feed = feedparser.parse(fc["url"])
        arts = []
        for e in feed.entries[:15]:
            title = e.get("title","")
            desc = re.sub(r'<[^>]+>','',e.get("summary",e.get("description","")))[:300]
            link = e.get("link","")
            pub_dt = None
            # Use feedparser's pre-parsed time tuples (most reliable)
            pub_parsed = e.get("published_parsed") or e.get("updated_parsed")
            if pub_parsed:
                try:
                    pub_dt = datetime.fromtimestamp(timegm(pub_parsed), tz=timezone.utc)
                except Exception:
                    pass
            # Fallback: parse the raw string
            if not pub_dt:
                pub = e.get("published","") or e.get("updated","")
                if pub:
                    try:
                        from email.utils import parsedate_to_datetime
                        pub_dt = parsedate_to_datetime(pub)
                    except Exception:
                        pass
            # Last resort: use current time
            if not pub_dt:
                pub_dt = datetime.now(timezone.utc)
            tags = _taxonomy_tags(title, desc, fc.get("category", ""))
            text = f"{title} {desc}".lower()
            sentiment = analyze_sentiment(f"{title} {desc}")
            impact_tags = _get_impact_tags(title, desc)
            for key in impact_tags["simple"]:
                mapped = {
                    "monetary": "central_bank",
                    "economy": "macro",
                    "tech": "ai",
                    "trade": "geopolitics",
                    "sanctions": "geopolitics",
                    "taiwan": "geopolitics",
                    "danger": "geopolitics",
                    "conflict": "geopolitics",
                }.get(key)
                if mapped:
                    _append_tag(tags, mapped)
            tags.append({"type":"source","key":fc["source"].lower().replace(" ","_"),"value":fc["source"]})
            arts.append({"title":title,"summary":desc,"source":fc["source"],"url":link,
                "published":pub_dt.isoformat(),"sentiment":sentiment,"tags":tags,
                "impact_tags": impact_tags["simple"], "impact_details": impact_tags["detailed"],
                "feed_category": fc.get("category", "")})
        return arts
    except: return []

def fetch_all_news():
    ck = "news_all"
    c = _cached(ck)
    if c: return c
    all_arts = []
    threads = []
    results = [None]*len(NEWS_FEEDS)
    def worker(i, fc): results[i] = _fetch_rss(fc)
    for i, fc in enumerate(NEWS_FEEDS):
        t = threading.Thread(target=worker, args=(i, fc))
        threads.append(t); t.start()
    for t in threads: t.join(timeout=20)
    for r in results:
        if r: all_arts.extend(r)
    all_arts.sort(key=lambda x: x["published"], reverse=True)
    _cache["news_all"] = (all_arts, time.time())
    return all_arts

@router.get("/news")
def get_news(sentiment: str = None, category: str = None, limit: int = 50):
    news = fetch_all_news()
    if sentiment: news = [n for n in news if sentiment in n["sentiment"]]
    if category:
        cat_lower = category.lower()
        def matches(article):
            if cat_lower == (article.get("feed_category") or "").lower():
                return True
            if cat_lower in [str(t).lower() for t in article.get("impact_tags", [])]:
                return True
            for tag in article.get("tags", []):
                values = [tag.get("key"), tag.get("type"), tag.get("value")]
                if any(cat_lower == str(v or "").lower() or cat_lower in str(v or "").lower() for v in values):
                    return True
            return False
        news = [n for n in news if matches(n)]
    return {"articles": news[:limit]}

@router.get("/geopolitical")
def geopolitical():
    news = fetch_all_news()
    scores = defaultdict(int)
    for art in news[:100]:
        txt = f"{art['title']} {art.get('summary','')}"
        for kw, info in GEO_KW.items():
            if kw.lower() in txt.lower():
                scores[info["cat"]] += info["w"]
    mx = max(scores.values()) if scores else 1
    norm = {k: min(10, round(v/mx*10,1)) for k,v in scores.items()}
    weights = {"trade":1.2,"sanctions":1.5,"taiwan":2.0,"conflict":2.0,"monetary":1.0,"economy":1.0,"tech":0.5,"danger":2.5}
    overall = sum(norm.get(k,0)*weights.get(k,1) for k in norm) / max(sum(weights.values()),1)
    cat_labels = {"trade":"贸易战⚔️","sanctions":"制裁🚫","taiwan":"台海局势🌊","conflict":"地缘冲突💥","monetary":"央行政策🏦","economy":"经济风险📉","tech":"科技竞争💡","danger":"军事风险🔴"}
    return {"overall": min(10, round(overall,1)), "categories": [{"key":k,"name":cat_labels.get(k,k),"score":norm.get(k,0)} for k in cat_labels]}

@router.get("/sentiment-trend")
def sentiment_trend():
    news = fetch_all_news()
    daily = {}
    for a in news[:200]:
        try: d = datetime.fromisoformat(a["published"]).date().isoformat()
        except: continue
        if d not in daily: daily[d] = {"positive":0,"negative":0,"neutral":0,"total":0}
        s = a["sentiment"]
        if s in ("positive","slightly_positive"): daily[d]["positive"] += 1
        elif s in ("negative","slightly_negative"): daily[d]["negative"] += 1
        else: daily[d]["neutral"] += 1
        daily[d]["total"] += 1
    result = []
    for i in range(7):
        d = (datetime.now()-timedelta(days=i)).date().isoformat()
        s = daily.get(d, {"positive":0,"negative":0,"neutral":0,"total":0})
        total = s["total"] or 1
        result.append({"date":d,"score":round((s["positive"]-s["negative"])/total,2),**s})
    result.reverse()
    return result

@router.get("/news/symbol/{symbol}")
def get_news_for_any_symbol(symbol: str, limit: int = 30):
    """Get news for any symbol (indices, crypto, commodities) via Google News RSS."""
    articles = fetch_news_for_symbol(symbol)
    return {"symbol": symbol, "articles": articles[:limit]}

@router.get("/trending")
def trending():
    news = fetch_all_news()
    kc = defaultdict(int)
    for a in news[:100]:
        for t in a.get("tags", []):
            if t.get("type") == "topic": kc[t["value"]] += 1
    topics = sorted(kc.items(), key=lambda x: x[1], reverse=True)[:15]
    return {"topics": [{"keyword":k,"mentions":c} for k,c in topics]}
