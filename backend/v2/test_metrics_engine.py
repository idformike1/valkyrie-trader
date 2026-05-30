import unittest
from datetime import datetime, timedelta
from typing import List

from v2.position_models import Position, PositionStatus
from v2.pnl_models import TradeCharges, TradeAccountingResult
from v2.metrics_engine import MetricsEngine
from v2.metrics_models import MetricsReport

class TestMetricsEngine(unittest.TestCase):

    def setUp(self):
        self.engine = MetricsEngine(initial_capital=100000.0)
        self.base_time = datetime(2025, 4, 15, 9, 30)

        # Helper trade builder
        self.charges = TradeCharges(
            brokerage=40.0, stt=10.0, exchange_charges=7.0, sebi_charges=0.0,
            gst=8.0, stamp_duty=0.3, other_charges=0.0, total_charges=65.3
        )

    def _make_trade(self, pid: str, entry_offset: int, exit_offset: int, net_pnl: float) -> TradeAccountingResult:
        return TradeAccountingResult(
            position_id=pid,
            entry_time=self.base_time + timedelta(minutes=entry_offset),
            exit_time=self.base_time + timedelta(minutes=exit_offset),
            contract="NIFTY 23300 CE (2025-04-17)",
            entry_premium=100.0,
            exit_premium=100.0 + (net_pnl / 75.0),
            quantity=75,
            gross_pnl=net_pnl + 65.3,
            charges=self.charges,
            net_pnl=net_pnl
        )

    def _make_position(self, entry_offset: int, exit_offset: int) -> Position:
        return Position(
            position_id="pos", status=PositionStatus.CLOSED, underlying="NIFTY",
            strike=23300.0, expiry="2025-04-17", option_type="CE", instrument_key="key",
            entry_time=self.base_time + timedelta(minutes=entry_offset), entry_premium=100.0,
            quantity=75, lot_size=75, entry_value=7500.0,
            exit_time=self.base_time + timedelta(minutes=exit_offset), exit_premium=101.0,
            exit_value=7575.0, broker="Upstox", entry_signal="BUY"
        )

    # 1. Win Rate Calculation
    def test_win_rate_calculation(self):
        trades = [
            self._make_trade("t1", 0, 10, 100.0),
            self._make_trade("t2", 20, 30, -50.0),
            self._make_trade("t3", 40, 50, 200.0),
            self._make_trade("t4", 60, 70, -100.0)
        ]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.trade_stats.win_rate, 50.0)
        self.assertEqual(report.trade_stats.loss_rate, 50.0)

    # 2. Win Rate Zero Wins
    def test_win_rate_zero_wins(self):
        trades = [self._make_trade("t1", 0, 10, -50.0)]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.trade_stats.win_rate, 0.0)
        self.assertEqual(report.trade_stats.loss_rate, 100.0)

    # 3. Win Rate Zero Losses
    def test_win_rate_zero_losses(self):
        trades = [self._make_trade("t1", 0, 10, 50.0)]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.trade_stats.win_rate, 100.0)
        self.assertEqual(report.trade_stats.loss_rate, 0.0)

    # 4. Win Rate Breakeven Only
    def test_win_rate_breakeven_only(self):
        trades = [
            TradeAccountingResult(
                position_id="t1", entry_time=self.base_time, exit_time=self.base_time + timedelta(minutes=10),
                contract="NIFTY", entry_premium=100.0, exit_premium=100.0, quantity=75,
                gross_pnl=0.0, charges=self.charges, net_pnl=0.0
            )
        ]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.trade_stats.win_rate, 0.0)
        self.assertEqual(report.trade_stats.breakeven_trades, 1)

    # 5. Profit Factor Calculation
    def test_profit_factor_calculation(self):
        trades = [
            self._make_trade("t1", 0, 10, 300.0),
            self._make_trade("t2", 20, 30, -100.0)
        ]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.performance.profit_factor, 3.0)

    # 6. Profit Factor No Losses
    def test_profit_factor_no_losses(self):
        trades = [self._make_trade("t1", 0, 10, 300.0)]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.performance.profit_factor, 99.9)

    # 7. Profit Factor No Wins
    def test_profit_factor_no_wins(self):
        trades = [self._make_trade("t1", 0, 10, -300.0)]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.performance.profit_factor, 0.0)

    # 8. Expectancy Calculation
    def test_expectancy_calculation(self):
        trades = [
            self._make_trade("t1", 0, 10, 200.0),
            self._make_trade("t2", 20, 30, -100.0)
        ]
        report = self.engine.calculate_metrics([], trades)
        # wr=50%, avg_win=200, loss_rate=50%, avg_loss=100. Expectancy = 0.5 * 200 - 0.5 * 100 = 50.0
        self.assertEqual(report.performance.expectancy, 50.0)

    # 9. Expectancy Losing Strategy
    def test_expectancy_losing_strategy(self):
        trades = [
            self._make_trade("t1", 0, 10, 100.0),
            self._make_trade("t2", 20, 30, -300.0)
        ]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.performance.expectancy, -100.0)

    # 10. Payoff Ratio Calculation
    def test_payoff_ratio_calculation(self):
        trades = [
            self._make_trade("t1", 0, 10, 400.0),
            self._make_trade("t2", 20, 30, -100.0)
        ]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.performance.payoff_ratio, 4.0)

    # 11. Payoff Ratio Division by Zero
    def test_payoff_ratio_division_by_zero(self):
        trades = [self._make_trade("t1", 0, 10, 400.0)]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.performance.payoff_ratio, 400.0)

    # 12. Streaks Calculation
    def test_streaks_calculation(self):
        trades = [
            self._make_trade("t1", 0, 5, 10.0),
            self._make_trade("t2", 10, 15, 20.0),
            self._make_trade("t3", 20, 25, -10.0),
            self._make_trade("t4", 30, 35, -20.0),
            self._make_trade("t5", 40, 45, -30.0),
            self._make_trade("t6", 50, 55, 5.0)
        ]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.performance.max_consecutive_wins, 2)
        self.assertEqual(report.performance.max_consecutive_losses, 3)

    # 13. Streaks All Wins
    def test_streaks_all_wins(self):
        trades = [self._make_trade("t1", 0, 5, 10.0), self._make_trade("t2", 10, 15, 20.0)]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.performance.max_consecutive_wins, 2)
        self.assertEqual(report.performance.max_consecutive_losses, 0)

    # 14. Streaks All Losses
    def test_streaks_all_losses(self):
        trades = [self._make_trade("t1", 0, 5, -10.0), self._make_trade("t2", 10, 15, -20.0)]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.performance.max_consecutive_wins, 0)
        self.assertEqual(report.performance.max_consecutive_losses, 2)

    # 15. Time Metrics Calculation
    def test_time_metrics_calculation(self):
        positions = [
            self._make_position(0, 10), # 600s
            self._make_position(20, 45) # 1500s
        ]
        report = self.engine.calculate_metrics(positions, [])
        self.assertEqual(report.performance.avg_hold_time_seconds, 1050.0)
        self.assertEqual(report.performance.shortest_hold_time_seconds, 600.0)
        self.assertEqual(report.performance.longest_hold_time_seconds, 1500.0)
        self.assertEqual(report.performance.exposure_time_seconds, 2100.0)

    # 16. Time Metrics Empty
    def test_time_metrics_empty(self):
        report = self.engine.calculate_metrics([], [])
        self.assertEqual(report.performance.avg_hold_time_seconds, 0.0)
        self.assertEqual(report.performance.exposure_time_seconds, 0.0)

    # 17. Equity Curve Generation
    def test_equity_curve_generation(self):
        trades = [
            self._make_trade("t1", 0, 10, 1000.0),
            self._make_trade("t2", 20, 30, -500.0)
        ]
        report = self.engine.calculate_metrics([], trades)
        # Prepend + 2 trades = 3 points
        self.assertEqual(len(report.equity_curve), 3)
        self.assertEqual(report.equity_curve[0].equity_value, 100000.0)
        self.assertEqual(report.equity_curve[1].equity_value, 101000.0)
        self.assertEqual(report.equity_curve[2].equity_value, 100500.0)

    # 18. Drawdown Curve Generation
    def test_drawdown_curve_generation(self):
        trades = [
            self._make_trade("t1", 0, 10, 1000.0), # Peak = 101000
            self._make_trade("t2", 20, 30, -500.0) # Equity = 100500, DD = 500
        ]
        report = self.engine.calculate_metrics([], trades)
        # Prepend + 2 trades = 3 points
        self.assertEqual(report.drawdown_curve[2].drawdown_value, 500.0)
        self.assertEqual(report.drawdown_curve[2].drawdown_pct, (500.0 / 101000.0) * 100.0)

    # 19. Max Drawdown Calculation
    def test_max_drawdown_calculation(self):
        trades = [
            self._make_trade("t1", 0, 10, -5000.0), # peak=100k, equity=95k, dd=5k
            self._make_trade("t2", 20, 30, 10000.0), # peak=105k, equity=105k, dd=0
            self._make_trade("t3", 40, 50, -8000.0) # peak=105k, equity=97k, dd=8k
        ]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.max_drawdown, 8000.0)
        self.assertEqual(report.max_drawdown_pct, round((8000.0 / 105000.0) * 100.0, 2))

    # 20. Max Drawdown Duration
    def test_max_drawdown_duration(self):
        trades = [
            self._make_trade("t1", 0, 10, 1000.0), # exit 10m. Peak=101k
            self._make_trade("t2", 20, 30, -500.0), # exit 30m. Equity=100.5k
            self._make_trade("t3", 40, 50, 1000.0) # exit 50m. Equity=101.5k. Peak. Duration = 20m (1200s)
        ]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.max_drawdown_duration_seconds, 1200.0)

    # 21. Sharpe Ratio Single Day (Trade-level)
    def test_sharpe_ratio_single_day(self):
        # All exits on the same day -> trade level fallback
        trades = [
            self._make_trade("t1", 0, 10, 100.0),
            self._make_trade("t2", 20, 30, -50.0),
            self._make_trade("t3", 40, 50, 150.0)
        ]
        report = self.engine.calculate_metrics([], trades)
        self.assertGreater(report.sharpe_ratio, 0.0)

    # 22. Sharpe Ratio Multi Day (Annualized)
    def test_sharpe_ratio_multi_day(self):
        # Exits across different days
        t1 = self._make_trade("t1", 0, 10, 1000.0)
        t2 = self._make_trade("t2", 1440, 1450, -500.0) # +24 hours (next day)
        t3 = self._make_trade("t3", 2880, 2890, 2000.0) # +48 hours (day after next)
        
        report = self.engine.calculate_metrics([], [t1, t2, t3])
        self.assertNotEqual(report.sharpe_ratio, 0.0)

    # 23. Sharpe Ratio Zero Volatility
    def test_sharpe_ratio_zero_volatility(self):
        trades = [self._make_trade("t1", 0, 10, 100.0)]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.sharpe_ratio, 0.0)

    # 24. Sortino Ratio Single Day
    def test_sortino_ratio_single_day(self):
        trades = [
            self._make_trade("t1", 0, 10, 100.0),
            self._make_trade("t2", 20, 30, -50.0),
            self._make_trade("t3", 40, 50, 150.0)
        ]
        report = self.engine.calculate_metrics([], trades)
        self.assertGreater(report.sortino_ratio, 0.0)

    # 25. Sortino Ratio Multi Day
    def test_sortino_ratio_multi_day(self):
        t1 = self._make_trade("t1", 0, 10, 1000.0)
        t2 = self._make_trade("t2", 1440, 1450, -500.0)
        t3 = self._make_trade("t3", 2880, 2890, 2000.0)
        report = self.engine.calculate_metrics([], [t1, t2, t3])
        self.assertGreater(report.sortino_ratio, 0.0)

    # 26. Sortino Ratio Zero Volatility
    def test_sortino_ratio_zero_volatility(self):
        trades = [self._make_trade("t1", 0, 10, 100.0)]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.sortino_ratio, 0.0)

    # 27. Return Metrics
    def test_return_metrics(self):
        trades = [self._make_trade("t1", 0, 10, 5000.0)]
        report = self.engine.calculate_metrics([], trades)
        self.assertEqual(report.absolute_return_pct, 5.0)
        self.assertEqual(report.net_return_pct, 5.0)
        self.assertEqual(report.capital_growth_pct, 5.0)

    # 28. Scorecard Grade A+
    def test_scorecard_grade_aplus(self):
        # Win rate = 100%, PF = 99.9, Sharpe > 2.0 (we use mock multi-day to ensure Sharpe), DD = 0%
        # High metrics -> A+
        t1 = self._make_trade("t1", 0, 10, 10000.0)
        t2 = self._make_trade("t2", 1440, 1450, 12000.0)
        report = self.engine.calculate_metrics([], [t1, t2])
        self.assertEqual(report.grade, "A+")

    # 29. Scorecard Grade A
    def test_scorecard_grade_a(self):
        # Slightly lower Sharpe/Win Rate
        t1 = self._make_trade("t1", 0, 10, 10000.0)
        t2 = self._make_trade("t2", 20, 30, 10000.0)
        t3 = self._make_trade("t3", 40, 50, 10000.0)
        report = self.engine.calculate_metrics([], [t1, t2, t3])
        self.assertEqual(report.grade, "A")

    # 30. Scorecard Grade B
    def test_scorecard_grade_b(self):
        t1 = self._make_trade("t1", 0, 10, 10000.0)
        t2 = self._make_trade("t2", 20, 30, -10.0)
        t3 = self._make_trade("t3", 40, 50, -10.0)
        report = self.engine.calculate_metrics([], [t1, t2, t3])
        self.assertEqual(report.grade, "B")

    # 31. Scorecard Grade C
    def test_scorecard_grade_c(self):
        t1 = self._make_trade("t1", 0, 10, 10000.0)
        t2 = self._make_trade("t2", 20, 30, -10.0)
        t3 = self._make_trade("t3", 40, 50, -5000.0)
        report = self.engine.calculate_metrics([], [t1, t2, t3])
        self.assertEqual(report.grade, "C")

    # 32. Scorecard Grade D
    def test_scorecard_grade_d(self):
        t1 = self._make_trade("t1", 0, 10, 10000.0)
        t2 = self._make_trade("t2", 20, 30, -2000.0)
        t3 = self._make_trade("t3", 40, 50, -5000.0)
        report = self.engine.calculate_metrics([], [t1, t2, t3])
        self.assertEqual(report.grade, "D")

    # 33. Scorecard Grade F
    def test_scorecard_grade_f(self):
        t1 = self._make_trade("t1", 0, 10, -500.0)
        report = self.engine.calculate_metrics([], [t1])
        self.assertEqual(report.grade, "F")

    # 34. Single Trade Edge Case
    def test_single_trade_edge_case(self):
        t = self._make_trade("t1", 0, 10, 100.0)
        report = self.engine.calculate_metrics([], [t])
        self.assertEqual(report.trade_stats.total_trades, 1)
        self.assertEqual(report.final_equity, 100100.0)

    # 35. Zero Trades Edge Case
    def test_zero_trades_edge_case(self):
        report = self.engine.calculate_metrics([], [])
        self.assertEqual(report.trade_stats.total_trades, 0)
        self.assertEqual(report.final_equity, 100000.0)
        self.assertEqual(report.grade, "F")

    # 36. Pydantic Field Serialization
    def test_pydantic_field_serialization(self):
        t = self._make_trade("t1", 0, 10, 100.0)
        report = self.engine.calculate_metrics([], [t])
        data = report.model_dump()
        self.assertEqual(data["initial_capital"], 100000.0)
        self.assertEqual(len(data["equity_curve"]), 2)

if __name__ == "__main__":
    unittest.main()
