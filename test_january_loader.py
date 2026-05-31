import os
import sys
import logging
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(ROOT_DIR, "backend"))

# Set up logging to print to stdout
logging.basicConfig(level=logging.INFO)

from v2.cache.database import DEFAULT_CACHE_DB_PATH
from v2.cache.manager import HistoricalDataCacheManager
from v2.data_loader import UnderlyingHistoricalLoader

def test():
    db_path = DEFAULT_CACHE_DB_PATH
    print(f"Database path: {db_path}")
    cache_manager = HistoricalDataCacheManager(db_path)
    loader = UnderlyingHistoricalLoader(cache_manager)
    
    start_dt = datetime(2026, 1, 1, 9, 15)
    end_dt = datetime(2026, 1, 31, 15, 30)
    
    print("Loading candles...")
    try:
        candles = loader.load_candles("NIFTY", "1m", start_dt, end_dt)
        print(f"Loaded {len(candles)} candles.")
        if candles:
            print(f"First candle: {candles[0]}")
            print(f"Last candle: {candles[-1]}")
    except Exception as e:
        print(f"Exception during load: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
