# Replay Signal Validation

This document presents the detailed candle-by-candle audit and signal validation for the NIFTY replay on **2025-04-15** under 5-minute intervals using the EMA Crossover strategy (Fast EMA = 2, Slow EMA = 3, cutoff time = 15:25).

---

## 1. Step-by-Step Candle Calculations & Signal Output

Below is the complete dataset for the 75 candles of the session. It tracks the spot price, the calculated EMAs, and the resulting signals.

| Candle | Timestamp | Close | EMA Fast (2) | EMA Slow (3) | Signal Output | Position State | Notes / Crossover Type |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | 09:15:00 | 23279.40 | 23279.4000 | 23279.4000 | HOLD | Flat | Warm-up start |
| 1 | 09:20:00 | 23299.90 | 23293.0667 | 23289.6500 | HOLD | Flat | Warm-up |
| 2 | 09:25:00 | 23297.65 | 23296.1222 | 23293.6500 | HOLD | Flat | Warm-up |
| 3 | 09:30:00 | 23267.40 | 23276.9741 | 23280.5250 | HOLD | Flat | Warm-up (Fast < Slow) |
| 4 | 09:35:00 | 23300.55 | 23292.6914 | 23290.5375 | **BUY** | Long CE | **Bullish Crossover** (Fast > Slow) |
| 5 | 09:40:00 | 23310.95 | 23304.8638 | 23300.7438 | HOLD | Long CE | Persistent trend |
| 6 | 09:45:00 | 23316.45 | 23312.5879 | 23308.5969 | HOLD | Long CE | Persistent trend |
| 7 | 09:50:00 | 23329.65 | 23323.9626 | 23319.1234 | HOLD | Long CE | Persistent trend |
| 8 | 09:55:00 | 23306.10 | 23312.0542 | 23312.6117 | **SELL** | Flat | **Bearish Crossover** (Fast < Slow) |
| 9 | 10:00:00 | 23302.10 | 23305.4181 | 23307.3559 | HOLD | Flat | Flat (Fast < Slow) |
| 10 | 10:05:00 | 23306.85 | 23306.3727 | 23307.1029 | HOLD | Flat | Flat (Fast < Slow) |
| 11 | 10:10:00 | 23312.10 | 23310.1909 | 23309.6015 | **BUY** | Long CE | **Bullish Crossover** (Fast > Slow) |
| 12 | 10:15:00 | 23301.20 | 23304.1970 | 23305.4007 | **SELL** | Flat | **Bearish Crossover** (Fast < Slow) |
| 13 | 10:20:00 | 23308.85 | 23307.2990 | 23307.1254 | **BUY** | Long CE | **Bullish Crossover** (Fast > Slow) |
| 14 | 10:25:00 | 23314.90 | 23312.3663 | 23311.0127 | HOLD | Long CE | Persistent trend |
| 15 | 10:30:00 | 23307.95 | 23309.4221 | 23309.4813 | **SELL** | Flat | **Bearish Crossover** (Fast < Slow) |
| 16 | 10:35:00 | 23306.60 | 23307.5407 | 23308.0407 | HOLD | Flat | Flat (Fast < Slow) |
| 17 | 10:40:00 | 23309.60 | 23308.9136 | 23308.8203 | **BUY** | Long CE | **Bullish Crossover** (Fast > Slow) |
| 18 | 10:45:00 | 23311.75 | 23310.8045 | 23310.2852 | HOLD | Long CE | Persistent trend |
| 19 | 10:50:00 | 23304.30 | 23306.4682 | 23307.2926 | **SELL** | Flat | **Bearish Crossover** (Fast < Slow) |
| 20 | 10:55:00 | 23309.55 | 23308.5227 | 23308.4213 | **BUY** | Long CE | **Bullish Crossover** (Fast > Slow) |
| 21 | 11:00:00 | 23314.50 | 23312.5076 | 23311.4606 | HOLD | Long CE | Persistent trend |
| 22 | 11:05:00 | 23308.80 | 23310.0359 | 23310.1303 | **SELL** | Flat | **Bearish Crossover** (Fast < Slow) |
| 23 | 11:10:00 | 23295.15 | 23300.1120 | 23302.6402 | HOLD | Flat | Flat (Fast < Slow) |
| 24 | 11:15:00 | 23303.90 | 23302.6373 | 23303.2701 | HOLD | Flat | Flat (Fast < Slow) |
| 25 | 11:20:00 | 23305.30 | 23304.4124 | 23304.2850 | **BUY** | Long CE | **Bullish Crossover** (Fast > Slow) |
| 26 | 11:25:00 | 23311.00 | 23308.8041 | 23307.6425 | HOLD | Long CE | Persistent trend |
| 27 | 11:30:00 | 23305.55 | 23306.6347 | 23306.5963 | HOLD | Long CE | Persistent trend |
| 28 | 11:35:00 | 23307.35 | 23307.1116 | 23306.9731 | HOLD | Long CE | Persistent trend |
| 29 | 11:40:00 | 23304.90 | 23305.6372 | 23305.9366 | **SELL** | Flat | **Bearish Crossover** (Fast < Slow) |
| 30 | 11:45:00 | 23299.25 | 23301.3791 | 23302.5933 | HOLD | Flat | Flat (Fast < Slow) |
| 31 | 11:50:00 | 23305.85 | 23304.3597 | 23304.2216 | **BUY** | Long CE | **Bullish Crossover** (Fast > Slow) |
| 32 | 11:55:00 | 23312.80 | 23309.9866 | 23308.5108 | HOLD | Long CE | Persistent trend |
| 33 | 12:00:00 | 23318.15 | 23315.4289 | 23313.3304 | HOLD | Long CE | Persistent trend |
| 34 | 12:05:00 | 23325.50 | 23322.1430 | 23319.4152 | HOLD | Long CE | ATM migrates 23300 -> 23350 |
| 35 | 12:10:00 | 23332.55 | 23329.0810 | 23325.9826 | HOLD | Long CE | Persistent trend |
| 36 | 12:15:00 | 23336.60 | 23334.0937 | 23331.2913 | HOLD | Long CE | Persistent trend |
| 37 | 12:20:00 | 23335.80 | 23335.2312 | 23333.5457 | HOLD | Long CE | Persistent trend |
| 38 | 12:25:00 | 23337.35 | 23336.6437 | 23335.4478 | HOLD | Long CE | Persistent trend |
| 39 | 12:30:00 | 23345.75 | 23342.7146 | 23340.5989 | HOLD | Long CE | Persistent trend |
| 40 | 12:35:00 | 23344.40 | 23343.8382 | 23342.4995 | HOLD | Long CE | Persistent trend |
| 41 | 12:40:00 | 23340.35 | 23341.5127 | 23341.4247 | HOLD | Long CE | Persistent trend |
| 42 | 12:45:00 | 23342.10 | 23341.9042 | 23341.7624 | HOLD | Long CE | Persistent trend |
| 43 | 12:50:00 | 23335.45 | 23337.6014 | 23338.6062 | **SELL** | Flat | **Bearish Crossover** (Fast < Slow) |
| 44 | 12:55:00 | 23337.80 | 23337.7338 | 23338.2031 | HOLD | Flat | Flat (Fast < Slow) |
| 45 | 13:00:00 | 23345.50 | 23342.9113 | 23341.8515 | **BUY** | Long CE | **Bullish Crossover** (Fast > Slow) |
| 46 | 13:05:00 | 23344.60 | 23344.0371 | 23343.2258 | HOLD | Long CE | Persistent trend |
| 47 | 13:10:00 | 23337.70 | 23339.8124 | 23340.4629 | **SELL** | Flat | **Bearish Crossover** (Fast < Slow) |
| 48 | 13:15:00 | 23331.35 | 23334.1708 | 23335.9064 | HOLD | Flat | Flat (Fast < Slow) |
| 49 | 13:20:00 | 23332.20 | 23332.8569 | 23334.0532 | HOLD | Flat | Flat (Fast < Slow) |
| 50 | 13:25:00 | 23334.20 | 23333.7523 | 23334.1266 | HOLD | Flat | Flat (Fast < Slow) |
| 51 | 13:30:00 | 23332.80 | 23333.1174 | 23333.4633 | HOLD | Flat | Flat (Fast < Slow) |
| 52 | 13:35:00 | 23327.20 | 23329.1725 | 23330.3317 | HOLD | Flat | Flat (Fast < Slow) |
| 53 | 13:40:00 | 23328.55 | 23328.7575 | 23329.4408 | HOLD | Flat | Flat (Fast < Slow) |
| 54 | 13:45:00 | 23325.00 | 23326.2525 | 23327.2204 | HOLD | Flat | Flat (Fast < Slow) |
| 55 | 13:50:00 | 23326.25 | 23326.2508 | 23326.7352 | HOLD | Flat | Flat (Fast < Slow) |
| 56 | 13:55:00 | 23325.75 | 23325.9169 | 23326.2426 | HOLD | Flat | Flat (Fast < Slow) |
| 57 | 14:00:00 | 23323.35 | 23324.2056 | 23324.7963 | HOLD | Flat | Flat (Fast < Slow) |
| 58 | 14:05:00 | 23320.65 | 23321.8352 | 23322.7232 | HOLD | Flat | Flat (Fast < Slow) |
| 59 | 14:10:00 | 23326.05 | 23324.6451 | 23324.3866 | **BUY** | Long CE | **Bullish Crossover** (Fast > Slow) |
| 60 | 14:15:00 | 23329.20 | 23327.6817 | 23326.7933 | HOLD | Long CE | Persistent trend |
| 61 | 14:20:00 | 23331.50 | 23330.2272 | 23329.1466 | HOLD | Long CE | Persistent trend |
| 62 | 14:25:00 | 23323.20 | 23325.5424 | 23326.1733 | **SELL** | Flat | **Bearish Crossover** (Fast < Slow) |
| 63 | 14:30:00 | 23315.85 | 23319.0808 | 23321.0117 | HOLD | Flat | Flat (Fast < Slow) |
| 64 | 14:35:00 | 23316.80 | 23317.5603 | 23318.9058 | HOLD | Flat | Flat (Fast < Slow) |
| 65 | 14:40:00 | 23309.60 | 23312.2534 | 23314.2529 | HOLD | Flat | Flat (Fast < Slow) |
| 66 | 14:45:00 | 23323.15 | 23319.5178 | 23318.7015 | **BUY** | Long CE | **Bullish Crossover** (Fast > Slow) |
| 67 | 14:50:00 | 23319.90 | 23319.7726 | 23319.3007 | HOLD | Long CE | Persistent trend |
| 68 | 14:55:00 | 23312.00 | 23314.5909 | 23315.6504 | **SELL** | Flat | **Bearish Crossover** (Fast < Slow) |
| 69 | 15:00:00 | 23317.00 | 23316.1970 | 23316.3252 | HOLD | Flat | Flat (Fast < Slow) |
| 70 | 15:05:00 | 23320.85 | 23319.2990 | 23318.5876 | **BUY** | Long CE | **Bullish Crossover** (Fast > Slow) |
| 71 | 15:10:00 | 23321.20 | 23320.5663 | 23319.8938 | HOLD | Long CE | Persistent trend |
| 72 | 15:15:00 | 23328.05 | 23325.5554 | 23323.9719 | HOLD | Long CE | Persistent trend |
| 73 | 15:20:00 | 23343.35 | 23337.4185 | 23333.6609 | HOLD | Long CE | Persistent trend |
| 74 | 15:25:00 | 23344.10 | 23341.8728 | 23338.8805 | **SELL** | Flat | **Session Cutoff** (Time $\ge$ 15:25) |

---

## 2. Validation Audit Results

* **Bullish Crossover Verification**:
  * Every single `BUY` signal is generated exactly when `EMA Fast` crosses above `EMA Slow` (i.e. `prev_fast <= prev_slow` and `curr_fast > curr_slow`).
  * Total Bullish Crossovers: **11**.
* **Bearish Crossover & Cutoff Verification**:
  * Out of the 11 `SELL` signals:
    * **10** are triggered by a bearish crossover (`EMA Fast` crossing below `EMA Slow`).
    * **1** is triggered by the session cutoff rule (`time >= 15:25`) at index 74, enforcing flat books at day end.
* **No Phantom Signals**:
  * There are **zero** instances where a signal was generated without meeting the explicit mathematical crossover condition or session end parameter.
* **Status**: **PASS**
