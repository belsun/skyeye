from fastapi import APIRouter
from datetime import datetime, timedelta

router = APIRouter()

EVENT_KEYWORDS = [
    ("产品发布", ["发布", "launch", "release", "model", "m3", "ai", "大模型", "新产品"], ["0100.HK", "0700.HK", "9988.HK", "NVDA"]),
    ("IPO/上市", ["ipo", "listing", "上市", "招股", "聆讯"], ["0388.HK", "6066.HK", "6618.HK", "0100.HK"]),
    ("政策监管", ["fed", "rate", "policy", "regulation", "tariff", "央行", "美联储", "政策", "监管", "关税"], ["^HSI", "^GSPC", "0700.HK", "AAPL"]),
    ("财报业绩", ["earnings", "revenue", "guidance", "财报", "业绩", "收入"], ["NVDA", "AMD", "0700.HK", "9988.HK"]),
    ("地缘/宏观", ["war", "ceasefire", "inflation", "yield", "geopolitical", "战争", "停火", "通胀", "收益率"], ["GC=F", "CL=F", "^HSI", "^GSPC"]),
]

def _article_date(article: dict) -> str:
    raw = article.get("published") or article.get("date") or ""
    return raw[:10] if raw else datetime.now().strftime("%Y-%m-%d")

def _event_from_article(article: dict) -> dict | None:
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
    for category, keywords, tickers in EVENT_KEYWORDS:
        if any(kw.lower() in text for kw in keywords):
            sentiment = article.get("sentiment") or "neutral"
            impact = "positive" if "positive" in sentiment else "negative" if "negative" in sentiment else "watch"
            return {
                "title": article.get("title") or category,
                "category": category,
                "date": _article_date(article),
                "impact": impact,
                "related_stocks": tickers,
                "summary": article.get("summary") or f"{category}相关事件，适合观察市场预期是否已经兑现。",
                "source": article.get("source") or "RSS",
                "url": article.get("url") or "",
                "watch_points": _watch_points_for_category(category),
            }
    return None

def _watch_points_for_category(category: str) -> list[str]:
    if "产品" in category:
        return ["发布前预期是否过热", "发布后用户/机构评价", "股价是否跌破发布前支撑", "竞品是否快速跟进"]
    if "IPO" in category:
        return ["孖展倍数", "暗盘表现", "首日换手", "禁售期与基石阵容"]
    if "政策" in category:
        return ["政策落地时间", "受益/受损产业链", "估值倍数变化", "资金流向"]
    if "财报" in category:
        return ["收入增速", "毛利率", "下季指引", "管理层口径"]
    return ["新闻热度", "价格反应", "成交量", "避险资产联动"]

def _generate_events():
    """Generate current events from RSS first, with a small product-release watch fallback."""
    today = datetime.now()
    events = [{
        "title": "MiniMax / 稀宇科技新模型与股价反馈跟踪",
        "category": "产品发布",
        "date": today.strftime("%Y-%m-%d"),
        "impact": "watch",
        "related_stocks": ["0100.HK", "0700.HK", "9988.HK", "NVDA"],
        "summary": "产品发布前的看好预期可能提前反映到股价；发布后如果市场认为兑现不及预期，短线容易转为止盈压力。",
        "source": "产品发布雷达",
        "url": "",
        "watch_points": _watch_points_for_category("产品发布"),
    }]
    try:
        from routers.geopolitical import fetch_all_news
        seen = {events[0]["title"]}
        for article in fetch_all_news()[:120]:
            event = _event_from_article(article)
            if not event or event["title"] in seen:
                continue
            seen.add(event["title"])
            events.append(event)
            if len(events) >= 10:
                break
    except Exception:
        pass
    return events

PRIVATE_AI_COMPANIES = [
    {"name": "OpenAI", "valuation": "$300B+", "sector": "AI/Foundation Models",
     "description": "GPT系列大模型开发商，ChatGPT运营方。AI行业风向标。",
     "related_public_stocks": ["MSFT", "NVDA", "GOOGL", "AMZN"],
     "impact_note": "OpenAI产品发布/融资直接影响AI板块估值和微软股价。",
     "search_query": "OpenAI GPT funding valuation"},
    {"name": "Anthropic", "valuation": "$60B+", "sector": "AI/Safety",
     "description": "Claude系列大模型开发商，AI安全领域领导者。Google/Amazon投资。",
     "related_public_stocks": ["GOOGL", "AMZN", "NVDA"],
     "impact_note": "Anthropic融资和产品影响AI竞争格局和云计算需求。",
     "search_query": "Anthropic Claude funding"},
    {"name": "xAI", "valuation": "$50B+", "sector": "AI",
     "description": "马斯克旗下AI公司，Grok大模型开发商。",
     "related_public_stocks": ["TSLA", "NVDA"],
     "impact_note": "xAI进展影响特斯拉AI叙事和GPU需求预期。",
     "search_query": "xAI Grok Elon Musk"},
    {"name": "Databricks", "valuation": "$43B+", "sector": "AI/Data",
     "description": "领先的数据湖仓平台，大数据+AI基础设施。",
     "related_public_stocks": ["SNOW", "MDB", "PLTR", "MSFT"],
     "impact_note": "Databricks估值影响数据基础设施板块。",
     "search_query": "Databricks data AI valuation"},
    {"name": "MiniMax / 稀宇科技", "valuation": "HK listed", "sector": "AI/Application Models",
     "description": "中国大模型与AI应用公司，港交所代码 00100，行情源通常显示为 0100.HK。",
     "related_public_stocks": ["0100.HK", "0700.HK", "9988.HK", "NVDA"],
     "impact_note": "MiniMax 产品发布和用户反馈会影响港股AI应用、算力和互联网平台叙事。",
     "search_query": "MiniMax M3 AI model Hong Kong stock 00100"},
    {"name": "Stripe", "valuation": "$65B+", "sector": "Fintech",
     "description": "全球最大在线支付平台之一，潜在IPO热门标的。",
     "related_public_stocks": ["SQ", "PYPL", "ADYEN.AS"],
     "impact_note": "Stripe IPO/估值动态影响金融科技板块情绪。",
     "search_query": "Stripe fintech IPO valuation"},
]

UPCOMING_IPOS = [
    {"name":"MiniMax / 稀宇科技","sector":"AI应用/大模型","expected_date":"已上市观察","valuation":"HKEX 00100 / 0100.HK","description":"重点观察产品发布前后预期兑现、成交量、锁定期和同赛道AI应用情绪","related_tickers":["0100.HK","0700.HK","9988.HK","NVDA"],"status":"上市后跟踪","watch_points":["M3/新模型用户反馈","成交量是否放大","发布后止盈压力","同赛道AI应用估值"]},
    {"name":"港股AI/硬科技新股","sector":"港股打新","expected_date":"滚动跟踪","valuation":"以招股书为准","description":"优先看港交所聆讯、基石投资人、孖展倍数和暗盘，避免只看热度","related_tickers":["0388.HK","6066.HK","6618.HK","0100.HK"],"status":"候选池","watch_points":["聆讯/招股书","孖展倍数","一手中签率","暗盘成交"]},
    {"name":"Stripe","sector":"金融科技","expected_date":"2026 Q3","valuation":"$65B+","description":"全球最大在线支付平台之一","related_tickers":["SQ","PYPL","ADYEN.AS"]},
    {"name":"Databricks","sector":"AI/数据","expected_date":"2026 H2","valuation":"$43B+","description":"领先的数据湖仓平台","related_tickers":["SNOW","MDB","PLTR"]},
    {"name":"Discord","sector":"社交/游戏","expected_date":"2026","valuation":"$15B+","description":"全球最大游戏社交平台","related_tickers":["RBLX","U","EA"]},
]

SUPPLY_CHAIN_THEMES = [
    {
        "theme": "AI算力与HBM",
        "trigger": "大模型迭代、GPU供给、云厂商资本开支",
        "upstream": ["HBM/DRAM", "先进封装", "EDA/IP", "半导体设备"],
        "midstream": ["GPU/ASIC", "服务器ODM", "液冷/电源"],
        "downstream": ["云计算", "企业AI应用", "数据中心REITs"],
        "hk_tickers": ["0981.HK", "0522.HK", "1347.HK", "0700.HK"],
        "us_tickers": ["NVDA", "AMD", "AVGO", "MU", "AMAT", "TSM", "ANET", "VRT"],
        "watch_signals": ["HBM价格", "云厂商CapEx", "CoWoS产能", "电力瓶颈"],
        "risk": "预期拥挤后，财报兑现不及预期会放大回撤。",
    },
    {
        "theme": "港股打新与新经济IPO",
        "trigger": "港股流动性改善、南向资金、热门新股招股",
        "upstream": ["券商投行", "交易所生态", "基石投资人"],
        "midstream": ["云SaaS", "生物科技", "消费科技"],
        "downstream": ["经纪平台", "财富管理", "指数ETF"],
        "hk_tickers": ["0388.HK", "6066.HK", "6618.HK", "0700.HK", "9988.HK"],
        "us_tickers": ["FUTU", "TIGR", "MS", "GS"],
        "watch_signals": ["孖展倍数", "一手中签率", "暗盘成交", "禁售期"],
        "risk": "利好在上市首日可能快速兑现，打新和二级配置要分开管理。",
    },
    {
        "theme": "AI应用与新模型发布",
        "trigger": "MiniMax M3、AI Agent、办公/视频/搜索应用更新",
        "upstream": ["大模型训练", "推理算力", "数据与版权"],
        "midstream": ["AI应用公司", "云服务", "模型路由"],
        "downstream": ["企业订阅", "内容生产", "营销/客服/办公"],
        "hk_tickers": ["0100.HK", "0700.HK", "9988.HK", "1810.HK"],
        "us_tickers": ["MSFT", "GOOGL", "AMZN", "NVDA"],
        "watch_signals": ["发布前涨幅", "发布后口碑", "App下载/留存", "推理成本"],
        "risk": "产品发布常出现预期兑现，短线要防止“发布即止盈”。",
    },
    {
        "theme": "机器人与自动驾驶",
        "trigger": "Robotaxi、端侧AI、工业机器人订单",
        "upstream": ["传感器", "激光雷达", "功率半导体", "精密减速器"],
        "midstream": ["整车平台", "机器人本体", "控制器"],
        "downstream": ["物流", "制造业自动化", "出行服务"],
        "hk_tickers": ["1211.HK", "0986.HK", "2015.HK"],
        "us_tickers": ["TSLA", "NVDA", "MBLY", "SYM", "LAZR"],
        "watch_signals": ["L2/L3渗透率", "Robotaxi里程", "传感器降本", "政策牌照"],
        "risk": "技术演示和商业化交付之间可能有较长时间差。",
    },
    {
        "theme": "加密与稳定币基础设施",
        "trigger": "ETF资金流、稳定币监管、链上交易量",
        "upstream": ["矿机/算力", "托管", "合规支付"],
        "midstream": ["交易所", "钱包", "Layer2"],
        "downstream": ["跨境支付", "金融科技", "资产管理"],
        "hk_tickers": ["0863.HK", "1611.HK"],
        "us_tickers": ["COIN", "MSTR", "HOOD", "SQ", "RIOT", "MARA"],
        "watch_signals": ["BTC ETF flow", "稳定币供应", "监管进度", "链上费用"],
        "risk": "波动和监管标题会直接影响估值倍数。",
    },
]

@router.get("/events")
def get_events():
    return {
        "events": _generate_events(),
        "ipos": UPCOMING_IPOS,
        "private_ai_companies": PRIVATE_AI_COMPANIES,
        "supply_chains": SUPPLY_CHAIN_THEMES,
    }


@router.get("/events/private-ai-news")
def get_private_ai_news():
    """Fetch latest news about high-valuation private AI companies."""
    from routers.geopolitical import fetch_news_for_symbol
    import threading
    all_news = {}
    results = {}

    def fetch_company(company):
        try:
            articles = fetch_news_for_symbol(company["search_query"])
            for a in articles[:10]:
                a["company"] = company["name"]
                a["valuation"] = company["valuation"]
                a["related_public_stocks"] = company["related_public_stocks"]
                a["impact_note"] = company["impact_note"]
            results[company["name"]] = articles[:10]
        except:
            results[company["name"]] = []

    threads = []
    for company in PRIVATE_AI_COMPANIES:
        t = threading.Thread(target=fetch_company, args=(company,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join(timeout=30)

    return {"companies": PRIVATE_AI_COMPANIES, "news": results}
