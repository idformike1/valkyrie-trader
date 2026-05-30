import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any

from v2.optimization_engine import OptimizationEngine
from v2.optimization_models import ParameterRange
from v2.config import BacktestConfig
from v2.replay_engine import HistoricalReplayEngine
from v2.metrics_engine import MetricsEngine
from v2.walk_forward.walk_forward_models import (
    WalkForwardConfig,
    WalkForwardCycle,
    WalkForwardScore,
    WalkForwardReport,
)

logger = logging.getLogger("Valkyrie.WalkForwardEngine")
logger.setLevel(logging.INFO)


class WalkForwardEngine:
    """Lightweight Walk Forward Engine.

    Generates rolling training/testing windows, runs optimization on the training
    window, applies the best parameters to the testing window, collects metrics,
    and aggregates a final Walk Forward Score.
    """

    def __init__(self, base_config: BacktestConfig, wf_config: WalkForwardConfig):
        self.base_config = base_config
        self.wf_config = wf_config
        # Simple optimization engine (single worker to keep runtime low)
        self.opt_engine = OptimizationEngine(initial_capital=base_config.execution.initial_balance)

    # ---------------------------------------------------------------------
    # Window generation
    # ---------------------------------------------------------------------
    def _generate_windows(self) -> List[Tuple[Dict[str, str], Dict[str, str]]]:
        """Generate training/testing windows.

        Returns a list of tuples: (training_window, testing_window) where each
        window is a dict with ``start`` and ``end`` ISO date strings.
        """
        start = datetime.strptime(self.base_config.start_date, "%Y-%m-%d")
        end = datetime.strptime(self.base_config.end_date, "%Y-%m-%d")
        tw = self.wf_config.training_window_days
        te = self.wf_config.testing_window_days
        step = self.wf_config.step_size_days

        windows = []
        while True:
            train_start = start
            train_end = train_start + timedelta(days=tw - 1)
            test_start = train_end + timedelta(days=1)
            test_end = test_start + timedelta(days=te - 1)
            if test_end > end:
                break
            windows.append(
                (
                    {"start": train_start.strftime("%Y-%m-%d"), "end": train_end.strftime("%Y-%m-%d")},
                    {"start": test_start.strftime("%Y-%m-%d"), "end": test_end.strftime("%Y-%m-%d")},
                )
            )
            # roll forward by step days
            start = start + timedelta(days=step)
        return windows

    # ---------------------------------------------------------------------
    # Helper to run a single backtest and collect key metrics
    # ---------------------------------------------------------------------
    def _run_backtest(self, config: BacktestConfig) -> Dict[str, Any]:
        """Runs a replay and extracts a simplified metric dict.
        Returns keys: net_profit, win_rate, profit_factor, expectancy,
        max_drawdown_pct, sharpe_ratio, trade_count.
        """
        replay = HistoricalReplayEngine()
        replay.run(config)
        # Gather metrics via MetricsEngine
        # Use PnL engine for trades
        from v2.pnl_engine import PnLEngine
        from v2.position_manager import PositionManager
        from v2.position_ledger import PositionLedger

        pnl_engine = PnLEngine()
        # ledger populated by replay internally
        ledger = replay.ledger
        summary = pnl_engine.generate_accounting_summary(ledger.positions)
        metrics_engine = MetricsEngine(initial_capital=self.opt_engine.initial_capital)
        report = metrics_engine.calculate_metrics(ledger.positions, summary.trades)
        # Simplify extraction
        return {
            "net_profit": report.performance.net_profit,
            "win_rate": report.trade_stats.win_rate,
            "profit_factor": report.performance.profit_factor,
            "expectancy": report.performance.expectancy,
            "max_drawdown_pct": report.max_drawdown_pct,
            "sharpe_ratio": report.sharpe_ratio,
            "trade_count": report.trade_stats.total_trades,
        }

    # ---------------------------------------------------------------------
    # Core walk‑forward execution
    # ---------------------------------------------------------------------
    def run(self, max_cycles: int = 5) -> WalkForwardReport:
        windows = self._generate_windows()
        cycles: List[WalkForwardCycle] = []
        selected_params_history: List[Dict[str, Any]] = []
        for idx, (train_win, test_win) in enumerate(windows):
            if idx >= max_cycles:
                break
            logger.info(f"Walk‑forward Cycle {idx+1}: Train {train_win} Test {test_win}")
            # ---------- Training ----------
            train_cfg = self.base_config.copy()
            train_cfg.start_date = train_win["start"]
            train_cfg.end_date = train_win["end"]
            best_params: Dict[str, Any] = {}
            train_metrics: Dict[str, Any] = {}
            if self.wf_config.optimization_enabled:
                # small EMA range
                ranges = [
                    ParameterRange(name="fast_period", type="int", min_val=2, max_val=5, step=1),
                    ParameterRange(name="slow_period", type="int", min_val=8, max_val=15, step=1),
                ]
                opt_report = self.opt_engine.run_optimization(train_cfg, ranges, max_workers=1)
                if opt_report.top_10:
                    best = opt_report.top_10[0]
                    best_params = best.combination.params
                    train_metrics = {
                        "net_profit": best.net_profit,
                        "win_rate": best.win_rate,
                        "profit_factor": best.profit_factor,
                        "expectancy": best.expectancy,
                        "max_drawdown_pct": best.max_drawdown_pct,
                        "sharpe_ratio": best.sharpe_ratio,
                        "trade_count": best.trade_count,
                    }
                else:
                    logger.warning("Optimization produced no results – falling back to base params")
                    best_params = {}
            else:
                # No optimization – use existing params
                best_params = {}
                train_metrics = self._run_backtest(train_cfg)

            # Update base config with selected parameters for testing
            test_cfg = self.base_config.copy()
            test_cfg.start_date = test_win["start"]
            test_cfg.end_date = test_win["end"]
            # Merge parameters – EMA fast/slow are expected as "fast_period"/"slow_period"
            if best_params:
                test_cfg.strategy_params = {**test_cfg.strategy_params, **best_params}
            # ---------- Testing ----------
            test_metrics = self._run_backtest(test_cfg)

            # Record cycle
            cycle = WalkForwardCycle(
                cycle_index=idx,
                train_start=train_win["start"],
                train_end=train_win["end"],
                test_start=test_win["start"],
                test_end=test_win["end"],
                selected_parameters=best_params,
                train_metrics=train_metrics,
                test_metrics=test_metrics,
            )
            cycles.append(cycle)
            selected_params_history.append(best_params)

        # -----------------------------------------------------------------
        # Score aggregation – lightweight deterministic approach
        # -----------------------------------------------------------------
        # 40% Test Profitability – normalized to max net profit observed
        test_profits = [c.test_metrics.get("net_profit", 0) for c in cycles]
        max_profit = max(test_profits) if test_profits else 1
        test_profit_score = (sum(test_profits) / (len(test_profits) * max_profit)) * 100 if test_profits else 0

        # 30% Consistency – average win rate across test windows (0‑100 scale)
        win_rates = [c.test_metrics.get("win_rate", 0) for c in cycles]
        consistency_score = (sum(win_rates) / len(win_rates)) if win_rates else 0

        # 20% Drawdown – lower drawdown gives higher score
        drawdowns = [c.test_metrics.get("max_drawdown_pct", 0) for c in cycles]
        # Assume 20% drawdown is worst, 0% is best
        drawdown_score = (1 - (sum(drawdowns) / (len(drawdowns) * 20))) * 100 if drawdowns else 0

        # 10% Parameter stability – compute variance of fast/slow across cycles
        fast_vals = [p.get("fast_period") for p in selected_params_history if p.get("fast_period") is not None]
        slow_vals = [p.get("slow_period") for p in selected_params_history if p.get("slow_period") is not None]
        def _stability(vals: List[int]) -> float:
            if not vals:
                return 100.0
            mean = sum(vals) / len(vals)
            var = sum((v - mean) ** 2 for v in vals) / len(vals)
            # Normalise – smaller variance yields higher score (max 100)
            return max(0.0, 100.0 - (var * 10))
        fast_score = _stability(fast_vals)
        slow_score = _stability(slow_vals)
        param_stability_score = (fast_score + slow_score) / 2

        overall = (
            0.40 * test_profit_score
            + 0.30 * consistency_score
            + 0.20 * drawdown_score
            + 0.10 * param_stability_score
        )

        walk_score = WalkForwardScore(
            overall_score=round(overall, 2),
            test_profitability=round(test_profit_score, 2),
            consistency=round(consistency_score, 2),
            drawdown_score=round(drawdown_score, 2),
            parameter_stability=round(param_stability_score, 2),
        )

        status = "PASS" if all(c.test_metrics.get("trade_count", 0) >= self.wf_config.min_trades_required for c in cycles) else "FAIL"

        report = WalkForwardReport(
            config=self.wf_config,
            cycles=cycles,
            score=walk_score,
            stability_analysis={"selected_parameters": selected_params_history},
            status=status,
        )
        return report
