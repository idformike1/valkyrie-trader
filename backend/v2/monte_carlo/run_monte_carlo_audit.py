import json, time
from v2.config import BacktestConfig, StrikeConfig, ExpiryConfig
from v2.types import Timeframe
from v2.replay_engine import HistoricalReplayEngine
from v2.monte_carlo.monte_carlo_engine import MonteCarloEngine
from v2.monte_carlo.monte_carlo_models import MonteCarloConfig

# Helper to run a Monte Carlo simulation and return the report
def run_mc(seed: int, stress: bool = False):
    # Base backtest config for EMA strategy
    base_cfg = BacktestConfig(
        underlying_instrument_key="NSE_INDEX|Nifty 50",
        timeframe=Timeframe.MIN_5,
        start_date="2025-04-15",
        end_date="2025-05-14",
        strategy_name="EMA",
        strategy_params={},
        option_type_preference="CE_ONLY",
        strike_selection=StrikeConfig(),
        expiry_selection=ExpiryConfig(),
    )
    # Run historical replay to obtain a filled ledger
    replay = HistoricalReplayEngine()
    replay.run(base_cfg)
    ledger = replay.ledger

    # Monte Carlo configuration
    mc_cfg = MonteCarloConfig(
        simulation_count=100,
        random_seed=seed,
        slippage_variation_pct=5.0 if stress else 0.0,
        commission_variation_pct=5.0 if stress else 0.0,
        trade_order_shuffle=stress,
        skip_trade_probability=0.1 if stress else 0.0,
        position_size_variation_pct=5.0 if stress else 0.0,
        combined_stress_test=stress,
    )
    engine = MonteCarloEngine(mc_cfg, initial_balance=base_cfg.execution.initial_balance)
    report = engine.run(ledger)
    return report

def reproducibility_audit():
    r1 = run_mc(seed=42)
    r2 = run_mc(seed=42)
    assert r1.model_dump() == r2.model_dump(), "Results differ between two runs with the same seed"
    print("[Reproducibility] PASS – identical reports for seed 42.")
    return r1

def seed_variation_audit():
    r42 = run_mc(seed=42, stress=True)
    r99 = run_mc(seed=99, stress=True)
    # Simple check: at least one metric differs
    diff = any(
        r42.robustness_metrics[k] != r99.robustness_metrics[k]
        for k in r42.robustness_metrics
    )
    assert diff, "Reports are identical for different seeds"
    print("[Seed Variation] PASS – different seeds produce different distributions.")
    # Capture key metrics for reporting
    print(f"Seed 42 – Mean Profit: {r42.robustness_metrics.get('mean_net_profit')}, Median Profit: {r42.robustness_metrics.get('median_net_profit')}, MonteCarloScore: {r42.score.overall_score:.2f}")
    print(f"Seed 99 – Mean Profit: {r99.robustness_metrics.get('mean_net_profit')}, Median Profit: {r99.robustness_metrics.get('median_net_profit')}, MonteCarloScore: {r99.score.overall_score:.2f}")

def equity_curve_audit(report):
    # Ensure each simulation produced a valid equity curve internally (no negative errors)
    # The MonteCarloEngine does not expose curves, but we can verify metrics are numeric
    for sim in report.simulations:
        assert isinstance(sim.net_profit, (int, float)), "Invalid net profit type"
        assert isinstance(sim.max_drawdown_pct, (int, float)), "Invalid drawdown type"
    print("[Equity Curve] PASS – all simulation metrics are numeric.")

def robustness_audit(report):
    rm = report.robustness_metrics
    print("Robustness Metrics:")
    for k, v in rm.items():
        print(f"  {k}: {v}")
    # Basic sanity checks
    assert rm["worst_net_profit"] <= rm["best_net_profit"], "Profit ordering error"
    assert rm["worst_drawdown_pct"] >= rm["mean_drawdown_pct"], "Drawdown ordering error"
    print("[Robustness] PASS – metrics sanity checks.")

def survival_analysis_audit(report):
    surv = report.survival_analysis
    print("Survival Analysis:")
    for k, v in surv.items():
        print(f"  {k}: {v:.4f}")
    # Probabilities must be between 0 and 1
    for v in surv.values():
        assert 0.0 <= v <= 1.0, "Survival probability out of bounds"
    print("[Survival] PASS – probabilities within [0,1].")

def risk_of_ruin_audit(report):
    print(f"Risk of Ruin Score: {report.risk_of_ruin_score:.4f}")
    assert 0.0 <= report.risk_of_ruin_score <= 1.0, "Risk of ruin out of bounds"
    print("[Risk of Ruin] PASS – score within bounds.")

def stress_test_audit():
    normal = run_mc(seed=42, stress=False)
    stress = run_mc(seed=42, stress=True)
    # Expect that stress metrics are worse (lower profit, higher drawdown, lower survival)
    assert stress.robustness_metrics["mean_net_profit"] <= normal.robustness_metrics["mean_net_profit"], "Stress profit not lower"
    assert stress.robustness_metrics["worst_drawdown_pct"] >= normal.robustness_metrics["worst_drawdown_pct"], "Stress drawdown not higher"
    assert stress.survival_analysis["prob_profit_positive"] <= normal.survival_analysis["prob_profit_positive"], "Stress survival not lower"
    print("[Stress Test] PASS – metrics deteriorate under stress conditions.")

def monte_carlo_score_audit(report):
    sc = report.score
    total = (
        0.40 * sc.survival +
        0.30 * sc.drawdown_stability +
        0.20 * sc.profit_stability +
        0.10 * sc.risk_of_ruin
    )
    assert abs(total - sc.overall_score) < 0.01, "Score aggregation mismatch"
    print(f"Monte Carlo Score: {sc.overall_score} (components: {sc.survival}, {sc.drawdown_stability}, {sc.profit_stability}, {sc.risk_of_ruin})")
    print("[Score] PASS – weighted calculation correct.")

def performance_audit(start_time, end_time, report):
    runtime = end_time - start_time
    avg_sim_time = runtime / report.config.simulation_count
    print(f"Runtime (s): {runtime:.2f}")
    print(f"Simulation count: {report.config.simulation_count}")
    print(f"Avg time per simulation (s): {avg_sim_time:.4f}")
    # Memory usage not directly measured; placeholder note
    print("[Performance] PASS – runtime metrics captured.")

if __name__ == "__main__":
    t0 = time.time()
    report = run_mc(seed=42)
    t1 = time.time()
    # Audits
    reproducibility_audit()
    seed_variation_audit()
    equity_curve_audit(report)
    robustness_audit(report)
    survival_analysis_audit(report)
    risk_of_ruin_audit(report)
    stress_test_audit()
    monte_carlo_score_audit(report)
    performance_audit(t0, t1, report)
    # Save JSON for reference
    with open('monte_carlo_audit_report.json', 'w') as f:
        json.dump(report.dict(), f, indent=2)
    print("Audit completed and report saved to monte_carlo_audit_report.json")
