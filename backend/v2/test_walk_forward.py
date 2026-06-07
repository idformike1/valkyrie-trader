import unittest
import sys
from datetime import datetime, timedelta

# Ensure backend folder is in path
sys.path.append("/Users/rajumaharjan/Documents/Anit Gravity Projects/Valkyrie/backend")

from v2.config import BacktestConfig, StrikeConfig, ExpiryConfig, RiskConfig, ExecutionConfig
from v2.types import StrikeMode, ExpiryMode, Timeframe as V2Timeframe, ExecutionModel
from v2.optimization_engine import ParameterRange
from v2.walk_forward_engine import WalkForwardAnalyzer

class TestWalkForwardEngine(unittest.TestCase):
    
    def setUp(self):
        # Base config set up
        self.payload = {
            "underlying_instrument_key": "NSE_INDEX|Nifty 50",
            "timeframe": "5m",
            "start_date": "2025-04-15",
            "end_date": "2025-04-22",
            "strategy_name": "EMA",
            "strategy_params": {
                "fastEma": 2,
                "slowEma": 3,
                "cut_off_time": "15:25"
            },
            "option_type_preference": "CE_ONLY",
            "strike_mode": "ATM",
            "expiry_mode": "CURRENT_WEEKLY",
            "initial_capital": 100000.0,
            "lot_multiplier": 1,
            "brokerage_flat": 20.0,
            "slippage_pct": 0.05
        }
        
        self.config = BacktestConfig(
            underlying_instrument_key=self.payload["underlying_instrument_key"],
            timeframe=V2Timeframe(self.payload["timeframe"]),
            start_date=self.payload["start_date"],
            end_date=self.payload["end_date"],
            strategy_name=self.payload["strategy_name"],
            strategy_params={"fast_period": 2, "slow_period": 3, "cut_off_time": "15:25"},
            option_type_preference=self.payload["option_type_preference"],
            execution_model=ExecutionModel.THEORETICAL,
            strike_selection=StrikeConfig(mode=StrikeMode(self.payload["strike_mode"])),
            expiry_selection=ExpiryConfig(mode=ExpiryMode(self.payload["expiry_mode"])),
            risk_management=RiskConfig(
                target_type="none",
                target_value=0.0,
                stop_loss_type="none",
                stop_loss_value=1.0,
                trailing_sl_gap=0.0,
                max_holding_candles=10,
                cutoff_time="15:25"
            ),
            execution=ExecutionConfig(
                brokerage_flat=self.payload["brokerage_flat"],
                slippage_pct=self.payload["slippage_pct"],
                lot_size=self.payload["lot_multiplier"],
                initial_balance=self.payload["initial_capital"]
            )
        )
        
        # Ranges to optimize
        self.ranges = [
            ParameterRange(name="fastEma", type="int", min_val=2, max_val=4, step=2),
            ParameterRange(name="slowEma", type="int", min_val=3, max_val=5, step=2)
        ]

    def test_window_generation(self):
        # Fake active trading days
        days = ["2025-04-15", "2025-04-16", "2025-04-17", "2025-04-21", "2025-04-22"]
        # train_len=2, test_len=1, step_len=1
        windows = WalkForwardAnalyzer.generate_windows_by_days(days, train_len=2, test_len=1, step_len=1)
        
        self.assertEqual(len(windows), 3)
        
        # Window 0
        self.assertEqual(windows[0]["train_start"], "2025-04-15")
        self.assertEqual(windows[0]["train_end"], "2025-04-16")
        self.assertEqual(windows[0]["test_start"], "2025-04-17")
        self.assertEqual(windows[0]["test_end"], "2025-04-17")
        
        # Window 1
        self.assertEqual(windows[1]["train_start"], "2025-04-16")
        self.assertEqual(windows[1]["train_end"], "2025-04-17")
        self.assertEqual(windows[1]["test_start"], "2025-04-21")
        self.assertEqual(windows[1]["test_end"], "2025-04-21")
        
        # Window 2
        self.assertEqual(windows[2]["train_start"], "2025-04-17")
        self.assertEqual(windows[2]["train_end"], "2025-04-21")
        self.assertEqual(windows[2]["test_start"], "2025-04-22")
        self.assertEqual(windows[2]["test_end"], "2025-04-22")
        
        # Check no overlap contamination
        for w in windows:
            # Test start must be strictly after train end
            self.assertTrue(datetime.strptime(w["test_start"], "%Y-%m-%d") > datetime.strptime(w["train_end"], "%Y-%m-%d"))

    def test_end_to_end_walk_forward(self):
        # Runs analysis with 2 train days, 1 test day, 1 step day
        # Spanning April 15 to April 22 (5 trading days: 15, 16, 17, 21, 22)
        # Generates exactly 3 windows
        report = WalkForwardAnalyzer.analyze(
            base_config=self.config,
            ranges=self.ranges,
            train_days=2,
            test_days=1,
            step_days=1
        )
        
        self.assertEqual(len(report.windows), 3)
        self.assertTrue(0.0 <= report.walk_forward_score <= 100.0)
        self.assertIn(report.classification, ["Institutional", "Strong", "Tradable", "Fragile", "Overfit"])
        
        # Validate properties on windows
        for w in report.windows:
            self.assertIsNotNone(w.best_params)
            self.assertIn("fastEma", w.best_params)
            self.assertIn("slowEma", w.best_params)
            self.assertTrue(w.train_robustness_score >= 0)
            self.assertTrue(w.test_robustness_score >= 0)
            self.assertIn("THEORETICAL", w.test_mode_results)
            self.assertIn("STRESS_TEST", w.test_mode_results)

if __name__ == '__main__':
    unittest.main()
