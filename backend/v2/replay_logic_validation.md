# Replay Logic Validation Report

This report presents the findings of the **Replay Logic Validation Audit** conducted on the Valkyrie V2 Historical Replay Engine. It verifies that all trade lifecycles, signal translations, contract rolls, and mathematical calculations are correct prior to building the position management and P&L layers.

---

## 1. Signal Audit (BUY_INTENT & SELL_INTENT)

During the replay run on **2025-04-15** for NIFTY (5m timeframe, EMA strategy), the engine generated exactly **22 trade intent events** (11 BUY_INTENT and 11 SELL_INTENT).
- **BUY_INTENT** is emitted when the strategy generates a `BUY` signal, which triggers contract resolution (ATM strike, Weekly expiry) and premium price fetch.
- **SELL_INTENT** is emitted when the strategy generates an `EXIT` or `SELL` signal. This fetches the exit premium of the currently held option contract and closes out the trade.

Both represent valid, actionable trade entries and exits. No phantom signals or stray intents were detected.

---

## 2. EMA Audit & Crossover Verification

The `EmaCrossoverStrategy` uses pandas `.ewm(span=X, adjust=False).mean()` to compute indicators. 
- The strategy requires a warmup period of at least `slow_period + 2` candles (23 candles for a 9/21 setup; 5 candles for our 2/3 validation setup).
- Every `BUY` signal corresponded strictly to a bullish crossover:
  $$\text{EMA Fast}_{t-1} \le \text{EMA Slow}_{t-1} \quad \text{and} \quad \text{EMA Fast}_t > \text{EMA Slow}_t$$
- Every `SELL` signal corresponded to a bearish crossover:
  $$\text{EMA Fast}_t < \text{EMA Slow}_t$$
  ...except for the final exit candle at `15:25:00` which was triggered by the session cutoff rule, enforcing a flat book before market close.

All calculations are mathematically correct and conform directly to the strategy specifications.

---

## 3. HOLD State Audit

When a strong trend persists, the strategy must remain in a `HOLD` state to avoid spamming duplicate trade intents.
- **Observed Behavior**: At index 4 (`09:35:00`), a `BUY_INTENT` was generated for `23300.0 CE`.
- For the next three candles (index 5, 6, 7), the trend persisted upward. The signal output remained `HOLD`.
- No new `BUY_INTENT` events were generated.
- The engine enforces this by ignoring all `BUY` signals when a position is already active:
  ```python
  # Code trace from backend/v2/replay_engine.py:
  if signal == "BUY":
      if active_contract is not None:
          continue  # Already in position, ignore new entries
  ```
This behavior is verified as correct: `BUY -> HOLD -> HOLD -> HOLD -> SELL`.

---

## 4. Duplicate Signal Audit

A check was run across all 75 candles to verify that no duplicate identical intents were generated on consecutive candles.
- **Signal Count**:
  - `BUY` signals: **11**
  - `SELL` signals: **11**
  - `HOLD` signals: **53**
- Consecutive candles never produced consecutive identical actions (e.g. `BUY` then `BUY` was never observed). Even when a position was exited and entered quickly (e.g., BUY at 11, SELL at 12, BUY at 13), each step represented a distinct, alternating crossover event.
- **Status**: **PASS**

---

## 5. ATM Transition Audit

The underlying spot price fluctuated across strike boundaries during the replay. Strike intervals for NIFTY are 50.
- **ATM Strike Calculation**: $\text{ATM} = \text{round}(\text{Spot} / 50) * 50$.
- **ATM Transition Timeline**:
  - At **11:50:00** (Spot: `23305.85`): ATM strike was resolved to `23300`. A `BUY_INTENT` was triggered for the `23300 CE` contract.
  - At **12:05:00** (Spot: `23325.50`): ATM strike migrated from `23300` to `23350` (since $23325.50 \ge 23325.0$). The strategy was in a `HOLD` state, holding the `23300 CE` contract.
  - At **12:50:00** (Spot: `23335.45`): A `SELL_INTENT` occurred, exiting the original `23300 CE` contract.
  - At **13:00:00** (Spot: `23345.50`): A new `BUY_INTENT` occurred. The strike resolved to the new ATM strike: `23350 CE`.
- Strike migration functions correctly: it resolves the strike using the current spot price at the exact moment of a `BUY_INTENT` trigger.

---

## 6. Contract Switching Audit

When the ATM strike changes mid-trade (e.g., at `12:05:00` while holding the `23300 CE` contract), how does the engine behave?
- **Behavior**: The engine **continues using the original contract** until an exit signal is received. It does *not* dynamically switch or rotate contracts mid-trade.
- **Code Path Trace**:
  ```python
  # Code trace from backend/v2/replay_engine.py:
  elif signal == "SELL":
      if active_contract is None:
          continue
      
      # Looks up premium using the strike stored in the active contract:
      premium_candle = self._lookup_premium(
          index_name=underlying_name,
          strike=active_contract["strike"],       # Stays 23300.0
          expiry=active_contract["expiry"],       # Stays 2025-04-17
          option_type=active_contract["option_type"],
          timeframe="1m",
          timestamp=current_ts,
          day_date=current_ts
      )
  ```
This is the correct behavior for standard options backtesting: positions remain tied to the specific contract purchased at entry.

---

## 7. Expiry Rollover Audit

To verify that the `CURRENT_WEEKLY` expiry resolver handles the transition across expiry dates correctly, we ran the engine across the `2025-04-17` weekly expiry boundary:
- **Before & On Expiry Day**:
  - Replay Date: `2025-04-16` -> Resolves to `2025-04-17` expiry (correct).
  - Replay Date: `2025-04-17` (expiry day) -> Resolves to `2025-04-17` expiry (correct).
- **After Expiry Day**:
  - Replay Date: `2025-04-21` (next trading day) -> Resolves to `2025-04-24` expiry (correct weekly roll).
  - Replay Date: `2025-04-22` -> Resolves to `2025-04-24` expiry (correct weekly roll).
- **Status**: **PASS** (rollover logic is fully correct and contains zero hardcoded shortcuts).

---

## 8. Multi-Day Replay Audit

The replay engine supports continuous execution across multiple consecutive trading days:
- Spot underlying candles are resampled as a single continuous time series.
- Indicators (EMAs) do not reset at session boundaries; they maintain their warmed-up state across days.
- State is preserved inside the `SignalAdapter` strategy object without corruption or leaks.
- Contract lookups continue successfully on subsequent days, failover handles API errors gracefully, and caches are populated correctly.

---

## 9. Look-Ahead Bias Audit

To prevent future leakage:
- Resampling is executed only on completed historical intervals.
- The chronological loop restricts the strategy evaluation slice to `candles[:i+1]`.
- **Unit Test Evidence**: `TestHistoricalReplayEngine.test_evaluation_history_growth` patches `SignalAdapter.evaluate` and verifies that the history list length grows exactly by 1 at each step, and that the last item corresponds strictly to the current step timestamp.
- **Status**: **PASS**

---

## 10. Trade Lifecycle Recommendation for Phase 13C.3

Based on our findings, we recommend implementing **Option C (Configurable trade lifecycles)** for Phase 13C.3:

### Proposed Architecture

```
[SignalAdapter] 
       ↓
[Execution Router]
       ↓
┌───────────────────────┼────────────────────────┐
↓                       ↓                        ↓
[Option A: Hold/Exit]   [Option B: Swaps/Flips]  [Option D: Strike Rolling]
- Buy and hold contract - Exit CE, Buy PE        - Adjusts position strike
  until bearish cross.   on bearish crossover.   when ATM shifts.
```

### Recommendation Details

1. **Options Scalping**: Use **Option A (Hold / Exit)** with short SL/TP brackets and trailing stops. Option contracts decay quickly; holding through whipsaws is high-risk, and scalpers need immediate exit rather than automated reversal.
2. **ATM Rotation**: Require **Option D (Strike Rolling / Rotation)** as a configurable option. If a strategy wishes to remain delta-neutral or ATM, it needs to close the old strike and open the new strike when the ATM shifts. This requires position adjustment triggers.
3. **Weekly Expiry Trading**: Require a **DTE-based Roll Rule**. When trading close to expiry (e.g. within 2 hours of market close on Thursday), the engine should roll entries to the next weekly cycle (`NEXT_WEEKLY`) to mitigate extreme gamma risk and zero-premium decay.
