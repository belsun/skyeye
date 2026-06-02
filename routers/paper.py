from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from math import sqrt
from statistics import pstdev

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from database import get_conn
from routers.stocks import normalize_symbol

router = APIRouter()

DEFAULT_BOOKS = {
    "hkd": {"label": "HKD Paper Book", "currency": "HKD", "initial_cash": 1_000_000.0},
    "usd": {"label": "USD Paper Book", "currency": "USD", "initial_cash": 40_000.0},
}


class PaperOrderRequest(BaseModel):
    book_id: str = Field(..., pattern="^(hkd|usd)$")
    symbol: str
    side: str = Field(..., pattern="^(buy|sell)$")
    notional: float = Field(..., gt=0)
    reason: str = ""
    radar_alert_id: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _round(value, digits: int = 4):
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _ensure_books() -> None:
    now = _now_iso()
    conn = get_conn()
    try:
        for book_id, book in DEFAULT_BOOKS.items():
            conn.execute(
                """INSERT OR IGNORE INTO paper_books (id, label, currency, initial_cash, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (book_id, book["label"], book["currency"], book["initial_cash"], now, now),
            )
        conn.commit()
    finally:
        conn.close()


def _market_for_symbol(symbol: str) -> str:
    sym = symbol.upper()
    if sym.endswith(".HK"):
        return "hk"
    if sym.startswith("^") or sym.endswith("=F") or sym.endswith("-USD"):
        return "observe"
    if "." in sym:
        return "observe"
    return "us"


def _expected_book(symbol: str) -> str | None:
    market = _market_for_symbol(symbol)
    if market == "hk":
        return "hkd"
    if market == "us":
        return "usd"
    return None


def _latest_price(symbol: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT date, close
               FROM ohlc
               WHERE symbol = ?
               ORDER BY date DESC
               LIMIT 1""",
            (symbol,),
        ).fetchone()
    finally:
        conn.close()
    if not row or row["close"] is None:
        return _latest_price_from_yfinance(symbol)
    return {"date": row["date"], "price": float(row["close"])}


@lru_cache(maxsize=128)
def _latest_price_from_yfinance(symbol: str) -> dict | None:
    try:
        import yfinance as yf

        hist = yf.Ticker(symbol).history(period="10d", interval="1d", auto_adjust=False)
        if hist is None or hist.empty or "Close" not in hist:
            return None
        closes = hist["Close"].dropna()
        if closes.empty:
            return None
        idx = closes.index[-1]
        date = idx.date().isoformat() if hasattr(idx, "date") else str(idx)[:10]
        return {"date": date, "price": float(closes.iloc[-1])}
    except Exception:
        return None


@lru_cache(maxsize=128)
def _history_from_yfinance(symbol: str, rows: int) -> tuple[dict, ...]:
    try:
        import yfinance as yf

        hist = yf.Ticker(symbol).history(period=f"{max(rows * 2, 30)}d", interval="1d", auto_adjust=False)
        if hist is None or hist.empty or "Close" not in hist:
            return ()
        result = []
        for idx, close in hist["Close"].dropna().tail(rows).items():
            date = idx.date().isoformat() if hasattr(idx, "date") else str(idx)[:10]
            result.append({"date": date, "close": float(close)})
        return tuple(result)
    except Exception:
        return ()


def _cash_for_book(conn, book_id: str, initial_cash: float) -> float:
    row = conn.execute(
        """SELECT
             COALESCE(SUM(CASE WHEN side = 'buy' THEN notional ELSE -notional END), 0) AS spent
           FROM paper_orders
           WHERE book_id = ?""",
        (book_id,),
    ).fetchone()
    return float(initial_cash) - float(row["spent"] or 0.0)


def _position_value(position: dict) -> dict:
    price = _latest_price(position["symbol"])
    latest_price = price["price"] if price else None
    market_value = float(position["shares"] or 0.0) * latest_price if latest_price is not None else None
    cost_basis = float(position["shares"] or 0.0) * float(position["avg_cost"] or 0.0)
    unrealized = market_value - cost_basis if market_value is not None else None
    return {
        **position,
        "latest_close": _round(latest_price, 4),
        "price_date": price["date"] if price else None,
        "market_value": round(market_value, 2) if market_value is not None else None,
        "cost_basis": round(cost_basis, 2),
        "unrealized_pnl": round(unrealized, 2) if unrealized is not None else None,
        "unrealized_pnl_pct": _round(unrealized / cost_basis if unrealized is not None and cost_basis else None),
    }


def _book_snapshot(book_id: str) -> dict:
    _ensure_books()
    conn = get_conn()
    try:
        book = conn.execute("SELECT * FROM paper_books WHERE id = ?", (book_id,)).fetchone()
        if not book:
            raise HTTPException(status_code=404, detail="Paper book not found")
        raw_positions = conn.execute(
            """SELECT book_id, symbol, shares, avg_cost, realized_pnl, updated_at
               FROM paper_positions
               WHERE book_id = ? AND shares > 0
               ORDER BY symbol""",
            (book_id,),
        ).fetchall()
        orders = conn.execute(
            """SELECT id, book_id, symbol, side, quantity, price, notional, reason, radar_alert_id, trade_date, created_at
               FROM paper_orders
               WHERE book_id = ?
               ORDER BY id DESC
               LIMIT 20""",
            (book_id,),
        ).fetchall()
        cash = _cash_for_book(conn, book_id, book["initial_cash"])
    finally:
        conn.close()

    positions = [_position_value(dict(row)) for row in raw_positions]
    market_value = sum(float(row.get("market_value") or 0.0) for row in positions)
    equity = cash + market_value
    return {
        "id": book["id"],
        "label": book["label"],
        "currency": book["currency"],
        "initial_cash": round(float(book["initial_cash"]), 2),
        "cash": round(cash, 2),
        "market_value": round(market_value, 2),
        "equity": round(equity, 2),
        "total_return": _round(equity / float(book["initial_cash"]) - 1.0 if book["initial_cash"] else None),
        "positions": positions,
        "orders": [dict(row) for row in orders],
    }


def _load_position(conn, book_id: str, symbol: str):
    return conn.execute(
        "SELECT * FROM paper_positions WHERE book_id = ? AND symbol = ?",
        (book_id, symbol),
    ).fetchone()


def _apply_order(req: PaperOrderRequest) -> dict:
    _ensure_books()
    symbol = normalize_symbol(req.symbol)
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")
    expected = _expected_book(symbol)
    if not expected:
        raise HTTPException(status_code=400, detail="Only HK and US equities can be paper traded in v1.")
    if expected != req.book_id:
        raise HTTPException(status_code=400, detail=f"{symbol} belongs in {expected.upper()} paper book.")
    price_info = _latest_price(symbol)
    if not price_info:
        raise HTTPException(status_code=400, detail=f"No OHLC close price available for {symbol}. Add/fetch data first.")
    price = float(price_info["price"])
    filled_notional = float(req.notional)
    quantity = filled_notional / price
    now = _now_iso()

    conn = get_conn()
    try:
        book = conn.execute("SELECT * FROM paper_books WHERE id = ?", (req.book_id,)).fetchone()
        if not book:
            raise HTTPException(status_code=404, detail="Paper book not found")
        cash = _cash_for_book(conn, req.book_id, book["initial_cash"])
        position = _load_position(conn, req.book_id, symbol)
        current_shares = float(position["shares"] or 0.0) if position else 0.0
        current_avg = float(position["avg_cost"] or 0.0) if position and position["avg_cost"] is not None else None
        realized = float(position["realized_pnl"] or 0.0) if position else 0.0

        if req.side == "buy":
            if filled_notional > cash + 1e-6:
                raise HTTPException(status_code=400, detail="Insufficient paper cash.")
            new_shares = current_shares + quantity
            new_avg = ((current_shares * (current_avg or price)) + filled_notional) / new_shares if new_shares else price
        else:
            if current_shares <= 0:
                raise HTTPException(status_code=400, detail="No paper position to sell.")
            if quantity > current_shares + 1e-6:
                raise HTTPException(status_code=400, detail="Sell notional exceeds current paper position.")
            quantity = min(quantity, current_shares)
            filled_notional = quantity * price
            realized += (price - (current_avg or price)) * quantity
            new_shares = current_shares - quantity
            new_avg = current_avg if new_shares > 1e-9 else None

        cur = conn.execute(
            """INSERT INTO paper_orders (book_id, symbol, side, quantity, price, notional, reason, radar_alert_id, trade_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (req.book_id, symbol, req.side, quantity, price, filled_notional, req.reason, req.radar_alert_id, price_info["date"], now),
        )
        conn.execute(
            """INSERT INTO paper_positions (book_id, symbol, shares, avg_cost, realized_pnl, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(book_id, symbol) DO UPDATE SET
                 shares = excluded.shares,
                 avg_cost = excluded.avg_cost,
                 realized_pnl = excluded.realized_pnl,
                 updated_at = excluded.updated_at""",
            (req.book_id, symbol, new_shares, new_avg, realized, now),
        )
        conn.execute("UPDATE paper_books SET updated_at = ? WHERE id = ?", (now, req.book_id))
        conn.commit()
        order_id = cur.lastrowid
    finally:
        conn.close()

    return {"order_id": order_id, "book": _book_snapshot(req.book_id)}


def _history(symbols: list[str], rows: int) -> dict[str, list[dict]]:
    conn = get_conn()
    try:
        result = {}
        for symbol in symbols:
            raw = conn.execute(
                """SELECT date, close
                   FROM ohlc
                   WHERE symbol = ?
                   ORDER BY date DESC
                   LIMIT ?""",
                (symbol, rows),
            ).fetchall()
            result[symbol] = [{"date": row["date"], "close": float(row["close"])} for row in reversed(raw) if row["close"] is not None]
            if len(result[symbol]) < 2:
                result[symbol] = list(_history_from_yfinance(symbol, rows))
    finally:
        conn.close()
    return result


def _performance(book_id: str, window_days: int) -> dict:
    book = _book_snapshot(book_id)
    positions = book["positions"]
    symbols = [row["symbol"] for row in positions if row.get("shares", 0) > 0]
    if not symbols:
        return {
            "generated_at": _now_iso(),
            "book_id": book_id,
            "currency": book["currency"],
            "window_days": window_days,
            "status": "empty",
            "label": "No Paper Positions",
            "message": "Create a paper order from Opportunity Radar before monitoring this book.",
            "summary": {
                "positions": 0,
                "cash": book["cash"],
                "market_value": 0.0,
                "equity": book["equity"],
                "total_return": book["total_return"],
                "window_return": None,
                "annualized_volatility": None,
                "max_drawdown": None,
            },
            "positions": [],
            "orders": book["orders"],
            "curve": [],
        }
    history = _history(symbols, window_days + 8)
    shares = {row["symbol"]: float(row["shares"] or 0.0) for row in positions}
    date_sets = [{item["date"] for item in rows} for rows in history.values() if len(rows) > 1]
    dates = sorted(set.intersection(*date_sets))[-(window_days + 1):] if date_sets else []
    close_map = {symbol: {row["date"]: row["close"] for row in rows} for symbol, rows in history.items()}
    curve = []
    daily = []
    previous = None
    for date in dates:
        market_value = 0.0
        valid = False
        for symbol, qty in shares.items():
            close = close_map.get(symbol, {}).get(date)
            if close is None:
                continue
            valid = True
            market_value += qty * close
        if not valid:
            continue
        equity = book["cash"] + market_value
        if previous:
            daily.append(equity / previous - 1.0)
        curve.append({
            "date": date,
            "equity": round(equity, 2),
            "market_value": round(market_value, 2),
            "return": _round(equity / book["initial_cash"] - 1.0 if book["initial_cash"] else None),
        })
        previous = equity
    if curve:
        window_return = curve[-1]["equity"] / curve[0]["equity"] - 1.0 if curve[0]["equity"] else None
        max_drawdown = 0.0
        peak = curve[0]["equity"] or 0.0
        for point in curve:
            peak = max(peak, point["equity"])
            if peak:
                max_drawdown = min(max_drawdown, point["equity"] / peak - 1.0)
    else:
        window_return = None
        max_drawdown = None
    return {
        "generated_at": _now_iso(),
        "book_id": book_id,
        "currency": book["currency"],
        "window_days": window_days,
        "status": "tracking" if positions else "empty",
        "label": "Tracking" if positions else "No Paper Positions",
        "message": "Paper book performance is based on simulated fills and latest OHLC closes.",
        "summary": {
            "positions": len(positions),
            "cash": book["cash"],
            "market_value": book["market_value"],
            "equity": book["equity"],
            "total_return": book["total_return"],
            "window_return": _round(window_return),
            "annualized_volatility": _round(pstdev(daily) * sqrt(252)) if len(daily) > 1 else None,
            "max_drawdown": _round(max_drawdown),
        },
        "positions": positions,
        "orders": book["orders"],
        "curve": curve[-45:],
    }


@router.get("/books")
def get_books():
    _ensure_books()
    return {"generated_at": _now_iso(), "books": [_book_snapshot("hkd"), _book_snapshot("usd")]}


@router.post("/orders")
def post_order(req: PaperOrderRequest):
    return _apply_order(req)


@router.get("/performance")
def get_performance(
    book: str = Query("hkd", pattern="^(hkd|usd)$"),
    window_days: int = Query(20, ge=5, le=120),
):
    return _performance(book, window_days)
