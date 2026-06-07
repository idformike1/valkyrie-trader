from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class TradeCharges(BaseModel):
    brokerage: float = Field(..., description="Brokerage charges (INR)")
    stt: float = Field(..., description="Securities Transaction Tax (INR)")
    exchange_charges: float = Field(..., description="Exchange transaction charges + IPFT (INR)")
    sebi_charges: float = Field(..., description="SEBI turnover fees (INR)")
    gst: float = Field(..., description="Goods and Services Tax @ 18% (INR)")
    stamp_duty: float = Field(..., description="Stamp duty (INR)")
    other_charges: float = Field(default=0.0, description="Any other additional charges (INR)")
    total_charges: float = Field(..., description="Sum of all individual charges (INR)")

class TradePnL(BaseModel):
    gross_pnl: float = Field(..., description="Gross profit and loss (INR)")
    total_charges: float = Field(..., description="Total transactional charges (INR)")
    net_pnl: float = Field(..., description="Net profit and loss (INR)")

class TradeExplanation(BaseModel):
    strategy_name: str
    entry_reason: str
    exit_reason: str
    signal_snapshot: Dict[str, Any]
    resolver_snapshot: Dict[str, Any]
    risk_snapshot: Dict[str, Any]
    market_snapshot: Dict[str, Any]

class ExecutionAnalysis(BaseModel):
    execution_model: str
    theoretical_entry: float
    effective_entry: float
    theoretical_exit: float
    effective_exit: float
    spread_cost: float
    volatility_cost: float
    pnl_degradation: float

class TradeAccountingResult(BaseModel):
    position_id: str = Field(..., description="Unique position identifier")
    entry_time: datetime = Field(..., description="Position entry timestamp")
    exit_time: datetime = Field(..., description="Position exit timestamp")
    contract: str = Field(..., description="Formatted contract description")
    entry_premium: float = Field(..., description="Premium price at entry")
    exit_premium: float = Field(..., description="Premium price at exit")
    quantity: int = Field(..., description="Contract quantity traded")
    gross_pnl: float = Field(..., description="Gross PnL of the trade")
    charges: TradeCharges = Field(..., description="Detailed breakdown of charges")
    net_pnl: float = Field(..., description="Net PnL of the trade")
    explanation: Optional[TradeExplanation] = None
    execution_analysis: Optional[ExecutionAnalysis] = None

class BacktestAccountingResult(BaseModel):
    trades: List[TradeAccountingResult] = Field(default_factory=list, description="List of all completed trades")
    total_gross_pnl: float = Field(default=0.0, description="Aggregated Gross PnL across all trades")
    total_charges: float = Field(default=0.0, description="Aggregated Charges across all trades")
    total_net_pnl: float = Field(default=0.0, description="Aggregated Net PnL across all trades")
