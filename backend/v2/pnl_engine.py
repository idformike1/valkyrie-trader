from typing import List
from v2.position_models import Position
from v2.cost_models import CostModel, UpstoxCostModel
from v2.pnl_models import TradeCharges, TradePnL, TradeAccountingResult, BacktestAccountingResult, TradeExplanation, ExecutionAnalysis

class PnLEngine:
    def __init__(self, cost_model: CostModel = None):
        self.cost_model = cost_model or UpstoxCostModel()

    def calculate_gross_pnl(self, position: Position) -> float:
        if position.exit_premium is None:
            raise ValueError(
                f"Position {position.position_id} is not closed. "
                "exit_premium is required for PnL calculation."
            )
        return round((position.exit_premium - position.entry_premium) * position.quantity, 2)

    def calculate_pnl_and_charges(self, position: Position) -> TradePnL:
        gross_pnl = self.calculate_gross_pnl(position)
        charges = self.cost_model.calculate_charges(position)
        net_pnl = round(gross_pnl - charges.total_charges, 2)
        return TradePnL(
            gross_pnl=gross_pnl,
            total_charges=charges.total_charges,
            net_pnl=net_pnl
        )

    def account_trade(self, position: Position) -> TradeAccountingResult:
        pnl_result = self.calculate_pnl_and_charges(position)
        charges = self.cost_model.calculate_charges(position)
        
        contract_desc = f"{position.underlying} {position.strike:.1f} {position.option_type} ({position.expiry})"
        
        explanation = None
        if position.metadata and "explanation" in position.metadata:
            explanation = TradeExplanation(**position.metadata["explanation"])
            
        # Execution Reality Engine Integration
        meta = position.metadata or {}
        mode = meta.get("execution_model", "THEORETICAL")
        
        theoretical_entry = position.entry_premium
        theoretical_exit = position.exit_premium if position.exit_premium is not None else 0.0
        
        effective_entry = theoretical_entry
        effective_exit = theoretical_exit
        
        entry_spread_cost = 0.0
        entry_vol_cost = 0.0
        exit_spread_cost = 0.0
        exit_vol_cost = 0.0
        
        if mode != "THEORETICAL":
            entry_spot = meta.get("entry_spot_price", theoretical_entry)
            entry_dist = meta.get("entry_strike_distance", 0.0)
            entry_atr = meta.get("entry_atr", 10.0)
            entry_range = meta.get("entry_candle_range", 10.0)
            
            exit_spot = meta.get("exit_spot_price", theoretical_exit)
            exit_dist = meta.get("exit_strike_distance", 0.0)
            exit_atr = meta.get("exit_atr", 10.0)
            exit_range = meta.get("exit_candle_range", 10.0)
            
            from v2.execution_reality_engine import (
                calculate_spread_penalty,
                calculate_volatility_penalty,
                calculate_effective_fill
            )
            
            # Calculate entry penalties
            _, entry_spread_cost = calculate_spread_penalty(
                theoretical_entry, entry_spot, entry_dist, position.option_type, mode
            )
            _, entry_vol_cost = calculate_volatility_penalty(
                entry_atr, entry_range, theoretical_entry, mode
            )
            
            # Calculate exit penalties
            _, exit_spread_cost = calculate_spread_penalty(
                theoretical_exit, exit_spot, exit_dist, position.option_type, mode
            )
            _, exit_vol_cost = calculate_volatility_penalty(
                exit_atr, exit_range, theoretical_exit, mode
            )
            
            effective_entry, effective_exit = calculate_effective_fill(
                theoretical_entry, theoretical_exit,
                entry_spread_cost, entry_vol_cost,
                exit_spread_cost, exit_vol_cost,
                mode
            )
            
        theoretical_entry = round(theoretical_entry, 2)
        theoretical_exit = round(theoretical_exit, 2)
        effective_entry = round(effective_entry, 2)
        effective_exit = round(effective_exit, 2)

        spread_cost = (entry_spread_cost + exit_spread_cost) * position.quantity
        volatility_cost = (entry_vol_cost + exit_vol_cost) * position.quantity
        
        theo_gross = round((theoretical_exit - theoretical_entry) * position.quantity, 2)
        theo_net = round(theo_gross - charges.total_charges, 2)
        
        eff_gross = round((effective_exit - effective_entry) * position.quantity, 2)
        eff_net = round(eff_gross - charges.total_charges, 2)
        
        pnl_degradation = round(theo_net - eff_net, 2)
        
        execution_analysis = ExecutionAnalysis(
            execution_model=mode,
            theoretical_entry=round(theoretical_entry, 2),
            effective_entry=round(effective_entry, 2),
            theoretical_exit=round(theoretical_exit, 2),
            effective_exit=round(effective_exit, 2),
            spread_cost=round(spread_cost, 2),
            volatility_cost=round(volatility_cost, 2),
            pnl_degradation=round(pnl_degradation, 2)
        )
            
        return TradeAccountingResult(
            position_id=position.position_id,
            entry_time=position.entry_time,
            exit_time=position.exit_time,
            contract=contract_desc,
            entry_premium=round(effective_entry if mode != "THEORETICAL" else theoretical_entry, 2),
            exit_premium=round(effective_exit if mode != "THEORETICAL" else theoretical_exit, 2),
            quantity=position.quantity,
            gross_pnl=round(eff_gross if mode != "THEORETICAL" else theo_gross, 2),
            charges=charges,
            net_pnl=round(eff_net if mode != "THEORETICAL" else theo_net, 2),
            explanation=explanation,
            execution_analysis=execution_analysis
        )

    def generate_accounting_summary(self, positions: List[Position]) -> BacktestAccountingResult:
        trades = []
        total_gross = 0.0
        total_charges = 0.0
        total_net = 0.0
        
        for pos in positions:
            if pos.exit_premium is not None:
                tr = self.account_trade(pos)
                trades.append(tr)
                total_gross += tr.gross_pnl
                total_charges += tr.charges.total_charges
                total_net += tr.net_pnl
                
        return BacktestAccountingResult(
            trades=trades,
            total_gross_pnl=round(total_gross, 2),
            total_charges=round(total_charges, 2),
            total_net_pnl=round(total_net, 2)
        )
