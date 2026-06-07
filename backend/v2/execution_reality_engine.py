import math
from typing import Tuple, Dict, Any
from v2.types import ExecutionModel

def calculate_spread_penalty(
    option_premium: float,
    spot_price: float,
    strike_distance: float,
    option_type: str,
    mode: str
) -> Tuple[float, float]:
    """
    Calculates the bid-ask spread penalty.
    ATM options have the smallest spread.
    OTM and deep OTM options have progressively larger spreads.
    """
    # Normalize mode
    if isinstance(mode, ExecutionModel):
        mode = mode.value
    else:
        mode = str(mode).upper()

    if mode == "THEORETICAL":
        return 0.0, 0.0

    # Base ATM spread pct by mode
    if mode == "REALISTIC":
        base_atm_spread = 0.005   # 0.5%
        scaling_factor = 8.0
    elif mode == "CONSERVATIVE":
        base_atm_spread = 0.010   # 1.0%
        scaling_factor = 12.0
    elif mode == "STRESS_TEST":
        base_atm_spread = 0.025   # 2.5%
        scaling_factor = 20.0
    else:
        base_atm_spread = 0.005
        scaling_factor = 8.0

    # Distance fraction relative to spot price
    dist_ratio = strike_distance / max(spot_price, 1.0)
    
    # Scale spread percentage continuously
    spread_pct = base_atm_spread * (1.0 + scaling_factor * dist_ratio)
    
    # Cap spread percentage to realistic bounds (e.g., max 50% for highly stressed deep OTM)
    spread_pct = min(spread_pct, 0.50)
    
    spread_cost = option_premium * spread_pct
    return spread_pct, spread_cost

def calculate_volatility_penalty(
    atr: float,
    spot_candle_range: float,
    entry_premium: float,
    mode: str
) -> Tuple[float, float]:
    """
    Calculates execution slippage due to market volatility.
    Higher volatility relative to ATR increases execution degradation.
    """
    if isinstance(mode, ExecutionModel):
        mode = mode.value
    else:
        mode = str(mode).upper()

    if mode == "THEORETICAL":
        return 0.0, 0.0

    # Base volatility slippage pct by mode
    if mode == "REALISTIC":
        base_vol_pct = 0.005     # 0.5%
    elif mode == "CONSERVATIVE":
        base_vol_pct = 0.012     # 1.2%
    elif mode == "STRESS_TEST":
        base_vol_pct = 0.030     # 3.0%
    else:
        base_vol_pct = 0.005

    # Ratio of current candle range to ATR
    vol_ratio = spot_candle_range / max(atr, 1.0)
    
    # Scaling volatility multiplier (min 0.5x, max 5.0x base pct)
    vol_mult = 0.5 + 0.5 * min(vol_ratio, 5.0)
    
    volatility_pct = base_vol_pct * vol_mult
    volatility_cost = entry_premium * volatility_pct
    return volatility_pct, volatility_cost

def calculate_effective_fill(
    theoretical_entry: float,
    theoretical_exit: float,
    spread_cost_entry: float,
    volatility_cost_entry: float,
    spread_cost_exit: float,
    volatility_cost_exit: float,
    mode: str
) -> Tuple[float, float]:
    """
    Computes effective fill prices.
    For standard option buyers:
    - Effective entry price increases (buy at higher price due to slippage).
    - Effective exit price decreases (sell at lower price due to slippage).
    """
    if isinstance(mode, ExecutionModel):
        mode = mode.value
    else:
        mode = str(mode).upper()

    if mode == "THEORETICAL":
        return theoretical_entry, theoretical_exit

    effective_entry = theoretical_entry + (spread_cost_entry + volatility_cost_entry)
    effective_exit = max(theoretical_exit - (spread_cost_exit + volatility_cost_exit), 0.0)
    
    return effective_entry, effective_exit
