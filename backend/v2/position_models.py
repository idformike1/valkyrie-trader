from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel

class PositionStatus(str, Enum):
    FLAT = "FLAT"
    LONG = "LONG"
    CLOSED = "CLOSED"

class Position(BaseModel):
    position_id: str
    status: PositionStatus
    underlying: str
    strike: float
    expiry: str
    option_type: str
    instrument_key: str
    entry_time: datetime
    exit_time: Optional[datetime] = None
    entry_premium: float
    exit_premium: Optional[float] = None
    quantity: int
    lot_size: int
    entry_value: float
    exit_value: Optional[float] = None
    broker: str
    entry_signal: str
    exit_signal: Optional[str] = None
    metadata: Dict[str, Any] = {}

class PositionOpened(BaseModel):
    timestamp: datetime
    position_id: str
    underlying: str
    strike: float
    expiry: str
    option_type: str
    instrument_key: str
    entry_premium: float
    quantity: int

class PositionHeld(BaseModel):
    timestamp: datetime
    position_id: str
    underlying: str
    strike: float
    expiry: str
    option_type: str
    instrument_key: str
    current_premium: float

class PositionClosed(BaseModel):
    timestamp: datetime
    position_id: str
    underlying: str
    strike: float
    expiry: str
    option_type: str
    instrument_key: str
    exit_premium: float
    quantity: int

class PositionLedgerModel(BaseModel):
    positions: List[Position] = []
    events: List[Union[PositionOpened, PositionHeld, PositionClosed]] = []
