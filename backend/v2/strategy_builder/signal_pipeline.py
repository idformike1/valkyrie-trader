import pandas as pd
from typing import Dict, Any, Tuple
from datetime import datetime
from v2.strategy_builder.strategy_definition import StrategyDefinition
from v2.strategy_builder.indicator_registry import IndicatorRegistry
from v2.strategy_builder.rule_engine import RuleEngine

def invert_condition(condition: Dict[str, Any]) -> Dict[str, Any]:
    if not condition or not isinstance(condition, dict):
        return {}
        
    operator = condition.get("operator")
    if operator:
        op_upper = operator.upper()
        sub_conds = condition.get("conditions", [])
        if op_upper == "AND":
            return {
                "operator": "OR",
                "conditions": [invert_condition(c) for c in sub_conds]
            }
        elif op_upper == "OR":
            return {
                "operator": "AND",
                "conditions": [invert_condition(c) for c in sub_conds]
            }
        elif op_upper == "NOT":
            if isinstance(sub_conds, list) and sub_conds:
                return sub_conds[0]
            nested = condition.get("condition")
            if nested:
                return nested
            return {}
            
    cond_type = condition.get("type")
    if not cond_type:
        return {}
        
    params = condition.get("params", {})
    type_lower = cond_type.lower()
    
    if type_lower == "crossover_up":
        return {"type": "crossover_down", "params": params}
    elif type_lower == "crossover_down":
        return {"type": "crossover_up", "params": params}
    elif type_lower in ["greater_than", "greaterthan", "gt", ">"]:
        return {"type": "less_than", "params": params}
    elif type_lower in ["less_than", "lessthan", "lt", "<"]:
        return {"type": "greater_than", "params": params}
    elif type_lower in ["equal", "eq", "=="]:
        val = params.get("value")
        if val == "GREEN":
            new_params = params.copy()
            new_params["value"] = "RED"
            return {"type": "equal", "params": new_params}
        elif val == "RED":
            new_params = params.copy()
            new_params["value"] = "GREEN"
            return {"type": "equal", "params": new_params}
        return {"type": "not_equal", "params": params}
        
    return {"operator": "NOT", "conditions": [condition]}

class SignalPipeline:
    def __init__(self, definition: StrategyDefinition):
        self.definition = definition
        self.is_holding = False
        self.entry_price = 0.0
        self.candles_held = 0
        self.entry_timestamp = None
        
    def reset_state(self):
        self.is_holding = False
        self.entry_price = 0.0
        self.candles_held = 0
        self.entry_timestamp = None

    def evaluate(self, df_input: Any) -> Tuple[str, Dict[str, Any]]:
        """
        Evaluates signals on the given DataFrame or list of candle dicts.
        Returns:
            Tuple of (action, info_dict)
            action can be "BUY", "SELL", or "HOLD".
        """
        if isinstance(df_input, list):
            if not df_input:
                return "HOLD", {}
            df = pd.DataFrame(df_input)
        else:
            df = df_input
            
        if df.empty:
            return "HOLD", {}
            
        # Enforce warm-up candles based on maximum indicator period
        max_period = 0
        indicators = self.definition.signal.indicators
        for col_name, ind_config in indicators.items():
            params = ind_config.get("params", {})
            for k in ["period", "fast_period", "slow_period", "signal_period"]:
                if k in params:
                    try:
                        max_period = max(max_period, int(params[k]))
                    except (ValueError, TypeError):
                        pass
        
        min_candles = max(3, max_period + 2)
        if len(df) < min_candles:
            return "HOLD", {}
            
        df_calc = df.copy()
        if "timestamp" in df_calc.columns:
            df_calc["timestamp"] = pd.to_datetime(df_calc["timestamp"])
        
        # 1. Compute registered indicators
        indicators = self.definition.signal.indicators
        for col_name, ind_config in indicators.items():
            ind_type = ind_config.get("type")
            params = ind_config.get("params", {})
            
            try:
                ind_cls = IndicatorRegistry.get(ind_type)
                ind_instance = ind_cls()
                result = ind_instance.calculate(df_calc, params, col_name)
                
                if isinstance(result, pd.Series):
                    df_calc[col_name] = result
                elif isinstance(result, pd.DataFrame):
                    for col in result.columns:
                        df_calc[col] = result[col]
            except Exception as e:
                raise RuntimeError(f"Failed to calculate indicator {col_name} ({ind_type}): {e}")

        # Get the current tick (last candle in history)
        current_tick = df_calc.iloc[-1]
        
        ts = current_tick.get('timestamp')
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        else:
            dt = ts
            
        current_time = dt.time()
        
        cutoff_time = None
        if self.definition.exit.time_exit and self.definition.exit.time_exit.cutoff_time:
            cutoff_time = datetime.strptime(self.definition.exit.time_exit.cutoff_time, "%H:%M").time()
            
        # EXITS
        if self.is_holding:
            self.candles_held += 1
            
            # 1. Cutoff time exit
            if cutoff_time and current_time >= cutoff_time:
                self.reset_state()
                return "SELL", {"reason": "SESSION_END", "price": float(current_tick['close'])}
                
            # 2. Custom exit condition evaluation
            custom_exit_cond = getattr(self.definition.exit, "exit_condition", None)
            if custom_exit_cond and RuleEngine.evaluate(df_calc, custom_exit_cond):
                self.reset_state()
                return "SELL", {"reason": "TECHNICAL_EXIT", "price": float(current_tick['close'])}
                
            # 3. Reversal exit evaluation
            if self.definition.exit.exit_on_reversal:
                inv_cond = invert_condition(self.definition.signal.entry_condition)
                if RuleEngine.evaluate(df_calc, inv_cond):
                    self.reset_state()
                    return "SELL", {"reason": "TECHNICAL_REVERSAL", "price": float(current_tick['close'])}
                    
            return "HOLD", {}
            
        # ENTRIES
        else:
            if cutoff_time and current_time >= cutoff_time:
                return "HOLD", {}
                
            # Check entry condition
            if RuleEngine.evaluate(df_calc, self.definition.signal.entry_condition):
                self.is_holding = True
                self.entry_price = float(current_tick['close'])
                self.candles_held = 0
                self.entry_timestamp = ts
                return "BUY", {"entry_price": self.entry_price, "timestamp": self.entry_timestamp}
                
            return "HOLD", {}
