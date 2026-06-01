import unittest
from datetime import datetime
import pandas as pd
from v2.types import StrikeMode, ExpiryMode, OptionType, Timeframe
from v2.config import BacktestConfig
from v2.resolvers import (
    HistoricalStrikeResolver, 
    HistoricalExpiryResolver, 
    HistoricalContractResolver,
    ContractMasterCache,
    MockExpiryProvider,
    ExpiryCalendarProvider
)

class TestV2ConfigSchema(unittest.TestCase):
    def test_valid_config(self):
        payload = {
            "underlying_instrument_key": "NSE_INDEX|Nifty 50",
            "timeframe": "1m",
            "start_date": "2026-05-25",
            "end_date": "2026-05-29",
            "strategy_name": "heikin_ashi_gar",
            "strategy_params": {"candle_limit": 10},
            "option_type_preference": "DYNAMIC",
            "strike_selection": {"mode": "ATM"},
            "expiry_selection": {"mode": "CURRENT_WEEKLY", "roll_threshold_hours": 2.0},
            "risk_management": {
                "target_type": "percent",
                "target_value": 3.0,
                "stop_loss_type": "percent",
                "stop_loss_value": 1.0,
                "trailing_sl_gap": 0.0,
                "max_holding_candles": 10,
                "cutoff_time": "15:15"
            },
            "execution": {
                "brokerage_flat": 20.0,
                "slippage_pct": 0.05,
                "lot_size": 1,
                "initial_balance": 100000.0
            }
        }
        for mode in [StrikeMode.ATM, StrikeMode.OTM_1, StrikeMode.ITM_1, StrikeMode.ATM_PLUS_1]:
            payload["strike_selection"]["mode"] = mode.value
            config = BacktestConfig(**payload)
            self.assertEqual(config.strike_selection.mode, mode)

    def test_invalid_enum_validation(self):
        payload = {
            "underlying_instrument_key": "NSE_INDEX|Nifty 50",
            "timeframe": "invalid_tf",
            "start_date": "2026-05-25",
            "end_date": "2026-05-29",
            "strategy_name": "heikin_ashi_gar",
            "option_type_preference": "DYNAMIC",
        }
        with self.assertRaises(Exception):
            BacktestConfig(**payload)

class TestHistoricalStrikeResolver(unittest.TestCase):
    def test_nifty_ce_moneyness(self):
        # NIFTY spot = 22000. step = 50.
        # ATM: 22000
        # OTM_1: 22050 (Higher strike)
        # ITM_1: 21950 (Lower strike)
        res_atm = HistoricalStrikeResolver.resolve("NIFTY", 22000.0, StrikeMode.ATM, OptionType.CE)
        self.assertEqual(res_atm["resolved_strike"], 22000.0)
        self.assertEqual(res_atm["classification"], "ATM")

        res_otm = HistoricalStrikeResolver.resolve("NIFTY", 22000.0, StrikeMode.OTM_1, OptionType.CE)
        self.assertEqual(res_otm["resolved_strike"], 22050.0)
        self.assertEqual(res_otm["classification"], "OTM")

        res_itm = HistoricalStrikeResolver.resolve("NIFTY", 22000.0, StrikeMode.ITM_1, OptionType.CE)
        self.assertEqual(res_itm["resolved_strike"], 21950.0)
        self.assertEqual(res_itm["classification"], "ITM")

    def test_nifty_pe_moneyness(self):
        # NIFTY spot = 22000. step = 50.
        # ATM: 22000
        # OTM_1: 21950 (Lower strike)
        # ITM_1: 22050 (Higher strike)
        res_atm = HistoricalStrikeResolver.resolve("NIFTY", 22000.0, StrikeMode.ATM, OptionType.PE)
        self.assertEqual(res_atm["resolved_strike"], 22000.0)
        self.assertEqual(res_atm["classification"], "ATM")

        res_otm = HistoricalStrikeResolver.resolve("NIFTY", 22000.0, StrikeMode.OTM_1, OptionType.PE)
        self.assertEqual(res_otm["resolved_strike"], 21950.0)
        self.assertEqual(res_otm["classification"], "OTM")

        res_itm = HistoricalStrikeResolver.resolve("NIFTY", 22000.0, StrikeMode.ITM_1, OptionType.PE)
        self.assertEqual(res_itm["resolved_strike"], 22050.0)
        self.assertEqual(res_itm["classification"], "ITM")

    def test_banknifty_ce_moneyness(self):
        # BANKNIFTY spot = 48000. step = 100.
        # ATM: 48000
        # OTM_2: 48200 (Higher strike)
        # ITM_2: 47800 (Lower strike)
        res_otm = HistoricalStrikeResolver.resolve("BANKNIFTY", 48000.0, StrikeMode.OTM_2, OptionType.CE)
        self.assertEqual(res_otm["resolved_strike"], 48200.0)
        self.assertEqual(res_otm["classification"], "OTM")

        res_itm = HistoricalStrikeResolver.resolve("BANKNIFTY", 48000.0, StrikeMode.ITM_2, OptionType.CE)
        self.assertEqual(res_itm["resolved_strike"], 47800.0)
        self.assertEqual(res_itm["classification"], "ITM")

    def test_banknifty_pe_moneyness(self):
        # BANKNIFTY spot = 48000. step = 100.
        # ATM: 48000
        # OTM_2: 47800 (Lower strike)
        # ITM_2: 48200 (Higher strike)
        res_otm = HistoricalStrikeResolver.resolve("BANKNIFTY", 48000.0, StrikeMode.OTM_2, OptionType.PE)
        self.assertEqual(res_otm["resolved_strike"], 47800.0)
        self.assertEqual(res_otm["classification"], "OTM")

        res_itm = HistoricalStrikeResolver.resolve("BANKNIFTY", 48000.0, StrikeMode.ITM_2, OptionType.PE)
        self.assertEqual(res_itm["resolved_strike"], 48200.0)
        self.assertEqual(res_itm["classification"], "ITM")

    def test_backward_compatibility(self):
        # Legacy ATM+1 CE -> OTM_1 (22050)
        res_plus_ce = HistoricalStrikeResolver.resolve("NIFTY", 22000.0, StrikeMode.ATM_PLUS_1, OptionType.CE)
        self.assertEqual(res_plus_ce["resolved_strike"], 22050.0)
        self.assertEqual(res_plus_ce["classification"], "OTM")

        # Legacy ATM+1 PE -> ITM_1 (22050)
        res_plus_pe = HistoricalStrikeResolver.resolve("NIFTY", 22000.0, StrikeMode.ATM_PLUS_1, OptionType.PE)
        self.assertEqual(res_plus_pe["resolved_strike"], 22050.0)
        self.assertEqual(res_plus_pe["classification"], "ITM")

class TestHistoricalExpiryResolver(unittest.TestCase):
    def test_expiry_resolver_with_calendar_provider(self):
        HistoricalExpiryResolver.set_provider(MockExpiryProvider())
        signal_time = datetime.fromisoformat("2026-05-25T10:00:00")
        expiry = HistoricalExpiryResolver.resolve("NIFTY", signal_time, ExpiryMode.CURRENT_WEEKLY)
        self.assertEqual(expiry, "2026-05-28")

        expiry_next = HistoricalExpiryResolver.resolve("NIFTY", signal_time, ExpiryMode.NEXT_WEEKLY)
        self.assertEqual(expiry_next, "2026-06-04")

        class CustomProvider(ExpiryCalendarProvider):
            def get_expiries(self, index_name: str) -> list:
                return ["2026-10-10", "2026-10-17"]

        HistoricalExpiryResolver.set_provider(CustomProvider())
        sig_time_custom = datetime.fromisoformat("2026-10-01T10:00:00")
        expiry_custom = HistoricalExpiryResolver.resolve("NIFTY", sig_time_custom, ExpiryMode.CURRENT_WEEKLY)
        self.assertEqual(expiry_custom, "2026-10-10")

        # Restore MockProvider
        HistoricalExpiryResolver.set_provider(MockExpiryProvider())

class TestContractMasterCache(unittest.TestCase):
    def test_cache_preload_and_lookup(self):
        cache = ContractMasterCache()
        cache.preload()
        self.assertTrue(cache._is_loaded)
        
        key = cache.lookup("NIFTY", 27000.0, "2026-06-30", "CE")
        self.assertEqual(key, "NSE_FO|50973")

        with self.assertRaises(ValueError):
            cache.lookup("NIFTY", 99999.0, "2026-06-30", "CE")

class TestEngineRouting(unittest.TestCase):
    def test_routing_v2(self):
        from app import start_engine, StartEngineModel
        
        req = StartEngineModel(
            mode="BACKTEST",
            lot_size=1,
            live_protection=False,
            expiry="2025-04-17",
            option_type="CE",
            strike="OTM_1",
            exchange="NSE",
            index_name="NIFTY",
            start_date="2025-04-15",
            end_date="2025-04-15",
            timeframe="1minute",
            max_candles=10,
            cutoff_time="15:15",
            brokerage_flat=20.0,
            slippage_pct=0.05,
            initial_balance=100000.0,
            strategy="heikin_ashi_gar",
            five_ema_period=5,
            five_ema_rr=3.0,
            live_trading=False,
            engine_version="v2"
        )
        
        res = start_engine(req)
        self.assertEqual(res["status"], "accepted")
        self.assertEqual(res["engine"], "v2")
        self.assertIn("configuration", res)
        self.assertEqual(res["configuration"]["underlying_instrument_key"], "NSE_INDEX|Nifty 50")
        self.assertEqual(res["configuration"]["strike_selection"]["mode"], "OTM_1")

if __name__ == "__main__":
    unittest.main()
