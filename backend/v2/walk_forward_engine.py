import logging
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field

from v2.config import BacktestConfig, StrikeConfig, ExpiryConfig, RiskConfig, ExecutionConfig
from v2.types import StrikeMode, ExpiryMode, Timeframe as V2Timeframe, ExecutionModel
from v2.optimization_engine import OptimizationEngine, ParameterRange, ParameterCombination
from v2.robustness_analyzer import ExecutionRobustnessAnalyzer
from v2.backtest_runner import BacktestRunner

logger = logging.getLogger("Valkyrie.WalkForwardEngine")
logger.setLevel(logging.INFO)

# --- Pydantic Schemas ---

class WalkForwardWindow(BaseModel):
    window_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    
    # Training results (from best optimized parameters in TRAIN period)
    best_params: Dict[str, Any]
    train_net_profit: float
    train_win_rate: float
    train_profit_factor: float
    train_max_drawdown: float
    train_net_return: float
    train_robustness_score: float
    train_classification: str
    
    # Test results (using the best_params in TEST period under reality/robustness analysis)
    test_net_profit: float
    test_win_rate: float
    test_profit_factor: float
    test_max_drawdown: float
    test_net_return: float
    test_robustness_score: float
    test_classification: str
    
    # Mode-by-mode results in the testing phase
    test_mode_results: Dict[str, Dict[str, float]]
    
    # V2 extensions
    profit_decay: float = 0.0
    pf_decay: float = 0.0
    winrate_decay: float = 0.0
    drawdown_expansion: float = 0.0
    regime: str = "SIDEWAYS"
    test_equity_curve: Optional[List[Dict[str, Any]]] = None

class WalkForwardStability(BaseModel):
    profit_stability: float      # Average of Test Profit / Train Profit
    pf_stability: float          # Average of Test PF / Train PF
    drawdown_stability: float    # Average of Train DD / Test DD
    robustness_stability: float  # Average of Test Robustness / Train Robustness
    consistency_score: float     # Percentage of windows where test net profit is positive

class WalkForwardReport(BaseModel):
    walk_forward_score: float
    classification: str
    stability: WalkForwardStability
    windows: List[WalkForwardWindow]
    
    # V2 extensions
    parameter_drift_analysis: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    stitched_oos_equity_curve: List[Dict[str, Any]] = Field(default_factory=list)
    average_profit_decay: float = 0.0
    average_pf_decay: float = 0.0
    average_winrate_decay: float = 0.0
    average_drawdown_expansion: float = 0.0
    walk_forward_confidence: float = 0.0
    walk_forward_confidence_classification: str = "Overfit"
    heatmap_dataset: List[Dict[str, Any]] = Field(default_factory=list)


# --- Core Analyzer ---

class WalkForwardAnalyzer:
    
    @staticmethod
    def get_active_trading_days(db_path: str, start_date: str, end_date: str) -> List[str]:
        """
        Query distinct trading days present in the underlying candles database.
        """
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT date(timestamp) FROM underlying_candles "
            "WHERE date(timestamp) >= ? AND date(timestamp) <= ? "
            "ORDER BY date(timestamp)",
            (start_date, end_date)
        )
        days = [r[0] for r in cur.fetchall()]
        conn.close()
        return days

    @staticmethod
    def generate_windows_by_days(days: List[str], train_len: int, test_len: int, step_len: int) -> List[Dict[str, Any]]:
        """
        Generates rolling training/testing window boundaries from a list of trading days.
        """
        windows = []
        n = len(days)
        idx = 0
        w_index = 0
        while True:
            train_start_idx = idx
            train_end_idx = train_start_idx + train_len - 1
            test_start_idx = train_end_idx + 1
            test_end_idx = test_start_idx + test_len - 1
            
            if test_end_idx >= n:
                break
                
            windows.append({
                "window_index": w_index,
                "train_start": days[train_start_idx],
                "train_end": days[train_end_idx],
                "test_start": days[test_start_idx],
                "test_end": days[test_end_idx]
            })
            w_index += 1
            idx += step_len
            
        return windows

    @staticmethod
    def analyze(
        base_config: BacktestConfig,
        ranges: List[ParameterRange],
        train_days: int = 2,
        test_days: int = 1,
        step_days: int = 1,
        db_path: str = "/Users/rajumaharjan/Documents/Anit Gravity Projects/Valkyrie/backend/v2/valkyrie_options_cache.db"
    ) -> WalkForwardReport:
        """
        Executes the walk-forward testing validation pipeline.
        """
        # 1. Fetch active trading days
        days = WalkForwardAnalyzer.get_active_trading_days(db_path, base_config.start_date, base_config.end_date)
        if len(days) < (train_days + test_days):
            raise ValueError(
                f"Insufficient trading days ({len(days)}) for train_days={train_days} and test_days={test_days}."
            )
            
        # 2. Generate window boundaries
        win_specs = WalkForwardAnalyzer.generate_windows_by_days(days, train_days, test_days, step_days)
        if not win_specs:
            raise ValueError("No walk forward windows could be generated with the specified durations.")
            
        windows_results: List[WalkForwardWindow] = []
        
        # 3. Process each window
        for spec in win_specs:
            w_idx = spec["window_index"]
            logger.info(f"Processing Walk-Forward Window {w_idx}: Train {spec['train_start']}->{spec['train_end']} | Test {spec['test_start']}->{spec['test_end']}")
            
            # --- TRAINING PHASE ---
            # Construct training base config
            train_config = base_config.model_copy(deep=True)
            train_config.start_date = spec["train_start"]
            train_config.end_date = spec["train_end"]
            
            # Run grid optimization
            opt_engine = OptimizationEngine(initial_capital=base_config.execution.initial_balance)
            opt_report = opt_engine.run_optimization(train_config, ranges)
            
            if not opt_report.top_10:
                # Fallback if no valid parameter sets were generated
                best_params = {}
                train_net_profit = 0.0
                train_win_rate = 0.0
                train_profit_factor = 0.0
                train_max_drawdown = 0.0
                train_net_return = 0.0
                train_robustness_score = 0.0
                train_classification = "Dangerous"
            else:
                best_combo = opt_report.top_10[0]
                best_params = best_combo.combination.params
                
                # Run robustness analysis on best train parameters
                train_robust_config = train_config.model_copy(deep=True)
                train_robust_config.strategy_params.update(best_params)
                
                # Map fastEma/slowEma to fast_period/slow_period
                if "fastEma" in best_params:
                    train_robust_config.strategy_params["fast_period"] = int(best_params["fastEma"])
                if "slowEma" in best_params:
                    train_robust_config.strategy_params["slow_period"] = int(best_params["slowEma"])
                    
                train_robustness = ExecutionRobustnessAnalyzer.analyze(train_robust_config)
                
                # Theoretical baseline metrics are in the mode results
                theo_train = train_robustness.mode_results["THEORETICAL"]
                train_net_profit = theo_train.net_profit
                train_win_rate = theo_train.win_rate
                train_profit_factor = theo_train.profit_factor
                train_max_drawdown = theo_train.max_drawdown
                train_net_return = theo_train.net_return
                train_robustness_score = train_robustness.robustness_score
                train_classification = train_robustness.classification
                
            # --- OUT-OF-SAMPLE TESTING PHASE ---
            test_config = base_config.model_copy(deep=True)
            test_config.start_date = spec["test_start"]
            test_config.end_date = spec["test_end"]
            test_config.strategy_params.update(best_params)
            
            if "fastEma" in best_params:
                test_config.strategy_params["fast_period"] = int(best_params["fastEma"])
            if "slowEma" in best_params:
                test_config.strategy_params["slow_period"] = int(best_params["slowEma"])
                
            # Run Robustness / Execution Reality analysis on the test window
            test_robustness = ExecutionRobustnessAnalyzer.analyze(test_config)
            
            # Extract test mode metrics
            theo_test = test_robustness.mode_results["THEORETICAL"]
            test_net_profit = theo_test.net_profit
            test_win_rate = theo_test.win_rate
            test_profit_factor = theo_test.profit_factor
            test_max_drawdown = theo_test.max_drawdown
            test_net_return = theo_test.net_return
            test_robustness_score = test_robustness.robustness_score
            test_classification = test_robustness.classification
            
            # Serialize test mode results
            test_mode_results = {}
            for mode, m_res in test_robustness.mode_results.items():
                test_mode_results[mode] = {
                    "net_profit": m_res.net_profit,
                    "win_rate": m_res.win_rate,
                    "profit_factor": m_res.profit_factor,
                    "max_drawdown": m_res.max_drawdown,
                    "net_return": m_res.net_return
                }
                
            # V2 Extension: Regime classification using underlying prices
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute(
                    "SELECT close FROM underlying_candles "
                    "WHERE date(timestamp) >= ? AND date(timestamp) <= ? "
                    "ORDER BY timestamp",
                    (spec["test_start"], spec["test_end"])
                )
                prices = [r[0] for r in cur.fetchall()]
                conn.close()
                if len(prices) >= 2:
                    net_change_pct = (prices[-1] - prices[0]) / prices[0] * 100.0
                    if net_change_pct > 0.5:
                        regime = "BULL"
                    elif net_change_pct < -0.5:
                        regime = "BEAR"
                    else:
                        regime = "SIDEWAYS"
                else:
                    regime = "SIDEWAYS"
            except Exception as e:
                logger.error(f"Error classifying regime: {e}")
                regime = "SIDEWAYS"

            # V2 Extension: Decays calculation
            profit_decay = ((train_net_profit - test_net_profit) / (train_net_profit if train_net_profit != 0 else 1.0)) * 100.0
            pf_decay = ((train_profit_factor - test_profit_factor) / (train_profit_factor if train_profit_factor != 0 else 1.0)) * 100.0
            winrate_decay = ((train_win_rate - test_win_rate) / (train_win_rate if train_win_rate != 0 else 1.0)) * 100.0
            drawdown_expansion = ((test_max_drawdown - train_max_drawdown) / (train_max_drawdown if train_max_drawdown != 0 else 1.0)) * 100.0

            windows_results.append(
                WalkForwardWindow(
                    window_index=w_idx,
                    train_start=spec["train_start"],
                    train_end=spec["train_end"],
                    test_start=spec["test_start"],
                    test_end=spec["test_end"],
                    best_params=best_params,
                    train_net_profit=train_net_profit,
                    train_win_rate=train_win_rate,
                    train_profit_factor=train_profit_factor,
                    train_max_drawdown=train_max_drawdown,
                    train_net_return=train_net_return,
                    train_robustness_score=train_robustness_score,
                    train_classification=train_classification,
                    test_net_profit=test_net_profit,
                    test_win_rate=test_win_rate,
                    test_profit_factor=test_profit_factor,
                    test_max_drawdown=test_max_drawdown,
                    test_net_return=test_net_return,
                    test_robustness_score=test_robustness_score,
                    test_classification=test_classification,
                    test_mode_results=test_mode_results,
                    profit_decay=round(profit_decay, 2),
                    pf_decay=round(pf_decay, 2),
                    winrate_decay=round(winrate_decay, 2),
                    drawdown_expansion=round(drawdown_expansion, 2),
                    regime=regime,
                    test_equity_curve=test_robustness.theoretical_equity_curve
                )
            )
            
        # 4. Calculate Stability Metrics across all windows
        avg_train_profit = sum(w.train_net_profit for w in windows_results) / len(windows_results)
        avg_test_profit = sum(w.test_net_profit for w in windows_results) / len(windows_results)
        
        avg_train_pf = sum(w.train_profit_factor for w in windows_results) / len(windows_results)
        avg_test_pf = sum(w.test_profit_factor for w in windows_results) / len(windows_results)
        
        avg_train_dd = sum(w.train_max_drawdown for w in windows_results) / len(windows_results)
        avg_test_dd = sum(w.test_max_drawdown for w in windows_results) / len(windows_results)
        
        avg_train_robust = sum(w.train_robustness_score for w in windows_results) / len(windows_results)
        avg_test_robust = sum(w.test_robustness_score for w in windows_results) / len(windows_results)
        
        profitable_test_windows = sum(1 for w in windows_results if w.test_net_profit > 0)
        consistency_score = (profitable_test_windows / len(windows_results)) * 100.0
        
        # Stability Ratios (0.0 to 1.0)
        # Profit stability
        if avg_train_profit <= 0:
            profit_stability = 1.0 if avg_test_profit >= 0 else 0.0
        else:
            profit_stability = max(0.0, min(1.0, avg_test_profit / avg_train_profit))
            
        # PF stability
        if avg_train_pf <= 0:
            pf_stability = 1.0 if avg_test_pf >= 0 else 0.0
        else:
            pf_stability = max(0.0, min(1.0, avg_test_pf / avg_train_pf))
            
        # DD stability (lower is better, so ratio of train DD / test DD)
        if avg_test_dd <= 0:
            dd_stability = 1.0
        else:
            if avg_test_dd <= avg_train_dd:
                dd_stability = 1.0
            else:
                dd_stability = avg_train_dd / avg_test_dd
                
        # Robustness stability
        if avg_train_robust <= 0:
            robustness_stability = 1.0 if avg_test_robust >= 0 else 0.0
        else:
            robustness_stability = max(0.0, min(1.0, avg_test_robust / avg_train_robust))
            
        stability = WalkForwardStability(
            profit_stability=round(profit_stability, 4),
            pf_stability=round(pf_stability, 4),
            drawdown_stability=round(dd_stability, 4),
            robustness_stability=round(robustness_stability, 4),
            consistency_score=round(consistency_score, 2)
        )
        
        # 5. Walk Forward Score (0-100)
        raw_wf_score = (
            0.30 * (consistency_score / 100.0) +
            0.20 * profit_stability +
            0.20 * pf_stability +
            0.15 * dd_stability +
            0.15 * robustness_stability
        )
        walk_forward_score = round(raw_wf_score * 100.0, 2)
        
        # Classifications
        if walk_forward_score >= 90:
            classification = "Institutional"
        elif walk_forward_score >= 75:
            classification = "Strong"
        elif walk_forward_score >= 60:
            classification = "Tradable"
        elif walk_forward_score >= 40:
            classification = "Fragile"
        else:
            classification = "Overfit"

        # V2 Extension: Calculate aggregated decays
        average_profit_decay = sum(w.profit_decay for w in windows_results) / len(windows_results)
        average_pf_decay = sum(w.pf_decay for w in windows_results) / len(windows_results)
        average_winrate_decay = sum(w.winrate_decay for w in windows_results) / len(windows_results)
        average_drawdown_expansion = sum(w.drawdown_expansion for w in windows_results) / len(windows_results)

        # V2 Extension: Parameter drift analysis
        parameter_drift_analysis = {}
        all_param_keys = set()
        for w in windows_results:
            all_param_keys.update(w.best_params.keys())

        for p_key in all_param_keys:
            vals = [float(w.best_params[p_key]) for w in windows_results if p_key in w.best_params]
            if vals:
                avg_val = sum(vals) / len(vals)
                variance = sum((v - avg_val)**2 for v in vals) / len(vals) if len(vals) > 1 else 0.0
                std_dev = variance ** 0.5
                p_stability = max(0.0, min(1.0, 1.0 - (std_dev / (avg_val if avg_val != 0 else 1.0))))
                drift_pct = ((vals[-1] - vals[0]) / (vals[0] if vals[0] != 0 else 1.0)) * 100.0
                drift_vel = (vals[-1] - vals[0]) / (len(vals) - 1) if len(vals) >= 2 else 0.0
                trend = "UPWARD" if drift_vel > 0 else ("DOWNWARD" if drift_vel < 0 else "STABLE")
                parameter_drift_analysis[p_key] = {
                    "stability": round(p_stability, 4),
                    "average_value": round(avg_val, 4),
                    "drift_pct": round(drift_pct, 2),
                    "drift_velocity": round(drift_vel, 4),
                    "drift_trend": trend
                }

        # V2 Extension: OOS Equity Curve Stitching
        stitched_oos_equity_curve = []
        current_equity = base_config.execution.initial_balance
        for w in windows_results:
            if not w.test_equity_curve:
                continue
            start_val = w.test_equity_curve[0]["equity"]
            for pt in w.test_equity_curve:
                pnl = pt["equity"] - start_val
                stitched_oos_equity_curve.append({
                    "date": pt["date"],
                    "equity": round(current_equity + pnl, 2)
                })
            current_equity += (w.test_equity_curve[-1]["equity"] - start_val)

        # V2 Extension: Heatmap Dataset Generation
        heatmap_dataset = []
        for w in windows_results:
            p_stab = max(0.0, min(1.0, w.test_net_profit / w.train_net_profit)) if w.train_net_profit > 0 else (1.0 if w.test_net_profit >= 0 else 0.0)
            pf_stab = max(0.0, min(1.0, w.test_profit_factor / w.train_profit_factor)) if w.train_profit_factor > 0 else (1.0 if w.test_profit_factor >= 0 else 0.0)
            heatmap_dataset.append({
                "window": w.window_index,
                "profit_stability": round(p_stab, 4),
                "pf_stability": round(pf_stab, 4),
                "robustness": round(w.test_robustness_score / 100.0, 4)
            })

        # V2 Extension: Confidence Score Calculation
        sub_consistency = consistency_score
        sub_stability = 100.0 * (profit_stability + pf_stability + dd_stability + robustness_stability) / 4.0
        
        if parameter_drift_analysis:
            avg_p_stab = sum(d["stability"] for d in parameter_drift_analysis.values()) / len(parameter_drift_analysis)
        else:
            avg_p_stab = 1.0
        sub_param_stability = avg_p_stab * 100.0

        p_d_pen = max(0.0, min(100.0, average_profit_decay))
        pf_d_pen = max(0.0, min(100.0, average_pf_decay))
        wr_d_pen = max(0.0, min(100.0, average_winrate_decay))
        dd_e_pen = max(0.0, min(100.0, average_drawdown_expansion))
        sub_decay = max(0.0, 100.0 - (p_d_pen + pf_d_pen + wr_d_pen + dd_e_pen) / 4.0)

        walk_forward_confidence = 0.25 * sub_consistency + 0.25 * sub_stability + 0.25 * sub_param_stability + 0.25 * sub_decay
        walk_forward_confidence = round(max(0.0, min(100.0, walk_forward_confidence)), 2)

        # Confidence Classification
        if walk_forward_confidence >= 95:
            conf_class = "Institutional"
        elif walk_forward_confidence >= 80:
            conf_class = "Strong"
        elif walk_forward_confidence >= 60:
            conf_class = "Tradable"
        elif walk_forward_confidence >= 40:
            conf_class = "Fragile"
        else:
            conf_class = "Overfit"

        return WalkForwardReport(
            walk_forward_score=walk_forward_score,
            classification=classification,
            stability=stability,
            windows=windows_results,
            parameter_drift_analysis=parameter_drift_analysis,
            stitched_oos_equity_curve=stitched_oos_equity_curve,
            average_profit_decay=round(average_profit_decay, 2),
            average_pf_decay=round(average_pf_decay, 2),
            average_winrate_decay=round(average_winrate_decay, 2),
            average_drawdown_expansion=round(average_drawdown_expansion, 2),
            walk_forward_confidence=walk_forward_confidence,
            walk_forward_confidence_classification=conf_class,
            heatmap_dataset=heatmap_dataset
        )
