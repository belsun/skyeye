import sqlite3
from config import DATABASE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickers (
    symbol TEXT PRIMARY KEY, name TEXT, sector TEXT,
    last_ohlc_fetch TEXT, last_news_fetch TEXT
);
CREATE TABLE IF NOT EXISTS ohlc (
    symbol TEXT NOT NULL, date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume REAL, vwap REAL, transactions INTEGER,
    PRIMARY KEY (symbol, date)
);
CREATE TABLE IF NOT EXISTS news_raw (
    id TEXT PRIMARY KEY, title TEXT, description TEXT,
    publisher TEXT, author TEXT, published_utc TEXT,
    article_url TEXT, amp_url TEXT, image_url TEXT,
    tickers_json TEXT, insights_json TEXT
);
CREATE TABLE IF NOT EXISTS news_ticker (
    news_id TEXT NOT NULL, symbol TEXT NOT NULL,
    PRIMARY KEY (news_id, symbol), FOREIGN KEY (news_id) REFERENCES news_raw(id)
);
CREATE TABLE IF NOT EXISTS layer0_results (
    news_id TEXT NOT NULL, symbol TEXT NOT NULL, passed INTEGER NOT NULL, reason TEXT,
    PRIMARY KEY (news_id, symbol)
);
CREATE TABLE IF NOT EXISTS layer1_results (
    news_id TEXT NOT NULL, symbol TEXT NOT NULL, relevance TEXT, key_discussion TEXT,
    chinese_summary TEXT, sentiment TEXT, discussion TEXT, reason_growth TEXT, reason_decrease TEXT,
    PRIMARY KEY (news_id, symbol)
);
CREATE TABLE IF NOT EXISTS layer2_results (
    news_id TEXT NOT NULL, symbol TEXT NOT NULL, discussion TEXT,
    growth_reasons TEXT, decrease_reasons TEXT, created_at TEXT,
    PRIMARY KEY (news_id, symbol)
);
CREATE TABLE IF NOT EXISTS news_aligned (
    news_id TEXT NOT NULL, symbol TEXT NOT NULL, trade_date TEXT NOT NULL,
    published_utc TEXT, ret_t0 REAL, ret_t1 REAL, ret_t3 REAL, ret_t5 REAL, ret_t10 REAL,
    PRIMARY KEY (news_id, symbol)
);
CREATE INDEX IF NOT EXISTS idx_news_aligned_symbol_date ON news_aligned(symbol, trade_date);
CREATE TABLE IF NOT EXISTS batch_jobs (
    batch_id TEXT PRIMARY KEY, symbol TEXT, status TEXT,
    total INTEGER, completed INTEGER DEFAULT 0, created_at TEXT, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS batch_request_map (
    batch_id TEXT NOT NULL, custom_id TEXT NOT NULL,
    symbol TEXT NOT NULL, article_ids TEXT NOT NULL,
    PRIMARY KEY (batch_id, custom_id)
);
CREATE TABLE IF NOT EXISTS portfolio_positions (
    symbol TEXT PRIMARY KEY,
    shares REAL NOT NULL DEFAULT 0,
    avg_cost REAL,
    thesis TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS trade_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    trade_date TEXT NOT NULL,
    thesis TEXT,
    setup TEXT,
    review TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_trade_journal_symbol_date ON trade_journal(symbol, trade_date);
CREATE TABLE IF NOT EXISTS paper_books (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    currency TEXT NOT NULL,
    initial_cash REAL NOT NULL,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS paper_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    notional REAL NOT NULL,
    reason TEXT,
    radar_alert_id TEXT,
    trade_date TEXT NOT NULL,
    created_at TEXT,
    FOREIGN KEY (book_id) REFERENCES paper_books(id)
);
CREATE INDEX IF NOT EXISTS idx_paper_orders_book_symbol ON paper_orders(book_id, symbol);
CREATE TABLE IF NOT EXISTS paper_positions (
    book_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    shares REAL NOT NULL DEFAULT 0,
    avg_cost REAL,
    realized_pnl REAL NOT NULL DEFAULT 0,
    updated_at TEXT,
    PRIMARY KEY (book_id, symbol),
    FOREIGN KEY (book_id) REFERENCES paper_books(id)
);
CREATE TABLE IF NOT EXISTS company_profiles (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    name_zh TEXT,
    market TEXT,
    sector TEXT,
    industry TEXT,
    website TEXT,
    ir_url TEXT,
    filings_url TEXT,
    financials_url TEXT,
    country TEXT,
    currency TEXT,
    employees INTEGER,
    summary TEXT,
    summary_zh TEXT,
    source TEXT,
    fetched_at TEXT
);
"""

def get_conn():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(news_raw)").fetchall()}
    if "image_url" not in cols:
        conn.execute("ALTER TABLE news_raw ADD COLUMN image_url TEXT")
        conn.commit()
    profile_cols = {row["name"] for row in conn.execute("PRAGMA table_info(company_profiles)").fetchall()}
    for col, ddl in {
        "name_zh": "TEXT",
        "ir_url": "TEXT",
        "filings_url": "TEXT",
        "financials_url": "TEXT",
        "summary_zh": "TEXT",
        "fetched_at": "TEXT",
    }.items():
        if col not in profile_cols:
            conn.execute(f"ALTER TABLE company_profiles ADD COLUMN {col} {ddl}")
            conn.commit()
    conn.close()
    print(f"Database initialized at {DATABASE_PATH}")
