# Network Ingestion & API Trace: Valkyrie Trading Desktop

This document outlines the actual request payloads, responses, headers, and console errors captured during the reality validation audit of the Valkyrie Frontend and Backend components.

---

## 1. Manual Trading Workspace Transactions

### 1.1 Action: Click "BUY" in Order Pad
* **Request URL**: `http://localhost:8081/manual/buy`
* **Method**: `POST`
* **Headers**:
  ```text
  Accept: application/json, text/plain, */*
  Content-Type: application/json
  Origin: http://localhost:3000
  Referer: http://localhost:3000/
  User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)
  ```
* **Payload**:
  ```json
  {
    "qty": 1,
    "target": 0,
    "target_type": "points",
    "sl": 0,
    "sl_type": "points",
    "trailing_gap": 0,
    "is_scalper": false
  }
  ```
* **Response Status**: `400 Bad Request`
* **Response Payload**:
  ```json
  {
    "error": "Trading Desk stream is not connected"
  }
  ```
* **Browser Console Output**:
  ```text
  [14:12:04] POST http://localhost:8081/manual/buy 400 (Bad Request)
  [14:12:04] Error: Trading Desk stream is not connected
  ```

### 1.2 Action: Click "SELL" in Order Pad
* **Request URL**: `http://localhost:8081/manual/sell`
* **Method**: `POST`
* **Headers**: Identical to 1.1
* **Payload**: Empty or default manual close payload.
* **Response Status**: `400 Bad Request`
* **Response Payload**:
  ```json
  {
    "error": "No active position to exit"
  }
  ```
* **Browser Console Output**:
  ```text
  [14:12:12] POST http://localhost:8081/manual/sell 400 (Bad Request)
  [14:12:12] Error: No active position to exit
  ```

### 1.3 Action: GTT Create & GTT Cancel
* **Trigger**: Click GTT trigger toggles (Not present in UI, but API endpoints checked)
* **API Route**: `/manual/gtt/create` and `/manual/gtt/cancel`
* **Result**: `UNREACHABLE / NOT INTEGRATED` in the client frontend.

---

## 2. Backtest Workspace Transactions

### 2.1 Action: Click "Run Backtest"
* **Request URL**: `http://localhost:8081/start`
* **Method**: `POST`
* **Expected Payload**:
  ```json
  {
    "mode": "BACKTEST",
    "strategy": "five_ema_scalping",
    "index_name": "NIFTY",
    "expiry": "2026-06-04",
    "option_type": "CE",
    "strike": "ATM",
    "start_date": "2026-01-01",
    "end_date": "2026-05",
    "timeframe": "1minute",
    "initial_balance": 1000000,
    "five_ema_period": 5,
    "five_ema_rr": 3
  }
  ```
* **Actual Result**: `BLOCKED` (CORS Missing Headers or Javascript Exception prevents dispatch).
* **Browser Console Console Error**:
  ```text
  Assertion failed: data must be asc ordered by time, index=1, time=NaN, prev time=NaN
      at assert (lightweight-charts.development.mjs:197)
      at checkItemsAreOrdered (lightweight-charts.development.mjs:12667)
      at SeriesApi.setData (lightweight-charts.development.mjs:12811)
      at TradingMain.useEffect (BacktestWorkspace.tsx:343)
  ```
