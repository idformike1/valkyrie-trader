# PnL & Charges Engine Verification Report

This report documents the design, implementation, and successful validation of the **Valkyrie V2 PnL & Charges Engine** (Phase 13C.4). The engine calculates gross profit/loss, applies detailed statutory and broker-specific transaction costs, and produces net trade-accounting summaries.

---

## 1. Cost Model & Rate Documentation

Valkyrie V2 uses an extensible `CostModel` interface. The **`UpstoxCostModel`** implements the official NSE F&O Equity Option fee structure (verified on **2026-05-30**):

| Charge Type | Rate / Value | Application | Base / Turnover |
| :--- | :--- | :--- | :--- |
| **Brokerage** | Flat ₹20.00 | Per executed order (Buy/Sell) | Flat per order |
| **STT** (Securities Transaction Tax) | **0.1%** (`0.001`) | Sell side only | Premium value |
| **Exchange charges** (NSE + IPFT) | **0.03553%** (`0.0003553`) | Both sides (Buy and Sell) | Premium value |
| **SEBI Turnover Fee** | **₹10 / crore** (`1e-7`) | Both sides (Buy and Sell) | Premium value |
| **GST** | **18%** (`0.18`) | Both sides | Brokerage + Exchange charges + SEBI |
| **Stamp Duty** | **0.003%** (`0.00003`) | Buy side only | Premium value |

---

## 2. Validation Examples

### Trade #1 (Break-Even Gross, Negligible Net)
* **Parameters**: Buy px: `133.60`, Sell px: `134.60`, Qty: `75`
* **Gross PnL**: $(134.60 - 133.60) \times 75 = \mathbf{₹75.00}$
* **Charges Breakdown**:
  * Brokerage: ₹40.00 (₹20 entry + ₹20 exit)
  * STT (Sell side only): $134.60 \times 75 \times 0.001 = \mathbf{₹10.10}$ (rounded)
  * Exchange Charges (Both sides): $(133.60 + 134.60) \times 75 \times 0.0003553 = \mathbf{₹7.15}$ (rounded)
  * SEBI turnover fee: $(133.60 + 134.60) \times 75 \times 1e-7 = \mathbf{₹0.00}$ (rounded)
  * GST (18% of Brokerage + Exchange + SEBI): $(40.00 + 7.15) \times 0.18 = \mathbf{₹8.49}$ (rounded)
  * Stamp Duty (Buy side only): $133.60 \times 75 \times 0.00003 = \mathbf{₹0.30}$ (rounded)
  * **Total Charges**: $40.00 + 10.10 + 7.15 + 0.00 + 8.49 + 0.30 = \mathbf{₹66.04}$
* **Net PnL**: $75.00 - 66.04 = \mathbf{₹8.96}$

---

### Trade #7 (Large Positive Trade)
* **Parameters**: Buy px: `112.90`, Sell px: `133.40`, Qty: `75`
* **Gross PnL**: $(133.40 - 112.90) \times 75 = \mathbf{₹1537.50}$
* **Charges Breakdown**:
  * Brokerage: ₹40.00
  * STT (Sell side): $133.40 \times 75 \times 0.001 = \mathbf{₹10.01}$ (rounded)
  * Exchange Charges: $(112.90 + 133.40) \times 75 \times 0.0003553 = \mathbf{₹6.56}$ (rounded)
  * SEBI turnover fee: $\mathbf{₹0.00}$
  * GST: $(40.00 + 6.56) \times 0.18 = \mathbf{₹8.38}$ (rounded)
  * Stamp Duty (Buy side): $112.90 \times 75 \times 0.00003 = \mathbf{₹0.25}$ (rounded)
  * **Total Charges**: $40.00 + 10.01 + 6.56 + 0.00 + 8.38 + 0.25 = \mathbf{₹65.20}$
* **Net PnL**: $1537.50 - 65.20 = \mathbf{₹1472.30}$

---

### Trade #11 (Maximum Profit Trade of Day)
* **Parameters**: Buy px: `84.10`, Sell px: `110.40`, Qty: `75`
* **Gross PnL**: $(110.40 - 84.10) \times 75 = \mathbf{₹1972.50}$
* **Charges Breakdown**:
  * Brokerage: ₹40.00
  * STT (Sell side): $110.40 \times 75 \times 0.001 = \mathbf{₹8.28}$
  * Exchange Charges: $(84.10 + 110.40) \times 75 \times 0.0003553 = \mathbf{₹5.18}$ (rounded)
  * SEBI: $\mathbf{₹0.00}$
  * GST: $(40.00 + 5.18) \times 0.18 = \mathbf{₹8.13}$ (rounded)
  * Stamp Duty: $84.10 \times 75 \times 0.00003 = \mathbf{₹0.19}$ (rounded)
  * **Total Charges**: $40.00 + 8.28 + 5.18 + 0.00 + 8.13 + 0.19 = \mathbf{₹61.78}$
* **Net PnL**: $1972.50 - 61.78 = \mathbf{₹1910.72}$

---

## 3. Trade-by-Trade Accounting Table (Replay walk on 2025-04-15)

The following table displays all **11 completed trades** from the historical backtest replay on **2025-04-15** (NIFTY underlying, 5-minute EMA crossover strategy):

| Trade # | Entry Time | Exit Time | Contract | Qty | Entry px | Exit px | Gross PnL | Charges | Net PnL |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | 09:35:00 | 09:55:00 | NIFTY 23300.0 CE (2025-04-17) | 75 | 133.60 | 134.60 | ₹75.00 | ₹66.04 | ₹8.96 |
| **2** | 10:10:00 | 10:15:00 | NIFTY 23300.0 CE (2025-04-17) | 75 | 127.65 | 127.25 | ₹-30.00 | ₹65.04 | ₹-95.04 |
| **3** | 10:20:00 | 10:30:00 | NIFTY 23300.0 CE (2025-04-17) | 75 | 118.25 | 123.05 | ₹360.00 | ₹64.29 | ₹295.71 |
| **4** | 10:40:00 | 10:50:00 | NIFTY 23300.0 CE (2025-04-17) | 75 | 119.00 | 120.75 | ₹131.25 | ₹64.07 | ₹67.18 |
| **5** | 10:55:00 | 11:05:00 | NIFTY 23300.0 CE (2025-04-17) | 75 | 118.70 | 117.75 | ₹-71.25 | ₹63.73 | ₹-134.98 |
| **6** | 11:20:00 | 11:40:00 | NIFTY 23300.0 CE (2025-04-17) | 75 | 116.00 | 116.80 | ₹60.00 | ₹63.54 | ₹-3.54 |
| **7** | 11:50:00 | 12:50:00 | NIFTY 23300.0 CE (2025-04-17) | 75 | 112.90 | 133.40 | ₹1537.50 | ₹65.20 | ₹1472.30 |
| **8** | 13:00:00 | 13:10:00 | NIFTY 23350.0 CE (2025-04-17) | 75 | 103.20 | 102.35 | ₹-63.75 | ₹61.58 | ₹-125.33 |
| **9** | 14:10:00 | 14:25:00 | NIFTY 23350.0 CE (2025-04-17) | 75 | 76.95 | 82.15 | ₹390.00 | ₹58.53 | ₹331.47 |
| **10** | 14:45:00 | 14:55:00 | NIFTY 23300.0 CE (2025-04-17) | 75 | 85.95 | 91.00 | ₹378.75 | ₹59.79 | ₹318.96 |
| **11** | 15:05:00 | 15:25:00 | NIFTY 23300.0 CE (2025-04-17) | 75 | 84.10 | 110.40 | ₹1972.50 | ₹61.78 | ₹1910.72 |

### Aggregated Accounting Metrics:
* **Total Gross PnL**: **₹4,740.00**
* **Total Charges**: **₹693.59**
* **Total Net PnL**: **₹4,046.41**

---

## 4. Test Verification Summary

The test suite in `backend/v2/test_pnl_engine.py` contains **32 comprehensive tests** designed to validate every aspect of the engine.

### Run command:
```bash
PYTHONPATH=backend ./venv/bin/python -m unittest backend/v2/test_pnl_engine.py
```
### Result output:
```text
Ran 32 tests in 0.002s

OK
```

### Coverage Scope:
* **Gross PnL**: Verified winning (positive), losing (negative), flat (break-even), and massive moves.
* **Exchange & Taxes**: Individually audited STT, Exchange transaction fee, IPFT, GST (18%), Stamp Duty, and SEBI charges against official formulas.
* **Edge cases**: Verified that open positions raise `ValueError`, GST is never computed on tax components, STT is buy-exempt, and Stamp Duty is sell-exempt.
* **Lot sizing**: Confirmed volume and lot sizes scale correctly for NIFTY, BANKNIFTY, and FINNIFTY.

---

## 5. Verification Methodology
* **Precision**: To prevent floating-point representation drift (e.g. `10.0950000000000006`), each individual charge field is rounded to 2 decimal places at calculation time.
* **Deterministic Sum**: `total_charges` is derived directly as the rounded sum of individual rounded components. This guarantees that UI ledgers sum up exactly with no paise mismatches.
* **Separation of Concerns**: PnL calculations, tax models, and data persistence layers are decoupled, enabling effortless hot-swapping for future brokers or exchange fee updates.
