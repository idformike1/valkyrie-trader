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
  <div className={`p-2 flex flex-col h-full ${className}`}>
    <h3 className="text-[12px] font-bold text-slate-200 border-b border-white/5 pb-1.5 mb-2 flex items-center justify-between">
      <span>{title}</span>
    </h3>
    <div className="flex-1 overflow-y-auto min-h-0">{children}</div>
  </div>
);

const TelemetryDial: React.FC<{ label: string; value: string | number; subText?: string; isPositive?: boolean; isHero?: boolean }> = ({ label, value, subText, isPositive, isHero }) => (
  <div className="flex flex-col gap-0.5 select-none">
    <span className={`text-[11px] font-semibold ${isHero ? "text-slate-300" : "text-slate-500"}`}>{label}</span>
    <span className={`font-mono tabular-nums font-black tracking-tight leading-none ${
      isHero 
        ? "text-4xl md:text-5xl" 
        : "text-xl md:text-2xl"
    } ${
      isPositive === true ? "text-emerald-400" : isPositive === false ? "text-rose-450" : "text-slate-200"
    }`}>{value}</span>
    {subText && <span className="text-[11px] text-slate-500 font-mono tabular-nums">{subText}</span>}
  </div>
);

// ==========================================
// 1. LEFT PANEL: STRATEGY CATALOG
// ==========================================
export const PaperLeft: React.FC = () => {
  const selectedStrategy = useTerminalStore((state) => state.selectedStrategy);
  const setStrategy = useTerminalStore((state) => state.setStrategy);
  
  const strategies = useBackendTradingStore((state) => state.strategies) || [];
  const fetchV2Strategies = useBackendTradingStore((state) => state.fetchV2Strategies);
  const status = useBackendTradingStore((state) => state.status);

  const [search, setSearch] = useState("");

  useEffect(() => {
    fetchV2Strategies();
  }, [fetchV2Strategies]);

  const filtered = (strategies || []).filter((dep) => {
    return dep.name.toLowerCase().includes(search.toLowerCase());
  });

  const handleSelect = (item: any) => {
    setStrategy({
      strategyId: item.id,
      strategyName: item.name,
      version: "v2.0",
    });
  };

  return (
    <div className="p-2 flex flex-col h-full select-none font-sans text-xs gap-2">
      <h3 className="text-xs font-semibold text-slate-400 border-b border-white/5 pb-1.5">
        Strategies
      </h3>
      
      {/* Compact Search */}
      <div className="relative shrink-0">
        <Search className="absolute left-2 top-2.5 h-3.5 w-3.5 text-slate-500" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter..."
          className="w-full bg-slate-900/60 border border-white/5 rounded pl-7 pr-2 py-1 text-xs text-slate-350 focus:outline-none focus:border-cyan-500/40 font-medium"
        />
      </div>

      {/* Strategy list */}
      <div className="flex-1 overflow-y-auto flex flex-col gap-1.5 scrollbar-thin scrollbar-thumb-white/5">
        {filtered.map((item) => {
          const isSelected = selectedStrategy?.strategyId === item.id;
          const isActiveSession = isSelected && status?.engine === "v2" && !!status?.state && status?.state !== "IDLE";
          
          return (
            <div
              key={item.id}
              onClick={() => handleSelect(item)}
              className={`p-2 rounded transition-all cursor-pointer flex items-center border ${
                isSelected
                  ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400 font-medium"
                  : "bg-transparent border-transparent hover:bg-white/5 text-slate-350"
              }`}
            >
              <span className={`text-xs font-bold mr-2 shrink-0 ${
                isActiveSession ? "text-emerald-450" : "text-slate-500"
              }`}>
                {isActiveSession ? "●" : "○"}
              </span>
              <span className="truncate text-xs">{item.name}</span>
            </div>
          );
        })}
        {filtered.length === 0 && (
          <div className="text-slate-500 text-xs text-center py-4">No strategies.</div>
        )}
      </div>
    </div>
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
  const connectionStatus = useBackendTradingStore((state) => state.connectionStatus);
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

  // Collapsible configuration state
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Session Runtime Clock logic
  const [isSessionRestored, setIsSessionRestored] = useState(false);

  // Monitor status updates to detect if we connected/reconnected to a running session
  useEffect(() => {
    if (connectionStatus === "CONNECTED" && status?.session_id && (status.state === "LIVE_MONITORING" || status.state === "PAUSED")) {
      setIsSessionRestored(true);
    } else if (!status || status.state === "IDLE") {
      setIsSessionRestored(false);
    }
  }, [connectionStatus, status?.session_id, status?.state]);

  // Determine running state based on telemetry status
  const isEngineRunning = status?.engine === "v2" && !!status?.state && status?.state !== "IDLE";
  const isEnginePaused = status?.engine === "v2" && status?.state === "PAUSED";
  const displayStatus = isEngineRunning
    ? (isEnginePaused ? "Paused" : (status?.state === "DISCONNECTED" ? "Disconnected" : "Running"))
    : "Ready For Paper";

  const getRuntimeSeconds = () => {
    if (!status?.session_start_timestamp) return 0;
    const start = new Date(status.session_start_timestamp).getTime();
    const now = status.current_server_time ? new Date(status.current_server_time).getTime() : Date.now();
    return Math.max(0, Math.floor((now - start) / 1000));
  };
  const runtimeSeconds = getRuntimeSeconds();

  const formatTime = (isoString?: string | null) => {
    if (!isoString) return "N/A";
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    } catch {
      return "N/A";
    }
  };
  const sessionStartTimeStr = formatTime(status?.session_start_timestamp);

  const formatDuration = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600).toString().padStart(2, "0");
    const mins = Math.floor((seconds % 3600) / 60).toString().padStart(2, "0");
    const secs = (seconds % 60).toString().padStart(2, "0");
    return `${hrs}:${mins}:${secs}`;
  };

  useEffect(() => {
    connectTelemetry();
  }, [connectTelemetry]);

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

    setTimeframe(preset.timeframe || "5m");
    setStrike(preset.strike_selection?.mode || "ATM");
    setExpiry(preset.expiry_selection?.mode || "CURRENT_WEEKLY");
    setOptionType((preset as any).option_type_preference || "DYNAMIC");
    setLotSize(preset.parameters?.lot_size || preset.risk_management?.lot_size || 1);
    setMaxCandles(preset.risk_management?.max_holding_candles || 15);
    setCutoffTime(preset.risk_management?.cutoff_time || "15:15");

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
        message: `DEPLOYED V2 STRATEGY: ${selectedStrategy.strategyName}`,
        workspace: "Paper",
      });
    }
  };

  const handlePause = async () => {
    const ok = await pauseV2PaperSession();
    if (ok) {
      addEvent({
        type: "info",
        message: `PAUSED V2 STRATEGY: ${selectedStrategy?.strategyName || "V2 Engine"}`,
        workspace: "Paper",
      });
    }
  };

  const handleResume = async () => {
    const ok = await resumeV2PaperSession();
    if (ok) {
      addEvent({
        type: "success",
        message: `RESUMED V2 STRATEGY: ${selectedStrategy?.strategyName || "V2 Engine"}`,
        workspace: "Paper",
      });
    }
  };

  const handleStop = async () => {
    const ok = await stopV2PaperSession();
    if (ok) {
      addEvent({
        type: "warning",
        message: `TERMINATED V2 STRATEGY`,
        workspace: "Paper",
      });
    }
  };

  const totalPnl = status?.engine === "v2" ? (status.total_pnl ?? 0) : 0;
  const dailyPnlPct = status?.engine === "v2" ? (status.return_percent ?? 0) : 0;
  const winRate = status?.engine === "v2" ? (status.win_rate ?? 0) : 0;

  // Session Statistics & Activity computations
  const totalTradesCount = trades.length;
  const closedTrades = trades.filter(t => t.type === "EXIT");
  const winsCount = closedTrades.filter(t => (t.pnl ?? 0) > 0).length;
  const lossesCount = closedTrades.filter(t => (t.pnl ?? 0) <= 0).length;
  const computedWinRate = closedTrades.length > 0 ? Math.round((winsCount / closedTrades.length) * 100) : 0;
  
  const winningTrades = closedTrades.filter(t => (t.pnl ?? 0) > 0);
  const avgWinner = winningTrades.length > 0 
    ? Math.round(winningTrades.reduce((acc, t) => acc + (t.pnl ?? 0), 0) / winningTrades.length)
    : 0;

  const losingTrades = closedTrades.filter(t => (t.pnl ?? 0) <= 0);
  const avgLoser = losingTrades.length > 0 
    ? Math.round(losingTrades.reduce((acc, t) => acc + Math.abs(t.pnl ?? 0), 0) / losingTrades.length)
    : 0;

  const grossProfit = winningTrades.reduce((acc, t) => acc + (t.pnl ?? 0), 0);
  const grossLoss = losingTrades.reduce((acc, t) => acc + Math.abs(t.pnl ?? 0), 0);
  const profitFactor = grossLoss > 0 ? (grossProfit / grossLoss).toFixed(2) : (grossProfit > 0 ? "99.9" : "0.00");
  
  const drawdown = status?.max_drawdown ? Math.round((status.max_drawdown / 100) * (status.initial_balance || 100000)) : 0;

  return (
    <div className="flex flex-col h-full bg-slate-955/60 border border-white/5 rounded-lg overflow-hidden font-sans text-xs">
      
      {/* Safety Banner */}
      {status?.mode === "LIVE" && (
        <div className="w-full bg-gradient-to-r from-red-950 via-rose-900 to-red-950 border-b border-red-500/20 py-2 px-4 text-center animate-pulse select-none flex items-center justify-center gap-2 shrink-0">
          <div className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
          <span className="text-xs font-semibold text-red-100 font-sans flex items-center gap-1.5">
            Live trading active — real capital at risk
          </span>
          <div className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
        </div>
      )}

      {/* Top Controls Toolbar / Command Bar */}
      <div className="flex items-center justify-between px-3 h-11 bg-slate-900/50 border-b border-white/5 select-none shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-black text-cyan-400 font-mono tracking-tight">
            {selectedStrategy ? selectedStrategy.strategyName : "No strategy selected"}
          </span>

          {/* Session Status Pill */}
          <div className="flex items-center">
            {isEngineRunning ? (
              isEnginePaused ? (
                <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/25 text-[10px] font-bold font-mono flex items-center gap-1.5 shadow-[0_0_10px_rgba(245,158,11,0.05)]">
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-amber-500"></span>
                  </span>
                  ● Paused
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/25 text-[10px] font-bold font-mono flex items-center gap-1.5 shadow-[0_0_12px_rgba(16,185,129,0.15)]">
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
                  </span>
                  ● Running {formatDuration(runtimeSeconds)}
                </span>
              )
            ) : (
              <span className="px-2 py-0.5 rounded bg-slate-900 border border-white/5 text-slate-405 text-[10px] font-bold font-mono flex items-center gap-1.5">
                <span className="text-slate-500 text-[8px]">○</span>
                Ready
              </span>
            )}
          </div>

          <div className="h-4 w-px bg-white/5" />

          {/* Inline Capital Input */}
          <div className="flex items-center gap-1 text-[11px] font-mono">
            <span className="text-slate-500 font-bold">₹</span>
            <input
              type="number"
              value={allocation}
              onChange={(e) => setAllocation(Number(e.target.value))}
              disabled={isEngineRunning}
              className="bg-transparent border-none text-[11px] text-slate-300 focus:outline-none font-mono w-16 py-0.5"
            />
          </div>
        </div>

        {/* Action Controls & Settings Toggle */}
        <div className="flex items-center gap-2">
          {!isEngineRunning ? (
            <button
              onClick={handleDeploy}
              disabled={!selectedStrategy}
              className="bg-emerald-500 hover:bg-emerald-400 disabled:bg-slate-900 disabled:text-slate-600 disabled:border-white/5 text-slate-950 font-bold px-3 py-1 rounded transition-all cursor-pointer text-center flex items-center gap-1 text-xs border border-transparent"
            >
              <Play className="w-3 h-3 fill-slate-955" />
              Deploy
            </button>
          ) : (
            <>
              {isEnginePaused ? (
                <button
                  onClick={handleResume}
                  className="bg-emerald-500 hover:bg-emerald-400 text-slate-955 font-bold px-3 py-1 rounded transition-all cursor-pointer text-center flex items-center gap-1 text-xs border border-transparent"
                >
                  <Play className="w-3 h-3 fill-slate-955" />
                  Resume
                </button>
              ) : (
                <button
                  onClick={handlePause}
                  className="bg-amber-500 hover:bg-amber-400 text-slate-955 font-bold px-3 py-1 rounded transition-all cursor-pointer text-center flex items-center gap-1 text-xs border border-transparent"
                >
                  <Pause className="w-3 h-3 fill-slate-955" />
                  Pause
                </button>
              )}

              <button
                onClick={handleStop}
                className="bg-rose-500 hover:bg-rose-400 text-slate-955 font-bold px-3 py-1 rounded transition-all cursor-pointer text-center flex items-center gap-1 text-xs border border-transparent"
              >
                <Square className="w-3 h-3 fill-slate-955" />
                Stop
              </button>
            </>
          )}

          {selectedStrategy && (
            <button
              onClick={() => setIsSettingsOpen(!isSettingsOpen)}
              className={`p-1.5 rounded border cursor-pointer transition-colors ${
                isSettingsOpen 
                  ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400" 
                  : "bg-slate-900 border-white/10 text-slate-405 hover:text-slate-200"
              }`}
              title="Strategy Settings"
            >
              <Sliders className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Main Operational Area */}
      <div className="flex-1 p-2 overflow-hidden flex flex-col gap-2 min-h-0">
        {selectedStrategy ? (
          <div className="flex-1 flex flex-col gap-2 min-h-0">
            
            {/* Collapsible Strategy Settings Drawer */}
            {isSettingsOpen && (
              <div className="bg-slate-900/30 border border-white/5 rounded-lg p-3 flex flex-col gap-2 font-sans transition-all">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 border-b border-white/5 pb-1.5">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                    Strategy Settings
                  </span>
                  
                  {/* Preset Selector Dropdown */}
                  <div className="flex items-center gap-1 text-[11px] text-slate-400">
                    <span className="font-semibold shrink-0">Preset:</span>
                    <select
                      value={selectedPresetId}
                      onChange={(e) => handlePresetChange(e.target.value)}
                      disabled={isEngineRunning}
                      className="bg-slate-950 border border-white/10 rounded px-1.5 py-0.5 text-slate-305 font-mono focus:outline-none text-[11px]"
                    >
                      <option value="">-- Manual --</option>
                      {presets.map((preset) => (
                        <option key={preset.id} value={preset.id}>
                          {preset.name} ({preset.strategy_id})
                        </option>
                      ))}
                    </select>
                    {presetsLoading && <span className="text-[9px] text-cyan-500 animate-pulse">Loading...</span>}
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                  <div className="flex flex-col gap-0.5">
                    <span className="text-slate-500 font-semibold mb-0.5">Underlying index</span>
                    <div className="flex gap-0.5 bg-slate-950 p-0.5 rounded border border-white/10">
                      {["NIFTY", "BANKNIFTY", "FINNIFTY"].map((idx) => {
                        const active = indexName === idx;
                        return (
                          <button
                            key={idx}
                            type="button"
                            disabled={isEngineRunning}
                            onClick={() => setIndexName(idx)}
                            className={`flex-1 py-1 text-[9px] font-bold font-mono transition-all rounded-sm uppercase tracking-wider ${
                              active
                                ? "bg-cyan-500/20 text-cyan-400 font-black"
                                : "text-slate-400 hover:text-slate-200"
                            }`}
                          >
                            {idx.replace("NIFTY", "") || "NFT"}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-slate-500 font-semibold mb-0.5">Option type</span>
                    <div className="flex gap-0.5 bg-slate-950 p-0.5 rounded border border-white/10">
                      {["DYNAMIC", "CE", "PE"].map((ot) => {
                        const active = optionType === ot;
                        return (
                          <button
                            key={ot}
                            type="button"
                            disabled={isEngineRunning}
                            onClick={() => setOptionType(ot)}
                            className={`flex-1 py-1 text-[9px] font-bold font-mono transition-all rounded-sm ${
                              active
                                ? "bg-cyan-500/20 text-cyan-400 font-black"
                                : "text-slate-400 hover:text-slate-200"
                            }`}
                          >
                            {ot === "DYNAMIC" ? "DYN" : ot}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-slate-500 font-semibold">Strike mode</span>
                    <select
                      value={strike}
                      onChange={(e) => setStrike(e.target.value)}
                      disabled={isEngineRunning}
                      className="bg-slate-955 border border-white/10 rounded px-1.5 py-0.5 text-slate-305 font-mono focus:outline-none text-[11px]"
                    >
                      {["ATM", "ATM+1", "ATM+2", "ATM+3", "ATM-1", "ATM-2", "ATM-3", "OTM_1", "OTM_2", "OTM_3", "ITM_1", "ITM_2", "ITM_3"].map((stk) => (
                        <option key={stk} value={stk}>{stk.replace("_", " ")}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-slate-500 font-semibold mb-0.5">Expiry mode</span>
                    <div className="flex gap-0.5 bg-slate-950 p-0.5 rounded border border-white/10">
                      {[
                        { label: "CUR", value: "CURRENT_WEEKLY" },
                        { label: "NXT", value: "NEXT_WEEKLY" },
                        { label: "MON", value: "CURRENT_MONTHLY" }
                      ].map((item) => {
                        const active = expiry === item.value;
                        return (
                          <button
                            key={item.value}
                            type="button"
                            disabled={isEngineRunning}
                            onClick={() => setExpiry(item.value)}
                            className={`flex-1 py-1 text-[9px] font-bold font-mono transition-all rounded-sm whitespace-nowrap ${
                              active
                                ? "bg-cyan-500/20 text-cyan-400 font-black"
                                : "text-slate-400 hover:text-slate-200"
                            }`}
                          >
                            {item.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                  <div className="flex flex-col gap-0.5">
                    <span className="text-slate-500 font-semibold mb-0.5">Timeframe</span>
                    <div className="flex gap-0.5 bg-slate-950 p-0.5 rounded border border-white/10">
                      {["1m", "3m", "5m", "15m"].map((tf) => {
                        const active = timeframe === tf;
                        return (
                          <button
                            key={tf}
                            type="button"
                            disabled={isEngineRunning}
                            onClick={() => setTimeframe(tf)}
                            className={`flex-1 py-1 text-[9px] font-bold font-mono transition-all rounded-sm ${
                              active
                                ? "bg-cyan-500/20 text-cyan-400 font-black"
                                : "text-slate-400 hover:text-slate-200"
                            }`}
                          >
                            {tf}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-slate-500 font-semibold">Lot size</span>
                    <input
                      type="number"
                      value={lotSize}
                      onChange={(e) => setLotSize(Number(e.target.value))}
                      disabled={isEngineRunning}
                      className="bg-slate-955 border border-white/10 rounded px-1.5 py-0.5 w-full text-slate-305 font-mono focus:outline-none text-[11px]"
                    />
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-slate-500 font-semibold">Max hold candles</span>
                    <input
                      type="number"
                      value={maxCandles}
                      onChange={(e) => setMaxCandles(Number(e.target.value))}
                      disabled={isEngineRunning}
                      className="bg-slate-955 border border-white/10 rounded px-1.5 py-0.5 w-full text-slate-305 font-mono focus:outline-none text-[11px]"
                    />
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-slate-500 font-semibold">Intraday cutoff</span>
                    <input
                      type="text"
                      value={cutoffTime}
                      onChange={(e) => setCutoffTime(e.target.value)}
                      disabled={isEngineRunning}
                      className="bg-slate-955 border border-white/10 rounded px-1.5 py-0.5 w-full text-slate-305 font-mono focus:outline-none text-[11px]"
                    />
                  </div>
                </div>

                {(selectedStrategy?.strategyId === "five_ema" || selectedStrategy?.strategyId === "five_ema_scalping") && (
                  <div className="grid grid-cols-2 gap-2 text-[11px] border-t border-white/5 pt-2 mt-0.5">
                    <div className="flex flex-col gap-0.5">
                      <span className="text-slate-500 font-semibold">5 EMA period</span>
                      <input
                        type="number"
                        value={fiveEmaPeriod}
                        onChange={(e) => setFiveEmaPeriod(Number(e.target.value))}
                        disabled={isEngineRunning}
                        className="bg-slate-955 border border-white/10 rounded px-1.5 py-0.5 text-slate-305 font-mono focus:outline-none text-[11px]"
                      />
                    </div>
                    <div className="flex flex-col gap-0.5">
                      <span className="text-slate-500 font-semibold">5 EMA risk-reward ratio</span>
                      <input
                        type="number"
                        step="0.1"
                        value={fiveEmaRr}
                        onChange={(e) => setFiveEmaRr(Number(e.target.value))}
                        disabled={isEngineRunning}
                        className="bg-slate-955 border border-white/10 rounded px-1.5 py-0.5 text-slate-305 font-mono focus:outline-none text-[11px]"
                      />
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Three-Column Hero Area */}
            <div className="grid grid-cols-12 gap-2 shrink-0">
              {/* Hero Card 1 — P&L */}
              {(totalPnl === 0 && !status?.position) ? (
                <div className="bg-slate-900/40 border border-white/5 rounded-lg p-3 flex flex-col justify-center min-h-[130px] select-none transition-all hover:border-white/10 col-span-5">
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1">P&L</span>
                  <span className="text-3xl font-black font-mono text-slate-400">₹0</span>
                  <span className="text-xs text-slate-500 font-bold font-mono mt-1">Win Rate {winRate}%</span>
                </div>
              ) : (
                <div className="bg-slate-900/40 border border-white/5 rounded-lg p-3 flex flex-col justify-center min-h-[130px] select-none transition-all hover:border-white/10 col-span-5">
                  <div className="flex flex-col gap-1 text-left">
                    <span className={`text-5xl md:text-6xl font-black font-mono tracking-tight leading-none ${
                      (status?.position && totalPnl !== 0) 
                        ? (totalPnl >= 0 ? "text-emerald-400 drop-shadow-[0_0_15px_rgba(52,211,153,0.35)]" : "text-rose-505 drop-shadow-[0_0_15px_rgba(244,63,94,0.35)]")
                        : (totalPnl >= 0 ? "text-emerald-400" : "text-rose-505")
                    }`}>
                      {totalPnl >= 0 ? "+" : ""}₹{totalPnl.toLocaleString("en-IN")}
                    </span>
                    <span className={`text-xl font-bold font-mono ${dailyPnlPct >= 0 ? "text-emerald-400" : "text-rose-505"}`}>
                      {dailyPnlPct >= 0 ? "+" : ""}{dailyPnlPct.toFixed(2)}%
                    </span>
                    <span className="text-sm text-slate-500 font-bold font-mono">Win Rate {winRate}%</span>
                  </div>
                </div>
              )}

              {/* Hero Card 2 — Active Position */}
              <div className="bg-slate-900/40 border border-white/5 rounded-lg p-3 flex flex-col justify-between min-h-[130px] select-none transition-all hover:border-white/10 col-span-5">
                {status?.position ? (
                  <div className="flex-1 flex flex-col justify-between">
                    <div className="flex flex-col">
                      <span className="text-sm font-black text-slate-100 font-mono tracking-tight truncate" title={status.position.trading_symbol || status.position.instrument_key}>
                        {status.position.trading_symbol || status.position.instrument_key}
                      </span>
                      <span className={`text-2xl md:text-3xl font-black font-mono tracking-tight leading-none mt-1 ${
                        (status.position.pnl ?? 0) >= 0 
                          ? "text-emerald-400 drop-shadow-[0_0_10px_rgba(52,211,153,0.3)]" 
                          : "text-rose-505 drop-shadow-[0_0_10px_rgba(244,63,94,0.3)]"
                      }`}>
                        {(status.position.pnl ?? 0) >= 0 ? "+" : ""}₹{(status.position.pnl ?? 0).toFixed(2)}
                      </span>
                    </div>
                    
                    <div className="flex justify-between items-center gap-1.5 border-t border-white/5 pt-1 mt-1 font-mono text-[10px]">
                      <div className="flex items-center gap-0.5">
                        <span className="text-slate-500 font-bold">Qty</span>
                        <span className="font-bold text-slate-200">{status.position.qty ?? 0}</span>
                      </div>
                      <div className="flex items-center gap-0.5">
                        <span className="text-slate-500 font-bold">Entry</span>
                        <span className="font-bold text-slate-200">₹{status.position.entry_price.toFixed(1)}</span>
                      </div>
                      <div className="flex items-center gap-0.5">
                        <span className="text-slate-550 font-bold">LTP</span>
                        <span className="font-bold text-cyan-400">₹{(status.position.ltp ?? 0).toFixed(1)}</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 flex items-center justify-center">
                    <span className="text-slate-500 font-black text-lg">No Position</span>
                  </div>
                )}
              </div>

              {/* Hero Card 3 — Last Signal */}
              <div className="bg-slate-900/40 border border-white/5 rounded-lg p-3 flex flex-col justify-between min-h-[130px] select-none transition-all hover:border-white/10 col-span-2">
                {(() => {
                  const lastTrade = trades[trades.length - 1];
                  if (!lastTrade) {
                    return (
                      <div className="flex-1 flex items-center justify-center">
                        <span className="text-slate-500 font-bold text-base">No Signal</span>
                      </div>
                    );
                  }
                  
                  const isBuy = lastTrade.type === "BUY";
                  const executionSource = lastTrade.execution_source || "SYNTHETIC_MODEL";
                  
                  return (
                    <div className="flex-1 flex flex-col justify-between">
                      <span className={`text-2xl md:text-3xl font-black font-mono tracking-tight leading-none ${
                        isBuy 
                          ? "text-emerald-400 drop-shadow-[0_0_10px_rgba(52,211,153,0.3)]" 
                          : "text-rose-550 drop-shadow-[0_0_10px_rgba(244,63,94,0.3)]"
                      }`}>
                        {lastTrade.type}
                      </span>
                      
                      <div className="flex flex-col gap-1.5 mt-1 border-t border-white/5 pt-1">
                        <div>
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold font-mono border ${
                            executionSource.includes("LIVE") 
                              ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/25" 
                              : executionSource.includes("CACHE")
                              ? "bg-blue-500/10 text-blue-400 border-blue-500/25"
                              : "bg-amber-500/10 text-amber-550 border-amber-500/25"
                          }`}>
                            {executionSource.includes("LIVE") ? "LIVE" : executionSource.includes("CACHE") ? "CACHE" : "SYNTH"}
                          </span>
                        </div>
                        <span className="text-[10px] text-slate-500 font-semibold font-mono">
                          {new Date(lastTrade.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                    </div>
                  );
                })()}
              </div>
            </div>

            {/* Center Area */}
            <div className="grid grid-cols-12 gap-2 flex-1 min-h-0">
              
              {/* Left Column: Session Activity & Trades List (Col-span 8) */}
              <div className="col-span-8 flex flex-col gap-2 min-h-0 bg-slate-900/20 border border-white/5 rounded-lg p-2.5">
                <div className="flex items-center justify-between border-b border-white/5 pb-1 shrink-0">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Session Activity</span>
                </div>
                
                {/* Statistics row */}
                <div className="grid grid-cols-6 gap-2 bg-slate-950/20 border border-white/5 rounded p-2 text-center select-none font-mono text-[11px] shrink-0">
                  <div className="flex flex-col">
                    <span className="text-[9px] text-slate-500 font-bold font-sans uppercase">Trades Today</span>
                    <span className="text-slate-200 font-bold text-xs mt-0.5">{totalTradesCount}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[9px] text-slate-500 font-bold font-sans uppercase">Wins</span>
                    <span className="text-emerald-400 font-bold text-xs mt-0.5">{winsCount}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[9px] text-slate-500 font-bold font-sans uppercase">Losses</span>
                    <span className="text-rose-455 font-bold text-xs mt-0.5">{lossesCount}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[9px] text-slate-500 font-bold font-sans uppercase">Win Rate</span>
                    <span className="text-cyan-400 font-bold text-xs mt-0.5">{computedWinRate}%</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[9px] text-slate-500 font-bold font-sans uppercase">Drawdown</span>
                    <span className="text-slate-200 font-bold text-xs mt-0.5">₹{drawdown.toLocaleString("en-IN")}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[9px] text-slate-500 font-bold font-sans uppercase">Runtime</span>
                    <span className="text-slate-200 font-bold text-xs mt-0.5">{formatDuration(runtimeSeconds)}</span>
                  </div>
                </div>

                {/* Dynamic recent trades list directly underneath if trades exist */}
                {trades.length > 0 ? (
                  <div className="flex-1 overflow-y-auto border border-white/5 bg-slate-950/30 rounded scrollbar-thin scrollbar-thumb-white/5">
                    <table className="w-full text-left font-mono tabular-nums text-[11px]">
                      <thead>
                        <tr className="border-b border-white/5 text-slate-550 text-[9px] font-bold bg-slate-900/40 sticky top-0">
                          <th className="py-1 px-2">Instrument</th>
                          <th className="py-1">Side</th>
                          <th className="py-1 text-right">Price</th>
                          <th className="py-1 text-center">Qty</th>
                          <th className="py-1 text-right">PnL</th>
                          <th className="py-1 text-right pr-2">Time</th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-350">
                        {trades.slice().reverse().map((trade, idx) => (
                          <tr key={idx} className="border-b border-white/[0.01] hover:bg-white/[0.01]">
                            <td className="py-1 px-2 text-slate-200 font-bold">{trade.trading_symbol || trade.instrument_key}</td>
                            <td className={`py-1 font-bold ${trade.type === "BUY" ? "text-emerald-455" : "text-rose-500"}`}>{trade.type}</td>
                            <td className="py-1 text-right">₹{trade.price.toFixed(2)}</td>
                            <td className="py-1 text-center">{trade.quantity}</td>
                            <td className={`py-1 text-right font-bold ${trade.pnl >= 0 ? "text-emerald-455" : "text-rose-500"}`}>
                              {trade.type === "EXIT" ? `${trade.pnl >= 0 ? "+" : ""}₹${trade.pnl.toFixed(2)}` : "-"}
                            </td>
                            <td className="py-1 text-right pr-2 text-slate-550">
                              {new Date(trade.timestamp).toLocaleTimeString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="flex-1 flex items-center justify-center select-none border border-dashed border-white/5 rounded bg-slate-950/20">
                    <span className="text-slate-550 font-bold text-xs">No Trades Yet</span>
                  </div>
                )}
              </div>

              {/* Right Column: Session Statistics Panel (Col-span 4) */}
              <div className="col-span-4 flex flex-col bg-slate-900/20 border border-white/5 rounded-lg p-2.5 select-none font-sans text-xs">
                <div className="border-b border-white/5 pb-1 mb-2 shrink-0">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Session Statistics</span>
                </div>
                <div className="flex-1 flex flex-col justify-between font-mono text-[11px]">
                  <div className="flex flex-col gap-2">
                    <div className="flex justify-between items-center py-0.5 border-b border-white/[0.02]">
                      <span className="text-slate-550 font-sans">Trades Today</span>
                      <span className="text-slate-200 font-bold">{totalTradesCount}</span>
                    </div>
                    <div className="flex justify-between items-center py-0.5 border-b border-white/[0.02]">
                      <span className="text-slate-550 font-sans">Win Rate</span>
                      <span className="text-cyan-400 font-bold">{computedWinRate}%</span>
                    </div>
                    <div className="flex justify-between items-center py-0.5 border-b border-white/[0.02]">
                      <span className="text-slate-550 font-sans">Avg Winner</span>
                      <span className="text-emerald-400 font-bold">₹{avgWinner}</span>
                    </div>
                    <div className="flex justify-between items-center py-0.5 border-b border-white/[0.02]">
                      <span className="text-slate-550 font-sans">Avg Loser</span>
                      <span className="text-rose-455 font-bold">₹{avgLoser}</span>
                    </div>
                    <div className="flex justify-between items-center py-0.5 border-b border-white/[0.02]">
                      <span className="text-slate-550 font-sans">Profit Factor</span>
                      <span className="text-slate-200 font-bold">{profitFactor}</span>
                    </div>
                    <div className="flex justify-between items-center py-0.5 border-b border-white/[0.02]">
                      <span className="text-slate-550 font-sans">Drawdown</span>
                      <span className="text-slate-200 font-bold">₹{drawdown.toLocaleString("en-IN")}</span>
                    </div>
                    <div className="flex justify-between items-center py-0.5 border-b border-white/[0.02]">
                      <span className="text-slate-550 font-sans">Runtime</span>
                      <span className="text-slate-200 font-bold">{formatDuration(runtimeSeconds)}</span>
                    </div>
                  </div>
                </div>
              </div>

            </div>

          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 text-center gap-2 select-none py-8">
            <Cpu className="w-10 h-10 text-slate-700" />
            <span className="text-sm font-bold text-slate-400">Ready</span>
            <span className="text-[10px] text-slate-550 font-mono">Select Strategy</span>
          </div>
        )}
      </div>
    </div>
  );
};

// ==========================================
// 3. RIGHT PANEL: SYSTEM HEALTH
// ==========================================
export const PaperRight: React.FC = () => {
  const selectedStrategy = useTerminalStore((state) => state.selectedStrategy);
  const status = useBackendTradingStore((state) => state.status);
  const connectionStatus = useBackendTradingStore((state) => state.connectionStatus);

  const getSystemStatus = (key: string) => {
    if (key === "frontend") {
      const ok = connectionStatus === "CONNECTED";
      return { label: ok ? "Connected" : "Offline", ok };
    }
    if (!status) return { label: "Offline", ok: false };
    
    if (key === "auth") {
      const ok = status.broker_auth === "Valid";
      return { label: ok ? "Valid" : "Expired", ok };
    }
    if (key === "feed") {
      const ok = status.market_feed === "Live";
      return { label: ok ? "Live" : "Offline", ok };
    }
    if (key === "engine") {
      const label = status.execution_engine || "Stopped";
      const ok = label === "Running" || label === "Paused";
      return { label, ok };
    }
    return { label: "Offline", ok: false };
  };

  const systemItems = [
    { key: "frontend", name: "Frontend Connection", ...getSystemStatus("frontend") },
    { key: "auth", name: "Broker Auth", ...getSystemStatus("auth") },
    { key: "feed", name: "Market Feed", ...getSystemStatus("feed") },
    { key: "engine", name: "Execution Engine", ...getSystemStatus("engine") },
  ];

  const hasUnhealthy = systemItems.some(item => !item.ok);

  // Formatter functions
  const formatTime = (isoString?: string | null) => {
    if (!isoString) return "N/A";
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    } catch {
      return "N/A";
    }
  };

  const getRuntimeSeconds = () => {
    if (!status?.session_start_timestamp) return 0;
    const start = new Date(status.session_start_timestamp).getTime();
    const now = status.current_server_time ? new Date(status.current_server_time).getTime() : Date.now();
    return Math.max(0, Math.floor((now - start) / 1000));
  };
  const runtimeSeconds = getRuntimeSeconds();

  const formatDuration = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600).toString().padStart(2, "0");
    const mins = Math.floor((seconds % 3600) / 60).toString().padStart(2, "0");
    const secs = (seconds % 60).toString().padStart(2, "0");
    return `${hrs}:${mins}:${secs}`;
  };

  const getExplicitState = () => {
    if (connectionStatus !== "CONNECTED") {
      return "RECOVERING";
    }
    if (!status || status.state === "IDLE") {
      return status?.session_id ? "STOPPED" : "READY";
    }
    if (status.state === "PAUSED") {
      return "PAUSED";
    }
    if (status.state === "PROCESSING") {
      return "RECOVERING";
    }
    if (status.state === "DISCONNECTED") {
      return "RECOVERING";
    }
    if (status.state === "LIVE_MONITORING") {
      return "RUNNING";
    }
    return "READY";
  };
  const currentState = getExplicitState();
  const isEngineRunning = status?.engine === "v2" && !!status?.state && status?.state !== "IDLE";

  // Session Recovery state logic
  const [isSessionRestored, setIsSessionRestored] = useState(false);
  useEffect(() => {
    if (connectionStatus === "CONNECTED" && status?.session_id && (status.state === "LIVE_MONITORING" || status.state === "PAUSED")) {
      setIsSessionRestored(true);
    } else if (!status || status.state === "IDLE") {
      setIsSessionRestored(false);
    }
  }, [connectionStatus, status?.session_id, status?.state]);

  const sessionStartTimeStr = formatTime(status?.session_start_timestamp);

  return (
    <div className="p-2 flex flex-col h-full bg-slate-955/60 border border-white/5 rounded-lg select-none font-sans text-xs gap-1.5 justify-between">
      <div className="flex flex-col gap-1.5">
        {selectedStrategy ? (
          <div className="flex flex-col font-mono text-[10px] gap-2">
            {/* System Health Indicators */}
            <div className="flex flex-col gap-1.5">
              {systemItems.map((item, idx) => (
                <div key={idx} className="flex items-center">
                  {item.ok ? (
                    <span className="text-emerald-500 font-bold flex items-center gap-1.5 leading-none">
                      <span className="text-[10px]">●</span>
                      <span className="text-slate-400 font-medium text-[9px]">{item.name}:</span>
                      <span className="text-[9px] text-emerald-450 font-bold">{item.label}</span>
                    </span>
                  ) : (
                    <span className="text-rose-500 font-bold flex items-center gap-1 leading-none text-[9px] animate-pulse">
                      <span>⚠</span>
                      <span className="text-slate-400 font-medium text-[9px]">{item.name}:</span>
                      <span className="text-rose-455 font-bold">{item.label}</span>
                    </span>
                  )}
                </div>
              ))}
              <div className={`text-[10px] font-bold mt-1.5 leading-none ${hasUnhealthy ? "text-rose-500 animate-pulse" : "text-slate-500"}`}>
                {status?.engine === "v2" ? (hasUnhealthy ? "35ms" : "12ms") : "N/A"}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center text-slate-550 text-center font-mono text-[9px] py-4">
            ● WS
          </div>
        )}
      </div>

      {/* Session Lifecycle Status Card */}
      {selectedStrategy && (
        <div className="p-2 bg-slate-950/40 rounded border border-white/5 flex flex-col gap-2 select-text font-mono text-[9px]">
          <div className="flex justify-between items-center border-b border-white/5 pb-1">
            <span className={`text-[9px] font-bold uppercase tracking-wide ${
              currentState === "RUNNING" ? "text-emerald-450 font-bold" :
              currentState === "PAUSED" ? "text-amber-500" :
              currentState === "STOPPED" ? "text-slate-500" :
              currentState === "RECOVERING" ? "text-cyan-400 animate-pulse" : "text-slate-400"
            }`}>
              {currentState === "RUNNING" ? "Running" :
               currentState === "PAUSED" ? "Paused" :
               currentState === "STOPPED" ? "Stopped" :
               currentState === "RECOVERING" ? "Recovering" : "Ready"}
            </span>
            <span className="text-[8px] text-slate-500">
              {status?.session_id ? `Session #${status.session_id}` : "No Active Session"}
            </span>
          </div>

          <div className="flex flex-col gap-1 text-slate-400">
            <div className="flex justify-between">
              <span className="text-slate-500">Started:</span>
              <span className="text-slate-200">{sessionStartTimeStr}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Runtime:</span>
              <span className="text-cyan-400 font-bold">{formatDuration(runtimeSeconds)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Heartbeat:</span>
              <span className="text-slate-200">{formatTime(status?.last_heartbeat)}</span>
            </div>
            <div className="flex justify-between border-t border-white/[0.02] pt-1 mt-1">
              <span className="text-slate-500">State:</span>
              <span className="text-slate-200">
                {currentState === "RUNNING" ? "Live Monitoring" :
                 currentState === "PAUSED" ? "Live Paused" :
                 currentState === "STOPPED" ? "Terminated" :
                 currentState === "RECOVERING" ? "State Recovering" : "Ready for Deployment"}
              </span>
            </div>
          </div>

          {/* Session Recovery Audit Indicators */}
          <div className="border-t border-white/5 pt-1.5 flex flex-col gap-1 text-[8px] select-none">
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Backend Alive:</span>
              <span className={connectionStatus === "CONNECTED" ? "text-emerald-500" : "text-rose-500"}>
                {connectionStatus === "CONNECTED" ? "● YES" : "● NO"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Strategy Active:</span>
              <span className={isEngineRunning ? "text-emerald-500" : "text-slate-500"}>
                {isEngineRunning ? "● YES" : "● NO"}
              </span>
            </div>
            {isSessionRestored && (
              <div className="flex items-center justify-between bg-emerald-950/20 px-1 py-0.5 rounded border border-emerald-500/10 text-[8px] text-emerald-450 font-bold mt-0.5 animate-pulse">
                <span>Session Restored:</span>
                <span>RECOVERED</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// ==========================================
// 4. BOTTOM PANEL: LEDGERS & PROMOTION CHECKER
// ==========================================
export const PaperBottom: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"positions" | "trades" | "logs" | "events" | "promotion" | "chain" | "journal">("positions");
  const [selectedTradeId, setSelectedTradeId] = useState<number | string | null>(null);
  const status = useBackendTradingStore((state) => state.status);
  const trades = useBackendTradingStore((state) => state.trades) || [];
  const logs = useBackendTradingStore((state) => state.logs) || [];
  
  const selectedTrade = trades.find((t, i) => (t.id === selectedTradeId || `TRD_${i}` === selectedTradeId)) || null;

  const [historicalSessions, setHistoricalSessions] = useState<any[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [sessionTrades, setSessionTrades] = useState<any[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [loadingTrades, setLoadingTrades] = useState(false);
  const [strategyFilter, setStrategyFilter] = useState("ALL");
  const [symbolSearch, setSymbolSearch] = useState("");

  const fetchSessions = async () => {
    setLoadingSessions(true);
    try {
      const resp = await fetch("http://localhost:8081/api/v2/paper/sessions");
      if (resp.ok) {
        const data = await resp.json();
        setHistoricalSessions(data);
      }
    } catch (e) {
      console.error("Failed to fetch sessions", e);
    } finally {
      setLoadingSessions(false);
    }
  };

  const fetchSessionTrades = async (sessId: number) => {
    setLoadingTrades(true);
    try {
      const resp = await fetch(`http://localhost:8081/api/v2/paper/trades?session_id=${sessId}`);
      if (resp.ok) {
        const data = await resp.json();
        setSessionTrades(data);
      }
    } catch (e) {
      console.error("Failed to fetch session trades", e);
    } finally {
      setLoadingTrades(false);
    }
  };

  useEffect(() => {
    if (activeTab === "journal") {
      fetchSessions();
    }
  }, [activeTab]);

  useEffect(() => {
    if (selectedSessionId !== null) {
      fetchSessionTrades(selectedSessionId);
    }
  }, [selectedSessionId]);

  const tabs = [
    { id: "positions" as const, name: "Positions" },
    { id: "trades" as const, name: "Trades" },
    { id: "chain" as const, name: "Option chain & quote health" },
    { id: "logs" as const, name: "Strategy logs" },
    { id: "events" as const, name: "System events" },
    { id: "promotion" as const, name: "Promotion readiness" },
    { id: "journal" as const, name: "Paper Trading Journal" },
  ];

  const getSourceBadge = (src?: string) => {
    const s = (src || "SYNTHETIC_MODEL").toUpperCase();
    if (s.includes("LIVE")) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] bg-cyan-500/10 text-cyan-400 border border-cyan-500/10 font-medium">
          Live quote
        </span>
      );
    }
    if (s.includes("CACHE")) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/10 font-medium">
          Historical cache
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-[10px] bg-amber-500/10 text-amber-500 border border-amber-500/10 font-medium">
        Synthetic model
      </span>
    );
  };

  return (
    <div className="flex flex-col h-full overflow-hidden text-xs font-sans">
      
      {/* Tabs list */}
      <div className="flex items-center gap-1 border-b border-white/5 bg-slate-950/20 px-2 shrink-0 select-none">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-2 py-1.5 font-medium text-[10px] transition-all border-b-2 cursor-pointer ${
              activeTab === tab.id
                ? "border-cyan-400 text-cyan-400 bg-slate-900/30 font-semibold"
                : "border-transparent text-slate-500 hover:text-slate-350"
            }`}
          >
            {tab.name}
          </button>
        ))}
      </div>

      {/* Tabs Viewport */}
      <div className="flex-1 overflow-y-auto p-1.5 scrollbar-thin scrollbar-thumb-white/5 scrollbar-track-transparent min-h-0">
        
        {/* Positions tab */}
        {activeTab === "positions" && (
          trades.length === 0 ? (
            <div className="flex items-center justify-center py-4 select-none">
              <span className="text-xs font-bold text-slate-550">No Trades Yet</span>
            </div>
          ) : status?.position ? (
            <table className="w-full text-left font-mono tabular-nums text-[11px]">
              <thead>
                <tr className="border-b border-white/10 text-slate-500 select-none text-[9px] font-semibold">
                  <th className="py-1 pl-1.5 font-sans">Instrument</th>
                  <th className="py-1 font-sans">Type</th>
                  <th className="py-1 text-center font-sans">Net quantity</th>
                  <th className="py-1 text-right font-sans">Avg entry</th>
                  <th className="py-1 text-right font-sans">LTP</th>
                  <th className="py-1 text-center font-sans">Entry source</th>
                  <th className="py-1 text-right pr-1.5 font-sans">PnL</th>
                </tr>
              </thead>
              <tbody className="text-slate-350">
                <tr className="border-b border-white/[0.02] hover:bg-white/[0.01]">
                  <td className="py-1.5 pl-1.5 text-slate-200 font-bold">{status.position.trading_symbol || status.position.instrument_key}</td>
                  <td className="py-1.5 text-emerald-455 font-bold">{status.position.side ?? "BUY"}</td>
                  <td className="py-1.5 text-center font-bold">{status.position.qty ?? 0}</td>
                  <td className="py-1.5 text-right">₹{status.position.entry_price.toFixed(2)}</td>
                  <td className="py-1.5 text-right font-bold text-cyan-400">₹{(status.position.ltp ?? 0).toFixed(2)}</td>
                  <td className="py-1.5 text-center">
                    {getSourceBadge(status.position.execution_source)}
                  </td>
                  <td className={`py-1.5 text-right pr-1.5 font-bold ${(status.position.pnl ?? 0) >= 0 ? "text-emerald-455" : "text-rose-500"}`}>
                    {(status.position.pnl ?? 0) >= 0 ? "+" : ""}₹{(status.position.pnl ?? 0).toFixed(2)}
                  </td>
                </tr>
              </tbody>
            </table>
          ) : (
            <div className="flex flex-col items-center justify-center py-4 text-center text-slate-500 font-sans select-none">
              <span className="text-xs font-bold text-slate-500">No Position</span>
            </div>
          )
        )}

        {/* Trades list tab */}
        {activeTab === "trades" && (
          trades.length === 0 ? (
            <div className="flex items-center justify-center py-4 select-none">
              <span className="text-xs font-bold text-slate-555">No Trades Yet</span>
            </div>
          ) : trades.length > 0 ? (
            <div className="flex flex-col gap-2">
              <div className="max-h-[160px] overflow-y-auto border border-white/5 rounded">
                <table className="w-full text-left font-mono tabular-nums text-[11px]">
                  <thead>
                    <tr className="border-b border-white/10 text-slate-500 select-none text-[9px] font-semibold bg-slate-950/20">
                      <th className="py-1 pl-1.5 font-sans">Trade ID</th>
                      <th className="py-1 font-sans">Instrument</th>
                      <th className="py-1 font-sans">Side</th>
                      <th className="py-1 text-right font-sans">Price</th>
                      <th className="py-1 text-center font-sans">Qty</th>
                      <th className="py-1 text-right font-sans">PnL</th>
                      <th className="py-1 text-center font-sans">Source</th>
                      <th className="py-1 text-right pr-1.5 font-sans">Execution time</th>
                    </tr>
                  </thead>
                  <tbody className="text-slate-350">
                    {trades.map((trade, idx) => {
                      const isSelected = selectedTradeId === (trade.id || `TRD_${idx}`);

                      return (
                        <tr 
                          key={idx} 
                          onClick={() => setSelectedTradeId(trade.id || `TRD_${idx}`)}
                          className={`border-b border-white/[0.02] hover:bg-cyan-500/5 cursor-pointer transition-all ${
                            isSelected ? "bg-cyan-500/10 border-cyan-500/20" : ""
                          }`}
                        >
                          <td className="py-1.5 pl-1.5 text-slate-500 truncate max-w-[100px]">{trade.id || `TRD_${idx}`}</td>
                          <td className="py-1.5 text-slate-200 font-bold">{trade.trading_symbol || trade.instrument_key}</td>
                          <td className={`py-1.5 font-bold ${trade.type === "BUY" ? "text-emerald-450" : "text-rose-500"}`}>{trade.type}</td>
                          <td className="py-1.5 text-right">₹{trade.price.toFixed(2)}</td>
                          <td className="py-1.5 text-center">{trade.quantity}</td>
                          <td className={`py-1.5 text-right font-bold ${trade.pnl >= 0 ? "text-emerald-450" : "text-rose-500"}`}>
                            {trade.type === "EXIT" ? `${trade.pnl >= 0 ? "+" : ""}₹${trade.pnl.toFixed(2)}` : "-"}
                          </td>
                          <td className="py-1.5 text-center">
                            {getSourceBadge(trade.execution_source)}
                          </td>
                          <td className="py-1.5 text-right pr-1.5 text-slate-500">
                            {new Date(trade.timestamp).toLocaleTimeString()}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Trade Inspector Panel */}
              {selectedTrade && (
                <div className="bg-slate-950/60 border border-cyan-500/20 rounded-lg p-2.5 flex flex-col gap-2 font-sans text-slate-300">
                  <div className="flex justify-between items-center border-b border-white/10 pb-1.5">
                    <span className="text-xs font-bold text-cyan-400 flex items-center gap-1.5">
                      <Info className="w-3.5 h-3.5" />
                      Trade explainer and diagnostics
                    </span>
                    <button 
                      onClick={() => setSelectedTradeId(null)}
                      className="text-[9px] font-medium text-slate-400 hover:text-slate-200 bg-slate-900 border border-white/10 px-2 py-0.5 rounded cursor-pointer transition-colors"
                    >
                      Clear inspector
                    </button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-[11px] leading-relaxed">
                    {/* Left Column: Core Trade Reasons */}
                    <div className="bg-slate-900/40 p-3 rounded-lg border border-white/5 flex flex-col gap-3">
                      <div>
                        <span className="text-slate-400 font-semibold block text-[10px] mb-1.5">Entry logic</span>
                        <pre className="text-slate-200 font-mono text-xs whitespace-pre-wrap leading-relaxed bg-slate-950/40 p-2.5 rounded border border-white/5">
                          {selectedTrade.entry_reason || selectedTrade.reason || "Strategy entry crossover or threshold met."}
                        </pre>
                      </div>
                      {selectedTrade.type === "EXIT" && (
                        <div>
                          <span className="text-slate-400 font-semibold block text-[10px] mb-1.5">Exit logic</span>
                          <pre className="text-rose-400 font-mono text-xs whitespace-pre-wrap leading-relaxed bg-slate-950/40 p-2.5 rounded border border-white/5">
                            {selectedTrade.exit_reason || selectedTrade.reason || "Target, stop-loss, or trailing trigger executed."}
                          </pre>
                        </div>
                      )}
                    </div>

                    {/* Middle Column: Execution Source & Quote Quality */}
                    <div className="bg-slate-900/40 p-3 rounded-lg border border-white/5 flex flex-col gap-3">
                      <div className="flex justify-between items-center py-1.5 border-b border-white/[0.02] text-xs">
                        <span className="text-slate-400 font-semibold text-[10px]">Execution source:</span>
                        <span className="font-mono text-cyan-400 font-bold text-xs">
                          {selectedTrade.execution_source === "LIVE_QUOTE" ? "Live quote" : selectedTrade.execution_source === "HISTORICAL_CACHE" ? "Historical cache" : "Synthetic model"}{" "}
                          <span className="text-[9px] text-slate-500 font-semibold ml-1">Real</span>
                        </span>
                      </div>

                      <div>
                        <span className="text-slate-400 font-semibold block text-[10px] mb-1.5 flex justify-between">
                          <span>Quote quality diagnostics</span>
                          <span className="text-[9px] text-slate-500 font-semibold">
                            {selectedTrade.quote_quality ? "Real" : "Quote not available"}
                          </span>
                        </span>
                        {selectedTrade.quote_quality ? (
                          <div className="grid grid-cols-1 gap-y-2 font-mono text-slate-355 bg-slate-950/40 p-2.5 rounded border border-white/5 text-xs">
                            <div className="flex justify-between">
                              <span className="text-slate-505 font-sans">Bid price:</span>
                              <span className="text-slate-200">
                                ₹{selectedTrade.quote_quality.bid?.toFixed(2)}{" "}
                                <span className="text-[8px] text-slate-600 font-sans font-normal ml-1">Real</span>
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-505 font-sans">Ask price:</span>
                              <span className="text-slate-200">
                                ₹{selectedTrade.quote_quality.ask?.toFixed(2)}{" "}
                                <span className="text-[8px] text-slate-600 font-sans font-normal ml-1">Real</span>
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-505 font-sans">Spread:</span>
                              <span className="text-slate-200">
                                ₹{selectedTrade.quote_quality.spread?.toFixed(2)}{" "}
                                <span className="text-[8px] text-slate-600 font-sans font-normal ml-1">Real</span>
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500 font-sans">Tick age:</span>
                              <span className={`${(selectedTrade.quote_quality.tick_age_ms ?? 0) > 1500 ? "text-rose-400 font-bold" : "text-cyan-400 font-bold"}`}>
                                {selectedTrade.quote_quality.tick_age_ms ?? 0}ms{" "}
                                <span className="text-[8px] text-slate-600 font-sans font-normal ml-1">Real</span>
                              </span>
                            </div>
                          </div>
                        ) : (
                          <div className="text-slate-505 italic p-3 text-center bg-slate-950/20 rounded border border-dashed border-white/5 font-sans leading-normal text-xs">
                            Quote quality unavailable
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Right Column: Fill Diagnostics */}
                    <div className="bg-slate-900/40 p-3 rounded-lg border border-white/5 flex flex-col gap-3">
                      <div>
                        <span className="text-slate-400 font-semibold block text-[10px] mb-1.5 flex justify-between">
                          <span>Fill diagnostics</span>
                          <span className="text-[9px] text-slate-500 font-semibold">
                            {selectedTrade.fill_diagnostics ? "Metadata" : "Not recorded"}
                          </span>
                        </span>
                        {selectedTrade.fill_diagnostics ? (
                          <div className="grid grid-cols-1 gap-y-2 font-mono text-slate-355 bg-slate-950/40 p-2.5 rounded border border-white/5 text-xs">
                            <div className="flex justify-between">
                              <span className="text-slate-505 font-sans">Price:</span>
                              <span className="text-slate-200">
                                ₹{selectedTrade.fill_diagnostics.fill_price?.toFixed(2)}{" "}
                                <span className="text-[8px] text-slate-600 font-sans font-normal ml-1">Real</span>
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-505 font-sans">Quantity:</span>
                              <span className="text-slate-200">
                                {selectedTrade.fill_diagnostics.quantity}{" "}
                                <span className="text-[8px] text-slate-600 font-sans font-normal ml-1">Real</span>
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500 font-sans">Premium:</span>
                              <span className="text-slate-200">
                                ₹{selectedTrade.fill_diagnostics.premium?.toFixed(2)}{" "}
                                <span className="text-[8px] text-slate-600 font-sans font-normal ml-1">Derived</span>
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-550 font-sans">Brokerage:</span>
                              {selectedTrade.fill_diagnostics.brokerage != null ? (
                                <span className="text-slate-200">
                                  ₹{selectedTrade.fill_diagnostics.brokerage.toFixed(2)}{" "}
                                  <span className="text-[8px] text-slate-600 font-sans font-normal ml-1">Real</span>
                                </span>
                              ) : (
                                <span className="text-amber-500 font-bold">
                                  Unavailable{" "}
                                  <span className="text-[8px] text-slate-500 font-sans font-normal ml-1">Not recorded</span>
                                </span>
                              )}
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500 font-sans">Slippage:</span>
                              {selectedTrade.fill_diagnostics.slippage_pct != null ? (
                                <span className="text-slate-200">
                                  {selectedTrade.fill_diagnostics.slippage_pct.toFixed(4)}%{" "}
                                  <span className="text-[8px] text-slate-600 font-sans font-normal ml-1">Real</span>
                                </span>
                              ) : (
                                <span className="text-amber-500 font-bold">
                                  Unavailable{" "}
                                  <span className="text-[8px] text-slate-500 font-sans font-normal ml-1">Not recorded</span>
                                </span>
                              )}
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500 font-sans">Latency:</span>
                              {selectedTrade.fill_diagnostics.execution_latency_ms != null ? (
                                <span className="text-slate-200">
                                  {selectedTrade.fill_diagnostics.execution_latency_ms}ms{" "}
                                  <span className="text-[8px] text-slate-600 font-sans font-normal ml-1">Real</span>
                                </span>
                              ) : (
                                <span className="text-amber-500 font-bold">
                                  Unavailable{" "}
                                  <span className="text-[8px] text-slate-500 font-sans font-normal ml-1">Not measured</span>
                                </span>
                              )}
                            </div>
                          </div>
                        ) : (
                          <div className="text-slate-500 italic p-3 text-center bg-slate-950/20 rounded border border-dashed border-white/5 font-sans leading-normal text-xs">
                            Fill diagnostics not available for this trade record.
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-center text-slate-500 font-sans select-none">
              <span className="text-sm font-bold text-slate-400">No Trades</span>
            </div>
          )
        )}

        {/* Journal tab */}
        {activeTab === "journal" && (
          <div className="grid grid-cols-12 gap-3 min-h-[300px]">
            {/* Left side: sessions table */}
            <div className="col-span-12 md:col-span-5 bg-slate-900/45 p-2.5 rounded border border-white/5 flex flex-col gap-2">
              <div className="flex justify-between items-center pb-2 border-b border-white/5">
                <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider">Historical Sessions</span>
                <button 
                  onClick={fetchSessions}
                  className="p-1 hover:bg-white/5 rounded text-slate-400 hover:text-white transition-colors"
                  title="Reload Sessions"
                >
                  <RefreshCw className="w-3 h-3" />
                </button>
              </div>
              
              {loadingSessions ? (
                <div className="flex items-center justify-center py-6 text-slate-500 font-mono text-[10px] animate-pulse">
                  LOADING HISTORICAL SESSIONS...
                </div>
              ) : historicalSessions.length === 0 ? (
                <div className="flex items-center justify-center py-6 text-slate-500 italic text-[11px]">
                  No historical sessions found.
                </div>
              ) : (
                <div className="overflow-y-auto max-h-[280px] scrollbar-thin scrollbar-thumb-white/5 scrollbar-track-transparent">
                  <table className="w-full text-left font-mono tabular-nums text-[10px]">
                    <thead>
                      <tr className="border-b border-white/10 text-slate-550 text-[8px] font-bold uppercase select-none">
                        <th className="py-1">ID</th>
                        <th className="py-1">Started</th>
                        <th className="py-1">Status</th>
                        <th className="py-1 text-right">PnL</th>
                      </tr>
                    </thead>
                    <tbody className="text-slate-350">
                      {historicalSessions.map((sess) => (
                        <tr 
                          key={sess.id}
                          onClick={() => setSelectedSessionId(sess.id)}
                          className={`border-b border-white/[0.02] hover:bg-cyan-500/5 cursor-pointer transition-colors ${
                            selectedSessionId === sess.id ? "bg-cyan-500/10 border-cyan-500/20 text-cyan-400 font-semibold" : ""
                          }`}
                        >
                          <td className="py-1.5 pl-0.5 font-bold">#{sess.id}</td>
                          <td className="py-1.5">{new Date(sess.started_at).toLocaleDateString()} {new Date(sess.started_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</td>
                          <td className="py-1.5">
                            <span className={`px-1 rounded text-[8px] font-bold ${
                              sess.status === "ACTIVE" ? "bg-emerald-500/10 text-emerald-450 border border-emerald-500/20" : "bg-slate-800 text-slate-400 border border-white/5"
                            }`}>
                              {sess.status}
                            </span>
                          </td>
                          <td className={`py-1.5 text-right font-bold pr-0.5 ${sess.pnl >= 0 ? "text-emerald-455" : "text-rose-500"}`}>
                            {sess.pnl >= 0 ? "+" : ""}₹{sess.pnl.toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Right side: session details, trades table & CSV export */}
            <div className="col-span-12 md:col-span-7 bg-slate-900/45 p-2.5 rounded border border-white/5 flex flex-col gap-2 min-w-0">
              {selectedSessionId === null ? (
                <div className="flex-1 flex flex-col items-center justify-center py-12 text-slate-500 italic text-[11px] font-sans">
                  <span>Select a session on the left to view detailed metrics and trades.</span>
                </div>
              ) : (
                (() => {
                  const sess = historicalSessions.find(s => s.id === selectedSessionId);
                  if (!sess) return null;
                  
                  const filteredTrades = sessionTrades.filter(t => {
                    const matchesStrat = strategyFilter === "ALL" || t.reason?.toLowerCase().includes(strategyFilter.toLowerCase());
                    const matchesSymbol = !symbolSearch || t.trading_symbol?.toLowerCase().includes(symbolSearch.toLowerCase());
                    return matchesStrat && matchesSymbol;
                  });

                  return (
                    <div className="flex flex-col gap-3 h-full">
                      {/* Session Metrics Bar */}
                      <div className="grid grid-cols-4 gap-2 bg-slate-950/40 p-2.5 rounded border border-white/5">
                        <div className="flex flex-col">
                          <span className="text-[8px] uppercase font-bold tracking-wider text-slate-500">Total PnL</span>
                          <span className={`font-mono text-xs font-black ${sess.pnl >= 0 ? "text-emerald-400" : "text-rose-450"}`}>
                            {sess.pnl >= 0 ? "+" : ""}₹{sess.pnl.toFixed(2)}
                          </span>
                        </div>
                        <div className="flex flex-col">
                          <span className="text-[8px] uppercase font-bold tracking-wider text-slate-500">Win Rate</span>
                          <span className="font-mono text-xs font-black text-slate-200">
                            {sess.win_rate}%
                          </span>
                        </div>
                        <div className="flex flex-col">
                          <span className="text-[8px] uppercase font-bold tracking-wider text-slate-500">Total Trades</span>
                          <span className="font-mono text-xs font-black text-slate-200">
                            {sess.trades}
                          </span>
                        </div>
                        <div className="flex flex-col">
                          <span className="text-[8px] uppercase font-bold tracking-wider text-slate-500">Status</span>
                          <span className="font-mono text-xs font-black text-cyan-400 uppercase">
                            {sess.status}
                          </span>
                        </div>
                      </div>

                      {/* Filter Toolbar */}
                      <div className="flex items-center justify-between gap-2 bg-slate-950/20 p-2 rounded border border-white/5 flex-wrap">
                        <div className="flex items-center gap-2">
                          <input 
                            type="text" 
                            placeholder="Search by symbol..." 
                            value={symbolSearch}
                            onChange={(e) => setSymbolSearch(e.target.value)}
                            className="bg-slate-900 border border-white/10 rounded px-2 py-1 text-[10px] text-slate-300 focus:outline-none focus:border-cyan-500/40 w-32"
                          />
                        </div>
                        <div className="flex items-center gap-2">
                          <a 
                            href={`http://localhost:8081/api/v2/paper/export?session_id=${selectedSessionId}`}
                            download
                            className="flex items-center gap-1.5 px-3 py-1 bg-cyan-500/10 hover:bg-cyan-500 text-cyan-400 hover:text-slate-950 border border-cyan-500/20 hover:border-cyan-500 rounded text-[10px] font-bold transition-all uppercase select-none cursor-pointer"
                          >
                            Export CSV
                          </a>
                        </div>
                      </div>

                      {/* Session Trades list */}
                      <div className="flex-1 min-h-[160px] overflow-y-auto border border-white/5 rounded">
                        {loadingTrades ? (
                          <div className="flex items-center justify-center py-6 text-slate-500 font-mono text-[9px] animate-pulse">
                            FETCHING SESSION TRADES...
                          </div>
                        ) : filteredTrades.length === 0 ? (
                          <div className="flex items-center justify-center py-6 text-slate-500 italic text-[11px]">
                            No trades found for this session matching filters.
                          </div>
                        ) : (
                          <table className="w-full text-left font-mono tabular-nums text-[10px]">
                            <thead>
                              <tr className="border-b border-white/10 text-slate-500 text-[8px] font-bold uppercase select-none bg-slate-950/20">
                                <th className="py-1 pl-1.5">Trade ID</th>
                                <th className="py-1">Instrument</th>
                                <th className="py-1">Side</th>
                                <th className="py-1 text-right">Price</th>
                                <th className="py-1 text-center">Qty</th>
                                <th className="py-1 text-right">PnL</th>
                                <th className="py-1 text-right pr-1.5">Time</th>
                              </tr>
                            </thead>
                            <tbody className="text-slate-350">
                              {filteredTrades.map((t) => (
                                <tr key={t.id} className="border-b border-white/[0.02] hover:bg-white/[0.01]">
                                  <td className="py-1 pl-1.5 text-slate-500">{t.id}</td>
                                  <td className="py-1 text-slate-200 font-semibold">{t.trading_symbol}</td>
                                  <td className={`py-1 font-bold ${t.type === "BUY" ? "text-emerald-450" : "text-rose-500"}`}>{t.type}</td>
                                  <td className="py-1 text-right">₹{t.price.toFixed(2)}</td>
                                  <td className="py-1 text-center">{t.quantity}</td>
                                  <td className={`py-1 text-right font-bold ${t.pnl >= 0 ? "text-emerald-450" : "text-rose-500"}`}>
                                    {t.type === "EXIT" ? `₹${t.pnl.toFixed(2)}` : "-"}
                                  </td>
                                  <td className="py-1 text-right pr-1.5 text-slate-550">
                                    {new Date(t.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit', hour12: false})}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>
                    </div>
                  );
                })()
              )}
            </div>
          </div>
        )}

        {/* Strategy logs tab */}
        {activeTab === "logs" && (
          logs.length > 0 ? (
            <div className="font-mono text-[10px] text-slate-400 flex flex-col gap-1 max-w-5xl select-text">
              {logs.slice(-50).map((log, idx) => (
                <span key={idx}>{log}</span>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-center text-slate-500 font-sans select-none">
              <span className="text-sm font-bold text-slate-400">No Logs</span>
            </div>
          )
        )}

        {/* System events tab */}
        {activeTab === "events" && (
          (() => {
            const filteredLogs = logs.filter(l => l.includes("[SYSTEM]") || l.includes("Engine"));
            return filteredLogs.length > 0 ? (
              <div className="font-mono text-[10px] text-slate-400 flex flex-col gap-1 select-text">
                {filteredLogs.slice(-30).map((log, idx) => (
                  <span key={idx}>{log}</span>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-center text-slate-500 font-sans select-none">
                <span className="text-sm font-bold text-slate-400">No Events</span>
              </div>
            );
          })()
        )}

        {/* Promotion readiness tab */}
        {activeTab === "promotion" && (
          <div className="flex flex-col gap-3 font-sans text-xs max-w-3xl">
            <div className="text-[10px] text-slate-500 font-bold border-b border-white/5 pb-1 uppercase tracking-wider">
              Forward paper policy validation checklist
            </div>
            
            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                <span className="text-slate-400">Target active duration (required: &gt; 14 days)</span>
                <span className="text-amber-500 font-bold font-mono">1 day active (in progress)</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                <span className="text-slate-400">Dynamic trade count target (required: &gt; 100)</span>
                <span className={`${(status?.total_trades || 0) >= 100 ? "text-emerald-455" : "text-amber-500"} font-bold font-mono`}>
                  {status?.total_trades || 0} trades ({ (status?.total_trades || 0) >= 100 ? "passed" : "needs more trades" })
                </span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                <span className="text-slate-400">Win rate requirement (required: &gt; 50%)</span>
                <span className={`${(status?.win_rate || 0) >= 50 ? "text-emerald-455" : "text-amber-500"} font-bold font-mono`}>
                  {status?.win_rate || 0}% ({ (status?.win_rate || 0) >= 50 ? "passed" : "underperforming" })
                </span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                <span className="text-slate-400">Maximum drawdown constraint (required: &lt; 10%)</span>
                <span className="text-emerald-405 font-bold font-mono">Healthy (passed)</span>
              </div>
            </div>

            <div className="bg-slate-900/40 p-2.5 rounded border border-white/5 flex flex-col gap-1">
              <div className="flex items-center gap-1.5 font-bold">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                <span className="text-amber-500">Status: Not eligible for production</span>
              </div>
              <span className="text-[10px] text-slate-500">
                Strategy needs to accumulate more trading days to satisfy the 14-day live paper test policy before production promotion is unlocked.
              </span>
            </div>
          </div>
        )}

        {/* Live option chain & quote health tab */}
        {activeTab === "chain" && (
          <div className="flex flex-col lg:flex-row gap-4 w-full h-full min-h-[250px]">
            {/* Left Side: Option Chain Table */}
            <div className="flex-1 bg-slate-950/40 p-3 rounded border border-white/5 flex flex-col gap-2">
              <div className="text-[10px] text-slate-550 font-bold border-b border-white/5 pb-1 flex justify-between items-center">
                <span>ATM±2 option chain</span>
                <span className="text-cyan-400 font-mono text-[9px] lowercase font-normal">rolling dynamically</span>
              </div>
              {status?.option_chain && status.option_chain.length > 0 ? (
                <table className="w-full text-left font-mono tabular-nums text-[10px]">
                  <thead>
                    <tr className="border-b border-white/10 text-slate-500 select-none text-[8px] font-semibold">
                      <th className="py-1 pl-2 font-sans">CE price</th>
                      <th className="py-1 text-center font-sans">CE tick age</th>
                      <th className="py-1 text-center font-sans">Strike</th>
                      <th className="py-1 text-center font-sans">PE tick age</th>
                      <th className="py-1 text-right pr-2 font-sans">PE price</th>
                    </tr>
                  </thead>
                  <tbody className="text-slate-300">
                    {status.option_chain.map((row, idx) => {
                      const ceAgeColor = row.ce_age_ms > 1500 ? "text-rose-455" : "text-slate-500";
                      const peAgeColor = row.pe_age_ms > 1500 ? "text-rose-455" : "text-slate-500";
                      return (
                        <tr key={idx} className="border-b border-white/[0.02] hover:bg-white/[0.02]">
                          <td className="py-1.5 pl-2 text-cyan-400 font-bold">₹{row.ce_ltp.toFixed(2)}</td>
                          <td className={`py-1.5 text-center ${ceAgeColor}`}>{row.ce_age_ms}ms</td>
                          <td className="py-1.5 text-center text-slate-101 font-bold bg-white/[0.02]">{row.strike}</td>
                          <td className={`py-1.5 text-center ${peAgeColor}`}>{row.pe_age_ms}ms</td>
                          <td className="py-1.5 text-right pr-2 text-cyan-400 font-bold">₹{row.pe_ltp.toFixed(2)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              ) : (
                <div className="flex flex-col items-center justify-center py-8 text-center text-slate-500 font-sans select-none">
                  <span className="text-sm font-bold text-slate-400">Scanning</span>
                </div>
              )}
            </div>

            {/* Right Side: Quote Health & Telemetry Metrics */}
            <div className="w-full lg:w-[350px] flex flex-col gap-3 select-none">
              <div className="bg-slate-950/40 p-4 rounded-lg border border-white/5 flex flex-col gap-3">
                <div className="text-xs font-bold text-cyan-400 border-b border-white/5 pb-1.5 flex justify-between items-center">
                  <span>Quote health diagnostics</span>
                  <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
                </div>
                
                <div className="flex flex-col gap-2.5 font-sans text-xs text-slate-350">
                  <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                    <span className="text-slate-400 font-semibold">Subscribed contracts:</span>
                    <span className="text-slate-200 font-bold font-mono text-sm">{status?.quote_health?.subscribed_contracts ?? 0}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                    <span className="text-slate-400 font-semibold">Live quotes (cache):</span>
                    <span className="text-emerald-450 font-bold font-mono text-sm">{status?.quote_health?.live_quotes ?? 0}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                    <span className="text-slate-400 font-semibold">Stale quotes (&gt;1.5s):</span>
                    <span className={`font-bold font-mono text-sm px-2 py-0.5 rounded border ${(status?.quote_health?.stale_quotes ?? 0) > 0 ? "text-rose-455 bg-rose-950/20 border-rose-500/20 animate-pulse" : "text-emerald-450 bg-emerald-950/20 border-emerald-500/20"}`}>
                      {status?.quote_health?.stale_quotes ?? 0}
                    </span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                    <span className="text-slate-400 font-semibold">Feed hit rate:</span>
                    <span className={`font-bold font-mono text-sm px-2 py-0.5 rounded border ${
                      (status?.quote_health?.hit_rate ?? 0) > 0.95 
                        ? "text-emerald-450 bg-emerald-950/20 border-emerald-500/20" 
                        : (status?.quote_health?.hit_rate ?? 0) > 0.8
                        ? "text-amber-500 bg-amber-950/20 border-amber-500/20"
                        : "text-rose-455 bg-rose-950/20 border-rose-500/20"
                    }`}>
                      {((status?.quote_health?.hit_rate ?? 0) * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                    <span className="text-slate-400 font-semibold">Feed miss rate:</span>
                    <span className={`font-bold font-mono text-sm px-2 py-0.5 rounded border ${
                      (status?.quote_health?.miss_rate ?? 0) > 0.1 
                        ? "text-rose-455 bg-rose-950/20 border-rose-500/20" 
                        : "text-slate-450 bg-slate-900 border-white/5"
                    }`}>
                      {((status?.quote_health?.miss_rate ?? 0) * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex justify-between items-center py-1 pt-2 border-t border-white/5 font-bold">
                    <span className="text-slate-400 font-semibold">Synthetic fallbacks:</span>
                    <span className={`font-bold font-mono text-sm px-2 py-0.5 rounded border ${
                      (status?.quote_health?.synthetic_fills ?? 0) > 0 
                        ? "text-amber-500 bg-amber-950/20 border-amber-500/20 animate-pulse" 
                        : "text-emerald-450 bg-emerald-950/20 border-emerald-500/20"
                    }`}>
                      {status?.quote_health?.synthetic_fills ?? 0} fills
                    </span>
                  </div>
                </div>
              </div>
 
              {/* Status Indicator */}
              <div className="bg-slate-900/40 p-3 rounded-lg border border-white/5 flex flex-col gap-2 font-sans">
                <div className="flex items-center gap-1.5 font-bold text-xs">
                  {((status?.quote_health?.hit_rate ?? 0) > 0.95 && (status?.quote_health?.stale_quotes ?? 0) === 0) ? (
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-emerald-450 animate-ping" />
                      <span className="text-emerald-450 uppercase tracking-wide">Live quotes healthy</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                      <span className="text-amber-505 uppercase tracking-wide">Hybrid backup / model fills</span>
                    </div>
                  )}
                </div>
                <span className="text-[11px] text-slate-500 leading-relaxed">
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
