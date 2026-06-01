"use client";

import React, { useState, useEffect, useRef } from "react";
import { createChart, IChartApi, ISeriesApi, UTCTimestamp, CandlestickSeries, HistogramSeries, LineSeries } from "lightweight-charts";
import { 
  Play, Activity, Terminal, Shield, Cpu, RefreshCw, BarChart2,
  TrendingUp, Layers, Server, Settings, Zap, ArrowUpRight, ArrowDownRight,
  Sliders, Search, Plus, Trash2, SlidersHorizontal, Lock, CheckCircle2, 
  AlertTriangle, Star, Check, X, Maximize2, Minimize2, ZoomIn, ZoomOut
} from "lucide-react";
import { useTerminalStore, Instrument, Timeframe } from "@/store/useTerminalStore";
import { useBackendTradingStore } from "@/services/tradingQueries";
import { useEventStore } from "@/store/useEventStore";
import { tradingApi } from "@/services/tradingApi";

// Helper components for professional aesthetics
const GlowingCard: React.FC<{ title: string; children: React.ReactNode; className?: string }> = ({ title, children, className = "" }) => (
  <div className={`p-3 flex flex-col h-full bg-slate-950/40 border border-white/5 rounded-lg hover:border-cyan-500/10 transition-all ${className}`}>
    <h3 className="text-[10px] font-bold tracking-widest text-cyan-400 uppercase border-b border-white/5 pb-1.5 mb-2.5 flex items-center justify-between">
      <span>{title}</span>
      <span className="w-1 h-1 rounded-full bg-cyan-400 animate-pulse" />
    </h3>
    <div className="flex-1 overflow-y-auto min-h-0">{children}</div>
  </div>
);

// MOCK INSTRUMENT DATA FOR WATCHLIST
const AVAILABLE_INSTRUMENTS: Instrument[] = [
  { instrumentKey: "NSE_INDEX|Nifty 50", symbol: "NIFTY 50", exchange: "NSE" },
  { instrumentKey: "NSE_INDEX|Nifty Bank", symbol: "BANKNIFTY", exchange: "NSE" },
  { instrumentKey: "NSE_EQ|INE002A01018", symbol: "RELIANCE", exchange: "NSE" },
  { instrumentKey: "NSE_EQ|INE467B01029", symbol: "TCS", exchange: "NSE" },
  { instrumentKey: "NSE_EQ|INE009A01021", symbol: "INFOSYS", exchange: "NSE" },
];

// ==========================================
// 1. LEFT PANEL: WATCHLIST
// ==========================================
const MASTER_INSTRUMENTS: Instrument[] = [
  { instrumentKey: "NSE_INDEX|Nifty 50", symbol: "NIFTY 50", exchange: "NSE" },
  { instrumentKey: "NSE_INDEX|Nifty Bank", symbol: "BANKNIFTY", exchange: "NSE" },
  { instrumentKey: "NSE_INDEX|Nifty Fin Service", symbol: "FINNIFTY", exchange: "NSE" },
  { instrumentKey: "NSE_INDEX|NIFTY MID SELECT", symbol: "MIDCPNIFTY", exchange: "NSE" },
  { instrumentKey: "BSE_INDEX|SENSEX", symbol: "SENSEX", exchange: "BSE" },
  { instrumentKey: "BSE_INDEX|BANKEX", symbol: "BANKEX", exchange: "BSE" },
  { instrumentKey: "NSE_EQ|INE002A01018", symbol: "RELIANCE", exchange: "NSE" },
  { instrumentKey: "NSE_EQ|INE467B01029", symbol: "TCS", exchange: "NSE" },
  { instrumentKey: "NSE_EQ|INE009A01021", symbol: "INFY", exchange: "NSE" },
  { instrumentKey: "NSE_EQ|INE040A01034", symbol: "HDFCBANK", exchange: "NSE" },
  { instrumentKey: "NSE_EQ|INE090A01021", symbol: "ICICIBANK", exchange: "NSE" },
  { instrumentKey: "NSE_EQ|INE062A01020", symbol: "SBIN", exchange: "NSE" },
  { instrumentKey: "NSE_EQ|INE397D01024", symbol: "BHARTIARTL", exchange: "NSE" },
  { instrumentKey: "NSE_EQ|INE154A01025", symbol: "ITC", exchange: "NSE" },
  { instrumentKey: "NSE_EQ|INE018A01030", symbol: "LT", exchange: "NSE" },
  { instrumentKey: "NSE_EQ|INE237A01028", symbol: "KOTAKBANK", exchange: "NSE" }
];

export const TradingLeft: React.FC = () => {
  const currentInstrument = useTerminalStore((state) => state.selectedInstrument);
  const setInstrument = useTerminalStore((state) => state.setInstrument);
  
  const [watchlist, setWatchlist] = useState<Instrument[]>([]);
  const [search, setSearch] = useState("");
  const [showSearchResults, setShowSearchResults] = useState(false);
  const [pinned, setPinned] = useState<string[]>(["NIFTY 50", "BANKNIFTY"]);

  const connectionStatus = useBackendTradingStore((state) => state.connectionStatus);
  const connectTelemetry = useBackendTradingStore((state) => state.connectTelemetry);
  
  const [prices, setPrices] = useState<Record<string, { ltp: number; change: string; up: boolean; timestamp?: string }>>({});

  // Initialize and persist watchlist in local storage
  useEffect(() => {
    const saved = localStorage.getItem("valkyrie_watchlist");
    if (saved) {
      try {
        setWatchlist(JSON.parse(saved));
      } catch (e) {
        setWatchlist(AVAILABLE_INSTRUMENTS);
      }
    } else {
      setWatchlist(AVAILABLE_INSTRUMENTS);
    }
  }, []);

  const saveWatchlist = (list: Instrument[]) => {
    setWatchlist(list);
    localStorage.setItem("valkyrie_watchlist", JSON.stringify(list));
  };

  const fetchWatchlistQuotes = async () => {
    if (watchlist.length === 0) return;
    try {
      const keys = watchlist.map((ins) => ins.instrumentKey).join(",");
      const res = await tradingApi.getBrokerQuotes(keys);
      if (res.status === "success" && res.data) {
        const newPrices: Record<string, { ltp: number; change: string; up: boolean; timestamp?: string }> = {};
        
        watchlist.forEach((ins) => {
          const k1 = ins.instrumentKey;
          const k2 = k1.replace("|", ":");
          let q = res.data[k1] || res.data[k2];
          if (!q) {
            q = Object.values(res.data).find(
              (val: any) => val.instrument_token === k1 || val.instrument_token === k2
            );
          }
          
          if (q) {
            const ltp = Number(q.last_price || 0);
            const close = Number(q.ohlc?.close || ltp);
            const diff = ltp - close;
            const pct = close > 0 ? (diff / close) * 100 : 0;
            
            newPrices[ins.symbol] = {
              ltp: ltp,
              change: `${diff >= 0 ? "+" : ""}${pct.toFixed(2)}%`,
              up: diff >= 0,
              timestamp: q.timestamp 
                ? new Date(Number(q.timestamp)).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" }) + " IST"
                : new Date().toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" }) + " IST",
            };
          }
        });
        
        setPrices((prev) => ({
          ...prev,
          ...newPrices,
        }));
      }
    } catch (err) {
      console.error("Failed to fetch watchlist quotes:", err);
    }
  };

  useEffect(() => {
    connectTelemetry();
  }, [connectTelemetry]);

  useEffect(() => {
    fetchWatchlistQuotes();
    const interval = setInterval(fetchWatchlistQuotes, 5000);
    return () => clearInterval(interval);
  }, [watchlist]);

  const togglePin = (sym: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setPinned((prev) =>
      prev.includes(sym) ? prev.filter((s) => s !== sym) : [...prev, sym]
    );
  };

  const handleAddSymbol = (ins: Instrument) => {
    if (watchlist.some((w) => w.symbol === ins.symbol)) {
      setSearch("");
      setShowSearchResults(false);
      return;
    }
    const updated = [...watchlist, ins];
    saveWatchlist(updated);
    setSearch("");
    setShowSearchResults(false);
  };

  const handleDeleteSymbol = (symbol: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updated = watchlist.filter((w) => w.symbol !== symbol);
    saveWatchlist(updated);
  };

  const handleMoveUp = (index: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (index === 0) return;
    const updated = [...watchlist];
    const temp = updated[index];
    updated[index] = updated[index - 1];
    updated[index - 1] = temp;
    saveWatchlist(updated);
  };

  const handleMoveDown = (index: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (index === watchlist.length - 1) return;
    const updated = [...watchlist];
    const temp = updated[index];
    updated[index] = updated[index + 1];
    updated[index + 1] = temp;
    saveWatchlist(updated);
  };

  const filteredWatchlist = watchlist.filter((ins) =>
    ins.symbol.toLowerCase().includes(search.toLowerCase())
  );

  const searchResults = search
    ? MASTER_INSTRUMENTS.filter(
        (m) =>
          m.symbol.toLowerCase().includes(search.toLowerCase()) &&
          !watchlist.some((w) => w.symbol === m.symbol)
      )
    : [];

  const connectionDotColor = 
    connectionStatus === "CONNECTED" ? "bg-emerald-500 shadow-emerald-500/20" :
    connectionStatus === "CONNECTING" ? "bg-amber-500 animate-pulse shadow-amber-500/20" :
    "bg-rose-500 shadow-rose-500/20";

  return (
    <div className="flex flex-col h-full bg-slate-950/40 border border-white/5 rounded-lg p-3 hover:border-cyan-500/10 transition-all select-none">
      <h3 className="text-[10px] font-bold tracking-widest text-cyan-400 uppercase border-b border-white/5 pb-1.5 mb-2.5 flex items-center justify-between select-none">
        <span>Watchlist</span>
        <div className="flex items-center gap-1.5">
          <span className="text-[8px] text-slate-500 font-mono font-medium lowercase">{connectionStatus}</span>
          <span className={`w-1.5 h-1.5 rounded-full ${connectionDotColor} shadow-md`} />
        </div>
      </h3>
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="flex flex-col gap-2 h-full">
          {/* Search bar */}
          <div className="relative shrink-0">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setShowSearchResults(true);
              }}
              onFocus={() => setShowSearchResults(true)}
              placeholder="Search / Add Stock Options..."
              className="w-full bg-slate-900/60 border border-white/5 rounded pl-8 pr-3 py-1.5 text-[11px] text-slate-300 focus:outline-none focus:border-cyan-500/40 font-sans"
            />
            {/* Search results popup */}
            {showSearchResults && searchResults.length > 0 && (
              <div className="absolute left-0 right-0 mt-1 bg-slate-950 border border-white/10 rounded shadow-xl max-h-48 overflow-y-auto z-50 font-sans text-xs">
                {searchResults.map((item) => (
                  <div
                    key={item.instrumentKey}
                    onClick={() => handleAddSymbol(item)}
                    className="flex justify-between items-center px-3 py-2 hover:bg-cyan-500/10 cursor-pointer transition-colors text-slate-200 border-b border-white/[0.02]"
                  >
                    <span>{item.symbol}</span>
                    <span className="text-[9px] text-cyan-400 font-mono bg-cyan-950/40 px-1 py-0.5 rounded border border-cyan-500/10 font-bold uppercase">{item.exchange}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Instruments list */}
          <div className="flex-1 overflow-y-auto flex flex-col gap-0.5 mt-1 pr-1 font-sans text-xs scrollbar-thin scrollbar-thumb-white/5 scrollbar-track-transparent">
            {/* Header Row */}
            <div className="grid grid-cols-12 px-2 py-1 text-[9px] font-bold text-slate-500 uppercase tracking-wider select-none shrink-0 border-b border-white/[0.02]">
              <span className="col-span-6">Symbol</span>
              <span className="col-span-3 text-right">LTP</span>
              <span className="col-span-3 text-right">Change</span>
            </div>

            {filteredWatchlist.map((item, index) => {
              const priceInfo = prices[item.symbol] || { ltp: 0, change: "0.00%", up: true, timestamp: "" };
              const isSelected = currentInstrument?.symbol === item.symbol;
              const isPinned = pinned.includes(item.symbol);

              return (
                <div
                  key={item.instrumentKey}
                  onClick={() => setInstrument(item)}
                  className={`grid grid-cols-12 items-center px-2 py-1.5 rounded cursor-pointer border transition-all ${
                    isSelected
                      ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400 font-semibold"
                      : "bg-transparent border-transparent hover:bg-white/5 text-slate-300 hover:text-white"
                  }`}
                >
                  {/* Symbol & Pin indicator */}
                  <div className="col-span-6 flex items-center gap-1.5 min-w-0">
                    <button
                      onClick={(e) => togglePin(item.symbol, e)}
                      className="text-slate-600 hover:text-cyan-400 transition-colors cursor-pointer"
                    >
                      <Star className={`w-3 h-3 ${isPinned ? "fill-cyan-400 text-cyan-400" : ""}`} />
                    </button>
                    
                    {/* Reorder Up/Down buttons */}
                    <div className="flex flex-col text-[7px] text-slate-600 font-mono shrink-0 select-none mr-0.5">
                      <button onClick={(e) => handleMoveUp(index, e)} className="hover:text-cyan-400 cursor-pointer">▲</button>
                      <button onClick={(e) => handleMoveDown(index, e)} className="hover:text-cyan-400 cursor-pointer">▼</button>
                    </div>

                    <div className="flex flex-col min-w-0 flex-1">
                      <span className="truncate uppercase font-medium">{item.symbol}</span>
                      {priceInfo.timestamp && (
                        <span className="text-[7px] text-slate-500 font-mono leading-none mt-0.5">{priceInfo.timestamp}</span>
                      )}
                    </div>
                  </div>

                  {/* LTP */}
                  <span className="col-span-3 text-right font-mono text-[11px]">
                    ₹{priceInfo.ltp.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>

                  {/* Change & Delete */}
                  <div className="col-span-3 flex items-center justify-end gap-1.5 min-w-0">
                    <span
                      className={`text-right font-mono text-[10px] font-semibold ${
                        priceInfo.up ? "text-emerald-400" : "text-rose-400"
                      }`}
                    >
                      {priceInfo.change}
                    </span>
                    <button
                      onClick={(e) => handleDeleteSymbol(item.symbol, e)}
                      className="text-slate-600 hover:text-rose-400 transition-colors cursor-pointer text-xs font-bold font-sans shrink-0 px-0.5 select-none"
                      title="Remove Symbol"
                    >
                      ×
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

// ==========================================
// 2. MAIN PANEL: TRADINGVIEW LIGHTWEIGHT CHART
// ==========================================
export const TradingMain: React.FC = () => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const vwapSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ema9SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ema21SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  const selectedInstrument = useTerminalStore((state) => state.selectedInstrument);
  const selectedTimeframe = useTerminalStore((state) => state.selectedTimeframe);
  const setInstrument = useTerminalStore((state) => state.setInstrument);
  const setTimeframe = useTerminalStore((state) => state.setTimeframe);

  const [activeIndicators, setActiveIndicators] = useState<string[]>([]);
  const [showDrawMenu, setShowDrawMenu] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [currentLtp, setCurrentLtp] = useState<number>(0);
  const [chartLoading, setChartLoading] = useState(false);

  // --- Indicator calculation helpers ---
  const calcVWAP = (candles: any[]) => {
    let cumTPV = 0, cumVol = 0;
    return candles.map((c) => {
      const tp = (c.high + c.low + c.close) / 3;
      const vol = c.volume || 0;
      cumTPV += tp * vol;
      cumVol += vol;
      return { time: c.time as UTCTimestamp, value: cumVol > 0 ? cumTPV / cumVol : c.close };
    });
  };

  const calcEMA = (candles: any[], period: number) => {
    const k = 2 / (period + 1);
    const result: { time: UTCTimestamp; value: number }[] = [];
    let ema = 0;
    candles.forEach((c, i) => {
      if (i < period - 1) { return; }
      if (i === period - 1) {
        ema = candles.slice(0, period).reduce((s, x) => s + x.close, 0) / period;
      } else {
        ema = c.close * k + ema * (1 - k);
      }
      result.push({ time: c.time as UTCTimestamp, value: ema });
    });
    return result;
  };

  // Apply / remove indicator overlays
  const applyIndicators = (candles: any[], indicators: string[]) => {
    if (vwapSeriesRef.current) { chartRef.current?.removeSeries(vwapSeriesRef.current as any); vwapSeriesRef.current = null; }
    if (ema9SeriesRef.current) { chartRef.current?.removeSeries(ema9SeriesRef.current as any); ema9SeriesRef.current = null; }
    if (ema21SeriesRef.current) { chartRef.current?.removeSeries(ema21SeriesRef.current as any); ema21SeriesRef.current = null; }
    if (!chartRef.current || !candles.length) return;
    if (indicators.includes("VWAP")) {
      const s = chartRef.current.addSeries(LineSeries, { color: "rgba(251, 191, 36, 0.9)", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
      s.setData(calcVWAP(candles));
      vwapSeriesRef.current = s as any;
    }
    if (indicators.includes("EMA")) {
      const s9 = chartRef.current.addSeries(LineSeries, { color: "rgba(52, 211, 153, 0.9)", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
      s9.setData(calcEMA(candles, 9));
      ema9SeriesRef.current = s9 as any;
      const s21 = chartRef.current.addSeries(LineSeries, { color: "rgba(251, 113, 133, 0.9)", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
      s21.setData(calcEMA(candles, 21));
      ema21SeriesRef.current = s21 as any;
    }
  };

  // Initialize and update chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Clean up previous instances
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const themeColors = {
      background: "#020617",
      text: "#94a3b8",
      grid: "#1e293b",
      border: "#334155",
      emerald: "#10b981",
      rose: "#ef4444",
    };

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 380,
      layout: {
        background: { color: themeColors.background },
        textColor: themeColors.text,
        fontSize: 10,
        fontFamily: "var(--font-mono, Courier New, monospace)",
      },
      grid: {
        vertLines: { color: themeColors.grid, style: 2 },
        horzLines: { color: themeColors.grid, style: 2 },
      },
      crosshair: {
        mode: 1, // Magnet mode
        vertLine: {
          color: "rgba(6, 182, 212, 0.4)",
          width: 1,
          style: 1,
          labelBackgroundColor: "#06b6d4",
        },
        horzLine: {
          color: "rgba(6, 182, 212, 0.4)",
          width: 1,
          style: 1,
          labelBackgroundColor: "#06b6d4",
        },
      },
      rightPriceScale: {
        borderColor: themeColors.border,
        textColor: themeColors.text,
      },
      timeScale: {
        borderColor: themeColors.border,
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: themeColors.emerald,
      downColor: themeColors.rose,
      borderUpColor: themeColors.emerald,
      borderDownColor: themeColors.rose,
      wickUpColor: themeColors.emerald,
      wickDownColor: themeColors.rose,
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "", // overlay pane
    });
    
    // Position the volume chart at the bottom
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    // Populate data - start clean to avoid fabricated values
    candleSeries.setData([]);
    volumeSeries.setData([]);

    // Fit content
    chart.timeScale().fitContent();

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    // Handle resizing dynamically using ResizeObserver
    const observer = new ResizeObserver((entries) => {
      if (entries[0] && chartRef.current) {
        const { width, height } = entries[0].contentRect;
        chartRef.current.resize(width, Math.max(280, height));
      }
    });
    observer.observe(chartContainerRef.current);

    return () => {
      observer.disconnect();
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [selectedInstrument]);

  const status = useBackendTradingStore((state) => state.status);
  const connectTelemetry = useBackendTradingStore((state) => state.connectTelemetry);

  useEffect(() => {
    connectTelemetry();
  }, [connectTelemetry]);

  // Sync current LTP when backend tick updates spot price
  useEffect(() => {
    if (status && status.spot_price > 0) {
      setCurrentLtp(status.spot_price);
    }
  }, [status]);

  // Ref to store fetched candles for indicator recalculation
  const fetchedCandlesRef = useRef<any[]>([]);

  // Bug #2 fix — fetch real candles from Upstox whenever instrument or timeframe changes
  useEffect(() => {
    if (!selectedInstrument || !candleSeriesRef.current || !volumeSeriesRef.current) return;
    let cancelled = false;
    const load = async () => {
      try {
        const days = ["1m", "3m"].includes(selectedTimeframe) ? 1 : ["5m", "15m"].includes(selectedTimeframe) ? 5 : 30;
        const res = await tradingApi.getBrokerCandles(selectedInstrument.instrumentKey, selectedTimeframe, days);
        if (cancelled) return;
        if (res.status === "success" && res.data?.length) {
          const fmtCandles = res.data.map((c: any) => ({ ...c, time: c.time as UTCTimestamp }));
          fetchedCandlesRef.current = fmtCandles;
          candleSeriesRef.current?.setData(fmtCandles.map((c: any) => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close })));
          volumeSeriesRef.current?.setData(fmtCandles.map((c: any) => ({ time: c.time, value: c.volume, color: c.close >= c.open ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)" })));
          
          // Update LTP from last candle
          const last = fmtCandles[fmtCandles.length - 1];
          if (last?.close > 0) setCurrentLtp(last.close);
          // Reapply active indicators
          applyIndicators(fmtCandles, activeIndicators);
        }
      } catch (e) {
        console.error("Chart candle fetch failed:", e);
      }
    };
    
    setChartLoading(true);
    load().finally(() => {
      if (!cancelled) setChartLoading(false);
    });
    
    const interval = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [selectedInstrument, selectedTimeframe]);

  // Bug #3 & #4 fix — re-apply indicators when toggle changes
  useEffect(() => {
    if (fetchedCandlesRef.current.length > 0) {
      applyIndicators(fetchedCandlesRef.current, activeIndicators);
    }
  }, [activeIndicators]);

  const toggleIndicator = (ind: string) => {
    setActiveIndicators((prev) =>
      prev.includes(ind) ? prev.filter((i) => i !== ind) : [...prev, ind]
    );
  };

  return (
    <div className="flex flex-col h-full bg-slate-950/60 border border-white/5 rounded-lg overflow-hidden">
      {/* Top Toolbar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-slate-900/50 border-b border-white/5 select-none shrink-0 font-sans text-xs">
        <div className="flex items-center gap-2">
          {/* Symbol dropdown selection */}
          <select
            value={selectedInstrument?.symbol || "NIFTY 50"}
            onChange={(e) => {
              const matched = AVAILABLE_INSTRUMENTS.find((i) => i.symbol === e.target.value);
              if (matched) setInstrument(matched);
            }}
            className="bg-slate-900 border border-white/10 rounded px-2 py-0.5 text-cyan-400 font-bold uppercase focus:outline-none"
          >
            {AVAILABLE_INSTRUMENTS.map((ins) => (
              <option key={ins.instrumentKey} value={ins.symbol}>
                {ins.symbol}
              </option>
            ))}
            {selectedInstrument && !AVAILABLE_INSTRUMENTS.some((i) => i.symbol === selectedInstrument.symbol) && (
              <option key={selectedInstrument.instrumentKey} value={selectedInstrument.symbol}>
                {selectedInstrument.symbol}
              </option>
            )}
          </select>

          {/* Timeframe dropdown */}
          <select
            value={selectedTimeframe}
            onChange={(e) => setTimeframe(e.target.value as Timeframe)}
            className="bg-slate-900 border border-white/10 rounded px-2 py-0.5 text-slate-300 focus:outline-none"
          >
            {["1m", "3m", "5m", "15m", "1h", "1d"].map((tf) => (
              <option key={tf} value={tf}>
                {tf}
              </option>
            ))}
          </select>

          <div className="h-4 w-px bg-white/5 mx-1" />

          {/* Indicators Button */}
          <div className="relative">
            <button
              onClick={() => toggleIndicator("VWAP")}
              className={`px-2 py-0.5 rounded border transition-colors cursor-pointer text-[10px] ${
                activeIndicators.includes("VWAP")
                  ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400 font-bold"
                  : "bg-slate-900 border-white/10 text-slate-400 hover:text-slate-200"
              }`}
            >
              VWAP
            </button>
          </div>
          <button
            onClick={() => toggleIndicator("EMA")}
            className={`px-2 py-0.5 rounded border transition-colors cursor-pointer text-[10px] ${
              activeIndicators.includes("EMA")
                ? "bg-amber-500/10 border-amber-500/30 text-amber-400 font-bold"
                : "bg-slate-900 border-white/10 text-slate-400 hover:text-slate-200"
            }`}
          >
            EMA (9/21)
          </button>
        </div>

        <div className="flex items-center gap-2">
          {/* Chart loading indicator */}
          {chartLoading && (
            <span className="flex items-center gap-1 text-[9px] text-cyan-400 font-mono animate-pulse">
              <RefreshCw className="w-2.5 h-2.5 animate-spin" />
              LOADING
            </span>
          )}
          {/* Drawing Tools Toggle */}
          <button 
            onClick={() => setShowDrawMenu(!showDrawMenu)}
            className={`p-1 rounded border transition-colors cursor-pointer ${
              showDrawMenu 
                ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400" 
                : "bg-slate-900 border-white/10 text-slate-400 hover:text-slate-200"
            }`}
            title="Drawing Tools"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Layout Workspace with Chart */}
      <div className="flex-1 min-h-0 relative flex flex-row">
        {/* Drawing Sidebar HUD */}
        {showDrawMenu && (
          <div className="w-9 border-r border-white/5 bg-slate-950/60 flex flex-col items-center py-3 gap-3 shrink-0 select-none">
            {["Trendline", "Fibonacci", "Crosshair", "Eraser"].map((tool, idx) => (
              <button 
                key={idx} 
                className="text-slate-500 hover:text-cyan-400 transition-colors p-1"
                title={tool}
              >
                <Sliders className="w-3.5 h-3.5" />
              </button>
            ))}
          </div>
        )}

        {/* Chart Canvas */}
        <div className="flex-1 h-full min-h-0 relative">
          <div ref={chartContainerRef} className="w-full h-full min-h-0" />
          
          {/* Price overlay indicator */}
          <div className="absolute top-3 left-4 bg-slate-950/80 backdrop-blur border border-white/5 px-2 py-1 rounded text-[10px] font-mono text-slate-300 flex items-center gap-2 shadow-md">
            <span className="font-bold text-slate-400">LTP:</span>
            <span className="text-emerald-400 font-bold">
              ₹{currentLtp.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

const BrokerAccountPanel: React.FC = () => {
  const [profile, setProfile] = useState<any>(null);
  const [funds, setFunds] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastSync, setLastSync] = useState<string>("");
  const [brokerConnected, setBrokerConnected] = useState<boolean>(false);
  const [tokenStatus, setTokenStatus] = useState<string>("UNKNOWN");

  const fetchData = async () => {
    try {
      setLoading(true);
      const profileData = await tradingApi.getBrokerProfile();
      setProfile(profileData.data);
      
      const fundsData = await tradingApi.getBrokerFunds();
      setFunds(fundsData.data);
      
      setError(null);
      setBrokerConnected(true);
      setTokenStatus("VALID");
      setLastSync(new Date().toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" }) + " IST");
    } catch (err: any) {
      setBrokerConnected(false);
      const errMsg = err.message || "Failed to fetch broker data";
      setError(errMsg);

      if (errMsg.includes("401") || errMsg.toLowerCase().includes("unauthorized") || errMsg.toLowerCase().includes("token")) {
        setTokenStatus("EXPIRED");
      } else {
        setTokenStatus("API_ERROR");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // 30s auto-refresh
    return () => clearInterval(interval);
  }, []);

  const formatCurrency = (val: any) => {
    if (val === undefined || val === null) return "₹0.00";
    return `₹${Number(val).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  return (
    <div className="p-3 bg-slate-950/40 border border-white/5 rounded-lg flex flex-col gap-2.5 hover:border-cyan-500/10 transition-all select-none">
      <h3 className="text-[10px] font-bold tracking-widest text-cyan-400 uppercase border-b border-white/5 pb-1.5 flex items-center justify-between">
        <span>BROKER ACCOUNT</span>
        <div className="flex items-center gap-1">
          <span className={`w-1.5 h-1.5 rounded-full ${brokerConnected ? "bg-emerald-400 animate-pulse" : "bg-rose-500 animate-pulse"}`} />
          <span className="text-[8px] font-mono text-slate-500">
            {brokerConnected ? "CONNECTED" : "DISCONNECTED"}
          </span>
        </div>
      </h3>

      <div className="grid grid-cols-2 gap-2 text-[10px] bg-slate-900/20 p-2 rounded border border-white/5 font-sans">
        <div className="flex flex-col gap-0.5">
          <span className="text-[8px] text-slate-500 uppercase tracking-wider">Client Name</span>
          <span className="font-bold text-slate-200 uppercase truncate">
            {profile?.user_name || (loading ? "Loading..." : "N/A")}
          </span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-[8px] text-slate-500 uppercase tracking-wider">Client ID</span>
          <span className="font-bold text-slate-200 font-mono">
            {profile?.user_id || (loading ? "Loading..." : "N/A")}
          </span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-[8px] text-slate-500 uppercase tracking-wider">Broker</span>
          <span className="font-bold text-slate-200 uppercase">
            {profile?.broker || "UPSTOX"}
          </span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-[8px] text-slate-500 uppercase tracking-wider">Token Status</span>
          <span className={`font-bold uppercase ${tokenStatus === "VALID" ? "text-emerald-400" : "text-rose-400 animate-pulse"}`}>
            {tokenStatus}
          </span>
        </div>
      </div>

      {error && (
        <div className="p-2 bg-rose-950/40 border border-rose-500/20 text-rose-400 text-[10px] rounded flex items-center gap-1.5 font-mono">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span className="truncate" title={error}>{error}</span>
        </div>
      )}

      <div className="flex flex-col gap-1.5 font-mono text-[10px]">
        <div className="flex justify-between items-center text-slate-400 py-0.5 border-b border-white/[0.02]">
          <span>Available Margin</span>
          <span className="font-bold text-cyan-400">
            {loading && !funds ? "Syncing..." : formatCurrency(funds?.equity?.available_margin)}
          </span>
        </div>
        <div className="flex justify-between items-center text-slate-400 py-0.5 border-b border-white/[0.02]">
          <span>Used Margin</span>
          <span className="font-bold text-slate-200">
            {loading && !funds ? "Syncing..." : formatCurrency(funds?.equity?.used_margin)}
          </span>
        </div>
        <div className="flex justify-between items-center text-slate-400 py-0.5 border-b border-white/[0.02]">
          <span>Available Funds</span>
          <span className="font-bold text-slate-200">
            {loading && !funds ? "Syncing..." : formatCurrency(funds?.equity?.available_margin)}
          </span>
        </div>
        <div className="flex justify-between items-center text-slate-400 py-0.5 border-b border-white/[0.02]">
          <span>Payin Amount</span>
          <span className="font-bold text-slate-200">
            {loading && !funds ? "Syncing..." : formatCurrency(funds?.equity?.payin_amount)}
          </span>
        </div>
        <div className="flex justify-between items-center text-slate-400 py-0.5 border-b border-white/[0.02]">
          <span>Span Margin</span>
          <span className="font-bold text-slate-200">
            {loading && !funds ? "Syncing..." : formatCurrency(funds?.equity?.span_margin)}
          </span>
        </div>
        <div className="flex justify-between items-center text-slate-400 py-0.5">
          <span>Exposure Margin</span>
          <span className="font-bold text-slate-200">
            {loading && !funds ? "Syncing..." : formatCurrency(funds?.equity?.exposure_margin)}
          </span>
        </div>
      </div>

      <div className="flex justify-between items-center text-[8px] text-slate-500 font-mono border-t border-white/5 pt-1.5 mt-0.5">
        <span>LAST SYNC: {lastSync || "NEVER"}</span>
        <button 
          onClick={fetchData} 
          disabled={loading}
          className="hover:text-cyan-400 transition-colors cursor-pointer flex items-center gap-1 disabled:opacity-50"
        >
          <RefreshCw className={`w-2.5 h-2.5 ${loading ? "animate-spin" : ""}`} />
          <span>FORCE REFRESH</span>
        </button>
      </div>
    </div>
  );
};

// Helper to extract option details from symbol strings
interface OptionDetails {
  expiry?: string;
  strike?: string;
  type?: "CE" | "PE" | "EQ" | "INDEX";
}

const parseInstrument = (symbol: string): OptionDetails => {
  // Regex to match option symbols like:
  // "NIFTY 24850 CE"
  // "NIFTY 29AUG24 24850 CE"
  // "BANKNIFTY 26JUN24 46700 PE"
  const regex = /([A-Z0-9]+)\s+(?:(\d+[A-Z]+\d+|\d{2}\s+[A-Z]{3}\s+\d{2}|\d{2}[A-Z]{3}\d{2})\s+)?(\d+(?:\.\d+)?)\s+(CE|PE)/i;
  const match = symbol.match(regex);
  if (match) {
    return {
      expiry: match[2] || "—",
      strike: match[3],
      type: match[4] as "CE" | "PE",
    };
  }
  
  if (symbol.includes("CE")) {
    return { type: "CE", expiry: "—", strike: "—" };
  }
  if (symbol.includes("PE")) {
    return { type: "PE", expiry: "—", strike: "—" };
  }
  
  if (symbol.includes("50") || symbol.includes("BANK") || symbol.includes("MIDCP") || symbol.includes("FIN")) {
    return { type: "INDEX" };
  }
  
  return { type: "EQ" };
};

// ==========================================
// 3. RIGHT PANEL: ORDER ENTRY & POSITIONS SUMMARY
// ==========================================
export const TradingRight: React.FC = () => {
  const currentInstrument = useTerminalStore((state) => state.selectedInstrument);
  const activeMode = useTerminalStore((state) => state.activeMode);
  const currentAccount = useTerminalStore((state) => state.currentAccount);
  const addEvent = useEventStore((state) => state.addEvent);

  const [lotSize, setLotSize] = useState<number>(1);
  const [quantity, setQuantity] = useState<number>(1);

  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [productType, setProductType] = useState<"MIS" | "NRML" | "CNC">("MIS");
  const [orderType, setOrderType] = useState<"MARKET" | "LIMIT">("MARKET");
  const [limitPrice, setLimitPrice] = useState(0);
  const [triggerPrice, setTriggerPrice] = useState(0);

  // Dynamic lot size engine
  useEffect(() => {
    if (!currentInstrument) return;
    let active = true;
    const fetchLotSize = async () => {
      try {
        const res = await tradingApi.getBrokerInstrumentInfo(currentInstrument.instrumentKey);
        if (active && res.status === "success" && res.lot_size) {
          setLotSize(res.lot_size);
          setQuantity(res.lot_size);
        }
      } catch (e) {
        console.error("Failed to fetch dynamic lot size:", e);
        // Robust fallback based on exchange standards
        const sym = currentInstrument.symbol.toUpperCase();
        let fallback = 1;
        if (sym.includes("BANKNIFTY")) fallback = 15;
        else if (sym.includes("FINNIFTY")) fallback = 40;
        else if (sym.includes("MIDCPNIFTY")) fallback = 75;
        else if (sym.includes("NIFTY")) fallback = 75;
        if (active) {
          setLotSize(fallback);
          setQuantity(fallback);
        }
      }
    };
    fetchLotSize();
    return () => {
      active = false;
    };
  }, [currentInstrument]);

  
  // Risk & Target state
  const [stopLoss, setStopLoss] = useState<number>(0);
  const [targetPrice, setTargetPrice] = useState<number>(0);

  // Quote info state
  const [bidPrice, setBidPrice] = useState<number>(0);
  const [askPrice, setAskPrice] = useState<number>(0);
  const [contractPrice, setContractPrice] = useState<number>(0);
  const [lastUpdated, setLastUpdated] = useState<string>("");
  const [quoteLoading, setQuoteLoading] = useState<boolean>(false);

  // Margin info state
  const [brokerMarginReq, setBrokerMarginReq] = useState<number>(0);
  const [brokerMarginError, setBrokerMarginError] = useState<string | null>(null);
  const [availableMargin, setAvailableMargin] = useState<number>(0);

  // Positions list state
  const [positions, setPositions] = useState<any[]>([]);

  // Fetch available margin
  const fetchAvailableMargin = async () => {
    try {
      const res = await tradingApi.getBrokerFunds();
      const margin = Number(res.data?.equity?.available_margin || 0);
      setAvailableMargin(margin);
    } catch (e) {
      console.error("Failed to fetch available margin:", e);
    }
  };

  // Fetch broker positions
  const fetchPositions = async () => {
    try {
      const res = await tradingApi.getBrokerPositions();
      setPositions(res.data || []);
    } catch (e) {
      console.error("Failed to fetch broker positions in TradingRight", e);
    }
  };

  // Sync pricing & info bases when switching symbols
  useEffect(() => {
    if (!currentInstrument) return;
    
    // Clear and reset values
    setLimitPrice(0);
    setTriggerPrice(0);
    setStopLoss(0);
    setTargetPrice(0);
    setBidPrice(0);
    setAskPrice(0);
    setContractPrice(0);
    setLastUpdated("");

    let isMounted = true;
    const fetchQuote = async () => {
      try {
        if (isMounted) setQuoteLoading(true);
        const res = await tradingApi.getBrokerQuotes(currentInstrument.instrumentKey);
        
        const k1 = currentInstrument.instrumentKey;
        const k2 = k1.replace("|", ":");
        let q = res.data?.[k1] || res.data?.[k2];
        if (!q && res.data) {
          q = Object.values(res.data).find(
            (val: any) => val.instrument_token === k1 || val.instrument_token === k2
          );
        }
        
        if (q && isMounted) {
          const ltp = Number(q.last_price || 0);
          const bid = Number(q.depth?.buy?.[0]?.price || ltp);
          const ask = Number(q.depth?.sell?.[0]?.price || ltp);
          
          setContractPrice(ltp);
          setBidPrice(bid);
          setAskPrice(ask);
          setLastUpdated(new Date().toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" }) + " IST");
          
          // Populate default pricing on first fetch
          setLimitPrice((prev) => prev === 0 ? ltp : prev);
        }
      } catch (err) {
        console.error("Failed to fetch quote in order ticket:", err);
      } finally {
        if (isMounted) setQuoteLoading(false);
      }
    };
    
    fetchQuote();
    const interval = setInterval(fetchQuote, 5000);
    
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [currentInstrument]);

  // Sync margin, funds, and positions periodically
  useEffect(() => {
    fetchAvailableMargin();
    fetchPositions();
    const interval = setInterval(() => {
      fetchAvailableMargin();
      fetchPositions();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  // Fetch dynamic required margin when ticket fields change
  useEffect(() => {
    if (!currentInstrument || quantity <= 0) return;
    if (currentInstrument.instrumentKey.includes("INDEX") || currentInstrument.instrumentKey.includes("index")) {
      setBrokerMarginReq(0);
      setBrokerMarginError(null);
      return;
    }
    
    const fetchMarginReq = async () => {
      try {
        setBrokerMarginError(null);
        const res = await tradingApi.getBrokerMargin({
          instrument_key: currentInstrument.instrumentKey,
          quantity: quantity,
          transaction_type: side,
          product: productType,
        });
        if (res.status === "success" && res.data) {
          setBrokerMarginReq(Number(res.data.required_margin || res.data.final_margin || 0));
        } else {
          setBrokerMarginReq(0);
          setBrokerMarginError("Margin API error");
        }
      } catch (err: any) {
        console.error("Failed to fetch broker margin:", err);
        setBrokerMarginReq(0);
        setBrokerMarginError(err.message || "Failed to fetch margin");
      }
    };
    
    const delayDebounce = setTimeout(fetchMarginReq, 400);
    return () => clearTimeout(delayDebounce);
  }, [currentInstrument, quantity, side, productType]);

  const [orderSubmitting, setOrderSubmitting] = useState(false);
  const [orderError, setOrderError] = useState<string | null>(null);
  const [orderSuccess, setOrderSuccess] = useState<string | null>(null);

  const handlePlaceOrder = async (overrideSide?: "BUY" | "SELL") => {
    if (!currentInstrument) return;
    const orderSide = overrideSide || side;
    const entryPrice = orderType === "MARKET" ? 0 : limitPrice;

    setOrderSubmitting(true);
    setOrderError(null);
    setOrderSuccess(null);

    try {
      const result = await tradingApi.placeBrokerOrder({
        instrument_key: currentInstrument.instrumentKey,
        quantity,
        transaction_type: orderSide,
        order_type: orderType,
        product: productType,
        price: entryPrice,
        trigger_price: triggerPrice > 0 ? triggerPrice : 0,
      });

      const orderId = result?.data?.order_id || result?.order_id || "—";
      const msg = `${orderSide} ${quantity} ${currentInstrument.symbol} — Order ID: ${orderId}`;
      setOrderSuccess(msg);
      addEvent({ type: "success", message: msg, workspace: "Trading" });
      fetchPositions();
    } catch (err: any) {
      const errMsg = err.message || "Order placement failed";
      setOrderError(errMsg);
      addEvent({ type: "error", message: `ORDER FAILED: ${errMsg}`, workspace: "Trading" });
    } finally {
      setOrderSubmitting(false);
    }
  };

  const closePosition = async (sym?: string) => {
    await handlePlaceOrder("SELL");
    fetchPositions();
  };

  const entryPriceVal = orderType === "MARKET" ? contractPrice : limitPrice;
  const hasSL = stopLoss > 0;
  
  const riskAmount = hasSL ? Math.abs(entryPriceVal - stopLoss) * quantity : 0;
  const riskPct = hasSL && entryPriceVal > 0 ? (Math.abs(entryPriceVal - stopLoss) / entryPriceVal) * 100 : 0;
  
  const rewardAmount = targetPrice > 0 ? Math.abs(targetPrice - entryPriceVal) : 0;
  const rrRatio = (hasSL && rewardAmount > 0) ? (rewardAmount / Math.abs(entryPriceVal - stopLoss)).toFixed(1) : "N/A";

  return (
    <div className="flex flex-col gap-3 h-full font-sans text-xs">
      {/* Order Pad Card */}
      <div className="p-3 bg-slate-950/40 border border-white/5 rounded-lg flex flex-col gap-2.5">
        <h3 className="text-[10px] font-bold tracking-widest text-cyan-400 uppercase border-b border-white/5 pb-1.5 flex items-center justify-between select-none">
          <span>ORDER TICKET</span>
          <span className="text-[8px] font-mono text-slate-500">{currentAccount.name}</span>
        </h3>


        {/* Selected Instrument Info with Real-time Quote Panel */}
        <div className="flex flex-col gap-1.5 bg-slate-900/40 p-2 rounded border border-white/5 font-mono text-[10px] select-none text-slate-300">
          <div className="flex justify-between items-center">
            <span>CONTRACT:</span>
            <span className="font-bold text-cyan-400 uppercase">
              {currentInstrument ? currentInstrument.symbol : "NONE SELECTED"}
            </span>
          </div>
          {currentInstrument && (
            <>
              {(() => {
                const details = parseInstrument(currentInstrument.symbol);
                if (details.type === "CE" || details.type === "PE") {
                  return (
                    <div className="grid grid-cols-3 gap-1 mt-0.5 border-t border-white/5 pt-1.5 text-[8px] text-slate-400 uppercase">
                      <div>
                        <span>TYPE: </span>
                        <span className={`font-bold ${details.type === "CE" ? "text-emerald-400" : "text-rose-400"}`}>{details.type}</span>
                      </div>
                      <div>
                        <span>STRIKE: </span>
                        <span className="font-bold text-slate-200">{details.strike}</span>
                      </div>
                      <div>
                        <span>EXPIRY: </span>
                        <span className="font-bold text-slate-200">{details.expiry}</span>
                      </div>
                    </div>
                  );
                }
                return null;
              })()}
              <div className="grid grid-cols-2 gap-x-3 gap-y-1 mt-1 border-t border-white/5 pt-1.5 text-[9px] text-slate-400">
                <div className="flex justify-between">
                  <span>LTP:</span>
                  <span className="text-slate-200 font-bold">₹{contractPrice.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span>UPDATED:</span>
                  <span className="text-slate-500">{lastUpdated || "N/A"}</span>
                </div>
                <div className="flex justify-between">
                  <span>BID:</span>
                  <span className="text-emerald-400 font-bold">₹{bidPrice.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span>ASK:</span>
                  <span className="text-rose-400 font-bold">₹{askPrice.toFixed(2)}</span>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Side Selector Toggle */}
        <div className="grid grid-cols-2 gap-2 bg-slate-900/30 p-1 rounded border border-white/5 select-none shrink-0">
          <button
            onClick={() => setSide("BUY")}
            className={`py-1.5 rounded text-[11px] font-bold transition-all cursor-pointer text-center ${
              side === "BUY"
                ? "bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/10"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            BUY
          </button>
          <button
            onClick={() => setSide("SELL")}
            className={`py-1.5 rounded text-[11px] font-bold transition-all cursor-pointer text-center ${
              side === "SELL"
                ? "bg-rose-500 text-slate-950 shadow-md shadow-rose-500/10"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            SELL
          </button>
        </div>

        {/* Action Feedbacks */}
        {orderError && (
          <div className="p-2 bg-rose-950/40 border border-rose-500/20 text-rose-400 text-[10px] rounded flex items-center gap-1.5 font-sans animate-pulse">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            <span className="truncate">{orderError}</span>
          </div>
        )}
        {orderSuccess && (
          <div className="p-2 bg-emerald-950/40 border border-emerald-500/20 text-emerald-400 text-[10px] rounded flex items-center gap-1.5 font-sans">
            <CheckCircle2 className="w-3.5 h-3.5 shrink-0 text-emerald-400" />
            <span className="truncate">{orderSuccess}</span>
          </div>
        )}

        {/* Product Type (MIS/NRML/CNC) */}
        <div className="flex flex-col gap-1 select-none">
          <span className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Product Type</span>
          <div className="grid grid-cols-3 gap-1 bg-slate-900/40 p-0.5 rounded border border-white/5">
            {(["MIS", "NRML", "CNC"] as const).map((type) => (
              <button
                key={type}
                onClick={() => setProductType(type)}
                className={`py-1 rounded text-[10px] font-bold uppercase transition-all cursor-pointer text-center ${
                  productType === type
                    ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20"
                    : "text-slate-500 hover:text-slate-300 border border-transparent"
                }`}
              >
                {type}
              </button>
            ))}
          </div>
        </div>

        {/* Quantity (Lots / Units) */}
        <div className="flex flex-col gap-1">
          <div className="flex justify-between items-center">
            <span className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Quantity</span>
            <span className="text-[9px] text-slate-500 font-mono">Lot Size: {lotSize}</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setQuantity((q) => Math.max(lotSize, q - lotSize))}
              className="bg-slate-900 border border-white/5 hover:border-white/10 w-8 py-1 rounded text-slate-300 font-bold hover:text-white transition-all cursor-pointer text-center"
            >
              -
            </button>
            <input
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(Math.max(1, Number(e.target.value)))}
              className="flex-1 bg-slate-900/60 border border-white/5 rounded py-1 text-center font-mono text-slate-200 focus:outline-none focus:border-cyan-500/40"
            />
            <button
              onClick={() => setQuantity((q) => q + lotSize)}
              className="bg-slate-900 border border-white/5 hover:border-white/10 w-8 py-1 rounded text-slate-300 font-bold hover:text-white transition-all cursor-pointer text-center"
            >
              +
            </button>
          </div>
        </div>

        {/* Order Type Toggle */}
        <div className="flex flex-col gap-1 select-none">
          <span className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Order Type</span>
          <div className="grid grid-cols-2 gap-1.5">
            <button
              onClick={() => setOrderType("MARKET")}
              className={`py-1 rounded border transition-all cursor-pointer text-center font-bold text-[10px] ${
                orderType === "MARKET"
                  ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400"
                  : "bg-slate-900 border-white/5 text-slate-400 hover:text-slate-200"
              }`}
            >
              MARKET
            </button>
            <button
              onClick={() => setOrderType("LIMIT")}
              className={`py-1 rounded border transition-all cursor-pointer text-center font-bold text-[10px] ${
                orderType === "LIMIT"
                  ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400"
                  : "bg-slate-900 border-white/5 text-slate-400 hover:text-slate-200"
              }`}
            >
              LIMIT
            </button>
          </div>
        </div>

        {/* Limit Price / Trigger Price */}
        <div className="grid grid-cols-2 gap-2">
          <div className="flex flex-col gap-1">
            <span className="text-[9px] text-slate-500 uppercase tracking-wider">Limit Price</span>
            <input
              type="number"
              disabled={orderType === "MARKET"}
              value={limitPrice || ""}
              onChange={(e) => setLimitPrice(Number(e.target.value))}
              className="w-full bg-slate-900 border border-white/5 rounded py-1 px-2 font-mono text-center text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:border-cyan-500/40"
            />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-[9px] text-slate-500 uppercase tracking-wider">Trigger Price</span>
            <input
              type="number"
              value={triggerPrice || ""}
              onChange={(e) => setTriggerPrice(Number(e.target.value))}
              className="w-full bg-slate-900 border border-white/5 rounded py-1 px-2 font-mono text-center text-slate-200 focus:outline-none focus:border-cyan-500/40"
            />
          </div>
        </div>

        {/* Risk Targets (Optional for SL / Target placement) */}
        <div className="grid grid-cols-2 gap-2">
          <div className="flex flex-col gap-1">
            <div className="flex justify-between">
              <span className="text-[9px] text-slate-500 uppercase tracking-wider">Stop Loss</span>
              {!stopLoss && <span className="text-[8px] text-rose-400 font-sans uppercase">Required</span>}
            </div>
            <input
              type="number"
              placeholder="SL Price"
              value={stopLoss || ""}
              onChange={(e) => setStopLoss(Number(e.target.value))}
              className="w-full bg-slate-900 border border-white/5 rounded py-1 px-2 font-mono text-center text-slate-200 focus:outline-none focus:border-cyan-500/40"
            />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-[9px] text-slate-500 uppercase tracking-wider">Target Price</span>
            <input
              type="number"
              placeholder="Target Price"
              value={targetPrice || ""}
              onChange={(e) => setTargetPrice(Number(e.target.value))}
              className="w-full bg-slate-900 border border-white/5 rounded py-1 px-2 font-mono text-center text-slate-200 focus:outline-none focus:border-cyan-500/40"
            />
          </div>
        </div>

        {/* Real Broker Margin HUD & Risk Estimation */}
        <div className="flex flex-col gap-1.5 bg-slate-950/40 p-2 rounded border border-white/5 font-mono text-[9px] text-slate-500 select-none">
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-0.5">
              <span>REQUIRED MARGIN:</span>
              <span className="font-bold text-slate-300">
                ₹{brokerMarginReq.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span>AVAILABLE MARGIN:</span>
              <span className="font-bold text-slate-300">
                ₹{availableMargin.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 border-t border-white/5 pt-1 mt-1">
            <div className="flex flex-col gap-0.5">
              <span>POST-TRADE MARGIN:</span>
              <span className="font-bold text-slate-300">
                ₹{(availableMargin - brokerMarginReq).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span>MARGIN UTILIZATION:</span>
              <span className="font-bold text-slate-300">
                {(availableMargin > 0 ? (brokerMarginReq / availableMargin) * 100 : 0).toFixed(2)}%
              </span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 border-t border-white/5 pt-1.5 mt-1">
            <div className="col-span-2 flex flex-col gap-0.5">
              <span>RISK ESTIMATE:</span>
              {hasSL ? (
                <div className="flex flex-col text-slate-300 font-bold">
                  <span>₹{riskAmount.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</span>
                  <span className="text-[8px] text-slate-500 font-normal mt-0.5">
                    Risk %: {riskPct.toFixed(2)}% | R:R Ratio: 1:{rrRatio}
                  </span>
                </div>
              ) : (
                <span className="text-rose-400 font-sans font-bold animate-pulse text-[8px] uppercase">
                  Stop Loss Required
                </span>
              )}
            </div>
          </div>
          {brokerMarginError && (
            <span className="text-[8px] text-rose-400 mt-1 uppercase font-sans animate-pulse">
              * {brokerMarginError}
            </span>
          )}
        </div>

        {/* Big Action Submit Buttons */}
        <div className="grid grid-cols-2 gap-2 pt-1 border-t border-white/5">
          <button
            onClick={() => handlePlaceOrder("BUY")}
            disabled={orderSubmitting || !currentInstrument}
            className={`w-full font-bold py-2 rounded text-xs transition-all uppercase tracking-wider text-center shadow-lg ${
              orderSubmitting
                ? "bg-slate-700 text-slate-400 cursor-not-allowed"
                : "bg-emerald-500 hover:bg-emerald-400 text-slate-950 cursor-pointer shadow-emerald-500/10"
            }`}
          >
            {orderSubmitting ? "SUBMITTING..." : "BUY"}
          </button>
          <button
            onClick={() => handlePlaceOrder("SELL")}
            disabled={orderSubmitting || !currentInstrument}
            className={`w-full font-bold py-2 rounded text-xs transition-all uppercase tracking-wider text-center shadow-lg ${
              orderSubmitting
                ? "bg-slate-700 text-slate-400 cursor-not-allowed"
                : "bg-rose-500 hover:bg-rose-400 text-slate-950 cursor-pointer shadow-rose-500/10"
            }`}
          >
            {orderSubmitting ? "SUBMITTING..." : "SELL"}
          </button>
        </div>
      </div>

      {/* Broker Account Panel */}
      <BrokerAccountPanel />

      {/* Mini Position Summary Panel - Sync'd to Broker Account */}
      <div className="p-3 bg-slate-950/40 border border-white/5 rounded-lg flex flex-col gap-2 flex-1 min-h-0 select-none">
        <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest border-b border-white/5 pb-1">
          Open Positions ({positions.length})
        </span>
        <div className="flex-1 overflow-y-auto flex flex-col gap-1.5 pr-1 font-sans text-xs scrollbar-thin scrollbar-thumb-white/5">
          {positions.length > 0 ? (
            positions.map((pos) => {
              const qty = Number(pos.quantity || 0);
              return (
                <div 
                  key={`${pos.instrument_token}_${pos.product}`}
                  className="p-2 rounded bg-slate-900/40 border border-white/5 flex flex-col gap-1 relative group"
                >
                  <div className="flex justify-between items-center">
                    <span className="font-bold text-slate-200">{pos.trading_symbol}</span>
                    <button 
                      onClick={() => closePosition(pos.trading_symbol)}
                      className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-rose-400 transition-all absolute right-2 top-2 cursor-pointer"
                      title="Squareoff Position"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="grid grid-cols-4 text-[10px] text-slate-400 font-mono">
                    <div className="flex flex-col">
                      <span className="text-[8px] text-slate-600 font-sans uppercase">Side</span>
                      <span className={qty > 0 ? "text-emerald-400 font-bold" : qty < 0 ? "text-rose-400 font-bold" : "text-slate-500"}>
                        {qty > 0 ? "LONG" : qty < 0 ? "SHORT" : "CLOSED"}
                      </span>
                    </div>
                    <div className="flex flex-col text-right">
                      <span className="text-[8px] text-slate-600 font-sans uppercase">Qty</span>
                      <span>{qty}</span>
                    </div>
                    <div className="flex flex-col text-right">
                      <span className="text-[8px] text-slate-600 font-sans uppercase">Avg/LTP</span>
                      <span>₹{Number(pos.average_price || pos.buy_price || 0).toFixed(1)}/₹{Number(pos.last_price || 0).toFixed(1)}</span>
                    </div>
                    <div className="flex flex-col text-right">
                      <span className="text-[8px] text-slate-600 font-sans uppercase">PnL</span>
                      <span className={`font-bold ${Number(pos.unrealised || 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {Number(pos.unrealised || 0) >= 0 ? "+" : ""}₹{Number(pos.unrealised || 0).toLocaleString("en-IN", { maximumFractionDigits: 1 })}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="flex-1 flex items-center justify-center text-slate-500 text-[10px]">
              No active open positions.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// ==========================================
// OPTION CONTRACT SELECTOR & CHAIN PANEL
// ==========================================
const OptionChainPanel: React.FC = () => {
  const currentInstrument = useTerminalStore((state) => state.selectedInstrument);
  const setInstrument = useTerminalStore((state) => state.setInstrument);
  
  const [underlying, setUnderlying] = useState<string>("NIFTY");
  const [expiries, setExpiries] = useState<string[]>([]);
  const [selectedExpiry, setSelectedExpiry] = useState<string>("");
  const [spotPrice, setSpotPrice] = useState<number>(0.0);
  const [strikesData, setStrikesData] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Bug #1 fix — sync option chain underlying when watchlist instrument changes
  useEffect(() => {
    if (!currentInstrument) return;
    const sym = currentInstrument.symbol.toUpperCase();
    if (sym.includes("BANKNIFTY") || currentInstrument.instrumentKey.includes("Nifty Bank")) {
      setUnderlying("BANKNIFTY");
    } else if (sym.includes("FINNIFTY") || currentInstrument.instrumentKey.includes("Nifty Fin")) {
      setUnderlying("FINNIFTY");
    } else if (sym.includes("MIDCPNIFTY") || sym.includes("MID SELECT")) {
      setUnderlying("MIDCPNIFTY");
    } else if (sym.includes("NIFTY") || currentInstrument.instrumentKey.includes("Nifty 50")) {
      setUnderlying("NIFTY");
    } else {
      setUnderlying(sym);
    }
  }, [currentInstrument?.instrumentKey]);

  const lastUnderlyingRef = useRef<string>("");

  const fetchMetadata = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(`http://localhost:8081/api/options/metadata?index=${underlying}&exchange=NSE`);
      if (!res.ok) throw new Error("Failed to load metadata");
      const data = await res.json();
      const loadedExpiries = data.expiries || [];
      setExpiries(loadedExpiries);
      if (loadedExpiries.length > 0) {
        if (!loadedExpiries.includes(selectedExpiry)) {
          setSelectedExpiry(loadedExpiries[0]);
        }
      }
      setSpotPrice(data.spot_price || 0.0);
    } catch (err: any) {
      setError(err.message || "Failed to load option metadata");
    } finally {
      setLoading(false);
    }
  };

  const fetchChain = async () => {
    if (!selectedExpiry) return;
    try {
      const res = await fetch(`http://localhost:8081/api/options/chain?expiry=${selectedExpiry}&index=${underlying}&exchange=NSE`);
      if (!res.ok) throw new Error("Failed to load option chain");
      const data = await res.json();
      setSpotPrice(data.spot_price || 0.0);
      const strikes = data.strikes || [];
      setStrikesData(strikes);

      // Auto ATM CE selection workflow
      if (lastUnderlyingRef.current !== underlying && data.atm_strike > 0 && strikes.length > 0) {
        const atmRow = strikes.find((s: any) => Number(s.strike) === Number(data.atm_strike)) || strikes[Math.floor(strikes.length / 2)];
        if (atmRow && atmRow.ce_key && atmRow.ce_symbol) {
          // Trigger global hotswap of the active instrument to the ATM CE option contract
          handleSelectContract(atmRow.strike, "CE", atmRow.ce_key, atmRow.ce_symbol);
          lastUnderlyingRef.current = underlying;
        }
      }
    } catch (err: any) {
      setError(err.message || "Failed to load option chain");
    }
  };

  useEffect(() => {
    fetchMetadata();
  }, [underlying]);

  useEffect(() => {
    if (selectedExpiry) {
      fetchChain();
    }
  }, [selectedExpiry, underlying]);

  useEffect(() => {
    if (!selectedExpiry) return;
    const timer = setInterval(() => {
      fetchChain();
    }, 2500);
    return () => clearInterval(timer);
  }, [selectedExpiry, underlying]);

  const handleSelectContract = async (strike: number, type: "CE" | "PE", key: string, symbol: string) => {
    setInstrument({
      instrumentKey: key,
      symbol: symbol,
      exchange: "NSE",
    });

    try {
      await fetch("http://localhost:8081/api/standard/update_target", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expiry: selectedExpiry,
          option_type: type,
          strike: String(strike),
          exchange: "NSE",
          index_name: underlying,
        }),
      });
    } catch (e) {
      console.error("Failed to hot-swap option target on backend", e);
    }
  };

  return (
    <div className="flex flex-col h-full gap-2 p-1">
      {/* Option Chain Control Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/40 p-2 rounded border border-white/5 select-none shrink-0">
        <div className="flex items-center gap-3">
          {/* Underlying Selector */}
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] text-slate-500 font-bold uppercase tracking-wider">Index:</span>
            <select
              value={underlying}
              onChange={(e) => setUnderlying(e.target.value)}
              className="bg-slate-950 border border-white/10 rounded px-2 py-1 text-[11px] text-slate-200 focus:outline-none focus:border-cyan-500/40 cursor-pointer font-sans"
            >
              <option value="NIFTY">NIFTY</option>
              <option value="BANKNIFTY">BANKNIFTY</option>
              <option value="FINNIFTY">FINNIFTY</option>
              <option value="MIDCPNIFTY">MIDCPNIFTY</option>
              {!["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"].includes(underlying) && (
                <option value={underlying}>{underlying}</option>
              )}
            </select>
          </div>

          {/* Expiry Selector */}
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] text-slate-500 font-bold uppercase tracking-wider">Expiry:</span>
            <select
              value={selectedExpiry}
              onChange={(e) => setSelectedExpiry(e.target.value)}
              className="bg-slate-950 border border-white/10 rounded px-2 py-1 text-[11px] text-slate-200 focus:outline-none focus:border-cyan-500/40 cursor-pointer font-sans"
            >
              {expiries.map((exp) => (
                <option key={exp} value={exp}>
                  {exp}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Spot Price and Status Indicator */}
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] text-slate-500 uppercase tracking-wider">Spot Price:</span>
            <span className="text-cyan-400 font-bold">
              ₹{spotPrice.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </span>
          </div>
          {loading && <span className="text-[9px] text-cyan-500 animate-pulse uppercase">Syncing...</span>}
        </div>
      </div>

      {/* Selected Contract Quick HUD */}
      {currentInstrument && (
        <div className="bg-cyan-500/5 border border-cyan-500/20 px-3 py-1.5 rounded flex items-center justify-between text-[11px] font-sans">
          <div className="flex items-center gap-2">
            <span className="text-slate-500 font-bold uppercase tracking-wider text-[9px]">Active Target:</span>
            <span className="font-bold text-cyan-400 font-mono">{currentInstrument.symbol}</span>
          </div>
          <span className="text-[9px] font-mono text-slate-500 uppercase">Key: {currentInstrument.instrumentKey}</span>
        </div>
      )}

      {/* Error alert */}
      {error && (
        <div className="p-2 bg-rose-950/40 border border-rose-500/20 text-rose-400 text-[10px] rounded select-none">
          {error}
        </div>
      )}

      {/* Option Chain Table */}
      <div className="flex-1 min-h-0 overflow-y-auto border border-white/5 rounded">
        <table className="w-full text-left font-mono text-[10px] border-collapse">
          <thead className="sticky top-0 bg-slate-950/90 backdrop-blur border-b border-white/10 z-10">
            <tr className="text-slate-500 uppercase text-[9px] tracking-wider select-none">
              <th className="py-2 pl-3 text-emerald-400 font-bold">Call LTP</th>
              <th className="py-2 text-center text-slate-400 font-bold">Strike</th>
              <th className="py-2 pr-3 text-right text-rose-400 font-bold">Put LTP</th>
            </tr>
          </thead>
          <tbody className="text-slate-300 divide-y divide-white/[0.02]">
            {strikesData.length > 0 ? (
              strikesData.map((row) => {
                const isATM = Math.abs(row.strike - spotPrice) <= (underlying === "NIFTY" || underlying === "MIDCPNIFTY" ? 25 : 50);
                
                return (
                  <tr
                    key={row.strike}
                    className={`hover:bg-cyan-500/5 transition-all ${
                      isATM ? "bg-cyan-500/[0.02] border-y border-cyan-500/10" : ""
                    }`}
                  >
                    {/* Call LTP */}
                    <td className="py-2 pl-3">
                      {row.ce_key ? (
                        <button
                          onClick={() => handleSelectContract(row.strike, "CE", row.ce_key, row.ce_symbol)}
                          className="flex items-center gap-1.5 group cursor-pointer text-left w-full focus:outline-none"
                        >
                          <span className="text-emerald-400 font-bold font-mono">
                            ₹{row.ce_ltp.toFixed(2)}
                          </span>
                          <span className="opacity-0 group-hover:opacity-100 text-[8px] bg-emerald-500/10 text-emerald-400 px-1 rounded uppercase font-sans font-medium transition-opacity">
                            Trade CE
                          </span>
                        </button>
                      ) : (
                        <span className="text-slate-600">-</span>
                      )}
                    </td>

                    {/* Strike */}
                    <td className="py-2 text-center font-bold text-slate-200">
                      <span className={`px-1.5 py-0.5 rounded ${
                        isATM ? "bg-cyan-500/10 text-cyan-400 font-extrabold" : "text-slate-400"
                      }`}>
                        {row.strike}
                      </span>
                    </td>

                    {/* Put LTP */}
                    <td className="py-2 pr-3 text-right">
                      {row.pe_key ? (
                        <button
                          onClick={() => handleSelectContract(row.strike, "PE", row.pe_key, row.pe_symbol)}
                          className="flex items-center justify-end gap-1.5 group cursor-pointer text-right w-full focus:outline-none"
                        >
                          <span className="opacity-0 group-hover:opacity-100 text-[8px] bg-rose-500/10 text-rose-400 px-1 rounded uppercase font-sans font-medium transition-opacity">
                            Trade PE
                          </span>
                          <span className="text-rose-400 font-bold font-mono">
                            ₹{row.pe_ltp.toFixed(2)}
                          </span>
                        </button>
                      ) : (
                        <span className="text-slate-600">-</span>
                      )}
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={3} className="py-6 text-center text-slate-500 text-[10px] font-sans">
                  No options chain data loaded. Please select a valid expiry.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ==========================================
// 4. BOTTOM PANEL: TABBED PORTFOLIO LEDGER
// ==========================================
export const TradingBottom: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"positions" | "orders" | "trades" | "holdings" | "pnl" | "optionChain">("optionChain");
  
  const [brokerPositions, setBrokerPositions] = useState<any[]>([]);
  const [brokerOrders, setBrokerOrders] = useState<any[]>([]);
  const [brokerTrades, setBrokerTrades] = useState<any[]>([]);
  const [brokerHoldings, setBrokerHoldings] = useState<any[]>([]);

  const fetchPositions = async () => {
    try {
      const res = await tradingApi.getBrokerPositions();
      setBrokerPositions(res.data || []);
    } catch (e) {
      console.error("Failed to fetch broker positions", e);
    }
  };

  const fetchOrders = async () => {
    try {
      const res = await tradingApi.getBrokerOrders();
      setBrokerOrders(res.data || []);
    } catch (e) {
      console.error("Failed to fetch broker orders", e);
    }
  };

  const fetchTrades = async () => {
    try {
      const res = await tradingApi.getBrokerTrades();
      setBrokerTrades(res.data || []);
    } catch (e) {
      console.error("Failed to fetch broker trades", e);
    }
  };

  const fetchHoldings = async () => {
    try {
      const res = await tradingApi.getBrokerHoldings();
      setBrokerHoldings(res.data || []);
    } catch (e) {
      console.error("Failed to fetch broker holdings", e);
    }
  };

  useEffect(() => {
    fetchPositions();
    fetchOrders();
    fetchTrades();
    fetchHoldings();

    const interval = setInterval(() => {
      fetchPositions();
      fetchOrders();
      fetchTrades();
      fetchHoldings();
    }, 15000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (activeTab === "positions") fetchPositions();
    else if (activeTab === "orders") fetchOrders();
    else if (activeTab === "trades") fetchTrades();
    else if (activeTab === "holdings") fetchHoldings();
  }, [activeTab]);

  const realizedPnL = brokerPositions.reduce((acc, pos) => acc + Number(pos.realised || 0), 0);
  const unrealizedPnL = brokerPositions.reduce((acc, pos) => acc + Number(pos.unrealised || 0), 0);
  const brokerage = brokerTrades.length * 20.0;
  const netPnL = realizedPnL + unrealizedPnL - brokerage;

  const tabs = [
    { id: "optionChain" as const, name: "Option Chain" },
    { id: "positions" as const, name: `Positions (${brokerPositions.length})` },
    { id: "orders" as const, name: `Orders (${brokerOrders.length})` },
    { id: "trades" as const, name: `Trades (${brokerTrades.length})` },
    { id: "holdings" as const, name: `Holdings (${brokerHoldings.length})` },
    { id: "pnl" as const, name: "PnL Summary" },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden text-xs font-sans">
      {/* Tabs list */}
      <div className="flex items-center gap-1 border-b border-white/5 bg-slate-950/20 px-2 shrink-0 select-none">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-3 py-1.5 font-bold uppercase text-[10px] tracking-wider transition-all border-b-2 cursor-pointer ${
              activeTab === tab.id
                ? "border-cyan-400 text-cyan-400 bg-slate-900/30"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}
          >
            {tab.name}
          </button>
        ))}
      </div>

      {/* Tabs Contents */}
      <div className="flex-1 overflow-y-auto p-2 scrollbar-thin scrollbar-thumb-white/5 scrollbar-track-transparent min-h-0">
        
        {/* Tab 0: Option Chain */}
        {activeTab === "optionChain" && <OptionChainPanel />}

        {/* Tab 1: Positions */}
        {activeTab === "positions" && (
          <table className="w-full text-left font-mono text-[10px]">
            <thead>
              <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-[9px] tracking-wider">
                <th className="py-1.5 pl-2">Symbol</th>
                <th className="py-1.5 text-center">Qty</th>
                <th className="py-1.5 text-center">Product</th>
                <th className="py-1.5 text-center">Exchange</th>
                <th className="py-1.5 text-right">Avg Price</th>
                <th className="py-1.5 text-right">LTP</th>
                <th className="py-1.5 text-right">MTM</th>
                <th className="py-1.5 text-right">Realized PnL</th>
                <th className="py-1.5 text-center pr-2">Status</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              {brokerPositions.length > 0 ? (
                brokerPositions.map((pos) => {
                  const qty = Number(pos.quantity || 0);
                  const statusLabel = qty === 0 ? "CLOSED" : qty > 0 ? "LONG" : "SHORT";
                  const statusClass = qty === 0 ? "bg-slate-900 text-slate-500 border-white/5" : qty > 0 ? "bg-emerald-950/40 text-emerald-400 border-emerald-800/30" : "bg-rose-950/40 text-rose-400 border-rose-800/30";
                  
                  return (
                    <tr key={`${pos.instrument_token}_${pos.product}`} className="border-b border-white/[0.02] hover:bg-white/[0.01] transition-all">
                      <td className="py-1.5 pl-2 font-sans font-bold text-slate-200">{pos.trading_symbol}</td>
                      <td className="py-1.5 text-center font-bold">{qty}</td>
                      <td className="py-1.5 text-center text-slate-400 font-sans">{pos.product}</td>
                      <td className="py-1.5 text-center text-slate-400 font-sans">{pos.exchange}</td>
                      <td className="py-1.5 text-right">₹{Number(pos.average_price || pos.buy_price || 0).toFixed(2)}</td>
                      <td className="py-1.5 text-right font-bold">₹{Number(pos.last_price || 0).toFixed(2)}</td>
                      <td className={`py-1.5 text-right font-bold ${Number(pos.unrealised || 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {Number(pos.unrealised || 0) >= 0 ? "+" : ""}₹{Number(pos.unrealised || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className={`py-1.5 text-right font-bold ${Number(pos.realised || 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {Number(pos.realised || 0) >= 0 ? "+" : ""}₹{Number(pos.realised || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="py-1.5 text-center pr-2">
                        <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold font-sans border ${statusClass}`}>
                          {statusLabel}
                        </span>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={9} className="py-6 text-center text-slate-500 text-[10px] font-sans">
                    No active positions found in Upstox account.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}

        {/* Tab 2: Orders */}
        {activeTab === "orders" && (
          <table className="w-full text-left font-mono text-[10px]">
            <thead>
              <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-[9px] tracking-wider">
                <th className="py-1.5 pl-2">Order ID</th>
                <th className="py-1.5">Symbol</th>
                <th className="py-1.5 text-center">Qty</th>
                <th className="py-1.5 text-center">Type</th>
                <th className="py-1.5 text-center">Status</th>
                <th className="py-1.5 text-right">Avg Price</th>
                <th className="py-1.5 text-right pr-2">Timestamp</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              {brokerOrders.length > 0 ? (
                brokerOrders.map((ord) => {
                  const statusLower = (ord.status || "").toLowerCase();
                  let statusLabel = "PENDING";
                  let statusClass = "bg-amber-950/20 text-amber-400 border-amber-800/30";
                  
                  if (statusLower === "complete") {
                    statusLabel = "FILLED";
                    statusClass = "bg-emerald-950/20 text-emerald-400 border-emerald-800/30";
                  } else if (statusLower === "rejected") {
                    statusLabel = "REJECTED";
                    statusClass = "bg-rose-950/20 text-rose-400 border-rose-800/30";
                  } else if (statusLower === "cancelled") {
                    statusLabel = "CANCELLED";
                    statusClass = "bg-slate-900 text-slate-500 border-white/5";
                  } else if (statusLower === "open" || statusLower === "trigger pending" || statusLower === "put order req received") {
                    statusLabel = "PENDING";
                    statusClass = "bg-amber-950/20 text-amber-400 border-amber-800/30";
                  } else {
                    statusLabel = (ord.status || "UNKNOWN").toUpperCase();
                    statusClass = "bg-slate-900 text-slate-400 border-white/5";
                  }

                  return (
                    <tr key={ord.order_id} className="border-b border-white/[0.02] hover:bg-white/[0.01]">
                      <td className="py-1.5 pl-2 text-slate-500 font-mono">{ord.order_id}</td>
                      <td className="py-1.5 font-sans font-bold text-slate-200">{ord.trading_symbol}</td>
                      <td className="py-1.5 text-center">{ord.quantity}</td>
                      <td className="py-1.5 text-center font-bold text-slate-400 font-sans">{ord.order_type}</td>
                      <td className="py-1.5 text-center">
                        <span className={`px-1 py-0.5 rounded text-[8px] font-bold uppercase font-sans border ${statusClass}`}>
                          {statusLabel}
                        </span>
                      </td>
                      <td className="py-1.5 text-right">₹{Number(ord.average_price || 0).toFixed(2)}</td>
                      <td className="py-1.5 text-right pr-2 text-slate-500">{ord.order_timestamp || ord.exchange_timestamp}</td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-slate-500 text-[10px] font-sans">
                    No orders found in Upstox account.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}

        {/* Tab 3: Trades */}
        {activeTab === "trades" && (
          <table className="w-full text-left font-mono text-[10px]">
            <thead>
              <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-[9px] tracking-wider">
                <th className="py-1.5 pl-2">Trade ID</th>
                <th className="py-1.5">Order ID</th>
                <th className="py-1.5">Symbol</th>
                <th className="py-1.5 text-center">Side</th>
                <th className="py-1.5 text-center">Qty</th>
                <th className="py-1.5 text-right">Price</th>
                <th className="py-1.5 text-right pr-2">Timestamp</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              {brokerTrades.length > 0 ? (
                brokerTrades.map((trd) => (
                  <tr key={trd.trade_id} className="border-b border-white/[0.02] hover:bg-white/[0.01]">
                    <td className="py-1.5 pl-2 text-slate-500 font-mono">{trd.trade_id}</td>
                    <td className="py-1.5 text-slate-500 font-mono">{trd.order_id}</td>
                    <td className="py-1.5 font-sans font-bold text-slate-200">{trd.trading_symbol}</td>
                    <td className="py-1.5 text-center">
                      <span className={`font-sans font-bold text-[9px] ${trd.transaction_type === "BUY" ? "text-emerald-400" : "text-rose-400"}`}>
                        {trd.transaction_type}
                      </span>
                    </td>
                    <td className="py-1.5 text-center">{trd.quantity}</td>
                    <td className="py-1.5 text-right">₹{Number(trd.average_price || 0).toFixed(2)}</td>
                    <td className="py-1.5 text-right pr-2 text-slate-500">{trd.exchange_timestamp || trd.order_timestamp}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-slate-500 text-[10px] font-sans">
                    No trades executed today in Upstox account.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}

        {/* Tab 4: Holdings */}
        {activeTab === "holdings" && (
          <table className="w-full text-left font-mono text-[10px]">
            <thead>
              <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-[9px] tracking-wider">
                <th className="py-1.5 pl-2">Symbol</th>
                <th className="py-1.5 text-center">Qty</th>
                <th className="py-1.5 text-right">Avg Cost</th>
                <th className="py-1.5 text-right">Current Value</th>
                <th className="py-1.5 text-right">PnL</th>
                <th className="py-1.5 text-center pr-2">Exchange</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              {brokerHoldings.length > 0 ? (
                brokerHoldings.map((hold) => {
                  const qty = Number(hold.quantity || 0);
                  const avgPrice = Number(hold.average_price || 0);
                  const lastPrice = Number(hold.last_price || 0);
                  const currentValue = qty * lastPrice;
                  const pnl = Number(hold.pnl || 0);
                  
                  return (
                    <tr key={`${hold.isin}_${hold.product}`} className="border-b border-white/[0.02] hover:bg-white/[0.01]">
                      <td className="py-1.5 pl-2 font-sans font-bold text-slate-200">{hold.trading_symbol}</td>
                      <td className="py-1.5 text-center">{qty}</td>
                      <td className="py-1.5 text-right">₹{avgPrice.toFixed(2)}</td>
                      <td className="py-1.5 text-right font-bold">₹{currentValue.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                      <td className={`py-1.5 text-right font-bold ${pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {pnl >= 0 ? "+" : ""}₹{pnl.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="py-1.5 text-center pr-2 text-slate-400 font-sans">{hold.exchange}</td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-slate-500 text-[10px] font-sans">
                    No holdings found in Upstox account.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}

        {/* Tab 5: PnL Summary */}
        {activeTab === "pnl" && (
          <div className="grid grid-cols-5 gap-4 max-w-4xl p-2 select-none">
            <div className="bg-slate-900/30 p-2.5 rounded border border-white/5">
              <span className="text-[9px] text-slate-500 block uppercase font-sans tracking-wide">Realized P&L</span>
              <span className={`font-mono text-base font-bold ${realizedPnL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                ₹{realizedPnL.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </span>
            </div>
            <div className="bg-slate-900/30 p-2.5 rounded border border-white/5">
              <span className="text-[9px] text-slate-500 block uppercase font-sans tracking-wide">Unrealized P&L</span>
              <span className={`font-mono text-base font-bold ${unrealizedPnL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                ₹{unrealizedPnL.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </span>
            </div>
            <div className="bg-slate-900/30 p-2.5 rounded border border-white/5">
              <span className="text-[9px] text-slate-500 block uppercase font-sans tracking-wide">Brokerage Fees</span>
              <span className="font-mono text-base font-bold text-slate-300">
                ₹{brokerage.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </span>
            </div>
            <div className="bg-slate-900/30 p-2.5 rounded border border-white/5">
              <span className="text-[9px] text-slate-500 block uppercase font-sans tracking-wide">Day P&L Total</span>
              <span className={`font-mono text-base font-bold ${realizedPnL + unrealizedPnL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                ₹{(realizedPnL + unrealizedPnL).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </span>
            </div>
            <div className="bg-cyan-950/20 p-2.5 rounded border border-cyan-500/20">
              <span className="text-[9px] text-cyan-400 block uppercase font-sans tracking-wide font-semibold">Net P&L</span>
              <span className={`font-mono text-base font-bold ${netPnL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                ₹{netPnL.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </span>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};
