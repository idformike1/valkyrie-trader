# WebSocket & Live Stream Connection Trace

This document captures the WebSocket connection configurations, telemetry flow sizes, and frame payload samples collected from the live integration endpoints.

---

## 1. System Telemetry Connection

* **WebSocket URL**: `ws://localhost:8081/ws/telemetry`
* **Protocol**: `ws` (non-secure developer mode)
* **Status**: `CONNECTED`
* **Frames Exchanged**:
  * Client sends: *None (Receive-only listener)*
  * Server sends: *System telemetry frame state updates (Every 350-1000ms)*

---

## 2. Decoded Frame Sample

The following payload represents an active telemetry update pushed by the FastAPI strategy daemon over the WebSocket connection:

```json
{
  "status": {
    "state": "IDLE",
    "mode": "NONE",
    "balance": 100000.0,
    "initial_balance": 100000.0,
    "position": null,
    "instrument_key": null,
    "trading_symbol": null,
    "strike": null,
    "expiry": null,
    "option_type": null,
    "exchange": "NSE",
    "index_name": "NIFTY",
    "live_protection": false,
    "is_real_execution": false,
    "lot_size": 1,
    "lot_size_multiplier": 75,
    "spot_price": 0.0,
    "total_pnl": 0.0,
    "return_percent": 0.0,
    "max_drawdown": 0.0,
    "profit_factor": 0.0,
    "total_trades": 0,
    "win_rate": 0.0,
    "chart_interval": "1minute",
    "chart_type": "heikin_ashi",
    "scalper_instrument_key": null,
    "scalper_trading_symbol": null,
    "scalper_lot_multiplier": 75,
    "scalper_option_type": null,
    "scalper_strike": null,
    "scalper_spot_price": 0.0,
    "nifty_spot": 23547.75
  },
  "trades": [],
  "logs": [
    "[18:27:12] [SYSTEM] Halted previous active session 141 on startup.",
    "[18:27:27] [WS] Telemetry WebSocket client connected.",
    "[18:27:30] [WS] Telemetry WebSocket client connected."
  ],
  "candles": [
    {
      "time": 1778137680,
      "open": 3059.8,
      "high": 3059.8,
      "low": 3059.8,
      "close": 3059.8
    }
  ],
  "gtt_orders": [],
  "equity_curve": []
}
```

---

## 3. Frame Diagnostics & Payload Concerns

* **Average Frame Size**: ~180-220 KB (scaled by historical candles array length).
* **Decoupling Impact**: The frontend receives these websocket updates correctly and binds them to `useBackendTradingStore`. However, the order pad execution component enforces its own connection check which does not evaluate the websocket connection status accurately, causing false stream-disconnect warnings.
* **Date Format Mismatch**: The `candles` objects emitted inside the WS frame contain `time` (a Unix timestamp in seconds), but the frontend expects a `timestamp` string property, causing it to evaluate as `NaN` and crash the Lightweight Chart component.
