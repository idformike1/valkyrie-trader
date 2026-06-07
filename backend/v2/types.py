from enum import Enum

class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    EXIT = "EXIT"
    HOLD = "HOLD"

class Direction(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"

class ExpiryMode(str, Enum):
    CURRENT_WEEKLY = "CURRENT_WEEKLY"
    NEXT_WEEKLY = "NEXT_WEEKLY"
    CURRENT_MONTHLY = "CURRENT_MONTHLY"

class StrikeMode(str, Enum):
    ATM = "ATM"
    OTM_1 = "OTM_1"
    OTM_2 = "OTM_2"
    OTM_3 = "OTM_3"
    ITM_1 = "ITM_1"
    ITM_2 = "ITM_2"
    ITM_3 = "ITM_3"
    # Legacy backward compatibility mappings
    ATM_PLUS_1 = "ATM+1"
    ATM_PLUS_2 = "ATM+2"
    ATM_PLUS_3 = "ATM+3"
    ATM_MINUS_1 = "ATM-1"
    ATM_MINUS_2 = "ATM-2"
    ATM_MINUS_3 = "ATM-3"

class Timeframe(str, Enum):
    SEC_10 = "10s"
    SEC_30 = "30s"
    MIN_1 = "1m"
    MIN_3 = "3m"
    MIN_5 = "5m"
    MIN_15 = "15m"
    MIN_30 = "30m"
    HOUR_1 = "1h"

class OptionType(str, Enum):
    CE = "CE"
    PE = "PE"

class TargetStopLossType(str, Enum):
    POINTS = "points"
    PERCENT = "percent"
    UNDERLYING_POINTS = "underlying_points"
    NONE = "none"

class ExecutionModel(str, Enum):
    THEORETICAL = "THEORETICAL"
    REALISTIC = "REALISTIC"
    CONSERVATIVE = "CONSERVATIVE"
    STRESS_TEST = "STRESS_TEST"
