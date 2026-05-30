"use client";

import React, { useState, useEffect, useRef } from "react";
import { createChart, IChartApi, ISeriesApi, UTCTimestamp, CandlestickSeries, HistogramSeries } from "lightweight-charts";
import { 
  Play, Activity, Terminal, Shield, Cpu, RefreshCw, BarChart2,
  TrendingUp, Layers, Server, Settings, Zap, ArrowUpRight, ArrowDownRight,
  Sliders, Search, Plus, Trash2, SlidersHorizontal, Lock, CheckCircle2, 
  AlertTriangle, Star, Check, X, Maximize2, Minimize2, ZoomIn, ZoomOut
} from "lucide-react";
import { useTerminalStore, Instrument, Timeframe } from "@/store/useTerminalStore";
import { useBackendTradingStore } from "@/services/tradingQueries";
import { useEventStore } from "@/store/useEventStore";

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
  { instrumentKey: "NSE_INDEX|NIFTY_50", symbol: "NIFTY 50", exchange: "NSE" },
  { instrumentKey: "NSE_INDEX|BANKNIFTY", symbol: "BANKNIFTY", exchange: "NSE" },
  { instrumentKey: "NSE_EQ|RELIANCE", symbol: "RELIANCE", exchange: "NSE" },
  { instrumentKey: "NSE_EQ|TCS", symbol: "TCS", exchange: "NSE" },
  { instrumentKey: "NSE_EQ|INFOSYS", symbol: "INFOSYS", exchange: "NSE" },
];

// ==========================================
// 1. LEFT PANEL: WATCHLIST
// ==========================================
export const TradingLeft: React.FC = () => {
  const currentInstrument = useTerminalStore((state) => state.selectedInstrument);
  const setInstrument = useTerminalStore((state) => state.setInstrument);
  const [search, setSearch] = useState("");
  const [pinned, setPinned] = useState<string[]>(["NIFTY 50", "BANKNIFTY"]);

  const status = useBackendTradingStore((state) => state.status);
  const connectionStatus = useBackendTradingStore((state) => state.connectionStatus);
  const connectTelemetry = useBackendTradingStore((state) => state.connectTelemetry);
  
  const [prices, setPrices] = useState<Record<string, { ltp: number; change: string; up: boolean }>>({
    "NIFTY 50": { ltp: 22212.40, change: "+0.32%", up: true },
    "BANKNIFTY": { ltp: 46772.50, change: "+0.54%", up: true },
    "RELIANCE": { ltp: 2452.10, change: "+0.15%", up: true },
    "TCS": { ltp: 3848.00, change: "-0.22%", up: false },
    "INFOSYS": { ltp: 1448.20, change: "-0.85%", up: false },
  });

  useEffect(() => {
    connectTelemetry();
  }, [connectTelemetry]);

  useEffect(() => {
    if (status && currentInstrument) {
      const activeSym = currentInstrument.symbol;
      const spot = status.spot_price;
      const changePct = status.return_percent;
      if (spot > 0) {
        setPrices((prev) => ({
          ...prev,
          [activeSym]: {
            ltp: spot,
            change: `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%`,
            up: changePct >= 0,
          },
        }));
      }
    }
  }, [status, currentInstrument]);

  const togglePin = (sym: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setPinned((prev) =>
      prev.includes(sym) ? prev.filter((s) => s !== sym) : [...prev, sym]
    );
  };

  const filtered = AVAILABLE_INSTRUMENTS.filter((ins) =>
    ins.symbol.toLowerCase().includes(search.toLowerCase())
  );

  const connectionDotColor = 
    connectionStatus === "CONNECTED" ? "bg-emerald-500 shadow-emerald-500/20" :
    connectionStatus === "CONNECTING" ? "bg-amber-500 animate-pulse shadow-amber-500/20" :
    "bg-rose-500 shadow-rose-500/20";

  return (
    <div className="flex flex-col h-full bg-slate-950/40 border border-white/5 rounded-lg p-3 hover:border-cyan-500/10 transition-all">
      <h3 className="text-[10px] font-bold tracking-widest text-cyan-400 uppercase border-b border-white/5 pb-1.5 mb-2.5 flex items-center justify-between select-none">
        <span>Watchlist</span>
        <div className="flex items-center gap-1.5">
          <span className="text-[8px] text-slate-500 font-mono font-medium lowercase">{connectionStatus}</span>
          <span className={`w-1.5 h-1.5 rounded-full ${connectionDotColor} shadow-md`} />
        </div>
      </h3>
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="flex flex-col gap-2 h-full">
          {/* Search */}
          <div className="relative shrink-0">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search symbols..."
              className="w-full bg-slate-900/60 border border-white/5 rounded pl-8 pr-3 py-1.5 text-[11px] text-slate-300 focus:outline-none focus:border-cyan-500/40"
            />
          </div>

          {/* Instruments list */}
          <div className="flex-1 overflow-y-auto flex flex-col gap-0.5 mt-1 pr-1 font-sans text-xs scrollbar-thin scrollbar-thumb-white/5 scrollbar-track-transparent">
            {/* Header Row */}
            <div className="grid grid-cols-12 px-2 py-1 text-[9px] font-bold text-slate-500 uppercase tracking-wider select-none shrink-0 border-b border-white/[0.02]">
              <span className="col-span-6">Symbol</span>
              <span className="col-span-3 text-right">LTP</span>
              <span className="col-span-3 text-right">Change</span>
            </div>

            {filtered.map((item) => {
              const priceInfo = prices[item.symbol] || { ltp: 0, change: "0.00%", up: true };
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
                    <span className="truncate uppercase font-medium">{item.symbol}</span>
                  </div>

                  {/* LTP */}
                  <span className="col-span-3 text-right font-mono text-[11px]">
                    ₹{priceInfo.ltp.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>

                  {/* Change */}
                  <span
                    className={`col-span-3 text-right font-mono text-[10px] font-semibold ${
                      priceInfo.up ? "text-emerald-400" : "text-rose-400"
                    }`}
                  >
                    {priceInfo.change}
                  </span>
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

  const selectedInstrument = useTerminalStore((state) => state.selectedInstrument);
  const selectedTimeframe = useTerminalStore((state) => state.selectedTimeframe);
  const setInstrument = useTerminalStore((state) => state.setInstrument);
  const setTimeframe = useTerminalStore((state) => state.setTimeframe);

  const [activeIndicators, setActiveIndicators] = useState<string[]>([]);
  const [showDrawMenu, setShowDrawMenu] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [currentLtp, setCurrentLtp] = useState<number>(22212.40);

  // Generate realistic candles based on selected symbol
  const generateInitialData = (symbol: string) => {
    let basePrice = 22200;
    if (symbol === "BANKNIFTY") basePrice = 46700;
    if (symbol === "RELIANCE") basePrice = 2450;
    if (symbol === "TCS") basePrice = 3850;
    if (symbol === "INFOSYS") basePrice = 1450;

    const data = [];
    const volumeData = [];
    const now = Math.floor(Date.now() / 1000) - 300 * 60; // 300 minutes ago

    let currentPrice = basePrice;
    for (let i = 0; i < 150; i++) {
      const open = currentPrice + (Math.random() - 0.5) * (basePrice * 0.002);
      const close = open + (Math.random() - 0.5) * (basePrice * 0.002);
      const high = Math.max(open, close) + Math.random() * (basePrice * 0.001);
      const low = Math.min(open, close) - Math.random() * (basePrice * 0.001);

      const time = (now + i * 60) as UTCTimestamp;
      data.push({ time, open, high, low, close });

      const volume = Math.floor(Math.random() * 5000) + 1000;
      const color = close >= open ? "rgba(16, 185, 129, 0.25)" : "rgba(239, 68, 68, 0.25)";
      volumeData.push({ time, value: volume, color });

      currentPrice = close;
    }
    return { candleData: data, volumeData };
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

    // Populate data
    const symbol = selectedInstrument?.symbol || "NIFTY 50";
    const { candleData, volumeData } = generateInitialData(symbol);
    candleSeries.setData(candleData);
    volumeSeries.setData(volumeData);

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

  const candles = useBackendTradingStore((state) => state.candles);
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

  // Set real database candle series data
  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current || !candles || candles.length === 0) return;
    
    // Convert BackendCandle to the format expected by lightweight-charts (with a 'time' property)
    const formattedCandles = candles.map((c) => ({
      time: (c.time ?? (typeof c.timestamp === "number" ? c.timestamp : Math.floor(new Date(c.timestamp || "").getTime() / 1000))) as UTCTimestamp,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close
    }));

    // Set main candlestick data
    candleSeriesRef.current.setData(formattedCandles);

    // Populate volume series matched to candles
    const volumeData = formattedCandles.map((c) => ({
      time: c.time,
      value: Math.floor(Math.random() * 300) + 50,
      color: c.close >= c.open ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)"
    }));
    volumeSeriesRef.current.setData(volumeData);
  }, [candles]);

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

// ==========================================
// 3. RIGHT PANEL: ORDER ENTRY & POSITIONS SUMMARY
// ==========================================
export const TradingRight: React.FC = () => {
  const currentInstrument = useTerminalStore((state) => state.selectedInstrument);
  const activeMode = useTerminalStore((state) => state.activeMode);
  const currentAccount = useTerminalStore((state) => state.currentAccount);
  const addEvent = useEventStore((state) => state.addEvent);

  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [productType, setProductType] = useState<"MIS" | "NRML" | "CNC">("MIS");
  const [orderType, setOrderType] = useState<"MARKET" | "LIMIT">("MARKET");
  const [quantity, setQuantity] = useState(50);
  const [limitPrice, setLimitPrice] = useState(22212.40);
  const [triggerPrice, setTriggerPrice] = useState(0);

  // Sync pricing bases when switching symbols
  useEffect(() => {
    if (!currentInstrument) return;
    const sym = currentInstrument.symbol;
    let basePrice = 22212.40;
    let baseQty = 50;

    if (sym === "BANKNIFTY") {
      basePrice = 46772.50;
      baseQty = 15;
    } else if (sym === "RELIANCE") {
      basePrice = 2452.10;
      baseQty = 1;
    } else if (sym === "TCS") {
      basePrice = 3848.00;
      baseQty = 1;
    } else if (sym === "INFOSYS") {
      basePrice = 1448.20;
      baseQty = 1;
    }

    setLimitPrice(basePrice);
    setQuantity(baseQty);
  }, [currentInstrument]);

  const status = useBackendTradingStore((state) => state.status);
  const isLoading = useBackendTradingStore((state) => state.isLoading);
  const actionError = useBackendTradingStore((state) => state.actionError);
  const successMessage = useBackendTradingStore((state) => state.successMessage);

  const buyAction = useBackendTradingStore((state) => state.buy);
  const sellAction = useBackendTradingStore((state) => state.sell);
  const createGttAction = useBackendTradingStore((state) => state.createGtt);
  const clearMessages = useBackendTradingStore((state) => state.clearMessages);

  // Clear messages on symbol switch
  useEffect(() => {
    clearMessages();
  }, [currentInstrument, clearMessages]);

  const handlePlaceOrder = async (overrideSide?: "BUY" | "SELL") => {
    if (!currentInstrument) return;
    const orderSide = overrideSide || side;

    if (triggerPrice > 0) {
      const direction = triggerPrice >= limitPrice ? "ABOVE" : "BELOW";
      const success = await createGttAction(
        triggerPrice,
        quantity,
        orderSide,
        orderType,
        limitPrice,
        0.0,
        "points",
        0.0,
        "points",
        0.0,
        direction
      );
      if (success) {
        addEvent({
          type: "success",
          message: `GTT ORDER CREATED - ${orderSide} ${quantity} ${currentInstrument.symbol} @ Trigger ₹${triggerPrice}`,
          workspace: "Trading",
        });
      } else {
        const err = useBackendTradingStore.getState().actionError || "Failed to create GTT";
        addEvent({
          type: "error",
          message: `GTT ORDER FAILED: ${err}`,
          workspace: "Trading",
        });
      }
    } else {
      if (orderSide === "BUY") {
        const success = await buyAction(quantity, 0.0, "points", 0.0, "points", 0.0, false);
        if (success) {
          addEvent({
            type: "success",
            message: `BUY ORDER PLACED - ${quantity} ${currentInstrument.symbol} @ LTP`,
            workspace: "Trading",
          });
        } else {
          const err = useBackendTradingStore.getState().actionError || "Failed to execute order";
          addEvent({
            type: "error",
            message: `BUY ORDER FAILED: ${err}`,
            workspace: "Trading",
          });
        }
      } else {
        const success = await sellAction();
        if (success) {
          addEvent({
            type: "success",
            message: `SELL ORDER PLACED - Exit active position`,
            workspace: "Trading",
          });
        } else {
          const err = useBackendTradingStore.getState().actionError || "Failed to execute exit";
          addEvent({
            type: "error",
            message: `SELL ORDER FAILED: ${err}`,
            workspace: "Trading",
          });
        }
      }
    }
  };

  const marginRequired = quantity * limitPrice * (productType === "MIS" ? 0.1 : 1.0);
  const maxRisk = quantity * limitPrice * 0.02; // Hypothetical 2% SL risk

  // Positions summary data mapped from backend telemetry
  const positions = status?.position ? [{
    symbol: status.trading_symbol || "ACTIVE POSITION",
    qty: status.position.total_qty,
    side: "LONG" as const,
    avgPrice: status.position.entry_price,
    ltp: status.spot_price,
    pnl: status.total_pnl,
  }] : [];

  const closePosition = async (sym?: string) => {
    await sellAction();
  };

  return (
    <div className="flex flex-col gap-3 h-full font-sans text-xs">
      {/* Order Pad Card */}
      <div className="p-3 bg-slate-950/40 border border-white/5 rounded-lg flex flex-col gap-2.5">
        <h3 className="text-[10px] font-bold tracking-widest text-cyan-400 uppercase border-b border-white/5 pb-1.5 flex items-center justify-between select-none">
          <span>ORDER TICKET</span>
          <span className="text-[8px] font-mono text-slate-500">{currentAccount.name}</span>
        </h3>

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
        {actionError && (
          <div className="p-2 bg-rose-950/40 border border-rose-500/20 text-rose-400 text-[10px] rounded flex items-center gap-1.5 font-sans animate-pulse">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            <span className="truncate">{actionError}</span>
          </div>
        )}
        {successMessage && (
          <div className="p-2 bg-emerald-950/40 border border-emerald-500/20 text-emerald-400 text-[10px] rounded flex items-center gap-1.5 font-sans">
            <CheckCircle2 className="w-3.5 h-3.5 shrink-0 text-emerald-400" />
            <span className="truncate">{successMessage}</span>
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
            <span className="text-[9px] text-slate-500 font-mono">Lot Size: {currentInstrument?.symbol === "NIFTY 50" ? 50 : currentInstrument?.symbol === "BANKNIFTY" ? 15 : 1}</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setQuantity((q) => Math.max(1, q - (currentInstrument?.symbol === "NIFTY 50" ? 50 : currentInstrument?.symbol === "BANKNIFTY" ? 15 : 1)))}
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
              onClick={() => setQuantity((q) => q + (currentInstrument?.symbol === "NIFTY 50" ? 50 : currentInstrument?.symbol === "BANKNIFTY" ? 15 : 1))}
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

        {/* Dynamic fields (Limit Price / Trigger Price) */}
        <div className="grid grid-cols-2 gap-2">
          <div className="flex flex-col gap-1">
            <span className="text-[9px] text-slate-500 uppercase tracking-wider">Limit Price</span>
            <input
              type="number"
              disabled={orderType === "MARKET"}
              value={limitPrice}
              onChange={(e) => setLimitPrice(Number(e.target.value))}
              className="w-full bg-slate-900 border border-white/5 rounded py-1 px-2 font-mono text-center text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:border-cyan-500/40"
            />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-[9px] text-slate-500 uppercase tracking-wider">Trigger Price</span>
            <input
              type="number"
              value={triggerPrice}
              onChange={(e) => setTriggerPrice(Number(e.target.value))}
              className="w-full bg-slate-900 border border-white/5 rounded py-1 px-2 font-mono text-center text-slate-200 focus:outline-none"
            />
          </div>
        </div>

        {/* Margin Preview & Risk HUD */}
        <div className="grid grid-cols-2 gap-2 bg-slate-950/40 p-2 rounded border border-white/5 font-mono text-[9px] text-slate-500 select-none">
          <div className="flex flex-col gap-0.5">
            <span>MARGIN REQ:</span>
            <span className="font-bold text-slate-300">
              ₹{marginRequired.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
            </span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span>RISK ESTIMATE:</span>
            <span className="font-bold text-slate-300">
              ₹{maxRisk.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
            </span>
          </div>
        </div>

        {/* Big Action Submit Buttons */}
        <div className="grid grid-cols-2 gap-2 pt-1 border-t border-white/5">
          <button
            onClick={() => handlePlaceOrder("BUY")}
            className="w-full bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold py-2 rounded text-xs transition-all uppercase tracking-wider cursor-pointer text-center shadow-lg shadow-emerald-500/10"
          >
            BUY
          </button>
          <button
            onClick={() => handlePlaceOrder("SELL")}
            className="w-full bg-rose-500 hover:bg-rose-400 text-slate-950 font-bold py-2 rounded text-xs transition-all uppercase tracking-wider cursor-pointer text-center shadow-lg shadow-rose-500/10"
          >
            SELL
          </button>
        </div>
      </div>

      {/* Mini Position Summary Panel */}
      <div className="p-3 bg-slate-950/40 border border-white/5 rounded-lg flex flex-col gap-2 flex-1 min-h-0 select-none">
        <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest border-b border-white/5 pb-1">
          Open Positions ({positions.length})
        </span>
        <div className="flex-1 overflow-y-auto flex flex-col gap-1.5 pr-1 font-sans text-xs scrollbar-thin scrollbar-thumb-white/5">
          {positions.length > 0 ? (
            positions.map((pos) => (
              <div 
                key={pos.symbol}
                className="p-2 rounded bg-slate-900/40 border border-white/5 flex flex-col gap-1 relative group"
              >
                <div className="flex justify-between items-center">
                  <span className="font-bold text-slate-200">{pos.symbol}</span>
                  <button 
                    onClick={() => closePosition(pos.symbol)}
                    className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-rose-400 transition-all absolute right-2 top-2 cursor-pointer"
                    title="Squareoff Position"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="grid grid-cols-4 text-[10px] text-slate-400 font-mono">
                  <div className="flex flex-col">
                    <span className="text-[8px] text-slate-600 font-sans uppercase">Side</span>
                    <span className={pos.side === "LONG" ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}>
                      {pos.side}
                    </span>
                  </div>
                  <div className="flex flex-col text-right">
                    <span className="text-[8px] text-slate-600 font-sans uppercase">Avg</span>
                    <span>₹{pos.avgPrice.toFixed(1)}</span>
                  </div>
                  <div className="flex flex-col text-right">
                    <span className="text-[8px] text-slate-600 font-sans uppercase">LTP</span>
                    <span>₹{pos.ltp.toFixed(1)}</span>
                  </div>
                  <div className="flex flex-col text-right">
                    <span className="text-[8px] text-slate-600 font-sans uppercase">PnL</span>
                    <span className={`font-bold ${pos.pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {pos.pnl >= 0 ? "+" : ""}₹{pos.pnl.toLocaleString("en-IN", { maximumFractionDigits: 1 })}
                    </span>
                  </div>
                </div>
              </div>
            ))
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
// 4. BOTTOM PANEL: TABBED PORTFOLIO LEDGER
// ==========================================
export const TradingBottom: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"positions" | "orders" | "trades" | "holdings" | "pnl">("positions");
  
  const status = useBackendTradingStore((state) => state.status);
  const tradesList = useBackendTradingStore((state) => state.trades);
  const gttOrdersList = useBackendTradingStore((state) => state.gttOrders);
  const cancelGttAction = useBackendTradingStore((state) => state.cancelGtt);
  const sellAction = useBackendTradingStore((state) => state.sell);

  // Positions mapped from status.position
  const positions = status?.position ? [{
    symbol: status.trading_symbol || "ACTIVE POSITION",
    qty: status.position.total_qty,
    side: "LONG" as const,
    avgPrice: status.position.entry_price,
    ltp: status.spot_price,
    pnl: status.total_pnl,
  }] : [];

  // Trades mapped from real trade logs
  const trades = tradesList.map((t) => ({
    tradeId: t.id || `T_${t.timestamp}`,
    symbol: t.trading_symbol,
    side: t.type,
    qty: t.quantity,
    entry: t.price,
    timestamp: t.timestamp,
  }));

  // GTT orders mapped to orders tab
  const orders = gttOrdersList.map((o) => ({
    orderId: o.id,
    symbol: status?.trading_symbol || "OPTION CONTRACT",
    side: o.side,
    type: o.order_type,
    qty: o.qty,
    price: o.price,
    status: o.status,
    timestamp: o.timestamp,
  }));

  const holdings: any[] = [];
  const realizedPnL = status?.total_pnl || 0.0;
  const unrealizedPnL = status?.position ? (status.spot_price - status.position.entry_price) * status.position.total_qty : 0.0;
  const brokerage = tradesList.length * 20.0; // Flat brokerage estimate
  const netPnL = realizedPnL + unrealizedPnL - brokerage;

  const closePosition = async () => {
    await sellAction();
  };

  const cancelOrder = async (id: string) => {
    await cancelGttAction(id);
  };

  const tabs = [
    { id: "positions" as const, name: `Positions (${positions.length})` },
    { id: "orders" as const, name: `Orders (${orders.length})` },
    { id: "trades" as const, name: `Trades (${trades.length})` },
    { id: "holdings" as const, name: `Holdings (${holdings.length})` },
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
        
        {/* Tab 1: Positions */}
        {activeTab === "positions" && (
          <table className="w-full text-left font-mono text-[10px]">
            <thead>
              <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-[9px] tracking-wider">
                <th className="py-1.5 pl-2">Symbol</th>
                <th className="py-1.5 text-center">Qty</th>
                <th className="py-1.5 text-center">Side</th>
                <th className="py-1.5 text-right">Avg Price</th>
                <th className="py-1.5 text-right">LTP</th>
                <th className="py-1.5 text-right">PnL</th>
                <th className="py-1.5 text-right pr-2">Action</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              {positions.length > 0 ? (
                positions.map((pos) => (
                  <tr key={pos.symbol} className="border-b border-white/[0.02] hover:bg-white/[0.01] transition-all">
                    <td className="py-1.5 pl-2 font-sans font-bold text-slate-200">{pos.symbol}</td>
                    <td className="py-1.5 text-center font-bold">{pos.qty}</td>
                    <td className="py-1.5 text-center">
                      <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold font-sans ${
                        pos.side === "LONG" ? "bg-emerald-950/40 text-emerald-400" : "bg-rose-950/40 text-rose-400"
                      }`}>
                        {pos.side}
                      </span>
                    </td>
                    <td className="py-1.5 text-right">₹{pos.avgPrice.toFixed(2)}</td>
                    <td className="py-1.5 text-right font-bold">₹{pos.ltp.toFixed(2)}</td>
                    <td className={`py-1.5 text-right font-bold ${pos.pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {pos.pnl >= 0 ? "+" : ""}₹{pos.pnl.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td className="py-1.5 text-right pr-2">
                      <button 
                        onClick={() => closePosition()}
                        className="bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded px-1.5 py-0.5 font-bold font-sans text-[8px] cursor-pointer"
                      >
                        CLOSE
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-slate-500 text-[10px] font-sans">
                    No active positions. Submit an order in the ticket.
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
                <th className="py-1.5 text-center">Side</th>
                <th className="py-1.5 text-center">Type</th>
                <th className="py-1.5 text-center">Qty</th>
                <th className="py-1.5 text-right">Price</th>
                <th className="py-1.5 text-center">Status</th>
                <th className="py-1.5 text-right pr-2">Time</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              {orders.length > 0 ? (
                orders.map((ord) => (
                  <tr key={ord.orderId} className="border-b border-white/[0.02] hover:bg-white/[0.01]">
                    <td className="py-1.5 pl-2 text-slate-500">{ord.orderId}</td>
                    <td className="py-1.5 font-sans font-bold text-slate-200">{ord.symbol}</td>
                    <td className="py-1.5 text-center">
                      <span className={`font-sans font-bold text-[9px] ${ord.side === "BUY" ? "text-emerald-400" : "text-rose-400"}`}>
                        {ord.side}
                      </span>
                    </td>
                    <td className="py-1.5 text-center font-bold text-slate-400">{ord.type}</td>
                    <td className="py-1.5 text-center font-semibold">{ord.qty}</td>
                    <td className="py-1.5 text-right">₹{ord.price.toFixed(2)}</td>
                    <td className="py-1.5 text-center flex items-center justify-center gap-1.5">
                      <span className={`px-1 py-0.5 rounded text-[8px] font-bold uppercase font-sans border ${
                        ord.status === "PENDING"
                          ? "bg-amber-950/20 text-amber-400 border-amber-800/30"
                          : ord.status === "TRIGGERED"
                          ? "bg-emerald-950/20 text-emerald-400 border-emerald-800/30"
                          : "bg-slate-900 text-slate-500 border-white/5"
                      }`}>
                        {ord.status}
                      </span>
                      {ord.status === "PENDING" && (
                        <button
                          onClick={() => cancelOrder(ord.orderId)}
                          className="bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded px-1.5 py-0.5 font-bold font-sans text-[8px] cursor-pointer"
                        >
                          CANCEL
                        </button>
                      )}
                    </td>
                    <td className="py-1.5 text-right pr-2 text-slate-500">{ord.timestamp}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} className="py-6 text-center text-slate-500 text-[10px] font-sans">
                    No orders placed in this session.
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
                <th className="py-1.5">Symbol</th>
                <th className="py-1.5 text-center">Side</th>
                <th className="py-1.5 text-center">Qty</th>
                <th className="py-1.5 text-right">Price</th>
                <th className="py-1.5 text-right pr-2">Timestamp</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              {trades.length > 0 ? (
                trades.map((trd) => (
                  <tr key={trd.tradeId} className="border-b border-white/[0.02] hover:bg-white/[0.01]">
                    <td className="py-1.5 pl-2 text-slate-500">{trd.tradeId}</td>
                    <td className="py-1.5 font-sans font-bold text-slate-200">{trd.symbol}</td>
                    <td className="py-1.5 text-center">
                      <span className={`font-sans font-bold text-[9px] ${trd.side === "BUY" ? "text-emerald-400" : "text-rose-400"}`}>
                        {trd.side}
                      </span>
                    </td>
                    <td className="py-1.5 text-center">{trd.qty}</td>
                    <td className="py-1.5 text-right">₹{trd.entry.toFixed(2)}</td>
                    <td className="py-1.5 text-right pr-2 text-slate-500">{trd.timestamp}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-slate-500 text-[10px] font-sans">
                    No executed trades recorded.
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
                <th className="py-1.5 pl-2">Instrument</th>
                <th className="py-1.5 text-center">Qty</th>
                <th className="py-1.5 text-right">Avg Cost</th>
                <th className="py-1.5 text-right">Market Value</th>
                <th className="py-1.5 text-right pr-2">PnL</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              {holdings.length > 0 ? (
                holdings.map((hold) => (
                  <tr key={hold.instrument} className="border-b border-white/[0.02]">
                    <td className="py-1.5 pl-2 font-sans font-bold text-slate-200">{hold.instrument}</td>
                    <td className="py-1.5 text-center">{hold.qty}</td>
                    <td className="py-1.5 text-right">₹{hold.avgCost.toFixed(2)}</td>
                    <td className="py-1.5 text-right font-bold">₹{hold.marketValue.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                    <td className={`py-1.5 text-right font-bold ${hold.pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {hold.pnl >= 0 ? "+" : ""}₹{hold.pnl.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-slate-500 text-[10px] font-sans">
                    No long-term holdings in active session desk.
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
