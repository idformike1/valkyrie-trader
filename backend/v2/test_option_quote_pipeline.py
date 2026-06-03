import unittest
import sys
import os
import sqlite3
from datetime import datetime
import time

sys.path.append("/Users/rajumaharjan/Documents/Anit Gravity Projects/Valkyrie/backend")

from v2.option_chain_manager import OptionChainManager
from v2.option_quote_cache import OptionQuoteCache, get_subscribed_keys
from v2.quote_health import QuoteHealthTracker
from v2.telemetry_logger import TelemetryLogger
from v2.resolvers import HistoricalExpiryResolver, HistoricalContractResolver
from database import log_trade, get_session_trades, DEFAULT_DB_PATH

class TestOptionQuotePipeline(unittest.TestCase):
    def setUp(self):
        TelemetryLogger.start_session()
        OptionQuoteCache.clear()
        QuoteHealthTracker.reset()
        self.chain_mgr = OptionChainManager()
        self.chain_mgr.active_universes.clear()
        self.chain_mgr.current_atms.clear()

    def tearDown(self):
        OptionQuoteCache.clear()
        QuoteHealthTracker.reset()
        TelemetryLogger.clear_session()

    def test_pipeline_flow(self):
        # 1. Chain initializes when spot updates
        spot_price = 22430.0  # NIFTY ATM is 22450.0
        self.chain_mgr.on_spot_update("NSE_INDEX|Nifty 50", spot_price)
        
        active_contracts = self.chain_mgr.get_active_contracts()
        self.assertEqual(len(active_contracts), 10, "Expected 10 active contracts (5 strikes CE & PE)")
        
        # Check telemetry for CHAIN_INITIALIZED and NEW_ATM_DETECTED
        logs = TelemetryLogger.get_logs()
        messages = [log.message for log in logs]
        self.assertTrue(any("CHAIN_INITIALIZED" in m for m in messages), "Should log CHAIN_INITIALIZED event")
        self.assertTrue(any("NEW_ATM_DETECTED" in m for m in messages), "Should log NEW_ATM_DETECTED event")
        
        # 2. Contracts are subscribed
        sub_keys = get_subscribed_keys()
        self.assertEqual(len(sub_keys), 10, "Expected 10 keys subscribed in cache")
        for contract in active_contracts:
            self.assertIn(contract, sub_keys, f"Contract {contract} should be in sub_keys")

        # 3. Quotes populate cache
        test_key = active_contracts[0]
        OptionQuoteCache.update(
            instrument_key=test_key,
            ltp=150.0,
            bid=148.0,
            ask=152.0,
            volume=1000,
            oi=5000,
            timestamp=datetime.utcnow()
        )
        
        quote = OptionQuoteCache.get(test_key)
        self.assertIsNotNone(quote)
        self.assertEqual(quote.ltp, 150.0)
        self.assertEqual(quote.bid, 148.0)
        self.assertEqual(quote.ask, 152.0)
        
        # 4. Cache updates on every tick (verify telemetry logs it)
        OptionQuoteCache.update(
            instrument_key=test_key,
            ltp=151.5,
            bid=149.0,
            ask=153.0,
            volume=1050,
            oi=5100,
            timestamp=datetime.utcnow()
        )
        quote = OptionQuoteCache.get(test_key)
        self.assertEqual(quote.ltp, 151.5)
        
        logs = TelemetryLogger.get_logs()
        messages = [log.message for log in logs]
        self.assertTrue(any("QUOTE_UPDATED" in m for m in messages), "Should emit QUOTE_UPDATED event")

        # 5. Health metrics populate
        # Trigger some hits and misses and a synthetic fill
        QuoteHealthTracker.record_hit()
        QuoteHealthTracker.record_miss()
        QuoteHealthTracker.record_synthetic_fill()
        
        health = QuoteHealthTracker.get_health_metrics()
        self.assertEqual(health["subscribed_contracts"], 10)
        self.assertEqual(health["quote_hits"], 1)
        self.assertEqual(health["quote_misses"], 1)
        self.assertEqual(health["synthetic_fill_count"], 1)
        self.assertGreater(health["live_quotes"], 0)
        
        # 6. execution_source persists
        test_db = "test_valkyrie_trades.db"
        if os.path.exists(test_db):
            os.remove(test_db)
            
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                instrument_key TEXT,
                trading_symbol TEXT,
                type TEXT,
                price REAL,
                quantity INTEGER,
                stop_loss REAL,
                target_price REAL,
                reason TEXT,
                pnl REAL,
                timestamp TEXT,
                upstox_order_id TEXT,
                execution_source TEXT
            )
        """)
        conn.commit()
        conn.close()
        
        log_trade(
            session_id=999,
            instrument_key=test_key,
            trading_symbol="NIFTY26JUN22450CE",
            trade_type="BUY",
            price=150.0,
            quantity=75,
            stop_loss=120.0,
            target_price=200.0,
            reason="Signal entry",
            pnl=0.0,
            execution_source="LIVE_QUOTE",
            db_path=test_db
        )
        
        trades = get_session_trades(session_id=999, db_path=test_db)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["execution_source"], "LIVE_QUOTE")
        
        if os.path.exists(test_db):
            os.remove(test_db)

    def test_dynamic_chain_rolling(self):
        # 1. Initialize
        spot_price = 22430.0  # ATM strike is 22450.0
        self.chain_mgr.on_spot_update("NSE_INDEX|Nifty 50", spot_price)
        init_contracts = set(self.chain_mgr.get_active_contracts())
        
        # 2. Roll beyond strike interval (e.g. step is 50 for NIFTY, 22450 -> 22520, ATM strike becomes 22500)
        new_spot_price = 22520.0
        self.chain_mgr.on_spot_update("NSE_INDEX|Nifty 50", new_spot_price)
        rolled_contracts = set(self.chain_mgr.get_active_contracts())
        
        # Ensure ATM changed
        self.assertEqual(self.chain_mgr.current_atms["NIFTY"], 22500.0)
        
        # Telemetry should contain CHAIN_ROLLED
        logs = TelemetryLogger.get_logs()
        messages = [log.message for log in logs]
        self.assertTrue(any("CHAIN_ROLLED" in m for m in messages), "Should log CHAIN_ROLLED event")
        
        # Check that we subscribed new and unsubscribed old contracts
        self.assertNotEqual(init_contracts, rolled_contracts, "Universes should differ after ATM roll")
        
if __name__ == "__main__":
    unittest.main()
