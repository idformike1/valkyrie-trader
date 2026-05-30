import pandas as pd
from typing import Dict, Any, Union, List

class RuleEngine:
    @classmethod
    def evaluate(cls, df: pd.DataFrame, condition: Dict[str, Any]) -> bool:
        """
        Recursively evaluates a logical condition dictionary on the given DataFrame.
        """
        if not condition or not isinstance(condition, dict):
            return False
            
        # Check if it is a logical operator node
        operator = condition.get("operator")
        if operator:
            op_upper = operator.upper()
            sub_conds = condition.get("conditions", [])
            
            if op_upper == "AND":
                if not sub_conds:
                    return False
                return all(cls.evaluate(df, c) for c in sub_conds)
                
            elif op_upper == "OR":
                if not sub_conds:
                    return False
                return any(cls.evaluate(df, c) for c in sub_conds)
                
            elif op_upper == "NOT":
                if isinstance(sub_conds, list):
                    if not sub_conds:
                        return False
                    return not cls.evaluate(df, sub_conds[0])
                else:
                    nested = condition.get("condition")
                    if nested:
                        return not cls.evaluate(df, nested)
                    return False
            else:
                raise ValueError(f"Unsupported logical operator: {operator}")
                
        # If not operator, it is a condition leaf node
        cond_type = condition.get("type")
        if not cond_type:
            raise ValueError("Condition node must have either an 'operator' or a 'type'.")
            
        params = condition.get("params", {})
        return cls.evaluate_leaf(df, cond_type, params)

    @classmethod
    def evaluate_leaf(cls, df: pd.DataFrame, cond_type: str, params: Dict[str, Any]) -> bool:
        type_lower = cond_type.lower()
        
        if type_lower in ["crossover_up", "crossoverup"]:
            return cls.check_crossover_up(df, params)
            
        elif type_lower in ["crossover_down", "crossoverdown"]:
            return cls.check_crossover_down(df, params)
            
        elif type_lower in ["greater_than", "greaterthan", "gt", ">"]:
            primary = cls.resolve_operand(df, params.get("primary"))
            secondary = cls.resolve_operand(df, params.get("secondary", params.get("value")))
            if primary is None or secondary is None:
                return False
            multiplier = float(params.get("multiplier", 1.0))
            return primary > (secondary * multiplier)
            
        elif type_lower in ["less_than", "lessthan", "lt", "<"]:
            primary = cls.resolve_operand(df, params.get("primary"))
            secondary = cls.resolve_operand(df, params.get("secondary", params.get("value")))
            if primary is None or secondary is None:
                return False
            multiplier = float(params.get("multiplier", 1.0))
            return primary < (secondary * multiplier)
            
        elif type_lower in ["equal", "eq", "=="]:
            primary = cls.resolve_operand(df, params.get("primary"))
            secondary = cls.resolve_operand(df, params.get("secondary", params.get("value")))
            if primary is None or secondary is None:
                return False
            return primary == secondary
            
        else:
            raise ValueError(f"Unknown condition type: {cond_type}")

    @classmethod
    def resolve_operand(cls, df: pd.DataFrame, operand: Any) -> Any:
        if not isinstance(operand, str):
            return operand
            
        offset = -1
        if "[" in operand and operand.endswith("]"):
            try:
                parts = operand.split("[")
                col_name = parts[0]
                offset_str = parts[1][:-1]
                offset = int(offset_str)
            except Exception:
                col_name = operand
        else:
            col_name = operand
            
        col_name = col_name.replace(".", "_")
        
        if col_name in df.columns:
            if len(df) < abs(offset) if offset < 0 else len(df) <= offset:
                return None
            return df[col_name].iloc[offset]
            
        if col_name in ["open", "high", "low", "close", "volume"]:
            if len(df) < abs(offset) if offset < 0 else len(df) <= offset:
                return None
            return df[col_name].iloc[offset]
            
        return operand

    @classmethod
    def check_crossover_up(cls, df: pd.DataFrame, params: Dict[str, Any]) -> bool:
        primary = params.get("primary")
        secondary = params.get("secondary", params.get("value"))
        if not primary or secondary is None:
            return False
            
        p_col = str(primary).replace(".", "_")
        s_col = str(secondary).replace(".", "_")
        
        p_series = df[p_col] if p_col in df.columns else df[primary] if primary in df.columns else None
        if p_series is None and primary in ["close", "open", "high", "low", "volume"]:
            p_series = df[primary]
            
        s_series = df[s_col] if s_col in df.columns else df[secondary] if secondary in df.columns else None
        if s_series is None and secondary in ["close", "open", "high", "low", "volume"]:
            s_series = df[secondary]
            
        if p_series is None or len(df) < 2:
            return False
            
        if s_series is None:
            try:
                s_val = float(secondary)
                return p_series.iloc[-2] <= s_val and p_series.iloc[-1] > s_val
            except ValueError:
                return False
                
        return p_series.iloc[-2] <= s_series.iloc[-2] and p_series.iloc[-1] > s_series.iloc[-1]

    @classmethod
    def check_crossover_down(cls, df: pd.DataFrame, params: Dict[str, Any]) -> bool:
        primary = params.get("primary")
        secondary = params.get("secondary", params.get("value"))
        if not primary or secondary is None:
            return False
            
        p_col = str(primary).replace(".", "_")
        s_col = str(secondary).replace(".", "_")
        
        p_series = df[p_col] if p_col in df.columns else df[primary] if primary in df.columns else None
        if p_series is None and primary in ["close", "open", "high", "low", "volume"]:
            p_series = df[primary]
            
        s_series = df[s_col] if s_col in df.columns else df[secondary] if secondary in df.columns else None
        if s_series is None and secondary in ["close", "open", "high", "low", "volume"]:
            s_series = df[secondary]
            
        if p_series is None or len(df) < 2:
            return False
            
        if s_series is None:
            try:
                s_val = float(secondary)
                return p_series.iloc[-2] >= s_val and p_series.iloc[-1] < s_val
            except ValueError:
                return False
                
        return p_series.iloc[-2] >= s_series.iloc[-2] and p_series.iloc[-1] < s_series.iloc[-1]
