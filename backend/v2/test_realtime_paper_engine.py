import unittest
import sys
from datetime import datetime

# Add workspace backend to path
sys.path.append("/Users/rajumaharjan/Documents/Anit Gravity Projects/Valkyrie/backend")

from v2.config import BacktestConfig
from v2.position_manager import PositionManager
from v2.position_ledger import PositionLedger
from v2.realtime_signal_runner import RealtimeSignalRunner
from v2.telemetry_logger import TelemetryLogger
from v2.metrics_engine import MetricsEngine
from v2.option_quote_cache import OptionQuoteCache

class TestRealtimePaperEngine(unittest.TestCase):
    def setUp(self):
        # 1. Setup a standard V2 Config for Real-Time Paper Trading
        self.payload = {
            "underlying_instrument_key": "NIFTY",
            "timeframe": "1m",
            "start_date": "2026-06-02",
            "end_date": "2026-06-02",
            "strategy_name": "five_ema",
            "strategy_params": {
                "ema_period": 5,
                "rr_ratio": 3.0,
                "cut_off_time": "15:15"
            },
            "option_type_preference": "DYNAMIC",
            "strike_selection": {"mode": "ATM"},
            "expiry_selection": {"mode": "CURRENT_WEEKLY", "roll_threshold_hours": 2.0},
            "risk_management": {
                "target_type": "percent",
                "target_value": 0.0,
                "stop_loss_type": "percent",
                "stop_loss_value": 0.0,
                "trailing_sl_gap": 0.0,
                "max_holding_candles": 15,
                "cutoff_time": "15:15"
            },
            "execution": {
                "brokerage_flat": 20.0,
                "slippage_pct": 0.0,
                "lot_size": 1,
                "initial_balance": 100000.0
            }
        }
        # Force a mock expiry provider for deterministic tests
        from v2.resolvers import HistoricalExpiryResolver, ExpiryCalendarProvider, LiveExpiryProvider
        class TestExpiryProvider(ExpiryCalendarProvider):
            def get_expiries(self, index_name: str) -> list:
                return ["2026-06-04", "2026-06-11"]
        self.original_provider = LiveExpiryProvider()
        HistoricalExpiryResolver.set_provider(TestExpiryProvider())

        self.config = BacktestConfig(**self.payload)
        self.ledger = PositionLedger()
        self.position_manager = PositionManager(ledger=self.ledger)
        self.runner = RealtimeSignalRunner(self.config, self.position_manager)

    def tearDown(self):
        from v2.resolvers import HistoricalExpiryResolver
        if hasattr(self, "original_provider"):
            HistoricalExpiryResolver.set_provider(self.original_provider)

    def test_end_to_end_realtime_execution(self):
        TelemetryLogger.start_session()
        OptionQuoteCache.clear()
        
        # 2. Construct 10 synthetic completed NIFTY spot candles
        base_time = datetime(2026, 6, 2, 9, 15)
        synthetic_candles = [
            {"timestamp": base_time.isoformat(), "open": 99.0, "high": 100.0, "low": 99.0, "close": 100.0, "volume": 100},
            {"timestamp": datetime(2026, 6, 2, 9, 16).isoformat(), "open": 98.2, "high": 98.2, "low": 97.0, "close": 98.0, "volume": 100},
            {"timestamp": datetime(2026, 6, 2, 9, 17).isoformat(), "open": 96.1, "high": 96.1, "low": 95.0, "close": 96.0, "volume": 100},
            {"timestamp": datetime(2026, 6, 2, 9, 18).isoformat(), "open": 94.1, "high": 94.1, "low": 93.0, "close": 94.0, "volume": 100},
            {"timestamp": datetime(2026, 6, 2, 9, 19).isoformat(), "open": 92.1, "high": 92.1, "low": 91.0, "close": 92.0, "volume": 100},
            # Candle 6: Completed high (90.1) is below EMA (~94). Sets Alert Candle.
            {"timestamp": datetime(2026, 6, 2, 9, 20).isoformat(), "open": 90.1, "high": 90.1, "low": 89.0, "close": 90.0, "volume": 100},
            # Candle 7: Breakout -> BUY
            {"timestamp": datetime(2026, 6, 2, 9, 21).isoformat(), "open": 90.0, "high": 92.0, "low": 89.5, "close": 92.0, "volume": 100},
            # Candle 8: Holding
            {"timestamp": datetime(2026, 6, 2, 9, 22).isoformat(), "open": 92.0, "high": 96.0, "low": 94.0, "close": 95.0, "volume": 100},
            # Candle 9: Holding
            {"timestamp": datetime(2026, 6, 2, 9, 23).isoformat(), "open": 95.0, "high": 99.0, "low": 97.0, "close": 98.0, "volume": 100},
            # Candle 10: Target Hit -> SELL
            {"timestamp": datetime(2026, 6, 2, 9, 24).isoformat(), "open": 98.0, "high": 102.0, "low": 98.0, "close": 102.0, "volume": 100},
        ]

        # 3. Stream candles into runner
        actions = []
        for candle in synthetic_candles:
            action, data = self.runner.on_candle(candle)
            actions.append(action)

        self.assertEqual(actions[6], "BUY")
        self.assertEqual(actions[9], "SELL")
        self.assertIsNone(self.position_manager.active_position)
        self.assertEqual(len(self.ledger.positions), 1)

        TelemetryLogger.clear_session()

    def test_live_option_premium_fills(self):
        """
        PHASE P1.1A VALIDATION:
        Injects a mock options quote inside OptionQuoteCache and verifies
        that BUY fills exactly at the ask price and SELL fills exactly at the bid price,
        completely bypassing synthetic pricing.
        """
        TelemetryLogger.start_session()
        OptionQuoteCache.clear()

        # Target option contract details will resolve to NIFTY CE current weekly ATM strike
        # Let's pre-populate the Quote cache for NIFTY ATM CE
        # Strike ATM for spot 92.0 is 100.0 (since NIFTY step is 50)
        # Expiry current weekly is 2026-06-04
        instrument_key = "NIFTY_2026-06-04_100_CE"  # Resolved fallback key
        
        # Inject real market quote
        # LTP = 100.0, Bid = 98.0 (sell target), Ask = 102.0 (buy target)
        OptionQuoteCache.update(
            instrument_key=instrument_key,
            ltp=100.0,
            bid=98.0,
            ask=102.0,
            volume=5000,
            oi=25000.0,
            timestamp=datetime.utcnow()
        )

        base_time = datetime(2026, 6, 2, 9, 15)
        synthetic_candles = [
            {"timestamp": base_time.isoformat(), "open": 99.0, "high": 100.0, "low": 99.0, "close": 100.0, "volume": 100},
            {"timestamp": datetime(2026, 6, 2, 9, 16).isoformat(), "open": 98.2, "high": 98.2, "low": 97.0, "close": 98.0, "volume": 100},
            {"timestamp": datetime(2026, 6, 2, 9, 17).isoformat(), "open": 96.1, "high": 96.1, "low": 95.0, "close": 96.0, "volume": 100},
            {"timestamp": datetime(2026, 6, 2, 9, 18).isoformat(), "open": 94.1, "high": 94.1, "low": 93.0, "close": 94.0, "volume": 100},
            {"timestamp": datetime(2026, 6, 2, 9, 19).isoformat(), "open": 92.1, "high": 92.1, "low": 91.0, "close": 92.0, "volume": 100},
            # Candle 6: Completed high (90.1) is below EMA (~94). Sets Alert Candle.
            {"timestamp": datetime(2026, 6, 2, 9, 20).isoformat(), "open": 90.1, "high": 90.1, "low": 89.0, "close": 90.0, "volume": 100},
            # Candle 7: Breakout -> BUY (Ask price 102.0 is expected)
            {"timestamp": datetime(2026, 6, 2, 9, 21).isoformat(), "open": 90.0, "high": 92.0, "low": 89.5, "close": 92.0, "volume": 100},
            # Candle 8: Holding
            {"timestamp": datetime(2026, 6, 2, 9, 22).isoformat(), "open": 92.0, "high": 96.0, "low": 94.0, "close": 95.0, "volume": 100},
            # Candle 9: Holding
            {"timestamp": datetime(2026, 6, 2, 9, 23).isoformat(), "open": 95.0, "high": 99.0, "low": 97.0, "close": 98.0, "volume": 100},
            # Candle 10: Target Hit -> SELL (Bid price 98.0 is expected)
            {"timestamp": datetime(2026, 6, 2, 9, 24).isoformat(), "open": 98.0, "high": 102.0, "low": 98.0, "close": 102.0, "volume": 100},
        ]

        # Stream candles into runner
        actions = []
        for candle in synthetic_candles:
            action, data = self.runner.on_candle(candle)
            actions.append(action)

        # Confirm actions matched correctly
        self.assertEqual(actions[6], "BUY")
        self.assertEqual(actions[9], "SELL")

        # Verify exact fills
        trade = self.ledger.accounting_records[0]
        # Gross PnL: (98.0 - 102.0) * 65 = -260.0 INR
        self.assertAlmostEqual(trade.entry_premium, 102.0)  # BUY filled at Ask
        self.assertAlmostEqual(trade.exit_premium, 98.0)    # SELL filled at Bid
        self.assertAlmostEqual(trade.gross_pnl, -260.0)

        # Check Telemetry logs
        logs = TelemetryLogger.get_logs()
        messages = [log.message for log in logs]
        
        # Verify Telemetry events
        has_quote_received = any("QUOTE_RECEIVED" in m for m in messages)
        has_real_fill = any("REAL_FILL_USED" in m for m in messages)
        has_synthetic_fallback = any("SYNTHETIC_FILL_USED" in m for m in messages)

        self.assertTrue(has_quote_received, "Telemetry must emit 'QUOTE_RECEIVED'")
        self.assertTrue(has_real_fill, "Telemetry must emit 'REAL_FILL_USED'")
        self.assertFalse(has_synthetic_fallback, "Should NOT use synthetic fallback when quote is available!")

        print("\n=== Phase P1.1A Live Options Feed Integration Certified ===")
        print(f"Option Contract: {instrument_key}")
        print(f"BUY filled at Ask price: INR {trade.entry_premium:.2f}")
        print(f"SELL filled at Bid price: INR {trade.exit_premium:.2f}")
        print(f"Resulting Gross Trade P&L: INR {trade.gross_pnl:.2f}")
        print("Success! Live option market quote feed correctly utilized and synthetic pricing bypassed entirely.\n")

        TelemetryLogger.clear_session()
        OptionQuoteCache.clear()

if __name__ == "__main__":
    unittest.main()
