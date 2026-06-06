import logging
import time
import threading
from datetime import datetime
from typing import Set, Dict, List, Optional
from v2.resolvers import HistoricalExpiryResolver, HistoricalContractResolver
from v2.types import ExpiryMode, OptionType
from v2.option_quote_cache import subscribe_option_contract, unsubscribe_option_contracts, OptionQuoteCache
from v2.telemetry_logger import TelemetryLogger

logger = logging.getLogger("Valkyrie.OptionChainManager")

class OptionChainManager:
    STRIKE_STEPS = {
        "NIFTY": 50,
        "BANKNIFTY": 100,
        "FINNIFTY": 50,
        "MIDCPNIFTY": 50,
        "SENSEX": 100,
        "BANKEX": 100,
    }
    
    KEY_TO_INDEX_MAP = {
        "NSE_INDEX|Nifty 50": "NIFTY",
        "NSE_INDEX|Nifty Bank": "BANKNIFTY",
        "NSE_INDEX|Nifty Fin Service": "FINNIFTY",
        "NSE_INDEX|NIFTY MID SELECT": "MIDCPNIFTY",
        "BSE_INDEX|SENSEX": "SENSEX",
        "BSE_INDEX|BANKEX": "BANKEX"
    }

    _instance: Optional['OptionChainManager'] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(OptionChainManager, cls).__new__(cls, *args, **kwargs)
                cls._instance.active_universes = {}
                cls._instance.current_atms = {}
                cls._instance.expiry_mode = ExpiryMode.CURRENT_WEEKLY
            return cls._instance

    def reset(self):
        with self._lock:
            self.active_universes = {}
            self.current_atms = {}
            self.expiry_mode = ExpiryMode.CURRENT_WEEKLY

    def get_active_contracts(self) -> List[str]:
        """
        Returns a list of all currently active/subscribed option contract keys across all indices.
        """
        contracts = set()
        for universe in self.active_universes.values():
            contracts.update(universe)
        return list(contracts)

    def on_spot_update(self, instrument_key: str, spot_price: float):
        index_name = self.KEY_TO_INDEX_MAP.get(instrument_key)
        if not index_name:
            return
        
        step = self.STRIKE_STEPS.get(index_name, 100)
        atm_strike = round(spot_price / step) * step
        
        old_atm = self.current_atms.get(index_name)
        if old_atm is None:
            self.current_atms[index_name] = atm_strike
            TelemetryLogger.log(
                "SIGNAL",
                "INFO",
                f"NEW_ATM_DETECTED: Initial ATM strike detected for {index_name} at {atm_strike}",
                {"index_name": index_name, "spot_price": spot_price, "atm_strike": atm_strike, "event": "NEW_ATM_DETECTED"}
            )
            self._roll_chain(index_name, spot_price, atm_strike, is_initial=True)
        elif abs(atm_strike - old_atm) >= step:
            self.current_atms[index_name] = atm_strike
            TelemetryLogger.log(
                "SIGNAL",
                "INFO",
                f"NEW_ATM_DETECTED: New ATM strike detected for {index_name} at {atm_strike} (moved from {old_atm})",
                {"index_name": index_name, "spot_price": spot_price, "atm_strike": atm_strike, "old_atm": old_atm, "event": "NEW_ATM_DETECTED"}
            )
            self._roll_chain(index_name, spot_price, atm_strike, is_initial=False)

    def _roll_chain(self, index_name: str, spot_price: float, atm_strike: float, is_initial: bool = False):
        try:
            expiry_date = HistoricalExpiryResolver.resolve(index_name, datetime.now(), self.expiry_mode)
        except Exception as e:
            logger.error(f"Failed to resolve expiry for {index_name}: {e}")
            return
        
        step = self.STRIKE_STEPS.get(index_name, 100)
        strikes = [atm_strike + (offset * step) for offset in range(-2, 3)]
        
        new_universe = set()
        for strike in strikes:
            for option_type in ["CE", "PE"]:
                try:
                    contract_key = HistoricalContractResolver.resolve(index_name, strike, expiry_date, option_type)
                    new_universe.add(contract_key)
                except Exception as e:
                    logger.debug(f"Failed to resolve contract for {index_name} strike {strike}: {e}")
                    # Construct fallback key
                    segment = "NSE_FO" if index_name not in ["SENSEX", "BANKEX"] else "BSE_FO"
                    contract_key = f"{segment}|{index_name}_{expiry_date}_{int(strike)}_{option_type}"
                    new_universe.add(contract_key)
        
        old_universe = self.active_universes.get(index_name, set())
        to_unsubscribe = list(old_universe - new_universe)
        to_subscribe = list(new_universe - old_universe)
        
        if to_unsubscribe:
            unsubscribe_option_contracts(to_unsubscribe)
            for k in to_unsubscribe:
                OptionQuoteCache.remove(k)
        
        if to_subscribe:
            for k in to_subscribe:
                subscribe_option_contract(k)
                
        self.active_universes[index_name] = new_universe
        
        event_name = "CHAIN_INITIALIZED" if is_initial else "CHAIN_ROLLED"
        TelemetryLogger.log(
            "SIGNAL",
            "INFO",
            f"{event_name}: Option chain {event_name.lower().replace('_', ' ')} for {index_name}. ATM = {atm_strike}",
            {
                "index_name": index_name,
                "spot_price": spot_price,
                "atm_strike": atm_strike,
                "subscribed_count": len(to_subscribe),
                "unsubscribed_count": len(to_unsubscribe),
                "event": event_name
            }
        )
        logger.info(f"[{event_name}] Chain Rolled for {index_name}. New ATM = {atm_strike}. Subscribed: {len(to_subscribe)}, Unsubscribed: {len(to_unsubscribe)}")
