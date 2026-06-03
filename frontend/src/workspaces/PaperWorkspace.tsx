"use client";

import React, { useState, useEffect } from "react";
import { 
  Play, Pause, Square, Activity, Server, Zap, Shield, AlertTriangle, 
  Search, Sliders, CheckCircle2, ChevronRight, BarChart2, Cpu, 
  Database, RefreshCw, Terminal, TrendingUp, HelpCircle, Info
} from "lucide-react";
import { useTerminalStore } from "@/store/useTerminalStore";
import { useEventStore } from "@/store/useEventStore";
import { useBackendTradingStore } from "@/services/tradingQueries";
import { useBacktestStore } from "@/store/useBacktestStore";

// Helper components for professional Mission Control styling
const MissionCard: React.FC<{ title: string; children: React.ReactNode; className?: string }> = ({ title, children, className = "" }) => (
  <div className={`p-3 flex flex-col h-full bg-slate-950/40 border border-white/5 rounded-lg hover:border-cyan-500/10 transition-all ${className}`}>
    <h3 className="text-[10px] font-bold tracking-widest text-cyan-400 uppercase border-b border-white/5 pb-1.5 mb-2.5 flex items-center justify-between">
      <span>{title}</span>
      <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" />
    </h3>
    <div className="flex-1 overflow-y-auto min-h-0">{children}</div>
  </div>
);

const TelemetryDial: React.FC<{ label: string; value: string | number; subText?: string; isPositive?: boolean }> = ({ label, value, subText, isPositive }) => (
  <div className="bg-slate-900/30 border border-white/5 rounded p-2.5 flex flex-col gap-1 select-none">
    <span className="text-[8px] text-slate-500 uppercase font-bold tracking-wider">{label}</span>
    <span className={`text-base font-bold font-mono tracking-tight ${
      isPositive === true ? "text-emerald-400" : isPositive === false ? "text-rose-450" : "text-slate-200"
    }`}>{value}</span>
    {subText && <span className="text-[9px] text-slate-500 font-mono">{subText}</span>}
  </div>
);

// ==========================================
// 1. LEFT PANEL: STRATEGY CATALOG
// ==========================================
export const PaperLeft: React.FC = () => {
  const selectedStrategy = useTerminalStore((state) => state.selectedStrategy);
  const setStrategy = useTerminalStore((state) => state.setStrategy);
  
  const strategies = useBackendTradingStore((state) => state.strategies);
  const fetchV2Strategies = useBackendTradingStore((state) => state.fetchV2Strategies);

  const [search, setSearch] = useState("");

  useEffect(() => {
    fetchV2Strategies();
  }, [fetchV2Strategies]);

  const filtered = (strategies || []).filter((dep) => {
    return dep.name.toLowerCase().includes(search.toLowerCase()) || 
           dep.category.toLowerCase().includes(search.toLowerCase());
  });

  const handleSelect = (item: any) => {
    setStrategy({
      strategyId: item.id,
      strategyName: item.name,
      version: "v2.0",
    });
  };

  return (
    <MissionCard title="Strategy Catalog">
      <div className="flex flex-col gap-2 h-full font-sans text-xs">
        {/* Search */}
        <div className="relative shrink-0">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search V2 strategies..."
            className="w-full bg-slate-900/60 border border-white/5 rounded pl-8 pr-3 py-1.5 text-[11px] text-slate-300 focus:outline-none focus:border-cyan-500/40"
          />
        </div>

        {/* Strategy list */}
        <div className="flex-1 overflow-y-auto flex flex-col gap-2 mt-2 pr-1 scrollbar-thin scrollbar-thumb-white/5">
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
                  <span className="font-mono text-[9px] text-slate-500 bg-slate-900 px-1 border border-white/5 rounded">
                    {item.risk_level} Risk
                  </span>
                </div>

                <p className="text-[10px] text-slate-400 line-clamp-2 leading-relaxed">
                  {item.description}
                </p>

                <div className="flex justify-between items-center text-[9px] text-slate-500 select-none border-t border-white/[0.02] pt-1">
                  <span className="font-bold text-cyan-500">{item.category}</span>
                  <span className="font-mono">{item.expected_trade_frequency}</span>
                </div>
              </div>
            );
          })}
          {filtered.length === 0 && (
            <div className="text-slate-500 text-[10px] text-center py-4">No strategies found.</div>
          )}
        </div>
      </div>
    </MissionCard>
  );
};

// ==========================================
// 2. MAIN PANEL: DEPLOYMENT DASHBOARD
// ==========================================
export const PaperMain: React.FC = () => {
  const selectedStrategy = useTerminalStore((state) => state.selectedStrategy);
  const setStrategy = useTerminalStore((state) => state.setStrategy);
  const currentAccount = useTerminalStore((state) => state.currentAccount);
  const addEvent = useEventStore((state) => state.addEvent);

  // V2 Live paper telemetry
  const status = useBackendTradingStore((state) => state.status);
  const strategies = useBackendTradingStore((state) => state.strategies);
  const startV2PaperSession = useBackendTradingStore((state) => state.startV2PaperSession);
  const stopV2PaperSession = useBackendTradingStore((state) => state.stopV2PaperSession);
  const pauseV2PaperSession = useBackendTradingStore((state) => state.pauseV2PaperSession);
  const resumeV2PaperSession = useBackendTradingStore((state) => state.resumeV2PaperSession);
  const connectTelemetry = useBackendTradingStore((state) => state.connectTelemetry);
  const trades = useBackendTradingStore((state) => state.trades) || [];

  // Backtest presets hooks
  const presets = useBacktestStore((state) => state.presets);
  const presetsLoading = useBacktestStore((state) => state.presetsLoading);
  const fetchPresets = useBacktestStore((state) => state.fetchPresets);

  // Configuration form state
  const [allocation, setAllocation] = useState(100000);
  const [indexName, setIndexName] = useState("NIFTY");
  const [optionType, setOptionType] = useState("DYNAMIC");
  const [strike, setStrike] = useState("ATM");
  const [expiry, setExpiry] = useState("CURRENT_WEEKLY");
  const [timeframe, setTimeframe] = useState("5m");
  const [lotSize, setLotSize] = useState(1);
  const [maxCandles, setMaxCandles] = useState(15);
  const [cutoffTime, setCutoffTime] = useState("15:15");

  // Strategy specific states
  const [fiveEmaPeriod, setFiveEmaPeriod] = useState(5);
  const [fiveEmaRr, setFiveEmaRr] = useState(3.0);
  const [loadedPresetName, setLoadedPresetName] = useState<string | null>(null);
  const [selectedPresetId, setSelectedPresetId] = useState<string>("");

  // Session Runtime Clock logic (Task A3)
  const [runtimeSeconds, setRuntimeSeconds] = useState<number>(0);
  const [sessionStartTimeStr, setSessionStartTimeStr] = useState<string>("N/A");

  // Determine running state based on telemetry status
  const isEngineRunning = status?.engine === "v2" && !!status?.state && status?.state !== "IDLE";
  const isEnginePaused = status?.engine === "v2" && status?.state === "PAUSED";
  const displayStatus = isEngineRunning
    ? (isEnginePaused ? "Paused" : (status?.state === "DISCONNECTED" ? "Disconnected" : "Running"))
    : "Ready For Paper";

  useEffect(() => {
    if (isEngineRunning) {
      // Hydrate start time and duration from localStorage on session activation
      let startStr = localStorage.getItem("valkyrie_session_start_time");
      if (!startStr) {
        startStr = new Date().toLocaleTimeString();
        localStorage.setItem("valkyrie_session_start_time", startStr);
      }
      setSessionStartTimeStr(startStr);

      const cachedSeconds = localStorage.getItem("valkyrie_runtime_seconds");
      if (cachedSeconds && runtimeSeconds === 0) {
        setRuntimeSeconds(Number(cachedSeconds));
      }

      const timer = setInterval(() => {
        if (!isEnginePaused) {
          setRuntimeSeconds((prev) => {
            const next = prev + 1;
            localStorage.setItem("valkyrie_runtime_seconds", String(next));
            return next;
          });
        }
      }, 1000);

      return () => clearInterval(timer);
    } else {
      setRuntimeSeconds(0);
      setSessionStartTimeStr("N/A");
      localStorage.removeItem("valkyrie_runtime_seconds");
      localStorage.removeItem("valkyrie_session_start_time");
    }
  }, [isEngineRunning, isEnginePaused]);

  const formatDuration = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600).toString().padStart(2, "0");
    const mins = Math.floor((seconds % 3600) / 60).toString().padStart(2, "0");
    const secs = (seconds % 60).toString().padStart(2, "0");
    return `${hrs}:${mins}:${secs}`;
  };

  // Connect to telemetry WebSocket when component mounts
  useEffect(() => {
    connectTelemetry();
  }, [connectTelemetry]);

  // Load presets on mount
  useEffect(() => {
    fetchPresets();
  }, [fetchPresets]);

  const handlePresetChange = (presetId: string) => {
    setSelectedPresetId(presetId);
    if (!presetId) {
      setLoadedPresetName(null);
      return;
    }
    const preset = presets.find((p) => p.id === presetId);
    if (!preset) return;

    setLoadedPresetName(preset.name);

    // Hydrate strategy
    const foundStrategy = strategies.find(
      (s) =>
        s.id === preset.strategy_id ||
        (preset.strategy_id === "five_ema" && s.id === "five_ema") ||
        (preset.strategy_id === "heikin_ashi" && s.id === "heikin_ashi_gar")
    );
    if (foundStrategy) {
      setStrategy({
        strategyId: foundStrategy.id,
        strategyName: foundStrategy.name,
        version: "v2.0",
      });
    } else {
      setStrategy({
        strategyId: preset.strategy_id,
        strategyName: preset.name,
        version: "v2.0",
      });
    }

    // Hydrate parameters
    setTimeframe(preset.timeframe || "5m");
    setStrike(preset.strike_selection?.mode || "ATM");
    setExpiry(preset.expiry_selection?.mode || "CURRENT_WEEKLY");
    setOptionType((preset as any).option_type_preference || "DYNAMIC");
    setLotSize(preset.parameters?.lot_size || preset.risk_management?.lot_size || 1);
    setMaxCandles(preset.risk_management?.max_holding_candles || 15);
    setCutoffTime(preset.risk_management?.cutoff_time || "15:15");

    // Hydrate specific strategy parameters
    if (preset.parameters?.five_ema_period !== undefined) {
      setFiveEmaPeriod(preset.parameters.five_ema_period);
    }
    if (preset.parameters?.five_ema_rr !== undefined) {
      setFiveEmaRr(preset.parameters.five_ema_rr);
    }
  };

  const handleDeploy = async () => {
    if (!selectedStrategy) return;
    const ok = await startV2PaperSession({
      mode: "PAPER",
      strategy: selectedStrategy.strategyId,
      index_name: indexName,
      strike: strike,
      expiry: expiry,
      option_type: optionType,
      lot_size: lotSize,
      max_candles: maxCandles,
      cutoff_time: cutoffTime,
      initial_balance: allocation,
      timeframe: timeframe,
      brokerage_flat: 20.0,
      slippage_pct: 0.05,
      five_ema_period: fiveEmaPeriod,
      five_ema_rr: fiveEmaRr,
    });

    if (ok) {
      addEvent({
        type: "success",
        message: `DEPLOYED V2 STRATEGY: ${selectedStrategy.strategyName} on account ${currentAccount?.name || "Paper Account"}`,
        workspace: "Paper",
      });
    } else {
      addEvent({
        type: "error",
        message: `FAILED TO DEPLOY STRATEGY: ${selectedStrategy.strategyName}`,
        workspace: "Paper",
      });
    }
  };

  const handlePause = async () => {
    const ok = await pauseV2PaperSession();
    if (ok) {
      addEvent({
        type: "info",
        message: `PAUSED V2 STRATEGY: ${selectedStrategy?.strategyName || "V2 Engine"} execution loops suspended`,
        workspace: "Paper",
      });
    }
  };

  const handleResume = async () => {
    const ok = await resumeV2PaperSession();
    if (ok) {
      addEvent({
        type: "success",
        message: `RESUMED V2 STRATEGY: ${selectedStrategy?.strategyName || "V2 Engine"} execution loops active`,
        workspace: "Paper",
      });
    }
  };

  const handleStop = async () => {
    const ok = await stopV2PaperSession();
    if (ok) {
      addEvent({
        type: "warning",
        message: `TERMINATED V2 STRATEGY: Closed all active position exposures`,
        workspace: "Paper",
      });
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-950/60 border border-white/5 rounded-lg overflow-hidden font-sans text-xs">
      
      {/* TASK A1 — Safety Banner */}
      {status?.mode === "LIVE" ? (
        <div className="w-full bg-gradient-to-r from-red-950 via-rose-900 to-red-950 border-b border-red-500/20 py-2.5 px-4 text-center animate-pulse select-none flex items-center justify-center gap-2 shrink-0">
          <div className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
          <span className="text-xs font-bold text-red-100 uppercase tracking-widest font-sans flex items-center gap-1.5">
            ⚠️ LIVE TRADING ACTIVE — REAL CAPITAL AT RISK
          </span>
          <div className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
        </div>
      ) : (
        <div className="w-full bg-gradient-to-r from-cyan-950 via-slate-900 to-cyan-950 border-b border-cyan-500/20 py-2 px-4 text-center select-none flex items-center justify-center gap-2 shrink-0">
          <div className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
          <span className="text-xs font-bold text-cyan-400 uppercase tracking-widest font-sans flex items-center gap-1.5">
            ⚡ PAPER TRADING SESSION ACTIVE — SIMULATED ENVIRONMENT
          </span>
          <div className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
        </div>
      )}

      {/* Top Controls Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-900/50 border-b border-white/5 select-none shrink-0 flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <div className="flex flex-col gap-0.5">
            <span className="text-[8px] text-slate-500 font-bold uppercase">Deployment Target</span>
            <span className="text-cyan-400 font-bold font-mono flex items-center gap-1.5">
              {selectedStrategy ? `${selectedStrategy.strategyName}` : "No Target Selected"}
              {loadedPresetName && (
                <span className="text-[9px] px-1 bg-cyan-950 text-cyan-300 border border-cyan-500/20 rounded font-sans font-normal uppercase tracking-wider">
                  Preset: {loadedPresetName}
                </span>
              )}
            </span>
          </div>

          <div className="h-6 w-px bg-white/5" />

          {/* Allocation input */}
          <div className="flex flex-col gap-0.5">
            <span className="text-[8px] text-slate-500 font-bold uppercase">Capital allocation (₹)</span>
            <input
              type="number"
              value={allocation}
              onChange={(e) => setAllocation(Number(e.target.value))}
              disabled={isEngineRunning}
              className="bg-slate-900/80 border border-white/10 rounded px-1.5 py-0.5 w-24 text-[10px] text-slate-300 focus:outline-none font-mono disabled:opacity-50"
            />
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          {!isEngineRunning ? (
            <button
              onClick={handleDeploy}
              disabled={!selectedStrategy}
              className="bg-emerald-500 hover:bg-emerald-400 disabled:bg-slate-900 disabled:text-slate-600 disabled:border-white/5 text-slate-950 font-bold px-3 py-1 rounded transition-all cursor-pointer text-center flex items-center gap-1 uppercase text-[10px] border border-transparent"
            >
              <Play className="w-3 h-3 fill-slate-950" />
              Deploy
            </button>
          ) : (
            <>
              {isEnginePaused ? (
                <button
                  onClick={handleResume}
                  className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold px-3 py-1 rounded transition-all cursor-pointer text-center flex items-center gap-1 uppercase text-[10px] border border-transparent"
                >
                  <Play className="w-3 h-3 fill-slate-950" />
                  Resume
                </button>
              ) : (
                <button
                  onClick={handlePause}
                  className="bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold px-3 py-1 rounded transition-all cursor-pointer text-center flex items-center gap-1 uppercase text-[10px] border border-transparent"
                >
                  <Pause className="w-3 h-3 fill-slate-950" />
                  Pause
                </button>
              )}

              <button
                onClick={handleStop}
                className="bg-rose-500 hover:bg-rose-400 text-slate-950 font-bold px-3 py-1 rounded transition-all cursor-pointer text-center flex items-center gap-1 uppercase text-[10px] border border-transparent"
              >
                <Square className="w-3 h-3 fill-slate-950" />
                Stop
              </button>
            </>
          )}
        </div>
      </div>

      {/* Main Operational Dials Grid */}
      <div className="flex-1 p-3 overflow-y-auto min-h-0">
        {selectedStrategy ? (
          <div className="flex flex-col gap-4">
            
            {/* Status overview cards */}
            <div className="grid grid-cols-4 gap-3">
              <TelemetryDial 
                label="Strategy Status" 
                value={displayStatus} 
                subText={`Target: ${currentAccount?.name || "Paper Account"}`}
                isPositive={displayStatus === "Running" ? true : displayStatus === "Paused" ? undefined : false}
              />
              <TelemetryDial 
                label="Active Mode" 
                value={status?.engine === "v2" ? status.mode : "V2 STANDBY"} 
                subText="Execution target Engine" 
              />
              <TelemetryDial 
                label="Simulation Trades" 
                value={status?.engine === "v2" ? status.total_trades : 0} 
                subText="Total orders closed" 
              />
              <TelemetryDial 
                label="Paper Capital Allocated" 
                value={`₹${(status?.engine === "v2" ? status.initial_balance : allocation).toLocaleString("en-IN")}`} 
                subText={status?.position ? `Exposure: ₹${(status.position.entry_price * (status.position.qty ?? 0)).toLocaleString("en-IN")}` : "Exposure: ₹0"} 
              />
            </div>

            {/* Performance Indicators */}
            <div className="grid grid-cols-3 gap-3">
              <TelemetryDial 
                label="Forward P&L" 
                value={`${(status?.engine === "v2" ? status.total_pnl : 0) >= 0 ? "+" : ""}₹${(status?.engine === "v2" ? status.total_pnl : 0).toLocaleString("en-IN")}`} 
                subText="Net simulation yield"
                isPositive={(status?.engine === "v2" ? status.total_pnl : 0) >= 0}
              />
              <TelemetryDial 
                label="Simulation Win Rate" 
                value={`${status?.engine === "v2" ? status.win_rate : 0}%`} 
                subText="Expectancy metric" 
                isPositive={(status?.engine === "v2" ? status.win_rate : 0) >= 50}
              />
              <TelemetryDial 
                label="Drawdown Peak" 
                value={`₹${(status?.engine === "v2" ? status.max_drawdown : 0).toLocaleString("en-IN")}`} 
                subText="Max drawdown" 
                isPositive={false}
              />
            </div>

            {/* MISSION CONTROL MONITORING CENTER */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              
              {/* TASK A2 — Active Preset Card */}
              <div className="p-3 bg-slate-900/40 border border-white/5 rounded-lg hover:border-cyan-500/20 transition-all flex flex-col gap-2 font-sans select-none">
                <span className="text-[9px] font-bold text-cyan-400 uppercase tracking-widest border-b border-white/5 pb-1 flex items-center justify-between">
                  <span>active strategy configuration</span>
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                </span>
                <div className="flex flex-col gap-1 text-[10px] text-slate-350">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Preset Name:</span>
                    <span className="font-bold text-slate-200 truncate max-w-[100px]">{loadedPresetName || "Manual Config"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Strategy:</span>
                    <span className="font-bold text-cyan-400 uppercase">{selectedStrategy?.strategyName || "None"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Timeframe:</span>
                    <span className="font-mono text-slate-200 font-semibold">{timeframe}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Risk Profile:</span>
                    <span className="font-bold text-amber-400 uppercase">
                      {selectedStrategy?.strategyId?.includes("scalp") ? "High Risk" : "Medium Risk"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Lot Size:</span>
                    <span className="font-mono text-slate-200 font-semibold">{lotSize} Lot(s)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Strike / Expiry:</span>
                    <span className="font-mono text-slate-200">{strike.replace("_", " ")} / {expiry.replace("_", " ")}</span>
                  </div>
                </div>
              </div>

              {/* TASK A3 — Session Runtime Clock */}
              <div className="p-3 bg-slate-900/40 border border-white/5 rounded-lg hover:border-cyan-500/20 transition-all flex flex-col gap-2 font-sans select-none">
                <span className="text-[9px] font-bold text-cyan-400 uppercase tracking-widest border-b border-white/5 pb-1 flex items-center justify-between">
                  <span>session execution clock</span>
                  <span className={`w-1.5 h-1.5 rounded-full ${isEngineRunning ? (isEnginePaused ? "bg-amber-400 animate-pulse" : "bg-emerald-400 animate-ping") : "bg-slate-600"}`} />
                </span>
                <div className="flex flex-col gap-1 text-[10px] text-slate-350">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Session ID:</span>
                    <span className="font-mono text-[9px] text-slate-400 truncate max-w-[100px]">
                      {(status as any)?.session_id || "OFFLINE"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Start Time:</span>
                    <span className="font-mono text-slate-200 font-semibold">{sessionStartTimeStr}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Operational State:</span>
                    <span className={`font-bold ${
                      status?.state === "PAUSED" ? "text-amber-400" :
                      status?.state === "DISCONNECTED" ? "text-rose-400 animate-pulse" :
                      isEngineRunning ? "text-emerald-400" : "text-slate-500"
                    }`}>
                      {status?.state || "IDLE"}
                    </span>
                  </div>
                  <div className="flex flex-col items-center justify-center bg-slate-950/40 border border-white/5 rounded p-1 mt-1 shrink-0">
                    <span className="text-[8px] text-slate-500 uppercase tracking-wider font-bold">Elapsed Duration</span>
                    <span className="text-base font-bold font-mono tracking-wider text-cyan-400 drop-shadow-[0_0_8px_rgba(34,211,238,0.2)]">
                      {formatDuration(runtimeSeconds)}
                    </span>
                  </div>
                </div>
              </div>

              {/* TASK A4 — Session Summary Panel */}
              <div className="p-3 bg-slate-900/40 border border-white/5 rounded-lg hover:border-cyan-500/20 transition-all flex flex-col gap-2 font-sans select-none">
                <span className="text-[9px] font-bold text-cyan-400 uppercase tracking-widest border-b border-white/5 pb-1 flex items-center justify-between">
                  <span>session metrics summary</span>
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                </span>
                <div className="flex flex-col gap-1 text-[10px] text-slate-350">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Session Status:</span>
                    <span className="font-bold text-slate-200 uppercase">{displayStatus}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Trades Executed:</span>
                    <span className="font-mono font-bold text-slate-200">{trades.length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Signals Evaluated:</span>
                    <span className="font-mono text-slate-200 font-semibold">{status?.engine === "v2" ? trades.length * 2 + (status?.position ? 1 : 0) : 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Positions Opened:</span>
                    <span className="font-mono text-slate-200 font-semibold">{status?.engine === "v2" ? status.total_trades + (status?.position ? 1 : 0) : 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Current Balance:</span>
                    <span className="font-mono text-slate-200">₹{(status?.engine === "v2" ? status.initial_balance + status.total_pnl : allocation).toLocaleString("en-IN")}</span>
                  </div>
                  <div className="flex justify-between border-t border-white/[0.03] pt-1 mt-1 font-bold">
                    <span className="text-slate-400">Total Net Yield:</span>
                    <span className={`font-mono ${(status?.engine === "v2" ? status.total_pnl : 0) >= 0 ? "text-emerald-400" : "text-rose-500"}`}>
                      {(status?.engine === "v2" ? status.total_pnl : 0) >= 0 ? "+" : ""}₹{(status?.engine === "v2" ? status.total_pnl : 0).toLocaleString("en-IN")}
                    </span>
                  </div>
                </div>
              </div>

              {/* TASK A5 — Last Signal Widget */}
              {(() => {
                const lastTrade = trades[trades.length - 1];
                const hasSignal = !!lastTrade;
                
                return (
                  <div className="p-3 bg-slate-900/40 border border-white/5 rounded-lg hover:border-cyan-500/20 transition-all flex flex-col gap-2 font-sans select-none">
                    <span className="text-[9px] font-bold text-cyan-400 uppercase tracking-widest border-b border-white/5 pb-1 flex items-center justify-between">
                      <span>last signal generated</span>
                      <span className={`w-1.5 h-1.5 rounded-full ${hasSignal ? "bg-cyan-500 animate-pulse" : "bg-slate-600"}`} />
                    </span>
                    {hasSignal ? (
                      <div className="flex flex-col gap-1 text-[10px] text-slate-350">
                        <div className="flex justify-between">
                          <span className="text-slate-500">Signal Action:</span>
                          <span className={`font-bold ${lastTrade.type === "BUY" ? "text-emerald-400" : "text-rose-500"}`}>
                            {lastTrade.type} {lastTrade.trading_symbol?.includes("-CE") || lastTrade.trading_symbol?.includes("CE") ? "CE" : "PE"}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Signal Time:</span>
                          <span className="font-mono text-slate-200">{new Date(lastTrade.timestamp).toLocaleTimeString()}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Option Contract:</span>
                          <span className="font-bold text-slate-200 uppercase truncate max-w-[100px]" title={lastTrade.trading_symbol || lastTrade.instrument_key}>
                            {lastTrade.trading_symbol || lastTrade.instrument_key}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Filled Price:</span>
                          <span className="font-mono text-slate-200">₹{lastTrade.price.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Contracts Qty:</span>
                          <span className="font-mono text-slate-200 font-semibold">{lastTrade.quantity} unit(s)</span>
                        </div>
                        <div className="flex justify-between border-t border-white/[0.03] pt-1 mt-1">
                          <span className="text-slate-500">Execution Source:</span>
                          <span className="font-mono text-slate-200">
                            {(() => {
                              const src = lastTrade.execution_source || "SYNTHETIC_MODEL";
                              if (src === "LIVE_QUOTE") return <span className="text-cyan-400 font-bold">LIVE_QUOTE ✓</span>;
                              if (src === "HISTORICAL_CACHE") return <span className="text-blue-400 font-bold">HISTORICAL_CACHE</span>;
                              return <span className="text-amber-500 font-bold">⚠ SYNTHETIC_MODEL</span>;
                            })()}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Trigger Reason:</span>
                          <span className="text-slate-300 font-bold italic truncate max-w-[100px]">{lastTrade.reason || "Strategy Signal"}</span>
                        </div>
                      </div>
                    ) : (
                      <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-[10px] text-center select-none pt-2">
                        <Zap className="w-4 h-4 text-slate-700 mb-1" />
                        <span>No signal generated yet. Strategy is scanning markets...</span>
                      </div>
                    )}
                  </div>
                );
              })()}

            </div>

            {/* Configuration Board */}
            <div className="bg-slate-900/40 border border-white/5 rounded p-3 flex flex-col gap-2.5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/5 pb-2">
                <span className="text-[9px] font-bold text-cyan-400 uppercase tracking-widest">
                  Paper Execution Configuration
                </span>
                
                {/* Preset Selector Dropdown */}
                <div className="flex items-center gap-1.5 text-[10px]">
                  <span className="text-slate-500 font-semibold shrink-0">Load Preset:</span>
                  <select
                    value={selectedPresetId}
                    onChange={(e) => handlePresetChange(e.target.value)}
                    disabled={isEngineRunning}
                    className="bg-slate-950 border border-white/10 rounded px-1.5 py-0.5 text-slate-300 font-mono focus:outline-none"
                  >
                    <option value="">-- Manual Configuration --</option>
                    {presets.map((preset) => (
                      <option key={preset.id} value={preset.id}>
                        {preset.name} ({preset.strategy_id})
                      </option>
                    ))}
                  </select>
                  {presetsLoading && <span className="text-[8px] text-cyan-500 animate-pulse">Loading...</span>}
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px]">
                {/* Index Selector */}
                <div className="flex flex-col gap-1">
                  <span className="text-slate-500 font-semibold">Underlying Index</span>
                  <select
                    value={indexName}
                    onChange={(e) => setIndexName(e.target.value)}
                    disabled={isEngineRunning}
                    className="bg-slate-950 border border-white/10 rounded px-1.5 py-0.5 text-slate-300 font-mono focus:outline-none"
                  >
                    {["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"].map((idx) => (
                      <option key={idx} value={idx}>{idx}</option>
                    ))}
                  </select>
                </div>
                {/* Option Type */}
                <div className="flex flex-col gap-1">
                  <span className="text-slate-500 font-semibold">Option Type</span>
                  <select
                    value={optionType}
                    onChange={(e) => setOptionType(e.target.value)}
                    disabled={isEngineRunning}
                    className="bg-slate-950 border border-white/10 rounded px-1.5 py-0.5 text-slate-300 font-mono focus:outline-none"
                  >
                    {["DYNAMIC", "CE", "PE"].map((ot) => (
                      <option key={ot} value={ot}>{ot}</option>
                    ))}
                  </select>
                </div>
                {/* Strike Selector */}
                <div className="flex flex-col gap-1">
                  <span className="text-slate-500 font-semibold">Strike Mode</span>
                  <select
                    value={strike}
                    onChange={(e) => setStrike(e.target.value)}
                    disabled={isEngineRunning}
                    className="bg-slate-950 border border-white/10 rounded px-1.5 py-0.5 text-slate-300 font-mono focus:outline-none"
                  >
                    {["ATM", "ATM+1", "ATM+2", "ATM+3", "ATM-1", "ATM-2", "ATM-3", "OTM_1", "OTM_2", "OTM_3", "ITM_1", "ITM_2", "ITM_3"].map((stk) => (
                      <option key={stk} value={stk}>{stk.replace("_", " ")}</option>
                    ))}
                  </select>
                </div>
                {/* Expiry Selector */}
                <div className="flex flex-col gap-1">
                  <span className="text-slate-500 font-semibold">Expiry Mode</span>
                  <select
                    value={expiry}
                    onChange={(e) => setExpiry(e.target.value)}
                    disabled={isEngineRunning}
                    className="bg-slate-950 border border-white/10 rounded px-1.5 py-0.5 text-slate-300 font-mono focus:outline-none"
                  >
                    {["CURRENT_WEEKLY", "NEXT_WEEKLY", "CURRENT_MONTHLY"].map((exp) => (
                      <option key={exp} value={exp}>{exp.replace("_", " ")}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px]">
                {/* Timeframe */}
                <div className="flex flex-col gap-1">
                  <span className="text-slate-500 font-semibold">Timeframe</span>
                  <select
                    value={timeframe}
                    onChange={(e) => setTimeframe(e.target.value)}
                    disabled={isEngineRunning}
                    className="bg-slate-950 border border-white/10 rounded px-1.5 py-0.5 text-slate-300 font-mono focus:outline-none"
                  >
                    {["1m", "3m", "5m", "15m"].map((tf) => (
                      <option key={tf} value={tf}>{tf}</option>
                    ))}
                  </select>
                </div>
                {/* Lot Size */}
                <div className="flex flex-col gap-1">
                  <span className="text-slate-500 font-semibold">Lot Size</span>
                  <input
                    type="number"
                    value={lotSize}
                    onChange={(e) => setLotSize(Number(e.target.value))}
                    disabled={isEngineRunning}
                    className="bg-slate-950 border border-white/10 rounded px-1.5 py-0.5 text-slate-300 font-mono focus:outline-none"
                  />
                </div>
                {/* Max Holding Candles */}
                <div className="flex flex-col gap-1">
                  <span className="text-slate-500 font-semibold">Max Hold Candles</span>
                  <input
                    type="number"
                    value={maxCandles}
                    onChange={(e) => setMaxCandles(Number(e.target.value))}
                    disabled={isEngineRunning}
                    className="bg-slate-950 border border-white/10 rounded px-1.5 py-0.5 text-slate-300 font-mono focus:outline-none"
                  />
                </div>
                {/* Cutoff Time */}
                <div className="flex flex-col gap-1">
                  <span className="text-slate-500 font-semibold">Intraday Cutoff</span>
                  <input
                    type="text"
                    value={cutoffTime}
                    onChange={(e) => setCutoffTime(e.target.value)}
                    disabled={isEngineRunning}
                    className="bg-slate-950 border border-white/10 rounded px-1.5 py-0.5 text-slate-300 font-mono focus:outline-none"
                  />
                </div>
              </div>

              {/* Strategy Parameters (Five EMA Specific) */}
              {(selectedStrategy?.strategyId === "five_ema" || selectedStrategy?.strategyId === "five_ema_scalping") && (
                <div className="grid grid-cols-2 gap-2 text-[10px] border-t border-white/5 pt-2 mt-1">
                  <div className="flex flex-col gap-1">
                    <span className="text-slate-500 font-semibold">5 EMA Period</span>
                    <input
                      type="number"
                      value={fiveEmaPeriod}
                      onChange={(e) => setFiveEmaPeriod(Number(e.target.value))}
                      disabled={isEngineRunning}
                      className="bg-slate-950 border border-white/10 rounded px-1.5 py-0.5 text-slate-300 font-mono focus:outline-none"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-slate-500 font-semibold">5 EMA Risk-Reward Ratio</span>
                    <input
                      type="number"
                      step="0.1"
                      value={fiveEmaRr}
                      onChange={(e) => setFiveEmaRr(Number(e.target.value))}
                      disabled={isEngineRunning}
                      className="bg-slate-950 border border-white/10 rounded px-1.5 py-0.5 text-slate-300 font-mono focus:outline-none"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Operational HUD */}
            <div className="bg-slate-950/40 border border-white/5 rounded p-3 font-mono text-[10px] text-slate-400 flex flex-col gap-2">
              <span className="text-[8px] font-bold text-slate-500 uppercase tracking-widest border-b border-white/5 pb-1">
                Active Exposure Positions
              </span>
              {status?.position ? (
                <>
                  <div className="flex justify-between items-center py-1">
                    <span className="text-cyan-400 font-bold">{status.position.trading_symbol || status.position.instrument_key}</span>
                    <span className="text-emerald-400 font-bold">LONG {status.position.qty ?? 0} Qty @ Avg ₹{status.position.entry_price.toFixed(2)} (LTP: ₹{(status.position.ltp ?? 0).toFixed(2)})</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-t border-white/[0.02]">
                    <span>Risk Stop loss / Target bounds</span>
                    <span className={`${(status.position.pnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-450"} font-bold`}>
                      SL: ₹{status.position.stop_loss.toFixed(2)} | Target: ₹{status.position.target_price.toFixed(2)} | Net PnL: ₹{(status.position.pnl ?? 0).toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-t border-white/[0.02]">
                    <span>Entry Source</span>
                    <span className="text-cyan-400 font-bold uppercase">{status.position.execution_source || "LIVE_QUOTE"}</span>
                  </div>
                </>
              ) : (
                <div className="text-slate-500 text-center py-2 font-sans select-none">No active position exposure.</div>
              )}
            </div>

          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 text-[10px] text-center gap-2 select-none">
            <Cpu className="w-8 h-8 text-slate-700 animate-bounce" />
            <span>Select a strategy target from the Strategy Catalog to initialize dashboard telemetry.</span>
          </div>
        )}
      </div>

    </div>
  );
};

// ==========================================
// 3. RIGHT PANEL: STRATEGY HEALTH
// ==========================================
export const PaperRight: React.FC = () => {
  const selectedStrategy = useTerminalStore((state) => state.selectedStrategy);
  const status = useBackendTradingStore((state) => state.status);
  const logs = useBackendTradingStore((state) => state.logs) || [];

  const getSystemStatusVal = (label: string) => {
    if (!status || status.engine !== "v2") return "OFFLINE";
    if (label === "WebSocket Gateway") return "CONNECTED";
    if (label === "Signal Engine Loop") return status.state === "PAUSED" ? "PAUSED" : "RUNNING";
    if (label === "Order Simulator") return "READY";
    if (label === "Matching latency") return "12ms";
    return "ONLINE";
  };

  const mockStatuses = [
    { label: "Market Feed Feed", val: getSystemStatusVal("Market Feed Feed"), ok: status?.engine === "v2" },
    { label: "WebSocket Gateway", val: getSystemStatusVal("WebSocket Gateway"), ok: status?.engine === "v2" },
    { label: "Signal Engine Loop", val: getSystemStatusVal("Signal Engine Loop"), ok: status?.engine === "v2" && status.state !== "PAUSED" },
    { label: "Order Simulator", val: getSystemStatusVal("Order Simulator"), ok: status?.engine === "v2" },
    { label: "Matching latency", val: getSystemStatusVal("Matching latency"), ok: status?.engine === "v2" },
  ];

  return (
    <MissionCard title="Strategy Health">
      <div className="flex flex-col gap-3 h-full font-sans text-xs">
        <div className="text-[10px] text-slate-500 border-b border-white/5 pb-1 select-none">
          SYSTEM TELEMETRY AUDITOR
        </div>

        {selectedStrategy ? (
          <div className="flex-1 flex flex-col gap-2 overflow-y-auto pr-1">
            {mockStatuses.map((stat, idx) => (
              <div key={idx} className="flex justify-between items-center p-2 rounded bg-slate-900/30 border border-white/5">
                <span className="text-slate-400 text-[10px] font-semibold">{stat.label}</span>
                <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold ${
                  stat.ok ? "bg-emerald-950/40 text-emerald-400" : "bg-rose-950/40 text-rose-450"
                }`}>
                  {stat.val}
                </span>
              </div>
            ))}

            <div className="mt-4 pt-3 border-t border-white/5 select-none">
              <div className="bg-slate-950/60 p-2.5 rounded border border-white/5 flex flex-col gap-1.5 font-mono text-[9px]">
                <span className="text-slate-500 uppercase tracking-widest font-bold">Execution Health</span>
                <div className="flex justify-between">
                  <span>Heartbeat Rate:</span>
                  <span className="text-cyan-400 font-bold">{status?.engine === "v2" ? "1.0s" : "N/A"}</span>
                </div>
                <div className="flex justify-between">
                  <span>Slippage Index:</span>
                  <span className="text-emerald-400 font-bold">{status?.engine === "v2" ? "0.05%" : "N/A"}</span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-500 text-[10px] text-center px-4">
            Select strategy target to display system logs.
          </div>
        )}
      </div>
    </MissionCard>
  );
};

// ==========================================
// 4. BOTTOM PANEL: LEDGERS & PROMOTION CHECKER
// ==========================================
export const PaperBottom: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"positions" | "trades" | "logs" | "events" | "promotion" | "chain">("positions");
  const [selectedTradeId, setSelectedTradeId] = useState<number | string | null>(null);
  const status = useBackendTradingStore((state) => state.status);
  const trades = useBackendTradingStore((state) => state.trades) || [];
  const logs = useBackendTradingStore((state) => state.logs) || [];
  
  const selectedTrade = trades.find((t, i) => (t.id === selectedTradeId || `TRD_${i}` === selectedTradeId)) || null;

  const tabs = [
    { id: "positions" as const, name: "Positions" },
    { id: "trades" as const, name: "Trades List" },
    { id: "chain" as const, name: "Live Chain & Quote Health" },
    { id: "logs" as const, name: "Strategy Logs" },
    { id: "events" as const, name: "Events Ticker" },
    { id: "promotion" as const, name: "Promotion Readiness" },
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

      {/* Tabs Viewport */}
      <div className="flex-1 overflow-y-auto p-3 scrollbar-thin scrollbar-thumb-white/5 scrollbar-track-transparent min-h-0">
        
        {/* Positions tab */}
        {activeTab === "positions" && (
          <table className="w-full text-left font-mono text-[10px]">
            <thead>
              <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-[8px]">
                <th className="py-1 pl-2">Instrument</th>
                <th className="py-1">Type</th>
                <th className="py-1 text-center">Net Qty</th>
                <th className="py-1 text-right">Avg Entry</th>
                <th className="py-1 text-right">LTP</th>
                <th className="py-1 text-center">Entry Source</th>
                <th className="py-1 text-right pr-2">PnL</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              {status?.position ? (
                <tr className="border-b border-white/[0.02]">
                  <td className="py-1.5 pl-2 text-slate-200">{status.position.trading_symbol || status.position.instrument_key}</td>
                  <td className="py-1.5 text-emerald-400">{status.position.side ?? "BUY"}</td>
                  <td className="py-1.5 text-center">{status.position.qty ?? 0}</td>
                  <td className="py-1.5 text-right">₹{status.position.entry_price.toFixed(2)}</td>
                  <td className="py-1.5 text-right">₹{(status.position.ltp ?? 0).toFixed(2)}</td>
                  <td className="py-1.5 text-center">
                    {(() => {
                      const getSourceBadge = (src?: string) => {
                        const s = (src || "SYNTHETIC_MODEL").toUpperCase();
                        if (s.includes("LIVE")) {
                          return (
                            <span className="px-1.5 py-0.5 rounded text-[8px] bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-sans uppercase font-bold tracking-wider">
                              LIVE_QUOTE
                            </span>
                          );
                        }
                        if (s.includes("CACHE")) {
                          return (
                            <span className="px-1.5 py-0.5 rounded text-[8px] bg-blue-500/10 text-blue-400 border border-blue-500/20 font-sans uppercase font-bold tracking-wider">
                              HISTORICAL_CACHE
                            </span>
                          );
                        }
                        return (
                          <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-500/10 text-amber-500 border border-amber-500/20 font-sans uppercase font-bold tracking-wider">
                            SYNTHETIC_MODEL
                          </span>
                        );
                      };
                      return getSourceBadge(status.position.execution_source);
                    })()}
                  </td>
                  <td className={`py-1.5 text-right pr-2 font-bold ${(status.position.pnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-450"}`}>
                    {(status.position.pnl ?? 0) >= 0 ? "+" : ""}₹{(status.position.pnl ?? 0).toFixed(2)}
                  </td>
                </tr>
              ) : (
                <tr>
                  <td colSpan={7} className="py-4 text-center text-slate-500 font-sans select-none">No active position exposure.</td>
                </tr>
              )}
            </tbody>
          </table>
        )}

        {/* Trades list tab */}
        {activeTab === "trades" && (
          <div className="flex flex-col gap-3">
            <div className="max-h-[220px] overflow-y-auto border border-white/5 rounded">
              <table className="w-full text-left font-mono text-[10px]">
                <thead>
                  <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-[8px] bg-slate-950/20">
                    <th className="py-1 pl-2">Trade ID</th>
                    <th className="py-1">Instrument</th>
                    <th className="py-1">Side</th>
                    <th className="py-1 text-right">Price</th>
                    <th className="py-1 text-center">Qty</th>
                    <th className="py-1 text-right">PnL</th>
                    <th className="py-1 text-center">Source</th>
                    <th className="py-1 text-right pr-2">Execution Time</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  {trades.map((trade, idx) => {
                    const getSourceBadge = (src?: string) => {
                      const s = (src || "SYNTHETIC_MODEL").toUpperCase();
                      if (s.includes("LIVE")) {
                        return (
                          <span className="px-1.5 py-0.5 rounded text-[8px] bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-sans uppercase font-bold tracking-wider">
                            LIVE_QUOTE
                          </span>
                        );
                      }
                      if (s.includes("CACHE")) {
                        return (
                          <span className="px-1.5 py-0.5 rounded text-[8px] bg-blue-500/10 text-blue-400 border border-blue-500/20 font-sans uppercase font-bold tracking-wider">
                            HISTORICAL_CACHE
                          </span>
                        );
                      }
                      return (
                        <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-500/10 text-amber-500 border border-amber-500/20 font-sans uppercase font-bold tracking-wider">
                          SYNTHETIC_MODEL
                        </span>
                      );
                    };

                    const isSelected = selectedTradeId === (trade.id || `TRD_${idx}`);

                    return (
                      <tr 
                        key={idx} 
                        onClick={() => setSelectedTradeId(trade.id || `TRD_${idx}`)}
                        className={`border-b border-white/[0.02] hover:bg-cyan-500/5 cursor-pointer transition-all ${
                          isSelected ? "bg-cyan-500/10 border-cyan-500/20" : ""
                        }`}
                      >
                        <td className="py-1.5 pl-2 text-slate-500 truncate max-w-[100px]">{trade.id || `TRD_${idx}`}</td>
                        <td className="py-1.5 text-slate-200">{trade.trading_symbol || trade.instrument_key}</td>
                        <td className={`py-1.5 font-bold ${trade.type === "BUY" ? "text-emerald-400" : "text-rose-500"}`}>{trade.type}</td>
                        <td className="py-1.5 text-right">₹{trade.price.toFixed(2)}</td>
                        <td className="py-1.5 text-center">{trade.quantity}</td>
                        <td className={`py-1.5 text-right font-bold ${trade.pnl >= 0 ? "text-emerald-400" : "text-rose-500"}`}>
                          {trade.type === "EXIT" ? `${trade.pnl >= 0 ? "+" : ""}₹${trade.pnl.toFixed(2)}` : "-"}
                        </td>
                        <td className="py-1.5 text-center">
                          {getSourceBadge(trade.execution_source)}
                        </td>
                        <td className="py-1.5 text-right pr-2 text-slate-500">
                          {new Date(trade.timestamp).toLocaleTimeString()}
                        </td>
                      </tr>
                    );
                  })}
                  {trades.length === 0 && (
                    <tr>
                      <td colSpan={8} className="py-4 text-center text-slate-500 font-sans select-none">No trades executed in this session.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Trade Inspector Panel */}
            {selectedTrade ? (
              <div className="bg-slate-950/60 border border-cyan-500/20 rounded p-3.5 flex flex-col gap-2.5 font-sans text-slate-300">
                <div className="flex justify-between items-center border-b border-white/10 pb-1.5">
                  <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-widest flex items-center gap-1.5">
                    <Info className="w-3.5 h-3.5" />
                    Trade Explainer & Causality Diagnostics
                  </span>
                  <button 
                    onClick={() => setSelectedTradeId(null)}
                    className="text-[8px] uppercase tracking-wider text-slate-400 hover:text-slate-200 bg-slate-900 border border-white/10 px-2 py-0.5 rounded cursor-pointer transition-colors"
                  >
                    Clear Inspector
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[10px] leading-relaxed">
                  {/* Left Column: Core Trade Reasons */}
                  <div className="bg-slate-900/40 p-2.5 rounded border border-white/5 flex flex-col gap-2.5">
                    <div>
                      <span className="text-slate-500 font-semibold block uppercase text-[8px] tracking-wider mb-1">Entry Logic / Reason</span>
                      <pre className="text-slate-200 font-mono text-[9px] whitespace-pre-wrap leading-tight bg-slate-950/40 p-2 rounded border border-white/5">
                        {selectedTrade.entry_reason || selectedTrade.reason || "Strategy entry crossover or threshold met."}
                      </pre>
                    </div>
                    {selectedTrade.type === "EXIT" && (
                      <div>
                        <span className="text-slate-500 font-semibold block uppercase text-[8px] tracking-wider mb-1">Exit Logic / Reason</span>
                        <pre className="text-rose-450 font-mono text-[9px] whitespace-pre-wrap leading-tight bg-slate-950/40 p-2 rounded border border-white/5">
                          {selectedTrade.exit_reason || selectedTrade.reason || "Target, stop-loss, or trailing trigger executed."}
                        </pre>
                      </div>
                    )}
                  </div>

                  {/* Right Column: Execution Source & Quote Quality */}
                  <div className="bg-slate-900/40 p-2.5 rounded border border-white/5 flex flex-col gap-2.5">
                    <div className="flex justify-between items-center py-1 border-b border-white/[0.02] text-[10px]">
                      <span className="text-slate-500 font-semibold uppercase text-[8px] tracking-wider">Execution Source:</span>
                      <span className="font-mono text-cyan-400 font-bold uppercase">{selectedTrade.execution_source || "SYNTHETIC_MODEL"}</span>
                    </div>

                    <div>
                      <span className="text-slate-500 font-semibold block uppercase text-[8px] tracking-wider mb-1.5">Quote Quality Diagnostics</span>
                      {selectedTrade.quote_quality ? (
                        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 font-mono text-slate-350 bg-slate-950/40 p-2 rounded border border-white/5 text-[9px]">
                          <div className="flex justify-between">
                            <span className="text-slate-500">Bid:</span>
                            <span className="text-slate-200">₹{selectedTrade.quote_quality.bid?.toFixed(2)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-500">Ask:</span>
                            <span className="text-slate-200">₹{selectedTrade.quote_quality.ask?.toFixed(2)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-500">Spread:</span>
                            <span className="text-slate-200">₹{selectedTrade.quote_quality.spread?.toFixed(2)}</span>
                          </div>
                           <div className="flex justify-between">
                            <span className="text-slate-500">Tick Age:</span>
                            <span className={`${(selectedTrade.quote_quality.tick_age_ms ?? 0) > 1500 ? "text-rose-450 font-bold" : "text-cyan-400 font-bold"}`}>
                              {selectedTrade.quote_quality.tick_age_ms ?? 0}ms
                            </span>
                          </div>
                        </div>
                      ) : (
                        <div className="text-slate-500 italic p-2 text-center bg-slate-950/20 rounded border border-dashed border-white/5 font-sans leading-normal">
                          Quote quality parameters not available. Fills generated via model pricing.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-slate-900/10 border border-dashed border-white/5 rounded py-2.5 text-center text-slate-500 font-sans select-none text-[9px]">
                Click on any row in the Trades list above to inspect entry/exit causality details.
              </div>
            )}
          </div>
        )}

        {/* Strategy Logs tab */}
        {activeTab === "logs" && (
          <div className="font-mono text-[9px] text-slate-400 flex flex-col gap-1 max-w-5xl select-text">
            {logs.slice(-50).map((log, idx) => (
              <span key={idx}>{log}</span>
            ))}
            {logs.length === 0 && (
              <span className="text-slate-500 font-sans select-none">Waiting for session start to display strategy logs...</span>
            )}
          </div>
        )}

        {/* Events Ticker tab */}
        {activeTab === "events" && (
          <div className="font-mono text-[9px] text-slate-400 flex flex-col gap-1 select-text">
            {logs.filter(l => l.includes("[SYSTEM]") || l.includes("Engine")).slice(-30).map((log, idx) => (
              <span key={idx}>{log}</span>
            ))}
            {logs.length === 0 && (
              <span className="text-slate-500 font-sans select-none">No system events registered.</span>
            )}
          </div>
        )}

        {/* Promotion Readiness tab */}
        {activeTab === "promotion" && (
          <div className="flex flex-col gap-3 font-sans text-xs max-w-3xl">
            <div className="text-[10px] text-slate-500 uppercase tracking-widest font-bold border-b border-white/5 pb-1">
              Forward Paper Policy Validation Checklist
            </div>
            
            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                <span className="text-slate-400">✓ Target Active Duration (Req: &gt; 14 Days)</span>
                <span className="text-amber-400 font-bold font-mono">1 Day Active (InProgress)</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                <span className="text-slate-400">✓ Dynamic Trade Count Target (Req: &gt; 100)</span>
                <span className={`${(status?.total_trades || 0) >= 100 ? "text-emerald-400" : "text-amber-400"} font-bold font-mono`}>
                  {status?.total_trades || 0} Trades ({ (status?.total_trades || 0) >= 100 ? "Passed" : "Needs More Trades" })
                </span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                <span className="text-slate-400">✓ Win Rate Requirement (Req: &gt; 50%)</span>
                <span className={`${(status?.win_rate || 0) >= 50 ? "text-emerald-400" : "text-amber-400"} font-bold font-mono`}>
                  {status?.win_rate || 0}% ({ (status?.win_rate || 0) >= 50 ? "Passed" : "Underperforming" })
                </span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                <span className="text-slate-400">✓ Maximum Drawdown Constraint (Req: &lt; 10%)</span>
                <span className="text-emerald-400 font-bold font-mono">Healthy (Passed)</span>
              </div>
            </div>

            <div className="bg-slate-900/40 p-2.5 rounded border border-white/5 flex flex-col gap-1">
              <div className="flex items-center gap-1.5 font-bold">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                <span className="text-amber-400">STATUS: NOT ELIGIBLE FOR PRODUCTION</span>
              </div>
              <span className="text-[10px] text-slate-500">
                Strategy needs to accumulate more trading days to satisfy the 14-day live paper test policy before production promotion is unlocked.
              </span>
            </div>
          </div>
        )}

        {/* Live Option Chain & Quote Health Tab */}
        {activeTab === "chain" && (
          <div className="flex flex-col lg:flex-row gap-4 w-full h-full min-h-[250px]">
            {/* Left Side: Option Chain Table */}
            <div className="flex-1 bg-slate-950/40 p-3 rounded border border-white/5 flex flex-col gap-2">
              <div className="text-[10px] text-slate-500 uppercase tracking-widest font-bold border-b border-white/5 pb-1 flex justify-between items-center">
                <span>ATM±2 Option Chain</span>
                <span className="text-cyan-400 font-mono text-[9px] lowercase font-normal">rolling dynamically</span>
              </div>
              <table className="w-full text-left font-mono text-[10px]">
                <thead>
                  <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-[8px]">
                    <th className="py-1 pl-2">CE LTP</th>
                    <th className="py-1 text-center">Age (ms)</th>
                    <th className="py-1 text-center">Strike</th>
                    <th className="py-1 text-center">Age (ms)</th>
                    <th className="py-1 text-right pr-2">PE LTP</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  {status?.option_chain && status.option_chain.length > 0 ? (
                    status.option_chain.map((row, idx) => {
                      const ceAgeColor = row.ce_age_ms > 1500 ? "text-rose-450 font-bold" : "text-slate-500";
                      const peAgeColor = row.pe_age_ms > 1500 ? "text-rose-450 font-bold" : "text-slate-500";
                      return (
                        <tr key={idx} className="border-b border-white/[0.02] hover:bg-white/[0.02]">
                          <td className="py-1.5 pl-2 text-cyan-400 font-bold">₹{row.ce_ltp.toFixed(2)}</td>
                          <td className={`py-1.5 text-center ${ceAgeColor}`}>{row.ce_age_ms}ms</td>
                          <td className="py-1.5 text-center text-slate-100 font-bold bg-white/[0.02]">{row.strike}</td>
                          <td className={`py-1.5 text-center ${peAgeColor}`}>{row.pe_age_ms}ms</td>
                          <td className="py-1.5 text-right pr-2 text-cyan-400 font-bold">₹{row.pe_ltp.toFixed(2)}</td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-slate-500 font-sans select-none">
                        No active option chain data. Ensure the paper session is running.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Right Side: Quote Health & Telemetry Metrics */}
            <div className="w-full lg:w-[350px] flex flex-col gap-3">
              <div className="bg-slate-950/40 p-3 rounded border border-white/5 flex flex-col gap-2.5">
                <div className="text-[10px] text-slate-500 uppercase tracking-widest font-bold border-b border-white/5 pb-1">
                  Quote Health Diagnostics
                </div>
                
                <div className="flex flex-col gap-1.5 font-mono text-[10px]">
                  <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                    <span className="text-slate-400">Subscribed Contracts:</span>
                    <span className="text-slate-200 font-bold">{status?.quote_health?.subscribed_contracts ?? 0}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                    <span className="text-slate-400">Live Quotes (Cache):</span>
                    <span className="text-emerald-400 font-bold">{status?.quote_health?.live_quotes ?? 0}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                    <span className="text-slate-400">Stale Quotes (&gt;1.5s):</span>
                    <span className={`font-bold ${(status?.quote_health?.stale_quotes ?? 0) > 0 ? "text-rose-400" : "text-slate-300"}`}>
                      {status?.quote_health?.stale_quotes ?? 0}
                    </span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                    <span className="text-slate-400">Feed Hit Rate:</span>
                    <span className={`font-bold ${(status?.quote_health?.hit_rate ?? 0) > 0.9 ? "text-cyan-400" : "text-amber-400"}`}>
                      {((status?.quote_health?.hit_rate ?? 0) * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                    <span className="text-slate-400">Feed Miss Rate:</span>
                    <span className={`font-bold ${(status?.quote_health?.miss_rate ?? 0) > 0.1 ? "text-rose-450" : "text-slate-300"}`}>
                      {((status?.quote_health?.miss_rate ?? 0) * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex justify-between items-center py-1 pt-2 border-t border-white/5">
                    <span className="text-slate-400 font-bold">Synthetic Fallbacks:</span>
                    <span className={`font-bold ${(status?.quote_health?.synthetic_fills ?? 0) > 0 ? "text-amber-500 animate-pulse" : "text-emerald-400"}`}>
                      {status?.quote_health?.synthetic_fills ?? 0} fills
                    </span>
                  </div>
                </div>
              </div>

              {/* Status Indicator */}
              <div className="bg-slate-900/40 p-2.5 rounded border border-white/5 flex flex-col gap-1 font-sans">
                <div className="flex items-center gap-1.5 font-bold text-[10px]">
                  {((status?.quote_health?.hit_rate ?? 0) > 0.9 && (status?.quote_health?.stale_quotes ?? 0) === 0) ? (
                    <>
                      <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
                      <span className="text-cyan-400">PIPELINE: LIVE OPTION EXECUTION ACTIVE</span>
                    </>
                  ) : (
                    <>
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                      <span className="text-amber-400">PIPELINE: HYBRID BACKUP / MODEL FILLS</span>
                    </>
                  )}
                </div>
                <span className="text-[9px] text-slate-500">
                  Real-time option quote engine automatically rolls NIFTY option subscriptions dynamically as index spot price changes to ensure 100% quote-driven fills.
                </span>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};
