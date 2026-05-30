import unittest
from datetime import datetime
from v2.config import BacktestConfig, StrikeConfig, ExpiryConfig
from v2.types import Timeframe
from v2.walk_forward.walk_forward_models import WalkForwardConfig
from v2.walk_forward.walk_forward_engine import WalkForwardEngine

class TestWalkForwardEngine(unittest.TestCase):
    def setUp(self):
        # Base backtest config spanning the mock DB date range (2025‑04‑15 to 2025‑04‑17)
        self.base_cfg = BacktestConfig(
            underlying_instrument_key="NSE_INDEX|Nifty 50",
            timeframe=Timeframe.MIN_5,
            start_date="2025-04-15",
            end_date="2025-04-17",
            strategy_name="EMA",
            strategy_params={},
            option_type_preference="CE_ONLY",
            strike_selection=StrikeConfig(),
            expiry_selection=ExpiryConfig(),
        )
        self.wf_cfg = WalkForwardConfig(
            training_window_days=2,   # 2025‑04‑15 → 2025‑04‑16
            testing_window_days=1,    # 2025‑04‑17 only
            step_size_days=1,
            min_trades_required=1,
            optimization_enabled=True,
        )
        self.engine = WalkForwardEngine(self.base_cfg, self.wf_cfg)

    def test_window_generation(self):
        windows = self.engine._generate_windows()
        # Expect exactly one cycle given the tiny range
        self.assertEqual(len(windows), 1)
        train, test = windows[0]
        self.assertEqual(train["start"], "2025-04-15")
        self.assertEqual(train["end"], "2025-04-16")
        self.assertEqual(test["start"], "2025-04-17")
        self.assertEqual(test["end"], "2025-04-17")

    def test_full_run(self):
        # Run walk forward for up to 3 cycles (will stop early due to data range)
        report = self.engine.run(max_cycles=3)
        self.assertEqual(report.status, "PASS")
        self.assertTrue(len(report.cycles) >= 1)
        # Verify that each cycle contains test metrics and selected parameters
        for cyc in report.cycles:
            self.assertIn("net_profit", cyc.test_metrics)
            # Optimization should have produced fast/slow EMA params
            if self.wf_cfg.optimization_enabled:
                self.assertIn("fast_period", cyc.selected_parameters)
                self.assertIn("slow_period", cyc.selected_parameters)

    def test_score_components_range(self):
        report = self.engine.run(max_cycles=2)
        sc = report.score
        # All component scores should lie within 0‑100
        for attr in ["overall_score", "test_profitability", "consistency", "drawdown_score", "parameter_stability"]:
            val = getattr(sc, attr)
            self.assertGreaterEqual(val, 0)
            self.assertLessEqual(val, 100)

if __name__ == "__main__":
    unittest.main()
