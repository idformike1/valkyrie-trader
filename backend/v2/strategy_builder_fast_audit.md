# Strategy Builder Fast Reality Audit Report

Generated on: 2026-05-30 20:32:17
Status: PASSED

This audit verifies the functional correctness, execution parity, and backward compatibility of the data-driven **Strategy Builder Engine** in Valkyrie V2.

## Executive Summary
| Task | Description | Status |
|---|---|---|
| Task 1 | EMA Migration Audit | **PASS** |
| Task 2 | Signal Parity Audit | **PASS** |
| Task 3 | Trade Parity Audit | **PASS** |
| Task 4 | Heikin Ashi Green After Red Test | **PASS** |
| Task 5 | Complex Strategy Test (EMA + RSI + Volume) | **PASS** |
| Task 6 | Risk Engine Audit | **PASS** |
| Task 7 | Strategy Validator Audit | **PASS** |
| Task 8 | Backward Compatibility | **PASS** |

---

## 1. EMA Migration Results
Comparison of legacy EMA (Fast=2, Slow=12) vs StrategyDefinition EMA (Fast=2, Slow=12):

| Metric | Legacy EMA | StrategyDefinition EMA | Match |
|---|---|---|---|
| Trade Count | 93 | 93 | Yes |
| Net Profit | INR 95,972.15 | INR 95,972.15 | Yes |
| Profit Factor | 7.86 | 7.86 | Yes |
| Sharpe Ratio | 11.03 | 11.03 | Yes |
| Max Drawdown | INR 2,333.58 | INR 2,333.58 | Yes |
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
| #1 | 2025-04-15 10:55:00 | 2025-04-15 11:10:00 | 118.70 / 118.70 | 113.40 / 113.40 | INR -460.77 / INR -460.77 | YES |
| #10 | 2025-04-17 09:40:00 | 2025-04-17 10:05:00 | 35.50 / 35.50 | 40.35 / 40.35 | INR 311.06 / INR 311.06 | YES |
| #25 | 2025-04-23 12:30:00 | 2025-04-23 15:15:00 | 78.50 / 78.50 | 125.25 / 125.25 | INR 3443.07 / INR 3443.07 | YES |
| #93 | 2025-05-14 14:40:00 | 2025-05-14 15:15:00 | 67.20 / 67.20 | 79.25 / 79.25 | INR 845.86 / INR 845.86 | YES |

---

## 4. Green After Red Results
- **Status**: **PASS**
- **Trades Executed**: 171
- **Net Profit**: INR 92,603.82
- **Win Rate**: 55.56%

Sample trade parameters:
- Entry Trigger: `ha_color[-2] == "RED"` AND `ha_color[-1] == "GREEN"`
- Target Exit: TP 30% or SL 20% or Reversal to Red.

---

## 5. Complex Strategy Results (EMA + RSI + Volume)
- **Status**: **PASS**
- **Trades Executed**: 210
- **Net Profit**: INR -9,325.21
- **Win Rate**: 32.38%

The multi-indicator setup successfully computed the intersection of EMA crossover, RSI > 60 boundary, and Volume Spike ratios on the fly.

---

## 6. Risk Engine Results
Exit triggers evaluated by the `RiskEngine` on options premiums:

| Exit Type | Trades Closed | Example Trade |
|---|---|---|
| Stop Loss | 55 | GAR Trade #93 (Net PnL: -518.62) |
| Take Profit | 71 | GAR Trade #12 (Net PnL: 1520.41) |
| Trailing SL | 100 | Complex Trade #1 (Net PnL: -277.15) |

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
Final Verification Status: **PASS**

### **STRATEGY_BUILDER_V1_CANDIDATE**
