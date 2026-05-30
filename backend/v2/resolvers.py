import os
import abc
from datetime import datetime
import pandas as pd
from typing import Optional, Dict, Tuple
from v2.types import StrikeMode, ExpiryMode, OptionType

class HistoricalStrikeResolver:
    STRIKE_STEPS = {
        "NIFTY": 50,
        "BANKNIFTY": 100,
        "FINNIFTY": 50,
        "MIDCPNIFTY": 50,
        "SENSEX": 100,
        "BANKEX": 100,
    }

    @classmethod
    def get_step_size(cls, index_name: str) -> int:
        idx_upper = index_name.upper()
        if idx_upper not in cls.STRIKE_STEPS:
            raise ValueError(f"Unsupported index: {index_name}")
        return cls.STRIKE_STEPS[idx_upper]

    @classmethod
    def resolve(
        cls, 
        index_name: str, 
        spot_price: float, 
        strike_mode: StrikeMode, 
        option_type: OptionType
    ) -> dict:
        """
        Resolves the strike price, step size, and option classification based on moneyness.
        
        Moneyness logic:
        - CE (Call): OTM are higher strikes (+), ITM are lower strikes (-)
        - PE (Put): OTM are lower strikes (-), ITM are higher strikes (+)
        
        Returns:
            dict containing:
            - "resolved_strike": float
            - "step_size": int
            - "classification": str ("ATM", "ITM", "OTM")
            - "mode_label": str (the normalized mode name)
        """
        step = cls.get_step_size(index_name)
        atm_strike = round(spot_price / step) * step
        
        mode_val = strike_mode.value if isinstance(strike_mode, StrikeMode) else str(strike_mode)
        
        # Backward compatibility mapping for old ATM+1, ATM-1 formats:
        # ATM+1 means OTM for CE, ITM for PE
        # ATM-1 means ITM for CE, OTM for PE
        legacy_mapping = {
            "ATM+1": "OTM_1" if option_type == OptionType.CE else "ITM_1",
            "ATM-1": "ITM_1" if option_type == OptionType.CE else "OTM_1",
            "ATM+2": "OTM_2" if option_type == OptionType.CE else "ITM_2",
            "ATM-2": "ITM_2" if option_type == OptionType.CE else "OTM_2",
            "ATM+3": "OTM_3" if option_type == OptionType.CE else "ITM_3",
            "ATM-3": "ITM_3" if option_type == OptionType.CE else "OTM_3",
        }
        if mode_val in legacy_mapping:
            mode_val = legacy_mapping[mode_val]
            
        offset = 0
        classification = "ATM"
        
        if mode_val.startswith("OTM_"):
            n = int(mode_val.split("_")[1])
            classification = "OTM"
            # OTM CE is higher strikes (+), OTM PE is lower strikes (-)
            offset = n if option_type == OptionType.CE else -n
        elif mode_val.startswith("ITM_"):
            n = int(mode_val.split("_")[1])
            classification = "ITM"
            # ITM CE is lower strikes (-), ITM PE is higher strikes (+)
            offset = -n if option_type == OptionType.CE else n
            
        resolved_strike = atm_strike + (offset * step)
        
        return {
            "resolved_strike": float(resolved_strike),
            "step_size": step,
            "classification": classification,
            "mode_label": mode_val
        }

class ExpiryCalendarProvider(abc.ABC):
    @abc.abstractmethod
    def get_expiries(self, index_name: str) -> list:
        """
        Returns a sorted list of unique expiry dates in 'YYYY-MM-DD' format.
        """
        pass

class MockExpiryProvider(ExpiryCalendarProvider):
    MOCK_EXPIRIES = [
        "2026-05-28",  # Monthly/Weekly (last Thursday of May 2026)
        "2026-06-04",  # Weekly
        "2026-06-11",  # Weekly
        "2026-06-18",  # Weekly
        "2026-06-25",  # Monthly/Weekly (last Thursday of June 2026)
        "2026-07-02",  # Weekly
    ]

    def get_expiries(self, index_name: str) -> list:
        return self.MOCK_EXPIRIES

class HistoricalExpiryProvider(ExpiryCalendarProvider):
    def get_expiries(self, index_name: str) -> list:
        # Future database implementation
        raise NotImplementedError("HistoricalExpiryProvider will be implemented in Phase 13C.")

class HistoricalExpiryResolver:
    _provider: ExpiryCalendarProvider = MockExpiryProvider()

    @classmethod
    def set_provider(cls, provider: ExpiryCalendarProvider):
        cls._provider = provider

    @classmethod
    def resolve(
        cls, 
        index_name: str,
        signal_timestamp: datetime, 
        expiry_mode: ExpiryMode,
        roll_threshold_hours: float = 2.0
    ) -> str:
        """
        Resolves the expiry date based on signal timestamp, expiry mode, and roll threshold.
        """
        if isinstance(signal_timestamp, str):
            signal_timestamp = datetime.fromisoformat(signal_timestamp.replace('Z', '+00:00'))
            
        signal_date = signal_timestamp.date()
        
        # Load dates from calendar provider
        mock_list = cls._provider.get_expiries(index_name)
        
        expiries = []
        for exp_str in mock_list:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            expiries.append((exp_date, exp_str))
            
        expiries.sort(key=lambda x: x[0])
        
        valid_expiries = []
        for exp_date, exp_str in expiries:
            if exp_date > signal_date:
                valid_expiries.append((exp_date, exp_str))
            elif exp_date == signal_date:
                # Same day expiry! Check threshold
                expiry_time = datetime.combine(exp_date, datetime.strptime("15:30:00", "%H:%M:%S").time())
                time_to_expiry = expiry_time - signal_timestamp.replace(tzinfo=None)
                threshold_seconds = roll_threshold_hours * 3600
                
                if time_to_expiry.total_seconds() > threshold_seconds:
                    valid_expiries.append((exp_date, exp_str))
                
        if not valid_expiries:
            raise ValueError(f"No valid expiries found after signal date {signal_date} in calendar database.")
            
        if expiry_mode == ExpiryMode.CURRENT_WEEKLY:
            return valid_expiries[0][1]
        elif expiry_mode == ExpiryMode.NEXT_WEEKLY:
            if len(valid_expiries) < 2:
                raise ValueError("Next weekly expiry requested but only one expiry remains in calendar database.")
            return valid_expiries[1][1]
        elif expiry_mode == ExpiryMode.CURRENT_MONTHLY:
            monthly_expiries = ["2026-05-28", "2026-06-25"]
            for exp_date, exp_str in valid_expiries:
                if exp_str in monthly_expiries:
                    return exp_str
            return valid_expiries[-1][1]
        else:
            raise ValueError(f"Unsupported expiry mode: {expiry_mode}")

class ContractMasterCache:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ContractMasterCache, cls).__new__(cls, *args, **kwargs)
            cls._instance._cache = {}
            cls._instance._is_loaded = False
        return cls._instance

    def preload(self, csv_path: str = "/Users/rajumaharjan/Documents/Anit Gravity Projects/Valkyrie/nifty_options.csv"):
        if self._is_loaded:
            return
            
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Options database not found at: {csv_path}")
            
        df = pd.read_csv(csv_path)
        # Convert expiry in milliseconds to YYYY-MM-DD
        df['expiry_date'] = pd.to_datetime(df['expiry'], unit='ms').dt.strftime('%Y-%m-%d')
        
        for _, row in df.iterrows():
            key = (
                str(row['name']).upper(),
                float(row['strike_price']),
                str(row['expiry_date']),
                str(row['instrument_type']).upper()
            )
            self._cache[key] = str(row['instrument_key'])
            
        self._is_loaded = True

    def lookup(self, index_name: str, strike_price: float, expiry_date: str, option_type: str) -> str:
        key = (
            index_name.upper(),
            float(strike_price),
            expiry_date,
            option_type.upper()
        )
        
        val = self._cache.get(key)
        if val is None:
            raise ValueError(
                f"No option contract matches parameters in preloaded cache: "
                f"Index={index_name}, Strike={strike_price}, Expiry={expiry_date}, Type={option_type}"
            )
        return val

class HistoricalContractResolver:
    @classmethod
    def resolve(
        cls, 
        index_name: str, 
        strike_price: float, 
        expiry_date: str, 
        option_type: str, 
        csv_path: Optional[str] = None
    ) -> str:
        """
        Resolves the instrument_key using the HistoricalContractProvider.
        """
        from v2.expired_contract_provider import HistoricalContractProvider
        provider = HistoricalContractProvider()
        return provider.resolve_contract(index_name, expiry_date, strike_price, option_type)

