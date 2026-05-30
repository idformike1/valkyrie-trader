from pydantic import BaseModel
from typing import Optional

class UnderlyingCandleModel(BaseModel):
    instrument_key: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int = 0

class OptionCandleModel(BaseModel):
    instrument_key: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    strike: float
    option_type: str
    expiry: str

class CacheMetadataModel(BaseModel):
    instrument_key: str
    cached_from: str
    cached_to: str
    last_updated: str

class DownloadJobModel(BaseModel):
    job_id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
