import logging
from datetime import datetime

logger = logging.getLogger("Valkyrie.ReplayAudit")
logger.setLevel(logging.INFO)

# Setup console handler if not present
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

def log_replay_event(timestamp: datetime, signal: str, contract: str, premium: float, source: str):
    ts_str = timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)
    msg = f"[REPLAY] {ts_str} | {signal} | Contract: {contract} | Premium: {premium:.2f} | Source: {source}"
    logger.info(msg)
