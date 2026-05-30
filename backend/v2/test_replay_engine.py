import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, time as datetime_time, timedelta
import pandas as pd

from v2.config import BacktestConfig, StrikeConfig, ExpiryConfig
from v2.types import StrikeMode, ExpiryMode, Timeframe, OptionType
from v2.replay_engine import HistoricalReplayEngine, get_index_short_name, resample_candles
from v2.replay_models import ReplaySignalEvent, ReplayContractEvent, ReplayTradeIntent, ReplayTimeline
from v2.signal_adapter import SignalAdapter, EmaCrossoverStrategy


class TestHistoricalReplayEngine(unittest.TestCase):

    # 1. Short name mappings tests
    def test_short_name_nifty(self):
        self.assertEqual(get_index_short_name("NSE_INDEX|Nifty 50"), "NIFTY")
        self.assertEqual(get_index_short_name("NIFTY"), "NIFTY")

    def test_short_name_banknifty(self):
        self.assertEqual(get_index_short_name("NSE_INDEX|Nifty Bank"), "BANKNIFTY")
        self.assertEqual(get_index_short_name("BANKNIFTY"), "BANKNIFTY")

    def test_short_name_finnifty(self):
        self.assertEqual(get_index_short_name("NSE_INDEX|Nifty Fin Service"), "FINNIFTY")

    def test_short_name_midcpnifty(self):
        self.assertEqual(get_index_short_name("NSE_INDEX|NIFTY MID SELECT"), "MIDCPNIFTY")

    def test_short_name_sensex(self):
        self.assertEqual(get_index_short_name("BSE_INDEX|SENSEX"), "SENSEX")

    def test_short_name_bankex(self):
        self.assertEqual(get_index_short_name("BSE_INDEX|BANKEX"), "BANKEX")

    def test_short_name_unknown(self):
        self.assertEqual(get_index_short_name("CUSTOM_INDEX"), "CUSTOM_INDEX")

    # 2. Resampling tests
    def test_resample_empty(self):
        self.assertEqual(resample_candles([], "5m"), [])

    def test_resample_smaller_tf_10s(self):
        candles = [{"timestamp": datetime(2025, 4, 15, 9, 15), "open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "volume": 100}]
        res = resample_candles(candles, "10s")
        self.assertEqual(len(res), 1)

    def test_resample_smaller_tf_30s(self):
        candles = [{"timestamp": datetime(2025, 4, 15, 9, 15), "open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "volume": 100}]
        res = resample_candles(candles, "30s")
        self.assertEqual(len(res), 1)

    def test_resample_1m_to_5m(self):
        base_time = datetime(2025, 4, 15, 9, 15)
        candles = []
        for i in range(10):
            candles.append({
                "timestamp": base_time + timedelta(minutes=i),
                "open": 100.0 + i,
                "high": 105.0 + i,
                "low": 95.0 + i,
                "close": 102.0 + i,
                "volume": 100
            })
        res = resample_candles(candles, "5m")
        self.assertEqual(len(res), 2)
        # Verify first 5m candle aggregates correctly (indices 0 to 4)
        self.assertEqual(res[0]["timestamp"], base_time)
        self.assertEqual(res[0]["open"], 100.0)
        self.assertEqual(res[0]["high"], 109.0) # max of 105+i
        self.assertEqual(res[0]["low"], 95.0)   # min of 95+i
        self.assertEqual(res[0]["close"], 106.0) # close of 5th candle (i=4)
        self.assertEqual(res[0]["volume"], 500)  # sum of volume

    def test_resample_1m_to_15m(self):
        base_time = datetime(2025, 4, 15, 9, 15)
        candles = []
        for i in range(20):
            candles.append({
                "timestamp": base_time + timedelta(minutes=i),
                "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 10
            })
        res = resample_candles(candles, "15m")
        # Aggregations: [9:15 to 9:29] starting at 9:15 -> 15 candles. Next start at 9:30 -> 5 candles.
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["volume"], 150)
        self.assertEqual(res[1]["volume"], 50)

    # 3. Future leakage protection tests
    def test_evaluation_history_growth(self):
        # Verify that during the replay iteration, the slice size increases by exactly 1 and no future items exist
        engine = HistoricalReplayEngine("backend/v2/test_contracts_cache.db")
        mock_candles = [{"timestamp": datetime(2025, 4, 15, 9, 15 + i), "close": 100.0 + i} for i in range(5)]
        
        with patch.object(SignalAdapter, "evaluate", return_value=("HOLD", {})) as mock_eval:
            config = BacktestConfig(
                underlying_instrument_key="NIFTY",
                timeframe=Timeframe.MIN_1,
                start_date="2025-04-15",
                end_date="2025-04-15",
                strategy_name="EMA",
                strategy_params={"fast_period": 2, "slow_period": 3}
            )
            with patch.object(engine.spot_loader, "load_candles", return_value=mock_candles):
                engine.run(config)
                
            self.assertEqual(mock_eval.call_count, 5)
            # Verify the length of the list passed to evaluate at each step
            for idx, call in enumerate(mock_eval.call_args_list):
                history_passed = call[0][0]
                self.assertEqual(len(history_passed), idx + 1)
                # Verify no look-ahead (last item in history is the current step item)
                self.assertEqual(history_passed[-1]["timestamp"], mock_candles[idx]["timestamp"])

    # 4. Strategy Adapter tests
    def test_adapter_invalid_strategy(self):
        with self.assertRaises(ValueError):
            SignalAdapter("nonexistent_strategy", {})

    def test_adapter_hold_on_empty(self):
        adapter = SignalAdapter("EMA", {"fast_period": 2, "slow_period": 3})
        action, info = adapter.evaluate([])
        self.assertEqual(action, "HOLD")

    def test_ema_crossover_buy_and_sell_signals(self):
        # Setup underlying candles to trigger crossover
        # Fast EMA = 2, Slow EMA = 3.
        # When Fast crosses above Slow -> BUY. When Fast crosses below Slow -> EXIT (SELL).
        # We need slow_period + 2 = 5 candles minimum.
        # Let's verify using the custom EmaCrossoverStrategy
        df = pd.DataFrame([
            {"timestamp": datetime(2025, 4, 15, 9, 15), "close": 100.0},
            {"timestamp": datetime(2025, 4, 15, 9, 16), "close": 99.0},
            {"timestamp": datetime(2025, 4, 15, 9, 17), "close": 98.0},
            {"timestamp": datetime(2025, 4, 15, 9, 18), "close": 97.0},
            {"timestamp": datetime(2025, 4, 15, 9, 19), "close": 105.0}, # fast crosses up here
            {"timestamp": datetime(2025, 4, 15, 9, 20), "close": 90.0},  # fast crosses down here
        ])
        strategy = EmaCrossoverStrategy(fast_period=2, slow_period=3)
        
        # Test BUY
        action, info = strategy.evaluate(df.iloc[:5])
        self.assertEqual(action, "BUY")
        self.assertTrue(strategy.is_holding)
        
        # Test EXIT
        action, info = strategy.evaluate(df.iloc[:6])
        self.assertEqual(action, "EXIT")
        self.assertFalse(strategy.is_holding)

    # 5. Strike Resolution tests
    def test_strike_resolution_atm(self):
        from v2.resolvers import HistoricalStrikeResolver
        # NIFTY step is 50. ATM for 23316.75 is 23300.
        res = HistoricalStrikeResolver.resolve("NIFTY", 23316.75, StrikeMode.ATM, OptionType.CE)
        self.assertEqual(res["resolved_strike"], 23300.0)
        self.assertEqual(res["classification"], "ATM")

    # 6. Expiry Resolution tests
    def test_expiry_resolution(self):
        from v2.resolvers import HistoricalExpiryResolver, MockExpiryProvider
        provider = MockExpiryProvider()
        HistoricalExpiryResolver.set_provider(provider)
        expiry = HistoricalExpiryResolver.resolve("NIFTY", datetime(2025, 4, 15), ExpiryMode.CURRENT_WEEKLY)
        self.assertEqual(expiry, "2026-05-28")

    # 7. Model serialization tests
    def test_trade_intent_model(self):
        intent = ReplayTradeIntent(
            timestamp=datetime(2025, 4, 15, 10, 0),
            underlying="NIFTY",
            signal="BUY_INTENT",
            spot_price=23316.75,
            strike=23300.0,
            expiry="2025-04-17",
            option_type="CE",
            instrument_key="NSE_FO|48236|17-04-2025",
            premium_price=154.25,
            source="UPSTOX_EXPIRED_API"
        )
        self.assertEqual(intent.signal, "BUY_INTENT")
        self.assertEqual(intent.premium_price, 154.25)

    def test_timeline_model(self):
        timeline = ReplayTimeline(underlying="NIFTY", timeframe="5m", strategy="EMA")
        self.assertEqual(len(timeline.events), 0)

    # 8. Replay Engine premium lookup tests
    @patch("v2.replay_engine.OptionHistoricalLoader.load_candles")
    def test_premium_lookup_match(self, mock_load):
        engine = HistoricalReplayEngine("backend/v2/test_contracts_cache.db")
        mock_load.return_value = [
            {"timestamp": datetime(2025, 4, 15, 10, 0), "close": 154.25},
            {"timestamp": datetime(2025, 4, 15, 10, 5), "close": 160.0}
        ]
        res = engine._lookup_premium(
            index_name="NIFTY",
            strike=23300.0,
            expiry="2025-04-17",
            option_type="CE",
            timeframe="1m",
            timestamp=datetime(2025, 4, 15, 10, 5),
            day_date=datetime(2025, 4, 15)
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["close"], 160.0)

    @patch("v2.replay_engine.OptionHistoricalLoader.load_candles")
    def test_premium_lookup_no_match(self, mock_load):
        engine = HistoricalReplayEngine("backend/v2/test_contracts_cache.db")
        mock_load.return_value = [
            {"timestamp": datetime(2025, 4, 15, 10, 0), "close": 154.25}
        ]
        res = engine._lookup_premium(
            index_name="NIFTY",
            strike=23300.0,
            expiry="2025-04-17",
            option_type="CE",
            timeframe="1m",
            timestamp=datetime(2025, 4, 15, 10, 5),
            day_date=datetime(2025, 4, 15)
        )
        self.assertIsNone(res)

    # 9. Audit Logging tests
    @patch("v2.replay_audit.logger.info")
    def test_audit_logging_calls(self, mock_log):
        from v2.replay_audit import log_replay_event
        log_replay_event(datetime(2025, 4, 15, 10, 0), "BUY_INTENT", "23300 CE", 154.25, "UPSTOX_EXPIRED_API")
        self.assertTrue(mock_log.called)
        self.assertIn("BUY_INTENT", mock_log.call_args[0][0])
        self.assertIn("154.25", mock_log.call_args[0][0])

    # 10. Cache manager ranges with tolerance checks
    def test_cache_manager_coverage_exact(self):
        from v2.cache.manager import HistoricalDataCacheManager
        mgr = HistoricalDataCacheManager()
        cov = mgr.verify_coverage("2025-04-15T09:15:00", "2025-04-15T15:30:00", "2025-04-15T09:15:00", "2025-04-15T15:30:00")
        self.assertEqual(cov, "FULL")

    def test_cache_manager_coverage_with_tolerance(self):
        from v2.cache.manager import HistoricalDataCacheManager
        mgr = HistoricalDataCacheManager()
        # 15:29 cached close is within 5 minutes of 15:30 requested end
        cov = mgr.verify_coverage("2025-04-15T09:15:00", "2025-04-15T15:30:00", "2025-04-15T09:15:00", "2025-04-15T15:29:00")
        self.assertEqual(cov, "FULL")

    def test_cache_manager_coverage_missing(self):
        from v2.cache.manager import HistoricalDataCacheManager
        mgr = HistoricalDataCacheManager()
        cov = mgr.verify_coverage("2025-04-15T09:15:00", "2025-04-15T15:30:00", None, None)
        self.assertEqual(cov, "MISSING")

    def test_cache_manager_coverage_partial(self):
        from v2.cache.manager import HistoricalDataCacheManager
        mgr = HistoricalDataCacheManager()
        cov = mgr.verify_coverage("2025-04-15T09:15:00", "2025-04-15T15:30:00", "2025-04-15T10:00:00", "2025-04-15T14:00:00")
        self.assertEqual(cov, "PARTIAL")

    # 11. Complete Replay run integration mockup
    @patch("v2.replay_engine.OptionHistoricalLoader.load_candles")
    @patch("v2.replay_engine.HistoricalContractResolver.resolve")
    @patch("v2.replay_engine.UnderlyingHistoricalLoader.load_candles")
    def test_full_replay_run(self, mock_underlying, mock_contract, mock_opt_candles):
        # Set up underlying candles
        mock_underlying.return_value = [
            {"timestamp": datetime(2025, 4, 15, 9, 15 + i), "open": 23300.0, "high": 23300.0, "low": 23300.0, "close": 23300.0, "volume": 100}
            for i in range(10)
        ]
        # Contract and premium mocks
        mock_contract.return_value = "NSE_FO|48236|17-04-2025"
        mock_opt_candles.return_value = [
            {"timestamp": datetime(2025, 4, 15, 9, 15 + i), "close": 150.0}
            for i in range(10)
        ]
        
        engine = HistoricalReplayEngine("backend/v2/test_contracts_cache.db")
        config = BacktestConfig(
            underlying_instrument_key="NIFTY",
            timeframe=Timeframe.MIN_1,
            start_date="2025-04-15",
            end_date="2025-04-15",
            strategy_name="EMA",
            strategy_params={"fast_period": 2, "slow_period": 3}
        )
        
        # Patch evaluation to trigger a BUY and then a SELL
        with patch.object(SignalAdapter, "evaluate") as mock_eval:
            mock_eval.side_effect = [
                ("HOLD", {}),
                ("BUY", {}),  # BUY at 9:16
                ("HOLD", {}),
                ("SELL", {}), # SELL at 9:18
                ("HOLD", {}),
                ("HOLD", {}),
                ("HOLD", {}),
                ("HOLD", {}),
                ("HOLD", {}),
                ("HOLD", {})
            ]
            timeline = engine.run(config)
            
            self.assertEqual(len(timeline.events), 2)
            self.assertEqual(timeline.events[0].signal, "BUY_INTENT")
            self.assertEqual(timeline.events[1].signal, "SELL_INTENT")
            self.assertEqual(timeline.events[0].premium_price, 150.0)


if __name__ == "__main__":
    unittest.main()
