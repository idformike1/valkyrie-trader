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
        coverage = self.cache_manager.has_range(instrument_key, from_str, to_str, is_option=False)
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
        coverage = self.cache_manager.has_range(instrument_key, from_str, to_str, is_option=True)
        if coverage == "FULL":
            logger.info(f"Cache HIT: Loaded option premium candles for {instrument_key} ({from_str} to {to_str})")
            return self.cache_manager.get_range(instrument_key, from_str, to_str, is_option=True)
            
        try:
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
        except Exception as e:
            logger.warning(f"Failed to download option premium candles for {instrument_key}: {e}. Generating synthetic fallback candles.")
            return self.generate_synthetic_candles(
                index_name=index_name,
                strike_price=strike_price,
                expiry_date=expiry_date,
                option_type=option_type,
                timeframe=timeframe,
                from_date=from_date,
                to_date=to_date,
                instrument_key=instrument_key
            )

    def generate_synthetic_candles(
        self,
        index_name: str,
        strike_price: float,
        expiry_date: str,
        option_type: str,
        timeframe: str,
        from_date: datetime,
        to_date: datetime,
        instrument_key: str
    ) -> List[Dict[str, Any]]:
        import math
        
        spot_loader = UnderlyingHistoricalLoader(self.cache_manager)
        try:
            spot_candles = spot_loader.load_candles(index_name, timeframe, from_date, to_date)
        except Exception as spot_err:
            logger.error(f"Failed to load spot candles for synthetic option generation: {spot_err}")
            return []
            
        if not spot_candles:
            logger.warning(f"No spot candles found for index {index_name} between {from_date} and {to_date} to generate synthetic options.")
            return []
            
        def normal_cdf(x):
            a1 =  0.254829592
            a2 = -0.284496736
            a3 =  1.421413741
            a4 = -1.453152027
            a5 =  1.061405429
            p  =  0.3275911
            sign = 1
            if x < 0:
                sign = -1
            x = abs(x) / math.sqrt(2.0)
            t = 1.0 / (1.0 + p * x)
            y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
            return 0.5 * (1.0 + sign * y)

        def black_scholes_premium(spot: float, strike: float, days_to_expiry: float, opt_type: str, iv: float = 0.15, r: float = 0.07) -> float:
            T = max(days_to_expiry, 0.0001) / 365.0
            d1 = (math.log(spot / strike) + (r + 0.5 * iv ** 2) * T) / (iv * math.sqrt(T))
            d2 = d1 - iv * math.sqrt(T)
            if opt_type.upper() == "CE":
                premium = spot * normal_cdf(d1) - strike * math.exp(-r * T) * normal_cdf(d2)
            else:
                premium = strike * math.exp(-r * T) * normal_cdf(-d2) - spot * normal_cdf(-d1)
            return max(premium, 0.5)

        expiry_dt = datetime.strptime(expiry_date, "%Y-%m-%d")
        
        synthetic_candles = []
        for sc in spot_candles:
            sc_ts = sc["timestamp"]
            sc_dt = datetime.fromisoformat(sc_ts.replace('Z', '+00:00')) if isinstance(sc_ts, str) else sc_ts
            
            days_to_expiry = (expiry_dt.date() - sc_dt.date()).days
            
            minutes_since_open = max(0, (sc_dt.hour - 9) * 60 + (sc_dt.minute - 15))
            day_fraction = min(1.0, minutes_since_open / 375.0)
            remaining_days = max(0.0, float(days_to_expiry) - day_fraction)
            
            o_prem = black_scholes_premium(sc["open"], strike_price, remaining_days, option_type)
            h_prem = black_scholes_premium(sc["high"], strike_price, remaining_days, option_type)
            l_prem = black_scholes_premium(sc["low"], strike_price, remaining_days, option_type)
            c_prem = black_scholes_premium(sc["close"], strike_price, remaining_days, option_type)
            
            h_prem = max(h_prem, o_prem, c_prem)
            l_prem = min(l_prem, o_prem, c_prem)
            
            synthetic_candles.append({
                "timestamp": sc_dt,
                "open": o_prem,
                "high": h_prem,
                "low": l_prem,
                "close": c_prem,
                "volume": sc.get("volume", 0)
            })
            
        logger.info(f"Storing {len(synthetic_candles)} synthetic option premium candles for {instrument_key} in SQLite cache...")
        self.cache_manager.store_range(
            instrument_key=instrument_key,
            candles=synthetic_candles,
            is_option=True,
            strike=strike_price,
            option_type=option_type,
            expiry=expiry_date
        )
        
        return synthetic_candles
