# Database schema for valkyrie_options_cache.db

CREATE_UNDERLYING_CANDLES = """
CREATE TABLE IF NOT EXISTS underlying_candles (
    instrument_key TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER DEFAULT 0,
    PRIMARY KEY (instrument_key, timestamp)
);
"""

CREATE_OPTION_CANDLES = """
CREATE TABLE IF NOT EXISTS option_candles (
    instrument_key TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER DEFAULT 0,
    strike REAL NOT NULL,
    option_type TEXT NOT NULL,
    expiry TEXT NOT NULL,
    PRIMARY KEY (instrument_key, timestamp)
);
"""

CREATE_CACHE_METADATA = """
CREATE TABLE IF NOT EXISTS cache_metadata (
    instrument_key TEXT PRIMARY KEY,
    cached_from TEXT NOT NULL,
    cached_to TEXT NOT NULL,
    last_updated TEXT NOT NULL
);
"""

CREATE_DOWNLOAD_JOBS = """
CREATE TABLE IF NOT EXISTS download_jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error TEXT
);
"""

# Indexes for timestamp and instrument queries optimization
CREATE_INDEX_UNDERLYING_CANDLES_TS = """
CREATE INDEX IF NOT EXISTS idx_underlying_candles_ts ON underlying_candles (timestamp);
"""

CREATE_INDEX_OPTION_CANDLES_TS = """
CREATE INDEX IF NOT EXISTS idx_option_candles_ts ON option_candles (timestamp);
"""

CREATE_INDEX_OPTION_CANDLES_KEY_TS = """
CREATE INDEX IF NOT EXISTS idx_option_candles_key_ts ON option_candles (instrument_key, timestamp);
"""
