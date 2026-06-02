import re, threading, time, math
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query
from typing import Optional
import feedparser

router = APIRouter()

_cache = {}
def _cached(key, ttl=300):
    if key in _cache:
        v, t = _cache[key]
        if time.time() - t < ttl: return v
    return None
def _set_cache(key, val, ttl=300):
    _cache[key] = (val, time.time())

from polygon_client import polygon_stock_details
from routers.stocks import normalize_symbol

POS_WORDS = ["涨","利好","上涨","突破","增长","复苏","强劲","bull","bullish","surge","rally","gain","beat","soar","optimistic","upgrade"]
NEG_WORDS = ["跌","下跌","暴跌","崩盘","危机","泡沫","利空","抛售","暴雷","bear","bearish","crash","plunge","drop","downgrade","recession","crisis"]

def analyze_sentiment(text):
    t = text.lower()
    pos = sum(1 for w in POS_WORDS if w.lower() in t)
    neg = sum(1 for w in NEG_WORDS if w.lower() in t)
    if pos > neg+1: return "positive"
    elif neg > pos+1: return "negative"
    elif pos > neg: return "slightly_positive"
    elif neg > pos: return "slightly_negative"
    return "neutral"

CATEGORY_RULES = {
    "product_tech": {
        "label": "产品发布/技术迭代",
        "keywords": ["product","launch","release","model","m3","ai","chip","cloud","gpu","平台","发布","新产品","模型","大模型","技术","算力","芯片"],
        "watch": "看发布前预期是否过热、发布后用户/机构反馈、竞品跟进和股价是否跌破发布前支撑。",
    },
    "ipo_financing": {
        "label": "IPO/融资",
        "keywords": ["ipo","listing","funding","valuation","招股","上市","聆讯","融资","估值"],
        "watch": "分清打新热度和二级市场基本面，重点看孖展、暗盘、首日换手和禁售期。",
    },
    "policy": {
        "label": "政策/监管",
        "keywords": ["policy","regulation","sec","fed","tariff","sanction","rate","监管","政策","央行","美联储","降息","加息","关税","制裁"],
        "watch": "政策会先影响估值倍数，再影响业绩预期；留意细则、执行时间和受益/受损链条。",
    },
    "earnings": {
        "label": "财报/业绩",
        "keywords": ["earnings","revenue","profit","guidance","quarter","eps","财报","业绩","收入","利润","指引"],
        "watch": "看收入/利润是否超预期，以及管理层指引是否支持未来 1-2 个季度的估值。",
    },
    "competition": {
        "label": "竞争格局",
        "keywords": ["competitor","rival","competition","market share","vs","竞争","竞品","份额","价格战"],
        "watch": "竞争新闻常影响中期利润率，短线先看市场是否担心降价或份额流失。",
    },
    "macro_market": {
        "label": "宏观/市场情绪",
        "keywords": ["market","nasdaq","s&p","hang seng","yield","inflation","risk","流动性","恒生","纳指","通胀","收益率","风险偏好"],
        "watch": "宏观情绪决定仓位水位；同一条个股利好在弱市里可能只能带来反弹。",
    },
    "management": {
        "label": "管理层/组织",
        "keywords": ["ceo","executive","layoff","restructure","hire","管理层","裁员","重组","任命","组织"],
        "watch": "管理层变化要和战略执行一起看，短线容易被情绪放大。",
    },
}

def classify_news(row: dict) -> list[dict]:
    text = " ".join([
        str(row.get("title") or ""),
        str(row.get("description") or ""),
        str(row.get("key_discussion") or ""),
        str(row.get("reason_growth") or ""),
        str(row.get("reason_decrease") or ""),
    ]).lower()
    tags = []
    for key, rule in CATEGORY_RULES.items():
        if any(kw.lower() in text for kw in rule["keywords"]):
            tags.append({"key": key, "label": rule["label"]})
    if not tags:
        tags.append({"key": "macro_market", "label": CATEGORY_RULES["macro_market"]["label"]})
    return tags[:3]

def enrich_news_row(row) -> dict:
    item = dict(row)
    tags = classify_news(item)
    sentiment = item.get("sentiment") or "neutral"
    ret_t1 = item.get("ret_t1")
    ret_t5 = item.get("ret_t5")
    if sentiment in {"positive", "slightly_positive"}:
        label = "偏利好"
    elif sentiment in {"negative", "slightly_negative"}:
        label = "偏利空"
    else:
        label = "待观察"
    if ret_t1 is not None:
        move = float(ret_t1) * 100
        reaction = f"T+1 股价反应 {move:+.2f}%"
    elif ret_t5 is not None:
        move = float(ret_t5) * 100
        reaction = f"T+5 股价反应 {move:+.2f}%"
    else:
        reaction = "尚无足够历史反应数据"
    primary = tags[0]["key"]
    item["category_tags"] = tags
    item["impact_label"] = label
    item["impact_reason"] = f"{tags[0]['label']}新闻，当前文本情绪为{label}；{reaction}。"
    item["next_watch"] = CATEGORY_RULES.get(primary, CATEGORY_RULES["macro_market"])["watch"]
    return item

@router.get("/{symbol}")
def get_news_for_date(symbol: str, date: Optional[str] = None):
    from database import get_conn
    symbol = normalize_symbol(symbol)
    conn = get_conn()
    if date:
        rows = conn.execute(
            "SELECT na.news_id, na.trade_date, na.published_utc, na.ret_t0, na.ret_t1, na.ret_t3, na.ret_t5, na.ret_t10, "
            "nr.title, nr.description, nr.publisher, nr.article_url, nr.image_url, "
            "l1.relevance, l1.key_discussion, l1.chinese_summary, l1.sentiment, l1.reason_growth, l1.reason_decrease "
            "FROM news_aligned na JOIN news_raw nr ON na.news_id = nr.id "
            "LEFT JOIN layer1_results l1 ON na.news_id = l1.news_id AND l1.symbol = ? "
            "WHERE na.symbol = ? AND na.trade_date = ? ORDER BY na.published_utc DESC",
            (symbol, symbol, date)).fetchall()
    else:
        rows = conn.execute(
            "SELECT na.news_id, na.trade_date, na.published_utc, na.ret_t0, na.ret_t1, na.ret_t3, na.ret_t5, na.ret_t10, "
            "nr.title, nr.description, nr.publisher, nr.article_url, nr.image_url, "
            "l1.relevance, l1.key_discussion, l1.chinese_summary, l1.sentiment, l1.reason_growth, l1.reason_decrease "
            "FROM news_aligned na JOIN news_raw nr ON na.news_id = nr.id "
            "LEFT JOIN layer1_results l1 ON na.news_id = l1.news_id AND l1.symbol = ? "
            "WHERE na.symbol = ? ORDER BY na.published_utc DESC LIMIT 100",
            (symbol, symbol)).fetchall()
    conn.close()
    return [enrich_news_row(r) for r in rows]

@router.get("/{symbol}/range")
def get_news_for_range(symbol: str, start: str = Query(...), end: str = Query(...)):
    from database import get_conn
    symbol = normalize_symbol(symbol)
    conn = get_conn()
    rows = conn.execute(
        "SELECT na.news_id, na.trade_date, na.published_utc, na.ret_t0, na.ret_t1, "
        "nr.title, nr.description, nr.publisher, nr.article_url, nr.image_url, "
        "l1.relevance, l1.key_discussion, l1.chinese_summary, l1.sentiment, l1.reason_growth, l1.reason_decrease "
        "FROM news_aligned na JOIN news_raw nr ON na.news_id = nr.id "
        "LEFT JOIN layer1_results l1 ON na.news_id = l1.news_id AND l1.symbol = ? "
        "WHERE na.symbol = ? AND na.trade_date BETWEEN ? AND ? ORDER BY na.published_utc DESC",
        (symbol, symbol, start, end)).fetchall()
    conn.close()
    articles = [enrich_news_row(r) for r in rows]
    top_bullish = sorted([a for a in articles if a.get("sentiment") == "positive" and a.get("ret_t0")], key=lambda a: a["ret_t0"], reverse=True)[:5]
    top_bearish = sorted([a for a in articles if a.get("sentiment") == "negative" and a.get("ret_t0")], key=lambda a: a["ret_t0"])[:5]
    return {"total": len(articles), "date_range": [start, end], "articles": articles, "top_bullish": top_bullish, "top_bearish": top_bearish}

@router.get("/{symbol}/particles")
def get_news_particles(symbol: str):
    from database import get_conn
    symbol = normalize_symbol(symbol)
    conn = get_conn()
    rows = conn.execute(
        "SELECT na.news_id, na.trade_date, na.ret_t1, nr.title, l1.sentiment, l1.relevance "
        "FROM news_aligned na JOIN news_raw nr ON na.news_id = nr.id "
        "LEFT JOIN layer1_results l1 ON na.news_id = l1.news_id AND l1.symbol = ? "
        "WHERE na.symbol = ? ORDER BY na.trade_date ASC, l1.relevance DESC",
        (symbol, symbol)).fetchall()
    conn.close()
    return [{"id": r["news_id"], "d": r["trade_date"], "s": r["sentiment"], "r": r["relevance"],
             "t": (r["title"] or "")[:80], "rt1": r["ret_t1"]} for r in rows]

@router.get("/{symbol}/categories")
def get_news_categories(symbol: str):
    from database import get_conn
    symbol = normalize_symbol(symbol)
    conn = get_conn()
    rows = conn.execute(
        "SELECT na.news_id, nr.title, l1.key_discussion, l1.reason_growth, l1.reason_decrease, l1.sentiment "
        "FROM news_aligned na JOIN news_raw nr ON na.news_id = nr.id "
        "LEFT JOIN layer1_results l1 ON na.news_id = l1.news_id AND l1.symbol = ? "
        "WHERE na.symbol = ? ORDER BY na.trade_date DESC",
        (symbol, symbol)).fetchall()
    conn.close()
    CATEGORY_KEYWORDS = {
        "market": ["market","stock","rally","sell-off","trading","wall street","s&p","nasdaq","index","bull","bear","correction","恒生","纳指","市场","反弹","抛售"],
        "policy": ["regulation","fed","tariff","sanction","interest rate","policy","government","congress","sec","trade war","ban","监管","政策","央行","美联储","关税","制裁"],
        "earnings": ["earnings","revenue","profit","quarter","eps","guidance","forecast","income","sales","beat","miss","财报","业绩","收入","利润","指引"],
        "product_tech": ["product","ai","chip","cloud","launch","patent","technology","innovation","release","platform","gpu","m3","发布","新产品","模型","大模型","技术","算力","芯片"],
        "competition": ["competitor","rival","market share","overtake","compete","competition","vs","battle","竞争","竞品","份额","价格战"],
        "ipo_financing": ["ipo","listing","funding","valuation","招股","上市","聆讯","融资","估值"],
        "management": ["ceo","executive","resign","layoff","restructure","management","leadership","appoint","hire","board","管理层","裁员","重组","任命"]}
    label_map = {key: rule["label"] for key, rule in CATEGORY_RULES.items()}
    label_map["market"] = "市场走势/资金情绪"
    categories = {cat: {"label":label_map.get(cat, cat),"count":0,"article_ids":[],"positive_ids":[],"negative_ids":[],"neutral_ids":[]} for cat in CATEGORY_KEYWORDS}
    for r in rows:
        text = " ".join([(r["title"] or ""),(r["key_discussion"] or ""),(r["reason_growth"] or ""),(r["reason_decrease"] or "")]).lower()
        sentiment = r["sentiment"]
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                categories[cat]["count"] += 1
                categories[cat]["article_ids"].append(r["news_id"])
                if sentiment == "positive": categories[cat]["positive_ids"].append(r["news_id"])
                elif sentiment == "negative": categories[cat]["negative_ids"].append(r["news_id"])
                else: categories[cat]["neutral_ids"].append(r["news_id"])
    return {"categories": categories, "total": len(rows)}

@router.get("/{symbol}/timeline")
def get_news_timeline(symbol: str):
    from database import get_conn
    symbol = normalize_symbol(symbol)
    conn = get_conn()
    rows = conn.execute(
        "SELECT trade_date, COUNT(*) as news_count, SUM(CASE WHEN l1.relevance = 'relevant' THEN 1 ELSE 0 END) as relevant_count "
        "FROM news_aligned na LEFT JOIN layer1_results l1 ON na.news_id = l1.news_id AND l1.symbol = na.symbol "
        "WHERE na.symbol = ? GROUP BY trade_date ORDER BY trade_date ASC", (symbol,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
