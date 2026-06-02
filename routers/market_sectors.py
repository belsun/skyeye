"""Add multi-market sector data and API endpoint."""
import sqlite3
from fastapi import APIRouter
from database import get_conn
import yfinance as yf
import math

router = APIRouter()

# Market sector definitions
MARKET_SECTORS = {
    "hk": [
        {"key": "tech", "name": "科技", "icon": "💻", "stocks": [("0700.HK", "腾讯"), ("9988.HK", "阿里"), ("1810.HK", "小米")]},
        {"key": "finance", "name": "金融", "icon": "🏦", "stocks": [("0005.HK", "汇丰"), ("0388.HK", "港交所"), ("2318.HK", "平安")]},
        {"key": "consumer", "name": "消费", "icon": "🛍️", "stocks": [("3690.HK", "美团"), ("9618.HK", "京东"), ("9999.HK", "网易")]},
        {"key": "auto", "name": "汽车", "icon": "🚗", "stocks": [("1211.HK", "比亚迪"), ("9866.HK", "蔚来"), ("2015.HK", "理想")]},
        {"key": "healthcare", "name": "医药", "icon": "🏥", "stocks": [("2269.HK", "药明生物"), ("1093.HK", "石药"), ("6969.HK", "思摩尔")]},
    ],
    "cn": [
        {"key": "tech", "name": "科技", "icon": "💻", "stocks": [("002415.SZ", "海康威视"), ("000725.SZ", "京东方"), ("002230.SZ", "科大讯飞")]},
        {"key": "finance", "name": "金融", "icon": "🏦", "stocks": [("601318.SS", "中国平安"), ("600036.SS", "招商银行"), ("601166.SS", "兴业银行")]},
        {"key": "consumer", "name": "消费", "icon": "🛍️", "stocks": [("600519.SS", "贵州茅台"), ("000858.SZ", "五粮液"), ("603288.SS", "海天味业")]},
        {"key": "auto", "name": "汽车", "icon": "🚗", "stocks": [("002594.SZ", "比亚迪"), ("600104.SS", "上汽集团"), ("601238.SS", "广汽集团")]},
        {"key": "energy", "name": "能源", "icon": "⛽", "stocks": [("601857.SS", "中国石油"), ("600028.SS", "中国石化"), ("601088.SS", "中国神华")]},
    ],
    "jp": [
        {"key": "tech", "name": "科技", "icon": "💻", "stocks": [("6857.T", "爱德万"), ("6758.T", "索尼"), ("8035.T", "东京电子")]},
        {"key": "auto", "name": "汽车", "icon": "🚗", "stocks": [("7203.T", "丰田"), ("7267.T", "本田"), ("7201.T", "日产")]},
        {"key": "finance", "name": "金融", "icon": "🏦", "stocks": [("8316.T", "瑞穗"), ("8306.T", "三菱UFJ"), ("8411.T", "三井住友")]},
    ],
    "eu": [
        {"key": "tech", "name": "科技", "icon": "💻", "stocks": [("SAP.DE", "SAP"), ("ASML.AS", "ASML"), ("SIE.DE", "西门子")]},
        {"key": "auto", "name": "汽车", "icon": "🚗", "stocks": [("MBG.DE", "奔驰"), ("BMW.DE", "宝马"), ("VOW3.DE", "大众")]},
        {"key": "luxury", "name": "奢侈品", "icon": "💎", "stocks": [("MC.PA", "LVMH"), ("KER.PA", "开云"), ("RMS.PA", "爱马仕")]},
    ],
}


def _safe_price(symbol):
    """Get real-time price for a symbol."""
    try:
        tk = yf.Ticker(symbol)
        info = tk.fast_info
        price = getattr(info, 'last_price', None)
        prev = getattr(info, 'previous_close', None)
        if price and prev and not math.isnan(price) and not math.isnan(prev):
            change = price - prev
            pct = (change / prev * 100) if prev else 0
            return {"price": round(price, 2), "change": round(change, 2), "change_pct": round(pct, 2)}
    except:
        pass
    return None


@router.get("/market-sectors/{market}")
def get_market_sectors(market: str):
    """Get sector heatmap data for a specific market."""
    sectors = MARKET_SECTORS.get(market, [])
    if not sectors:
        return {"error": f"No sector data for market: {market}", "sectors": []}
    
    result = []
    for sector in sectors:
        stocks_data = []
        for sym, name in sector["stocks"]:
            price_data = _safe_price(sym)
            stocks_data.append({
                "symbol": sym,
                "name": name,
                "price": price_data["price"] if price_data else 0,
                "change": price_data["change"] if price_data else 0,
                "change_pct": price_data["change_pct"] if price_data else 0,
            })
        
        # Calculate sector average change
        changes = [s["change_pct"] for s in stocks_data if s["change_pct"] != 0]
        avg_change = sum(changes) / len(changes) if changes else 0
        
        result.append({
            "key": sector["key"],
            "name": sector["name"],
            "icon": sector["icon"],
            "change_pct": round(avg_change, 2),
            "leader": stocks_data[0] if stocks_data else None,
            "stocks": stocks_data,
        })
    
    return {"market": market, "sectors": result}
