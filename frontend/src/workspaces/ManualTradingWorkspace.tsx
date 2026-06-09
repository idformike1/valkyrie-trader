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

// Valkyrie Design System V3 imports
import { SegmentedTabs } from "@/design-system/SegmentedTabs";
import { DataTable, ColumnDef } from "@/design-system/DataTable";
import { StatusBadge } from "@/design-system/StatusBadge";
import { FormField, FormSection } from "@/design-system/FormField";
import { KpiCard } from "@/design-system/KpiCard";
import { EmptyState } from "@/design-system/EmptyState";
import { Toolbar } from "@/design-system/Toolbar";
import { Panel } from "@/design-system/Panel";

// Canonical panel wrapper maps directly to standardized Panel
const WorkspacePanel = Panel;


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
  
  const [prices, setPrices] = useState<Record<string, { ltp: number; change: string; up: boolean; timestamp?: string; diff?: number; pct?: number; volume?: number }>>({});

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
        const newPrices: Record<string, { ltp: number; change: string; up: boolean; timestamp?: string; diff?: number; pct?: number; volume?: number }> = {};
        
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
            const volume = Number(q.volume || 0);
            
            newPrices[ins.symbol] = {
              ltp: ltp,
              diff: diff,
              pct: pct,
              change: `${diff >= 0 ? "+" : ""}${pct.toFixed(2)}%`,
              volume: volume,
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
    const interval = setInterval(fetchWatchlistQuotes, 2000);
    return () => clearInterval(interval);
  }, [watchlist]);

  // Listen for option chain contract selections and auto-add them to the watchlist
  useEffect(() => {
    const handleAddFromChain = (e: Event) => {
      const ins = (e as CustomEvent).detail as Instrument;
      if (!ins?.instrumentKey || !ins?.symbol) return;
      setWatchlist((prev) => {
        if (prev.some((w) => w.instrumentKey === ins.instrumentKey)) return prev;
        const updated = [...prev, ins];
        localStorage.setItem("valkyrie_watchlist", JSON.stringify(updated));
        return updated;
      });
    };
    window.addEventListener("valkyrie-add-to-watchlist", handleAddFromChain);
    return () => window.removeEventListener("valkyrie-add-to-watchlist", handleAddFromChain);
  }, []);

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
    <div className="flex flex-col h-full p-3 select-none">
      <h3 className="vdl-section text-slate-200 border-b border-subtle pb-2 mb-2 flex items-center justify-between select-none">
        <span>Watchlist</span>
        <div className="flex items-center gap-1.5">
          <span className="vdl-body text-slate-500 font-mono font-medium lowercase">{connectionStatus}</span>
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
              className="w-full bg-deep border border-subtle rounded pl-8 pr-3 py-1.5 vdl-body text-slate-300 focus:outline-none focus:border-cyan-500/40 font-sans"
            />
            {/* Search results popup */}
            {showSearchResults && searchResults.length > 0 && (
              <div className="absolute left-0 right-0 mt-1 bg-card border border-subtle rounded shadow-xl max-h-48 overflow-y-auto z-50 font-sans vdl-body">
                {searchResults.map((item) => (
                  <div
                    key={item.instrumentKey}
                    onClick={() => handleAddSymbol(item)}
                    className="flex justify-between items-center px-3 py-2 hover:bg-cyan-500/10 cursor-pointer transition-colors text-slate-200 border-b border-subtle/50"
                  >
                    <span>{item.symbol}</span>
                    <span className="vdl-body text-cyan-400 font-mono bg-cyan-950/40 px-1 py-0.5 rounded border border-cyan-500/10 font-semibold">{item.exchange}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Instruments list */}
          <div className="flex-1 overflow-y-auto flex flex-col gap-0.5 mt-1 pr-1 font-sans vdl-body scrollbar-thin scrollbar-thumb-white/5 scrollbar-track-transparent">
            {/* Header Row */}
            <div className="grid grid-cols-12 px-2 py-1 text-[11px] font-sans font-semibold text-slate-500 select-none shrink-0 border-b border-subtle tracking-wider uppercase">
              <span className="col-span-5 text-left">Symbol</span>
              <span className="col-span-3 text-right">Ltp</span>
              <span className="col-span-2 text-right">Chg%</span>
              <span className="col-span-2 text-right">Vol</span>
            </div>

            {filteredWatchlist.map((item, index) => {
              const priceInfo = prices[item.symbol] || { ltp: 0, change: "0.00%", up: true, timestamp: "", diff: 0, pct: 0, volume: 0 };
              const isSelected = currentInstrument?.symbol === item.symbol;
              const isPinned = pinned.includes(item.symbol);
              const fmtVol = (v: number) => v >= 1000000 ? `${(v/1000000).toFixed(1)}M` : v >= 1000 ? `${(v/1000).toFixed(0)}K` : String(v);

              return (
                <div
                  key={item.instrumentKey}
                  onClick={() => setInstrument(item)}
                  className={`grid grid-cols-12 items-center px-2 py-1 rounded cursor-pointer border transition-all group ${
                    isSelected
                      ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400 font-semibold"
                      : "bg-transparent border-transparent hover:bg-white/5 text-slate-300 hover:text-white"
                  }`}
                >
                  {/* Symbol & Pin indicator */}
                  <div className="col-span-5 flex items-center gap-1.5 min-w-0">
                    <button
                      onClick={(e) => togglePin(item.symbol, e)}
                      className="text-slate-600 hover:text-cyan-400 transition-colors cursor-pointer shrink-0"
                    >
                      <Star className={`w-3 h-3 ${isPinned ? "fill-cyan-400 text-cyan-400" : ""}`} />
                    </button>
                    
                    {/* Reorder Up/Down buttons (Hover-only) */}
                    <div className="flex flex-col text-[7px] text-slate-600 font-mono shrink-0 select-none mr-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button onClick={(e) => handleMoveUp(index, e)} className="hover:text-cyan-400 cursor-pointer">▲</button>
                      <button onClick={(e) => handleMoveDown(index, e)} className="hover:text-cyan-400 cursor-pointer">▼</button>
                    </div>

                    <div className="flex flex-col min-w-0 flex-1">
                      <span className={`truncate font-semibold text-[12px] font-sans ${isSelected ? "text-cyan-400" : "text-slate-200"}`}>{item.symbol}</span>
                    </div>
                  </div>

                  {/* LTP */}
                  <span className="col-span-3 text-right font-mono tabular-nums text-[12px]">
                    ₹{(priceInfo.ltp || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>

                  {/* Δ% */}
                  <span className={`col-span-2 text-right font-mono tabular-nums text-[12px] ${(priceInfo.diff || 0) >= 0 ? "text-emerald-450" : "text-rose-500"}`}>
                    {priceInfo.pct !== undefined ? `${priceInfo.pct >= 0 ? "+" : ""}${priceInfo.pct.toFixed(2)}%` : "—"}
                  </span>

                  {/* Volume & Delete */}
                  <div className="col-span-2 flex items-center justify-end gap-1.5 min-w-0">
                    <span className="font-mono tabular-nums text-[11px] text-slate-500">
                      {priceInfo.volume !== undefined ? fmtVol(priceInfo.volume) : "—"}
                    </span>
                    <button
                      onClick={(e) => handleDeleteSymbol(item.symbol, e)}
                      className="text-slate-600 hover:text-rose-500 transition-colors cursor-pointer font-sans text-[13px] shrink-0 ml-1 opacity-0 group-hover:opacity-100 transition-opacity"
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
  const [panicSubmitting, setPanicSubmitting] = useState(false);

  const handlePanicExit = async () => {
    if (!window.confirm("ARE YOU SURE YOU WANT TO TRIGGER AN EMERGENCY PANIC EXIT? This will instantly cancel all open broker orders and exit all active option positions at market price.")) {
      return;
    }
    
    setPanicSubmitting(true);
    try {
      console.log("[Panic Switch] Dispatching real-broker square-off command...");
      const res = await tradingApi.brokerPanicExit();
      alert(`Panic Exit Executed Successfully:\n${res.message || "All orders cancelled and positions closed."}`);
      window.dispatchEvent(new Event("valkyrie-portfolio-refresh"));
    } catch (err: any) {
      console.error("[Panic Switch] Square-off command failed:", err);
      alert(`Panic Exit Failed: ${err.message || "An unknown error occurred during square-off."}`);
    } finally {
      setPanicSubmitting(false);
    }
  };

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
      background: "#111827", // Matches --bg-base / bg-card
      text: "#9ca3af", // Matches --text-mute
      grid: "#1f1f22", // Matches --border-subtle
      border: "#1f1f22", // Matches --border-subtle
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
      localization: {
        timeFormatter: (timestamp: number) => {
          return new Date(timestamp * 1000).toLocaleString("en-IN", {
            timeZone: "Asia/Kolkata",
            hour12: false,
          });
        },
      },
      timeScale: {
        borderColor: themeColors.border,
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: (time: number, tickMarkType: number, locale: string) => {
          const date = new Date(time * 1000);
          const options: Intl.DateTimeFormatOptions = {
            timeZone: "Asia/Kolkata",
            hour12: false,
          };
          if (tickMarkType <= 2) {
            options.day = "numeric";
            options.month = "short";
          } else {
            options.hour = "2-digit";
            options.minute = "2-digit";
          }
          return date.toLocaleString("en-IN", options);
        },
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

  // Sync current LTP when backend tick updates spot price (real WebSocket updates)
  useEffect(() => {
    if (status && status.spot_price > 0 && selectedInstrument) {
      const isIndex = selectedInstrument.instrumentKey.includes("NSE_INDEX") || 
                      selectedInstrument.instrumentKey.includes("BSE_INDEX") || 
                      selectedInstrument.symbol === "NIFTY 50" || 
                      selectedInstrument.symbol === "BANKNIFTY" || 
                      selectedInstrument.symbol === "FINNIFTY" ||
                      selectedInstrument.symbol === "MIDCPNIFTY" ||
                      selectedInstrument.symbol === "SENSEX" ||
                      selectedInstrument.symbol === "BANKEX";
      if (isIndex && candleSeriesRef.current) {
        const ltp = status.spot_price;
        const lastCandle = fetchedCandlesRef.current[fetchedCandlesRef.current.length - 1];
        if (lastCandle) {
          const updatedCandle = {
            time: lastCandle.time,
            open: lastCandle.open,
            high: Math.max(lastCandle.high, ltp),
            low: lastCandle.low === 0 ? ltp : Math.min(lastCandle.low, ltp),
            close: ltp,
          };
          candleSeriesRef.current.update(updatedCandle);
        }
        setCurrentLtp(ltp);
      }
    }
  }, [status, selectedInstrument]);

  // Real-time dynamic chart ticking via real REST Ticket Quotes
  useEffect(() => {
    const handleRealTick = (e: Event) => {
      const ltp = (e as CustomEvent).detail.price;
      const lastCandle = fetchedCandlesRef.current[fetchedCandlesRef.current.length - 1];
      if (lastCandle && candleSeriesRef.current) {
        const updatedCandle = {
          time: lastCandle.time,
          open: lastCandle.open,
          high: Math.max(lastCandle.high, ltp),
          low: lastCandle.low === 0 ? ltp : Math.min(lastCandle.low, ltp),
          close: ltp,
        };
        candleSeriesRef.current.update(updatedCandle);
        setCurrentLtp(ltp);
      }
    };
    window.addEventListener("valkyrie-real-quote-update", handleRealTick);
    return () => {
      window.removeEventListener("valkyrie-real-quote-update", handleRealTick);
    };
  }, [selectedInstrument]);

  // Ref to store fetched candles for indicator recalculation
  const fetchedCandlesRef = useRef<any[]>([]);

  // Bug #2 fix — fetch real candles from Upstox whenever instrument or timeframe changes
  useEffect(() => {
    if (!selectedInstrument || !candleSeriesRef.current || !volumeSeriesRef.current) return;
    let cancelled = false;
    const load = async () => {
      try {
        const days = ["1m", "3m"].includes(selectedTimeframe) ? 3 : ["5m", "15m"].includes(selectedTimeframe) ? 10 : 45;
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
    <div className="flex flex-col h-full bg-transparent overflow-hidden">
      {/* Top Toolbar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-deep border-b border-subtle select-none shrink-0 font-sans vdl-body">
        <div className="flex items-center gap-2">
          {/* Symbol dropdown selection */}
          <select
            value={selectedInstrument?.symbol || "NIFTY 50"}
            onChange={(e) => {
              const matched = AVAILABLE_INSTRUMENTS.find((i) => i.symbol === e.target.value);
              if (matched) setInstrument(matched);
            }}
            className="bg-card rounded px-2 py-0.5 text-cyan-400 font-semibold focus:outline-none"
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

          {/* Timeframe Segmented Control */}
          <div className="tab-container flex select-none font-mono">
            {(["1m", "5m", "15m", "1h"] as const).map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf as Timeframe)}
                className={`tab-item ${selectedTimeframe === tf ? "active" : ""}`}
              >
                {tf}
              </button>
            ))}
          </div>

          <div className="h-4 w-px bg-white/5 mx-1" />

          {/* Indicators Button */}
          <div className="relative">
            <button
              onClick={() => toggleIndicator("VWAP")}
              className={`px-2 py-0.5 rounded border transition-colors cursor-pointer vdl-body ${
                activeIndicators.includes("VWAP")
                  ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400 font-bold"
                  : "bg-card text-slate-400 hover:text-slate-200"
              }`}
            >
              VWAP
            </button>
          </div>
          <button
            onClick={() => toggleIndicator("EMA")}
            className={`px-2 py-0.5 rounded border transition-colors cursor-pointer vdl-body ${
              activeIndicators.includes("EMA")
                ? "bg-amber-500/10 border-amber-500/30 text-amber-400 font-bold"
                : "bg-card text-slate-400 hover:text-slate-200"
            }`}
          >
            EMA (9/21)
          </button>
        </div>

        <div className="flex items-center gap-2">
          {/* Chart loading indicator */}
          {chartLoading && (
            <span className="flex items-center gap-1 vdl-body text-cyan-400 font-mono animate-pulse">
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
                : "bg-card text-slate-400 hover:text-slate-200"
            }`}
            title="Drawing Tools"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
          </button>

          {/* Panic Exit Kill Switch */}
          <button
            onClick={handlePanicExit}
            disabled={panicSubmitting}
            className={`px-3 py-1 rounded border font-semibold vdl-body transition-all select-none cursor-pointer flex items-center gap-1.5 shadow-lg ${
              panicSubmitting
                ? "bg-slate-800 border-slate-700 text-slate-500 cursor-not-allowed"
                : "bg-rose-500/10 hover:bg-rose-500 border-rose-500/20 hover:border-rose-500 text-rose-400 hover:text-slate-950 shadow-rose-500/5 hover:shadow-rose-500/20"
            }`}
            title="Emergency Panic Exit (Cancel Orders & Square Off)"
          >
            <AlertTriangle className="w-3.5 h-3.5 text-rose-500 hover:text-slate-950 transition-colors" />
            {panicSubmitting ? "SQUARING OFF..." : "PANIC EXIT"}
          </button>
        </div>
      </div>

      {/* Main Layout Workspace with Chart */}
      <div className="flex-1 min-h-0 relative flex flex-row">
        {/* Drawing Sidebar HUD */}
        {showDrawMenu && (
          <div className="w-9 border-r border-subtle bg-deep flex flex-col items-center py-3 gap-3 shrink-0 select-none">
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
          <div className="absolute top-3 left-4 bg-deep/90 border border-subtle px-2 py-1 rounded vdl-body font-mono text-slate-300 flex items-center gap-2 shadow-md">
            <span className="font-semibold text-slate-400">Ltp:</span>
            <span className="text-emerald-400 font-semibold">
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
    const handleRefresh = () => {
      fetchData();
    };
    window.addEventListener("valkyrie-portfolio-refresh", handleRefresh);

    const interval = setInterval(fetchData, 30000); // 30s auto-refresh
    return () => {
      clearInterval(interval);
      window.removeEventListener("valkyrie-portfolio-refresh", handleRefresh);
    };
  }, []);

  const formatCurrency = (val: any) => {
    if (val === undefined || val === null) return "₹0.00";
    return `₹${Number(val).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  return (
    <div className="p-3 flex flex-col gap-2 select-none border-t border-subtle">
      <h3 className="vdl-section text-slate-200 border-b border-subtle pb-1.5 flex items-center justify-between">
        <span>Broker account</span>
        <div className="flex items-center gap-1">
          <span className={`w-1.5 h-1.5 rounded-full ${brokerConnected ? "bg-emerald-400 animate-pulse" : "bg-rose-500 animate-pulse"}`} />
          <span className="vdl-body font-mono text-slate-500">
            {brokerConnected ? "Connected" : "Disconnected"}
          </span>
        </div>
      </h3>

      <div className="grid grid-cols-2 gap-2 vdl-body bg-deep border border-subtle p-2 rounded font-sans">
        <div className="flex flex-col gap-0.5">
          <span className="vdl-body text-slate-500">Client name</span>
          <span className="font-semibold text-slate-200 truncate">
            {profile?.user_name || (loading ? "Loading..." : "N/A")}
          </span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="vdl-body text-slate-500">Client ID</span>
          <span className="font-semibold text-slate-200 font-mono">
            {profile?.user_id || (loading ? "Loading..." : "N/A")}
          </span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="vdl-body text-slate-500">Broker</span>
          <span className="font-semibold text-slate-200">
            {profile?.broker || "UPSTOX"}
          </span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="vdl-body text-slate-500">Token status</span>
          <span className={`font-semibold ${tokenStatus === "VALID" ? "text-emerald-400" : "text-rose-400 animate-pulse"}`}>
            {tokenStatus}
          </span>
        </div>
      </div>

      {error && (
        <div className="p-2 bg-rose-950/40 border border-rose-500/20 text-rose-400 vdl-body rounded flex items-center gap-1.5 font-mono">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span className="truncate" title={error}>{error}</span>
        </div>
      )}

      <div className="flex flex-col gap-1.5 font-mono vdl-body px-1">
        <div className="flex justify-between items-center text-slate-400 py-0.5 border-b border-subtle/50">
          <span>Available Margin</span>
          <span className="font-semibold text-cyan-400">
            {loading && !funds ? "Syncing..." : formatCurrency(funds?.equity?.available_margin)}
          </span>
        </div>
        <div className="flex justify-between items-center text-slate-400 py-0.5 border-b border-subtle/50">
          <span>Used Margin</span>
          <span className="font-semibold text-slate-200">
            {loading && !funds ? "Syncing..." : formatCurrency(funds?.equity?.used_margin)}
          </span>
        </div>
        <div className="flex justify-between items-center text-slate-400 py-0.5 border-b border-subtle/50">
          <span>Available Funds</span>
          <span className="font-semibold text-slate-200">
            {loading && !funds ? "Syncing..." : formatCurrency(funds?.equity?.available_margin)}
          </span>
        </div>
        <div className="flex justify-between items-center text-slate-400 py-0.5 border-b border-subtle/50">
          <span>Payin Amount</span>
          <span className="font-semibold text-slate-200">
            {loading && !funds ? "Syncing..." : formatCurrency(funds?.equity?.payin_amount)}
          </span>
        </div>
        <div className="flex justify-between items-center text-slate-400 py-0.5 border-b border-subtle/50">
          <span>Span Margin</span>
          <span className="font-semibold text-slate-200">
            {loading && !funds ? "Syncing..." : formatCurrency(funds?.equity?.span_margin)}
          </span>
        </div>
        <div className="flex justify-between items-center text-slate-400 py-0.5">
          <span>Exposure Margin</span>
          <span className="font-semibold text-slate-200">
            {loading && !funds ? "Syncing..." : formatCurrency(funds?.equity?.exposure_margin)}
          </span>
        </div>
      </div>

      <div className="flex justify-between items-center vdl-body text-slate-500 font-mono border-t border-subtle pt-1.5 mt-0.5">
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
  const [orderType, setOrderType] = useState<"MARKET" | "LIMIT" | "SL">("MARKET");
  const [limitPrice, setLimitPrice] = useState(0);
  const [triggerPrice, setTriggerPrice] = useState(0);
  const isSubmittingRef = useRef(false);

  const [analytics, setAnalytics] = useState<any>(null);

  // Sync with active contract option analytics from OptionChainPanel
  useEffect(() => {
    const handleAnalyticsUpdate = (e: Event) => {
      const customEvent = e as CustomEvent;
      if (customEvent.detail === null) {
        setAnalytics(null);
      } else if (customEvent.detail && customEvent.detail.instrumentKey === currentInstrument?.instrumentKey) {
        setAnalytics(customEvent.detail);
      }
    };
    window.addEventListener("valkyrie-active-instrument-analytics", handleAnalyticsUpdate);
    return () => {
      window.removeEventListener("valkyrie-active-instrument-analytics", handleAnalyticsUpdate);
    };
  }, [currentInstrument?.instrumentKey]);

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
    setAnalytics(null);

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

          // Dispatch real quote update to chart
          window.dispatchEvent(new CustomEvent("valkyrie-real-quote-update", { detail: { price: ltp } }));
        }
      } catch (err) {
        console.error("Failed to fetch quote in order ticket:", err);
      } finally {
        if (isMounted) setQuoteLoading(false);
      }
    };
    
    fetchQuote();
    const interval = setInterval(fetchQuote, 2000);
    
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
    }, 3000);
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

    if (isSubmittingRef.current) {
      console.warn("Order placement blocked: parallel submission or double-click prevented.");
      return;
    }
    isSubmittingRef.current = true;
    setOrderSubmitting(true);
    setOrderError(null);
    setOrderSuccess(null);

    console.log(`[Order Safeguard] Transition to SUBMITTING state. Side: ${orderSide}, Qty: ${quantity}, Contract: ${currentInstrument.symbol}`);

    // Pre-flight Daily Loss Guard Check
    const totalRealizedPnL = positions.reduce((acc, pos) => acc + Number(pos.realised || 0), 0);
    const dailyLimit = 20000; // Configured dynamically on backend or fallback
    if (totalRealizedPnL <= -dailyLimit) {
      const errorMsg = `Order Blocked Locally: Daily Realized Loss Limit of ₹${dailyLimit.toLocaleString("en-IN")} Exceeded (Current: ₹${totalRealizedPnL.toLocaleString("en-IN")}). Lockout active.`;
      console.error(`[Order Safeguard] ${errorMsg}`);
      setOrderError(errorMsg);
      addEvent({ type: "error", message: errorMsg, workspace: "Trading" });
      
      isSubmittingRef.current = false;
      setOrderSubmitting(false);
      return;
    }

    if (brokerMarginReq > availableMargin) {
      const errorMsg = `Order Blocked Locally: Insufficient Margin. Required: ₹${brokerMarginReq.toLocaleString("en-IN", { minimumFractionDigits: 2 })}, Available: ₹${availableMargin.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
      console.error(`[Order Safeguard] ${errorMsg}`);
      setOrderError(errorMsg);
      addEvent({ type: "error", message: errorMsg, workspace: "Trading" });
      
      isSubmittingRef.current = false;
      setOrderSubmitting(false);
      return;
    }

    try {
      const result = await tradingApi.placeBrokerOrder({
        instrument_key: currentInstrument.instrumentKey,
        quantity,
        transaction_type: orderSide,
        order_type: orderType === "SL" ? "LIMIT" : orderType,
        product: productType,
        price: entryPrice,
        trigger_price: triggerPrice > 0 ? triggerPrice : 0,
        stop_loss: stopLoss > 0 ? stopLoss : 0,
        target: targetPrice > 0 ? targetPrice : 0,
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
      isSubmittingRef.current = false;
      setOrderSubmitting(false);
      console.log(`[Order Safeguard] Transition to IDLE state.`);
    }
  };

  const closePosition = async (sym?: string) => {
    await handlePlaceOrder("SELL");
    fetchPositions();
  };

  const entryPriceVal = orderType === "MARKET" ? contractPrice : limitPrice;
  const hasSL = stopLoss > 0;
  const hasTarget = targetPrice > 0;
  
  const riskAmount = hasSL ? Math.abs(entryPriceVal - stopLoss) * quantity : 0;
  const riskPct = hasSL && entryPriceVal > 0 ? (Math.abs(entryPriceVal - stopLoss) / entryPriceVal) * 100 : 0;
  
  const rewardAmountVal = hasTarget ? Math.abs(targetPrice - entryPriceVal) * quantity : 0;
  const rrRatio = (hasSL && rewardAmountVal > 0) ? (rewardAmountVal / (Math.abs(entryPriceVal - stopLoss) * quantity)).toFixed(1) : "N/A";

  const totalUnrealizedPnL = positions.reduce((acc, pos) => acc + Number(pos.unrealised || 0), 0);
  const totalRealizedPnL = positions.reduce((acc, pos) => acc + Number(pos.realised || 0), 0);
  const totalPnL = totalUnrealizedPnL + totalRealizedPnL;

  return (
    <div className="flex flex-col h-full bg-transparent overflow-hidden">
      {/* Hero P&L Anchor */}
      <div className="p-3 bg-deep border-b border-subtle select-none flex flex-col gap-2 shrink-0">
        <div className="flex flex-col items-center justify-center">
          <span className="text-[12px] font-semibold text-slate-400 font-sans">Net P&L</span>
          <span className={`text-[42px] font-semibold font-mono tabular-nums leading-none mt-1 ${
            totalPnL > 0 ? "text-emerald-400" : totalPnL < 0 ? "text-rose-500" : "text-slate-350"
          }`}>
            {totalPnL > 0 ? "+" : ""}₹{totalPnL.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </div>
        
        <div className="grid grid-cols-2 gap-2 border-t border-subtle/50 pt-2 text-center">
          <div className="flex flex-col">
            <span className="text-[12px] text-slate-500 font-sans">Realized</span>
            <span className={`text-[20px] font-semibold font-mono tabular-nums mt-0.5 ${
              totalRealizedPnL > 0 ? "text-emerald-400" : totalRealizedPnL < 0 ? "text-rose-500" : "text-slate-400"
            }`}>
              {totalRealizedPnL > 0 ? "+" : ""}₹{totalRealizedPnL.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
          <div className="flex flex-col border-l border-subtle/50">
            <span className="text-[12px] text-slate-500 font-sans">Unrealized</span>
            <span className={`text-[20px] font-semibold font-mono tabular-nums mt-0.5 ${
              totalUnrealizedPnL > 0 ? "text-emerald-400" : totalUnrealizedPnL < 0 ? "text-rose-500" : "text-slate-400"
            }`}>
              {totalUnrealizedPnL > 0 ? "+" : ""}₹{totalUnrealizedPnL.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
        </div>
      </div>

      {/* Order Pad Card */}
      <div className="p-3 flex flex-col gap-1.5 shrink-0">
        <h3 className="vdl-section text-slate-200 border-b border-subtle pb-1.5 flex items-center justify-between select-none">
          <span>Order ticket</span>
          <span className="vdl-body font-mono text-slate-500">{currentAccount.name}</span>
        </h3>

        {/* Selected Instrument Info with Real-time Quote Panel */}
        <div className="flex flex-col gap-1 bg-deep border border-subtle p-2 rounded font-mono vdl-body select-none text-slate-300">
          <div className="flex justify-between items-center">
            <span>Contract:</span>
            <span className="font-semibold text-cyan-400">
              {currentInstrument ? currentInstrument.symbol : "NONE SELECTED"}
            </span>
          </div>
          {currentInstrument && (
            <>
              {(() => {
                const details = parseInstrument(currentInstrument.symbol);
                if (details.type === "CE" || details.type === "PE") {
                  return (
                    <div className="grid grid-cols-3 gap-1 mt-0.5 border-t border-subtle pt-1.5 vdl-body text-slate-400">
                      <div>
                        <span>Type: </span>
                        <span className={`font-semibold ${details.type === "CE" ? "text-emerald-400" : "text-rose-400"}`}>{details.type}</span>
                      </div>
                      <div>
                        <span>Strike: </span>
                        <span className="font-semibold text-slate-200">{details.strike}</span>
                      </div>
                      <div>
                        <span>Expiry: </span>
                        <span className="font-semibold text-slate-200">{details.expiry}</span>
                      </div>
                    </div>
                  );
                }
                return null;
              })()}
              <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 mt-0.5 border-t border-subtle pt-1.5 vdl-body text-slate-400">
                <div className="flex justify-between">
                  <span>Ltp:</span>
                  <span className="text-slate-200 font-semibold">₹{contractPrice.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Updated:</span>
                  <span className="text-slate-500">{lastUpdated || "N/A"}</span>
                </div>
                <div className="flex justify-between">
                  <span>Bid:</span>
                  <span className="text-emerald-400 font-semibold">₹{bidPrice.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Ask:</span>
                  <span className="text-rose-400 font-semibold">₹{askPrice.toFixed(2)}</span>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Side Selector Toggle */}
        <div className="tab-container grid grid-cols-2 select-none shrink-0">
          <button
            onClick={() => setSide("BUY")}
            className={`tab-item ${side === "BUY" ? "active text-emerald-400 bg-emerald-500/10 font-bold" : ""}`}
          >
            Buy
          </button>
          <button
            onClick={() => setSide("SELL")}
            className={`tab-item ${side === "SELL" ? "active text-rose-500 bg-rose-500/10 font-bold" : ""}`}
          >
            Sell
          </button>
        </div>

        {/* Action Feedbacks */}
        {orderError && (
          <div className="p-1.5 bg-rose-950/40 border border-rose-500/20 text-rose-400 vdl-body rounded flex items-center gap-1.5 font-sans animate-pulse">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            <span className="truncate">{orderError}</span>
          </div>
        )}
        {orderSuccess && (
          <div className="p-1.5 bg-emerald-950/40 border border-emerald-500/20 text-emerald-400 vdl-body rounded flex items-center gap-1.5 font-sans">
            <CheckCircle2 className="w-3.5 h-3.5 shrink-0 text-emerald-400" />
            <span className="truncate">{orderSuccess}</span>
          </div>
        )}

        {/* Product Type (MIS/NRML/CNC) */}
        <div className="flex flex-col gap-0.5 select-none">
          <span className="vdl-body text-slate-500 font-semibold">Product Type</span>
          <div className="tab-container grid grid-cols-3">
            {(["MIS", "NRML", "CNC"] as const).map((type) => (
              <button
                key={type}
                onClick={() => setProductType(type)}
                className={`tab-item ${productType === type ? "active" : ""}`}
              >
                {type}
              </button>
            ))}
          </div>
        </div>

        {/* Quantity (Lots / Units) */}
        <div className="flex flex-col gap-0.5">
          <div className="flex justify-between items-center">
            <span className="vdl-body text-slate-500 font-semibold">Quantity</span>
            <span className="vdl-body text-slate-500 font-mono">Lot: {lotSize}</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setQuantity((q) => Math.max(lotSize, q - lotSize))}
              className="bg-deep border border-subtle hover:border-cyan-500/40 w-8 py-0.5 rounded text-slate-300 font-semibold hover:text-white transition-all cursor-pointer text-center vdl-body"
            >
              -
            </button>
            <input
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(Math.max(1, Number(e.target.value)))}
              className="flex-1 bg-deep border border-subtle rounded py-0.5 text-center font-mono vdl-body text-slate-200 focus:outline-none focus:border-cyan-500/40"
            />
            <button
              onClick={() => setQuantity((q) => q + lotSize)}
              className="bg-deep border border-subtle hover:border-cyan-500/40 w-8 py-0.5 rounded text-slate-300 font-semibold hover:text-white transition-all cursor-pointer text-center vdl-body"
            >
              +
            </button>
          </div>
        </div>

        {/* Order Type Toggle */}
        <div className="flex flex-col gap-0.5 select-none">
          <span className="vdl-body text-slate-500 font-semibold">Order Type</span>
          <div className="tab-container grid grid-cols-3">
            {(["MARKET", "LIMIT", "SL"] as const).map((type) => (
              <button
                key={type}
                onClick={() => setOrderType(type)}
                className={`tab-item ${orderType === type ? "active" : ""}`}
              >
                {type}
              </button>
            ))}
          </div>
        </div>

        {/* Limit Price / Trigger Price */}
        <div className="grid grid-cols-2 gap-2">
          <div className="flex flex-col gap-0.5">
            <span className="vdl-body text-slate-500">Limit Price</span>
            <input
              type="number"
              disabled={orderType === "MARKET"}
              value={limitPrice || ""}
              onChange={(e) => setLimitPrice(Number(e.target.value))}
              className="w-full bg-deep border border-subtle rounded py-0.5 px-2 font-mono text-center vdl-body text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:border-cyan-500/40"
            />
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="vdl-body text-slate-500">Trigger Price</span>
            <input
              type="number"
              value={triggerPrice || ""}
              onChange={(e) => setTriggerPrice(Number(e.target.value))}
              className="w-full bg-deep border border-subtle rounded py-0.5 px-2 font-mono text-center vdl-body text-slate-200 focus:outline-none focus:border-cyan-500/40"
            />
          </div>
        </div>

        {/* Risk Targets (Optional for SL / Target placement) */}
        <div className="grid grid-cols-2 gap-2">
          <div className="flex flex-col gap-0.5">
            <div className="flex justify-between">
              <span className="vdl-body text-slate-500 font-semibold">Stop loss</span>
              <span className="vdl-body text-slate-500 font-mono">Opt</span>
            </div>
            <input
              type="number"
              placeholder="SL Price"
              value={stopLoss || ""}
              onChange={(e) => setStopLoss(Number(e.target.value))}
              className="w-full bg-deep border border-subtle rounded py-0.5 px-2 font-mono text-center vdl-body text-slate-200 focus:outline-none focus:border-cyan-500/40"
            />
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="vdl-body text-slate-500">Target price</span>
            <input
              type="number"
              placeholder="Target Price"
              value={targetPrice || ""}
              onChange={(e) => setTargetPrice(Number(e.target.value))}
              className="w-full bg-deep border border-subtle rounded py-0.5 px-2 font-mono text-center vdl-body text-slate-200 focus:outline-none focus:border-cyan-500/40"
            />
          </div>
        </div>

        {/* Real Broker Margin HUD & Risk Estimation */}
        <div className="flex flex-col gap-1 bg-deep border border-subtle p-2 rounded font-mono vdl-body text-slate-500 select-none">
          <div className="flex justify-between items-center border-b border-subtle pb-1 mb-1">
            <span>Risk status:</span>
            <span className={`px-2 py-0.5 rounded border vdl-body transition-all ${
              brokerMarginReq > availableMargin
                ? "text-rose-500 bg-rose-500/10 border-rose-500/20 animate-pulse font-extrabold"
                : (availableMargin > 0 && brokerMarginReq / availableMargin > 0.5)
                  ? "text-amber-400 bg-amber-500/10 border-amber-500/20 font-bold"
                  : "text-emerald-400 bg-emerald-500/10 border-emerald-500/20 font-semibold"
            }`}>
              {brokerMarginReq > availableMargin ? "BLOCKED" : (availableMargin > 0 && brokerMarginReq / availableMargin > 0.5) ? "WARNING" : "SAFE"}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-0.5">
              <span>REQUIRED MARGIN:</span>
              <span className="font-semibold text-slate-300">
                ₹{brokerMarginReq.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span>AVAILABLE MARGIN:</span>
              <span className="font-semibold text-slate-300">
                ₹{availableMargin.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 border-t border-subtle/50 pt-1 mt-1">
            <div className="flex flex-col gap-0.5">
              <span>POST-TRADE MARGIN:</span>
              <span className="font-semibold text-slate-300">
                ₹{(availableMargin - brokerMarginReq).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span>MARGIN UTILIZATION:</span>
              <span className="font-semibold text-slate-300">
                {(availableMargin > 0 ? (brokerMarginReq / availableMargin) * 100 : 0).toFixed(2)}%
              </span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 border-t border-subtle/50 pt-1.5 mt-1 select-none">
            <div className="col-span-2 flex flex-col gap-1">
              <span className="vdl-body text-slate-500 font-semibold">Risk estimation</span>
              
              {!hasSL ? (
                <div className="flex flex-col gap-0.5 bg-amber-500/5 p-1.5 rounded border border-amber-500/20 font-mono vdl-body">
                  <div className="flex justify-between">
                    <span className="text-slate-500">RISK ESTIMATE:</span>
                    <span className="font-semibold text-amber-400">Undefined</span>
                  </div>
                  <div className="flex justify-between mt-0.5">
                    <span className="text-slate-500">STATUS:</span>
                    <span className="font-semibold text-amber-400 animate-pulse font-sans">Warning</span>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col gap-0.5 bg-card/20 border border-subtle/50 p-1.5 rounded font-mono vdl-body">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Max loss:</span>
                    <span className="font-semibold text-rose-400">
                      ₹{riskAmount.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Risk percent:</span>
                    <span className="font-semibold text-rose-400">{riskPct.toFixed(2)}%</span>
                  </div>
                </div>
              )}

              {hasTarget && (
                <div className="flex flex-col gap-0.5 bg-card/20 border border-subtle/50 p-1.5 rounded font-mono vdl-body">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Potential reward:</span>
                    <span className="font-semibold text-emerald-400">
                      ₹{rewardAmountVal.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  {hasSL && (
                    <div className="flex justify-between border-t border-subtle/50 pt-0.5 mt-0.5">
                      <span className="text-slate-500">Risk/reward ratio:</span>
                      <span className="font-semibold text-cyan-400">1:{rrRatio}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
          {brokerMarginError && (
            <span className="vdl-body text-rose-400 mt-1 font-sans animate-pulse">
              * {brokerMarginError}
            </span>
          )}
        </div>

        {/* Primary Action Buttons — Maximum Visual Weight */}
        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-subtle">
          <button
            onClick={() => handlePlaceOrder("BUY")}
            disabled={orderSubmitting || !currentInstrument}
            className={`btn-buy w-full ${
              orderSubmitting ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
            }`}
          >
            {orderSubmitting ? "Submitting..." : "Buy"}
          </button>
          <button
            onClick={() => handlePlaceOrder("SELL")}
            disabled={orderSubmitting || !currentInstrument}
            className={`btn-sell w-full ${
              orderSubmitting ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
            }`}
          >
            {orderSubmitting ? "Submitting..." : "Sell"}
          </button>
        </div>
      </div>

      {/* Broker Account Panel */}
      <BrokerAccountPanel />

      {/* Option Greeks & Analytics HUD */}
      {analytics && (
        <div className="p-3 flex flex-col gap-2 font-mono vdl-body select-none text-slate-300 border-t border-subtle">
          <div className="text-[12px] font-sans font-semibold text-slate-200 border-b border-subtle pb-1 flex justify-between items-center">
            <span>Option analytics</span>
            <span className={`px-1 py-0.5 rounded vdl-body font-sans font-semibold border ${
              analytics.domSignal === "BULLISH" ? "text-emerald-400 bg-emerald-950/40 border-emerald-700/30" :
              analytics.domSignal === "BEARISH" ? "text-rose-400 bg-rose-950/40 border-rose-700/30" :
              "text-slate-400 bg-card/40"
            }`}>
              DOM: {analytics.domSignal}
            </span>
          </div>

          {/* Greeks Grid */}
          <div className="grid grid-cols-5 gap-1.5 border-b border-subtle pb-2 text-center vdl-body text-slate-400">
            <div>
              <div className="text-slate-500">Delta</div>
              <div className="font-semibold text-slate-200 mt-0.5">{analytics.delta.toFixed(3)}</div>
            </div>
            <div>
              <div className="text-slate-500">Gamma</div>
              <div className="font-semibold text-slate-200 mt-0.5">{analytics.gamma.toFixed(5)}</div>
            </div>
            <div>
              <div className="text-slate-500">Theta</div>
              <div className="font-semibold text-slate-200 mt-0.5">{analytics.theta.toFixed(1)}</div>
            </div>
            <div>
              <div className="text-slate-500">Vega</div>
              <div className="font-semibold text-slate-200 mt-0.5">{analytics.vega.toFixed(3)}</div>
            </div>
            <div>
              <div className="text-slate-500">Iv%</div>
              <div className="font-semibold text-amber-400 mt-0.5">{analytics.iv.toFixed(1)}%</div>
            </div>
          </div>

          {/* Market Data Grid */}
          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 pt-0.5">
            <div className="flex justify-between">
              <span className="text-slate-500">OI:</span>
              <span className="text-slate-300 font-semibold">{analytics.oi >= 1000000 ? `${(analytics.oi/1000000).toFixed(2)}M` : analytics.oi.toLocaleString("en-IN")}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">PCR:</span>
              <span className="text-slate-300 font-semibold">{analytics.pcr.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">OI Change:</span>
              <span className={`font-semibold ${analytics.oiChange > 0 ? "text-emerald-400" : analytics.oiChange < 0 ? "text-rose-400" : "text-slate-500"}`}>
                {analytics.oiChange > 0 ? "+" : ""}{analytics.oiChange >= 1000000 ? `${(analytics.oiChange/1000000).toFixed(2)}M` : analytics.oiChange.toLocaleString("en-IN")}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">OI Chg %:</span>
              <span className={`font-semibold ${analytics.oiChange > 0 ? "text-emerald-400" : analytics.oiChange < 0 ? "text-rose-400" : "text-slate-500"}`}>
                {analytics.oiChange > 0 ? "+" : ""}{analytics.oiPct.toFixed(1)}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Volume:</span>
              <span className="text-slate-300 font-semibold">{analytics.volume >= 1000000 ? `${(analytics.volume/1000000).toFixed(2)}M` : analytics.volume.toLocaleString("en-IN")}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Spread:</span>
              <span className="text-amber-400 font-semibold">₹{analytics.spread.toFixed(2)} ({((analytics.spread / (analytics.ltp || 1)) * 100).toFixed(2)}%)</span>
            </div>
          </div>

          {/* DOM Buy/Sell Ratio Progress Bar */}
          <div className="mt-1 border-t border-subtle pt-2 flex flex-col gap-1 select-none">
            <div className="flex justify-between vdl-body text-slate-500">
              <span>Buy Qty (Bid): {analytics.bidQty.toLocaleString()}</span>
              <span>Ask Qty (Ask): {analytics.askQty.toLocaleString()}</span>
            </div>
            <div className="w-full bg-rose-500/20 h-1.5 rounded overflow-hidden flex">
              <div 
                className="bg-emerald-500 h-full transition-all duration-300"
                style={{ width: `${(analytics.domRatio * 100).toFixed(1)}%` }}
              />
            </div>
            <div className="flex justify-between text-[7px] text-slate-600 font-mono mt-0.5">
              <span>{(analytics.domRatio * 100).toFixed(1)}%</span>
              <span>Ratio: {(analytics.bidQty / (analytics.askQty || 1)).toFixed(2)}x</span>
              <span>{((1 - analytics.domRatio) * 100).toFixed(1)}%</span>
            </div>
          </div>
        </div>
      )}

      {/* Mini Position Summary Panel - Sync'd to Broker Account */}
      <div className="p-3 flex flex-col gap-2 flex-1 min-h-0 select-none border-t border-subtle">
        <span className="vdl-section text-slate-200 border-b border-subtle pb-1.5">
          Open positions ({positions.length})
        </span>
        <div className="flex-1 overflow-y-auto flex flex-col gap-1.5 pr-1 font-sans vdl-body scrollbar-thin scrollbar-thumb-white/5">
          {positions.length > 0 ? (
            positions.map((pos) => {
              const qty = Number(pos.quantity || 0);
              return (
                <div 
                  key={`${pos.instrument_token}_${pos.product}`}
                  className="p-2 rounded bg-deep border border-subtle flex flex-col gap-1 relative group"
                >
                  <div className="flex justify-between items-center">
                    <span className="font-semibold text-slate-200">{pos.trading_symbol}</span>
                    <button 
                      onClick={() => closePosition(pos.trading_symbol)}
                      className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-rose-400 transition-all absolute right-2 top-2 cursor-pointer"
                      title="Squareoff Position"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="grid grid-cols-4 vdl-body text-slate-400 font-mono">
                    <div className="flex flex-col">
                      <span className="vdl-body text-slate-600 font-sans">Side</span>
                      <span className={qty > 0 ? "text-emerald-400 font-bold" : qty < 0 ? "text-rose-400 font-bold" : "text-slate-500"}>
                        {qty > 0 ? "LONG" : qty < 0 ? "SHORT" : "CLOSED"}
                      </span>
                    </div>
                    <div className="flex flex-col text-right">
                      <span className="vdl-body text-slate-600 font-sans">Qty</span>
                      <span>{qty}</span>
                    </div>
                    <div className="flex flex-col text-right">
                      <span className="vdl-body text-slate-600 font-sans">Avg/LTP</span>
                      <span>₹{Number(pos.average_price || pos.buy_price || 0).toFixed(1)}/₹{Number(pos.last_price || 0).toFixed(1)}</span>
                    </div>
                    <div className="flex flex-col text-right">
                      <span className="vdl-body text-slate-600 font-sans">PnL</span>
                      <span className={`font-semibold ${Number(pos.unrealised || 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {Number(pos.unrealised || 0) >= 0 ? "+" : ""}₹{Number(pos.unrealised || 0).toLocaleString("en-IN", { maximumFractionDigits: 1 })}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="empty-state flex-1">
              <span>No active open positions.</span>
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

  // Sync option chain underlying when watchlist instrument changes
  useEffect(() => {
    if (!currentInstrument) return;
    const sym = currentInstrument.symbol.toUpperCase();
    let targetUnderlying = "NIFTY";
    if (sym.includes("BANKNIFTY") || currentInstrument.instrumentKey.includes("Nifty Bank")) {
      targetUnderlying = "BANKNIFTY";
    } else if (sym.includes("FINNIFTY") || currentInstrument.instrumentKey.includes("Nifty Fin")) {
      targetUnderlying = "FINNIFTY";
    } else if (sym.includes("MIDCPNIFTY") || sym.includes("MID SELECT")) {
      targetUnderlying = "MIDCPNIFTY";
    } else if (sym.includes("NIFTY") || currentInstrument.instrumentKey.includes("Nifty 50")) {
      targetUnderlying = "NIFTY";
    } else {
      targetUnderlying = sym;
    }

    const isOption = currentInstrument.instrumentKey.includes("NSE_FO") || 
                     currentInstrument.instrumentKey.includes("BSE_FO") ||
                     sym.includes(" CE") || 
                     sym.includes(" PE");

    if (isOption) {
      // If it is a specific option contract, prevent the auto-ATM hotswap from overwriting it
      lastUnderlyingRef.current = targetUnderlying;
    }
    
    setUnderlying(targetUnderlying);
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
      const sym = currentInstrument?.symbol?.toUpperCase() || "";
      let currentInstrumentIndex = "NIFTY";
      if (sym.includes("BANKNIFTY") || currentInstrument?.instrumentKey?.includes("Nifty Bank")) {
        currentInstrumentIndex = "BANKNIFTY";
      } else if (sym.includes("FINNIFTY") || currentInstrument?.instrumentKey?.includes("Nifty Fin")) {
        currentInstrumentIndex = "FINNIFTY";
      } else if (sym.includes("MIDCPNIFTY") || sym.includes("MID SELECT")) {
        currentInstrumentIndex = "MIDCPNIFTY";
      } else if (sym.includes("NIFTY") || currentInstrument?.instrumentKey?.includes("Nifty 50")) {
        currentInstrumentIndex = "NIFTY";
      }

      const isCurrentIndex = !currentInstrument || 
                             currentInstrument.instrumentKey.includes("NSE_INDEX") || 
                             currentInstrument.instrumentKey.includes("BSE_INDEX");

      const needsAutoATM = (lastUnderlyingRef.current !== underlying) && (isCurrentIndex || currentInstrumentIndex !== underlying);

      if (needsAutoATM && data.atm_strike > 0 && strikes.length > 0) {
        const atmRow = strikes.find((s: any) => Number(s.strike) === Number(data.atm_strike)) || strikes[Math.floor(strikes.length / 2)];
        if (atmRow && atmRow.ce_key && atmRow.ce_symbol) {
          // Trigger global hotswap of the active instrument to the ATM CE option contract
          handleSelectContract(atmRow.strike, "CE", atmRow.ce_key, atmRow.ce_symbol);
          lastUnderlyingRef.current = underlying;
        }
      } else if (lastUnderlyingRef.current !== underlying) {
        // Just sync the ref if we do not need auto-ATM hotswap
        lastUnderlyingRef.current = underlying;
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

  // Sync selected instrument's Greeks, OI, Volume, DOM analytics to other panels
  useEffect(() => {
    if (!currentInstrument) {
      window.dispatchEvent(
        new CustomEvent("valkyrie-active-instrument-analytics", { detail: null })
      );
      return;
    }
    if (strikesData.length === 0) return;
    const matchingRow = strikesData.find(
      (r) => r.ce_key === currentInstrument.instrumentKey || r.pe_key === currentInstrument.instrumentKey
    );
    if (matchingRow) {
      const isCE = matchingRow.ce_key === currentInstrument.instrumentKey;
      const analytics = {
        instrumentKey: currentInstrument.instrumentKey,
        symbol: currentInstrument.symbol,
        strike: matchingRow.strike,
        type: isCE ? "CE" : "PE",
        pcr: matchingRow.pcr,
        ltp: isCE ? matchingRow.ce_ltp : matchingRow.pe_ltp,
        iv: isCE ? matchingRow.ce_iv : matchingRow.pe_iv,
        oi: isCE ? matchingRow.ce_oi : matchingRow.pe_oi,
        oiChange: isCE ? matchingRow.ce_oi_change : matchingRow.pe_oi_change,
        oiPct: isCE ? matchingRow.ce_oi_pct : matchingRow.pe_oi_pct,
        volume: isCE ? matchingRow.ce_volume : matchingRow.pe_volume,
        bid: isCE ? matchingRow.ce_bid : matchingRow.pe_bid,
        bidQty: isCE ? matchingRow.ce_bid_qty : matchingRow.pe_bid_qty,
        ask: isCE ? matchingRow.ce_ask : matchingRow.pe_ask,
        askQty: isCE ? matchingRow.ce_ask_qty : matchingRow.pe_ask_qty,
        spread: isCE ? matchingRow.ce_spread : matchingRow.pe_spread,
        delta: isCE ? matchingRow.ce_delta : matchingRow.pe_delta,
        gamma: isCE ? matchingRow.ce_gamma : matchingRow.pe_gamma,
        theta: isCE ? matchingRow.ce_theta : matchingRow.pe_theta,
        vega: isCE ? matchingRow.ce_vega : matchingRow.pe_vega,
        domRatio: isCE ? matchingRow.ce_dom_ratio : matchingRow.pe_dom_ratio,
        domSignal: isCE ? matchingRow.ce_dom_signal : matchingRow.pe_dom_signal,
      };
      window.dispatchEvent(
        new CustomEvent("valkyrie-active-instrument-analytics", { detail: analytics })
      );
    } else {
      window.dispatchEvent(
        new CustomEvent("valkyrie-active-instrument-analytics", { detail: null })
      );
    }
  }, [currentInstrument?.instrumentKey, strikesData]);

  const handleSelectContract = async (strike: number, type: "CE" | "PE", key: string, symbol: string) => {
    setInstrument({
      instrumentKey: key,
      symbol: symbol,
      exchange: "NSE",
    });

    // Notify TradingLeft watchlist to persist this option contract
    window.dispatchEvent(
      new CustomEvent("valkyrie-add-to-watchlist", {
        detail: { instrumentKey: key, symbol, exchange: "NSE" },
      })
    );

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
      <div className="flex flex-wrap items-center justify-between gap-3 bg-deep border border-subtle p-2 rounded select-none shrink-0">
        <div className="flex items-center gap-3">
          {/* Underlying Selector */}
          <div className="flex items-center gap-1.5">
            <span className="vdl-body text-slate-500 font-semibold">Index:</span>
            <select
              value={underlying}
              onChange={(e) => setUnderlying(e.target.value)}
              className="bg-card border border-subtle rounded px-2 py-1 vdl-body text-slate-200 focus:outline-none focus:border-cyan-500/40 cursor-pointer font-sans"
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
            <span className="vdl-body text-slate-500 font-semibold">Expiry:</span>
            <select
              value={selectedExpiry}
              onChange={(e) => setSelectedExpiry(e.target.value)}
              className="bg-card border border-subtle rounded px-2 py-1 vdl-body text-slate-200 focus:outline-none focus:border-cyan-500/40 cursor-pointer font-sans"
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
        <div className="flex items-center gap-4 vdl-body font-mono">
          <div className="flex items-center gap-1.5">
            <span className="vdl-body text-slate-500">Spot price:</span>
            <span className="text-cyan-400 font-semibold">
              ₹{spotPrice.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </span>
          </div>
          {loading && <span className="vdl-body text-cyan-500 animate-pulse">Syncing...</span>}
        </div>
      </div>

      {/* Selected Contract Quick HUD */}
      {currentInstrument && (
        <div className="bg-cyan-500/5 border border-cyan-500/20 px-3 py-1.5 rounded flex items-center justify-between vdl-body font-sans">
          <div className="flex items-center gap-2">
            <span className="text-slate-500 font-semibold vdl-body">Active target:</span>
            <span className="font-semibold text-cyan-400 font-mono">{currentInstrument.symbol}</span>
          </div>
          <span className="vdl-body font-mono text-slate-500">Key: {currentInstrument.symbol}</span>
        </div>
      )}

      {/* Error alert */}
      {error && (
        <div className="p-2 bg-rose-950/40 border border-rose-500/20 text-rose-400 vdl-body rounded select-none">
          {error}
        </div>
      )}

      {/* Option Chain Table */}
      <div className="flex-1 min-h-0 overflow-auto rounded">
        <table className="w-full text-left font-mono tabular-nums vdl-body border-collapse">
          <thead className="sticky top-0 bg-card/95 backdrop-blur border-b border-subtle z-10">
            {/* Section header row */}
            <tr className="vdl-body select-none border-b border-subtle bg-deep">
              <th colSpan={7} className="py-1.5 pl-3 text-emerald-450 font-semibold border-r border-subtle text-center">— CALLS —</th>
              <th className="py-1.5 text-center text-slate-350 font-semibold bg-card border-x border-subtle">Strike</th>
              <th colSpan={7} className="py-1.5 pr-3 text-right text-rose-400 font-semibold border-l border-subtle text-center">— PUTS —</th>
            </tr>
            {/* Column header row */}
            <tr className="text-slate-500 vdl-body select-none bg-deep">
              <th className="py-1.5 pl-3 text-left">DOM</th>
              <th className="py-1.5 text-right">Iv%</th>
              <th className="py-1.5 text-right">Oi</th>
              <th className="py-1.5 text-right">OI Chg</th>
              <th className="py-1.5 text-right">Vol</th>
              <th className="py-1.5 text-right">Bid×Qty</th>
              <th className="py-1.5 text-right text-emerald-400 font-semibold border-r border-subtle pr-2">Ltp</th>
              <th className="py-1.5 text-center font-semibold text-slate-300 bg-card border-x border-subtle px-2">Strike</th>
              <th className="py-1.5 text-left text-rose-400 font-semibold border-l border-subtle pl-2">Ltp</th>
              <th className="py-1.5 text-left">Ask×Qty</th>
              <th className="py-1.5 text-left">Vol</th>
              <th className="py-1.5 text-left">Oi</th>
              <th className="py-1.5 text-left">OI Chg</th>
              <th className="py-1.5 text-left">Iv%</th>
              <th className="py-1.5 pr-3 text-left">DOM</th>
            </tr>
          </thead>
          <tbody className="text-slate-300 divide-y divide-white/[0.02]">
            {strikesData.length > 0 ? (
              strikesData.map((row) => {
                const isATM = Math.abs(row.strike - spotPrice) <= (underlying === "NIFTY" || underlying === "MIDCPNIFTY" ? 25 : 50);
                const ceActive = currentInstrument?.instrumentKey === row.ce_key;
                const peActive = currentInstrument?.instrumentKey === row.pe_key;

                const fmtOI = (v: number) => v >= 1000000 ? `${(v/1000000).toFixed(1)}M` : v >= 1000 ? `${(v/1000).toFixed(0)}K` : String(v);
                const fmtVol = fmtOI;
                const domColor = (sig: string) =>
                  sig === "BULLISH" ? "text-emerald-400 bg-emerald-950/40 border-emerald-700/30" :
                  sig === "BEARISH" ? "text-rose-400 bg-rose-950/40 border-rose-700/30" :
                  "text-slate-400 bg-card/40";
                const oiChgColor = (v: number) => v > 0 ? "text-emerald-400" : v < 0 ? "text-rose-400" : "text-slate-500";

                return (
                  <tr
                    key={row.strike}
                    className={`hover:bg-cyan-500/[0.03] transition-all ${isATM ? "bg-cyan-500/[0.02] border-y border-cyan-500/10" : ""}`}
                  >
                    {/* CE: DOM Signal */}
                    <td className="py-1.5 pl-3">
                      <span className={`px-1 py-0.5 rounded vdl-body font-semibold font-sans border ${domColor(row.ce_dom_signal || "NEUTRAL")}`}>
                        {(row.ce_dom_signal || "—").slice(0, 4)}
                      </span>
                    </td>

                    {/* CE: IV */}
                    <td className="py-1.5 text-right text-amber-400/80">{row.ce_iv > 0 ? row.ce_iv.toFixed(1) : "—"}</td>

                    {/* CE: OI */}
                    <td className="py-1.5 text-right text-slate-400">{row.ce_oi > 0 ? fmtOI(row.ce_oi) : "—"}</td>

                    {/* CE: OI Change */}
                    <td className={`py-1.5 text-right font-semibold ${oiChgColor(row.ce_oi_change || 0)}`}>
                      {row.ce_oi_change !== 0 && row.ce_oi_change !== undefined ? `${row.ce_oi_change > 0 ? "+" : ""}${fmtOI(row.ce_oi_change)}` : "—"}
                    </td>

                    {/* CE: Volume */}
                    <td className="py-1.5 text-right text-slate-500">{row.ce_volume > 0 ? fmtVol(row.ce_volume) : "—"}</td>

                    {/* CE: Bid × Qty */}
                    <td className="py-1.5 text-right text-slate-400 vdl-body font-mono">
                      {row.ce_bid > 0 ? (
                        <span>{row.ce_bid.toFixed(1)}<span className="text-slate-600">×{fmtOI(row.ce_bid_qty)}</span></span>
                      ) : "—"}
                    </td>

                    {/* CE: LTP — clickable */}
                    <td className="py-1.5 pr-2 text-right border-r border-subtle">
                      {row.ce_key ? (
                        <button
                          onClick={() => handleSelectContract(row.strike, "CE", row.ce_key, row.ce_symbol)}
                          className={`flex items-center justify-end gap-1 group cursor-pointer w-full focus:outline-none rounded px-1 py-0.5 transition-all${
                            ceActive ? "bg-emerald-500/10 ring-1 ring-emerald-500/30" : "hover:bg-emerald-500/5"
                          }`}
                        >
                          <span className="text-emerald-400 font-semibold vdl-body">₹{row.ce_ltp.toFixed(2)}</span>
                          <span className="opacity-0 group-hover:opacity-100 vdl-body text-emerald-500 font-sans">CE▶</span>
                        </button>
                      ) : <span className="text-slate-600 pr-2">—</span>}
                    </td>

                    {/* Center Strike Axis Spine */}
                    <td className="py-1 text-center px-3 bg-card border-x border-subtle select-none">
                      <span className={`px-2 py-0.5 rounded font-mono font-semibold vdl-body tabular-nums${
                        isATM 
                          ? "bg-amber-500 text-slate-950 font-black shadow-[0_0_10px_rgba(245,158,11,0.45)]" 
                          : "text-slate-100"
                      }`}>
                        {row.strike}
                      </span>
                      {row.pcr > 0 && (
                        <div className="vdl-body text-slate-500 font-sans text-center mt-0.5">PCR {row.pcr.toFixed(1)}</div>
                      )}
                    </td>

                    {/* PE: LTP — clickable */}
                    <td className="py-1.5 pl-2 text-left border-l border-subtle">
                      {row.pe_key ? (
                        <button
                          onClick={() => handleSelectContract(row.strike, "PE", row.pe_key, row.pe_symbol)}
                          className={`flex items-center gap-1 group cursor-pointer w-full focus:outline-none rounded px-1 py-0.5 transition-all${
                            peActive ? "bg-rose-500/10 ring-1 ring-rose-500/30" : "hover:bg-rose-500/5"
                          }`}
                        >
                          <span className="opacity-0 group-hover:opacity-100 vdl-body text-rose-500 font-sans">◀PE</span>
                          <span className="text-rose-400 font-semibold vdl-body">₹{row.pe_ltp.toFixed(2)}</span>
                        </button>
                      ) : <span className="text-slate-600 pl-2">—</span>}
                    </td>

                    {/* PE: Ask × Qty */}
                    <td className="py-1.5 text-left text-slate-400 vdl-body font-mono">
                      {row.pe_ask > 0 ? (
                        <span>{row.pe_ask.toFixed(1)}<span className="text-slate-600">×{fmtOI(row.pe_ask_qty)}</span></span>
                      ) : "—"}
                    </td>

                    {/* PE: Volume */}
                    <td className="py-1.5 text-left text-slate-500">{row.pe_volume > 0 ? fmtVol(row.pe_volume) : "—"}</td>

                    {/* PE: OI */}
                    <td className="py-1.5 text-left text-slate-400">{row.pe_oi > 0 ? fmtOI(row.pe_oi) : "—"}</td>

                    {/* PE: OI Change */}
                    <td className={`py-1.5 text-left font-semibold ${oiChgColor(row.pe_oi_change || 0)}`}>
                      {row.pe_oi_change !== 0 && row.pe_oi_change !== undefined ? `${row.pe_oi_change > 0 ? "+" : ""}${fmtOI(row.pe_oi_change)}` : "—"}
                    </td>

                    {/* PE: IV */}
                    <td className="py-1.5 text-left text-amber-400/80">{row.pe_iv > 0 ? row.pe_iv.toFixed(1) : "—"}</td>

                    {/* PE: DOM Signal */}
                    <td className="py-1.5 pr-3">
                      <span className={`px-1 py-0.5 rounded vdl-body font-semibold font-sans border ${domColor(row.pe_dom_signal || "NEUTRAL")}`}>
                        {(row.pe_dom_signal || "—").slice(0, 4)}
                      </span>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={15}><div className="empty-state">No options chain data loaded. Please select a valid expiry.</div></td>
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

  const [cancellingOrderId, setCancellingOrderId] = useState<string | null>(null);

  const [editingOrderId, setEditingOrderId] = useState<string | null>(null);
  const [editPrice, setEditPrice] = useState<number>(0);
  const [editQty, setEditQty] = useState<number>(0);
  const [modifyingOrderId, setModifyingOrderId] = useState<string | null>(null);

  const handleModifyOrder = async (orderId: string, orderType: string) => {
    try {
      setModifyingOrderId(orderId);
      await tradingApi.modifyBrokerOrder({
        order_id: orderId,
        quantity: editQty,
        price: editPrice,
        order_type: orderType,
      });
      setEditingOrderId(null);
      fetchOrders();
      fetchPositions();
    } catch (err: any) {
      alert(`Failed to modify order: ${err.message || err}`);
    } finally {
      setModifyingOrderId(null);
    }
  };

  const handleCancelOrder = async (orderId: string) => {
    if (!window.confirm(`Cancel order ${orderId}?`)) return;
    try {
      setCancellingOrderId(orderId);
      await tradingApi.cancelBrokerOrder(orderId);
      fetchOrders();
      fetchPositions();
    } catch (err: any) {
      alert(`Failed to cancel order: ${err.message || err}`);
    } finally {
      setCancellingOrderId(null);
    }
  };

  const [squaringOffKey, setSquaringOffKey] = useState<string | null>(null);

  const handleSquareOff = async (pos: any) => {
    const qty = Number(pos.quantity || 0);
    if (qty === 0) return;
    
    const side = qty > 0 ? "SELL" : "BUY";
    const absQty = Math.abs(qty);
    const key = `${pos.instrument_token}_${pos.product}`;
    
    if (!window.confirm(`Square Off ${pos.trading_symbol}? This will place a MARKET ${side} for ${absQty} lot(s) immediately.`)) return;
    
    try {
      setSquaringOffKey(key);
      await tradingApi.placeBrokerOrder({
        instrument_key: pos.instrument_token,
        quantity: absQty,
        transaction_type: side,
        order_type: "MARKET",
        product: pos.product,
      });
      fetchPositions();
      fetchOrders();
    } catch (err: any) {
      alert(`Failed to square off position: ${err.message || err}`);
    } finally {
      setSquaringOffKey(null);
    }
  };

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

    const handleRefresh = () => {
      fetchPositions();
      fetchOrders();
      fetchTrades();
      fetchHoldings();
    };
    window.addEventListener("valkyrie-portfolio-refresh", handleRefresh);

    const interval = setInterval(() => {
      fetchPositions();
      fetchOrders();
      fetchTrades();
      fetchHoldings();
    }, 3000);

    return () => {
      clearInterval(interval);
      window.removeEventListener("valkyrie-portfolio-refresh", handleRefresh);
    };
  }, []);

  useEffect(() => {
    if (activeTab === "positions") fetchPositions();
    else if (activeTab === "orders") fetchOrders();
    else if (activeTab === "trades") fetchTrades();
    else if (activeTab === "holdings") fetchHoldings();
  }, [activeTab]);

  const realizedPnL = brokerPositions.reduce((acc, pos) => acc + Number(pos.realised || 0), 0);
  const unrealizedPnL = brokerPositions.reduce((acc, pos) => acc + Number(pos.unrealised || 0), 0);
  const brokerage = brokerTrades.reduce((acc, t) => {
    const tradeVal = Number(t.trade_value || 0) || (Number(t.price || 0) * Number(t.quantity || 0));
    const stt = (t.transaction_type === "SELL" ? tradeVal * 0.0005 : 0);
    return acc + 20 + 5.5 + stt;
  }, 0);
  const netPnL = realizedPnL + unrealizedPnL - brokerage;

  const tabItems = [
    { id: "optionChain", label: "Option Chain" },
    { id: "positions", label: "Positions", count: brokerPositions.length },
    { id: "orders", label: "Orders", count: brokerOrders.length },
    { id: "trades", label: "Trades", count: brokerTrades.length },
    { id: "holdings", label: "Holdings", count: brokerHoldings.length },
    { id: "pnl", label: "PnL Summary" },
  ];

  const positionsColumns: ColumnDef<any>[] = [
    {
      header: "Symbol",
      accessorKey: (pos) => <span className="font-sans font-semibold text-slate-200">{pos.trading_symbol}</span>,
    },
    {
      header: "Qty",
      accessorKey: (pos) => <span className="font-semibold">{Number(pos.quantity || 0)}</span>,
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Product",
      accessorKey: "product",
      className: "text-slate-400 font-sans text-center",
    },
    {
      header: "Exchange",
      accessorKey: "exchange",
      className: "text-slate-400 font-sans text-center",
    },
    {
      header: "Avg Price",
      accessorKey: (pos) => `₹${Number(pos.average_price || pos.buy_price || 0).toFixed(2)}`,
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Ltp",
      accessorKey: (pos) => `₹${Number(pos.last_price || 0).toFixed(2)}`,
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Mtm",
      accessorKey: (pos) => {
        const val = Number(pos.unrealised || 0);
        return (
          <span className={`font-semibold ${val >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            {val >= 0 ? "+" : ""}₹{val.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        );
      },
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Realized PnL",
      accessorKey: (pos) => {
        const val = Number(pos.realised || 0);
        return (
          <span className={`font-semibold ${val >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            {val >= 0 ? "+" : ""}₹{val.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        );
      },
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Status",
      accessorKey: (pos) => {
        const qty = Number(pos.quantity || 0);
        const stateLabel = qty === 0 ? "Stopped" : qty > 0 ? "Running" : "Paused";
        return <StatusBadge state={stateLabel} />;
      },
      className: "text-center",
    },
    {
      header: "Action",
      accessorKey: (pos) => {
        const qty = Number(pos.quantity || 0);
        const posKey = `${pos.instrument_token}_${pos.product}`;
        if (qty === 0) return <span className="text-slate-600">—</span>;
        return squaringOffKey === posKey ? (
          <span className="text-rose-400 animate-pulse">Exiting...</span>
        ) : (
          <button
            onClick={() => handleSquareOff(pos)}
            className="text-rose-400 hover:text-rose-300 font-semibold hover:underline cursor-pointer"
          >
            Square Off
          </button>
        );
      },
      className: "text-center",
    },
  ];

  const ordersColumns: ColumnDef<any>[] = [
    {
      header: "Order ID",
      accessorKey: (ord) => <span className="text-slate-500 font-mono select-all text-xs">{ord.order_id}</span>,
    },
    {
      header: "Symbol",
      accessorKey: (ord) => <span className="font-sans font-semibold text-slate-200">{ord.trading_symbol}</span>,
    },
    {
      header: "Qty",
      accessorKey: "quantity",
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Type",
      accessorKey: "transaction_type",
      className: "text-center font-sans",
    },
    {
      header: "Status",
      accessorKey: (ord) => {
        const statusLower = (ord.status || "").toLowerCase();
        let statusLabel = "Paused";
        if (statusLower === "complete") statusLabel = "Ready";
        else if (statusLower === "rejected") statusLabel = "Failed";
        else if (statusLower === "cancelled") statusLabel = "Stopped";
        return <StatusBadge state={statusLabel} />;
      },
      className: "text-center",
    },
    {
      header: "Avg Price",
      accessorKey: (ord) => `₹${Number(ord.average_price || ord.price || 0).toFixed(2)}`,
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Timestamp",
      accessorKey: (ord) => ord.order_timestamp || "—",
      className: "text-slate-500",
    },
    {
      header: "Action",
      accessorKey: (ord) => {
        const statusLower = (ord.status || "").toLowerCase();
        const isPending =
          statusLower === "open" ||
          statusLower === "trigger pending" ||
          statusLower === "put order req received" ||
          statusLower === "validation pending" ||
          statusLower === "modify validation pending" ||
          statusLower === "not cancelled" ||
          statusLower === "open pending" ||
          statusLower === "after market order req received";
        if (!isPending) return <span className="text-slate-600">—</span>;

        if (editingOrderId === ord.order_id) {
          return (
            <div className="flex items-center gap-1.5 font-sans justify-center">
              <input
                type="number"
                value={editPrice}
                onChange={(e) => setEditPrice(Number(e.target.value))}
                className="w-14 bg-card border border-subtle rounded px-1 py-0.5 text-xs text-right font-mono"
                placeholder="Price"
              />
              <input
                type="number"
                value={editQty}
                onChange={(e) => setEditQty(Number(e.target.value))}
                className="w-10 bg-card border border-subtle rounded px-1 py-0.5 text-xs text-right font-mono"
                placeholder="Qty"
              />
              <button
                onClick={() => handleModifyOrder(ord.order_id, ord.order_type)}
                className="text-emerald-400 hover:text-emerald-300 text-xs font-semibold cursor-pointer"
                disabled={modifyingOrderId === ord.order_id}
              >
                {modifyingOrderId === ord.order_id ? "..." : "Save"}
              </button>
              <button
                onClick={() => setEditingOrderId(null)}
                className="text-slate-400 hover:text-slate-300 text-xs cursor-pointer"
              >
                Cancel
              </button>
            </div>
          );
        }

        return (
          <div className="flex items-center justify-center gap-1.5 font-sans">
            <button
              onClick={() => {
                setEditPrice(Number(ord.price || 0));
                setEditQty(Number(ord.quantity || 0));
                setEditingOrderId(ord.order_id);
              }}
              className="text-cyan-400 hover:text-cyan-300 font-semibold cursor-pointer"
            >
              Edit
            </button>
            <span className="text-slate-700">|</span>
            <button
              onClick={() => handleCancelOrder(ord.order_id)}
              className="text-rose-400 hover:text-rose-300 font-semibold cursor-pointer"
              disabled={cancellingOrderId === ord.order_id}
            >
              {cancellingOrderId === ord.order_id ? "..." : "Cancel"}
            </button>
          </div>
        );
      },
      className: "text-center",
    },
  ];

  const tradesColumns: ColumnDef<any>[] = [
    {
      header: "Trade ID",
      accessorKey: (trd) => <span className="text-slate-500 font-mono select-all text-xs">{trd.trade_id}</span>,
    },
    {
      header: "Order ID",
      accessorKey: (trd) => <span className="text-slate-500 font-mono select-all text-xs">{trd.order_id}</span>,
    },
    {
      header: "Symbol",
      accessorKey: (trd) => <span className="font-sans font-semibold text-slate-200">{trd.trading_symbol}</span>,
    },
    {
      header: "Side",
      accessorKey: (trd) => (
        <span className={`font-semibold ${trd.transaction_type === "BUY" ? "text-emerald-400" : "text-rose-400"}`}>
          {trd.transaction_type}
        </span>
      ),
      className: "text-center",
    },
    {
      header: "Qty",
      accessorKey: "quantity",
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Price",
      accessorKey: (trd) => `₹${Number(trd.average_price || 0).toFixed(2)}`,
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Timestamp",
      accessorKey: (trd) => trd.exchange_timestamp || trd.order_timestamp || "—",
      className: "text-slate-500",
    },
  ];

  const holdingsColumns: ColumnDef<any>[] = [
    {
      header: "Symbol",
      accessorKey: (hold) => <span className="font-sans font-semibold text-slate-200">{hold.trading_symbol}</span>,
    },
    {
      header: "Qty",
      accessorKey: "quantity",
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Avg Cost",
      accessorKey: (hold) => `₹${Number(hold.average_price || 0).toFixed(2)}`,
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Current Value",
      accessorKey: (hold) => {
        const val = Number(hold.quantity || 0) * Number(hold.last_price || 0);
        return `₹${val.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      },
      isNumeric: true,
      isMono: true,
    },
    {
      header: "PnL",
      accessorKey: (hold) => {
        const val = Number(hold.pnl || 0);
        return (
          <span className={`font-semibold ${val >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            {val >= 0 ? "+" : ""}₹{val.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        );
      },
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Exchange",
      accessorKey: "exchange",
      className: "text-slate-400 font-sans text-center",
    },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <SegmentedTabs
        tabs={tabItems}
        activeTabId={activeTab}
        onChange={(id) => setActiveTab(id as any)}
      />

      <div className="flex-1 overflow-y-auto min-h-0">
        {activeTab === "optionChain" && <OptionChainPanel />}

        {activeTab === "positions" && (
          <DataTable
            columns={positionsColumns}
            data={brokerPositions}
            emptyState={
              <EmptyState
                icon={Activity}
                title="No Active Positions"
                description="No active positions found in Upstox account. Open order ticket to execute an entry."
              />
            }
          />
        )}

        {activeTab === "orders" && (
          <DataTable
            columns={ordersColumns}
            data={brokerOrders}
            emptyState={
              <EmptyState
                icon={Play}
                title="No Orders Found"
                description="No orders placed today. Send an order from the order panel."
              />
            }
          />
        )}

        {activeTab === "trades" && (
          <DataTable
            columns={tradesColumns}
            data={brokerTrades}
            emptyState={
              <EmptyState
                icon={Terminal}
                title="No Trades Executed"
                description="No trades executed today in Upstox account."
              />
            }
          />
        )}

        {activeTab === "holdings" && (
          <DataTable
            columns={holdingsColumns}
            data={brokerHoldings}
            emptyState={
              <EmptyState
                icon={Shield}
                title="No Holdings Found"
                description="No holdings found in Upstox account."
              />
            }
          />
        )}

        {activeTab === "pnl" && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-[12px] p-4">
            <KpiCard
              label="Net P&L"
              value={`₹${netPnL.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
              delta={{
                value: `${netPnL >= 0 ? "+" : ""}${netPnL.toFixed(2)}`,
                type: netPnL >= 0 ? "positive" : "negative",
              }}
            />
            <KpiCard
              label="Realized P&L"
              value={`₹${realizedPnL.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
              delta={{
                value: `${realizedPnL >= 0 ? "+" : ""}${realizedPnL.toFixed(2)}`,
                type: realizedPnL >= 0 ? "positive" : "negative",
              }}
            />
            <KpiCard
              label="Unrealized P&L"
              value={`₹${unrealizedPnL.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
              delta={{
                value: `${unrealizedPnL >= 0 ? "+" : ""}${unrealizedPnL.toFixed(2)}`,
                type: unrealizedPnL >= 0 ? "positive" : "negative",
              }}
            />
            <KpiCard
              label="Day Total"
              value={`₹${(realizedPnL + unrealizedPnL).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
              delta={{
                value: `${realizedPnL + unrealizedPnL >= 0 ? "+" : ""}${(realizedPnL + unrealizedPnL).toFixed(2)}`,
                type: realizedPnL + unrealizedPnL >= 0 ? "positive" : "negative",
              }}
            />
            <KpiCard
              label="Brokerage"
              value={`₹${brokerage.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
            />
          </div>
        )}
      </div>
    </div>
  );
};

