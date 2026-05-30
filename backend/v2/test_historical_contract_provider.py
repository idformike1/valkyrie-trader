import os
import unittest
import sqlite3
from datetime import datetime
from unittest.mock import patch, MagicMock
from v2.expired_contract_provider import HistoricalContractProvider

class TestHistoricalContractProvider(unittest.TestCase):
    def setUp(self):
        self.db_path = "/Users/rajumaharjan/Documents/Anit Gravity Projects/Valkyrie/backend/v2/test_contracts_cache.db"
        # Remove any leftover test DB
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.provider = HistoricalContractProvider(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_01_init_db(self):
        """Verify DB tables are created successfully during initialization."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()
        self.assertIn("historical_contracts", tables)
        self.assertIn("historical_expiries", tables)

    def test_02_get_expiries_unsupported_underlying(self):
        """Verify get_expiries raises ValueError for unsupported indices."""
        with self.assertRaises(ValueError):
            self.provider.get_expiries("INVALID_INDEX")

    def test_03_get_expiries_cache_hit(self):
        """Verify get_expiries retrieves values directly from the cache."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO historical_expiries VALUES ('NIFTY', '2025-04-17', 'now', 'TEST')"
        )
        conn.commit()
        conn.close()

        # Should fetch from cache without calling API
        with patch('requests.get') as mock_get:
            expiries = self.provider.get_expiries("NIFTY")
            mock_get.assert_not_called()
            self.assertEqual(expiries, ["2025-04-17"])

    @patch('requests.get')
    def test_04_get_expiries_api_success(self, mock_get):
        """Verify get_expiries correctly saves and returns values on successful API response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "success", "data": ["2025-04-24", "2025-04-17"]}
        mock_get.return_value = mock_resp

        expiries = self.provider.get_expiries("NIFTY")
        self.assertEqual(expiries, ["2025-04-17", "2025-04-24"])

        # Check DB persistence
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT expiry_date FROM historical_expiries WHERE underlying='NIFTY'")
        db_expiries = [r[0] for r in cursor.fetchall()]
        conn.close()
        self.assertEqual(sorted(db_expiries), ["2025-04-17", "2025-04-24"])

    @patch('requests.get')
    def test_05_get_expiries_api_failure_fallback(self, mock_get):
        """Verify get_expiries falls back to generator on API error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        expiries = self.provider.get_expiries("NIFTY")
        self.assertTrue(len(expiries) > 0)
        self.assertIn("2025-04-17", expiries)

    def test_06_discover_expiries_alias(self):
        """Verify discover_expiries alias exists and functions identically."""
        fallback_exp = self.provider.discover_expiries("NIFTY")
        self.assertTrue(len(fallback_exp) > 0)

    def test_07_generate_fallback_expiries(self):
        """Verify fallback expiries contain typical Thursday dates."""
        exp = self.provider._generate_fallback_expiries("NIFTY")
        # 2025-04-17 is indeed a Thursday
        self.assertIn("2025-04-17", exp)

    def test_08_get_option_contracts_unsupported_underlying(self):
        """Verify get_option_contracts raises ValueError for unsupported indices."""
        with self.assertRaises(ValueError):
            self.provider.get_option_contracts("INVALID", "2025-04-17")

    def test_09_get_option_contracts_cache_hit(self):
        """Verify get_option_contracts serves directly from cache on HIT."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO historical_contracts 
            VALUES ('NIFTY', '2025-04-17', 23300.0, 'CE', 'NSE_FO|123456', 'NSE', 'now', 'TEST')
            """
        )
        conn.commit()
        conn.close()

        with patch('requests.get') as mock_get:
            contracts = self.provider.get_option_contracts("NIFTY", "2025-04-17")
            mock_get.assert_not_called()
            self.assertEqual(len(contracts), 1)
            self.assertEqual(contracts[0]["instrument_key"], "NSE_FO|123456")

    @patch('requests.get')
    def test_10_get_option_contracts_api_success(self, mock_get):
        """Verify get_option_contracts saves and returns API responses."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "success",
            "data": [
                {
                    "strike_price": 23300.0,
                    "instrument_type": "CE",
                    "instrument_key": "NSE_FO|123456",
                    "exchange": "NSE"
                }
            ]
        }
        mock_get.return_value = mock_resp

        contracts = self.provider.get_option_contracts("NIFTY", "2025-04-17")
        self.assertEqual(len(contracts), 1)
        self.assertEqual(contracts[0]["instrument_key"], "NSE_FO|123456")

        # Verify DB persistence
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT instrument_key FROM historical_contracts")
        db_keys = [r[0] for r in cursor.fetchall()]
        conn.close()
        self.assertEqual(db_keys, ["NSE_FO|123456"])

    @patch('requests.get')
    def test_11_get_option_contracts_api_failure_fallback(self, mock_get):
        """Verify fallback contracts are generated on API failure."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        contracts = self.provider.get_option_contracts("NIFTY", "2025-04-17")
        self.assertTrue(len(contracts) > 0)
        # Should include strike 23300
        strikes = [c["strike"] for c in contracts]
        self.assertIn(23300.0, strikes)

    def test_12_resolve_contract_success_from_cache(self):
        """Verify resolve_contract returns cached instrument keys."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO historical_contracts 
            VALUES ('NIFTY', '2025-04-17', 23300.0, 'CE', 'NSE_FO|123456', 'NSE', 'now', 'TEST')
            """
        )
        conn.commit()
        conn.close()

        key = self.provider.resolve_contract("NIFTY", "2025-04-17", 23300.0, "CE")
        self.assertEqual(key, "NSE_FO|123456")

    @patch('requests.get')
    def test_13_resolve_contract_success_from_api(self, mock_get):
        """Verify resolve_contract resolves keys by querying the API on cache miss."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "success",
            "data": [
                {
                    "strike_price": 23300.0,
                    "instrument_type": "CE",
                    "instrument_key": "NSE_FO|123456",
                    "exchange": "NSE"
                }
            ]
        }
        mock_get.return_value = mock_resp

        key = self.provider.resolve_contract("NIFTY", "2025-04-17", 23300.0, "CE")
        self.assertEqual(key, "NSE_FO|123456")

    def test_14_resolve_contract_not_found_raises_error(self):
        """Verify resolve_contract raises ValueError if contract doesn't exist anywhere."""
        with self.assertRaises(ValueError):
            self.provider.resolve_contract("NIFTY", "2025-04-17", 99999.0, "CE")

    def test_15_duplicate_prevention_on_expiries(self):
        """Verify historical_expiries table UNIQUE index blocks duplicate inserts."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO historical_expiries VALUES ('NIFTY', '2025-04-17', 'now', 'TEST')")
        conn.commit()
        
        # Duplicate insert on Primary Key should raise IntegrityError
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute("INSERT INTO historical_expiries VALUES ('NIFTY', '2025-04-17', 'now', 'TEST')")
            conn.commit()
        conn.close()

    def test_16_duplicate_prevention_on_contracts(self):
        """Verify historical_contracts table UNIQUE index blocks duplicate inserts."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO historical_contracts 
            VALUES ('NIFTY', '2025-04-17', 23300.0, 'CE', 'NSE_FO|123456', 'NSE', 'now', 'TEST')
            """
        )
        conn.commit()

        # Duplicate insert on Primary Key should raise IntegrityError
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute(
                """
                INSERT INTO historical_contracts 
                VALUES ('NIFTY', '2025-04-17', 23300.0, 'CE', 'NSE_FO|654321', 'NSE', 'now', 'TEST')
                """
            )
            conn.commit()
        conn.close()

    def test_17_database_persistence_across_instances(self):
        """Verify data saved by one provider instance persists for subsequent instances."""
        self.provider._save_expiries_to_cache("NIFTY", ["2025-04-17"], "TEST")

        # Create a brand new instance pointing to same file
        new_provider = HistoricalContractProvider(self.db_path)
        exp = new_provider.get_expiries("NIFTY")
        self.assertEqual(exp, ["2025-04-17"])

    def test_18_get_expiries_nifty(self):
        """Verify get_expiries returns a list of expiries for NIFTY."""
        exp = self.provider.get_expiries("NIFTY")
        self.assertTrue(len(exp) > 0)
        self.assertIsInstance(exp[0], str)

    def test_19_get_expiries_banknifty(self):
        """Verify get_expiries returns a list of expiries for BANKNIFTY."""
        exp = self.provider.get_expiries("BANKNIFTY")
        self.assertTrue(len(exp) > 0)

    def test_20_get_option_contracts_nifty(self):
        """Verify NIFTY contracts load properly."""
        contracts = self.provider.get_option_contracts("NIFTY", "2025-04-17")
        self.assertTrue(len(contracts) > 0)

    def test_21_get_option_contracts_banknifty(self):
        """Verify BANKNIFTY contracts load properly."""
        contracts = self.provider.get_option_contracts("BANKNIFTY", "2025-04-17")
        self.assertTrue(len(contracts) > 0)

    def test_22_resolve_contract_nifty_fallback(self):
        """Verify resolution of NIFTY 23300 CE option contract on 2025-04-17."""
        key = self.provider.resolve_contract("NIFTY", "2025-04-17", 23300.0, "CE")
        self.assertTrue(key.startswith("NSE_FO|"))

if __name__ == "__main__":
    unittest.main()
