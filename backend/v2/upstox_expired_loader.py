import time
import urllib.parse
import logging
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from v2.cache.manager import HistoricalDataCacheManager

# Setup logger
logger = logging.getLogger("Valkyrie.UpstoxExpiredLoader")
logger.setLevel(logging.INFO)

def load_upstox_token(token_path: str = "/Users/rajumaharjan/Documents/Anit Gravity Projects/Valkyrie/token.txt") -> str:
    try:
        with open(token_path, "r") as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"Failed to load Upstox access token: {e}")
        raise ValueError(f"Upstox token file missing at {token_path}")

class UpstoxExpiredOptionDownloader:
    def __init__(self, cache_manager: HistoricalDataCacheManager):
        self.cache_manager = cache_manager

    def _parse_candles(self, json_data: dict) -> List[Dict[str, Any]]:
        candles_raw = json_data.get("data", {}).get("candles", [])
        candles = []
        for c in candles_raw:
            ts = datetime.fromisoformat(c[0].replace('Z', '+00:00'))
            candles.append({
                "timestamp": ts,
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": int(c[5]) if len(c) > 5 else 0
            })
        # Upstox returns candles in reverse chronological order. Reverse to chronological.
        return candles[::-1]

    def download_and_cache(
        self, 
        instrument_key: str, 
        interval: str, 
        from_date: datetime, 
        to_date: datetime,
        strike: float,
        option_type: str,
        expiry: str
    ) -> List[Dict[str, Any]]:
        """
        Downloads option candles from Upstox (active or expired) and stores them in the cache.
        """
        logger.info(f"Downloading candles for option contract {instrument_key} from {from_date} to {to_date}")
        token = load_upstox_token()
        encoded_key = urllib.parse.quote(instrument_key)
        
        # 1. Try standard historical candle API
        url = f"https://api.upstox.com/v2/historical-candle/{encoded_key}/{interval}/{to_date.strftime('%Y-%m-%d')}/{from_date.strftime('%Y-%m-%d')}"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        
        candles = []
        is_expired_error = False
        
        for retry in range(3):
            try:
                logger.info(f"Attempting standard API request for {instrument_key} (Try {retry + 1})")
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    candles = self._parse_candles(resp.json())
                    break
                elif resp.status_code in [400, 404] and ("UDAPI100011" in resp.text or "Invalid Instrument key" in resp.text):
                    logger.info("Standard API returned expired instrument error. Redirecting to Expired Instruments API...")
                    is_expired_error = True
                    break
                else:
                    logger.warning(f"Standard API returned status {resp.status_code}: {resp.text}. Retrying...")
                    time.sleep(1.5 * (retry + 1))
            except Exception as e:
                logger.error(f"Error during standard API call: {e}")
                time.sleep(1.5 * (retry + 1))
        
        # 2. Try Expired Instruments API if standard failed with expired contract code
        if is_expired_error or not candles:
            expired_url = f"https://api.upstox.com/v2/expired-instruments/historical-candle/{encoded_key}/{interval}/{to_date.strftime('%Y-%m-%d')}/{from_date.strftime('%Y-%m-%d')}"
            for retry in range(3):
                try:
                    logger.info(f"Attempting Expired API request for {instrument_key} (Try {retry + 1})")
                    resp = requests.get(expired_url, headers=headers, timeout=15)
                    if resp.status_code == 200:
                        candles = self._parse_candles(resp.json())
                        break
                    else:
                        logger.warning(f"Expired API returned status {resp.status_code}: {resp.text}. Retrying...")
                        time.sleep(1.5 * (retry + 1))
                except Exception as e:
                    logger.error(f"Error during Expired API call: {e}")
                    time.sleep(1.5 * (retry + 1))

        if not candles:
            raise ValueError(f"No option candle data could be retrieved for instrument {instrument_key} from standard or expired APIs.")

        # Store to cache
        logger.info(f"Successfully retrieved {len(candles)} option candles. Storing into SQLite cache...")
        self.cache_manager.store_range(
            instrument_key=instrument_key,
            candles=candles,
            is_option=True,
            strike=strike,
            option_type=option_type,
            expiry=expiry
        )
        return candles
