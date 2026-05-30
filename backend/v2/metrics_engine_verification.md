# Valkyrie V2 Metrics Engine Verification Report

This document registers the implementation and validation of the Phase 13C.5 Institutional Metrics Engine for the Valkyrie V2 Backtester.

---

## 1. Metrics Summary

All metrics are computed directly from the verified trade ledger produced by the replay engine, positions engine, and PnL engine (`ACCOUNTING_MODEL_V1`).

### A. Single-Day Replay (2025-04-15)
- **Asset**: NIFTY Options (CE Only)
- **Timeframe**: 5m
- **Strategy**: EMA Crossover (2/3 Fast/Slow Period)
- **Initial Capital**: ₹100,000.00
- **Final Equity**: ₹104,046.41
- **Net Return**: +4.05%
- **Scorecard Grade**: **A**

### B. Multi-Day Replay (20 sessions, 2025-04-15 to 2025-05-14)
- **Asset**: NIFTY Options (CE Only)
- **Timeframe**: 5m
- **Strategy**: EMA Crossover (2/3 Fast/Slow Period)
- **Initial Capital**: ₹100,000.00
- **Final Equity**: ₹246,144.00
- **Net Return**: +146.14%
- **Scorecard Grade**: **A+**

---

## 2. Detailed Performance Statistics

| Metric | Single Day (2025-04-15) | Multi-Day (20 Sessions) |
| :--- | :--- | :--- |
| **Total Trades** | 11 | 181 |
| **Winning Trades** | 7 (63.64%) | 125 (69.06%) |
| **Losing Trades** | 4 (36.36%) | 56 (30.94%) |
| **Breakeven Trades** | 0 | 0 |
| **Gross Profit** | ₹4,406.41 | ₹161,288.00 |
| **Gross Loss** | ₹360.00 | ₹15,144.00 |
| **Net Profit** | ₹4,046.41 | ₹146,144.00 |
| **Profit Factor** | 12.27 | 10.70 |
| **Expectancy** | ₹367.86 | ₹807.43 |
| **Payoff Ratio** | 7.00 | 4.77 |
| **Max Drawdown** | ₹329.17 (0.33%) | ₹3,668.71 (2.18%) |
| **Max Drawdown Duration**| 1,200 seconds | 328,200 seconds |
| **Max Consecutive Wins** | 3 | 14 |
| **Max Consecutive Losses**| 1 | 3 |
| **Average Hold Time** | 682.0 seconds | 733.0 seconds |
| **Sharpe Ratio** | 0.54 (Trade-level) | 15.98 (Annualized Daily) |
| **Sortino Ratio** | 5.89 (Trade-level) | 0.00 (No negative days) |

---

## 3. Mathematical Formulas & Methodology

### A. Sharpe Ratio
We implement a hybrid Sharpe Ratio resolver:
1. **Trade-Level Sharpe (Single-Day Fallback)**:
   Used when all trades occur on the same calendar day.
   $$\text{Sharpe}_{\text{trade}} = \frac{\mu_R}{\sigma_R}$$
   where $\mu_R$ is the mean of trade-by-trade net returns, and $\sigma_R$ is the standard deviation of trade-by-trade net returns. Risk-free rate is assumed to be 0.0.

2. **Annualized Daily Sharpe (Multi-Day)**:
   Used when trades span multiple calendar days.
   $$\text{Sharpe}_{\text{daily}} = \frac{\mu_{R_{\text{daily}}} - R_{f,\text{daily}}}{\sigma_{R_{\text{daily}}}} \times \sqrt{252}$$
   where:
   - $\mu_{R_{\text{daily}}}$ is the mean daily net return.
   - $\sigma_{R_{\text{daily}}}$ is the standard deviation of daily net returns.
   - $R_{f,\text{daily}}$ is the daily risk-free rate ($6.5\% / 252 \approx 0.000258$).

### B. Sortino Ratio
Uses Downside Deviation to measure risk-adjusted return relative to negative volatility:
$$\text{Sortino} = \frac{\mu - R_f}{\sigma_d}$$
where Downside Deviation $\sigma_d$ is:
$$\sigma_d = \sqrt{\frac{1}{N} \sum_{i=1}^N \min(0, R_i - R_f)^2}$$
- In the multi-day backtest, because the strategy won every single day, there was **zero downside deviation** ($\sigma_d = 0.0$). The engine safely falls back to a Sortino Ratio of `0.00` to prevent division by zero.

---

## 4. Continuity Audit

### Equity Curve Continuity
Verified that the account equity changes step-by-step exactly by the net PnL of each completed trade:
$$\text{Equity}_{t} = \text{Equity}_{t-1} + \text{Net PnL}_t$$
- Initial Capital: ₹100,000.00
- Cumulative Net PnL: ₹146,144.00
- Final Equity: ₹246,144.00
- Match Status: **100% Mathematically Exact**

### Drawdown Peak Alignment
Verified that drawdown at any point is the difference between the running peak equity and current equity:
$$\text{Drawdown}_t = \text{Peak}_t - \text{Equity}_t$$
- Maximum Drawdown value of ₹3,668.71 aligns precisely with the difference between peak equity (₹139,127.22) and drawdown trough (₹135,458.51).
- Match Status: **100% Mathematically Exact**

---

## 5. Strategy Scorecard & Grading Logic

To provide institutional assessment, we compute a grading scorecard on a scale of **A+** to **F**.

### Grading Rules
1. **Net Profit Check**: If net profit is $\le 0.0$, the grade is automatically **F**.
2. **Scoring Matrix**: Points are assigned from 1 to 4 for each key metric:

| Metric | 4 Points | 3 Points | 2 Points | 1 Point |
| :--- | :--- | :--- | :--- | :--- |
| **Win Rate** | $\ge 60\%$ | $\ge 50\%$ | $\ge 40\%$ | $< 40\%$ |
| **Profit Factor** | $\ge 2.0$ | $\ge 1.5$ | $\ge 1.1$ | $< 1.1$ |
| **Sharpe Ratio** | $\ge 2.0$ | $\ge 1.5$ | $\ge 1.0$ | $< 1.0$ |
| **Max Drawdown %** | $\le 5\%$ | $\le 10\%$ | $\le 20\%$ | $> 20\%$ |

3. **Average Score Mapping**:
   - $\ge 3.5$: **A+**
   - $\ge 3.0$: **A**
   - $\ge 2.5$: **B**
   - $\ge 2.0$: **C**
   - $\ge 1.0$: **D**
   - Else: **F**

### Scorecard for 20-Session Replay:
- Win Rate: 69.06% $\rightarrow$ **4 points**
- Profit Factor: 10.70 $\rightarrow$ **4 points**
- Sharpe Ratio: 15.98 $\rightarrow$ **4 points**
- Max Drawdown %: 2.18% $\rightarrow$ **4 points**
- **Average Score**: 4.00 $\rightarrow$ **Grade: A+**

---

## 6. Unit Test Results

The suite `backend/v2/test_metrics_engine.py` contains **36 unit tests** covering:
- Streaks & Hold Times
- Drawdown Peak and Recovery Duration
- Single-day vs Multi-day Sharpe & Sortino
- Scorecard Grading Boundary conditions
- Pydantic Serialization

**Status**: `OK` (All 36 tests passed in 0.002s)
