# Valkyrie V2 Option Backtest Engine - Foundation Layer

This directory contains the core foundation for the **V2 decoupled options backtest engine**. 
By separating the logic of technical signal analysis (run on underlying Spot Index/Futures charts) from transaction execution (run on specific option contract premiums), the V2 engine delivers institutional-grade backtesting fidelity and eliminates indicators distortion caused by option premium decay or strike liquidity gaps.

---

## Architecture Blueprint

```
                     +---------------------------------------+
                     |        Spot / Futures Candles         |
                     +---------------------------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |             SignalSource              |
                     |  - evaluate(underlying_df)            |
                     +---------------------------------------+
                                         |
                       [ BUY / SELL Signal + Direction ]
                                         v
       +---------------------------------+---------------------------------+
       |                                 |                                 |
       v                                 v                                 v
+--------------+                 +---------------+                 +---------------+
|    Strike    |                 |    Expiry     |                 |    Option     |
|   Resolver   |                 |   Resolver    |                 |     Type      |
+--------------+                 +---------------+                 +---------------+
       |                                 |                                 |
 [Strike Price]                    [Expiry Date]                        [CE/PE]
       |                                 |                                 |
       +---------------------------------+---------------------------------+
                                         |
                                         v
                         +-------------------------------+
                         |       Contract Resolver       |
                         |  (ContractMasterCache Lookup) |
                         +-------------------------------+
                                         |
                                  [Instrument Key]
                                         v
                         +-------------------------------+
                         |      Position Manager         |
                         |  - Monitored & Executed       |
                         +-------------------------------+
```

---

## Component Specifications

### 1. Configuration & Validation Schema (`config.py`)
Standardized configurations are defined using Pydantic (v2). It introduces strict validation schemas mapping:
*   `StrikeConfig`: Strike selection modes based on dynamic option moneyness (`ATM`, `OTM_1`, `OTM_2`, `OTM_3`, `ITM_1`, `ITM_2`, `ITM_3`).
*   `ExpiryConfig`: Expiry modes (`CURRENT_WEEKLY`, `NEXT_WEEKLY`, `CURRENT_MONTHLY`) and expiry roll thresholds.
*   `RiskConfig`: Trailing SL/TP checks mapped to both underlying asset movements and option premium decay.
*   `ExecutionConfig`: Slippage and transaction-cost environment parameters.

---

### 2. Strike Resolver Moneyness Design (`resolvers.py`)
To prevent the ambiguity of simple mathematical offsets (where `ATM+1` for PE would select an ITM option), the `HistoricalStrikeResolver` implements dynamic **Option Moneyness**:

*   **Call Options (CE)**:
    *   `ATM`: Resolves to the nearest rounded strike price.
    *   `OTM_n`: Resolves to higher strike prices ($S_{\text{ATM}} + n \times \text{Step}$).
    *   `ITM_n`: Resolves to lower strike prices ($S_{\text{ATM}} - n \times \text{Step}$).
*   **Put Options (PE)**:
    *   `ATM`: Resolves to the nearest rounded strike price.
    *   `OTM_n`: Resolves to lower strike prices ($S_{\text{ATM}} - n \times \text{Step}$).
    *   `ITM_n`: Resolves to higher strike prices ($S_{\text{ATM}} + n \times \text{Step}$).

#### Offsets Examples Matrix
| Index | Spot | ATM Strike | Mode | CE Resolved | PE Resolved |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **NIFTY** (Step 50) | 22,015 | 22,000 | `OTM_1` | 22,050 (OTM) | 21,950 (OTM) |
| **NIFTY** (Step 50) | 22,015 | 22,000 | `ITM_1` | 21,950 (ITM) | 22,050 (ITM) |
| **BANKNIFTY** (Step 100) | 48,120 | 48,100 | `OTM_2` | 48,300 (OTM) | 47,900 (OTM) |

---

### 3. Expiry Calendar Provider Architecture (`resolvers.py`)
The dependency on hardcoded expiry databases is decoupled using the `ExpiryCalendarProvider` interface:
*   `ExpiryCalendarProvider` (Abstract ABC): Defines `get_expiries(index_name: str)`.
*   `MockExpiryProvider`: Inherits the interface and returns the default mock dates list for local testing.
*   `HistoricalExpiryProvider` (Placeholder): Prepares for the database-driven schedule lookup in Phase 13C.
*   You can dynamically inject custom calendars in tests/production using `HistoricalExpiryResolver.set_provider(CustomProvider())`.

---

### 4. Contract Preload Cache (`resolvers.py`)
To prevent expensive file lookups ($O(N)$ operations parsing CSV files inside the core backtest replay loop), we pre-load option metadata:
*   `ContractMasterCache`: Singleton memory-cache loaded once on server startup.
*   Converts Unix epoch millisecond timestamps into standard `YYYY-MM-DD` strings inside RAM.
*   Enables $O(1)$ contract key resolution (`instrument_key` queries) using a simple dictionary compound-key: `(index_name, strike_price, expiry_date, option_type)`.

---

## Migration and Compatibility Notes

1.  **V1 Backward Compatibility**: Legacy start engine calls (without `engine_version` or set to `"v1"`) fall through immediately to the legacy backtest engine.
2.  **Legacy V2 Config Compatibility**: If an existing client triggers a V2 run using old configuration keys (`ATM+1`, `ATM-1`), the `HistoricalStrikeResolver` automatically intercept-maps the legacy labels to their corresponding `OTM_n` / `ITM_n` moneyness counterparts dynamically:
    *   `ATM+1` for CE $\rightarrow$ `OTM_1`
    *   `ATM-1` for CE $\rightarrow$ `ITM_1`
    *   `ATM+1` for PE $\rightarrow$ `ITM_1`
    *   `ATM-1` for PE $\rightarrow$ `OTM_1`
3.  **FASTAPI Payload Updates**: The whitelisted array in `/start` has been expanded to support the new `OTM_n` and `ITM_n` modes safely.
