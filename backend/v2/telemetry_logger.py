import threading
from datetime import datetime
from collections import deque
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class RuntimeLog(BaseModel):
    timestamp: str
    category: str
    severity: str
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TelemetryLogger:
    _thread_local = threading.local()
    _global_lock = threading.Lock()
    _global_logs = deque(maxlen=5000)
    _live_mode = False

    @classmethod
    def set_live_mode(cls, enabled: bool):
        with cls._global_lock:
            cls._live_mode = enabled
            if enabled:
                cls._global_logs.clear()

    @classmethod
    def start_session(cls):
        with cls._global_lock:
            is_live = cls._live_mode
        
        if is_live:
            with cls._global_lock:
                cls._global_logs.clear()
        else:
            cls._thread_local.logs = []

    @classmethod
    def log(cls, category: str, severity: str, message: str, metadata: Optional[Dict[str, Any]] = None):
        with cls._global_lock:
            is_live = cls._live_mode
            
        timestamp_str = datetime.utcnow().isoformat() + "Z"
        log_entry = RuntimeLog(
            timestamp=timestamp_str,
            category=category.upper(),
            severity=severity.upper(),
            message=message,
            metadata=metadata or {}
        )
        
        if is_live:
            with cls._global_lock:
                cls._global_logs.append(log_entry)
        else:
            if not hasattr(cls._thread_local, "logs"):
                cls._thread_local.logs = []
            cls._thread_local.logs.append(log_entry)

    @classmethod
    def get_logs(cls) -> List[RuntimeLog]:
        with cls._global_lock:
            is_live = cls._live_mode
            
        if is_live:
            with cls._global_lock:
                return list(cls._global_logs)
        else:
            return getattr(cls._thread_local, "logs", [])

    @classmethod
    def clear_session(cls):
        with cls._global_lock:
            is_live = cls._live_mode
            
        if is_live:
            with cls._global_lock:
                cls._global_logs.clear()
        else:
            if hasattr(cls._thread_local, "logs"):
                cls._thread_local.logs = []

