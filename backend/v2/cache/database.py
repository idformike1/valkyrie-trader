import sqlite3
import os
from v2.cache.schema import (
    CREATE_UNDERLYING_CANDLES,
    CREATE_OPTION_CANDLES,
    CREATE_CACHE_METADATA,
    CREATE_DOWNLOAD_JOBS,
    CREATE_INDEX_UNDERLYING_CANDLES_TS,
    CREATE_INDEX_OPTION_CANDLES_TS,
    CREATE_INDEX_OPTION_CANDLES_KEY_TS
)

DEFAULT_CACHE_DB_PATH = "/Users/rajumaharjan/Documents/Anit Gravity Projects/Valkyrie/backend/v2/cache/valkyrie_options_cache.db"

def get_cache_db_connection(db_path=DEFAULT_CACHE_DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_cache_db(db_path=DEFAULT_CACHE_DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = get_cache_db_connection(db_path)
    cursor = conn.cursor()
    
    # Initialize all tables and indexes
    cursor.execute(CREATE_UNDERLYING_CANDLES)
    cursor.execute(CREATE_OPTION_CANDLES)
    cursor.execute(CREATE_CACHE_METADATA)
    cursor.execute(CREATE_DOWNLOAD_JOBS)
    cursor.execute(CREATE_INDEX_UNDERLYING_CANDLES_TS)
    cursor.execute(CREATE_INDEX_OPTION_CANDLES_TS)
    cursor.execute(CREATE_INDEX_OPTION_CANDLES_KEY_TS)
    
    conn.commit()
    conn.close()
