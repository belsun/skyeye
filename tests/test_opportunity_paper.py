import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

import database
from database import init_db
from ml.opportunity import _filter_market_alerts, _score_alert
from routers.paper import PaperOrderRequest, _apply_order, _book_snapshot, _expected_book
from routers.stocks import normalize_symbol, search_symbols


class PaperBookTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = str(Path(self.tmpdir.name) / "skyeye_test.db")
        init_db()
        conn = database.get_conn()
        rows = [
            ("NVDA", "2026-05-27", 200, 215, 198, 210, 1000, None, None),
            ("NVDA", "2026-05-28", 210, 220, 205, 214, 1100, None, None),
            ("0700.HK", "2026-05-27", 380, 390, 375, 386, 1000, None, None),
            ("0700.HK", "2026-05-28", 386, 398, 382, 392, 1100, None, None),
        ]
        conn.executemany(
            "INSERT INTO ohlc (symbol, date, open, high, low, close, volume, vwap, transactions) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_market_routes_to_expected_book(self):
        self.assertEqual(_expected_book("0700.HK"), "hkd")
        self.assertEqual(_expected_book("NVDA"), "usd")
        self.assertIsNone(_expected_book("BTC-USD"))

    def test_buy_updates_cash_and_position(self):
        result = _apply_order(PaperOrderRequest(book_id="usd", symbol="NVDA", side="buy", notional=2140, reason="test"))
        book = result["book"]
        self.assertEqual(book["currency"], "USD")
        self.assertAlmostEqual(book["cash"], 37860.0)
        self.assertEqual(book["positions"][0]["symbol"], "NVDA")
        self.assertAlmostEqual(book["positions"][0]["shares"], 10.0)

    def test_wrong_book_rejected(self):
        with self.assertRaises(HTTPException):
            _apply_order(PaperOrderRequest(book_id="hkd", symbol="NVDA", side="buy", notional=1000, reason="wrong"))

    def test_insufficient_cash_rejected(self):
        with self.assertRaises(HTTPException):
            _apply_order(PaperOrderRequest(book_id="usd", symbol="NVDA", side="buy", notional=999999, reason="too much"))


class OpportunityTests(unittest.TestCase):
    def test_score_uses_authority_freshness_and_price_reaction(self):
        data = _score_alert(
            news_items=[
                {"source": "Bloomberg Markets", "published": "2026-05-31T00:00:00+00:00", "sentiment": "positive"},
                {"source": "CNBC", "published": "2026-05-31T00:00:00+00:00", "sentiment": "positive"},
            ],
            events=[{"date": "2026-05-31", "title": "AI event"}],
            catalysts=[{"score": 80, "trend_5d": 0.04, "news_count": 12}],
            chain={"theme": "AI算力与HBM"},
        )
        self.assertGreaterEqual(data["score"], 60)
        self.assertIn("source_quality", data["score_components"])

    def test_market_filter_keeps_matching_symbols(self):
        alerts = [
            {"market": "us", "primary_symbols": ["NVDA"]},
            {"market": "hk", "primary_symbols": ["0700.HK"]},
            {"market": "all", "primary_symbols": ["MSFT", "0700.HK"]},
        ]
        self.assertEqual(len(_filter_market_alerts(alerts, "us")), 2)
        self.assertEqual(len(_filter_market_alerts(alerts, "hk")), 2)
        self.assertEqual(len(_filter_market_alerts(alerts, "all")), 3)


class SearchTests(unittest.TestCase):
    def test_minimax_hk_alias_search(self):
        self.assertEqual(normalize_symbol("00100.HK"), "0100.HK")
        self.assertEqual(normalize_symbol("HKEX:00100"), "0100.HK")
        results = search_symbols("MiniMax", include_remote=False)
        self.assertTrue(results)
        self.assertEqual(results[0]["symbol"], "0100.HK")
        self.assertIn("MiniMax", results[0]["name"])


if __name__ == "__main__":
    unittest.main()
