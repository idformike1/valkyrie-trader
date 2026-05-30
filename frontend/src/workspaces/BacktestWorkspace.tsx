"use client";

import React, { useState, useEffect, useRef } from "react";
import { createChart, IChartApi, ISeriesApi, UTCTimestamp, CandlestickSeries, AreaSeries, createSeriesMarkers } from "lightweight-charts";
import { 
  Play, Activity, Terminal, Shield, Cpu, RefreshCw, BarChart2,
  TrendingUp, Layers, Server, Settings, Zap, ArrowUpRight, ArrowDownRight,
  Sliders, Search, Plus, Trash2, SlidersHorizontal, Lock, CheckCircle2, 
  AlertTriangle, Filter, Calendar, DollarSign, Percent, ChevronRight, Grid, AlertCircle
} from "lucide-react";
import { useTerminalStore } from "@/store/useTerminalStore";
import { useEventStore } from "@/store/useEventStore";
import { useBacktestStore, V2Config } from "@/store/useBacktestStore";

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

// STRATEGY DEFINITIONS
interface StrategyRepoItem {
  id: string;
  name: string;
  version: string;
  status: "Draft" | "Testing" | "Validated" | "Archived";
  promotionState: "Draft" | "Paper Approved" | "Live Approved" | "Archived";
  createdDate: string;
  lastRun: string;
}

const AVAILABLE_STRATEGIES: StrategyRepoItem[] = [
  {
    id: "EMA",
    name: "EMA Crossover Strategy",
    version: "v2.0",
    status: "Validated",
    promotionState: "Live Approved",
    createdDate: "2025-04-10",
    lastRun: "2025-05-14"
  },
  {
    id: "heikin_ashi_gar",
    name: "Heikin Ashi GAR Strategy",
    version: "v1.0",
    status: "Validated",
    promotionState: "Live Approved",
    createdDate: "2025-04-10",
    lastRun: "Never"
  },
  {
    id: "five_ema_scalping",
    name: "5 EMA Scalping Strategy",
    version: "v1.5",
    status: "Testing",
    promotionState: "Paper Approved",
    createdDate: "2025-05-15",
    lastRun: "Never"
  }
];

// ==========================================
// 1. LEFT PANEL: STRATEGY REPOSITORY
// ==========================================
export const BacktestLeft: React.FC = () => {
  const selectedStrategy = useTerminalStore((state) => state.selectedStrategy);
  const setStrategy = useTerminalStore((state) => state.setStrategy);
  const v2Config = useBacktestStore((state) => state.v2Config);
  const setV2Config = useBacktestStore((state) => state.setV2Config);
  
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState<string>("All");

  const handleSelect = (item: StrategyRepoItem) => {
    setStrategy({
      strategyId: item.id,
      strategyName: item.name,
      version: item.version,
    });
    
    // Update store config strategy
    setV2Config({
      strategy_name: item.id,
      strategy_params: item.id === "EMA" 
        ? { fastEma: 2, slowEma: 3, cut_off_time: "15:25" } 
        : item.id === "five_ema_scalping"
        ? { five_ema_period: 5, five_ema_rr: 3.0 }
        : { max_candles: 10 }
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
                  <span className="text-[9px] font-mono">Run: {item.lastRun}</span>
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
  const addEvent = useEventStore((state) => state.addEvent);

  const v2Config = useBacktestStore((state) => state.v2Config);
  const setV2Config = useBacktestStore((state) => state.setV2Config);
  const runV2Backtest = useBacktestStore((state) => state.runV2Backtest);
  const v2BacktestResult = useBacktestStore((state) => state.v2BacktestResult);
  const v2Status = useBacktestStore((state) => state.v2Status);
  const isBacktestLoading = useBacktestStore((state) => state.isBacktestLoading);

  const handleRunBacktest = async () => {
    if (!selectedStrategy) return;

    addEvent({
      type: "info",
      message: `INITIATING V2 ENGINE BACKTEST: ${v2Config.strategy_name} | Date: ${v2Config.start_date} to ${v2Config.end_date} | Capital: ₹${v2Config.initial_capital.toLocaleString("en-IN")}`,
      workspace: "Backtest",
    });

    const success = await runV2Backtest();
    if (success) {
      const metrics = useBacktestStore.getState().v2BacktestResult?.report;
      addEvent({
        type: "success",
        message: `BACKTEST COMPLETED - Net Profit: ₹${(metrics?.performance?.net_profit || 0).toLocaleString("en-IN")} | Win Rate: ${metrics?.trade_stats?.win_rate?.toFixed(1) || 0}% | Sharpe: ${metrics?.sharpe_ratio?.toFixed(2) || 0}`,
        workspace: "Backtest",
      });
    } else {
      const err = useBacktestStore.getState().v2Status.error;
      addEvent({
        type: "error",
        message: `BACKTEST FAILED: ${err || "Check backend console logs"}`,
        workspace: "Backtest",
      });
    }
  };

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

    if (v2BacktestResult && v2BacktestResult.candles && v2BacktestResult.candles.length > 0) {
      const priceData = v2BacktestResult.candles
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
      if (v2BacktestResult.chart_trades) {
        const markers = v2BacktestResult.chart_trades.map((t) => {
          const tradeTime = Math.floor(new Date(t.timestamp).getTime() / 1000) as UTCTimestamp;
          return {
            time: tradeTime,
            position: t.type === "BUY" ? ("belowBar" as const) : ("aboveBar" as const),
            color: t.type === "BUY" ? "#10b981" : "#ef4444",
            shape: t.type === "BUY" ? ("arrowUp" as const) : ("arrowDown" as const),
            text: `${t.type} (${t.strike} CE)`,
          };
        });
        markers.sort((a, b) => (a.time as number) - (b.time as number));
        createSeriesMarkers(candleSeries, markers);
      }
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
  }, [v2BacktestResult]);

  return (
    <div className="flex flex-col h-full bg-slate-950/60 border border-white/5 rounded-lg overflow-hidden font-sans text-xs">
      
      {/* Run Parameter Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-900/50 border-b border-white/5 select-none shrink-0 flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <div className="flex flex-col gap-0.5">
            <span className="text-[8px] text-slate-500 font-bold uppercase">Active Strategy</span>
            <span className="text-cyan-400 font-bold font-mono">
              {v2Config.strategy_name || "No Strategy Selected"}
            </span>
          </div>

          <div className="h-6 w-px bg-white/5" />

          {/* Date Picker */}
          <div className="flex flex-col gap-0.5">
            <span className="text-[8px] text-slate-500 font-bold uppercase">Start Date</span>
            <input
              type="date"
              value={v2Config.start_date}
              onChange={(e) => setV2Config({ start_date: e.target.value })}
              className="bg-slate-900/80 border border-white/10 rounded px-1.5 py-0.5 text-[10px] text-slate-300 focus:outline-none font-mono"
            />
          </div>

          <div className="flex flex-col gap-0.5">
            <span className="text-[8px] text-slate-500 font-bold uppercase">End Date</span>
            <input
              type="date"
              value={v2Config.end_date}
              onChange={(e) => setV2Config({ end_date: e.target.value })}
              className="bg-slate-900/80 border border-white/10 rounded px-1.5 py-0.5 text-[10px] text-slate-300 focus:outline-none font-mono"
            />
          </div>
        </div>

        {/* Buttons */}
        <div className="flex items-center gap-2">
          {isBacktestLoading ? (
            <div className="flex items-center gap-2">
              <div className="w-20 bg-slate-800 h-1.5 rounded-full overflow-hidden">
                <div style={{ width: `${v2Status.progress}%` }} className="bg-cyan-400 h-full transition-all duration-300" />
              </div>
              <span className="text-[9px] font-mono text-cyan-400 font-bold">{v2Status.progress}%</span>
            </div>
          ) : (
            <button
              onClick={handleRunBacktest}
              disabled={!selectedStrategy}
              className="bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 font-bold px-3 py-1 rounded transition-all cursor-pointer text-center flex items-center gap-1.5 tracking-wider uppercase text-[10px]"
            >
              <Play className="w-3 h-3 fill-slate-950" />
              Run Backtest
            </button>
          )}
        </div>
      </div>

      {/* Candlestick simulator canvas */}
      <div className="flex-1 min-h-0 relative">
        {isBacktestLoading && (
          <div className="absolute inset-0 bg-slate-950/80 z-10 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-6 h-6 text-cyan-400 animate-spin" />
            <span className="text-[11px] text-slate-400 font-mono">Running V2 chronological replay simulation...</span>
          </div>
        )}
        <div ref={chartContainerRef} className="w-full h-full min-h-0" />
      </div>
    </div>
  );
};

// ==========================================
// 3. RIGHT PANEL: STRATEGY PARAMETERS & CONFIG
// ==========================================
export const BacktestRight: React.FC = () => {
  const selectedStrategy = useTerminalStore((state) => state.selectedStrategy);
  const v2Config = useBacktestStore((state) => state.v2Config);
  const setV2Config = useBacktestStore((state) => state.setV2Config);

  const handleParamChange = (key: string, val: any) => {
    setV2Config({
      strategy_params: {
        ...v2Config.strategy_params,
        [key]: val
      }
    });
  };

  return (
    <GlowingCard title="Backtest Parameters">
      <div className="flex flex-col gap-3.5 h-full font-sans text-xs">
        <div className="text-[10px] text-slate-500 border-b border-white/5 pb-1 select-none">
          GLOBAL CONFIGURATION
        </div>

        {/* Global Configurations */}
        <div className="grid grid-cols-2 gap-2 text-[10px]">
          <div className="flex flex-col gap-1">
            <span className="text-slate-500 font-semibold">Underlying Index</span>
            <select
              value={v2Config.underlying_instrument_key}
              onChange={(e) => setV2Config({ underlying_instrument_key: e.target.value })}
              className="bg-slate-900 border border-white/10 rounded px-1.5 py-1 text-slate-300 focus:outline-none"
            >
              <option value="NSE_INDEX|Nifty 50">NIFTY 50</option>
              <option value="NSE_INDEX|Nifty Bank">BANKNIFTY</option>
              <option value="NSE_INDEX|Nifty Fin Service">FINNIFTY</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-slate-500 font-semibold">Signal Source</span>
            <select
              value={v2Config.signal_source}
              onChange={(e) => setV2Config({ signal_source: e.target.value })}
              className="bg-slate-900 border border-white/10 rounded px-1.5 py-1 text-slate-300 focus:outline-none"
            >
              <option value="SPOT">Spot Price</option>
              <option value="FUTURES">Futures underlying</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-slate-500 font-semibold">Timeframe</span>
            <select
              value={v2Config.timeframe}
              onChange={(e) => setV2Config({ timeframe: e.target.value })}
              className="bg-slate-900 border border-white/10 rounded px-1.5 py-1 text-slate-300 focus:outline-none font-mono"
            >
              <option value="10s">10 seconds</option>
              <option value="30s">30 seconds</option>
              <option value="1m">1 minute</option>
              <option value="3m">3 minutes</option>
              <option value="5m">5 minutes</option>
              <option value="15m">15 minutes</option>
              <option value="30m">30 minutes</option>
              <option value="1h">1 hour</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-slate-500 font-semibold">Option Pref</span>
            <select
              value={v2Config.option_type_preference}
              onChange={(e) => setV2Config({ option_type_preference: e.target.value })}
              className="bg-slate-900 border border-white/10 rounded px-1.5 py-1 text-slate-300 focus:outline-none"
            >
              <option value="DYNAMIC">Dynamic CE/PE</option>
              <option value="CE_ONLY">Call Options Only</option>
              <option value="PE_ONLY">Put Options Only</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-slate-500 font-semibold">Strike Mode</span>
            <select
              value={v2Config.strike_mode}
              onChange={(e) => setV2Config({ strike_mode: e.target.value })}
              className="bg-slate-900 border border-white/10 rounded px-1.5 py-1 text-slate-300 focus:outline-none"
            >
              <option value="ATM">ATM (At-The-Money)</option>
              <option value="OTM_1">OTM +1 Strike</option>
              <option value="OTM_2">OTM +2 Strike</option>
              <option value="OTM_3">OTM +3 Strike</option>
              <option value="ITM_1">ITM -1 Strike</option>
              <option value="ITM_2">ITM -2 Strike</option>
              <option value="ITM_3">ITM -3 Strike</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-slate-500 font-semibold">Expiry Mode</span>
            <select
              value={v2Config.expiry_mode}
              onChange={(e) => setV2Config({ expiry_mode: e.target.value })}
              className="bg-slate-900 border border-white/10 rounded px-1.5 py-1 text-slate-300 focus:outline-none"
            >
              <option value="CURRENT_WEEKLY">Current Weekly</option>
              <option value="NEXT_WEEKLY">Next Weekly</option>
              <option value="CURRENT_MONTHLY">Current Monthly</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-slate-500 font-semibold">Initial Capital (₹)</span>
            <input
              type="number"
              value={v2Config.initial_capital}
              onChange={(e) => setV2Config({ initial_capital: Number(e.target.value) })}
              className="bg-slate-900 border border-white/10 rounded px-1.5 py-1 text-slate-300 focus:outline-none font-mono"
            />
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-slate-500 font-semibold">Lot Multiplier</span>
            <input
              type="number"
              value={v2Config.lot_multiplier}
              onChange={(e) => setV2Config({ lot_multiplier: Number(e.target.value) })}
              className="bg-slate-900 border border-white/10 rounded px-1.5 py-1 text-slate-300 focus:outline-none font-mono"
            />
          </div>
        </div>

        <div className="text-[10px] text-slate-500 border-b border-white/5 pb-1 mt-2 select-none">
          STRATEGY PARAMETERS
        </div>

        {/* Strategy Specific Controls */}
        {selectedStrategy ? (
          <div className="flex flex-col gap-3 flex-1 overflow-y-auto">
            {v2Config.strategy_name === "EMA" && (
              <>
                <div className="flex flex-col gap-1">
                  <div className="flex justify-between items-center text-[10px] text-slate-400">
                    <span className="font-semibold">Fast EMA Period</span>
                    <span className="font-mono text-cyan-400 font-bold bg-slate-900/60 px-1.5 py-0.5 rounded border border-white/5">
                      {v2Config.strategy_params.fastEma || 2}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="2"
                    max="50"
                    value={v2Config.strategy_params.fastEma || 2}
                    onChange={(e) => handleParamChange("fastEma", Number(e.target.value))}
                    className="w-full accent-cyan-400 bg-slate-900 cursor-pointer h-1.5 rounded-lg"
                  />
                </div>

                <div className="flex flex-col gap-1">
                  <div className="flex justify-between items-center text-[10px] text-slate-400">
                    <span className="font-semibold">Slow EMA Period</span>
                    <span className="font-mono text-cyan-400 font-bold bg-slate-900/60 px-1.5 py-0.5 rounded border border-white/5">
                      {v2Config.strategy_params.slowEma || 3}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="3"
                    max="100"
                    value={v2Config.strategy_params.slowEma || 3}
                    onChange={(e) => handleParamChange("slowEma", Number(e.target.value))}
                    className="w-full accent-cyan-400 bg-slate-900 cursor-pointer h-1.5 rounded-lg"
                  />
                </div>
              </>
            )}

            {v2Config.strategy_name === "five_ema_scalping" && (
              <>
                <div className="flex flex-col gap-1">
                  <div className="flex justify-between items-center text-[10px] text-slate-400">
                    <span className="font-semibold">EMA Period</span>
                    <span className="font-mono text-cyan-400 font-bold bg-slate-900/60 px-1.5 py-0.5 rounded border border-white/5">
                      {v2Config.strategy_params.five_ema_period || 5}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="3"
                    max="20"
                    value={v2Config.strategy_params.five_ema_period || 5}
                    onChange={(e) => handleParamChange("five_ema_period", Number(e.target.value))}
                    className="w-full accent-cyan-400 bg-slate-900 cursor-pointer h-1.5 rounded-lg"
                  />
                </div>

                <div className="flex flex-col gap-1">
                  <div className="flex justify-between items-center text-[10px] text-slate-400">
                    <span className="font-semibold">Risk-Reward Ratio</span>
                    <span className="font-mono text-cyan-400 font-bold bg-slate-900/60 px-1.5 py-0.5 rounded border border-white/5">
                      {v2Config.strategy_params.five_ema_rr || 3.0}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1.5"
                    max="10"
                    step="0.5"
                    value={v2Config.strategy_params.five_ema_rr || 3.0}
                    onChange={(e) => handleParamChange("five_ema_rr", Number(e.target.value))}
                    className="w-full accent-cyan-400 bg-slate-900 cursor-pointer h-1.5 rounded-lg"
                  />
                </div>
              </>
            )}

            {/* Commissions & Slippage inputs */}
            <div className="grid grid-cols-2 gap-2 text-[10px] mt-2 pt-2.5 border-t border-white/5">
              <div className="flex flex-col gap-1">
                <span className="text-slate-500 font-semibold">Brokerage Flat (₹)</span>
                <input
                  type="number"
                  value={v2Config.brokerage_flat}
                  onChange={(e) => setV2Config({ brokerage_flat: Number(e.target.value) })}
                  className="bg-slate-900 border border-white/10 rounded px-1.5 py-0.5 text-slate-300 focus:outline-none font-mono"
                />
              </div>

              <div className="flex flex-col gap-1">
                <span className="text-slate-500 font-semibold">Slippage (%)</span>
                <input
                  type="number"
                  step="0.01"
                  value={v2Config.slippage_pct}
                  onChange={(e) => setV2Config({ slippage_pct: Number(e.target.value) })}
                  className="bg-slate-900 border border-white/10 rounded px-1.5 py-0.5 text-slate-300 focus:outline-none font-mono"
                />
              </div>
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
  const [activeTab, setActiveTab] = useState<"overview" | "trades" | "equity" | "drawdown" | "metrics" | "optimization">("overview");
  const equityContainerRef = useRef<HTMLDivElement>(null);
  const drawdownContainerRef = useRef<HTMLDivElement>(null);

  // V2 Store selectors
  const v2Result = useBacktestStore((state) => state.v2BacktestResult);
  const v2OptimizationReport = useBacktestStore((state) => state.v2OptimizationReport);
  const runV2Optimization = useBacktestStore((state) => state.runV2Optimization);
  const isOptimizationLoading = useBacktestStore((state) => state.isOptimizationLoading);
  const runV2Backtest = useBacktestStore((state) => state.runV2Backtest);
  const v2Config = useBacktestStore((state) => state.v2Config);
  const selectedInspectorParams = useBacktestStore((state) => state.selectedInspectorParams);
  const setSelectedInspectorParams = useBacktestStore((state) => state.setSelectedInspectorParams);

  // Optimization Parameter Ranges (Local Form State)
  const [fastEmaStart, setFastEmaStart] = useState(2);
  const [fastEmaEnd, setFastEmaEnd] = useState(5);
  const [fastEmaStep, setFastEmaStep] = useState(1);

  const [slowEmaStart, setSlowEmaStart] = useState(3);
  const [slowEmaEnd, setSlowEmaEnd] = useState(8);
  const [slowEmaStep, setSlowEmaStep] = useState(1);

  const [workerCount, setWorkerCount] = useState(4);
  const [heatmapMetric, setHeatmapMetric] = useState<"net_profit" | "sharpe_ratio" | "profit_factor" | "composite_score">("net_profit");
  const [optTab, setOptTab] = useState<"setup" | "ranked" | "heatmap">("setup");
  const [rankedFilter, setRankedFilter] = useState<"top10" | "top25" | "top50">("top10");

  const report = v2Result?.report;
  const netProfit = report?.performance?.net_profit || 0;
  const returnPct = report?.net_return_pct || 0;
  const winRate = report?.trade_stats?.win_rate || 0;
  const sharpe = report?.sharpe_ratio || 0;
  const maxDrawdown = report?.max_drawdown_pct || 0;
  const profitFactor = report?.performance?.profit_factor || 0;
  const totalTrades = report?.trade_stats?.total_trades || 0;

  // Run optimization sweep
  const handleRunOptimization = async () => {
    const ranges = [
      { name: "fastEma", type: "int", min_val: fastEmaStart, max_val: fastEmaEnd, step: fastEmaStep },
      { name: "slowEma", type: "int", min_val: slowEmaStart, max_val: slowEmaEnd, step: slowEmaStep }
    ];
    const ok = await runV2Optimization(ranges, workerCount);
    if (ok) {
      setOptTab("ranked");
    }
  };

  // Inspect specific parameters
  const handleInspectParams = async (comboParams: Record<string, any>) => {
    setSelectedInspectorParams(comboParams);
    // Run V2 Backtest with overridden parameter set
    await runV2Backtest({
      strategy_params: {
        ...v2Config.strategy_params,
        ...comboParams
      }
    });
  };

  // Render Equity Curve Chart on Tab Load
  useEffect(() => {
    if (activeTab !== "equity" || !equityContainerRef.current || !report?.equity_curve || report.equity_curve.length === 0) return;
    
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

    const rawPoints = report.equity_curve.map((pt) => ({
      time: Math.floor(new Date(pt.timestamp).getTime() / 1000) as UTCTimestamp,
      value: pt.equity_value,
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
  }, [activeTab, report?.equity_curve]);

  // Render Drawdown Chart on Tab Load
  useEffect(() => {
    if (activeTab !== "drawdown" || !drawdownContainerRef.current || !report?.drawdown_curve || report.drawdown_curve.length === 0) return;
    
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

    const rawPoints = report.drawdown_curve.map((pt) => ({
      time: Math.floor(new Date(pt.timestamp).getTime() / 1000) as UTCTimestamp,
      value: -Math.abs(pt.drawdown_pct),
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
  }, [activeTab, report?.drawdown_curve]);

  const tabs = [
    { id: "overview" as const, name: "Overview" },
    { id: "trades" as const, name: "Trade Ledger" },
    { id: "equity" as const, name: "Equity Curve" },
    { id: "drawdown" as const, name: "Drawdown" },
    { id: "metrics" as const, name: "Performance Metrics" },
    { id: "optimization" as const, name: "Sweep & Optimization" },
  ];

  // Helper to extract parameters list from top ranking
  const getRankedList = () => {
    if (!v2OptimizationReport) return [];
    if (rankedFilter === "top25") return v2OptimizationReport.top_25;
    if (rankedFilter === "top50") return v2OptimizationReport.top_50;
    return v2OptimizationReport.top_10;
  };

  return (
    <div className="flex flex-col h-full overflow-hidden text-xs font-sans">
      
      {/* Tabs selectors */}
      <div className="flex items-center justify-between border-b border-white/5 bg-slate-950/20 px-2 shrink-0 select-none">
        <div className="flex items-center gap-1">
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

        {selectedInspectorParams && (
          <div className="flex items-center gap-2 bg-cyan-950/40 border border-cyan-500/20 px-2 py-0.5 rounded text-[10px] font-mono text-cyan-300">
            <Sliders className="w-3 h-3 text-cyan-400" />
            <span>INSPECTING: {JSON.stringify(selectedInspectorParams)}</span>
            <button
              onClick={() => {
                setSelectedInspectorParams(null);
                runV2Backtest(); // Reload original backtest
              }}
              className="text-[9px] text-slate-500 hover:text-slate-300 font-bold ml-1 border-l border-white/10 pl-1 cursor-pointer"
            >
              Clear
            </button>
          </div>
        )}
      </div>

      {/* Tabs Container */}
      <div className="flex-1 overflow-y-auto p-3 scrollbar-thin scrollbar-thumb-white/5 scrollbar-track-transparent min-h-0">
        
        {!v2Result && activeTab !== "optimization" ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-500 py-6 select-none">
            <Activity className="w-8 h-8 text-slate-600 mb-2 animate-pulse" />
            <span>No V2 Backtest results loaded. Click "Run Backtest" to begin.</span>
          </div>
        ) : (
          <>
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
                  <span className="text-[8px] text-slate-500 uppercase block">Capital Return</span>
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

                <div className="bg-slate-900/20 border border-white/5 p-2 rounded">
                  <span className="text-[8px] text-slate-500 uppercase block">Profit Factor</span>
                  <span className="text-slate-200 font-bold text-sm">{profitFactor.toFixed(2)}</span>
                </div>
                <div className="bg-slate-900/20 border border-white/5 p-2 rounded">
                  <span className="text-[8px] text-slate-500 uppercase block">Total Trades</span>
                  <span className="text-slate-200 font-bold text-sm">{totalTrades}</span>
                </div>
                <div className="bg-slate-900/20 border border-white/5 p-2 rounded">
                  <span className="text-[8px] text-slate-500 uppercase block">Max Drawdown</span>
                  <span className="text-rose-400 font-bold text-sm">-{maxDrawdown.toFixed(2)}%</span>
                </div>
                <div className="bg-slate-900/20 border border-white/5 p-2 rounded">
                  <span className="text-[8px] text-slate-500 uppercase block">Score Rating</span>
                  <span className="text-cyan-400 font-bold text-sm">{report?.grade || "N/A"}</span>
                </div>
              </div>
            )}

            {/* Trade List Tab */}
            {activeTab === "trades" && (
              <table className="w-full text-left font-mono text-[10px]">
                <thead>
                  <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-[8px] tracking-wider">
                    <th className="py-1 pl-2">Contract Details</th>
                    <th className="py-1">Entry Time</th>
                    <th className="py-1">Exit Time</th>
                    <th className="py-1 text-right">Entry Premium</th>
                    <th className="py-1 text-right">Exit Premium</th>
                    <th className="py-1 text-center">Qty</th>
                    <th className="py-1 text-right">Gross PnL</th>
                    <th className="py-1 text-right">Charges</th>
                    <th className="py-1 text-right pr-2">Net PnL</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  {v2Result?.trades.map((t) => (
                    <tr key={t.position_id} className="border-b border-white/[0.02] hover:bg-white/[0.01]">
                      <td className="py-1.5 pl-2 text-cyan-400">{t.contract}</td>
                      <td className="py-1.5">{new Date(t.entry_time).toLocaleString("en-IN")}</td>
                      <td className="py-1.5">{new Date(t.exit_time).toLocaleString("en-IN")}</td>
                      <td className="py-1.5 text-right">₹{t.entry_premium.toFixed(2)}</td>
                      <td className="py-1.5 text-right">₹{t.exit_premium.toFixed(2)}</td>
                      <td className="py-1.5 text-center">{t.quantity}</td>
                      <td className={`py-1.5 text-right font-bold ${t.gross_pnl > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        ₹{t.gross_pnl.toFixed(2)}
                      </td>
                      <td className="py-1.5 text-right text-slate-500">₹{t.charges.total_charges.toFixed(2)}</td>
                      <td className={`py-1.5 text-right font-bold ${t.net_pnl > 0 ? "text-emerald-400" : "text-rose-400"} pr-2`}>
                        ₹{t.net_pnl.toFixed(2)}
                      </td>
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
            {activeTab === "metrics" && report && (
              <div className="grid grid-cols-2 gap-4 max-w-3xl font-mono text-[10px] select-none">
                <div className="flex flex-col gap-1.5">
                  <div className="flex justify-between border-b border-white/5 py-1">
                    <span className="text-slate-500">NET PROFIT:</span>
                    <span className="text-emerald-400 font-bold">₹{report.performance.net_profit.toLocaleString("en-IN")}</span>
                  </div>
                  <div className="flex justify-between border-b border-white/5 py-1">
                    <span className="text-slate-500">GROSS PROFIT:</span>
                    <span className="text-slate-300 font-bold">₹{report.performance.gross_profit.toLocaleString("en-IN")}</span>
                  </div>
                  <div className="flex justify-between border-b border-white/5 py-1">
                    <span className="text-slate-500">GROSS LOSS:</span>
                    <span className="text-rose-400 font-bold">₹{report.performance.gross_loss.toLocaleString("en-IN")}</span>
                  </div>
                  <div className="flex justify-between border-b border-white/5 py-1">
                    <span className="text-slate-500">PROFIT FACTOR:</span>
                    <span className="text-slate-300 font-bold">{report.performance.profit_factor.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between border-b border-white/5 py-1">
                    <span className="text-slate-500">EXPECTANCY:</span>
                    <span className="text-slate-300 font-bold">₹{report.performance.expectancy.toFixed(2)}</span>
                  </div>
                </div>
                <div className="flex flex-col gap-1.5">
                  <div className="flex justify-between border-b border-white/5 py-1">
                    <span className="text-slate-500">SHARPE RATIO:</span>
                    <span className="text-cyan-400 font-bold">{report.sharpe_ratio.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between border-b border-white/5 py-1">
                    <span className="text-slate-500">SORTINO RATIO:</span>
                    <span className="text-cyan-400 font-bold">{report.sortino_ratio.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between border-b border-white/5 py-1">
                    <span className="text-slate-500">MAX DRAWDOWN:</span>
                    <span className="text-rose-400 font-bold">-{report.max_drawdown_pct.toFixed(2)}%</span>
                  </div>
                  <div className="flex justify-between border-b border-white/5 py-1">
                    <span className="text-slate-500">WIN RATE / LOSS RATE:</span>
                    <span className="text-slate-300 font-bold">{report.trade_stats.win_rate.toFixed(1)}% / {report.trade_stats.loss_rate.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between border-b border-white/5 py-1">
                    <span className="text-slate-500">STREAK WINS / LOSSES:</span>
                    <span className="text-slate-300 font-bold">{report.performance.max_consecutive_wins} wins / {report.performance.max_consecutive_losses} losses</span>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* Optimization Tab */}
        {activeTab === "optimization" && (
          <div className="flex flex-col h-full min-h-0 text-[10px] font-sans">
            {/* Tab navigation inside Optimization */}
            <div className="flex gap-2 mb-3 border-b border-white/5 pb-1 select-none shrink-0">
              <button
                onClick={() => setOptTab("setup")}
                className={`px-3 py-1 font-bold rounded cursor-pointer ${
                  optTab === "setup" ? "bg-slate-800 text-cyan-400" : "text-slate-500 hover:text-slate-300"
                }`}
              >
                Configuration
              </button>
              <button
                onClick={() => setOptTab("ranked")}
                disabled={!v2OptimizationReport}
                className={`px-3 py-1 font-bold rounded cursor-pointer disabled:opacity-30 ${
                  optTab === "ranked" ? "bg-slate-800 text-cyan-400" : "text-slate-500 hover:text-slate-300"
                }`}
              >
                Ranked Combinations
              </button>
              <button
                onClick={() => setOptTab("heatmap")}
                disabled={!v2OptimizationReport}
                className={`px-3 py-1 font-bold rounded cursor-pointer disabled:opacity-30 ${
                  optTab === "heatmap" ? "bg-slate-800 text-cyan-400" : "text-slate-500 hover:text-slate-300"
                }`}
              >
                Heatmap Analytics
              </button>
            </div>

            {/* Sweep setup panel */}
            {optTab === "setup" && (
              <div className="grid grid-cols-2 gap-4 max-w-2xl select-none">
                <div className="flex flex-col gap-3.5 bg-slate-900/10 border border-white/5 p-3.5 rounded">
                  <span className="text-cyan-400 font-bold uppercase tracking-wider block border-b border-white/5 pb-1 mb-1">
                    Fast EMA Sweep Range
                  </span>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="flex flex-col gap-1">
                      <span className="text-slate-500">Min</span>
                      <input
                        type="number"
                        value={fastEmaStart}
                        onChange={(e) => setFastEmaStart(Number(e.target.value))}
                        className="bg-slate-900 border border-white/10 rounded px-1.5 py-1 text-slate-300 focus:outline-none font-mono text-[11px]"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <span className="text-slate-500">Max</span>
                      <input
                        type="number"
                        value={fastEmaEnd}
                        onChange={(e) => setFastEmaEnd(Number(e.target.value))}
                        className="bg-slate-900 border border-white/10 rounded px-1.5 py-1 text-slate-300 focus:outline-none font-mono text-[11px]"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <span className="text-slate-500">Step</span>
                      <input
                        type="number"
                        value={fastEmaStep}
                        onChange={(e) => setFastEmaStep(Number(e.target.value))}
                        className="bg-slate-900 border border-white/10 rounded px-1.5 py-1 text-slate-300 focus:outline-none font-mono text-[11px]"
                      />
                    </div>
                  </div>
                </div>

                <div className="flex flex-col gap-3.5 bg-slate-900/10 border border-white/5 p-3.5 rounded">
                  <span className="text-cyan-400 font-bold uppercase tracking-wider block border-b border-white/5 pb-1 mb-1">
                    Slow EMA Sweep Range
                  </span>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="flex flex-col gap-1">
                      <span className="text-slate-500">Min</span>
                      <input
                        type="number"
                        value={slowEmaStart}
                        onChange={(e) => setSlowEmaStart(Number(e.target.value))}
                        className="bg-slate-900 border border-white/10 rounded px-1.5 py-1 text-slate-300 focus:outline-none font-mono text-[11px]"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <span className="text-slate-500">Max</span>
                      <input
                        type="number"
                        value={slowEmaEnd}
                        onChange={(e) => setSlowEmaEnd(Number(e.target.value))}
                        className="bg-slate-900 border border-white/10 rounded px-1.5 py-1 text-slate-300 focus:outline-none font-mono text-[11px]"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <span className="text-slate-500">Step</span>
                      <input
                        type="number"
                        value={slowEmaStep}
                        onChange={(e) => setSlowEmaStep(Number(e.target.value))}
                        className="bg-slate-900 border border-white/10 rounded px-1.5 py-1 text-slate-300 focus:outline-none font-mono text-[11px]"
                      />
                    </div>
                  </div>
                </div>

                <div className="flex justify-between items-center bg-slate-900/10 border border-white/5 p-3.5 rounded col-span-2 mt-2">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-500 font-bold">Parallel Threads:</span>
                    <input
                      type="number"
                      value={workerCount}
                      onChange={(e) => setWorkerCount(Number(e.target.value))}
                      className="bg-slate-900 border border-white/10 rounded w-14 px-1.5 py-0.5 text-slate-300 focus:outline-none font-mono"
                    />
                  </div>

                  <button
                    onClick={handleRunOptimization}
                    disabled={isOptimizationLoading}
                    className="bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-1.5 rounded transition-all cursor-pointer tracking-wider uppercase text-[10px]"
                  >
                    {isOptimizationLoading ? "Running Sweep..." : "Run Parameter Sweep"}
                  </button>
                </div>
              </div>
            )}

            {/* Ranked combinations */}
            {optTab === "ranked" && v2OptimizationReport && (
              <div className="flex flex-col gap-3">
                <div className="flex justify-between items-center select-none">
                  <div className="flex gap-2">
                    {(["top10", "top25", "top50"] as const).map((f) => (
                      <button
                        key={f}
                        onClick={() => setRankedFilter(f)}
                        className={`px-2 py-0.5 rounded border text-[9px] font-mono cursor-pointer ${
                          rankedFilter === f
                            ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400"
                            : "bg-slate-900 border-white/5 text-slate-500"
                        }`}
                      >
                        {f.toUpperCase()}
                      </button>
                    ))}
                  </div>
                  <span className="text-slate-500 text-[9px] font-mono">
                    Executed: {v2OptimizationReport.run_info.executed_combinations} runs | Skipped: {v2OptimizationReport.run_info.skipped_combinations}
                  </span>
                </div>

                <table className="w-full text-left font-mono text-[10px]">
                  <thead>
                    <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-[8px] tracking-wider">
                      <th className="py-1 pl-2">Rank</th>
                      <th className="py-1">Parameters (Fast / Slow)</th>
                      <th className="py-1 text-right">Net Profit</th>
                      <th className="py-1 text-right">Profit Factor</th>
                      <th className="py-1 text-right">Expectancy</th>
                      <th className="py-1 text-right">Sharpe</th>
                      <th className="py-1 text-right">Sortino</th>
                      <th className="py-1 text-right">Max Drawdown</th>
                      <th className="py-1 text-right">Score</th>
                      <th className="py-1 text-center pr-2">Sensitivity</th>
                    </tr>
                  </thead>
                  <tbody className="text-slate-300">
                    {getRankedList().map((item, index) => {
                      const paramsKey = JSON.stringify(item.combination.params);
                      const isInspected = JSON.stringify(selectedInspectorParams) === paramsKey;
                      const stability = v2OptimizationReport.stability_findings[paramsKey];

                      return (
                        <tr
                          key={index}
                          onClick={() => handleInspectParams(item.combination.params)}
                          className={`border-b border-white/[0.02] hover:bg-white/[0.01] cursor-pointer ${
                            isInspected ? "bg-cyan-500/10 border-cyan-500/20" : ""
                          }`}
                        >
                          <td className="py-1.5 pl-2 text-slate-500">#{index + 1}</td>
                          <td className="py-1.5 text-cyan-400 font-bold">
                            Fast: {item.combination.params.fastEma || item.combination.params.fast_period} | Slow: {item.combination.params.slowEma || item.combination.params.slow_period}
                          </td>
                          <td className={`py-1.5 text-right font-bold ${item.net_profit > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                            ₹{item.net_profit.toLocaleString("en-IN")}
                          </td>
                          <td className="py-1.5 text-right">{item.profit_factor.toFixed(2)}</td>
                          <td className="py-1.5 text-right">₹{item.expectancy.toFixed(2)}</td>
                          <td className="py-1.5 text-right text-cyan-400">{item.sharpe_ratio.toFixed(2)}</td>
                          <td className="py-1.5 text-right">{item.sortino_ratio.toFixed(2)}</td>
                          <td className="py-1.5 text-right text-rose-400">-{item.max_drawdown_pct.toFixed(2)}%</td>
                          <td className="py-1.5 text-right text-cyan-300 font-bold">{item.composite_score}</td>
                          <td className="py-1.5 text-center pr-2">
                            {stability ? (
                              <span className={`px-1 rounded text-[8px] font-sans font-bold ${
                                stability.status === "STABLE" ? "bg-emerald-950/40 text-emerald-400" : "bg-rose-950/40 text-rose-400"
                              }`}>
                                {stability.status}
                              </span>
                            ) : (
                              <span className="text-slate-600">-</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Heatmap visualization */}
            {optTab === "heatmap" && v2OptimizationReport && (
              <div className="flex flex-col gap-3 text-slate-400">
                <div className="flex justify-between items-center select-none shrink-0">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-500">Heatmap Parameter Metric:</span>
                    <select
                      value={heatmapMetric}
                      onChange={(e: any) => setHeatmapMetric(e.target.value)}
                      className="bg-slate-900 border border-white/10 rounded px-1.5 py-0.5 text-slate-300 focus:outline-none"
                    >
                      <option value="net_profit">Net Profit</option>
                      <option value="sharpe_ratio">Sharpe Ratio</option>
                      <option value="profit_factor">Profit Factor</option>
                      <option value="composite_score">Composite Score</option>
                    </select>
                  </div>
                </div>

                <div className="flex gap-4">
                  {/* Heatmap Grid */}
                  <div className="bg-slate-950/40 border border-white/5 p-3 rounded flex-1 overflow-x-auto">
                    <div className="flex flex-col gap-1.5 min-w-[300px]">
                      {/* X values label header */}
                      <div className="flex">
                        <div className="w-16 font-mono text-[8px] text-slate-500 flex items-center justify-end pr-2 uppercase">
                          Slow \ Fast
                        </div>
                        <div className="flex-1 flex gap-1">
                          {v2OptimizationReport.heatmap_data.x_values.map((xVal) => (
                            <div key={xVal} className="flex-1 text-center font-mono font-bold text-[8px] text-cyan-500/80">
                              F:{xVal}
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Matrix Rows */}
                      {v2OptimizationReport.heatmap_data.y_values.map((yVal, yIdx) => (
                        <div key={yVal} className="flex">
                          {/* Y Label */}
                          <div className="w-16 font-mono font-bold text-[8px] text-slate-500 flex items-center justify-end pr-2">
                            S:{yVal}
                          </div>
                          
                          {/* Cell row */}
                          <div className="flex-1 flex gap-1">
                            {v2OptimizationReport.heatmap_data.x_values.map((xVal, xIdx) => {
                              // Find matching run inside report
                              const runItem = [...v2OptimizationReport.top_50, ...v2OptimizationReport.top_25, ...v2OptimizationReport.top_10].find(r => 
                                (r.combination.params.fastEma === xVal || r.combination.params.fast_period === xVal) &&
                                (r.combination.params.slowEma === yVal || r.combination.params.slow_period === yVal)
                              );

                              let cellVal = 0;
                              if (runItem) {
                                cellVal = runItem[heatmapMetric] || 0;
                              }

                              // Coloring intensity
                              let cellBg = "bg-slate-900/40";
                              if (cellVal > 0) {
                                const maxVal = Math.max(1, ...v2OptimizationReport.top_10.map(r => r[heatmapMetric] || 1));
                                const pct = Math.min(1, cellVal / maxVal);
                                if (pct > 0.75) cellBg = "bg-cyan-500 text-slate-950 font-bold border-cyan-400";
                                else if (pct > 0.5) cellBg = "bg-cyan-600/80 text-white font-semibold border-cyan-500/30";
                                else if (pct > 0.25) cellBg = "bg-cyan-800/50 text-cyan-300 border-cyan-800/20";
                                else cellBg = "bg-cyan-950/30 text-cyan-400/70 border-white/5";
                              } else if (cellVal < 0) {
                                cellBg = "bg-rose-950/20 text-rose-400/80 border-rose-950/30";
                              }

                              return (
                                <div
                                  key={xVal}
                                  onClick={() => handleInspectParams({ fastEma: xVal, slowEma: yVal })}
                                  title={`Fast: ${xVal}, Slow: ${yVal} | ${heatmapMetric}: ${cellVal}`}
                                  className={`flex-1 aspect-[1.8] rounded border flex items-center justify-center font-mono text-[9px] cursor-pointer transition-all hover:scale-105 select-none ${cellBg}`}
                                >
                                  {cellVal ? (heatmapMetric.includes("profit") ? `₹${Math.round(cellVal)}` : cellVal.toFixed(1)) : "-"}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Inspector card right side */}
                  <div className="w-56 flex flex-col gap-2.5">
                    <div className="bg-slate-900/10 border border-white/5 p-3 rounded">
                      <span className="text-slate-500 uppercase tracking-widest text-[8px] font-bold block mb-1">
                        Cell Parameter Inspector
                      </span>
                      {selectedInspectorParams ? (
                        <div className="flex flex-col gap-2">
                          <div className="font-mono text-cyan-400 font-bold border-b border-white/5 pb-1 select-text">
                            Fast: {selectedInspectorParams.fastEma} | Slow: {selectedInspectorParams.slowEma}
                          </div>
                          {report && (
                            <div className="flex flex-col gap-1 select-none">
                              <div className="flex justify-between">
                                <span className="text-slate-500">Net Profit:</span>
                                <span className="text-emerald-400 font-bold font-mono">₹{report.performance.net_profit.toLocaleString("en-IN")}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-slate-500">Sharpe Ratio:</span>
                                <span className="text-cyan-400 font-bold font-mono">{report.sharpe_ratio.toFixed(2)}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-slate-500">Win Rate:</span>
                                <span className="text-slate-300 font-mono">{report.trade_stats.win_rate.toFixed(1)}%</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-slate-500">Drawdown:</span>
                                <span className="text-rose-400 font-mono">-{report.max_drawdown_pct.toFixed(2)}%</span>
                              </div>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="text-[10px] text-slate-500 italic select-none">
                          Click any heatmap cell to run detailed backtest and inspect results.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
};
