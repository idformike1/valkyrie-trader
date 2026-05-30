import random
import copy
from typing import List, Dict, Any

from v2.position_ledger import PositionLedger
from v2.pnl_models import TradeAccountingResult
from v2.metrics_engine import MetricsEngine
from v2.monte_carlo.monte_carlo_models import (
    MonteCarloConfig,
    SimulationMetrics,
    MonteCarloReport,
    MonteCarloScore,
)


def _apply_variations(trades: List[TradeAccountingResult], cfg: MonteCarloConfig) -> List[TradeAccountingResult]:
    """Return a new list of trades with Monte Carlo variations applied.
    The original TradeAccountingResult objects are immutable (pydantic), so we create shallow copies
    and adjust the mutable fields (net_pnl, total_charges, quantity) via ``model_copy``.
    """
    # Convert to mutable dicts
    mutable = [t.model_copy() for t in trades]

    # 1. Trade order shuffle
    if cfg.trade_order_shuffle:
        random.shuffle(mutable)

    # 2. Trade skip simulation
    if cfg.skip_trade_probability > 0:
        mutable = [t for t in mutable if random.random() > cfg.skip_trade_probability]

    # 3. Slippage expansion (negative impact on net pnl)
    if cfg.slippage_variation_pct > 0:
        for t in mutable:
            # Apply a random negative slippage up to the configured percentage of gross pnl
            slippage_factor = random.uniform(0, cfg.slippage_variation_pct) / 100.0
            loss = t.gross_pnl * slippage_factor
            t.net_pnl = round(t.net_pnl - loss, 2)
            # Update charges.total_charges to keep accounting consistent
            t.charges.total_charges = round(t.charges.total_charges + loss, 2)

    # 4. Commission variation
    if cfg.commission_variation_pct > 0:
        for t in mutable:
            extra = t.charges.total_charges * (random.uniform(0, cfg.commission_variation_pct) / 100.0)
            t.charges.total_charges = round(t.charges.total_charges + extra, 2)
            t.net_pnl = round(t.net_pnl - extra, 2)

    # 5. Position size variation (affects profit proportionally)
    if cfg.position_size_variation_pct > 0:
        for t in mutable:
            variation = random.uniform(-cfg.position_size_variation_pct, cfg.position_size_variation_pct) / 100.0
            # Scale net pnl and gross pnl by (1 + variation)
            factor = 1 + variation
            t.gross_pnl = round(t.gross_pnl * factor, 2)
            t.net_pnl = round(t.net_pnl * factor, 2)

    return mutable


def _equity_curve(trades: List[TradeAccountingResult], initial_balance: float = 0.0) -> List[float]:
    """Build cumulative equity curve from net pnl list.
    Returns list of equity values after each trade.
    """
    equity = [initial_balance]
    cum = initial_balance
    for t in trades:
        cum += t.net_pnl
        equity.append(cum)
    return equity


def _max_drawdown_pct(equity: List[float]) -> float:
    """Calculate maximum drawdown as a percentage of the peak equity.
    If equity never falls, returns 0.0.
    """
    peak = equity[0]
    max_dd = 0.0
    for val in equity:
        if val > peak:
            peak = val
        dd = (peak - val) / peak if peak != 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd * 100, 2)


class MonteCarloEngine:
    """Engine that runs Monte Carlo simulations on a completed trade ledger.

    The engine is agnostic to the underlying strategy – it simply consumes the
    ``TradeAccountingResult`` objects produced by the Replay/Walk‑Forward pipelines.
    """

    def __init__(self, config: MonteCarloConfig, initial_balance: float = 0.0, random_seed: int = None):
        self.cfg = config
        self.initial_balance = initial_balance
        if random_seed is not None:
            random.seed(random_seed)
        elif self.cfg.random_seed is not None:
            random.seed(self.cfg.random_seed)
        else:
            random.seed()

    def _run_single(self, trades: List[TradeAccountingResult]) -> SimulationMetrics:
        # Apply variations (or none if combined_stress_test false and no flags)
        if self.cfg.combined_stress_test:
            # Force all variations regardless of individual flags
            varied = _apply_variations(
                trades,
                MonteCarloConfig(
                    simulation_count=self.cfg.simulation_count,
                    random_seed=self.cfg.random_seed,
                    slippage_variation_pct=self.cfg.slippage_variation_pct,
                    commission_variation_pct=self.cfg.commission_variation_pct,
                    trade_order_shuffle=True,
                    skip_trade_probability=self.cfg.skip_trade_probability,
                    position_size_variation_pct=self.cfg.position_size_variation_pct,
                    combined_stress_test=False,
                ),
            )
        else:
            varied = _apply_variations(trades, self.cfg)

        # Build equity curve and metrics
        equity = _equity_curve(varied, self.initial_balance)
        net_profit = round(equity[-1] - self.initial_balance, 2)
        max_dd = _max_drawdown_pct(equity)
        gross_pos = sum(t.gross_pnl for t in varied if t.gross_pnl > 0)
        gross_neg = -sum(t.gross_pnl for t in varied if t.gross_pnl < 0)
        profit_factor = round(gross_pos / gross_neg, 2) if gross_neg != 0 else float('inf')
        win_rate = round(
            sum(1 for t in varied if t.net_pnl > 0) / len(varied), 4
        ) if varied else 0.0
        return SimulationMetrics(
            net_profit=net_profit,
            max_drawdown_pct=max_dd,
            profit_factor=profit_factor,
            win_rate=win_rate,
            trade_count=len(varied),
        )

    def run(self, ledger: PositionLedger) -> MonteCarloReport:
        # Extract trade accounting results from the ledger
        base_trades = ledger.accounting_records
        simulations: List[SimulationMetrics] = []
        for i in range(self.cfg.simulation_count):
            metrics = self._run_single(base_trades)
            simulations.append(metrics)

        # Robustness metrics
        net_profits = [s.net_profit for s in simulations]
        drawdowns = [s.max_drawdown_pct for s in simulations]
        robustness = {
            "mean_net_profit": round(sum(net_profits) / len(net_profits), 2),
            "median_net_profit": round(sorted(net_profits)[len(net_profits)//2], 2),
            "worst_net_profit": min(net_profits),
            "best_net_profit": max(net_profits),
            "mean_drawdown_pct": round(sum(drawdowns) / len(drawdowns), 2),
            "worst_drawdown_pct": max(drawdowns),
        }

        # Survival analysis
        survive_count = sum(1 for p in net_profits if p > 0)
        pf_gt_one = sum(1 for s in simulations if s.profit_factor > 1)
        dd_lt_20 = sum(1 for d in drawdowns if d < 20)
        total = len(simulations)
        survival = {
            "prob_profit_positive": round(survive_count / total, 4),
            "prob_pf_gt_one": round(pf_gt_one / total, 4),
            "prob_dd_lt_20": round(dd_lt_20 / total, 4),
        }

        # Risk of ruin – simple definition: probability net profit < -50% of initial_balance (or < 0 if balance 0)
        ruin_threshold = -0.5 * self.initial_balance if self.initial_balance != 0 else 0.0
        ruin_count = sum(1 for p in net_profits if p <= ruin_threshold)
        risk_of_ruin_score = round(1 - (ruin_count / total), 4)  # higher is better

        # Monte Carlo Score components (weights sum to 100)
        survival_score = survival["prob_profit_positive"] * 100  # 40% weight later
        drawdown_score = (1 - (robustness["worst_drawdown_pct"] / 100)) * 100  # 30% weight
        profit_stability_score = (
            (robustness["best_net_profit"] - robustness["worst_net_profit"]) /
            (robustness["best_net_profit"] if robustness["best_net_profit"] != 0 else 1)
        ) * 100  # lower variance = higher score, 20% weight
        risk_ruin_component = risk_of_ruin_score * 100  # 10% weight

        overall = (
            0.40 * survival_score +
            0.30 * drawdown_score +
            0.20 * profit_stability_score +
            0.10 * risk_ruin_component
        )
        score = MonteCarloScore(
            overall_score=round(overall, 2),
            survival=round(survival_score, 2),
            drawdown_stability=round(drawdown_score, 2),
            profit_stability=round(profit_stability_score, 2),
            risk_of_ruin=round(risk_ruin_component, 2),
        )

        histogram = {
            "net_profit": net_profits,
            "max_drawdown_pct": drawdowns,
            "profit_factor": [s.profit_factor for s in simulations],
        }

        return MonteCarloReport(
            config=self.cfg,
            simulations=simulations,
            robustness_metrics=robustness,
            survival_analysis=survival,
            risk_of_ruin_score=risk_of_ruin_score,
            score=score,
            histogram_data=histogram,
        )
