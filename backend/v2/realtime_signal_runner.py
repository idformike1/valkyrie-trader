import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from v2.config import BacktestConfig
from v2.signal_adapter import SignalAdapter
from v2.position_manager import PositionManager
from v2.paper_execution_adapter import PaperExecutionAdapter
from v2.telemetry_logger import TelemetryLogger

logger = logging.getLogger("Valkyrie.RealtimeSignalRunner")

class RealtimeSignalRunner:
    """
    Orchestrator for V2 real-time strategy signal processing and paper execution.
    - Manages rollings completed candle buffer in memory.
    - Performs risk validation audits (SL, Target, cutoff bounds) on active exposures.
    - Runs SignalAdapter models on candle history.
    - Executes BUY/SELL transactions synchronously.
    """
    def __init__(self, config: BacktestConfig, position_manager: PositionManager, db_path: Optional[str] = None):
        self.config = config
        self.position_manager = position_manager
        self.execution_adapter = PaperExecutionAdapter(position_manager, config, db_path)
        
        # Setup strategy pipeline
        self.is_dynamic = False
        self.strategy_def = None
        if getattr(config, "strategy_definition", None) is not None:
            from v2.strategy_builder import StrategyDefinition, SignalPipeline
            self.strategy_def = StrategyDefinition(**config.strategy_definition)
            self.adapter = SignalPipeline(self.strategy_def)
            self.strategy_name = self.strategy_def.name
            self.is_dynamic = True
        else:
            self.adapter = SignalAdapter(config.strategy_name, config.strategy_params)
            self.strategy_name = config.strategy_name
            self.is_dynamic = False

        self.candle_buffer: List[Dict[str, Any]] = []
        self.active_contract: Optional[Dict[str, Any]] = None
        self.entry_index = 0
        self.is_paused = False

    def on_candle(self, candle: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        Invoked on each completed real-time index candle.
        1. Checks risk exits (daily cutoff, target, stop loss, trailing SL, max hold) first.
        2. Appends candle to buffer.
        3. Invokes SignalAdapter crossover rules.
        4. Fills transactions via PaperExecutionAdapter.
        
        Returns:
            Tuple[str, Dict[str, Any]] representing the execution action (BUY, SELL, or HOLD) and transaction metadata.
        """
        if self.is_paused:
            return "HOLD", {}

        current_ts = candle["timestamp"]
        if isinstance(current_ts, str):
            current_ts = datetime.fromisoformat(current_ts.replace('Z', '+00:00'))

        spot_price = float(candle["close"])

        # --- STEP 1: RISK EXITS EVALUATION ---
        if self.position_manager.active_position is not None and self.active_contract is not None:
            active = self.active_contract
            
            # 1.1 Daily Intraday cutoff time check
            cutoff_str = self.config.risk_management.cutoff_time or "15:15"
            try:
                cutoff_time = datetime.strptime(cutoff_str, "%H:%M").time()
                if current_ts.time() >= cutoff_time:
                    pos_data = self.execution_adapter.execute_sell(spot_price, current_ts, exit_reason="Intraday Cutoff Trigger")
                    self.active_contract = None
                    self.adapter.reset_state()
                    return "SELL", pos_data or {"exit_reason": "Intraday Cutoff Trigger"}
            except Exception as e:
                logger.error(f"Failed to check cutoff time: {e}")

            # 1.2 Maximum holding candles check
            candles_held = len(self.candle_buffer) - self.entry_index
            max_hold = self.config.risk_management.max_holding_candles
            if max_hold and candles_held >= max_hold:
                pos_data = self.execution_adapter.execute_sell(spot_price, current_ts, exit_reason="Maximum Holding Reached")
                self.active_contract = None
                self.adapter.reset_state()
                return "SELL", pos_data or {"exit_reason": "Maximum Holding Reached"}

            # 1.3 Premium/Spot evaluation
            held_premium = self.execution_adapter.estimate_premium(
                underlying=self.config.underlying_instrument_key,
                strike=active["strike"],
                expiry=active["expiry"],
                option_type=active["option_type"],
                spot_price=spot_price,
                timestamp=current_ts
            )
            
            active["last_premium"] = held_premium
            if held_premium > active.get("highest_premium", 0.0):
                active["highest_premium"] = held_premium

            exit_reason = None
            exit_price = held_premium

            # Dynamic strategy exits
            if self.is_dynamic and self.strategy_def is not None:
                from v2.strategy_builder.risk_engine import RiskEngine
                exit_reason, exit_price = RiskEngine.evaluate_exits(
                    self.strategy_def.risk,
                    active,
                    held_premium,
                    spot_price,
                    candles_held
                )
            else:
                # Standard risk SL / TP checking
                rm = self.config.risk_management
                entry_premium = active["entry_premium"]

                # Check Stop Loss
                if rm.stop_loss_value > 0:
                    sl_pct = rm.stop_loss_value / 100.0 if rm.stop_loss_type == "percent" else 0.0
                    sl_pts = rm.stop_loss_value if rm.stop_loss_type == "points" else (entry_premium * sl_pct)
                    
                    if held_premium <= (entry_premium - sl_pts):
                        exit_reason = "Stop Loss Hit"
                        exit_price = entry_premium - sl_pts

                # Check Target (Take Profit)
                if not exit_reason and rm.target_value > 0:
                    t_pct = rm.target_value / 100.0 if rm.target_type == "percent" else 0.0
                    t_pts = rm.target_value if rm.target_type == "points" else (entry_premium * t_pct)
                    
                    if held_premium >= (entry_premium + t_pts):
                        exit_reason = "Target Hit"
                        exit_price = entry_premium + t_pts

                # Check Trailing SL
                if not exit_reason and rm.trailing_sl_gap > 0:
                    highest = active.get("highest_premium", entry_premium)
                    if held_premium <= (highest - rm.trailing_sl_gap):
                        exit_reason = "Trailing SL Hit"
                        exit_price = highest - rm.trailing_sl_gap

            if exit_reason:
                pos_data = self.execution_adapter.execute_sell(exit_price, current_ts, exit_reason=exit_reason)
                self.active_contract = None
                self.adapter.reset_state()
                return "SELL", pos_data or {"exit_reason": exit_reason, "exit_price": exit_price}

        # --- STEP 2: SIGNAL GENERATION ---
        self.candle_buffer.append(candle)
        signal, info = self.adapter.evaluate(self.candle_buffer)

        if signal == "BUY":
            if self.position_manager.active_position is None:
                TelemetryLogger.log(
                    "SIGNAL",
                    "INFO",
                    f"BUY signal triggered by strategy logic. Spot: {spot_price}",
                    {"spot": spot_price, "timestamp": current_ts.isoformat()}
                )
                
                pos_data = self.execution_adapter.execute_buy(
                    underlying=self.config.underlying_instrument_key,
                    spot_price=spot_price,
                    timestamp=current_ts
                )
                
                self.entry_index = len(self.candle_buffer) - 1
                self.active_contract = {
                    "strike": pos_data["strike"],
                    "expiry": pos_data["expiry"],
                    "option_type": pos_data["option_type"],
                    "instrument_key": pos_data["instrument_key"],
                    "entry_premium": pos_data["premium_price"],
                    "entry_spot": spot_price,
                    "highest_premium": pos_data["premium_price"],
                    "last_premium": pos_data["premium_price"]
                }
                return "BUY", pos_data

        elif signal in ["SELL", "EXIT"]:
            if self.position_manager.active_position is not None:
                TelemetryLogger.log(
                    "SIGNAL",
                    "INFO",
                    f"SELL signal triggered by strategy logic. Spot: {spot_price}",
                    {"spot": spot_price, "timestamp": current_ts.isoformat()}
                )
                
                pos_data = self.execution_adapter.execute_sell(
                    spot_price=spot_price,
                    timestamp=current_ts,
                    exit_reason="Strategy Crossover Exit"
                )
                self.active_contract = None
                return "SELL", pos_data or {}

        # Handle Hold events
        if self.position_manager.active_position is not None and self.active_contract is not None:
            held_premium = self.active_contract["last_premium"]
            self.position_manager.hold_position({"premium_price": float(held_premium)}, current_ts)

        return "HOLD", {}
