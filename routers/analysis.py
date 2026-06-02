import json
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class DeepAnalysisRequest(BaseModel):
    news_id: str
    symbol: str

class RangeAnalysisRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    question: Optional[str] = None

class StoryRequest(BaseModel):
    symbol: str

class SimilarRequest(BaseModel):
    news_id: str
    symbol: str
    top_k: Optional[int] = 20

@router.post("/deep")
def deep_analysis(req: DeepAnalysisRequest):
    try:
        from database import get_conn
        from ai_analyzer import analyze_article_impact
        conn = get_conn()
        article = conn.execute("SELECT title, description FROM news_raw WHERE id = ?", (req.news_id,)).fetchone()
        conn.close()
        if not article:
            return {"error": "Article not found", "news_id": req.news_id, "symbol": req.symbol,
                    "discussion": "", "growth_reasons": "", "decrease_reasons": ""}
        result = analyze_article_impact(article["title"] or "", article["description"] or "", req.symbol.upper())
        result["news_id"] = req.news_id
        result["symbol"] = req.symbol
        return result
    except Exception as e:
        return {"error": str(e), "news_id": req.news_id, "symbol": req.symbol,
                "discussion": "", "growth_reasons": "", "decrease_reasons": ""}

@router.post("/story")
def create_story(req: StoryRequest):
    try:
        from database import get_conn
        from ai_analyzer import generate_trend_story
        symbol = req.symbol.upper()
        conn = get_conn()
        ohlc_rows = conn.execute("SELECT date, open, high, low, close, volume FROM ohlc WHERE symbol = ? ORDER BY date ASC", (symbol,)).fetchall()
        if not ohlc_rows:
            conn.close()
            return {"story": f"<p>No OHLC data available for {symbol}.</p>"}
        news_map = {}
        news_rows = conn.execute(
            "SELECT na.trade_date, l1.chinese_summary FROM news_aligned na "
            "JOIN layer1_results l1 ON na.news_id = l1.news_id AND l1.symbol = na.symbol "
            "WHERE na.symbol = ? AND l1.relevance = 'relevant' ORDER BY na.trade_date ASC", (symbol,)).fetchall()
        for nr in news_rows:
            d = nr["trade_date"]
            if d not in news_map: news_map[d] = []
            news_map[d].append(nr["chinese_summary"] or "")
        conn.close()
        lines = ["date,open,high,low,close,volume,news"]
        for row in ohlc_rows:
            news_text = "; ".join(news_map.get(row["date"], []))
            lines.append(f"{row['date']},{row['open']},{row['high']},{row['low']},{row['close']},{row['volume']},\"{news_text}\"")
        csv_content = "\n".join(lines)
        story_html = generate_trend_story(symbol, csv_content)
        return {"story": story_html or "<p>Story generation unavailable - configure AI_API_KEY in .env</p>"}
    except Exception as e:
        return {"story": f"<p>Story generation error: {e}</p>"}

@router.post("/range-local")
def range_analysis_local(req: RangeAnalysisRequest):
    from database import get_conn
    symbol = req.symbol.upper()
    conn = get_conn()
    ohlc_rows = conn.execute("SELECT date, open, high, low, close, volume FROM ohlc WHERE symbol = ? AND date >= ? AND date <= ? ORDER BY date ASC",
        (symbol, req.start_date, req.end_date)).fetchall()
    if not ohlc_rows:
        conn.close()
        # Try yfinance fallback
        try:
            import yfinance as yf
            tk = yf.Ticker(symbol)
            hist = tk.history(start=req.start_date, end=req.end_date)
            if not hist.empty:
                open_p = float(hist.iloc[0]["Open"])
                close_p = float(hist.iloc[-1]["Close"])
                high_p = float(hist["High"].max())
                low_p = float(hist["Low"].min())
                pct = round((close_p - open_p) / open_p * 100, 2)
                return {"symbol": symbol, "start_date": req.start_date, "end_date": req.end_date,
                    "price_change_pct": pct, "open_price": round(open_p,2), "close_price": round(close_p,2),
                    "high_price": round(high_p,2), "low_price": round(low_p,2), "news_count": 0,
                    "trading_days": len(hist), "question": req.question,
                    "sentiment_breakdown": {"positive": 0, "negative": 0, "neutral": 0},
                    "analysis": {"summary": f"{symbol} moved {pct:+.2f}% from {req.start_date} to {req.end_date}.",
                        "key_events": [], "bullish_factors": [], "bearish_factors": [],
                        "trend_analysis": f"Price range: ${low_p:.2f} - ${high_p:.2f}"}}
        except: pass
        return {"error": "No data for this range"}
    open_price = ohlc_rows[0]["open"]
    close_price = ohlc_rows[-1]["close"]
    high_price = max(r["high"] for r in ohlc_rows)
    low_price = min(r["low"] for r in ohlc_rows)
    price_change_pct = round((close_price - open_price) / open_price * 100, 2)
    news_rows = conn.execute(
        "SELECT nr.title, l1.sentiment, l1.chinese_summary, na.trade_date, na.ret_t0 "
        "FROM news_aligned na JOIN layer1_results l1 ON na.news_id = l1.news_id AND l1.symbol = na.symbol "
        "JOIN news_raw nr ON na.news_id = nr.id "
        "WHERE na.symbol = ? AND na.trade_date >= ? AND na.trade_date <= ? AND l1.relevance IN ('high','medium','relevant') "
        "ORDER BY ABS(COALESCE(na.ret_t0, 0)) DESC LIMIT 50",
        (symbol, req.start_date, req.end_date)).fetchall()
    conn.close()
    pos = [r for r in news_rows if r["sentiment"] == "positive"]
    neg = [r for r in news_rows if r["sentiment"] == "negative"]
    summary = f"{symbol} moved {'up' if price_change_pct > 0 else 'down'} {abs(price_change_pct):.2f}% from {req.start_date} to {req.end_date}, over {len(ohlc_rows)} trading days with {len(news_rows)} related news."
    key_events = []
    for r in news_rows[:8]:
        title = (r["title"] or "")[:80]
        ret = r.get("ret_t0")
        ret_s = (" (same-day %+.1f%%)" % (ret*100)) if ret else ""
        dt = r["trade_date"]
        key_events.append("[%s] %s%s" % (dt, title, ret_s))
    bullish = [(r["chinese_summary"] or (r["title"] or "")[:60]) for r in pos[:5] if r["chinese_summary"] or r["title"]]
    bearish = [(r["chinese_summary"] or (r["title"] or "")[:60]) for r in neg[:5] if r["chinese_summary"] or r["title"]]
    # Sentiment breakdown
    sentiment_breakdown = {"positive": len(pos), "negative": len(neg), "neutral": len(news_rows) - len(pos) - len(neg)}
    return {"symbol": symbol, "start_date": req.start_date, "end_date": req.end_date,
        "price_change_pct": price_change_pct, "open_price": open_price, "close_price": close_price,
        "high_price": high_price, "low_price": low_price, "news_count": len(news_rows),
        "trading_days": len(ohlc_rows), "question": req.question,
        "sentiment_breakdown": sentiment_breakdown,
        "analysis": {"summary": summary, "key_events": key_events, "bullish_factors": bullish, "bearish_factors": bearish,
            "trend_analysis": f"Price range ${low_price:.2f} - ${high_price:.2f}"}}

@router.post("/similar")
def similar_news(req: SimilarRequest):
    try:
        from pipeline.similarity import find_similar
        return find_similar(req.news_id, req.symbol.upper(), req.top_k or 20)
    except Exception as e:
        return {"error": str(e), "similar": []}
