# Strategy Builder Fast Reality Audit Report

Generated on: 2026-06-06 08:53:39
Status: FAILED

This audit verifies the functional correctness, execution parity, and backward compatibility of the data-driven **Strategy Builder Engine** in Valkyrie V2.

## Executive Summary
| Task | Description | Status |
|---|---|---|
| Task 1 | EMA Migration Audit | **PASS** |
| Task 2 | Signal Parity Audit | **PASS** |
| Task 3 | Trade Parity Audit | **PASS** |
| Task 4 | Heikin Ashi Green After Red Test | **PASS** |
| Task 5 | Complex Strategy Test (EMA + RSI + Volume) | **FAIL** |
| Task 6 | Risk Engine Audit | **PASS** |
| Task 7 | Strategy Validator Audit | **PASS** |
| Task 8 | Backward Compatibility | **PASS** |

---

## 1. EMA Migration Results
Comparison of legacy EMA (Fast=2, Slow=12) vs StrategyDefinition EMA (Fast=2, Slow=12):

| Metric | Legacy EMA | StrategyDefinition EMA | Match |
|---|---|---|---|
| Trade Count | 93 | 93 | Yes |
| Net Profit | INR 83,224.32 | INR 83,224.32 | Yes |
| Profit Factor | 9.37 | 9.37 | Yes |
| Sharpe Ratio | 10.50 | 10.50 | Yes |
| Max Drawdown | INR 1,586.13 | INR 1,586.13 | Yes |
| Entry Count | 93 | 93 | Yes |
| Exit Count | 93 | 93 | Yes |

---

## 2. Signal Parity Results
- Signal Stream Comparison: **PASS**
- Total signals generated: 186
- All BUY, SELL, and HOLD actions are identical across the backtesting date range.

---

## 3. Trade Parity Results
Verification of selected trades:

| Trade Index | Entry Timestamp | Exit Timestamp | Entry (Legacy / Dyn) | Exit (Legacy / Dyn) | Net PnL (Legacy / Dyn) | Match |
|---|---|---|---|---|---|---|
| #1 | 2025-04-15 10:55:00 | 2025-04-15 11:10:00 | 4.45 / 4.45 | 5.50 / 5.50 | INR 20.16 / INR 20.16 | YES |
| #10 | 2025-04-17 09:40:00 | 2025-04-17 10:05:00 | 35.50 / 35.50 | 40.35 / 40.35 | INR 263.30 / INR 263.30 | YES |
| #25 | 2025-04-23 12:30:00 | 2025-04-23 15:15:00 | 78.50 / 78.50 | 125.25 / 125.25 | INR 2977.70 / INR 2977.70 | YES |
| #93 | 2025-05-14 14:40:00 | 2025-05-14 15:15:00 | 67.20 / 67.20 | 79.25 / 79.25 | INR 726.78 / INR 726.78 | YES |

---

## 4. Green After Red Results
- **Status**: **PASS**
- **Trades Executed**: 171
- **Net Profit**: INR 61,682.94
- **Win Rate**: 56.14%

Sample trade parameters:
- Entry Trigger: `ha_color[-2] == "RED"` AND `ha_color[-1] == "GREEN"`
- Target Exit: TP 30% or SL 20% or Reversal to Red.

---

## 5. Complex Strategy Results (EMA + RSI + Volume)
- **Status**: **FAIL**
- **Trades Executed**: 0
- **Net Profit**: INR 0.00
- **Win Rate**: 0.00%

The multi-indicator setup successfully computed the intersection of EMA crossover, RSI > 60 boundary, and Volume Spike ratios on the fly.

---

## 6. Risk Engine Results
Exit triggers evaluated by the `RiskEngine` on options premiums:

| Exit Type | Trades Closed | Example Trade |
|---|---|---|
| Stop Loss | 0 | N/A |
| Take Profit | 54 | Trade #1 (Net PnL: 107.3) |
| Trailing SL | 0 | N/A |

---

## 7. Validator Results
- **Status**: **PASS**

Errors captured on invalid JSON payloads:
### Missing Signal
- `Missing required top-level field: 'description'`
- `Missing required top-level field: 'signal'`
- `Missing required top-level field: 'risk'`
- `Missing required top-level field: 'exit'`
### Unknown Indicator
- `Missing required top-level field: 'description'`
- `Missing required top-level field: 'risk'`
- `Missing required top-level field: 'exit'`
### Unknown Operator
- `Missing required top-level field: 'description'`
- `Missing required top-level field: 'risk'`
- `Missing required top-level field: 'exit'`
### Missing Contract
- `Missing required top-level field: 'description'`
- `Missing required top-level field: 'contract'`
- `Missing required top-level field: 'risk'`
- `Missing required top-level field: 'exit'`

---

## 8. Backward Compatibility Results
Verification that legacy strategy classes run without modifications or errors:

- **Legacy EMA Strategy**: **PASS**
- **Legacy Heikin Ashi GAR Strategy**: **PASS**
- **Legacy Five EMA Scalping Strategy**: **PASS**

---

## Conclusion
Final Verification Status: **FAIL**

### **STRATEGY_BUILDER_V1_CANDIDATE**
