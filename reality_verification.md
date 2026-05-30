# Reality Verification Audit: Valkyrie Trading Desktop

This document outlines the observed reality of the Valkyrie Trading Desktop application (`http://localhost:3000`) and the FastAPI backend daemon (`http://localhost:8081`) as verified during hands-on interaction and network tracking.

---

## 1. Executive Summary of Reality

The Valkyrie Trading Terminal has critical functional issues that prevent basic operations. While the shell navigation layout looks premium, the underlying backend endpoints, stream states, and charting libraries suffer from fatal bugs:
1.  **Manual Trading is Broken**: The execution panel throws HTTP `400 Bad Request` errors because the underlying broker market data feed stream is disconnected.
2.  **Backtest Workspace is Fatal**: Navigating to the Backtest panel triggers a fatal React tree crash inside the `lightweight-charts` rendering logic. The backend transmits historical candles with a `time` integer but no `timestamp` string. The frontend tries to parse `timestamp`, resulting in `NaN` values, violating the library's ascending numeric order check and triggering a Next.js crash overlay.
3.  **Entire SPA Locked Out**: Because workspace states are globally cached and re-rendered, once the Backtest tab is touched (or loaded as persistent default), the Next.js React engine crashes. This locks the user out of the rest of the application (Scalper, Paper Trading, Deployments, Operations) until the developer HUD context is manually reset or `localStorage` is wiped.

---

## 2. Workspace Action Classification Matrix

Each workspace control has been tested and classified under one of the five required states:
*   **WORKING**: Performs its expected business logic and updates system state.
*   **PARTIAL**: Works under specific conditions but has clear errors or missing links.
*   **BROKEN**: Fails to execute due to code bugs, validation constraints, or server errors.
*   **MOCK**: Responds client-side (logs console logs, updates local UI) but has no real backend execution.
*   **UNREACHABLE**: Cannot be clicked or verified because the parent view crashes or UI elements are missing.

### 2.1 Manual Trading Workspace
| Action / Control | Classification | Observed Reality & Verification Comments |
| :--- | :--- | :--- |
| **Buy** | **BROKEN** | Clicking BUY sends a `POST` request to `/manual/buy` which returns a `400 Bad Request` with response `{"error": "Trading Desk stream is not connected"}`. |
| **Sell** | **BROKEN** | Clicking SELL sends a `POST` request to `/manual/sell`. Since no position can be opened, it returns a `400 Bad Request` with response `{"error": "No active position to exit"}`. |
| **Panic Exit** | **UNREACHABLE** | This button is conditionally rendered and only displays when there is an active open position. Because buying is broken, the button cannot be rendered. |
| **GTT Create** | **BROKEN** | The UI components for GTT parameters and order creation are completely missing from the Manual Trading execution panel. |
| **GTT Cancel** | **UNREACHABLE** | Cannot create a GTT order, hence cannot cancel one. No cancel controls exist in the UI. |

### 2.2 Backtest Workspace
| Action / Control | Classification | Observed Reality & Verification Comments |
| :--- | :--- | :--- |
| **Run Backtest** | **BROKEN** | Clicking the button triggers the chart reload loop. The input date range is truncated in the UI to `"2026-01-01 to 2026-0"`. When parsed, it returns `NaN`, crashing the lightweight-charts engine instantly. |
| **Parameter Changes** | **UNREACHABLE** | Sliders cannot be manipulated because the panel crashes the React render tree on mount. |
| **Strategy Switching** | **UNREACHABLE** | Selecting a different strategy is blocked by the immediate application crash. |
| **Metrics Rendering** | **UNREACHABLE** | Blocked by the immediate application crash. |

### 2.3 Paper Trading Workspace
| Action / Control | Classification | Observed Reality & Verification Comments |
| :--- | :--- | :--- |
| **Deploy** | **MOCK** | If accessed prior to Backtest crash (by clearing local storage), clicking Deploy changes the local state indicator to `Running` and logs an event, but initiates no real-time backend execution. |
| **Pause** | **MOCK** | Suspends the local simulated state check loop and updates UI text. |
| **Stop** | **MOCK** | Resets the strategy deployment state back to idle. |
| **Telemetry Updates** | **MOCK** | The dials (PnL, Win Rate, Max Drawdown) display static, client-side hardcoded values that do not pull live telemetry data from `/telemetry`. |

### 2.4 Scalper Workspace
| Action / Control | Classification | Observed Reality & Verification Comments |
| :--- | :--- | :--- |
| **Buy MKT** | **MOCK** | Initiates a local simulated position in React state. Does not send API requests to `/manual/buy`. |
| **Sell MKT** | **MOCK** | Closes simulated positions or opens short positions client-side. |
| **Reverse** | **MOCK** | Reverses the local trade direction in state (e.g. from LONG to SHORT) and updates simulated profit calculations. |
| **Flatten** | **MOCK** | Instantly sets the local position to FLAT and writes a log entry to the events console. |
| **Panic Exit** | **MOCK** | Behaves identically to Flatten. |
| **Hotkeys** | **MOCK** | Keypress listeners for `Shift+B` and `Shift+S` increment the client-side simulated lot counts but trigger no network transactions. |

### 2.5 Deployments Workspace
| Action / Control | Classification | Observed Reality & Verification Comments |
| :--- | :--- | :--- |
| **Deploy Node** | **MOCK** | Logs a deployment initialization message in the console but triggers no container actions. |
| **Pause Node** | **MOCK** | Updates cluster grid status icon to paused. |
| **Restart Node** | **MOCK** | Simulates a container reboot status timer. |
| **Stop Node** | **MOCK** | Changes cluster node status to stopped. |

### 2.6 Operations Workspace
| Action / Control | Classification | Observed Reality & Verification Comments |
| :--- | :--- | :--- |
| **Log Filters** | **WORKING** | Correctly filters logs in the event stream table by INFO, WARN, and ERROR severities. |
| **Search Input** | **WORKING** | Filters log messages by query text. |
| **Observability Switches** | **MOCK** | Toggles cosmetic indicators in the sidebar panel. |
