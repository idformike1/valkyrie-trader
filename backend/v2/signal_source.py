import abc
import pandas as pd
from typing import Tuple, Dict, Any
from v2.types import SignalType

class SignalSource(abc.ABC):
    @abc.abstractmethod
    def __init__(self, **kwargs):
        """Initialize strategy-specific parameters."""
        pass

    @abc.abstractmethod
    def evaluate(self, underlying_df: pd.DataFrame) -> Tuple[SignalType, Dict[str, Any]]:
        """
        Evaluate the resampled underlying candles (Spot or Futures).
        
        Args:
            underlying_df: Historical dataframe of Spot/Futures index with columns:
                           ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                           
        Returns:
            Tuple containing:
            1. signal_type: SignalType (e.g. SignalType.BUY, SignalType.EXIT)
            2. metadata: Dictionary with signal attributes (e.g. direction, stop_loss, etc.)
        """
        pass
    
    @abc.abstractmethod
    def reset_state(self) -> None:
        """Reset internal indicators and state variables between runs."""
        pass
