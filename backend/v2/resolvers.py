import os
import abc
from datetime import datetime, timedelta
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
        "2026-05-05",  # Weekly (Tuesday)
        "2026-05-12",  # Weekly (Tuesday)
        "2026-05-19",  # Weekly (Tuesday)
        "2026-05-26",  # Weekly (Tuesday)
        "2026-06-02",  # Weekly (Tuesday)
        "2026-06-09",  # Weekly (Tuesday)
        "2026-06-16",  # Weekly (Tuesday)
        "2026-06-23",  # Weekly (Tuesday)
        "2026-06-30",  # Weekly (Tuesday)
        "2026-07-07",  # Weekly (Tuesday)
    ]
    MOCK_EXPIRIES_BSE = [
        "2026-05-07",  # Weekly (Thursday)
        "2026-05-14",  # Weekly (Thursday)
        "2026-05-21",  # Weekly (Thursday)
        "2026-05-28",  # Weekly (Thursday)
        "2026-06-04",  # Weekly (Thursday)
        "2026-06-11",  # Weekly (Thursday)
        "2026-06-18",  # Weekly (Thursday)
        "2026-06-25",  # Weekly (Thursday)
        "2026-07-02",  # Weekly (Thursday)
    ]

    def get_expiries(self, index_name: str) -> list:
        if index_name.upper() in ["SENSEX", "BANKEX"]:
            return self.MOCK_EXPIRIES_BSE
        return self.MOCK_EXPIRIES

class LiveExpiryProvider(ExpiryCalendarProvider):
    """Discovers real expiry dates by probing the Upstox live option chain API and caching in SQLite."""
    
    _cache: Dict[str, list] = {}  # In-memory cache per session to avoid repeated API calls
    
    UNDERLYING_KEYS = {
        "NIFTY": "NSE_INDEX|Nifty 50",
        "BANKNIFTY": "NSE_INDEX|Nifty Bank",
        "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
        "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
        "SENSEX": "BSE_INDEX|SENSEX",
        "BANKEX": "BSE_INDEX|BANKEX",
    }
    
    def get_expiries(self, index_name: str) -> list:
        import logging
        _log = logging.getLogger('Valkyrie.LiveExpiryProvider')
        
        idx = index_name.upper()
        
        # Return in-memory cache if available
        if idx in self._cache and self._cache[idx]:
            return self._cache[idx]
        
        # Try HistoricalContractProvider first (reads SQLite + Upstox expired API)
        try:
            from v2.expired_contract_provider import HistoricalContractProvider
            provider = HistoricalContractProvider()
            expiries = provider.get_expiries(idx)
            
            # Verify the nearest future expiry actually has live contracts on Upstox
            today_str = datetime.now().strftime("%Y-%m-%d")
            future_expiries = [e for e in expiries if e >= today_str]
            
            if future_expiries:
                # Quick probe: check if nearest future expiry returns data from live option chain
                from v2.upstox_expired_loader import load_upstox_token
                import requests as _req
                token = load_upstox_token()
                underlying_key = self.UNDERLYING_KEYS.get(idx, "NSE_INDEX|Nifty 50")
                
                if token:
                    test_expiry = future_expiries[0]
                    try:
                        resp = _req.get(
                            "https://api.upstox.com/v2/option/chain",
                            headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
                            params={"instrument_key": underlying_key, "expiry_date": test_expiry},
                            timeout=5
                        )
                        if resp.status_code == 200 and resp.json().get("data"):
                            # Cached expiry is valid — use it
                            self._cache[idx] = expiries
                            return expiries
                    except Exception:
                        pass
                    
                    # Cached nearest expiry is invalid — probe for real dates
                    _log.info(f"Cached expiry {test_expiry} invalid for {idx}. Probing live option chain...")
                    real_expiries = self._probe_live_expiries(token, underlying_key, idx)
                    if real_expiries:
                        # Merge discovered future expiries with historical past expiries
                        past = [e for e in expiries if e < today_str]
                        merged = sorted(set(past + real_expiries))
                        self._cache[idx] = merged
                        # Cache in SQLite for subsequent calls
                        try:
                            provider._save_expiries_to_cache(idx, real_expiries, "UPSTOX_LIVE_OPTION_CHAIN")
                        except Exception:
                            pass
                        return merged
            
            if expiries:
                self._cache[idx] = expiries
                return expiries
                
        except Exception as e:
            _log.warning(f"Live expiry lookup failed for {idx}: {e}")
        
        # Ultimate fallback (cache it to avoid hitting network again)
        fallback = MockExpiryProvider().get_expiries(idx)
        self._cache[idx] = fallback
        return fallback
    
    def _probe_live_expiries(self, token: str, underlying_key: str, index_name: str) -> list:
        """Probe the next 30 days to discover valid expiry dates from the live option chain API."""
        import requests as _req
        import logging
        _log = logging.getLogger('Valkyrie.LiveExpiryProvider')
        
        discovered = []
        today = datetime.now().date()
        
        for day_offset in range(30):
            probe_date = today + timedelta(days=day_offset)
            probe_str = probe_date.strftime("%Y-%m-%d")
            try:
                resp = _req.get(
                    "https://api.upstox.com/v2/option/chain",
                    headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
                    params={"instrument_key": underlying_key, "expiry_date": probe_str},
                    timeout=3
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    if data and len(data) > 0:
                        discovered.append(probe_str)
                        _log.info(f"Discovered live expiry for {index_name}: {probe_str} ({len(data)} strikes)")
            except Exception:
                continue
        
        return sorted(discovered)

class HistoricalExpiryProvider(ExpiryCalendarProvider):
    def get_expiries(self, index_name: str) -> list:
        # Future database implementation
        raise NotImplementedError("HistoricalExpiryProvider will be implemented in Phase 13C.")

class HistoricalExpiryResolver:
    _provider: ExpiryCalendarProvider = LiveExpiryProvider()

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
            from collections import defaultdict
            monthly_map = defaultdict(list)
            for exp_date, exp_str in expiries:
                monthly_map[(exp_date.year, exp_date.month)].append((exp_date, exp_str))
            
            monthly_expiries = {max(lst, key=lambda x: x[0])[1] for lst in monthly_map.values()}
            
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

