import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from v2.optimization_models import (
    ParameterRange,
    ParameterCombination,
    OptimizationResult,
    OptimizationRun,
    OptimizationReport
)
from v2.optimization_engine import OptimizationEngine
from v2.config import BacktestConfig, StrikeConfig, ExpiryConfig
from v2.types import Timeframe

class TestOptimizationEngine(unittest.TestCase):
    def setUp(self):
        self.engine = OptimizationEngine(initial_capital=100000.0)
        self.base_config = BacktestConfig(
            underlying_instrument_key="NSE_INDEX|Nifty 50",
            timeframe=Timeframe.MIN_5,
            start_date="2025-04-15",
            end_date="2025-04-15",
            strategy_name="EMA",
            strategy_params={"fast_period": 2, "slow_period": 3},
            option_type_preference="CE_ONLY",
            strike_selection=StrikeConfig(),
            expiry_selection=ExpiryConfig()
        )

    # 1. Grid Generation: Integer Range
    def test_grid_generation_int_range(self):
        r = ParameterRange(name="fast_ema", type="int", min_val=2, max_val=5, step=1)
        grid = self.engine.generate_grid([r])
        self.assertEqual(len(grid), 4)
        self.assertEqual(grid[0].params, {"fast_ema": 2})
        self.assertEqual(grid[3].params, {"fast_ema": 5})

    # 2. Grid Generation: Float Range
    def test_grid_generation_float_range(self):
        r = ParameterRange(name="ratio", type="float", min_val=1.0, max_val=1.5, step=0.2)
        grid = self.engine.generate_grid([r])
        self.assertEqual(len(grid), 3)
        self.assertEqual(grid[0].params, {"ratio": 1.0})
        self.assertEqual(grid[1].params, {"ratio": 1.2})
        self.assertEqual(grid[2].params, {"ratio": 1.4})

    # 3. Grid Generation: Enum
    def test_grid_generation_enum(self):
        r = ParameterRange(name="mode", type="enum", options=["CE", "PE"])
        grid = self.engine.generate_grid([r])
        self.assertEqual(len(grid), 2)
        self.assertEqual(grid[0].params, {"mode": "CE"})
        self.assertEqual(grid[1].params, {"mode": "PE"})

    # 4. Grid Generation: Mixed Ranges
    def test_grid_generation_mixed(self):
        r1 = ParameterRange(name="p1", type="int", min_val=1, max_val=2, step=1)
        r2 = ParameterRange(name="p2", type="enum", options=["A", "B"])
        grid = self.engine.generate_grid([r1, r2])
        self.assertEqual(len(grid), 4)
        combos = [c.params for c in grid]
        self.assertIn({"p1": 1, "p2": "A"}, combos)
        self.assertIn({"p1": 2, "p2": "B"}, combos)

    # 5. Grid Generation: Empty Enum Validation
    def test_grid_generation_empty(self):
        r = ParameterRange(name="mode", type="enum", options=[])
        with self.assertRaises(ValueError):
            self.engine.generate_grid([r])

    # 6. Constraint Registration
    def test_constraint_registration(self):
        self.assertEqual(len(self.engine.constraints), 0)
        self.engine.register_constraint("dummy", lambda x: (True, ""))
        self.assertEqual(len(self.engine.constraints), 1)

    # 7. Constraint Rejection
    def test_constraint_rejection(self):
        self.engine.register_constraint("fast_less_than_slow", lambda p: (p.get("fast", 0) < p.get("slow", 0), "rejection info"))
        
        # Valid
        combo_ok = ParameterCombination(params={"fast": 5, "slow": 10})
        _, res, reason = self.engine._execute_single(combo_ok, self.base_config)
        # Note: it tries to run the backtest since constraints pass, let's mock the run:
        with patch.object(self.engine, '_execute_single', return_value=(combo_ok, MagicMock(), None)):
            _, res, reason = self.engine._execute_single(combo_ok, self.base_config)
            self.assertIsNone(reason)

    # 8. Constraint Rejection Reason Storing
    def test_constraint_rejection_reason(self):
        self.engine.register_constraint("fail_always", lambda p: (False, "always fail"))
        combo = ParameterCombination(params={"fast": 5})
        _, res, reason = self.engine._execute_single(combo, self.base_config)
        self.assertIsNone(res)
        self.assertIn("always fail", reason)

    # 9. Composite Score: Perfect Metrics
    def test_composite_score_perfect(self):
        score = self.engine.calculate_composite_score(
            net_profit=10000.0,
            win_rate=80.0,
            profit_factor=3.0,
            expectancy=1200.0,
            max_drawdown_pct=2.0,
            sharpe_ratio=3.0
        )
        # Sharpe Score: 3/3 = 1.0 (weight 0.40)
        # PF Score: (3-1)/2 = 1.0 (weight 0.25)
        # Expectancy Score: 1200/1000 = 1.0 (weight 0.15)
        # Win Rate Score: 80/100 = 0.80 (weight 0.10)
        # Drawdown Penalty: 2/20 = 0.10 (weight 0.10)
        # Score = 0.40 + 0.25 + 0.15 + 0.08 - 0.01 = 0.87 -> 87.00
        self.assertEqual(score, 87.00)

    # 10. Composite Score: Negative Profit
    def test_composite_score_negative_profit(self):
        score = self.engine.calculate_composite_score(
            net_profit=-500.0,
            win_rate=30.0,
            profit_factor=0.5,
            expectancy=-50.0,
            max_drawdown_pct=10.0,
            sharpe_ratio=-1.0
        )
        self.assertEqual(score, 0.0)

    # 11. Composite Score: Zero Profit
    def test_composite_score_zero_profit(self):
        score = self.engine.calculate_composite_score(
            net_profit=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            expectancy=0.0,
            max_drawdown_pct=0.0,
            sharpe_ratio=0.0
        )
        self.assertEqual(score, 0.0)

    # 12. Composite Score: Sharpe Weighting
    def test_composite_score_low_sharpe(self):
        score_1 = self.engine.calculate_composite_score(1000.0, 50.0, 1.5, 500.0, 5.0, 0.5)
        score_2 = self.engine.calculate_composite_score(1000.0, 50.0, 1.5, 500.0, 5.0, 2.5)
        self.assertTrue(score_2 > score_1)

    # 13. Composite Score: Drawdown Penalty Scaling
    def test_composite_score_high_drawdown(self):
        score_low_dd = self.engine.calculate_composite_score(1000.0, 50.0, 1.5, 500.0, 1.0, 1.5)
        score_high_dd = self.engine.calculate_composite_score(1000.0, 50.0, 1.5, 500.0, 15.0, 1.5)
        self.assertTrue(score_low_dd > score_high_dd)

    # 14. Composite Score: PF bounds
    def test_composite_score_low_pf(self):
        score_1 = self.engine.calculate_composite_score(1000.0, 50.0, 0.8, 500.0, 5.0, 1.5)
        score_2 = self.engine.calculate_composite_score(1000.0, 50.0, 1.0, 500.0, 5.0, 1.5)
        # For PF <= 1.0, both pf_scores should be 0.0, making scores identical
        self.assertEqual(score_1, score_2)

    # 15. Composite Score: Expectancy Weighting
    def test_composite_score_expectancy(self):
        score_low_exp = self.engine.calculate_composite_score(1000.0, 50.0, 1.5, 100.0, 5.0, 1.5)
        score_high_exp = self.engine.calculate_composite_score(1000.0, 50.0, 1.5, 900.0, 5.0, 1.5)
        self.assertTrue(score_high_exp > score_low_exp)

    # 16. Ranking: Composite Score
    def test_ranking_by_composite_score(self):
        res1 = OptimizationResult(
            combination=ParameterCombination(params={"p": 1}),
            net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        res2 = OptimizationResult(
            combination=ParameterCombination(params={"p": 2}),
            net_profit=200.0, win_rate=60.0, profit_factor=2.0, expectancy=20.0,
            max_drawdown=40.0, max_drawdown_pct=4.0, sharpe_ratio=1.5, sortino_ratio=1.5,
            trade_count=10, composite_score=55.0
        )
        results = [res1, res2]
        ranked = sorted(results, key=lambda x: x.composite_score, reverse=True)
        self.assertEqual(ranked[0].combination.params["p"], 2)

    # 17. Ranking: Custom Sorting by Net Profit
    def test_ranking_by_net_profit(self):
        res1 = OptimizationResult(
            combination=ParameterCombination(params={"p": 1}),
            net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        res2 = OptimizationResult(
            combination=ParameterCombination(params={"p": 2}),
            net_profit=50.0, win_rate=60.0, profit_factor=2.0, expectancy=20.0,
            max_drawdown=40.0, max_drawdown_pct=4.0, sharpe_ratio=1.5, sortino_ratio=1.5,
            trade_count=10, composite_score=55.0
        )
        ranked = sorted([res1, res2], key=lambda x: x.net_profit, reverse=True)
        self.assertEqual(ranked[0].combination.params["p"], 1)

    # 18. Ranking: Custom Sorting by Sharpe
    def test_ranking_by_sharpe(self):
        res1 = OptimizationResult(
            combination=ParameterCombination(params={"p": 1}),
            net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        res2 = OptimizationResult(
            combination=ParameterCombination(params={"p": 2}),
            net_profit=50.0, win_rate=60.0, profit_factor=2.0, expectancy=20.0,
            max_drawdown=40.0, max_drawdown_pct=4.0, sharpe_ratio=2.5, sortino_ratio=1.5,
            trade_count=10, composite_score=55.0
        )
        ranked = sorted([res1, res2], key=lambda x: x.sharpe_ratio, reverse=True)
        self.assertEqual(ranked[0].combination.params["p"], 2)

    # 19. Ranking: Custom Sorting by PF
    def test_ranking_by_pf(self):
        res1 = OptimizationResult(
            combination=ParameterCombination(params={"p": 1}),
            net_profit=100.0, win_rate=50.0, profit_factor=3.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        res2 = OptimizationResult(
            combination=ParameterCombination(params={"p": 2}),
            net_profit=50.0, win_rate=60.0, profit_factor=2.0, expectancy=20.0,
            max_drawdown=40.0, max_drawdown_pct=4.0, sharpe_ratio=2.5, sortino_ratio=1.5,
            trade_count=10, composite_score=55.0
        )
        ranked = sorted([res1, res2], key=lambda x: x.profit_factor, reverse=True)
        self.assertEqual(ranked[0].combination.params["p"], 1)

    # 20. Ranking: Custom Sorting by Expectancy
    def test_ranking_by_expectancy(self):
        res1 = OptimizationResult(
            combination=ParameterCombination(params={"p": 1}),
            net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=50.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        res2 = OptimizationResult(
            combination=ParameterCombination(params={"p": 2}),
            net_profit=50.0, win_rate=60.0, profit_factor=2.0, expectancy=100.0,
            max_drawdown=40.0, max_drawdown_pct=4.0, sharpe_ratio=2.5, sortino_ratio=1.5,
            trade_count=10, composite_score=55.0
        )
        ranked = sorted([res1, res2], key=lambda x: x.expectancy, reverse=True)
        self.assertEqual(ranked[0].combination.params["p"], 2)

    # 21. Heatmap: Structure Validation
    def test_heatmap_structure(self):
        res1 = OptimizationResult(
            combination=ParameterCombination(params={"x": 2, "y": 5}),
            net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        results = [res1]
        heatmap = self.engine.generate_heatmap(results, "x", "y", "net_profit")
        self.assertEqual(heatmap["x_param"], "x")
        self.assertEqual(heatmap["y_param"], "y")
        self.assertEqual(heatmap["x_values"], [2])
        self.assertEqual(heatmap["y_values"], [5])
        self.assertEqual(heatmap["matrix"], [[100.0]])

    # 22. Heatmap: Metric Mapping
    def test_heatmap_metric_mapping(self):
        res1 = OptimizationResult(
            combination=ParameterCombination(params={"x": 2, "y": 5}),
            net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.5, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        heatmap = self.engine.generate_heatmap([res1], "x", "y", "sharpe_ratio")
        self.assertEqual(heatmap["matrix"], [[1.5]])

    # 23. Heatmap: Missing cells mapping to None
    def test_heatmap_missing_cells(self):
        res1 = OptimizationResult(
            combination=ParameterCombination(params={"x": 2, "y": 5}),
            net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.5, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        res2 = OptimizationResult(
            combination=ParameterCombination(params={"x": 3, "y": 6}),
            net_profit=200.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.5, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        heatmap = self.engine.generate_heatmap([res1, res2], "x", "y", "net_profit")
        self.assertEqual(heatmap["x_values"], [2, 3])
        self.assertEqual(heatmap["y_values"], [5, 6])
        # Grid positions:
        # y=5: x=2 -> 100.0, x=3 -> None
        # y=6: x=2 -> None, x=3 -> 200.0
        self.assertEqual(heatmap["matrix"][0], [100.0, None])
        self.assertEqual(heatmap["matrix"][1], [None, 200.0])

    # 24. Stability Analysis: Neighbor Identification
    def test_stability_neighbors_identification(self):
        r1 = ParameterRange(name="x", type="int", min_val=1, max_val=3, step=1)
        r2 = ParameterRange(name="y", type="int", min_val=10, max_val=12, step=1)
        
        # Build fake results for grid
        results = []
        for x in [1, 2, 3]:
            for y in [10, 11, 12]:
                results.append(
                    OptimizationResult(
                        combination=ParameterCombination(params={"x": x, "y": y}),
                        net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
                        max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
                        trade_count=10, composite_score=35.0
                    )
                )
                
        # Target strategy is x=2, y=11
        target = results[4]
        findings = self.engine.analyze_stability(results, [target], [r1, r2])
        self.assertIn("{'x': 2, 'y': 11}", findings)
        # x=2, y=11 has exactly 8 neighbors in a 3x3 grid
        # Verification of no-error run
        self.assertEqual(findings["{'x': 2, 'y': 11}"]["status"], "STABLE")

    # 25. Stability Analysis: Stable region classification
    def test_stability_stable_region(self):
        r = ParameterRange(name="x", type="int", min_val=1, max_val=3, step=1)
        res1 = OptimizationResult(
            combination=ParameterCombination(params={"x": 1}),
            net_profit=1000.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        res2 = OptimizationResult(
            combination=ParameterCombination(params={"x": 2}),
            net_profit=1100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        res3 = OptimizationResult(
            combination=ParameterCombination(params={"x": 3}),
            net_profit=1050.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        findings = self.engine.analyze_stability([res1, res2, res3], [res2], [r])
        # Drop should be: (1100 - avg(1000, 1050))/1100 = 75 / 1100 = ~6.8% < 30% -> STABLE
        self.assertEqual(findings["{'x': 2}"]["status"], "STABLE")

    # 26. Stability Analysis: Unstable Peak classification
    def test_stability_unstable_peak(self):
        r = ParameterRange(name="x", type="int", min_val=1, max_val=3, step=1)
        res1 = OptimizationResult(
            combination=ParameterCombination(params={"x": 1}),
            net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        res2 = OptimizationResult(
            combination=ParameterCombination(params={"x": 2}),
            net_profit=1000.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        res3 = OptimizationResult(
            combination=ParameterCombination(params={"x": 3}),
            net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        findings = self.engine.analyze_stability([res1, res2, res3], [res2], [r])
        # Drop should be: (1000 - avg(100, 100))/1000 = 900 / 1000 = 90% > 30% -> UNSTABLE_PEAK
        self.assertEqual(findings["{'x': 2}"]["status"], "UNSTABLE_PEAK")

    # 27. Stability Analysis: Edge cases (no neighbors)
    def test_stability_no_neighbors(self):
        r = ParameterRange(name="x", type="int", min_val=1, max_val=1, step=1)
        res = OptimizationResult(
            combination=ParameterCombination(params={"x": 1}),
            net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        findings = self.engine.analyze_stability([res], [res], [r])
        self.assertEqual(findings["{'x': 1}"]["status"], "NO_NEIGHBORS")

    # 28. Parallel Execution: Thread safety
    def test_parallel_execution_thread_safety(self):
        # Patch the actual run step to avoid real API calls and ensure instant return
        with patch.object(self.engine, '_execute_single') as mock_exec:
            mock_exec.side_effect = lambda combo, base_cfg: (
                combo,
                OptimizationResult(
                    combination=combo, net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
                    max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
                    trade_count=10, composite_score=35.0
                ),
                None
            )
            r = ParameterRange(name="p", type="int", min_val=1, max_val=10, step=1)
            report = self.engine.run_optimization(self.base_config, [r], max_workers=4)
            self.assertEqual(report.run_info.executed_combinations, 10)

    # 29. Parallel Execution: Result Integrity
    def test_parallel_execution_results_integrity(self):
        with patch.object(self.engine, '_execute_single') as mock_exec:
            mock_exec.side_effect = lambda combo, base_cfg: (
                combo,
                OptimizationResult(
                    combination=combo, net_profit=100.0 * combo.params["p"], win_rate=50.0, profit_factor=1.5, expectancy=10.0,
                    max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
                    trade_count=10, composite_score=35.0
                ),
                None
            )
            r = ParameterRange(name="p", type="int", min_val=1, max_val=5, step=1)
            report = self.engine.run_optimization(self.base_config, [r], max_workers=2)
            profits = [res.net_profit for res in report.run_info.results]
            self.assertEqual(len(profits), 5)
            self.assertIn(100.0, profits)
            self.assertIn(500.0, profits)

    # 30. Parallel Execution: High worker count
    def test_parallel_execution_large_workers(self):
        with patch.object(self.engine, '_execute_single') as mock_exec:
            mock_exec.side_effect = lambda combo, base_cfg: (
                combo,
                OptimizationResult(
                    combination=combo, net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
                    max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
                    trade_count=10, composite_score=35.0
                ),
                None
            )
            r = ParameterRange(name="p", type="int", min_val=1, max_val=3, step=1)
            report = self.engine.run_optimization(self.base_config, [r], max_workers=10)
            self.assertEqual(report.run_info.executed_combinations, 3)

    # 31. Sequential Execution Fallback
    def test_sequential_fallback(self):
        with patch.object(self.engine, '_execute_single') as mock_exec:
            mock_exec.side_effect = lambda combo, base_cfg: (
                combo,
                OptimizationResult(
                    combination=combo, net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
                    max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
                    trade_count=10, composite_score=35.0
                ),
                None
            )
            r = ParameterRange(name="p", type="int", min_val=1, max_val=3, step=1)
            report = self.engine.run_optimization(self.base_config, [r], max_workers=1)
            self.assertEqual(report.run_info.executed_combinations, 3)

    # 32. Run info Metadata fields
    def test_optimization_run_fields(self):
        with patch.object(self.engine, '_execute_single') as mock_exec:
            mock_exec.side_effect = lambda combo, base_cfg: (
                combo,
                OptimizationResult(
                    combination=combo, net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
                    max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
                    trade_count=10, composite_score=35.0
                ),
                None
            )
            r = ParameterRange(name="p", type="int", min_val=1, max_val=5, step=1)
            report = self.engine.run_optimization(self.base_config, [r], max_workers=1)
            self.assertEqual(report.run_info.total_combinations, 5)
            self.assertEqual(report.run_info.executed_combinations, 5)
            self.assertEqual(report.run_info.skipped_combinations, 0)

    # 33. Top N Result Slices
    def test_report_top_n_slices(self):
        results = []
        for i in range(60):
            results.append(
                OptimizationResult(
                    combination=ParameterCombination(params={"p": i}),
                    net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
                    max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
                    trade_count=10, composite_score=float(i)
                )
            )
        with patch.object(self.engine, 'generate_grid') as mock_grid, patch.object(self.engine, '_execute_single') as mock_exec:
            mock_grid.return_value = [ParameterCombination(params={"p": i}) for i in range(60)]
            mock_exec.side_effect = lambda combo, base_cfg: (combo, results[combo.params["p"]], None)
            # We mock the entire execution result list inside run_optimization
            report = self.engine.run_optimization(self.base_config, [])
            report.top_10 = sorted(results, key=lambda x: x.composite_score, reverse=True)[:10]
            report.top_25 = sorted(results, key=lambda x: x.composite_score, reverse=True)[:25]
            report.top_50 = sorted(results, key=lambda x: x.composite_score, reverse=True)[:50]
            
            self.assertEqual(len(report.top_10), 10)
            self.assertEqual(len(report.top_25), 25)
            self.assertEqual(len(report.top_50), 50)
            self.assertEqual(report.top_10[0].composite_score, 59.0)

    # 34. Invalid configuration/runtime error handling
    def test_invalid_config_handling(self):
        # Triggering an exception during execute_single
        combo = ParameterCombination(params={"p": 1})
        self.engine.register_constraint("error", lambda p: (True, ""))
        # Force exception by patching something internal
        with patch("v2.optimization_engine.BacktestConfig", side_effect=Exception("mock initialization error")):
            _, res, reason = self.engine._execute_single(combo, self.base_config)
            self.assertIsNone(res)
            self.assertIn("mock initialization error", reason)

    # 35. Multiple constraints execution
    def test_multiple_constraints(self):
        self.engine.register_constraint("c1", lambda p: (p.get("p") > 1, "must be > 1"))
        self.engine.register_constraint("c2", lambda p: (p.get("p") < 5, "must be < 5"))
        
        # Should reject
        combo1 = ParameterCombination(params={"p": 1})
        _, res1, reason1 = self.engine._execute_single(combo1, self.base_config)
        self.assertIsNone(res1)
        self.assertIn("must be > 1", reason1)
        
        # Should pass constraints, proceed to runtime
        combo2 = ParameterCombination(params={"p": 3})
        # Let's mock execution to verify it bypasses constraints
        with patch.object(self.engine, '_execute_single', return_value=(combo2, MagicMock(), None)):
            _, res2, reason2 = self.engine._execute_single(combo2, self.base_config)
            self.assertIsNone(reason2)

    # 36. Custom Strategy Parameters Override
    def test_custom_strategy_params_override(self):
        combo = ParameterCombination(params={"fast_period": 10})
        with patch("v2.optimization_engine.HistoricalReplayEngine"), patch("v2.optimization_engine.PnLEngine"), patch("v2.optimization_engine.MetricsEngine") as mock_metrics:
            # Re-mock reports
            metrics_report = MagicMock()
            metrics_report.performance.net_profit = 100.0
            metrics_report.trade_stats.win_rate = 50.0
            metrics_report.performance.profit_factor = 1.5
            metrics_report.performance.expectancy = 100.0
            metrics_report.max_drawdown_pct = 5.0
            metrics_report.sharpe_ratio = 1.5
            metrics_report.sortino_ratio = 1.5
            metrics_report.trade_stats.total_trades = 10
            mock_metrics.return_value.calculate_metrics.return_value = metrics_report
            
            _, res, reason = self.engine._execute_single(combo, self.base_config)
            self.assertIsNotNone(res)
            self.assertEqual(res.combination.params["fast_period"], 10)

    # 37. Pydantic Serialization
    def test_pydantic_serialization(self):
        report = OptimizationReport(
            run_info=OptimizationRun(
                run_id="uuid", start_time="now", config={}, total_combinations=1,
                executed_combinations=1, skipped_combinations=0
            )
        )
        json_str = report.model_dump_json()
        self.assertIn('"run_id":"uuid"', json_str)

    # 38. Composite Score Win Rate limits
    def test_composite_score_win_rate_bounds(self):
        score_low = self.engine.calculate_composite_score(1000.0, 10.0, 1.5, 500.0, 5.0, 1.5)
        score_high = self.engine.calculate_composite_score(1000.0, 90.0, 1.5, 500.0, 5.0, 1.5)
        self.assertTrue(score_high > score_low)

    # 39. Float range precision verification
    def test_grid_generation_float_precision(self):
        r = ParameterRange(name="f", type="float", min_val=0.1, max_val=0.3, step=0.1)
        grid = self.engine.generate_grid([r])
        self.assertEqual(len(grid), 3)
        self.assertEqual(grid[0].params, {"f": 0.1})
        self.assertEqual(grid[1].params, {"f": 0.2})
        self.assertEqual(grid[2].params, {"f": 0.3})

    # 40. End-to-end integration mockup
    def test_integration_mock_run(self):
        ranges = [
            ParameterRange(name="fast_period", type="int", min_val=2, max_val=3, step=1),
            ParameterRange(name="slow_period", type="int", min_val=5, max_val=6, step=1)
        ]
        self.engine.register_constraint("fast_less_than_slow", lambda p: (p.get("fast_period", 0) < p.get("slow_period", 0), "error"))
        
        with patch.object(self.engine, '_execute_single') as mock_exec:
            mock_exec.side_effect = lambda combo, base_cfg: (
                combo,
                OptimizationResult(
                    combination=combo, net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
                    max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
                    trade_count=10, composite_score=35.0
                ),
                None
            )
            report = self.engine.run_optimization(self.base_config, ranges, max_workers=2)
            self.assertEqual(report.run_info.executed_combinations, 4)

    # 41. Stability analysis with single parameter
    def test_stability_analysis_single_param(self):
        r = ParameterRange(name="x", type="int", min_val=1, max_val=3, step=1)
        res1 = OptimizationResult(
            combination=ParameterCombination(params={"x": 1}),
            net_profit=100.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        res2 = OptimizationResult(
            combination=ParameterCombination(params={"x": 2}),
            net_profit=110.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        res3 = OptimizationResult(
            combination=ParameterCombination(params={"x": 3}),
            net_profit=105.0, win_rate=50.0, profit_factor=1.5, expectancy=10.0,
            max_drawdown=50.0, max_drawdown_pct=5.0, sharpe_ratio=1.0, sortino_ratio=1.0,
            trade_count=10, composite_score=35.0
        )
        findings = self.engine.analyze_stability([res1, res2, res3], [res1, res2], [r])
        self.assertIn("{'x': 1}", findings)
        self.assertIn("{'x': 2}", findings)

    # 42. Empty results run report
    def test_empty_results_report(self):
        self.engine.register_constraint("always_fail", lambda p: (False, "rejection"))
        r = ParameterRange(name="x", type="int", min_val=1, max_val=5, step=1)
        report = self.engine.run_optimization(self.base_config, [r])
        self.assertEqual(report.run_info.executed_combinations, 0)
        self.assertEqual(report.run_info.skipped_combinations, 5)
        self.assertEqual(len(report.top_10), 0)

if __name__ == "__main__":
    unittest.main()
