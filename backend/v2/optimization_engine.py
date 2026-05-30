import os
import uuid
import logging
import threading
import itertools
import statistics
import math
from datetime import datetime
from typing import List, Dict, Any, Tuple, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from v2.optimization_models import (
    ParameterRange,
    ParameterCombination,
    OptimizationResult,
    OptimizationRun,
    OptimizationReport
)
from v2.replay_engine import HistoricalReplayEngine
from v2.config import BacktestConfig
from v2.pnl_engine import PnLEngine
from v2.metrics_engine import MetricsEngine

logger = logging.getLogger("Valkyrie.OptimizationEngine")
logger.setLevel(logging.INFO)

class OptimizationEngine:
    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.constraints: List[Tuple[str, Callable[[Dict[str, Any]], Tuple[bool, str]]]] = []
        self._lock = threading.Lock()

    def register_constraint(self, name: str, callable_fn: Callable[[Dict[str, Any]], Tuple[bool, str]]) -> None:
        """
        Registers a validation constraint. The function must accept a parameter dict
        and return a Tuple (is_valid, rejection_reason).
        """
        self.constraints.append((name, callable_fn))

    def generate_grid(self, ranges: List[ParameterRange]) -> List[ParameterCombination]:
        """
        Generates the Cartesian product of all parameter ranges.
        """
        param_values = {}
        for r in ranges:
            if r.type == "int":
                min_v = int(r.min_val)
                max_v = int(r.max_val)
                step = int(r.step or 1)
                param_values[r.name] = list(range(min_v, max_v + 1, step))
            elif r.type == "float":
                min_v = float(r.min_val)
                max_v = float(r.max_val)
                step = float(r.step or 1.0)
                vals = []
                curr = min_v
                while curr <= max_v + (step * 0.00001):
                    vals.append(round(curr, 6))
                    curr += step
                param_values[r.name] = vals
            elif r.type == "enum":
                if not r.options:
                    raise ValueError(f"Enum parameter range {r.name} has no options.")
                param_values[r.name] = list(r.options)
            else:
                raise ValueError(f"Unknown parameter range type: {r.type}")

        # Generate Cartesian product
        keys = list(param_values.keys())
        value_lists = [param_values[k] for k in keys]
        combinations = []
        for combo in itertools.product(*value_lists):
            param_dict = dict(zip(keys, combo))
            combinations.append(ParameterCombination(params=param_dict))

        return combinations

    def calculate_composite_score(
        self, 
        net_profit: float, 
        win_rate: float, 
        profit_factor: float, 
        expectancy: float, 
        max_drawdown_pct: float, 
        sharpe_ratio: float
    ) -> float:
        """
        Composite Score default formula:
        - 40% Sharpe Ratio (normalized: 3.0 Sharpe = 1.0)
        - 25% Profit Factor (normalized: (PF - 1.0)/2.0, PF=3.0 = 1.0)
        - 15% Expectancy (normalized: Expectancy / 1000.0 = 1.0)
        - 10% Win Rate (normalized: Win Rate / 100.0)
        - 10% Drawdown Penalty (normalized: Max DD % / 20.0 = 1.0)

        If Net Profit <= 0, the composite score is hardcapped to 0.0.
        """
        if net_profit <= 0.0:
            return 0.0

        sharpe_score = max(0.0, min(sharpe_ratio / 3.0, 1.0))
        pf_score = max(0.0, min((profit_factor - 1.0) / 2.0, 1.0))
        expectancy_score = max(0.0, min(expectancy / 1000.0, 1.0))
        win_rate_score = win_rate / 100.0
        dd_penalty = max(0.0, min(max_drawdown_pct / 20.0, 1.0))

        score = (
            (0.40 * sharpe_score) +
            (0.25 * pf_score) +
            (0.15 * expectancy_score) +
            (0.10 * win_rate_score) -
            (0.10 * dd_penalty)
        )
        # Scale to 0-100 and round to 2 decimals
        return round(max(0.0, score * 100.0), 2)

    def _execute_single(
        self, 
        combo: ParameterCombination, 
        base_config: BacktestConfig
    ) -> Tuple[ParameterCombination, Optional[OptimizationResult], Optional[str]]:
        """
        Executes a single backtest run for the given parameter combination.
        Returns Tuple of (combo, OptimizationResult, rejection_reason).
        """
        params = combo.params
        
        # Check constraints
        for name, constraint_fn in self.constraints:
            is_valid, reason = constraint_fn(params)
            if not is_valid:
                return combo, None, f"Constraint '{name}' failed: {reason}"

        try:
            # Build BacktestConfig
            config_dict = base_config.model_dump()
            config_dict["strategy_params"] = dict(config_dict.get("strategy_params", {}))
            config_dict["strategy_params"].update(params)
            
            # Since BacktestConfig inherits from BaseModel, we can reconstruct it
            config = BacktestConfig(**config_dict)
            
            # Lock the execution to protect against SQLite database lock issues
            with self._lock:
                replay_engine = HistoricalReplayEngine()
                replay_engine.run(config)
                
                pnl_engine = PnLEngine()
                summary = pnl_engine.generate_accounting_summary(replay_engine.ledger.positions)
                
                metrics_engine = MetricsEngine(initial_capital=self.initial_capital)
                report = metrics_engine.calculate_metrics(replay_engine.ledger.positions, summary.trades)

            # Calculate Composite Score
            comp_score = self.calculate_composite_score(
                net_profit=report.performance.net_profit,
                win_rate=report.trade_stats.win_rate,
                profit_factor=report.performance.profit_factor,
                expectancy=report.performance.expectancy,
                max_drawdown_pct=report.max_drawdown_pct,
                sharpe_ratio=report.sharpe_ratio
            )

            result = OptimizationResult(
                combination=combo,
                net_profit=report.performance.net_profit,
                win_rate=report.trade_stats.win_rate,
                profit_factor=report.performance.profit_factor,
                expectancy=report.performance.expectancy,
                max_drawdown=report.max_drawdown,
                max_drawdown_pct=report.max_drawdown_pct,
                sharpe_ratio=report.sharpe_ratio,
                sortino_ratio=report.sortino_ratio,
                trade_count=report.trade_stats.total_trades,
                composite_score=comp_score
            )
            return combo, result, None

        except Exception as e:
            logger.error(f"Error executing backtest for combination {params}: {e}")
            return combo, None, f"Runtime Error: {str(e)}"

    def run_optimization(
        self, 
        base_config: BacktestConfig, 
        ranges: List[ParameterRange], 
        max_workers: int = 1
    ) -> OptimizationReport:
        """
        Runs parameter optimization sweep.
        """
        start_time_str = datetime.now().isoformat()
        
        # 1. Generate grid
        combinations = self.generate_grid(ranges)
        total_combinations = len(combinations)
        
        results: List[OptimizationResult] = []
        skipped_details: Dict[str, str] = {}
        
        executed_combinations = 0
        skipped_combinations = 0

        # 2. Execute combinations (Parallel or Sequential)
        if max_workers > 1:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self._execute_single, combo, base_config): combo for combo in combinations}
                for future in as_completed(futures):
                    combo, res, reason = future.result()
                    if res:
                        results.append(res)
                        executed_combinations += 1
                    else:
                        skipped_details[str(combo.params)] = reason
                        skipped_combinations += 1
        else:
            for combo in combinations:
                combo, res, reason = self._execute_single(combo, base_config)
                if res:
                    results.append(res)
                    executed_combinations += 1
                else:
                    skipped_details[str(combo.params)] = reason
                    skipped_combinations += 1

        end_time_str = datetime.now().isoformat()

        # 3. Create OptimizationRun details
        run_info = OptimizationRun(
            run_id=str(uuid.uuid4()),
            start_time=start_time_str,
            end_time=end_time_str,
            config=base_config.model_dump(),
            total_combinations=total_combinations,
            executed_combinations=executed_combinations,
            skipped_combinations=skipped_combinations,
            skipped_details=skipped_details,
            results=results
        )

        # 4. Rank Results by Composite Score
        ranked_results = sorted(results, key=lambda x: x.composite_score, reverse=True)

        top_10 = ranked_results[:10]
        top_25 = ranked_results[:25]
        top_50 = ranked_results[:50]

        # 5. Generate Heatmap data for first two parameter ranges if available
        heatmap_data = {}
        if len(ranges) >= 2:
            x_param = ranges[0].name
            y_param = ranges[1].name
            heatmap_data = self.generate_heatmap(results, x_param, y_param, "net_profit")

        # 6. Stability Analysis
        stability_findings = self.analyze_stability(results, top_10, ranges)

        return OptimizationReport(
            run_info=run_info,
            top_10=top_10,
            top_25=top_25,
            top_50=top_50,
            heatmap_data=heatmap_data,
            stability_findings=stability_findings
        )

    def generate_heatmap(
        self, 
        results: List[OptimizationResult], 
        x_param: str, 
        y_param: str, 
        metric: str = "net_profit"
    ) -> Dict[str, Any]:
        """
        Generates 2D heatmap matrix data structures.
        """
        # Find distinct values for X and Y parameters
        x_vals = sorted(list(set(r.combination.params[x_param] for r in results if x_param in r.combination.params)))
        y_vals = sorted(list(set(r.combination.params[y_param] for r in results if y_param in r.combination.params)))

        # Create mapping of (x, y) -> OptimizationResult
        grid_map = {}
        for r in results:
            params = r.combination.params
            if x_param in params and y_param in params:
                grid_map[(params[x_param], params[y_param])] = r

        matrix = []
        for y in y_vals:
            row = []
            for x in x_vals:
                res = grid_map.get((x, y))
                if res:
                    row.append(getattr(res, metric, None))
                else:
                    row.append(None)
            matrix.append(row)

        return {
            "x_param": x_param,
            "y_param": y_param,
            "metric": metric,
            "x_values": x_vals,
            "y_values": y_vals,
            "matrix": matrix
        }

    def analyze_stability(
        self, 
        results: List[OptimizationResult], 
        top_strategies: List[OptimizationResult], 
        ranges: List[ParameterRange]
    ) -> Dict[str, Any]:
        """
        Inspects neighboring parameter values for top strategies to verify robustness.
        """
        # Build grid coordinates
        grid_vals = {}
        for r in ranges:
            # Reconstruct list of values in order
            if r.type == "int":
                min_v = int(r.min_val)
                max_v = int(r.max_val)
                step = int(r.step or 1)
                grid_vals[r.name] = list(range(min_v, max_v + 1, step))
            elif r.type == "float":
                min_v = float(r.min_val)
                max_v = float(r.max_val)
                step = float(r.step or 1.0)
                vals = []
                curr = min_v
                while curr <= max_v + (step * 0.00001):
                    vals.append(round(curr, 6))
                    curr += step
                grid_vals[r.name] = vals
            elif r.type == "enum":
                grid_vals[r.name] = list(r.options)

        # Mapping of str(combination.params) -> OptimizationResult for fast lookup
        result_map = {str(r.combination.params): r for r in results}

        findings = {}

        for strat in top_strategies:
            params = strat.combination.params
            # Generate neighbors: combinations where indices of each parameter differ by at most 1
            neighbor_indices = {}
            has_indices = True
            for k, v in params.items():
                if k not in grid_vals:
                    has_indices = False
                    break
                try:
                    idx = grid_vals[k].index(v)
                    neighbor_indices[k] = [idx - 1, idx, idx + 1]
                except ValueError:
                    has_indices = False
                    break

            if not has_indices:
                continue

            # Cartesian product of neighbor index options
            keys = list(neighbor_indices.keys())
            idx_lists = [neighbor_indices[k] for k in keys]
            neighbor_results = []
            
            for index_combo in itertools.product(*idx_lists):
                # Build parameter dictionary from indices
                p_dict = {}
                is_valid = True
                for i, k in enumerate(keys):
                    idx = index_combo[i]
                    if 0 <= idx < len(grid_vals[k]):
                        p_dict[k] = grid_vals[k][idx]
                    else:
                        is_valid = False
                        break
                
                if is_valid and p_dict != params:
                    # Look up in results
                    n_res = result_map.get(str(p_dict))
                    if n_res:
                        neighbor_results.append(n_res)

            # Analyze neighbors
            if neighbor_results:
                neighbor_profits = [n.net_profit for n in neighbor_results]
                neighbor_scores = [n.composite_score for n in neighbor_results]
                
                avg_profit = statistics.mean(neighbor_profits)
                std_profit = statistics.stdev(neighbor_profits) if len(neighbor_profits) > 1 else 0.0
                avg_score = statistics.mean(neighbor_scores)
                
                # Check drop percentage
                drop_pct = ((strat.net_profit - avg_profit) / strat.net_profit * 100.0) if strat.net_profit > 0 else 0.0
                
                findings[str(params)] = {
                    "avg_neighbor_profit": round(avg_profit, 2),
                    "std_neighbor_profit": round(std_profit, 2),
                    "avg_neighbor_composite_score": round(avg_score, 2),
                    "drop_pct": round(drop_pct, 2),
                    "status": "STABLE" if drop_pct < 30.0 else "UNSTABLE_PEAK"
                }
            else:
                findings[str(params)] = {
                    "avg_neighbor_profit": strat.net_profit,
                    "std_neighbor_profit": 0.0,
                    "avg_neighbor_composite_score": strat.composite_score,
                    "drop_pct": 0.0,
                    "status": "NO_NEIGHBORS"
                }

        return findings
