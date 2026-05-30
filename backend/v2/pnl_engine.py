from typing import List
from v2.position_models import Position
from v2.cost_models import CostModel, UpstoxCostModel
from v2.pnl_models import TradeCharges, TradePnL, TradeAccountingResult, BacktestAccountingResult

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
        
        return TradeAccountingResult(
            position_id=position.position_id,
            entry_time=position.entry_time,
            exit_time=position.exit_time,
            contract=contract_desc,
            entry_premium=position.entry_premium,
            exit_premium=position.exit_premium,
            quantity=position.quantity,
            gross_pnl=pnl_result.gross_pnl,
            charges=charges,
            net_pnl=pnl_result.net_pnl
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
