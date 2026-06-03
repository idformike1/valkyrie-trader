import threading
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel

logger = logging.getLogger("Valkyrie.OptionQuoteCache")

class OptionQuote(BaseModel):
    instrument_key: str
    ltp: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[int] = None
    oi: Optional[float] = None
    timestamp: datetime

class OptionQuoteCache:
    """
    Thread-safe global registry storing the latest options L1/L2 quotes (LTP, bid, ask, volume, OI)
    received from the Upstox Market Stream WebSocket client.
    """
    _lock = threading.Lock()
    _quotes: Dict[str, OptionQuote] = {}
    _is_live = False

    @classmethod
    def update(
        cls, 
        instrument_key: str, 
        ltp: float, 
        bid: Optional[float] = None, 
        ask: Optional[float] = None, 
        volume: Optional[int] = None, 
        oi: Optional[float] = None,
        timestamp: Optional[datetime] = None
    ):
        with cls._lock:
            cls._quotes[instrument_key] = OptionQuote(
                instrument_key=instrument_key,
                ltp=ltp,
                bid=bid,
                ask=ask,
                volume=volume,
                oi=oi,
                timestamp=timestamp or datetime.utcnow()
            )
            cls._is_live = True

    @classmethod
    def get(cls, instrument_key: str) -> Optional[OptionQuote]:
        with cls._lock:
            return cls._quotes.get(instrument_key)

    @classmethod
    def is_feed_available(cls) -> bool:
        with cls._lock:
            return cls._is_live

    @classmethod
    def clear(cls):
        with cls._lock:
            cls._quotes.clear()
            cls._is_live = False

def subscribe_option_contract(instrument_key: str):
    """
    Cross-thread binding that registers a key subscription on the active Upstox WebSocket thread.
    """
    try:
        import app
        if hasattr(app, 'current_feed') and app.current_feed is not None:
            import asyncio
            loop = getattr(app, 'running_loop', None)
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    app.current_feed.subscribe_to_keys([instrument_key]),
                    loop
                )
                logger.info(f"Dynamically subscribed Upstox WebSocket to options key: {instrument_key}")
    except Exception as e:
        logger.error(f"Failed dynamic contract WebSocket subscription: {e}")
