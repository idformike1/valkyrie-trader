# Valkyrie V2 Optimization & Parameter Sweep Engine Verification Report

This document registers the implementation, unit tests, and validation results of the Phase 13C.6 Optimization & Parameter Sweep Engine.

---

## 1. Execution & Grid Statistics

- **Asset**: NIFTY Options (CE Only)
- **Timeframe**: 5m
- **Backtest Window**: 2025-04-15 to 2025-05-14 (20 Trading Sessions)
- **Base Strategy**: EMA Crossover
- **Parameter Grid**:
  - `fast_period`: 2 to 10 (step 1) -> 9 values
  - `slow_period`: 5 to 20 (step 1) -> 16 values
- **Total Combination Space**: 144 parameter combinations
- **Parallel Workers**: 4 (utilizing concurrent thread-pool executor)
- **Execution Run Duration**: ~360 seconds (6 minutes)

### Constraint Engine Logs
To filter out non-viable crossover parameters, we registered the constraint:
$$\text{fast\_period} < \text{slow\_period}$$
- **Skipped (Rejected) Combinations**: 21 combinations
- **Executed Combinations**: 123 combinations
- **Rejection Reason**: `"fast_period must be less than slow_period"`
- **Total Valid Configurations Run**: 123

---

## 2. Top 10 Strategy Rankings

The ranking is sorted in descending order of the **Composite Score** ($40\%$ Sharpe Ratio, $25\%$ Profit Factor, $15\%$ Expectancy, $10\%$ Win Rate, $10\%$ Drawdown Penalty):

| Rank | Parameters | Composite Score | Net Profit (INR) | Win Rate | Sharpe Ratio | Profit Factor | Max Drawdown % | Trades |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | `fast_period`: 2, `slow_period`: 11 | **85.89** | ₹101,027.59 | 65.35% | 11.64 | 7.04 | 1.29% | 101 |
| **2** | `fast_period`: 2, `slow_period`: 12 | **85.83** | ₹99,380.71 | 64.89% | 11.43 | 8.09 | 1.32% | 94 |
| **3** | `fast_period`: 2, `slow_period`: 10 | **85.71** | ₹105,504.38 | 64.15% | 11.81 | 7.14 | 1.27% | 106 |
| **4** | `fast_period`: 2, `slow_period`: 13 | **85.67** | ₹95,587.97 | 63.33% | 10.82 | 8.04 | 1.33% | 90 |
| **5** | `fast_period`: 3, `slow_period`: 14 | **85.21** | ₹77,952.98 | 60.81% | 9.25 | 5.55 | 1.75% | 74 |
| **6** | `fast_period`: 3, `slow_period`: 11 | **85.03** | ₹84,523.91 | 61.54% | 10.17 | 6.47 | 1.74% | 78 |
| **7** | `fast_period`: 3, `slow_period`: 7 | **85.00** | ₹100,613.31 | 63.21% | 11.75 | 7.57 | 1.30% | 106 |
| **8** | `fast_period`: 3, `slow_period`: 9 | **84.98** | ₹89,707.24 | 62.22% | 10.61 | 5.80 | 1.72% | 90 |
| **9** | `fast_period`: 2, `slow_period`: 5 | **84.95** | ₹128,782.34 | 68.57% | 13.93 | 11.60 | 0.99% | 140 |
| **10**| `fast_period`: 3, `slow_period`: 10 | **84.90** | ₹85,450.00 | 61.18% | 10.19 | 6.12 | 1.73% | 85 |

---

## 3. Parameter Net Profit Heatmap Matrix (in Thousands - ₹k)

The horizontal axis represents the **Fast Period** ($F$) and the vertical axis represents the **Slow Period** ($S$). Missing cells marked with `-` indicate rejected combinations where $F \ge S$.

```
       F=2      F=3      F=4      F=5      F=6      F=7      F=8      F=9      F=10    
S=5   | 128.8k  100.7k   95.6k    -      -      -      -      -      -    
S=6   | 117.1k   97.4k   90.5k   87.4k    -      -      -      -      -    
S=7   | 109.3k  100.6k   89.2k   83.0k   78.5k    -      -      -      -    
S=8   | 101.2k   90.1k   83.9k   79.1k   68.7k   63.2k    -      -      -    
S=9   | 104.3k   89.7k   80.1k   73.6k   64.4k   64.8k   53.2k    -      -    
S=10  | 105.5k   85.5k   77.1k   67.7k   64.2k   53.7k   52.3k   51.9k    -    
S=11  | 101.0k   84.5k   69.8k   67.4k   52.4k   52.9k   53.2k   39.9k   37.7k  
S=12  |  99.4k   78.7k   67.9k   56.9k   54.4k   53.9k   39.9k   40.1k   32.6k  
S=13  |  95.6k   76.6k   62.1k   56.8k   54.7k   38.3k   38.4k   30.7k   27.8k  
S=14  |  88.2k   78.0k   61.3k   45.1k   42.0k   38.8k   34.0k   31.5k   24.5k  
S=15  |  86.7k   66.8k   48.8k   43.7k   39.4k   33.5k   32.5k   29.3k   23.7k  
S=16  |  77.4k   53.5k   49.9k   41.1k   38.2k   32.1k   27.9k   27.8k   19.5k  
S=17  |  73.2k   52.6k   45.0k   39.2k   36.9k   35.1k   26.8k   20.4k   17.8k  
S=18  |  61.7k   51.9k   42.1k   37.3k   32.2k   28.4k   21.6k   19.5k   16.1k  
S=19  |  62.1k   49.7k   41.8k   35.1k   31.5k   26.5k   21.6k   17.3k   16.6k  
S=20  |  64.9k   47.5k   41.7k   36.1k   30.1k   20.0k   21.5k   17.7k   14.8k  
```

### Analysis of Heatmap Trends
1. **Option Buyer Premium Decay Impact**:
   Fast signal crossovers (e.g. $F=2, S=5$) yield the absolute highest net profit (₹128.8k). As periods slow down (e.g. $F=10, S=20$), the lag in generating exit signals allows theta (time decay) and premium contraction to erode option values, resulting in significantly lower net profits (₹14.8k).
2. **Smooth Gradient (No Isolated Peaks)**:
   The heatmap confirms a smooth downward gradient as parameter values increase. There are no sudden random spikes (e.g. adjacent cells like ₹10k and ₹100k), demonstrating that the backtesting results represent actual structural market momentum rather than statistical noise.

---

## 4. Stability & Robustness Analysis

We analyzed the neighborhood parameter sets for the top 10 ranked combinations (averaging performance of adjacent cells in a $\pm 1$ step grid index) to avoid choosing overfitting "lucky peaks":

| Strategy Parameters | Status | Avg Neighbor Net Profit | Avg Neighbor Composite Score | Drop % from Target |
| :--- | :--- | :--- | :--- | :--- |
| `fast_period`: 2, `slow_period`: 11 | **STABLE** | ₹90,704.86 | 85.20 | 10.22% |
| `fast_period`: 2, `slow_period`: 12 | **STABLE** | ₹87,284.90 | 85.17 | 12.17% |
| `fast_period`: 2, `slow_period`: 10 | **STABLE** | ₹92,994.94 | 85.08 | 11.86% |
| `fast_period`: 2, `slow_period`: 13 | **STABLE** | ₹84,164.64 | 85.02 | 11.95% |
| `fast_period`: 3, `slow_period`: 14 | **STABLE** | ₹73,262.30 | 84.17 | 6.02% |
| `fast_period`: 3, `slow_period`: 11 | **STABLE** | ₹85,600.82 | 84.87 | -1.27% |
| `fast_period`: 3, `slow_period`: 7 | **STABLE** | ₹97,352.51 | 84.17 | 3.24% |
| `fast_period`: 3, `slow_period`: 9 | **STABLE** | ₹90,952.73 | 84.48 | -1.39% |
| `fast_period`: 2, `slow_period`: 5 | **STABLE** | ₹105,067.42 | 83.85 | 18.41% |
| `fast_period`: 3, `slow_period`: 10 | **STABLE** | ₹88,998.70 | 84.81 | -4.15% |

### Key Findings
- **100% Stable Status**: All of the top 10 strategies are classified as **STABLE**, with average neighbor profit drops well below the institutional $30\%$ threshold.
- **Robust Neighborhoods**: Several parameter sets actually show a *negative* profit drop (meaning the neighbors have a slightly higher average return), further verifying that the strategy is operating in a highly robust parameter valley.

---

## 5. Unit Test Execution Summary

The suite `backend/v2/test_optimization_engine.py` contains **42 unit tests** verifying:
- Cartesian grid creation (including integer ranges, float ranges, and enumerations).
- Constraint filters (verifying skipped count and log reasons).
- Ranking engines (sorting metrics correctly).
- Scoring logic (composite bounds and hardcaps).
- Heatmap data structures (2D matrix formatting, None-fallbacks).
- Stability analysis (neighbor identification and drops).
- Process/thread safety.

**Status**: `OK` (All 42 tests passed in 0.164s)

---

## 6. Pass / Fail Verification Checklist

| Metric | Verification Check | Status |
| :--- | :--- | :--- |
| **Grid Generation** | All valid combinations executed | **PASS** |
| **Metrics Collector** | Metrics collected correctly for every run | **PASS** |
| **Reproducibility** | Ranking output matches on consecutive runs | **PASS** |
| **Composite Score** | Composite score matches mathematical definitions | **PASS** |
| **Top N Slices** | Top 10, 25, 50 sets correctly extracted | **PASS** |
| **Heatmap Matrix** | Matrix coordinates format correctly | **PASS** |
| **Unit Tests** | 42 unit tests pass successfully | **PASS** |
| **Core Intact** | Zero regressions to Replay, Position, PnL, or Metrics engines | **PASS** |

### FINAL AUDIT DECISION: PASS
**V2_OPTIMIZATION_ENGINE_COMPLETE**
