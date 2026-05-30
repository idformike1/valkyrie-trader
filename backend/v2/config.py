from typing import Dict, Any, Literal
from pydantic import BaseModel, Field
from v2.types import StrikeMode, ExpiryMode, Timeframe, TargetStopLossType

class StrikeConfig(BaseModel):
    mode: StrikeMode = StrikeMode.ATM

class ExpiryConfig(BaseModel):
    mode: ExpiryMode = ExpiryMode.CURRENT_WEEKLY
    roll_threshold_hours: float = Field(
        default=2.0, 
        description="Roll to next expiry if signal is within N hours of current expiry expiration."
    )

class RiskConfig(BaseModel):
    target_type: TargetStopLossType = TargetStopLossType.NONE
    target_value: float = 0.0
    stop_loss_type: TargetStopLossType = TargetStopLossType.NONE
    stop_loss_value: float = 0.0
    trailing_sl_gap: float = Field(default=0.0, description="Trailing gap in option premium points.")
    max_holding_candles: int = Field(default=10, description="Max candle duration to hold the position.")
    cutoff_time: str = Field(default="15:15", description="Daily intraday square-off cutoff time (HH:MM).")

class ExecutionConfig(BaseModel):
    brokerage_flat: float = Field(default=20.0, description="Flat brokerage fee per executed order (INR).")
    slippage_pct: float = Field(default=0.05, description="Slippage percentage applied to option premiums.")
    lot_size: int = Field(default=1, description="Number of lots to trade.")
    initial_balance: float = Field(default=100000.0, description="Starting test capital.")

class BacktestConfig(BaseModel):
    underlying_instrument_key: str = Field(
        ..., description="Underlying instrument key, e.g., NSE_INDEX|Nifty 50 or Futures key."
    )
    timeframe: Timeframe = Timeframe.MIN_1
    start_date: str = Field(..., description="Start date of the backtest (YYYY-MM-DD).")
    end_date: str = Field(..., description="End date of the backtest (YYYY-MM-DD).")
    
    strategy_name: str = Field(..., description="Registered strategy identifier.")
    strategy_params: Dict[str, Any] = Field(default_factory=dict, description="Strategy hyperparameters.")
    
    option_type_preference: Literal["DYNAMIC", "CE_ONLY", "PE_ONLY"] = Field(
        default="DYNAMIC", 
        description="DYNAMIC selects CE for Bullish signals and PE for Bearish signals."
    )
    
    strike_selection: StrikeConfig = Field(default_factory=StrikeConfig)
    expiry_selection: ExpiryConfig = Field(default_factory=ExpiryConfig)
    risk_management: RiskConfig = Field(default_factory=RiskConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
