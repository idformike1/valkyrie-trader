"use client";

import React, { useState, useEffect, useRef } from "react";
import { createChart, IChartApi, ISeriesApi, UTCTimestamp, CandlestickSeries, AreaSeries, createSeriesMarkers } from "lightweight-charts";
import { 
  Play, Activity, Terminal, Shield, Cpu, RefreshCw, BarChart2,
  TrendingUp, Layers, Server, Settings, Zap, ArrowUpRight, ArrowDownRight,
  Sliders, Search, Plus, Trash2, SlidersHorizontal, Lock, CheckCircle2, 
  AlertTriangle, Filter, Calendar, DollarSign, Percent, ChevronRight
} from "lucide-react";
import { useTerminalStore, Strategy } from "@/store/useTerminalStore";
import { useEventStore } from "@/store/useEventStore";
import { useBackendTradingStore } from "@/services/tradingQueries";

// Shared backtest parameter cache to coordinate between panels
let currentBacktestParams: Record<string, number> = {};

const getBackendStrategyName = (strategyId: string): string => {
  if (strategyId === "heikin_ashi_gar" || strategyId === "five_ema_scalping") {
    return strategyId;
  }
  if (strategyId === "str_mean") {
    return "heikin_ashi_gar";
  }
  return "five_ema_scalping";
};

const fetchExpiry = async (indexName: string): Promise<string> => {
  try {
    const res = await fetch(`http://localhost:8081/api/options/metadata?exchange=NSE&index=${indexName}`);
    if (res.ok) {
      const data = await res.json();
      if (data.expiries && data.expiries.length > 0) {
        return data.expiries[0];
      }
    }
  } catch (e) {
    console.error("Failed to fetch expiry metadata:", e);
  }
  return "2026-06-04"; // Fallback contract
};

// Helper components for professional styling
const GlowingCard: React.FC<{ title: string; children: React.ReactNode; className?: string }> = ({ title, children, className = "" }) => (
  <div className={`p-3 flex flex-col h-full bg-slate-950/40 border border-white/5 rounded-lg hover:border-cyan-500/10 transition-all ${className}`}>
    <h3 className="text-[10px] font-bold tracking-widest text-cyan-400 uppercase border-b border-white/5 pb-1.5 mb-2.5 flex items-center justify-between">
      <span>{title}</span>
      <span className="w-1 h-1 rounded-full bg-cyan-400 animate-pulse" />
    </h3>
    <div className="flex-1 overflow-y-auto min-h-0">{children}</div>
  </div>
);

// MOCK STRATEGY REPOSITORY
interface StrategyRepoItem {
  id: string;
  name: string;
  version: string;
  status: "Draft" | "Testing" | "Validated" | "Archived";
  promotionState: "Draft" | "Paper Approved" | "Live Approved" | "Archived";
  createdDate: string;
  lastRun: string;
  parameters: Record<string, { type: "number"; label: string; default: number }>;
}

const AVAILABLE_STRATEGIES: StrategyRepoItem[] = [
  {
    id: "heikin_ashi_gar",
    name: "Heikin Ashi GAR Strategy",
    version: "v1.0",
    status: "Validated",
    promotionState: "Live Approved",
    createdDate: "2026-04-10",
    lastRun: "Never",
    parameters: {
      max_candles: { type: "number", label: "Max Candles Limit", default: 10 },
      slippage_pct: { type: "number", label: "Slippage %", default: 0.05 },
    }
  },
  {
    id: "five_ema_scalping",
    name: "5 EMA Scalping Strategy",
    version: "v1.5",
    status: "Testing",
    promotionState: "Paper Approved",
    createdDate: "2026-05-15",
    lastRun: "Never",
    parameters: {
      five_ema_period: { type: "number", label: "EMA Period", default: 5 },
      five_ema_rr: { type: "number", label: "EMA Risk-Reward", default: 3.0 },
    }
  },
  {
    id: "str_ema",
    name: "EMA Crossover",
    version: "v2.1",
    status: "Validated",
    promotionState: "Live Approved",
    createdDate: "2026-02-12",
    lastRun: "2026-05-28 14:22",
    parameters: {
      fastEma: { type: "number", label: "EMA Fast", default: 9 },
      slowEma: { type: "number", label: "EMA Slow", default: 21 },
      riskPct: { type: "number", label: "Risk % per Trade", default: 1.5 },
      positionSize: { type: "number", label: "Max Position Size", default: 100 },
    }
  },
  {
    id: "str_mean",
    name: "Bollinger Mean Reversion",
    version: "v1.0",
    status: "Testing",
    promotionState: "Draft",
    createdDate: "2026-05-01",
    lastRun: "2026-05-29 09:12",
    parameters: {
      bbPeriod: { type: "number", label: "BB Period", default: 20 },
      stdDev: { type: "number", label: "Standard Deviation", default: 2.0 },
      atrStop: { type: "number", label: "ATR Stop Mult", default: 1.5 },
      positionSize: { type: "number", label: "Max Position Size", default: 50 },
    }
  },
  {
    id: "str_vwap",
    name: "VWAP Breakout Signal",
    version: "v3.4",
    status: "Validated",
    promotionState: "Paper Approved",
    createdDate: "2026-01-20",
    lastRun: "2026-05-27 18:05",
    parameters: {
      vwapMult: { type: "number", label: "VWAP Band Mult", default: 1.25 },
      atrFilter: { type: "number", label: "ATR Volatility Filter", default: 2.1 },
      riskPct: { type: "number", label: "Risk % per Trade", default: 2.0 },
      positionSize: { type: "number", label: "Max Position Size", default: 150 },
    }
  },
  {
    id: "str_macd",
    name: "MACD Momentum Trigger",
    version: "v1.2",
    status: "Archived",
    promotionState: "Archived",
    createdDate: "2025-11-15",
    lastRun: "2026-03-01 10:00",
    parameters: {
      macdFast: { type: "number", label: "MACD Fast", default: 12 },
      macdSlow: { type: "number", label: "MACD Slow", default: 26 },
      macdSignal: { type: "number", label: "MACD Signal", default: 9 },
      positionSize: { type: "number", label: "Max Position Size", default: 75 },
    }
  }
];

// ==========================================
// 1. LEFT PANEL: STRATEGY REPOSITORY
// ==========================================
export const BacktestLeft: React.FC = () => {
  const selectedStrategy = useTerminalStore((state) => state.selectedStrategy);
  const setStrategy = useTerminalStore((state) => state.setStrategy);
  
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState<string>("All");

  const handleSelect = (item: StrategyRepoItem) => {
    setStrategy({
      strategyId: item.id,
      strategyName: item.name,
      version: item.version,
    });
  };

  const filtered = AVAILABLE_STRATEGIES.filter((str) => {
    const matchesSearch = str.name.toLowerCase().includes(search.toLowerCase());
    const matchesFilter = activeFilter === "All" || str.status === activeFilter;
    return matchesSearch && matchesFilter;
  });

  return (
    <GlowingCard title="Strategy Repository">
      <div className="flex flex-col gap-2 h-full font-sans text-xs">
        {/* Search */}
        <div className="relative shrink-0">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search strategies..."
            className="w-full bg-slate-900/60 border border-white/5 rounded pl-8 pr-3 py-1.5 text-[11px] text-slate-300 focus:outline-none focus:border-cyan-500/40"
          />
        </div>

        {/* Filter buttons grid */}
        <div className="grid grid-cols-2 gap-1.5 shrink-0 select-none">
          {["All", "Validated", "Testing", "Draft"].map((status) => (
            <button
              key={status}
              onClick={() => setActiveFilter(status)}
              className={`py-1 rounded text-[10px] font-bold transition-all cursor-pointer text-center border ${
                activeFilter === status
                  ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400"
                  : "bg-slate-900 border-white/5 text-slate-500 hover:text-slate-300"
              }`}
            >
              {status}
            </button>
          ))}
        </div>

        {/* Repository List */}
        <div className="flex-1 overflow-y-auto flex flex-col gap-1.5 mt-2 pr-1 scrollbar-thin scrollbar-thumb-white/5">
          {filtered.map((item) => {
            const isSelected = selectedStrategy?.strategyId === item.id;
            return (
              <div
                key={item.id}
                onClick={() => handleSelect(item)}
                className={`p-2.5 rounded border transition-all cursor-pointer flex flex-col gap-1.5 relative ${
                  isSelected
                    ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400"
                    : "bg-slate-950/20 border-white/5 hover:bg-white/5 text-slate-300"
                }`}
              >
                <div className="flex justify-between items-start">
                  <span className="font-bold uppercase tracking-wider text-[11px] truncate mr-2">
                    {item.name}
                  </span>
                  <span className="font-mono text-[9px] text-slate-500 font-bold bg-slate-900 px-1 border border-white/5 rounded">
                    {item.version}
                  </span>
                </div>

                <div className="flex justify-between items-center text-[10px] text-slate-500 select-none">
                  <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold ${
                    item.status === "Validated" ? "bg-emerald-950/40 text-emerald-400" :
                    item.status === "Testing" ? "bg-amber-950/40 text-amber-400" : "bg-slate-900 text-slate-400"
                  }`}>
                    {item.promotionState}
                  </span>
                  <span className="text-[9px] font-mono">Run: {item.lastRun.split(" ")[0]}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </GlowingCard>
  );
};

// ==========================================
// 2. MAIN PANEL: HISTORICAL CHART & RUN TOOLBAR
// ==========================================
export const BacktestMain: React.FC = () => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  const selectedStrategy = useTerminalStore((state) => state.selectedStrategy);
  const selectedInstrument = useTerminalStore((state) => state.selectedInstrument);
  const addEvent = useEventStore((state) => state.addEvent);

  const [dateRange, setDateRange] = useState("2026-01-01 to 2026-05-28");
  const [initialCapital, setInitialCapital] = useState(1000000);
  const [isRunning, setIsRunning] = useState(false);
  const [runProgress, setRunProgress] = useState(0);

  const startBacktest = useBackendTradingStore((state) => state.startBacktest);
  const connectTelemetry = useBackendTradingStore((state) => state.connectTelemetry);
  const disconnectTelemetry = useBackendTradingStore((state) => state.disconnectTelemetry);
  const candles = useBackendTradingStore((state) => state.candles);
  const trades = useBackendTradingStore((state) => state.trades);

  useEffect(() => {
    connectTelemetry();
    return () => {
      disconnectTelemetry();
    };
  }, [connectTelemetry, disconnectTelemetry]);

  // TV Lightweight Chart rendering from backend data
  useEffect(() => {
    if (!chartContainerRef.current) return;

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
      height: 360,
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
      rightPriceScale: {
        borderColor: themeColors.border,
        textColor: themeColors.text,
      },
      timeScale: {
        borderColor: themeColors.border,
        timeVisible: true,
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

    if (candles && candles.length > 0) {
      const priceData = candles
        .map((c) => ({
          time: c.time as UTCTimestamp,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }))
        .sort((a, b) => a.time - b.time);
      candleSeries.setData(priceData);

      // Render actual execution trade markers
      const markers = trades.map((t) => {
        const tradeTime = Math.floor(new Date(t.timestamp).getTime() / 1000) as UTCTimestamp;
        return {
          time: tradeTime,
          position: t.type === "BUY" ? ("belowBar" as const) : ("aboveBar" as const),
          color: t.type === "BUY" ? "#10b981" : "#ef4444",
          shape: t.type === "BUY" ? ("arrowUp" as const) : ("arrowDown" as const),
          text: t.type,
        };
      });
      markers.sort((a, b) => (a.time as number) - (b.time as number));
      createSeriesMarkers(candleSeries, markers);
      chart.timeScale().fitContent();
    }

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;

    const observer = new ResizeObserver((entries) => {
      if (entries[0] && chartRef.current) {
        const { width, height } = entries[0].contentRect;
        chartRef.current.resize(width, Math.max(260, height));
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
  }, [candles, trades]);

  // Run real backtesting engine on backend
  const handleRunBacktest = async () => {
    if (!selectedStrategy) return;

    setIsRunning(true);
    setRunProgress(0);
    
    addEvent({
      type: "info",
      message: `INITIATING BACKTEST: ${selectedStrategy.strategyName} ${selectedStrategy.version} | Capital: ₹${initialCapital.toLocaleString("en-IN")}`,
      workspace: "Backtest",
    });

    const indexName = selectedInstrument?.symbol.includes("BANK") ? "BANKNIFTY" : "NIFTY";
    const expiry = await fetchExpiry(indexName);

    const parts = dateRange.split(" to ");
    const start_date = parts[0] || "2026-01-01";
    const end_date = parts[1] || "2026-05-28";

    const backendStrategy = getBackendStrategyName(selectedStrategy.strategyId);

    // Map sliders values to parameters expected by strategies
    const mappedParams: Record<string, any> = {};
    if (backendStrategy === "five_ema_scalping") {
      mappedParams.five_ema_period = currentBacktestParams.five_ema_period || currentBacktestParams.fiveEma || currentBacktestParams.macdFast || 5;
      mappedParams.five_ema_rr = currentBacktestParams.five_ema_rr || currentBacktestParams.riskPct || 3.0;
    } else {
      mappedParams.max_candles = currentBacktestParams.max_candles || currentBacktestParams.positionSize || 10;
      mappedParams.slippage_pct = currentBacktestParams.slippage_pct || 0.05;
    }

    const payload = {
      mode: "BACKTEST" as const,
      strategy: backendStrategy,
      index_name: indexName,
      expiry,
      option_type: "CE",
      strike: "ATM",
      start_date,
      end_date,
      timeframe: "1minute",
      initial_balance: initialCapital,
      ...mappedParams
    };

    const success = await startBacktest(payload);
    if (!success) {
      setIsRunning(false);
      addEvent({
        type: "error",
        message: `Backtest start request failed.`,
        workspace: "Backtest",
      });
      return;
    }

    const interval = setInterval(() => {
      const currentStatus = useBackendTradingStore.getState().status;
      const currentState = currentStatus?.state;

      if (currentState === "COMPLETED") {
        clearInterval(interval);
        setIsRunning(false);
        setRunProgress(100);
        addEvent({
          type: "success",
          message: `BACKTEST COMPLETED - Profit: ₹${(currentStatus?.total_pnl || 0).toLocaleString("en-IN")} | Win Rate: ${currentStatus?.win_rate?.toFixed(1) || 0}%`,
          workspace: "Backtest",
        });
      } else if (currentState === "FAILED") {
        clearInterval(interval);
        setIsRunning(false);
        setRunProgress(0);
        addEvent({
          type: "error",
          message: `BACKTEST FAILED. Check backend console logs.`,
          workspace: "Backtest",
        });
      } else {
        setRunProgress((prev) => {
          if (prev >= 90) {
            return 90;
          }
          return prev + 15;
        });
      }
    }, 150);
  };

  return (
    <div className="flex flex-col h-full bg-slate-950/60 border border-white/5 rounded-lg overflow-hidden font-sans text-xs">
      
      {/* Run Parameter Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-900/50 border-b border-white/5 select-none shrink-0 flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <div className="flex flex-col gap-0.5">
            <span className="text-[8px] text-slate-500 font-bold uppercase">Active Strategy</span>
            <span className="text-cyan-400 font-bold font-mono">
              {selectedStrategy?.strategyName || "No Strategy Selected"} {selectedStrategy?.version}
            </span>
          </div>

          <div className="h-6 w-px bg-white/5" />

          {/* Date Range Selector */}
          <div className="flex flex-col gap-0.5">
            <span className="text-[8px] text-slate-500 font-bold uppercase">Date Range</span>
            <input
              type="text"
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="bg-slate-900/80 border border-white/10 rounded px-1.5 py-0.5 text-[10px] text-slate-300 focus:outline-none font-mono"
            />
          </div>

          {/* Capital Input */}
          <div className="flex flex-col gap-0.5">
            <span className="text-[8px] text-slate-500 font-bold uppercase">Capital (₹)</span>
            <input
              type="number"
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value))}
              className="bg-slate-900/80 border border-white/10 rounded px-1.5 py-0.5 w-24 text-[10px] text-slate-300 focus:outline-none font-mono"
            />
          </div>
        </div>

        {/* Buttons */}
        <div className="flex items-center gap-2">
          {isRunning ? (
            <div className="flex items-center gap-2">
              <div className="w-20 bg-slate-800 h-1.5 rounded-full overflow-hidden">
                <div style={{ width: `${runProgress}%` }} className="bg-cyan-400 h-full transition-all duration-300" />
              </div>
              <span className="text-[9px] font-mono text-cyan-400 font-bold">{runProgress}%</span>
            </div>
          ) : (
            <button
              onClick={handleRunBacktest}
              className="bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold px-3 py-1 rounded transition-all cursor-pointer text-center flex items-center gap-1.5 tracking-wider uppercase text-[10px]"
            >
              <Play className="w-3 h-3 fill-slate-950" />
              Run Backtest
            </button>
          )}

          <button className="bg-slate-900 border border-white/10 hover:border-white/20 text-slate-400 hover:text-slate-200 px-3 py-1 rounded transition-all cursor-pointer text-center text-[10px]">
            Optimize
          </button>
        </div>
      </div>

      {/* Candlestick simulator canvas */}
      <div className="flex-1 min-h-0 relative">
        <div ref={chartContainerRef} className="w-full h-full min-h-0" />
      </div>
    </div>
  );
};

// ==========================================
// 3. RIGHT PANEL: STRATEGY PARAMETERS
// ==========================================
export const BacktestRight: React.FC = () => {
  const selectedStrategy = useTerminalStore((state) => state.selectedStrategy);
  const [params, setParams] = useState<Record<string, number>>({});

  // Sync parameter presets when active strategy swaps
  useEffect(() => {
    if (!selectedStrategy) return;
    const item = AVAILABLE_STRATEGIES.find((s) => s.id === selectedStrategy.strategyId);
    if (!item) return;

    const initial: Record<string, number> = {};
    Object.keys(item.parameters).forEach((key) => {
      initial[key] = item.parameters[key].default;
    });
    setParams(initial);
    currentBacktestParams = initial;
  }, [selectedStrategy]);

  const handleParamChange = (key: string, val: number) => {
    setParams((prev) => {
      const updated = { ...prev, [key]: val };
      currentBacktestParams = updated;
      return updated;
    });
  };

  const item = AVAILABLE_STRATEGIES.find((s) => s.id === selectedStrategy?.strategyId);

  return (
    <GlowingCard title="Parameters">
      <div className="flex flex-col gap-3 h-full font-sans text-xs">
        <div className="text-[10px] text-slate-500 border-b border-white/5 pb-1 select-none">
          CONFIGURE STRATEGY CONTROLS
        </div>

        {item ? (
          <div className="flex-1 flex flex-col gap-3 overflow-y-auto pr-1">
            {Object.keys(item.parameters).map((key) => {
              const p = item.parameters[key];
              const val = params[key] !== undefined ? params[key] : p.default;

              return (
                <div key={key} className="flex flex-col gap-1">
                  <div className="flex justify-between items-center text-[10px] text-slate-400">
                    <span className="font-semibold">{p.label}</span>
                    <span className="font-mono text-cyan-400 font-bold bg-slate-900/60 px-1.5 py-0.5 rounded border border-white/5">
                      {val}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={key.includes("Ema") || key.includes("macd") ? 2 : 1}
                    max={key.includes("slow") || key.includes("macd") ? 200 : 50}
                    step={key.includes("riskPct") || key.includes("stdDev") || key.includes("vwap") ? 0.05 : 1}
                    value={val}
                    onChange={(e) => handleParamChange(key, Number(e.target.value))}
                    className="w-full accent-cyan-400 bg-slate-900 cursor-pointer h-1.5 rounded-lg"
                  />
                </div>
              );
            })}

            <div className="mt-4 pt-3 border-t border-white/5 flex flex-col gap-1.5">
              <span className="text-[9px] text-slate-500 uppercase tracking-widest font-bold">Commission Model</span>
              <select className="bg-slate-900 border border-white/10 rounded px-2 py-1 text-slate-300 focus:outline-none">
                <option>Percentage (0.03%)</option>
                <option>Fixed Flat (₹20 per order)</option>
                <option>Zero Slippage Model</option>
              </select>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-500 text-[10px] text-center px-4">
            Select a strategy from the repository to configure parameter controls.
          </div>
        )}
      </div>
    </GlowingCard>
  );
};

// ==========================================
// 4. BOTTOM PANEL: TABBED ANALYSIS RESULTS
// ==========================================
export const BacktestBottom: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"overview" | "trades" | "equity" | "drawdown" | "metrics" | "logs">("overview");
  const equityContainerRef = useRef<HTMLDivElement>(null);
  const drawdownContainerRef = useRef<HTMLDivElement>(null);

  const status = useBackendTradingStore((state) => state.status);
  const trades = useBackendTradingStore((state) => state.trades);
  const logs = useBackendTradingStore((state) => state.logs);
  const equityCurve = useBackendTradingStore((state) => state.equityCurve);

  const netProfit = status?.total_pnl || 0;
  const returnPct = status?.return_percent || 0;
  const winRate = status?.win_rate || 0;
  const sharpe = status?.sharpe_ratio || 0;
  const maxDrawdown = status?.max_drawdown || 0;
  const profitFactor = status?.profit_factor || 0;
  const totalTrades = status?.total_trades || 0;

  // Render Equity Curve Chart on Tab Load
  useEffect(() => {
    if (activeTab !== "equity" || !equityContainerRef.current || !equityCurve || equityCurve.length === 0) return;
    
    // Clear out container
    equityContainerRef.current.innerHTML = "";

    const chart = createChart(equityContainerRef.current, {
      width: equityContainerRef.current.clientWidth,
      height: 140,
      layout: {
        background: { color: "transparent" },
        textColor: "#64748b",
        fontSize: 9,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.02)" },
        horzLines: { color: "rgba(255,255,255,0.02)" },
      },
    });

    const series = chart.addSeries(AreaSeries, {
      lineColor: "#06b6d4",
      topColor: "rgba(6, 182, 212, 0.2)",
      bottomColor: "rgba(6, 182, 212, 0.0)",
      lineWidth: 2,
    });

    const rawPoints = equityCurve.map((pt) => ({
      time: Math.floor(new Date(pt.timestamp).getTime() / 1000) as UTCTimestamp,
      value: pt.equity,
    }));

    if (rawPoints.length > 1) {
      const firstTradeTime = rawPoints[1].time;
      if (rawPoints[0].time > firstTradeTime) {
        rawPoints[0].time = (firstTradeTime - 60) as UTCTimestamp;
      }
    }
    const points = rawPoints.sort((a, b) => a.time - b.time);
    series.setData(points);
    chart.timeScale().fitContent();

    return () => chart.remove();
  }, [activeTab, equityCurve]);

  // Render Drawdown Chart on Tab Load
  useEffect(() => {
    if (activeTab !== "drawdown" || !drawdownContainerRef.current || !equityCurve || equityCurve.length === 0) return;
    
    drawdownContainerRef.current.innerHTML = "";

    const chart = createChart(drawdownContainerRef.current, {
      width: drawdownContainerRef.current.clientWidth,
      height: 140,
      layout: {
        background: { color: "transparent" },
        textColor: "#64748b",
        fontSize: 9,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.02)" },
        horzLines: { color: "rgba(255,255,255,0.02)" },
      },
    });

    const series = chart.addSeries(AreaSeries, {
      lineColor: "#ef4444",
      topColor: "rgba(239, 68, 68, 0.15)",
      bottomColor: "rgba(239, 68, 68, 0.0)",
      lineWidth: 2,
    });

    let peak = equityCurve[0]?.equity || 100000;
    const rawPoints = equityCurve.map((pt) => {
      const eq = pt.equity;
      if (eq > peak) peak = eq;
      const dd = ((peak - eq) / peak) * -100;
      return {
        time: Math.floor(new Date(pt.timestamp).getTime() / 1000) as UTCTimestamp,
        value: dd
      };
    });

    if (rawPoints.length > 1) {
      const firstTradeTime = rawPoints[1].time;
      if (rawPoints[0].time > firstTradeTime) {
        rawPoints[0].time = (firstTradeTime - 60) as UTCTimestamp;
      }
    }
    const points = rawPoints.sort((a, b) => a.time - b.time);
    series.setData(points);
    chart.timeScale().fitContent();

    return () => chart.remove();
  }, [activeTab, equityCurve]);

  const tabs = [
    { id: "overview" as const, name: "Overview" },
    { id: "trades" as const, name: "Trade List" },
    { id: "equity" as const, name: "Equity Curve" },
    { id: "drawdown" as const, name: "Drawdown" },
    { id: "metrics" as const, name: "Metrics" },
    { id: "logs" as const, name: "Execution Logs" },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden text-xs font-sans">
      
      {/* Tabs selectors */}
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

      {/* Tabs Container */}
      <div className="flex-1 overflow-y-auto p-3 scrollbar-thin scrollbar-thumb-white/5 scrollbar-track-transparent min-h-0">
        
        {/* Overview Tab */}
        {activeTab === "overview" && (
          <div className="grid grid-cols-4 gap-3 max-w-4xl font-mono text-[10px] select-none">
            <div className="bg-slate-900/20 border border-white/5 p-2 rounded">
              <span className="text-[8px] text-slate-500 uppercase block">Net Profit</span>
              <span className={`font-bold text-sm ${netProfit >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                ₹{netProfit.toLocaleString("en-IN")}
              </span>
            </div>
            <div className="bg-slate-900/20 border border-white/5 p-2 rounded">
              <span className="text-[8px] text-slate-500 uppercase block">Est Return</span>
              <span className="text-slate-200 font-bold text-sm">{returnPct.toFixed(2)}%</span>
            </div>
            <div className="bg-slate-900/20 border border-white/5 p-2 rounded">
              <span className="text-[8px] text-slate-500 uppercase block">Win Rate</span>
              <span className="text-slate-200 font-bold text-sm">{winRate.toFixed(1)}%</span>
            </div>
            <div className="bg-slate-900/20 border border-white/5 p-2 rounded">
              <span className="text-[8px] text-slate-500 uppercase block">Sharpe Ratio</span>
              <span className="text-cyan-400 font-bold text-sm">{sharpe.toFixed(2)}</span>
            </div>
          </div>
        )}

        {/* Trade List Tab */}
        {activeTab === "trades" && (
          <table className="w-full text-left font-mono text-[10px]">
            <thead>
              <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-[8px] tracking-wider">
                <th className="py-1 pl-2">Trade ID</th>
                <th className="py-1">Timestamp</th>
                <th className="py-1 text-center">Type</th>
                <th className="py-1 text-right">Price</th>
                <th className="py-1 text-center">Qty</th>
                <th className="py-1 text-right">PnL</th>
                <th className="py-1 text-right pr-2">Reason</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              {trades.map((t, idx) => (
                <tr key={t.id || idx} className="border-b border-white/[0.02]">
                  <td className="py-1.5 pl-2 text-slate-500">{t.id || idx + 1}</td>
                  <td className="py-1.5">{t.timestamp}</td>
                  <td className="py-1.5 text-center">
                    <span className={`px-1.5 py-0.5 rounded text-[8px] font-sans font-bold ${
                      t.type === "BUY" ? "bg-emerald-950/30 text-emerald-400" : "bg-rose-950/30 text-rose-400"
                    }`}>
                      {t.type}
                    </span>
                  </td>
                  <td className="py-1.5 text-right">₹{(t.price || 0).toFixed(2)}</td>
                  <td className="py-1.5 text-center">{t.quantity}</td>
                  <td className={`py-1.5 text-right font-bold ${t.pnl > 0 ? "text-emerald-400" : t.pnl < 0 ? "text-rose-400" : "text-slate-400"}`}>
                    {t.pnl > 0 ? "+" : ""}₹{(t.pnl || 0).toFixed(2)}
                  </td>
                  <td className="py-1.5 text-right pr-2 text-slate-500">{t.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Equity Curve Tab */}
        {activeTab === "equity" && (
          <div className="w-full h-36 relative">
            <div ref={equityContainerRef} className="w-full h-full" />
          </div>
        )}

        {/* Drawdown Tab */}
        {activeTab === "drawdown" && (
          <div className="w-full h-36 relative">
            <div ref={drawdownContainerRef} className="w-full h-full" />
          </div>
        )}

        {/* Metrics Tab */}
        {activeTab === "metrics" && (
          <div className="grid grid-cols-2 gap-4 max-w-2xl font-mono text-[10px] select-none">
            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between border-b border-white/5 py-1">
                <span className="text-slate-500">PROFIT FACTOR:</span>
                <span className="text-slate-300 font-bold">{profitFactor.toFixed(2)}</span>
              </div>
              <div className="flex justify-between border-b border-white/5 py-1">
                <span className="text-slate-500">SHARPE RATIO:</span>
                <span className="text-slate-300 font-bold">{sharpe.toFixed(2)}</span>
              </div>
              <div className="flex justify-between border-b border-white/5 py-1">
                <span className="text-slate-500">MAX DRAWDOWN:</span>
                <span className="text-rose-400 font-bold">-{maxDrawdown.toFixed(2)}%</span>
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between border-b border-white/5 py-1">
                <span className="text-slate-500">TOTAL TRADES:</span>
                <span className="text-slate-300 font-bold">{totalTrades}</span>
              </div>
              <div className="flex justify-between border-b border-white/5 py-1">
                <span className="text-slate-500">WIN RATE:</span>
                <span className="text-emerald-400 font-bold">{winRate.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between border-b border-white/5 py-1">
                <span className="text-slate-500">INITIAL CAPITAL:</span>
                <span className="text-slate-300 font-bold">₹{(status?.initial_balance || 0).toLocaleString("en-IN")}</span>
              </div>
            </div>
          </div>
        )}

        {/* Logs Tab */}
        {activeTab === "logs" && (
          <div className="font-mono text-[9px] text-slate-400 flex flex-col gap-1 max-w-5xl select-text">
            {logs && logs.length > 0 ? (
              logs.map((log, idx) => <span key={idx}>{log}</span>)
            ) : (
              <span className="text-slate-600">No logs generated. Run a backtest first.</span>
            )}
          </div>
        )}

      </div>
    </div>
  );
};
