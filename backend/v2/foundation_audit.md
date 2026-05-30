# Valkyrie V2 Option Backtest Engine - Foundation Audit

This document presents a technical audit of the files created in Phase 13B. The goal is to verify architectural sanity, highlight design inconsistencies, and outline required modifications before executing the Phase 13C historical replay engine.

---

## 1. Strike Resolver Audit

### A. CE/PE ITM/OTM Logic Verification
The resolver uses the following logic to classify option moneyness relative to the At-The-Money (ATM) strike price:
*   **ATM**: `resolved_strike == atm_strike`
*   **CE (Call)**: 
    *   `resolved_strike < atm_strike` $\rightarrow$ **ITM** (In-the-Money)
    *   `resolved_strike > atm_strike` $\rightarrow$ **OTM** (Out-of-the-Money)
*   **PE (Put)**: 
    *   `resolved_strike > atm_strike` $\rightarrow$ **ITM** (In-the-Money)
    *   `resolved_strike < atm_strike` $\rightarrow$ **OTM** (Out-of-the-Money)

**Verification**: This logic aligns perfectly with options theory. Call options represent the right to buy, so a lower strike represents a positive intrinsic value (ITM). Put options represent the right to sell, so a higher strike represents a positive intrinsic value (ITM).

---

### B. The Offset Moneyness Design Flaw
There is a subtle but critical design conflict in how strike offsets (e.g., `ATM+1`, `ATM-1`) are interpreted:

1.  **Arithmetic Direction Offset (Current Implementation)**:
    The offset is treated as a simple mathematical sign applied to the strike step ($S_{\text{ATM}} + (n \times \text{Step})$).
    *   `ATM+1` means adding $1 \times \text{Step}$ to the strike.
    *   `ATM-1` means subtracting $1 \times \text{Step}$ from the strike.

2.  **Moneyness Offset (Standard Option Trading Context)**:
    Traders typically use `ATM+1` to mean "1 strike Out-of-the-Money" and `ATM-1` to mean "1 strike In-the-Money", regardless of whether they are trading Call (CE) or Put (PE) options.

#### Comparison Examples

#### **NIFTY Index** (Spot = 22,015 $\rightarrow$ ATM = 22,000, Step = 50)
*   **Call Option (CE)**:
    *   *Arithmetic ATM+1*: $22000 + 50 = 22050$ (Classification: **OTM**).
    *   *Moneyness ATM+1*: Resolves to 1-step OTM $\rightarrow 22050$ (**Matches**).
    *   *Arithmetic ATM-1*: $22000 - 50 = 21950$ (Classification: **ITM**).
    *   *Moneyness ATM-1*: Resolves to 1-step ITM $\rightarrow 21950$ (**Matches**).
*   **Put Option (PE)**:
    *   *Arithmetic ATM+1*: $22000 + 50 = 22050$ (Classification: **ITM**).
    *   *Moneyness ATM+1*: Resolves to 1-step OTM $\rightarrow 21950$ (**Inconsistent**).
    *   *Arithmetic ATM-1*: $22000 - 50 = 21950$ (Classification: **OTM**).
    *   *Moneyness ATM-1*: Resolves to 1-step ITM $\rightarrow 22050$ (**Inconsistent**).

#### **BANKNIFTY Index** (Spot = 48,120 $\rightarrow$ ATM = 48,100, Step = 100)
*   **Call Option (CE)**:
    *   *Arithmetic ATM+2*: $48100 + 200 = 48300$ (Classification: **OTM**).
    *   *Moneyness ATM+2*: Resolves to 2-steps OTM $\rightarrow 48300$ (**Matches**).
*   **Put Option (PE)**:
    *   *Arithmetic ATM+2*: $48100 + 200 = 48300$ (Classification: **ITM**).
    *   *Moneyness ATM+2*: Resolves to 2-steps OTM $\rightarrow 47900$ (**Inconsistent**).

> [!WARNING]
> **Design Flaw**: If a strategy configures `strike_selection.mode = "ATM+1"` under PE, it will purchase an In-The-Money option instead of an Out-of-the-Money option. We must determine if `ATM+1` should represent a mathematical direction or a moneyness shift.

---

## 2. Expiry Resolver Audit

### A. Weekly vs. Monthly Selection
The resolver routes the selection correctly based on the `ExpiryMode` enum:
*   `CURRENT_WEEKLY`: Returns the first sorted mock date $\ge$ signal date.
*   `NEXT_WEEKLY`: Returns the second sorted mock date.
*   `CURRENT_MONTHLY`: Looks up designated monthly expiries (last Thursday of the month).

### B. Mock Assumptions & Future Blockers
*   **Static List (`MOCK_EXPIRIES`)**: The resolver uses a hardcoded list of dates in May/June 2026. If a backtest is triggered for 2024 or 2025, the resolver will raise a `ValueError`.
*   **Holiday Calendar Blindness**: Resolving actual expiry dates requires checking market holidays. If a weekly expiry falls on a Thursday holiday (e.g., Republic Day), the exchange rolls expiration to Wednesday. The resolver does not account for this.
*   **Index-Agnostic Schedule**: In India, different indices expire on different days (Nifty: Thursday, BankNifty: Wednesday, Finnifty: Tuesday). The resolver assumes a single list of mock dates for all indices.

---

## 3. Contract Resolver Audit

### A. Compatibility with Upstox Expired Instrument Data
*   **Upstox API Limit**: Upstox's active `/v2/instruments` API only contains currently active (unexpired) contracts. For historical backtesting (e.g. testing a strategy over the past 2 years), we cannot query the live API for keys of contracts that expired months ago.
*   **nifty_options.csv Dependency**: The resolver relies on `nifty_options.csv`. While this is compatible with local file-based testing, if the CSV does not contain expired contracts for the backtest window, the resolver will raise an error.

### B. Expiry Date Conversion Performance
*   The resolver parses the entire options CSV and runs `pd.to_datetime(df['expiry'], unit='ms')` on every lookup. Running this conversion inside the inner replay loop will cause severe bottlenecks.

---

## 4. BacktestConfig Schema Future Compatibility

The config schema is ready for basic setups, but requires changes to support institutional options strategies:

| Strategy Selection | Current Status | Required Extension for V2 |
| :--- | :--- | :--- |
| **ATM / ITM / OTM** | Supported only via relative offset names (`ATM+1`). | Support strict moneyness labels: `ITM_1`, `OTM_1`. |
| **DTE-based Expiry** | Fixed to `CURRENT_WEEKLY` / `NEXT_WEEKLY`. | Add `dte_min` and `dte_max` to support trading contracts with specific Days-to-Expiry. |
| **Delta-based Selection** | Unsupported. | Add `target_delta` parameter. Requires Greek calculation libraries or pre-calculated Greek data. |
| **Premium-based Selection** | Unsupported. | Add `target_premium` parameter to search for options trading close to a specific price. |

---

## 5. Engine Routing Audit

*   **V1 Isolation**: The changes to `backend/app.py` wrapper route cleanly:
    ```python
    if getattr(req_data, "engine_version", "v1") == "v2":
        try:
            ...
            return run_backtest_v2(v2_payload)
        except Exception as ex:
            raise HTTPException(status_code=400, detail=...)
    ```
*   **Impact Verification**: If any error occurs during V2 initialization, it is intercepted and raised as a `400 Bad Request` before the V1 background thread code path is reached. This completely isolates the stable V1 engine.

---

## 6. Required Changes before Phase 13C Replay Implementation

To ensure a smooth transition to historical replay in Phase 13C, we must address these architectural points:

1.  **Resolve Strike Offset Interpretation**: Update `HistoricalStrikeResolver` to interpret `ATM+1` and `ATM-1` based on option type moneyness, or explicitly rename the modes to `OTM+1` / `ITM-1` to remove ambiguity.
2.  **Integrate Historical Instruments Master**: Replace the static `MOCK_EXPIRIES` list in `ExpiryResolver` with queries to the database or a processed historical calendar mapping indices to actual expiration dates.
3.  **Optimize Contract Resolver Cache**: Build a lookup dictionary or pre-process the CSV's timestamps during server startup to avoid converting milliseconds inside the replay loop.
