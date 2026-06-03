# Valkyrie V2 Real-Time Paper Trading Engine Architecture Report
**Prepared by:** Principal Trading Systems Architect & Quant Infrastructure Engineer  
**Status:** Approved for Implementation (Phase P1.1)

---

## 1. Minimal Execution Interfaces Audit

To run the existing validated V2 strategy engine in real time without visual regressions or modifications to historical modules, we forensically audited the core V2 abstractions:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CORE BACKTEST MODULES                           │
├─────────────────────────┬──────────────────────────────────────────────┤
│ Component               │ Minimal Interface required for Real-Time     │
├─────────────────────────┼──────────────────────────────────────────────┤
│ HistoricalReplayEngine  │ • Time-series candle aggregator / loop.      │
│                         │ • Strike / Expiry calendar resolvers.        │
│                         │ • Day-boundary premium lookup.               │
├─────────────────────────┼──────────────────────────────────────────────┤
│ SignalAdapter           │ • evaluate(candles: List[Dict]) -> str.      │
│                         │ • Expects chronological list to compute EMAs.│
├─────────────────────────┼──────────────────────────────────────────────┤
│ PositionManager         │ • open_position(data: Dict, ts: datetime).   │
│                         │ • hold_position(data: Dict, ts: datetime).   │
│                         │ • close_position(data: Dict, ts: datetime).  │
├─────────────────────────┼──────────────────────────────────────────────┤
│ PnLEngine               │ • account_trade(position: Position)          │
│                         │   -> TradeAccountingResult.                  │
└─────────────────────────┴──────────────────────────────────────────────┘
```

### Decoupling Plan
1. **HistoricalReplayEngine:** We must **NOT** reuse or modify `HistoricalReplayEngine` because it is intrinsically coupled to reading historical DB ranges and walking offline index loops. Instead, we extract its static helper methods (resolving short names, resampling candles) and its sequence of contract resolution into an asynchronous, event-driven runner: **`RealtimeSignalRunner`**.
2. **SignalAdapter:** Perfectly decoupled. It expects an in-memory chronological sequence of candles. The `RealtimeSignalRunner` will maintain a rolling window buffer of completed candles, feeding them directly to `SignalAdapter.evaluate(buffer)`.
3. **PositionManager / PositionLedger / PnLEngine:** Fully compatible. These run entirely on structured dictionary shapes and mutable models (`Position`, `TradeAccountingResult`). By feeding them live resolved transaction shapes instantly, we achieve 100% logic parity.

---

## 2. Conceptual System Architecture & Data Flow

The Real-Time V2 Paper Engine follows a strict unidirectional, single-threaded execution flow for each index runner, preventing timing races and state divergence:

```
[Realtime Spot Candle Feed]
             │
             ▼
┌───────────────────────────┐
│   RealtimeSignalRunner    │
│                           │
│   1. Risk Exit Evaluator  │ ──(If holding position)──> [Exit Signal Triggered]
│   2. Candle Buffer Update     │                                      │
│   3. Strategy Evaluator       │                                      │
└────────────┬──────────────┘                                      │
             │ (If BUY/SELL Signal Generated)                        │
             ▼                                                     │
┌───────────────────────────┐                                      │
│   PaperExecutionAdapter   │ <────────────────────────────────────┘
│                           │
│   1. Resolve Strike/Expiry│
│   2. Lookup/Derive Premium│
│   3. Fill instantly       │
└────────────┬──────────────┘
             │ (Dispatches intent)
             ▼
┌───────────────────────────┐
│      PositionManager      │ ──> Modifies ──> [PositionLedger]
└────────────┬──────────────┘
             │ (On Position Close)
             ▼
┌───────────────────────────┐
│         PnLEngine         │ ──> Generates ──> [TradeAccountingResult]
└────────────┬──────────────┘
             │
             ▼
┌───────────────────────────┐
│     TelemetryLogger       │ ──> Emits ──> [SYSTEM, SIGNAL, POSITION, PNL, METRICS]
└───────────────────────────┘
```

---

## 3. Detailed Component Specifications

### A. `RealtimeSignalRunner` (`v2/realtime_signal_runner.py`)
Responsible for managing real-time candle state buffers, running strategy loops, evaluating dynamic risk parameters, and routing signals.
* **Attributes:**
  - `config: BacktestConfig` (Initializes parameters, lot multipliers, risk thresholds)
  - `position_manager: PositionManager` (Coordinates state mutations)
  - `adapter: SignalAdapter` (Evaluates mathematical indicators)
  - `candle_buffer: List[Dict]` (Chronological list of completed spot candles)
  - `active_contract: Optional[Dict]` (Maintains active trade parameters for risk exits)
* **Execution Loop (`on_candle(candle: Dict)`):**
  1. **Risk Evaluation:** If a position is active:
     - Check intraday cutoff (`15:15` or config).
     - Check holding candle count limit.
     - Evaluate dynamic risk bounds (Target/Stop-loss/Trailing SL) utilizing `RiskEngine`.
     - If triggered, dispatch a `SELL_INTENT` event directly to `PaperExecutionAdapter`.
  2. **Buffer Appending:** Append the completed spot candle to `candle_buffer`.
  3. **Signal Generation:** Evaluate indicators: `signal, info = self.adapter.evaluate(self.candle_buffer)`.
  4. **Order Routing:** If `signal` is `BUY` (and flat) or `SELL` (and long), invoke the `PaperExecutionAdapter`.

---

### B. `PaperExecutionAdapter` (`v2/paper_execution_adapter.py`)
Bridges strategy decisions to the transactional execution engine. It fills paper orders instantly at the current option premium.
* **Responsibilities:**
  1. **Strike & Expiry Resolution:** Resolves target option descriptors using `HistoricalStrikeResolver` and `HistoricalExpiryResolver`.
  2. **Option Key Resolution:** Generates standard instrument keys using `HistoricalContractResolver`.
  3. **High-Fidelity Premium Estimation:** 
     - First, attempts to lookup true option premiums from historical database loaders (`OptionHistoricalLoader`) using the candle timestamp (allowing exact backtest-to-real-time verification).
     - If historical data is missing or if synthetic real-time candles are fed, it utilizes an analytical derived option premium model (Black-Scholes approximation or dynamic ATM delta-multiplier) based on the spot price and strike difference.
  4. **Instant Filling:** Forms transactional dicts and invokes `PositionManager.open_position` or `PositionManager.close_position`.
  5. **V2 Accounting Integration:** Ensures closed transactions invoke `PnLEngine` to calculate transaction costs (brokerage, STT, Exchange transaction charges, GST) and appends `TradeAccountingResult`.

---

## 4. Telemetry Log Mapping

To maintain full compatibility with the existing UI Runtime logs, the engine will dispatch structured logs through `TelemetryLogger.log` under five dedicated categories:

1. **`SYSTEM`:** Runtime setup, data buffering, and engine heartbeats.
   * *Example:* `TelemetryLogger.log("SYSTEM", "INFO", "V2 Paper Engine successfully initialized for NIFTY.")`
2. **`SIGNAL`:** Strategy crossover and risk indicators.
   * *Example:* `TelemetryLogger.log("SIGNAL", "INFO", "BUY crossover signal generated at Spot 22350.0.")`
3. **`POSITION`:** Instant fill completions.
   * *Example:* `TelemetryLogger.log("POSITION", "INFO", "Position opened: NIFTY 22350.0 CE | Qty: 75 | Entry Premium: 120.50")`
4. **`PNL`:** Transaction accounting updates.
   * *Example:* `TelemetryLogger.log("PNL", "INFO", "PnL Calculated: Gross +1500.00 | Charges 43.20 | Net +1456.80")`
5. **`METRICS`:** Overall session summary scoring.
   * *Example:* `TelemetryLogger.log("METRICS", "INFO", "Session completed. Profit Factor: 1.45 | Win Rate: 60%")`

---

## 5. Architectural Parity & Reuse Matrix

This audit confirms that we can **reuse 100% of the core analytical and math logic** from Valkyrie V2 without duplicating code or creating parallel maintenance layers:

| V2 Backtest Component | Real-Time Paper Reuse Mode | Modification Required |
| :--- | :--- | :---: |
| **`SignalAdapter`** | Consumes live rolling candle buffer. | **None** |
| **`PositionManager`** | Coordinates real-time state machine transitions. | **None** |
| **`PositionLedger`** | Maintains active ledger and transaction states. | **None** |
| **`PnLEngine`** | Accounts real-time trade costs and PnLs. | **None** |
| **`UpstoxCostModel`** | Calculates broker taxes and charges. | **None** |
| **`MetricsEngine`** | Renders dynamic scorecard and performance indicators. | **None** |
| **`Strategy Registry`**| Validates parameters and builds pipelines. | **None** |

---

## 6. Verification and Integration Testing Strategy

We will build a high-fidelity integration test `v2/test_realtime_paper_engine.py` that verifies the entire pipeline:
1. Initialize the `RealtimeSignalRunner` with a 5 EMA Scalping configuration.
2. Feed a series of completed synthetic spot candles designed to simulate a bullish crossover (inducing a `BUY` signal) followed by a bearish crossover or target hit (inducing a `SELL` signal).
3. Assert that:
   - Signals are generated dynamically.
   - Position transitions from FLAT to LONG (updating ledger events).
   - Position transitions from LONG to CLOSED.
   - PnLEngine successfully creates accounting results.
   - `TelemetryLogger` records all events in the correct schema.
   - `MetricsEngine` generates a final session scorecard.
