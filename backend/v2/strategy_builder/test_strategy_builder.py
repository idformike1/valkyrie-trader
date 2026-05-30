import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime, timedelta
from v2.strategy_builder.strategy_definition import StrategyDefinition
from v2.strategy_builder.indicator_registry import IndicatorRegistry
from v2.strategy_builder.rule_engine import RuleEngine
from v2.strategy_builder.signal_pipeline import SignalPipeline, invert_condition
from v2.strategy_builder.risk_engine import RiskEngine
from v2.strategy_builder.strategy_validator import StrategyValidator
from v2.config import BacktestConfig
from v2.types import Timeframe

class TestStrategyBuilder(unittest.TestCase):
    def setUp(self):
        # Create a sample strategy definition dict
        self.strategy_dict = {
            "strategy_id": "test_strat",
            "name": "EMA Crossover Test",
            "description": "Crosses fast over slow",
            "schema_version": "2.0.0",
            "signal": {
                "indicators": {
                    "ema_fast": { "type": "EMA", "params": { "period": 2, "source": "close" } },
                    "ema_slow": { "type": "EMA", "params": { "period": 5, "source": "close" } }
                },
                "entry_condition": {
                    "type": "crossover_up",
                    "params": { "primary": "ema_fast", "secondary": "ema_slow" }
                }
            },
            "contract": {
                "underlying": "NIFTY",
                "instrument_type": "OPTION",
                "option_type": "CE_ONLY",
                "strike": { "mode": "ATM" },
                "expiry": { "mode": "CURRENT_WEEKLY", "roll_threshold_hours": 2.0 }
            },
            "risk": {
                "position_sizing": { "mode": "FIXED_LOTS", "value": 1 },
                "stop_loss": { "type": "percent", "value": 10.0 },
                "take_profit": { "type": "percent", "value": 20.0 },
                "trailing_sl": { "type": "points", "value": 15.0 },
                "max_holding_candles": 5
            },
            "exit": {
                "exit_on_reversal": True,
                "time_exit": { "cutoff_time": "15:15" }
            }
        }

    # 1. Test StrategyValidator
    def test_validator_valid(self):
        is_valid, errors = StrategyValidator.validate_dict(self.strategy_dict)
        self.assertTrue(is_valid, f"Validation failed with errors: {errors}")

    def test_validator_invalid_field(self):
        bad_dict = self.strategy_dict.copy()
        del bad_dict["signal"]
        is_valid, errors = StrategyValidator.validate_dict(bad_dict)
        self.assertFalse(is_valid)
        self.assertTrue(any("Missing required top-level field" in e for e in errors))

    def test_validator_invalid_indicator(self):
        bad_dict = self.strategy_dict.copy()
        bad_dict["signal"] = {
            "indicators": {
                "my_ind": { "type": "UNKNOWN_IND_XYZ", "params": {} }
            },
            "entry_condition": {
                "type": "greater_than",
                "params": { "primary": "my_ind", "value": 50 }
            }
        }
        is_valid, errors = StrategyValidator.validate_dict(bad_dict)
        self.assertFalse(is_valid)
        self.assertTrue(any("unregistered type" in e for e in errors))

    # 2. Test Indicator calculations
    def test_ema_indicator(self):
        df = pd.DataFrame({"close": [10.0, 20.0, 30.0, 40.0, 50.0]})
        ema_ind = IndicatorRegistry.get("ema")()
        res = ema_ind.calculate(df, {"period": 3}, "ema_3")
        self.assertEqual(len(res), 5)
        self.assertTrue("ema_3" not in df.columns)

    def test_heikin_ashi_indicator(self):
        df = pd.DataFrame({
            "open": [10.0, 12.0],
            "high": [15.0, 16.0],
            "low": [9.0, 11.0],
            "close": [14.0, 15.0]
        })
        ha_ind = IndicatorRegistry.get("heikin_ashi")()
        res = ha_ind.calculate(df, {}, "ha")
        self.assertEqual(len(res), 2)
        self.assertIn("ha_close", res.columns)
        self.assertIn("ha_color", res.columns)

    def test_rsi_indicator(self):
        df = pd.DataFrame({"close": [10.0, 12.0, 15.0, 13.0, 14.0, 16.0, 17.0, 15.0, 14.0, 13.0, 15.0, 17.0, 18.0, 19.0, 20.0]})
        rsi_ind = IndicatorRegistry.get("rsi")()
        res = rsi_ind.calculate(df, {"period": 5}, "rsi_5")
        self.assertEqual(len(res), 15)

    def test_macd_indicator(self):
        df = pd.DataFrame({"close": [10.0 + i for i in range(30)]})
        macd_ind = IndicatorRegistry.get("macd")()
        res = macd_ind.calculate(df, {}, "macd")
        self.assertIn("macd_macd", res.columns)

    # 3. Test RuleEngine evaluation
    def test_rule_engine_gt_lt_eq(self):
        df = pd.DataFrame({"val": [10.0, 20.0, 30.0]})
        
        cond1 = {"type": "greater_than", "params": { "primary": "val[-1]", "value": 25.0 }}
        self.assertTrue(RuleEngine.evaluate(df, cond1))
        
        cond2 = {"type": "less_than", "params": { "primary": "val[-1]", "value": 15.0 }}
        self.assertFalse(RuleEngine.evaluate(df, cond2))

        cond3 = {"type": "equal", "params": { "primary": "val[-1]", "value": 30.0 }}
        self.assertTrue(RuleEngine.evaluate(df, cond3))

    def test_rule_engine_logical_operators(self):
        df = pd.DataFrame({"val1": [10, 20], "val2": [30, 40]})
        
        cond_and = {
            "operator": "AND",
            "conditions": [
                {"type": "greater_than", "params": { "primary": "val1[-1]", "value": 15.0 }},
                {"type": "greater_than", "params": { "primary": "val2[-1]", "value": 35.0 }}
            ]
        }
        self.assertTrue(RuleEngine.evaluate(df, cond_and))

        cond_or = {
            "operator": "OR",
            "conditions": [
                {"type": "less_than", "params": { "primary": "val1[-1]", "value": 5.0 }},
                {"type": "greater_than", "params": { "primary": "val2[-1]", "value": 35.0 }}
            ]
        }
        self.assertTrue(RuleEngine.evaluate(df, cond_or))

        cond_not = {
            "operator": "NOT",
            "conditions": [
                {"type": "less_than", "params": { "primary": "val1[-1]", "value": 5.0 }}
            ]
        }
        self.assertTrue(RuleEngine.evaluate(df, cond_not))

    # 4. Test Invert Condition
    def test_invert_condition(self):
        cond = {
            "operator": "AND",
            "conditions": [
                {"type": "crossover_up", "params": {"primary": "fast", "secondary": "slow"}},
                {"type": "equal", "params": {"primary": "ha_color", "value": "GREEN"}}
            ]
        }
        inverted = invert_condition(cond)
        self.assertEqual(inverted["operator"], "OR")
        self.assertEqual(inverted["conditions"][0]["type"], "crossover_down")
        self.assertEqual(inverted["conditions"][1]["params"]["value"], "RED")

    # 5. Test RiskEngine exits
    def test_risk_engine_sl_exit(self):
        active_contract = {
            "entry_premium": 100.0,
            "highest_premium": 100.0
        }
        
        risk_config = {"stop_loss": {"type": "percent", "value": 10.0}}
        exit_reason, exit_price = RiskEngine.evaluate_exits(
            risk_config, active_contract, current_premium=89.0, current_spot=22000.0, candles_held=2
        )
        self.assertEqual(exit_reason, "STOP_LOSS")
        self.assertEqual(exit_price, 89.0)

        exit_reason, exit_price = RiskEngine.evaluate_exits(
            risk_config, active_contract, current_premium=95.0, current_spot=22000.0, candles_held=2
        )
        self.assertIsNone(exit_reason)

    def test_risk_engine_tp_exit(self):
        active_contract = {
            "entry_premium": 100.0,
            "highest_premium": 100.0
        }
        
        risk_config = {"take_profit": {"type": "points", "value": 15.0}}
        exit_reason, exit_price = RiskEngine.evaluate_exits(
            risk_config, active_contract, current_premium=116.0, current_spot=22000.0, candles_held=2
        )
        self.assertEqual(exit_reason, "TAKE_PROFIT")

    def test_risk_engine_trailing_sl_exit(self):
        active_contract = {
            "entry_premium": 100.0,
            "highest_premium": 120.0
        }
        
        risk_config = {"trailing_sl": {"type": "points", "value": 10.0}}
        exit_reason, exit_price = RiskEngine.evaluate_exits(
            risk_config, active_contract, current_premium=109.0, current_spot=22000.0, candles_held=2
        )
        self.assertEqual(exit_reason, "TRAILING_STOP_LOSS")

    # 6. SignalPipeline Integration test
    def test_signal_pipeline(self):
        strategy_def = StrategyDefinition(**self.strategy_dict)
        pipeline = SignalPipeline(strategy_def)
        
        base_time = datetime(2025, 4, 15, 9, 15)
        df_candles = pd.DataFrame([
            {"timestamp": base_time + timedelta(minutes=i), "open": 100.0, "high": 102.0, "low": 98.0, "close": 100.0, "volume": 1000}
            for i in range(10)
        ])
        df_candles.loc[8, "close"] = 90.0
        df_candles.loc[9, "close"] = 110.0

        action, info = pipeline.evaluate(df_candles.iloc[:9])
        self.assertEqual(action, "HOLD")
        
        action, info = pipeline.evaluate(df_candles.iloc[:10])
        self.assertEqual(action, "BUY")
        self.assertTrue(pipeline.is_holding)

    @patch("v2.replay_engine.HistoricalStrikeResolver")
    @patch("v2.replay_engine.HistoricalExpiryResolver")
    @patch("v2.replay_engine.HistoricalContractResolver")
    def test_historical_replay_with_strategy_def(self, mock_contract, mock_expiry, mock_strike):
        from v2.replay_engine import HistoricalReplayEngine
        
        # 1. Setup Resolver Mocks
        mock_strike.resolve.return_value = {"resolved_strike": 22000.0, "classification": "ATM"}
        mock_expiry.resolve.return_value = "2025-04-17"
        mock_contract.resolve.return_value = "NSE_OPTION|NIFTY2541722000CE"
        
        # 2. Setup Replay Engine
        engine = HistoricalReplayEngine("./mock_db.db")
        engine.spot_loader = MagicMock()
        engine.opt_loader = MagicMock()
        
        base_time = datetime(2025, 4, 15, 9, 15)
        # Mock spot candles
        mock_spot_candles = [
            {"timestamp": base_time + timedelta(minutes=i), "open": 100.0, "high": 102.0, "low": 98.0, "close": 100.0, "volume": 1000}
            for i in range(10)
        ]
        # Cross EMA_2 over EMA_5
        mock_spot_candles[8]["close"] = 90.0
        mock_spot_candles[9]["close"] = 110.0
        
        engine.spot_loader.load_candles.return_value = mock_spot_candles
        
        # Mock premium candles
        mock_opt_candles = [
            {"timestamp": base_time + timedelta(minutes=i), "close": 50.0 + i}
            for i in range(10)
        ]
        engine.opt_loader.load_candles.return_value = mock_opt_candles
        
        # 3. Setup BacktestConfig with strategy_definition
        config_payload = {
            "underlying_instrument_key": "NSE_INDEX|Nifty 50",
            "timeframe": "1m",
            "start_date": "2025-04-15",
            "end_date": "2025-04-15",
            "strategy_definition": self.strategy_dict,
            "risk_management": {},
            "execution": {
                "brokerage_flat": 20.0,
                "slippage_pct": 0.05,
                "lot_size": 1,
                "initial_balance": 100000.0
            }
        }
        config = BacktestConfig(**config_payload)
        
        # 4. Run Backtest Replay
        timeline = engine.run(config)
        
        # We expect a BUY_INTENT signal to be executed at index 9
        buy_events = [e for e in timeline.events if e.signal == "BUY_INTENT"]
        self.assertEqual(len(buy_events), 1)
        self.assertEqual(buy_events[0].spot_price, 110.0)
        self.assertEqual(buy_events[0].premium_price, 59.0)

if __name__ == "__main__":
    unittest.main()

