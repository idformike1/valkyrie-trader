import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from v2.cache.database import get_cache_db_connection, init_cache_db

def parse_to_utc_naive(dt_str: str) -> datetime:
    if dt_str.endswith('Z'):
        dt_str = dt_str[:-1] + '+00:00'
    dt = datetime.fromisoformat(dt_str)
    return dt.replace(tzinfo=None)

def to_naive_iso(ts) -> str:
    if isinstance(ts, str):
        return parse_to_utc_naive(ts).isoformat()
    if isinstance(ts, datetime):
        return ts.replace(tzinfo=None).isoformat()
    return str(ts)

class HistoricalDataCacheManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        if db_path:
            init_cache_db(db_path)
            
    def _get_connection(self):
        if self.db_path:
            return get_cache_db_connection(self.db_path)
        return get_cache_db_connection()

    def verify_coverage(self, requested_from: str, requested_to: str, cached_from: Optional[str], cached_to: Optional[str]) -> str:
        if not cached_from or not cached_to:
            return "MISSING"
        
        req_from = parse_to_utc_naive(requested_from)
        req_to = parse_to_utc_naive(requested_to)
        cache_from = parse_to_utc_naive(cached_from)
        cache_to = parse_to_utc_naive(cached_to)

        if cache_from <= req_from and cache_to >= req_to:
            return "FULL"
        elif cache_to < req_from or cache_from > req_to:
            return "MISSING"
        else:
            return "PARTIAL"

    def has_range(self, instrument_key: str, from_date: str, to_date: str) -> str:
        metadata = self.get_metadata(instrument_key)
        if not metadata:
            return "MISSING"
        return self.verify_coverage(from_date, to_date, metadata["cached_from"], metadata["cached_to"])

    def get_metadata(self, instrument_key: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cache_metadata WHERE instrument_key = ?", (instrument_key,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    def store_range(
        self, 
        instrument_key: str, 
        candles: List[Dict[str, Any]], 
        is_option: bool,
        strike: float = 0.0,
        option_type: str = "",
        expiry: str = ""
    ) -> None:
        if not candles:
            return

        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Sort using naive timestamps to find boundaries
        sorted_candles = sorted(candles, key=lambda x: parse_to_utc_naive(x["timestamp"] if isinstance(x["timestamp"], str) else x["timestamp"].isoformat()))
        min_ts = sorted_candles[0]["timestamp"]
        max_ts = sorted_candles[-1]["timestamp"]

        min_ts_str = to_naive_iso(min_ts)
        max_ts_str = to_naive_iso(max_ts)

        if is_option:
            data_to_insert = []
            for c in candles:
                data_to_insert.append((
                    instrument_key,
                    to_naive_iso(c["timestamp"]),
                    float(c["open"]),
                    float(c["high"]),
                    float(c["low"]),
                    float(c["close"]),
                    int(c.get("volume", 0)),
                    float(strike),
                    str(option_type),
                    str(expiry)
                ))
            cursor.executemany(
                """
                INSERT OR REPLACE INTO option_candles 
                (instrument_key, timestamp, open, high, low, close, volume, strike, option_type, expiry)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                data_to_insert
            )
        else:
            data_to_insert = []
            for c in candles:
                data_to_insert.append((
                    instrument_key,
                    to_naive_iso(c["timestamp"]),
                    float(c["open"]),
                    float(c["high"]),
                    float(c["low"]),
                    float(c["close"]),
                    int(c.get("volume", 0))
                ))
            cursor.executemany(
                """
                INSERT OR REPLACE INTO underlying_candles 
                (instrument_key, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                data_to_insert
            )

        cursor.execute("SELECT * FROM cache_metadata WHERE instrument_key = ?", (instrument_key,))
        meta_row = cursor.fetchone()
        
        now_str = to_naive_iso(datetime.now())
        if meta_row:
            existing_from = meta_row["cached_from"]
            existing_to = meta_row["cached_to"]
            
            ef = parse_to_utc_naive(existing_from)
            et = parse_to_utc_naive(existing_to)
            nf = parse_to_utc_naive(min_ts_str)
            nt = parse_to_utc_naive(max_ts_str)
            
            updated_from = existing_from if ef < nf else min_ts_str
            updated_to = existing_to if et > nt else max_ts_str
            
            cursor.execute(
                """
                UPDATE cache_metadata 
                SET cached_from = ?, cached_to = ?, last_updated = ?
                WHERE instrument_key = ?
                """,
                (updated_from, updated_to, now_str, instrument_key)
            )
        else:
            cursor.execute(
                """
                INSERT INTO cache_metadata (instrument_key, cached_from, cached_to, last_updated)
                VALUES (?, ?, ?, ?)
                """,
                (instrument_key, min_ts_str, max_ts_str, now_str)
            )

        conn.commit()
        conn.close()

    def get_range(self, instrument_key: str, from_date: str, to_date: str, is_option: bool) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        from_str = to_naive_iso(from_date)
        to_str = to_naive_iso(to_date)
        
        table = "option_candles" if is_option else "underlying_candles"
        cursor.execute(
            f"""
            SELECT * FROM {table}
            WHERE instrument_key = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
            """,
            (instrument_key, from_str, to_str)
        )
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for r in rows:
            d = dict(r)
            if "timestamp" in d:
                d["timestamp"] = parse_to_utc_naive(d["timestamp"])
            result.append(d)
        return result

    def invalidate(self, instrument_key: str) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cache_metadata WHERE instrument_key = ?", (instrument_key,))
        cursor.execute("DELETE FROM underlying_candles WHERE instrument_key = ?", (instrument_key,))
        cursor.execute("DELETE FROM option_candles WHERE instrument_key = ?", (instrument_key,))
        conn.commit()
        conn.close()
