from typing import Dict, Any, Optional, Tuple

class RiskEngine:
    @classmethod
    def evaluate_exits(
        cls,
        risk_config: Any,
        active_contract: Dict[str, Any],
        current_premium: float,
        current_spot: float,
        candles_held: int
    ) -> Tuple[Optional[str], float]:
        """
        Evaluates risk-based exits (Stop Loss, Take Profit, Trailing Stop Loss, Max Candles).
        Returns (exit_reason, exit_price).
        If no exit is triggered, returns (None, 0.0).
        """
        if hasattr(risk_config, "dict"):
            risk_dict = risk_config.dict()
        elif hasattr(risk_config, "model_dump"):
            risk_dict = risk_config.model_dump()
        else:
            risk_dict = risk_config or {}
            
        entry_premium = active_contract.get("entry_premium", current_premium)
        highest_premium = active_contract.get("highest_premium", entry_premium)
        
        # Update highest premium for trailing SL
        if current_premium > highest_premium:
            highest_premium = current_premium
            active_contract["highest_premium"] = highest_premium
            
        # 1. Stop Loss Evaluation
        sl_config = risk_dict.get("stop_loss", {})
        if sl_config:
            sl_type = sl_config.get("type", "none").lower()
            sl_val = float(sl_config.get("value", 0.0))
            if sl_type != "none" and sl_val > 0.0:
                if sl_type == "points":
                    sl_price = entry_premium - sl_val
                elif sl_type == "percent":
                    sl_price = entry_premium * (1.0 - sl_val / 100.0)
                else:
                    sl_price = 0.0
                    
                if sl_price > 0.0 and current_premium <= sl_price:
                    return "STOP_LOSS", current_premium
                    
        # 2. Take Profit Evaluation
        tp_config = risk_dict.get("take_profit", {})
        if tp_config:
            tp_type = tp_config.get("type", "none").lower()
            tp_val = float(tp_config.get("value", 0.0))
            if tp_type != "none" and tp_val > 0.0:
                if tp_type == "points":
                    tp_price = entry_premium + tp_val
                elif tp_type == "percent":
                    tp_price = entry_premium * (1.0 + tp_val / 100.0)
                else:
                    tp_price = 0.0
                    
                if tp_price > 0.0 and current_premium >= tp_price:
                    return "TAKE_PROFIT", current_premium

        # 3. Trailing Stop Loss Evaluation
        trailing_config = risk_dict.get("trailing_sl", {})
        if trailing_config:
            trailing_type = trailing_config.get("type", "none").lower()
            trailing_val = float(trailing_config.get("value", 0.0))
            if trailing_type != "none" and trailing_val > 0.0:
                if trailing_type == "points":
                    trail_sl = highest_premium - trailing_val
                elif trailing_type == "percent":
                    trail_sl = highest_premium * (1.0 - trailing_val / 100.0)
                else:
                    trail_sl = 0.0
                    
                if trail_sl > 0.0 and current_premium <= trail_sl:
                    return "TRAILING_STOP_LOSS", current_premium
                    
        # 4. Max Candles Evaluation
        max_candles = risk_dict.get("max_holding_candles")
        if max_candles is not None and int(max_candles) > 0:
            if candles_held >= int(max_candles):
                return "MAX_DURATION", current_premium
                
        return None, 0.0
