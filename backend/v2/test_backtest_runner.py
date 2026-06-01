import unittest
import sys
from datetime import datetime

# Ensure backend folder is in PYTHONPATH
sys.path.append("/Users/rajumaharjan/Documents/Anit Gravity Projects/Valkyrie/backend")

from v2.config import BacktestConfig
from v2.backtest_runner import BacktestRunner, BacktestResult

class TestBacktestRunner(unittest.TestCase):
    def setUp(self):
        # Create a valid standard NIFTY CE/PE backtest config
        self.valid_payload = {
            "underlying_instrument_key": "NSE_INDEX|Nifty 50",
            "timeframe": "1m",
            "start_date": "2025-04-15",
            "end_date": "2025-04-15",
            "strategy_name": "five_ema",
            "strategy_params": {
                "candle_limit": 10,
                "five_ema_period": 5,
                "five_ema_rr": 3.0
            },
            "option_type_preference": "DYNAMIC",
            "strike_selection": {"mode": "OTM_1"},
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
        self.config = BacktestConfig(**self.valid_payload)

    def test_backtest_runner_flow(self):
        # Run Backtest
        result = BacktestRunner.run(self.config)
        
        # 1. Type validation
        self.assertIsInstance(result, BacktestResult)
        
        # 2. Schema integrity validation
        self.assertIsNotNone(result.report)
        self.assertIsNotNone(result.trades)
        self.assertIsNotNone(result.positions)
        self.assertIsNotNone(result.replay_timeline)
        self.assertIsNotNone(result.equity_curve)
        self.assertIsNotNone(result.drawdown_curve)
        self.assertIsNotNone(result.metadata)
        
        # 3. Value sanity checks
        self.assertEqual(result.metadata["underlying"], "NSE_INDEX|Nifty 50")
        self.assertEqual(result.metadata["start_date"], "2025-04-15")
        self.assertEqual(result.metadata["end_date"], "2025-04-15")
        self.assertEqual(result.report.initial_capital, 100000.0)
        
        # Ensure trades count matches the positions count
        closed_positions = [p for p in result.positions if p.exit_time is not None]
        self.assertEqual(len(result.trades), len(closed_positions))

    def test_backtest_runner_determinism(self):
        # Run twice to verify complete numerical and state determinism
        res1 = BacktestRunner.run(self.config)
        res2 = BacktestRunner.run(self.config)
        
        # Assert exact matches
        self.assertEqual(res1.report.final_equity, res2.report.final_equity)
        self.assertEqual(res1.report.performance.net_profit, res2.report.performance.net_profit)
        self.assertEqual(res1.report.trade_stats.total_trades, res2.report.trade_stats.total_trades)
        self.assertEqual(res1.report.performance.exposure_time_seconds, res2.report.performance.exposure_time_seconds)
        self.assertEqual(res1.report.max_drawdown, res2.report.max_drawdown)
        self.assertEqual(res1.report.sharpe_ratio, res2.report.sharpe_ratio)
        self.assertEqual(res1.report.sortino_ratio, res2.report.sortino_ratio)
        self.assertEqual(len(res1.trades), len(res2.trades))
        self.assertEqual(len(res1.positions), len(res2.positions))

    def test_empty_backtest_graceful_handling(self):
        # Create a day with no active signals (we shift start/end to a holiday or day with no signals)
        # Using a weekend date where no underlying data exists
        payload = dict(self.valid_payload)
        payload["start_date"] = "2025-04-13"  # Sunday
        payload["end_date"] = "2025-04-13"
        config = BacktestConfig(**payload)
        
        result = BacktestRunner.run(config)
        
        # Check that empty results are returned gracefully without crashes
        self.assertEqual(result.report.trade_stats.total_trades, 0)
        self.assertEqual(result.report.final_equity, 100000.0)
        self.assertEqual(result.report.performance.net_profit, 0.0)
        self.assertEqual(len(result.trades), 0)
        self.assertEqual(len(result.positions), 0)

if __name__ == "__main__":
    unittest.main()
