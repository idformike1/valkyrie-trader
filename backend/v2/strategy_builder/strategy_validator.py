from typing import Dict, Any, List, Tuple
from v2.strategy_builder.indicator_registry import IndicatorRegistry

class StrategyValidator:
    @classmethod
    def validate_dict(cls, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validates a strategy definition dictionary before parsing into Pydantic models.
        Returns a tuple of (is_valid, list_of_error_strings).
        """
        errors = []
        
        # 1. Required Top-Level Fields
        required_fields = ["strategy_id", "name", "description", "signal", "contract", "risk", "exit"]
        for f in required_fields:
            if f not in data or data[f] is None:
                errors.append(f"Missing required top-level field: '{f}'")
                
        if errors:
            return False, errors
            
        # 2. Schema version check
        schema_version = data.get("schema_version", "2.0.0")
        if not schema_version.startswith("2."):
            errors.append(f"Unsupported schema version: '{schema_version}'. Only 2.x versions are supported.")
            
        # 3. Validate Signal Section
        signal = data["signal"]
        if not isinstance(signal, dict):
            errors.append("Field 'signal' must be a dictionary.")
        else:
            indicators = signal.get("indicators", {})
            if not isinstance(indicators, dict):
                errors.append("Field 'signal.indicators' must be a dictionary.")
            else:
                for col_name, ind_config in indicators.items():
                    if not isinstance(ind_config, dict) or "type" not in ind_config:
                        errors.append(f"Indicator '{col_name}' configuration must be a dictionary with a 'type' field.")
                    else:
                        ind_type = ind_config["type"]
                        try:
                            IndicatorRegistry.get(ind_type)
                        except ValueError:
                            errors.append(f"Indicator '{col_name}' uses unregistered type '{ind_type}'.")
                            
            entry_cond = signal.get("entry_condition")
            if not entry_cond:
                errors.append("Missing required field: 'signal.entry_condition'")
            else:
                cls._validate_condition_node(entry_cond, errors)
                
        # 4. Validate Contract Section
        contract = data["contract"]
        if not isinstance(contract, dict):
            errors.append("Field 'contract' must be a dictionary.")
        else:
            if "underlying" not in contract:
                errors.append("Missing required field: 'contract.underlying'")
                
            opt_type = contract.get("option_type", "CE_ONLY")
            valid_opt_types = ["CE_ONLY", "PE_ONLY", "CE_PE", "DYNAMIC"]
            if opt_type not in valid_opt_types:
                errors.append(f"Invalid option_type '{opt_type}'. Supported values: {valid_opt_types}")
                
            strike = contract.get("strike", {})
            if not isinstance(strike, dict) or "mode" not in strike:
                errors.append("Field 'contract.strike' must have a 'mode' field.")
            else:
                mode = strike["mode"]
                valid_strike_modes = ["ATM", "ATM_PLUS_N", "ATM_MINUS_N", "DELTA", "PREMIUM_RANGE", "OTM_1", "OTM_2", "OTM_3", "ITM_1", "ITM_2", "ITM_3"]
                if not any(mode.startswith(m) for m in valid_strike_modes):
                    errors.append(f"Invalid strike mode: '{mode}'.")
                    
            expiry = contract.get("expiry", {})
            if not isinstance(expiry, dict) or "mode" not in expiry:
                errors.append("Field 'contract.expiry' must have a 'mode' field.")
            else:
                mode = expiry["mode"]
                valid_expiry_modes = ["CURRENT_WEEKLY", "NEXT_WEEKLY", "CURRENT_MONTHLY", "DTE_RANGE"]
                if mode not in valid_expiry_modes:
                    errors.append(f"Invalid expiry mode: '{mode}'. Supported values: {valid_expiry_modes}")
                    
        # 5. Validate Risk Section
        risk = data["risk"]
        if not isinstance(risk, dict):
            errors.append("Field 'risk' must be a dictionary.")
        else:
            pos_sizing = risk.get("position_sizing", {})
            if not isinstance(pos_sizing, dict):
                errors.append("Field 'risk.position_sizing' must be a dictionary.")
                
            sl = risk.get("stop_loss", {})
            if not isinstance(sl, dict):
                errors.append("Field 'risk.stop_loss' must be a dictionary.")
            elif sl:
                sl_type = sl.get("type", "none")
                valid_types = ["none", "points", "percent"]
                if sl_type not in valid_types:
                    errors.append(f"Invalid stop_loss type: '{sl_type}'. Supported values: {valid_types}")
                if sl_type != "none" and "value" not in sl:
                    errors.append("Stop loss is active but missing required field 'value'.")
                    
            tp = risk.get("take_profit", {})
            if not isinstance(tp, dict):
                errors.append("Field 'risk.take_profit' must be a dictionary.")
            elif tp:
                tp_type = tp.get("type", "none")
                valid_types = ["none", "points", "percent"]
                if tp_type not in valid_types:
                    errors.append(f"Invalid take_profit type: '{tp_type}'. Supported values: {valid_types}")
                if tp_type != "none" and "value" not in tp:
                    errors.append("Take profit is active but missing required field 'value'.")

        # 6. Validate Exit Section
        exit_rules = data["exit"]
        if not isinstance(exit_rules, dict):
            errors.append("Field 'exit' must be a dictionary.")
            
        return len(errors) == 0, errors

    @classmethod
    def _validate_condition_node(cls, node: Dict[str, Any], errors: List[str]):
        if not isinstance(node, dict):
            errors.append("Condition node must be a dictionary.")
            return
            
        operator = node.get("operator")
        if operator:
            op_upper = operator.upper()
            if op_upper not in ["AND", "OR", "NOT"]:
                errors.append(f"Invalid logical operator: '{operator}'. Supported: AND, OR, NOT")
                
            sub_conds = node.get("conditions", [])
            if not isinstance(sub_conds, list):
                errors.append(f"Field 'conditions' for operator '{operator}' must be a list.")
            else:
                for c in sub_conds:
                    cls._validate_condition_node(c, errors)
            
            nested = node.get("condition")
            if nested:
                cls._validate_condition_node(nested, errors)
                
            return
            
        cond_type = node.get("type")
        if not cond_type:
            errors.append("Condition node must have either an 'operator' or a 'type' field.")
            return
            
        valid_types = ["crossover_up", "crossoverup", "crossover_down", "crossoverdown", "greater_than", "greaterthan", "gt", ">", "less_than", "lessthan", "lt", "<", "equal", "eq", "=="]
        if cond_type.lower() not in valid_types:
            errors.append(f"Invalid condition type: '{cond_type}'. Supported: {valid_types}")
            
        params = node.get("params", {})
        if not isinstance(params, dict) or not params:
            errors.append(f"Condition type '{cond_type}' must have a non-empty 'params' dictionary.")
