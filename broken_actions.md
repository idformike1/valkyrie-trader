# Log of Broken Actions & System Bugs

This document details the functional failures, missing features, and critical crashes discovered during the reality verification phase of the Valkyrie Trading Terminal audit.

---

## 1. Critical Execution Failures

### 1.1 Manual Order Ticket (Buy / Sell Buttons)
* **Expected Behavior**: Clicking BUY or SELL on the order ticket submits the trade details to the backend API (`/manual/buy` or `/manual/sell`), logs an execution event, and updates the position ledger.
* **Actual Behavior**: The UI throws a red alert/console warning: `"Trading Desk stream is not connected. Connect first."` The backend logs a `400 Bad Request` with response `{"error": "Trading Desk stream is not connected"}` because the underlying broker live data connection is disconnected.
* **Impact**: **HIGH**. Prevents any manual trading desk operations.

### 1.2 Backtest Workspace Initialization (Next.js Application Crash)
* **Expected Behavior**: Clicking the Backtest workspace loads the strategy repository, configures the chart canvas, and displays strategy parameter sliders.
* **Actual Behavior**: The workspace immediately crashes the Next.js React tree with a fatal error:
  `Assertion failed: data must be asc ordered by time, index=1, time=NaN, prev time=NaN`
* **Impact**: **CRITICAL**. Locks the user out of the Backtest panel completely.
* **Root Cause**: The default date range in the strategy parameter definition is truncated to `"2026-01-01 to 2026-0"`. The parsing of `"2026-0"` returns `NaN`, violating the `lightweight-charts` ascending check.

### 1.3 Global Workspace Navigation Lockout
* **Expected Behavior**: Clicking the sidebar links (Paper Trading, Scalper, Deployments, Operations) changes active panels.
* **Actual Behavior**: The application is a Single Page Application (SPA). Once the Backtest workspace has been visited once, the active router state persists the crash. Subsequent workspace switching attempts or refreshes re-trigger the Backtest's background layout rendering, crash the React thread, and show the Turbopack dev error overlay.
* **Impact**: **CRITICAL**. Renders the entire application unresponsive until `localStorage` is cleared or the DEV HUD is used to perform a full context reset.

---

## 2. Missing Core Integrations & Mocks

### 2.1 Manual Trading GTT Panel
* **Expected Behavior**: Toggling GTT inside the order ticket should display parameters for configuring target points, stop loss values, trigger prices, and active directions.
* **Actual Behavior**: The GTT configuration panels, forms, and triggers are entirely missing from the HTML DOM of the Manual Trading panel.
* **Impact**: **MEDIUM**. The interface has no support for bracket orders or trigger-based automation.

### 2.2 Paper Trading Workspace
* **Expected Behavior**: Clicking "Deploy", "Pause", or "Stop" controls strategy tasks on the FastAPI daemon, running paper execution loops.
* **Actual Behavior**: The buttons update only local React state variables and logs static mock text messages to the screen. No network requests are dispatched.
* **Impact**: **HIGH**. The workspace is an isolated client-side mock dashboard.

### 2.3 Scalper Workspace
* **Expected Behavior**: Clicking BUY MKT or SELL MKT routes order packages to the `/manual/buy` endpoint with a `is_scalper: true` parameter tag. Pressing Shift+B or Shift+S overrides default hotkeys.
* **Actual Behavior**: Clicking buttons or pressing hotkeys updates local simulated positions in state. No backend connections or API network calls are triggered.
* **Impact**: **HIGH**. The scalper cockpit is an isolated client-side mock dashboard.

### 2.4 Deployments Workspace
* **Expected Behavior**: Cluster buttons (Deploy, Pause, Resume, Restart, Stop) perform operational changes on running container orchestration hosts (e.g. Docker, Kubernetes).
* **Actual Behavior**: Clicking buttons logs cosmetic console updates. All cluster nodes and system status metrics are populated from static local mocks.
* **Impact**: **MEDIUM**. The dashboard is entirely mock.
