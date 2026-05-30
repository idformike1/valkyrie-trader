from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field

class StrategyMetadata(BaseModel):
    name: str
    description: str
    author: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class SignalConfig(BaseModel):
    indicators: Dict[str, Any] = Field(default_factory=dict)
    entry_condition: Dict[str, Any]

class StrikeSelection(BaseModel):
    mode: str = "ATM"  # ATM, ATM_PLUS_N, ATM_MINUS_N, DELTA, PREMIUM_RANGE
    delta_target: Optional[float] = None
    premium_min: Optional[float] = None
    premium_max: Optional[float] = None

class ExpirySelection(BaseModel):
    mode: str = "CURRENT_WEEKLY"  # CURRENT_WEEKLY, NEXT_WEEKLY, CURRENT_MONTHLY, DTE_RANGE
    roll_threshold_hours: float = 2.0
    dte_min: Optional[int] = None
    dte_max: Optional[int] = None

class ContractConfig(BaseModel):
    underlying: str
    instrument_type: str = "OPTION"  # OPTION, FUTURE, EQUITY
    option_type: str = "CE_ONLY"  # CE_ONLY, PE_ONLY, CE_PE, DYNAMIC
    strike: StrikeSelection = Field(default_factory=StrikeSelection)
    expiry: ExpirySelection = Field(default_factory=ExpirySelection)

class RiskConfig(BaseModel):
    position_sizing: Dict[str, Any] = Field(default_factory=dict)
    stop_loss: Dict[str, Any] = Field(default_factory=dict)
    take_profit: Dict[str, Any] = Field(default_factory=dict)
    trailing_sl: Dict[str, Any] = Field(default_factory=dict)
    daily_loss_limit: Optional[float] = None

class TimeExitConfig(BaseModel):
    cutoff_time: str = "15:25"

class ExitConfig(BaseModel):
    exit_on_reversal: bool = True
    exit_condition: Optional[Dict[str, Any]] = None
    time_exit: Optional[TimeExitConfig] = None
    expiry_exit: Optional[Dict[str, Any]] = None
    manual_exit: Optional[Dict[str, Any]] = None

class StrategyDefinition(BaseModel):
    strategy_id: str
    name: str
    description: str
    schema_version: str = "2.0.0"
    metadata: Optional[StrategyMetadata] = None
    signal: SignalConfig
    contract: ContractConfig
    risk: RiskConfig
    exit: ExitConfig
