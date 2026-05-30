import time
import urllib.parse
import logging
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from v2.cache.manager import HistoricalDataCacheManager
from v2.upstox_expired_loader import load_upstox_token, UpstoxExpiredOptionDownloader
from v2.resolvers import HistoricalContractResolver

logger = logging.getLogger("Valkyrie.DataLoader")
logger.setLevel(logging.INFO)

class UnderlyingHistoricalLoader:
    def __init__(self, cache_manager: HistoricalDataCacheManager):
        self.cache_manager = cache_manager
        self.underlying_keys_map = {
            "NIFTY": "NSE_INDEX|Nifty 50",
            "BANKNIFTY": "NSE_INDEX|Nifty Bank",
            "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
            "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
            "SENSEX": "BSE_INDEX|SENSEX",
            "BANKEX": "BSE_INDEX|BANKEX"
        }
        self.interval_map = {
            "1m": "1minute",
            "3m": "3minute",
            "5m": "5minute",
            "15m": "15minute",
            "30m": "30minute",
            "10s": "1minute",
            "30s": "1minute"
        }

    def get_instrument_key(self, index_name: str) -> str:
        idx_upper = index_name.upper()
        if idx_upper not in self.underlying_keys_map:
            raise ValueError(f"Unsupported index: {index_name}")
        return self.underlying_keys_map[idx_upper]

    def _download_spot_candles(self, instrument_key: str, upstox_interval: str, from_date: datetime, to_date: datetime) -> List[Dict[str, Any]]:
        token = load_upstox_token()
        encoded_key = urllib.parse.quote(instrument_key)
        url = f"https://api.upstox.com/v2/historical-candle/{encoded_key}/{upstox_interval}/{to_date.strftime('%Y-%m-%d')}/{from_date.strftime('%Y-%m-%d')}"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        
        for retry in range(3):
            try:
                logger.info(f"Downloading spot candles for {instrument_key} (Try {retry + 1})")
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    raw_data = resp.json().get("data", {}).get("candles", [])
                    candles = []
                    for c in raw_data:
                        ts = datetime.fromisoformat(c[0].replace('Z', '+00:00'))
                        candles.append({
                            "timestamp": ts,
                            "open": float(c[1]),
                            "high": float(c[2]),
                            "low": float(c[3]),
                            "close": float(c[4]),
                            "volume": int(c[5]) if len(c) > 5 else 0
                        })
                    return candles[::-1]
                else:
                    logger.warning(f"Spot downloader API error status {resp.status_code}: {resp.text}")
                    time.sleep(1.5 * (retry + 1))
            except Exception as e:
                logger.error(f"Error during spot downloading API call: {e}")
                time.sleep(1.5 * (retry + 1))
        raise ValueError(f"Failed to download spot candles for index {instrument_key}")

    def load_candles(self, index_name: str, timeframe: str, from_date: datetime, to_date: datetime) -> List[Dict[str, Any]]:
        instrument_key = self.get_instrument_key(index_name)
        upstox_interval = self.interval_map.get(timeframe, "1minute")
        
        from_str = from_date.isoformat()
        to_str = to_date.isoformat()
        
        # Cache-First flow
        coverage = self.cache_manager.has_range(instrument_key, from_str, to_str)
        if coverage == "FULL":
            logger.info(f"Cache HIT: Loaded underlying spot candles for {index_name} ({from_str} to {to_str})")
            return self.cache_manager.get_range(instrument_key, from_str, to_str, is_option=False)
            
        logger.info(f"Cache {coverage}: Downloading underlying spot candles for {index_name}...")
        downloaded = self._download_spot_candles(instrument_key, upstox_interval, from_date, to_date)
        
        if downloaded:
            self.cache_manager.store_range(
                instrument_key=instrument_key,
                candles=downloaded,
                is_option=False
            )
        
        # Return requested sub-slice from the cache to ensure alignment
        return self.cache_manager.get_range(instrument_key, from_str, to_str, is_option=False)

class OptionHistoricalLoader:
    def __init__(self, cache_manager: HistoricalDataCacheManager):
        self.cache_manager = cache_manager
        self.downloader = UpstoxExpiredOptionDownloader(cache_manager)
        self.interval_map = {
            "1m": "1minute",
            "3m": "3minute",
            "5m": "5minute",
            "15m": "15minute",
            "30m": "30minute",
            "10s": "1minute",
            "30s": "1minute"
        }

    def load_candles(
        self, 
        index_name: str, 
        strike_price: float, 
        expiry_date: str, 
        option_type: str, 
        timeframe: str,
        from_date: datetime, 
        to_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Cache-first historical loader for option premium candles.
        Resolves option contract key using nifty_options.csv and queries cache or downloads.
        """
        # Resolve instrument key using the optimized Contract Resolver
        instrument_key = HistoricalContractResolver.resolve(
            index_name=index_name,
            strike_price=strike_price,
            expiry_date=expiry_date,
            option_type=option_type
        )
        
        upstox_interval = self.interval_map.get(timeframe, "1minute")
        from_str = from_date.isoformat()
        to_str = to_date.isoformat()

        # Cache-First flow
        coverage = self.cache_manager.has_range(instrument_key, from_str, to_str)
        if coverage == "FULL":
            logger.info(f"Cache HIT: Loaded option premium candles for {instrument_key} ({from_str} to {to_str})")
            return self.cache_manager.get_range(instrument_key, from_str, to_str, is_option=True)
            
        logger.info(f"Cache {coverage}: Downloading option premium candles for {instrument_key}...")
        self.downloader.download_and_cache(
            instrument_key=instrument_key,
            interval=upstox_interval,
            from_date=from_date,
            to_date=to_date,
            strike=strike_price,
            option_type=option_type,
            expiry=expiry_date
        )
        
        return self.cache_manager.get_range(instrument_key, from_str, to_str, is_option=True)
