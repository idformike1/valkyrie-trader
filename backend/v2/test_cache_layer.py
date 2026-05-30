import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import sqlite3

from v2.cache.database import init_cache_db
from v2.cache.manager import HistoricalDataCacheManager
from v2.upstox_expired_loader import UpstoxExpiredOptionDownloader
from v2.data_loader import UnderlyingHistoricalLoader, OptionHistoricalLoader
from v2.resolvers import HistoricalContractResolver

TEST_DB_PATH = "/Users/rajumaharjan/Documents/Anit Gravity Projects/Valkyrie/backend/v2/test_valkyrie_options_cache.db"

class TestCacheLayer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize test database
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        init_cache_db(TEST_DB_PATH)

    @classmethod
    def tearDownClass(cls):
        # Cleanup test database
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    def setUp(self):
        self.manager = HistoricalDataCacheManager(TEST_DB_PATH)
        # Clear tables before each test
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM underlying_candles")
        cursor.execute("DELETE FROM option_candles")
        cursor.execute("DELETE FROM cache_metadata")
        cursor.execute("DELETE FROM download_jobs")
        conn.commit()
        conn.close()

    # 1. Database Initialization Test
    def test_init_db(self):
        self.assertTrue(os.path.exists(TEST_DB_PATH))
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        self.assertIn("underlying_candles", tables)
        self.assertIn("option_candles", tables)
        self.assertIn("cache_metadata", tables)
        self.assertIn("download_jobs", tables)
        conn.close()

    # 2. Coverage Validation Tests
    def test_coverage_missing_no_metadata(self):
        cov = self.manager.verify_coverage("2026-05-25T10:00:00", "2026-05-25T15:00:00", None, None)
        self.assertEqual(cov, "MISSING")

    def test_coverage_full(self):
        cov = self.manager.verify_coverage(
            "2026-05-25T10:00:00", "2026-05-25T15:00:00",
            "2026-05-25T09:00:00", "2026-05-25T16:00:00"
        )
        self.assertEqual(cov, "FULL")

    def test_coverage_partial_left_gap(self):
        cov = self.manager.verify_coverage(
            "2026-05-25T08:00:00", "2026-05-25T15:00:00",
            "2026-05-25T09:00:00", "2026-05-25T16:00:00"
        )
        self.assertEqual(cov, "PARTIAL")

    def test_coverage_partial_right_gap(self):
        cov = self.manager.verify_coverage(
            "2026-05-25T10:00:00", "2026-05-25T17:00:00",
            "2026-05-25T09:00:00", "2026-05-25T16:00:00"
        )
        self.assertEqual(cov, "PARTIAL")

    def test_coverage_missing_completely_before(self):
        cov = self.manager.verify_coverage(
            "2026-05-25T07:00:00", "2026-05-25T08:00:00",
            "2026-05-25T09:00:00", "2026-05-25T16:00:00"
        )
        self.assertEqual(cov, "MISSING")

    def test_coverage_missing_completely_after(self):
        cov = self.manager.verify_coverage(
            "2026-05-25T17:00:00", "2026-05-25T18:00:00",
            "2026-05-25T09:00:00", "2026-05-25T16:00:00"
        )
        self.assertEqual(cov, "MISSING")

    # 3. Cache Database Operations Tests
    def test_store_and_retrieve_underlying_candles(self):
        candles = [
            {"timestamp": "2026-05-25T10:00:00", "open": 22000.0, "high": 22010.0, "low": 21990.0, "close": 22005.0, "volume": 100},
            {"timestamp": "2026-05-25T10:05:00", "open": 22005.0, "high": 22020.0, "low": 22000.0, "close": 22015.0, "volume": 150}
        ]
        self.manager.store_range("NSE_INDEX|Nifty 50", candles, is_option=False)
        
        retrieved = self.manager.get_range("NSE_INDEX|Nifty 50", "2026-05-25T09:00:00", "2026-05-25T11:00:00", is_option=False)
        self.assertEqual(len(retrieved), 2)
        self.assertEqual(retrieved[0]["close"], 22005.0)
        self.assertEqual(retrieved[1]["volume"], 150)

    def test_store_and_retrieve_option_candles(self):
        candles = [
            {"timestamp": "2026-05-25T10:00:00", "open": 150.0, "high": 155.0, "low": 148.0, "close": 152.0, "volume": 500}
        ]
        self.manager.store_range("NSE_FO|50973", candles, is_option=True, strike=27000.0, option_type="CE", expiry="2026-06-30")
        
        retrieved = self.manager.get_range("NSE_FO|50973", "2026-05-25T09:00:00", "2026-05-25T11:00:00", is_option=True)
        self.assertEqual(len(retrieved), 1)
        self.assertEqual(retrieved[0]["strike"], 27000.0)
        self.assertEqual(retrieved[0]["option_type"], "CE")
        self.assertEqual(retrieved[0]["expiry"], "2026-06-30")

    def test_get_metadata_empty(self):
        meta = self.manager.get_metadata("NON_EXISTENT")
        self.assertIsNone(meta)

    def test_metadata_creation_on_store(self):
        candles = [
            {"timestamp": "2026-05-25T10:00:00", "open": 22000.0, "high": 22010.0, "low": 21990.0, "close": 22005.0}
        ]
        self.manager.store_range("NSE_INDEX|Nifty 50", candles, is_option=False)
        meta = self.manager.get_metadata("NSE_INDEX|Nifty 50")
        self.assertIsNotNone(meta)
        self.assertEqual(meta["cached_from"], "2026-05-25T10:00:00")
        self.assertEqual(meta["cached_to"], "2026-05-25T10:00:00")

    def test_metadata_range_expansion_left(self):
        # Store initial candle
        self.manager.store_range("NSE_INDEX|Nifty 50", [
            {"timestamp": "2026-05-25T10:00:00", "open": 22000.0, "high": 22010.0, "low": 21990.0, "close": 22005.0}
        ], is_option=False)
        
        # Store earlier candle (expands from)
        self.manager.store_range("NSE_INDEX|Nifty 50", [
            {"timestamp": "2026-05-25T09:00:00", "open": 22000.0, "high": 22010.0, "low": 21990.0, "close": 22005.0}
        ], is_option=False)
        
        meta = self.manager.get_metadata("NSE_INDEX|Nifty 50")
        self.assertEqual(meta["cached_from"], "2026-05-25T09:00:00")
        self.assertEqual(meta["cached_to"], "2026-05-25T10:00:00")

    def test_metadata_range_expansion_right(self):
        # Store initial
        self.manager.store_range("NSE_INDEX|Nifty 50", [
            {"timestamp": "2026-05-25T10:00:00", "open": 22000.0, "high": 22010.0, "low": 21990.0, "close": 22005.0}
        ], is_option=False)
        
        # Store later candle (expands to)
        self.manager.store_range("NSE_INDEX|Nifty 50", [
            {"timestamp": "2026-05-25T11:00:00", "open": 22000.0, "high": 22010.0, "low": 21990.0, "close": 22005.0}
        ], is_option=False)
        
        meta = self.manager.get_metadata("NSE_INDEX|Nifty 50")
        self.assertEqual(meta["cached_from"], "2026-05-25T10:00:00")
        self.assertEqual(meta["cached_to"], "2026-05-25T11:00:00")

    def test_metadata_range_no_expansion(self):
        self.manager.store_range("NSE_INDEX|Nifty 50", [
            {"timestamp": "2026-05-25T09:00:00", "open": 22000.0, "high": 22010.0, "low": 21990.0, "close": 22005.0},
            {"timestamp": "2026-05-25T11:00:00", "open": 22000.0, "high": 22010.0, "low": 21990.0, "close": 22005.0}
        ], is_option=False)
        
        # Store intermediate (no expansion)
        self.manager.store_range("NSE_INDEX|Nifty 50", [
            {"timestamp": "2026-05-25T10:00:00", "open": 22000.0, "high": 22010.0, "low": 21990.0, "close": 22005.0}
        ], is_option=False)
        
        meta = self.manager.get_metadata("NSE_INDEX|Nifty 50")
        self.assertEqual(meta["cached_from"], "2026-05-25T09:00:00")
        self.assertEqual(meta["cached_to"], "2026-05-25T11:00:00")

    def test_get_range_empty(self):
        ret = self.manager.get_range("NSE_INDEX|Nifty 50", "2026-05-25T09:00:00", "2026-05-25T11:00:00", is_option=False)
        self.assertEqual(len(ret), 0)

    def test_get_range_filter(self):
        self.manager.store_range("NSE_INDEX|Nifty 50", [
            {"timestamp": "2026-05-25T09:00:00", "open": 22000.0, "high": 22010.0, "low": 21990.0, "close": 22005.0},
            {"timestamp": "2026-05-25T10:00:00", "open": 22000.0, "high": 22010.0, "low": 21990.0, "close": 22005.0},
            {"timestamp": "2026-05-25T11:00:00", "open": 22000.0, "high": 22010.0, "low": 21990.0, "close": 22005.0}
        ], is_option=False)
        
        # Request subrange
        ret = self.manager.get_range("NSE_INDEX|Nifty 50", "2026-05-25T09:30:00", "2026-05-25T10:30:00", is_option=False)
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]["timestamp"].hour, 10)

    def test_invalidate_instrument(self):
        self.manager.store_range("NSE_INDEX|Nifty 50", [
            {"timestamp": "2026-05-25T10:00:00", "open": 22000.0, "high": 22010.0, "low": 21990.0, "close": 22005.0}
        ], is_option=False)
        self.manager.invalidate("NSE_INDEX|Nifty 50")
        
        meta = self.manager.get_metadata("NSE_INDEX|Nifty 50")
        self.assertIsNone(meta)
        candles = self.manager.get_range("NSE_INDEX|Nifty 50", "2026-05-25T09:00:00", "2026-05-25T11:00:00", is_option=False)
        self.assertEqual(len(candles), 0)

    # 4. Downloader Mock Integration Tests
    @patch("v2.upstox_expired_loader.load_upstox_token")
    @patch("requests.get")
    def test_downloader_mock_success_standard(self, mock_get, mock_token):
        mock_token.return_value = "mock_token"
        
        # Setup mock API response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {
                "candles": [
                    ["2026-05-25T10:00:00Z", 150.0, 155.0, 148.0, 152.0, 500]
                ]
            }
        }
        mock_get.return_value = mock_resp
        
        downloader = UpstoxExpiredOptionDownloader(self.manager)
        candles = downloader.download_and_cache(
            instrument_key="NSE_FO|50973",
            interval="1minute",
            from_date=datetime(2026, 5, 25, 9, 0),
            to_date=datetime(2026, 5, 25, 11, 0),
            strike=27000.0,
            option_type="CE",
            expiry="2026-06-30"
        )
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0]["close"], 152.0)
        
        # Verify saved to cache
        ret = self.manager.get_range("NSE_FO|50973", "2026-05-25T09:00:00", "2026-05-25T11:00:00", is_option=True)
        self.assertEqual(len(ret), 1)

    @patch("v2.upstox_expired_loader.load_upstox_token")
    @patch("requests.get")
    def test_downloader_mock_success_expired(self, mock_get, mock_token):
        mock_token.return_value = "mock_token"
        
        # 1st request to standard endpoint returns expired error (e.g. 400 UDAPI100011)
        mock_resp_err = MagicMock()
        mock_resp_err.status_code = 400
        mock_resp_err.text = "Invalid Instrument key (UDAPI100011)"
        
        # 2nd request to expired endpoint returns 200 SUCCESS
        mock_resp_ok = MagicMock()
        mock_resp_ok.status_code = 200
        mock_resp_ok.json.return_value = {
            "data": {
                "candles": [
                    ["2026-05-25T10:00:00Z", 150.0, 155.0, 148.0, 152.0, 500]
                ]
            }
        }
        
        # Mock requests.get side effect to fail first, succeed second
        mock_get.side_effect = [mock_resp_err, mock_resp_ok]
        
        downloader = UpstoxExpiredOptionDownloader(self.manager)
        candles = downloader.download_and_cache(
            instrument_key="NSE_FO|50973",
            interval="1minute",
            from_date=datetime(2026, 5, 25, 9, 0),
            to_date=datetime(2026, 5, 25, 11, 0),
            strike=27000.0,
            option_type="CE",
            expiry="2026-06-30"
        )
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0]["close"], 152.0)
        self.assertEqual(mock_get.call_count, 2)

    @patch("v2.upstox_expired_loader.load_upstox_token")
    @patch("requests.get")
    def test_downloader_mock_failure(self, mock_get, mock_token):
        mock_token.return_value = "mock_token"
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_get.return_value = mock_resp
        
        downloader = UpstoxExpiredOptionDownloader(self.manager)
        with self.assertRaises(ValueError):
            downloader.download_and_cache(
                instrument_key="NSE_FO|50973",
                interval="1minute",
                from_date=datetime(2026, 5, 25, 9, 0),
                to_date=datetime(2026, 5, 25, 11, 0),
                strike=27000.0,
                option_type="CE",
                expiry="2026-06-30"
            )

    # 5. Loader Cache-First Integration Tests
    @patch("v2.data_loader.load_upstox_token")
    @patch("requests.get")
    def test_underlying_loader_cache_miss_then_hit(self, mock_get, mock_token):
        mock_token.return_value = "mock_token"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {
                "candles": [
                    ["2026-05-25T09:00:00Z", 22000.0, 22010.0, 21990.0, 22005.0, 100],
                    ["2026-05-25T11:00:00Z", 22000.0, 22010.0, 21990.0, 22005.0, 100]
                ]
            }
        }
        mock_get.return_value = mock_resp
        
        loader = UnderlyingHistoricalLoader(self.manager)
        from_date = datetime(2026, 5, 25, 9, 0)
        to_date = datetime(2026, 5, 25, 11, 0)
        
        # 1st call: Cache MISS -> invokes requests.get
        candles_miss = loader.load_candles("NIFTY", "1m", from_date, to_date)
        self.assertEqual(len(candles_miss), 2)
        self.assertEqual(mock_get.call_count, 1)
        
        # Reset mock call count to verify cache hit doesn't request API
        mock_get.reset_mock()
        
        # 2nd call: Cache HIT -> returns cached candles immediately
        candles_hit = loader.load_candles("NIFTY", "1m", from_date, to_date)
        self.assertEqual(len(candles_hit), 2)
        self.assertEqual(mock_get.call_count, 0)

    @patch("v2.data_loader.HistoricalContractResolver.resolve")
    @patch("v2.data_loader.load_upstox_token")
    @patch("requests.get")
    def test_option_loader_cache_miss_then_hit(self, mock_get, mock_token, mock_resolve):
        mock_resolve.return_value = "NSE_FO|50973"
        mock_token.return_value = "mock_token"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {
                "candles": [
                    ["2026-05-25T09:00:00Z", 150.0, 155.0, 148.0, 152.0, 500],
                    ["2026-05-25T11:00:00Z", 150.0, 155.0, 148.0, 152.0, 500]
                ]
            }
        }
        mock_get.return_value = mock_resp
        
        loader = OptionHistoricalLoader(self.manager)
        from_date = datetime(2026, 5, 25, 9, 0)
        to_date = datetime(2026, 5, 25, 11, 0)
        
        # 1st call: Cache MISS
        candles_miss = loader.load_candles("NIFTY", 27000.0, "2026-06-30", "CE", "1m", from_date, to_date)
        self.assertEqual(len(candles_miss), 2)
        self.assertEqual(mock_get.call_count, 1)
        
        mock_get.reset_mock()
        
        # 2nd call: Cache HIT
        candles_hit = loader.load_candles("NIFTY", 27000.0, "2026-06-30", "CE", "1m", from_date, to_date)
        self.assertEqual(len(candles_hit), 2)
        self.assertEqual(mock_get.call_count, 0)

    # 6. Performance Benchmarks
    def test_benchmarks(self):
        import time
        from v2.resolvers import ContractMasterCache
        
        # Make sure ContractMasterCache is initialized
        ContractMasterCache().preload()

        # A. Contract lookup benchmark (< 5ms)
        start_time = time.perf_counter()
        iterations = 500
        for _ in range(iterations):
            HistoricalContractResolver.resolve("NIFTY", 27000.0, "2026-06-30", "CE")
        elapsed_ms = ((time.perf_counter() - start_time) / iterations) * 1000.0
        print(f"\n[BENCHMARK] Average Contract Lookup Time: {elapsed_ms:.4f} ms")
        self.assertLess(elapsed_ms, 5.0)

        # B. Cache query benchmark (< 50ms)
        candles = [
            {"timestamp": f"2026-05-25T10:{i:02d}:00", "open": 22000.0, "high": 22010.0, "low": 21990.0, "close": 22005.0, "volume": 100}
            for i in range(50)
        ]
        self.manager.store_range("NSE_INDEX|Nifty 50", candles, is_option=False)
        
        start_time = time.perf_counter()
        self.manager.get_range("NSE_INDEX|Nifty 50", "2026-05-25T10:00:00", "2026-05-25T10:45:00", is_option=False)
        cache_query_elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        print(f"[BENCHMARK] Cache Query (50 candles) Time: {cache_query_elapsed_ms:.4f} ms")
        self.assertLess(cache_query_elapsed_ms, 50.0)

        # C. 1-year candle retrieval benchmark (< 500ms)
        large_candles = []
        base_time = datetime(2025, 1, 1, 9, 15)
        for i in range(20000):
            ts = base_time + timedelta(minutes=5 * i)
            large_candles.append({
                "timestamp": ts.isoformat(),
                "open": 22000.0 + (i % 100),
                "high": 22010.0 + (i % 100),
                "low": 21990.0 + (i % 100),
                "close": 22005.0 + (i % 100),
                "volume": 100
            })
        
        self.manager.store_range("NSE_INDEX|Nifty 50", large_candles, is_option=False)
        
        start_time = time.perf_counter()
        retrieved = self.manager.get_range(
            "NSE_INDEX|Nifty 50", 
            "2025-01-01T09:15:00", 
            (base_time + timedelta(minutes=5 * 20000)).isoformat(),
            is_option=False
        )
        one_year_elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        print(f"[BENCHMARK] 1-Year (20,000 candles) Retrieval Time: {one_year_elapsed_ms:.4f} ms")
        self.assertEqual(len(retrieved), 20000)
        self.assertLess(one_year_elapsed_ms, 500.0)

if __name__ == "__main__":
    unittest.main()
