from datetime import datetime
from typing import Optional, List, Union
from pydantic import BaseModel

class ReplaySignalEvent(BaseModel):
    timestamp: datetime
    underlying: str
    signal: str  # BUY, SELL, HOLD
    spot_price: float

class ReplayContractEvent(BaseModel):
    timestamp: datetime
    underlying: str
    strike: float
    expiry: str
    option_type: str
    instrument_key: str
    source: str

class ReplayTradeIntent(BaseModel):
    timestamp: datetime
    underlying: str
    signal: str  # BUY_INTENT, SELL_INTENT
    spot_price: float
    strike: float
    expiry: str
    option_type: str
    instrument_key: str
    premium_price: float
    source: str

class ReplayTimeline(BaseModel):
    underlying: str
    timeframe: str
    strategy: str
    events: List[Union[ReplaySignalEvent, ReplayContractEvent, ReplayTradeIntent]] = []
