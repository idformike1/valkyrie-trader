# Valkyrie Backtest Workspace Audit

An audit of the frontend file `frontend/src/workspaces/BacktestWorkspace.tsx` was conducted to map active functionality, identify mock features, and isolate areas requiring integration with the V2 backend engine.

---

## 1. Component Classifications

### A. Working Components (Connected or Active)
- **`BacktestLeft` (Strategy Repository List)**: Properly renders the sidebar list of available strategies, filtering by status (All, Validated, Testing, Draft), and triggering selecting states.
- **TV Lightweight Chart Rendering**: Renders raw candlestick data from `useBackendTradingStore.getState().candles` and maps executions using `useBackendTradingStore.getState().trades`.
- **Date Range and Capital Inputs**: Control inputs for editing range text (`2026-01-01 to 2026-05-28`) and capital (`1000000`) are fully interactive.
- **Commission Model dropdown**: Visual drop-down element for select controls.

### B. Mock Components (Fake Data generators or Static definitions)
- **`AVAILABLE_STRATEGIES` array**: Hardcoded mockup metadata including parameter definitions (default values, ranges) for strategies like `heikin_ashi_gar`, `five_ema_scalping`, `str_ema`, `str_mean`, `str_vwap`, and `str_macd`.
- **Commission / Slippage choices**: Static dropdown options ("Percentage 0.03%", "Fixed Flat", "Zero Slippage Model") not hooked to backend execution config.
- **V1 execution routing**: Clicking `Run Backtest` fires the legacy V1 API endpoints (mapping inputs to `five_ema_scalping` and sending requests to V1).

### C. Broken / Incomplete Components
- **`Optimize` button**: Renders but has no click action linked to optimization routines.
- **No Optimization panel/tab**: The UI completely lacks visual widgets for:
  - Inputting parameter ranges (Fast / Slow EMA min, max, step).
  - Configuring parallel worker counts.
  - Viewing Ranked results tables (Top 10, Top 25, Top 50).
  - Viewing Heatmap visualizations.
  - Using a Parameter Inspector to reload charts for specific cells.
- **`Overview` tab metrics**: Bound to the legacy V1 `status` fields.
- **`Metrics` tab details**: Displays only Sharpe, Max Drawdown, Total Trades, and Win Rate, using V1 fields.

### D. Unused Components
- **`SlidersHorizontal` / Lucide icons**: Imported but not actively used or wired up in the control bars.

---

## 2. Integration Action Plan

To fully integrate the validated V2 backend engine:
1. **Extend `useBackendTradingStore`**: Add states/actions for optimization runs, reports, and parameter selections.
2. **Build V2 REST Endpoints**: Implement FastAPI handlers for running backtests/optimizations, fetching results, and accessing ledger/equity curves.
3. **Refactor `BacktestWorkspace.tsx`**:
   - Create input fields for optimization parameters.
   - Implement the ranked parameter lists, interactive heatmaps, and cell inspectors.
   - Replace V1 telemetry data mapping with clean V2 model properties.
