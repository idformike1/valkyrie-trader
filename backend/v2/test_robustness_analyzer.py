import unittest
import sys
from datetime import datetime

# Ensure backend folder is in PYTHONPATH
sys.path.append("/Users/rajumaharjan/Documents/Anit Gravity Projects/Valkyrie/backend")

from v2.config import BacktestConfig
from v2.robustness_analyzer import ExecutionRobustnessAnalyzer, RobustnessAnalysisResult

class TestRobustnessAnalyzer(unittest.TestCase):
    def setUp(self):
        # Create standard payload configuration
        self.payload = {
            "underlying_instrument_key": "NSE_INDEX|Nifty 50",
            "timeframe": "5m",
            "start_date": "2025-04-15",
            "end_date": "2025-04-17",
            "strategy_name": "EMA",
            "strategy_params": {
                "fastEma": 2,
                "slowEma": 3,
                "cut_off_time": "15:25",
                "fast_period": 2,
                "slow_period": 3
            },
            "option_type_preference": "CE_ONLY",
            "strike_selection": {"mode": "ATM"},
            "expiry_selection": {"mode": "CURRENT_WEEKLY"},
            "risk_management": {
                "target_type": "none",
                "target_value": 0.0,
                "stop_loss_type": "none",
                "stop_loss_value": 1.0,
                "trailing_sl_gap": 0.0,
                "max_holding_candles": 10,
                "cutoff_time": "15:25"
            },
            "execution": {
                "brokerage_flat": 20.0,
                "slippage_pct": 0.05,
                "lot_size": 1,
                "initial_balance": 100000.0
            }
        }
        self.config = BacktestConfig(**self.payload)

    def test_robustness_analyzer_flow(self):
        result = ExecutionRobustnessAnalyzer.analyze(self.config)
        
        # 1. Verify result schema
        self.assertIsInstance(result, RobustnessAnalysisResult)
        self.assertIsNotNone(result.robustness_score)
        self.assertIsNotNone(result.classification)
        self.assertIn(result.classification, ["Excellent", "Strong", "Fragile", "Dangerous"])
        
        # 2. Verify metrics stability existence
        self.assertIsNotNone(result.metrics_stability.profit_stability)
        self.assertIsNotNone(result.metrics_stability.win_rate_stability)
        self.assertIsNotNone(result.metrics_stability.pf_stability)
        self.assertIsNotNone(result.metrics_stability.drawdown_stability)
        self.assertIsNotNone(result.metrics_stability.return_stability)
        
        # 3. Verify side-by-side mode results
        self.assertIn("THEORETICAL", result.mode_results)
        self.assertIn("REALISTIC", result.mode_results)
        self.assertIn("CONSERVATIVE", result.mode_results)
        self.assertIn("STRESS_TEST", result.mode_results)
        
        # Check that stress test profit is <= theoretical profit
        theo_p = result.mode_results["THEORETICAL"].net_profit
        stress_p = result.mode_results["STRESS_TEST"].net_profit
        self.assertLessEqual(stress_p, theo_p)

    def test_empty_robustness_handling(self):
        # Setup holiday with no trades
        payload = dict(self.payload)
        payload["start_date"] = "2025-04-13" # Sunday
        payload["end_date"] = "2025-04-13"
        config = BacktestConfig(**payload)
        
        result = ExecutionRobustnessAnalyzer.analyze(config)
        self.assertEqual(result.robustness_score, 0.0)
        self.assertEqual(result.classification, "Dangerous")

if __name__ == "__main__":
    unittest.main()
