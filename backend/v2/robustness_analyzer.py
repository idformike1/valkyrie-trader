import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from v2.config import BacktestConfig
from v2.types import ExecutionModel
from v2.backtest_runner import BacktestRunner

logger = logging.getLogger("Valkyrie.RobustnessAnalyzer")

class RobustnessMetricStability(BaseModel):
    profit_stability: float
    win_rate_stability: float
    pf_stability: float
    drawdown_stability: float
    return_stability: float

class ModeSummary(BaseModel):
    net_profit: float
    win_rate: float
    profit_factor: float
    max_drawdown: float
    net_return: float

class RobustnessAnalysisResult(BaseModel):
    robustness_score: float
    classification: str
    metrics_stability: RobustnessMetricStability
    mode_results: Dict[str, ModeSummary]
    theoretical_equity_curve: Optional[List[Dict[str, Any]]] = None

class ExecutionRobustnessAnalyzer:
    @staticmethod
    def analyze(config: BacktestConfig) -> RobustnessAnalysisResult:
        # Run across all 4 modes
        modes = [
            ExecutionModel.THEORETICAL,
            ExecutionModel.REALISTIC,
            ExecutionModel.CONSERVATIVE,
            ExecutionModel.STRESS_TEST
        ]
        
        results = {}
        theoretical_eq = []
        for mode in modes:
            config_copy = config.model_copy(deep=True)
            config_copy.execution_model = mode
            # Run the backtest
            res = BacktestRunner.run(config_copy)
            
            perf = res.report.performance
            stats = res.report.trade_stats
            results[mode.value] = {
                "net_profit": perf.net_profit,
                "win_rate": stats.win_rate,
                "profit_factor": perf.profit_factor,
                "max_drawdown": res.report.max_drawdown_pct,
                "net_return": res.report.net_return_pct
            }
            if mode == ExecutionModel.THEORETICAL:
                theoretical_eq = [
                    {"date": pt.timestamp.strftime("%Y-%m-%d"), "equity": pt.equity_value}
                    for pt in res.equity_curve
                ]
            
        theo = results[ExecutionModel.THEORETICAL.value]
        real = results[ExecutionModel.REALISTIC.value]
        cons = results[ExecutionModel.CONSERVATIVE.value]
        stress = results[ExecutionModel.STRESS_TEST.value]
        
        # Helper to compute stability
        def calc_stability(theo_val, real_val, cons_val, stress_val, is_drawdown=False):
            if is_drawdown:
                # For drawdown, higher is worse, so stability = theo / mode
                s_real = 1.0 if real_val <= theo_val else (theo_val / real_val if real_val > 0 else 0.0)
                s_cons = 1.0 if cons_val <= theo_val else (theo_val / cons_val if cons_val > 0 else 0.0)
                s_stress = 1.0 if stress_val <= theo_val else (theo_val / stress_val if stress_val > 0 else 0.0)
            else:
                # For profits/returns/winrate/pf, higher is better
                if theo_val <= 0:
                    return 0.0
                s_real = max(0.0, min(1.0, real_val / theo_val))
                s_cons = max(0.0, min(1.0, cons_val / theo_val))
                s_stress = max(0.0, min(1.0, stress_val / theo_val))
                
            # Weighted average: 50% Realistic, 30% Conservative, 20% Stress Test
            return 0.50 * s_real + 0.30 * s_cons + 0.20 * s_stress

        # Calculate individual metric stabilities
        profit_st = calc_stability(theo["net_profit"], real["net_profit"], cons["net_profit"], stress["net_profit"])
        win_rate_st = calc_stability(theo["win_rate"], real["win_rate"], cons["win_rate"], stress["win_rate"])
        pf_st = calc_stability(theo["profit_factor"], real["profit_factor"], cons["profit_factor"], stress["profit_factor"])
        drawdown_st = calc_stability(theo["max_drawdown"], real["max_drawdown"], cons["max_drawdown"], stress["max_drawdown"], is_drawdown=True)
        return_st = calc_stability(theo["net_return"], real["net_return"], cons["net_return"], stress["net_return"])
        
        # If theoretical profit <= 0, robustness is automatically 0
        if theo["net_profit"] <= 0:
            robustness_score = 0.0
        else:
            # Weighted overall robustness score (0-100)
            # 30% Profit, 20% Return, 20% Win Rate, 15% PF, 15% Drawdown
            raw_score = (
                0.30 * profit_st +
                0.20 * return_st +
                0.20 * win_rate_st +
                0.15 * pf_st +
                0.15 * drawdown_st
            )
            robustness_score = round(raw_score * 100.0, 2)
            
        # Classify
        if robustness_score >= 85.0:
            classification = "Excellent"
        elif robustness_score >= 70.0:
            classification = "Strong"
        elif robustness_score >= 50.0:
            classification = "Fragile"
        else:
            classification = "Dangerous"
            
        return RobustnessAnalysisResult(
            robustness_score=robustness_score,
            classification=classification,
            metrics_stability=RobustnessMetricStability(
                profit_stability=round(profit_st, 4),
                win_rate_stability=round(win_rate_st, 4),
                pf_stability=round(pf_st, 4),
                drawdown_stability=round(drawdown_st, 4),
                return_stability=round(return_st, 4)
            ),
            mode_results={
                k: ModeSummary(**v) for k, v in results.items()
            },
            theoretical_equity_curve=theoretical_eq
        )
