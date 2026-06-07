import unittest
from datetime import datetime, timedelta
from typing import Dict, Any

from v2.position_models import Position, PositionStatus
from v2.pnl_models import TradeCharges, TradePnL, TradeAccountingResult, ExecutionAnalysis
from v2.cost_models import UpstoxCostModel
from v2.pnl_engine import PnLEngine
from v2.metrics_engine import MetricsEngine
from v2.execution_reality_engine import (
    calculate_spread_penalty,
    calculate_volatility_penalty,
    calculate_effective_fill
)

class TestExecutionReality(unittest.TestCase):

    def setUp(self):
        self.cost_model = UpstoxCostModel()
        self.pnl_engine = PnLEngine(cost_model=self.cost_model)
        self.sample_time = datetime(2025, 4, 15, 9, 30)

        # Base theoretical position
        self.base_pos = Position(
            position_id="pos-real-123",
            status=PositionStatus.CLOSED,
            underlying="NIFTY",
            strike=23300.0,
            expiry="2025-04-17",
            option_type="CE",
            instrument_key="NSE_FO|48236|17-04-2025",
            entry_time=self.sample_time,
            entry_premium=100.0,
            quantity=75,
            lot_size=75,
            entry_value=100.0 * 75,
            exit_time=self.sample_time + timedelta(minutes=20),
            exit_premium=120.0,
            exit_value=120.0 * 75,
            broker="Upstox",
            entry_signal="BUY_INTENT",
            metadata={
                "execution_model": "REALISTIC",
                "entry_spot_price": 23300.0,
                "entry_atr": 15.0,
                "entry_candle_range": 12.0,
                "entry_strike_distance": 0.0,
                "exit_spot_price": 23350.0,
                "exit_atr": 18.0,
                "exit_candle_range": 16.0,
                "exit_strike_distance": 50.0
            }
        )

    def test_spread_penalty_scaling(self):
        # ATM
        pct_atm, val_atm = calculate_spread_penalty(
            option_premium=100.0,
            spot_price=23300.0,
            strike_distance=0.0,
            option_type="CE",
            mode="REALISTIC"
        )
        # OTM
        pct_otm, val_otm = calculate_spread_penalty(
            option_premium=100.0,
            spot_price=23300.0,
            strike_distance=200.0,
            option_type="CE",
            mode="REALISTIC"
        )
        # OTM spread penalty should be higher than ATM spread penalty
        self.assertGreater(pct_otm, pct_atm)
        self.assertGreater(val_otm, val_atm)

    def test_volatility_penalty_scaling(self):
        # Low Volatility
        _, low_vol_cost = calculate_volatility_penalty(
            atr=5.0,
            spot_candle_range=4.0,
            entry_premium=100.0,
            mode="REALISTIC"
        )
        # High Volatility
        _, high_vol_cost = calculate_volatility_penalty(
            atr=25.0,
            spot_candle_range=30.0,
            entry_premium=100.0,
            mode="REALISTIC"
        )
        self.assertGreater(high_vol_cost, low_vol_cost)

    def test_execution_modes_effective_fills(self):
        # Stress Test vs Realistic
        _, stress_spread = calculate_spread_penalty(100.0, 23300.0, 0.0, "CE", "STRESS_TEST")
        _, realistic_spread = calculate_spread_penalty(100.0, 23300.0, 0.0, "CE", "REALISTIC")
        self.assertGreater(stress_spread, realistic_spread)

        _, stress_vol = calculate_volatility_penalty(15.0, 12.0, 100.0, "STRESS_TEST")
        _, realistic_vol = calculate_volatility_penalty(15.0, 12.0, 100.0, "REALISTIC")
        self.assertGreater(stress_vol, realistic_vol)

    def test_pnl_engine_theoretical_mode(self):
        pos = self.base_pos.model_copy()
        pos.metadata["execution_model"] = "THEORETICAL"

        acc = self.pnl_engine.account_trade(pos)
        self.assertEqual(acc.entry_premium, 100.0)
        self.assertEqual(acc.exit_premium, 120.0)
        self.assertEqual(acc.execution_analysis.spread_cost, 0.0)
        self.assertEqual(acc.execution_analysis.volatility_cost, 0.0)
        self.assertEqual(acc.execution_analysis.pnl_degradation, 0.0)

    def test_pnl_engine_realistic_mode(self):
        pos = self.base_pos.model_copy()
        pos.metadata["execution_model"] = "REALISTIC"

        acc = self.pnl_engine.account_trade(pos)
        
        # In realistic mode, entry premium should increase (slippage cost added)
        # and exit premium should decrease (slippage cost subtracted)
        self.assertGreater(acc.entry_premium, 100.0)
        self.assertLess(acc.exit_premium, 120.0)

        # Gross PnL should be degraded compared to theoretical (120 - 100)*75 = 1500
        self.assertLess(acc.gross_pnl, 1500.0)
        self.assertGreater(acc.execution_analysis.spread_cost, 0.0)
        self.assertGreater(acc.execution_analysis.volatility_cost, 0.0)
        self.assertGreater(acc.execution_analysis.pnl_degradation, 0.0)

    def test_metrics_engine_execution_adjusted_integration(self):
        # Create one realistic trade and one theoretical trade
        p1 = self.base_pos.model_copy()
        p1.metadata["execution_model"] = "REALISTIC"
        
        # PnL accounting result
        tr = self.pnl_engine.account_trade(p1)
        
        # Run MetricsEngine
        metrics_engine = MetricsEngine(initial_capital=100000.0)
        report = metrics_engine.calculate_metrics([p1], [tr])

        self.assertGreater(report.average_slippage_cost, 0.0)
        self.assertGreater(report.average_spread_cost, 0.0)
        self.assertGreater(report.average_volatility_cost, 0.0)
        
        # Execution adjusted profit should be less than theoretical net profit
        # (Since it is realistic mode, the trade's net_pnl was already adjusted)
        self.assertEqual(report.execution_adjusted_profit, report.performance.net_profit)
        self.assertLess(report.execution_adjusted_profit, 1500.0)

if __name__ == "__main__":
    unittest.main()
