# Backtest Workspace Crash Fix Verification Report

This report documents the resolution and verification of the fatal `lightweight-charts` time assertion crash that locked the Valkyrie Trading Desktop application.

---

## 1. Summary of Changes

To align the client-side chart mapping with the FastAPI backend telemetry structures, we modified the candle mapping logic and sanitized the equity curve/drawdown datasets in `BacktestWorkspace.tsx`.

### 1.1 Candle Mapping Refactoring
We replaced the date parsing mechanism that was looking for a non-existent `c.timestamp` property, replacing it with the numeric `c.time` property provided by the backend:

```diff
-      const priceData = candles
-        .map((c) => ({
-          // Convert ISO timestamp string to UNIX seconds (integer) for lightweight‑charts
-          time: Math.floor(new Date(c.timestamp).getTime() / 1000) as UTCTimestamp,
-          open: c.open,
-          high: c.high,
-          low: c.low,
-          close: c.close,
-        }))
-        .sort((a, b) => a.time - b.time);
+      const priceData = candles
+        .map((c) => ({
+          time: c.time as UTCTimestamp,
+          open: c.open,
+          high: c.high,
+          low: c.low,
+          close: c.close,
+        }))
+        .sort((a, b) => a.time - b.time);
```

### 1.2 Equity Curve & Drawdown Ordering Fixes
To prevent the charts library from throwing out-of-order assertions (`prev time >= time`) caused by the backend's session creation timestamp (`datetime.now()`) being in the future compared to backdated backtest trade timestamps, we integrated a time adjustment utility before invoking `setData()`:

```typescript
    const rawPoints = equityCurve.map((pt) => ({
      time: Math.floor(new Date(pt.timestamp).getTime() / 1000) as UTCTimestamp,
      value: pt.equity,
    }));

    if (rawPoints.length > 1) {
      const firstTradeTime = rawPoints[1].time;
      if (rawPoints[0].time > firstTradeTime) {
        // Adjust session creation start balance point to be 60 seconds before first trade
        rawPoints[0].time = (firstTradeTime - 60) as UTCTimestamp;
      }
    }
    const points = rawPoints.sort((a, b) => a.time - b.time);
    series.setData(points);
```

---

## 2. Verification Outcomes

During browser testing (recorded in [full_backtest_verification_1780065413604.webp](file:///Users/rajumaharjan/.gemini/antigravity/brain/437d7eed-9832-45bb-b88e-3abfe0461b7e/full_backtest_verification_1780065413604.webp)), the following behaviors were observed and verified:

1.  **No NaN Values**: All candle and equity data items mapped correctly. Consoles are completely free of `NaN` warnings.
2.  **Candles Render**: The main chart successfully instantiates on load, renders OHLC green and red candles, and plots indicator overlays.
3.  **Equity Curve Renders**: The bottom `Equity Curve` tab successfully constructs a line series depicting equity trends.
4.  **Drawdown Renders**: The bottom `Drawdown` tab renders an area series showing peak-to-trough drawdowns.
5.  **Strategy Switching**: Swapping strategies (e.g. from Bollinger Mean Reversion to Heikin Ashi GAR) successfully updates parameters and updates chart references dynamically.
6.  **No Runtime Crashes**: Transitioning tabs, updating sliders, and reloading does not trigger any Next.js runtime crash overlays.
