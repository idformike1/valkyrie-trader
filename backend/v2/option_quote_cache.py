import threading
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, Set
from pydantic import BaseModel

logger = logging.getLogger("Valkyrie.OptionQuoteCache")

class OptionQuote(BaseModel):
    instrument_key: str
    bid: float = 0.0
    ask: float = 0.0
    ltp: float = 0.0
    volume: int = 0
    oi: int = 0
    timestamp: datetime
    last_update_ms: int

# Global set of subscribed keys (cross-thread tracking)
_subscribed_keys: Set[str] = set()
_subscribed_keys_lock = threading.Lock()

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
        now_ms = int(time.time() * 1000)
        
        # Calculate latency
        latency_ms = 0
        if timestamp:
            pkt_ms = int(timestamp.timestamp() * 1000)
            latency_ms = max(0, now_ms - pkt_ms)
            
        with cls._lock:
            is_new = instrument_key not in cls._quotes
            cls._quotes[instrument_key] = OptionQuote(
                instrument_key=instrument_key,
                bid=bid or 0.0,
                ask=ask or 0.0,
                ltp=ltp,
                volume=volume or 0,
                oi=oi or 0,
                timestamp=timestamp or datetime.utcnow(),
                last_update_ms=now_ms
            )
            cls._is_live = True

        # Emit validation telemetry events
        from v2.telemetry_logger import TelemetryLogger
        event_type = "QUOTE_RECEIVED" if is_new else "QUOTE_UPDATED"
        TelemetryLogger.log(
            "SIGNAL",
            "INFO",
            f"{event_type}: {instrument_key} LTP={ltp} Bid={bid or 0.0} Ask={ask or 0.0} Latency={latency_ms}ms",
            {
                "instrument": instrument_key,
                "ltp": ltp,
                "bid": bid or 0.0,
                "ask": ask or 0.0,
                "latency_ms": latency_ms
            }
        )

        # Broadcast telemetry immediately on main event loop for real-time UI updates
        try:
            import app
            if hasattr(app, 'main_event_loop') and app.main_event_loop is not None:
                import asyncio
                asyncio.run_coroutine_threadsafe(
                    app.broadcast_telemetry(),
                    app.main_event_loop
                )
        except Exception as e:
            logger.debug(f"Failed to trigger async broadcast from cache update: {e}")

    @classmethod
    def get(cls, instrument_key: str) -> Optional[OptionQuote]:
        with cls._lock:
            return cls._quotes.get(instrument_key)

    @classmethod
    def get_all_quotes(cls) -> Dict[str, OptionQuote]:
        with cls._lock:
            return dict(cls._quotes)

    @classmethod
    def is_feed_available(cls) -> bool:
        with cls._lock:
            return cls._is_live

    @classmethod
    def remove(cls, instrument_key: str):
        with cls._lock:
            if instrument_key in cls._quotes:
                del cls._quotes[instrument_key]

    @classmethod
    def clear(cls):
        with cls._lock:
            cls._quotes.clear()
            cls._is_live = False
        with _subscribed_keys_lock:
            _subscribed_keys.clear()

def get_subscribed_keys() -> Set[str]:
    with _subscribed_keys_lock:
        return set(_subscribed_keys)

def subscribe_option_contract(instrument_key: str):
    """
    Cross-thread binding that registers a key subscription on the active Upstox WebSocket thread.
    """
    with _subscribed_keys_lock:
        if instrument_key in _subscribed_keys:
            return
        _subscribed_keys.add(instrument_key)

    # Emit QUOTE_SUBSCRIBED telemetry
    from v2.telemetry_logger import TelemetryLogger
    TelemetryLogger.log(
        "SIGNAL",
        "INFO",
        f"QUOTE_SUBSCRIBED: Subscribed to options key: {instrument_key}",
        {"instrument": instrument_key}
    )

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

def unsubscribe_option_contracts(instrument_keys: list):
    """
    Cross-thread binding that unsubscribes keys from the active Upstox WebSocket thread.
    """
    if not instrument_keys:
        return
        
    with _subscribed_keys_lock:
        for k in instrument_keys:
            _subscribed_keys.discard(k)

    try:
        import app
        if hasattr(app, 'current_feed') and app.current_feed is not None:
            import asyncio
            loop = getattr(app, 'running_loop', None)
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    app.current_feed.unsubscribe_from_keys(instrument_keys),
                    loop
                )
                logger.info(f"Dynamically unsubscribed Upstox WebSocket from options keys: {instrument_keys}")
    except Exception as e:
        logger.error(f"Failed dynamic contract WebSocket unsubscription: {e}")
