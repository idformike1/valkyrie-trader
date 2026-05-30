# Valkyrie V2 Option Backtest Engine
## Historical Data Layer Review

This document reviews the design, implementation, and verified benchmarks of the **V2 Historical Data Layer**. It serves as the official sign-off for Phase 13C.1 before historical replay logic is introduced in Phase 13C.2.

---

## 1. Database Schema Specifications

The SQLite database (`valkyrie_options_cache.db`) stores market candle history for indices (Underlying) and derivative contracts (Options).

### Table Structures

```
  +-------------------------------------------------+
  |                underlying_candles               |
  +-------------------------------------------------+
  | PK  (instrument_key, timestamp)                 |
  |     open: REAL, high: REAL, low: REAL,          |
  |     close: REAL, volume: INTEGER                |
  +-------------------------------------------------+
                         ^
                         |
  +-------------------------------------------------+
  |                  option_candles                 |
  +-------------------------------------------------+
  | PK  (instrument_key, timestamp)                 |
  |     open: REAL, high: REAL, low: REAL,          |
  |     close: REAL, volume: INTEGER, strike: REAL, |
  |     option_type: TEXT, expiry: TEXT             |
  +-------------------------------------------------+
                         ^
                         |
  +-------------------------------------------------+
  |                  cache_metadata                 |
  +-------------------------------------------------+
  | PK  instrument_key                              |
  |     cached_from: TEXT, cached_to: TEXT,          |
  |     last_updated: TEXT                          |
  +-------------------------------------------------+
```

*   **composite primary keys**: `(instrument_key, timestamp)` ensures zero duplicate bars at identical time checkpoints.
*   **Indices**:
    *   `idx_underlying_candles_ts` on `underlying_candles(timestamp)`
    *   `idx_option_candles_ts` on `option_candles(timestamp)`
    *   `idx_option_candles_key_ts` on `option_candles(instrument_key, timestamp)`
    This accelerates SQL range scans (`timestamp >= ? AND timestamp <= ?`) from $O(N)$ scanning down to $O(\log N)$ binary tree search.

---

## 2. End-to-End Cache Flow

The loaders (`UnderlyingHistoricalLoader` and `OptionHistoricalLoader`) utilize a strict **Cache-First** strategy:

```
                  [ Get Candles Request ]
                             |
                             v
                  [ Check cache_metadata ]
                             |
                  +----------+----------+
                  |                     |
           (No Metadata)           (Has Metadata)
                  |                     |
                  |            [ verify_coverage() ]
                  |            /         |         \
                  |       (MISSING)  (PARTIAL)   (FULL)
                  |          /           |           \
                  +--->[ Download ]      |       [ Cache HIT ]
                             |           |             |
                     [ Normalize ]       |     [ Read SQL cache ]
                             |           |             |
                       [ Save SQL ]      |             v
                             |           |      [ Return Candles ]
                             v           v
                    [ Merge & Expand Ranges ]
```

### Date & Timezone Alignment
To prevent errors with naive vs offset-aware datetimes in comparisons (e.g. `2026-05-25T11:00:00+00:00` vs `2026-05-25T11:00:00`), all timestamps are standardized to **naive UTC ISO strings** on insertion and comparison, ensuring perfect alphabetical SQL string matching.

---

## 3. Data Lifecycle & Maintenance

*   **Cache Hit**: Served immediately in RAM/Disk read without API calls.
*   **Cache Miss**: Triggers live Upstox request (Standard API first, falls back to Expired Instruments API on expired token error code).
*   **Range Expansion**: Storing candles with a new date range dynamically merges bounds:
    $$\text{new\_from} = \min(\text{existing\_from}, \text{download\_from})$$
    $$\text{new\_to} = \max(\text{existing\_to}, \text{download\_to})$$
*   **Invalidation**: The `invalidate(instrument_key)` function deletes all associated candles and metadata, forcing a clean reload on the next run.

---

## 4. Performance Benchmarks

Actual execution latency measured on target workspace environment (23 tests passed):

| Metric | Target Specification | Actual Performance | Status |
| :--- | :--- | :--- | :--- |
| **Contract Lookup** | $< 5.0\text{ ms}$ | **$0.0003\text{ ms}$** | ✅ Exceeded (10,000x faster) |
| **Cache Query (50 bars)**| $< 50.0\text{ ms}$ | **$0.3226\text{ ms}$** | ✅ Exceeded (150x faster) |
| **1-Year (20k bars) Scan**| $< 500.0\text{ ms}$ | **$46.1833\text{ ms}$** | ✅ Exceeded (10x faster) |

*Analysis*: Preloading contract maps in memory (`ContractMasterCache`) and indexing composite keys on SQLite database yields near instantaneous reads, providing the necessary speeds to loop through historical data repeatedly.

---

## 5. Future Replay Integration Points

In Phase 13C.2, the Replay Engine will hook directly into the data loaders:
1.  **Chronological Feeder**: Plays back `UnderlyingHistoricalLoader` candles bar-by-bar.
2.  **Strike/Expiry Signals**: Evaluates EMA crossings, resolves contracts, and calls `OptionHistoricalLoader.load_candles()` on the fly.
3.  **Dynamic Preloads**: Replay engine can trigger a background batch preload of the resolved option contract to ensure $0\text{ ms}$ overhead during trade lifecycle monitoring.
