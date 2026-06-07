"use client";

import React, { useState, useEffect, useRef } from "react";
import { createChart, IChartApi, ISeriesApi, UTCTimestamp, CandlestickSeries, AreaSeries, createSeriesMarkers } from "lightweight-charts";
import { 
  Play, Pause, RotateCcw, ChevronLeft, ChevronRight, Activity, Terminal, Shield, Cpu, RefreshCw, BarChart2,
  TrendingUp, Layers, Server, Settings, Zap, ArrowUpRight, ArrowDownRight,
  Sliders, Search, Plus, Trash2, SlidersHorizontal, Lock, CheckCircle2, 
  AlertTriangle, Filter, Calendar, DollarSign, Percent, Grid, AlertCircle,
  X
} from "lucide-react";
import { useTerminalStore } from "@/store/useTerminalStore";
import { useEventStore } from "@/store/useEventStore";
import { useBacktestStore, V2Config } from "@/store/useBacktestStore";
import { useBackendTradingStore } from "@/services/tradingQueries";
import { useThemeStore } from "@/store/useThemeStore";

import { DataTable, ColumnDef } from "@/design-system/DataTable";
import { StatusBadge } from "@/design-system/StatusBadge";
import { EmptyState } from "@/design-system/EmptyState";
import { Panel } from "@/design-system/Panel";
import { SegmentedTabs } from "@/design-system/SegmentedTabs";
import { FormField, FormSection } from "@/design-system/FormField";

const WorkspacePanel = Panel;

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
    id: "heikin_ashi_v2",
    name: "Heikin Ashi V2 Strategy",
    version: "v2.0",
    status: "Validated",
    promotionState: "Live Approved",
    createdDate: "2026-06-05",
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
  const fetchStrategiesMetadata = useBacktestStore((state) => state.fetchStrategiesMetadata);
  const activeStrategyMetadata = useBacktestStore((state) => state.activeStrategyMetadata);

  // Presets Store Hooks
  const presets = useBacktestStore((state) => state.presets);
  const presetsLoading = useBacktestStore((state) => state.presetsLoading);
  const fetchPresets = useBacktestStore((state) => state.fetchPresets);
  const createPreset = useBacktestStore((state) => state.createPreset);
  const deletePreset = useBacktestStore((state) => state.deletePreset);
  const duplicatePreset = useBacktestStore((state) => state.duplicatePreset);
  const loadPreset = useBacktestStore((state) => state.loadPreset);

  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState<string>("All");

  // Save current preset form state
  const [showSaveForm, setShowSaveForm] = useState(false);
  const [newPresetName, setNewPresetName] = useState("");
  const [newPresetNotes, setNewPresetNotes] = useState("");
  const [newPresetTags, setNewPresetTags] = useState("");

  useEffect(() => {
    fetchStrategiesMetadata();
    fetchPresets();
  }, [fetchStrategiesMetadata, fetchPresets]);

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

  const handleLoadPreset = (preset: any) => {
    loadPreset(preset);
    // Also update selectedStrategy in useTerminalStore so the UI lists match
    let matchedRepo = AVAILABLE_STRATEGIES.find(s => {
      if (preset.strategy_id === "five_ema") return s.id === "five_ema_scalping";
      if (preset.strategy_id === "ema") return s.id === "EMA";
      if (preset.strategy_id === "heikin_ashi") return s.id === "heikin_ashi_gar";
      if (preset.strategy_id === "heikin_ashi_v2") return s.id === "heikin_ashi_v2";
      return s.id === preset.strategy_id;
    });
    if (matchedRepo) {
      setStrategy({
        strategyId: matchedRepo.id,
        strategyName: matchedRepo.name,
        version: matchedRepo.version
      });
    }
  };

  const handleSaveCurrent = async () => {
    if (!newPresetName.trim()) return;
    
    // Map frontend strategy name to backend ID
    let strategy_id = v2Config.strategy_name;
    if (v2Config.strategy_name === "five_ema_scalping") strategy_id = "five_ema";
    if (v2Config.strategy_name === "EMA") strategy_id = "ema";
    if (v2Config.strategy_name === "heikin_ashi_gar") strategy_id = "heikin_ashi";
    if (v2Config.strategy_name === "heikin_ashi_v2") strategy_id = "heikin_ashi_v2";

    const presetPayload = {
      name: newPresetName,
      strategy_id,
      parameters: v2Config.strategy_params,
      risk_management: {
        target_type: v2Config.strategy_name === "five_ema_scalping" ? "percent" : "none",
        target_value: v2Config.strategy_params.five_ema_rr || 0.0,
        stop_loss_type: v2Config.strategy_name === "five_ema_scalping" ? "percent" : "none",
        stop_loss_value: 1.0,
        max_holding_candles: v2Config.strategy_params.max_candles || 10,
        cutoff_time: v2Config.strategy_params.cut_off_time || "15:25"
      },
      strike_selection: { mode: v2Config.strike_mode },
      expiry_selection: { mode: v2Config.expiry_mode },
      timeframe: v2Config.timeframe,
      notes: newPresetNotes,
      tags: newPresetTags.split(",").map(t => t.trim()).filter(Boolean)
    };

    await createPreset(presetPayload);
    
    // Reset form
    setNewPresetName("");
    setNewPresetNotes("");
    setNewPresetTags("");
    setShowSaveForm(false);
  };

  const handleDuplicatePreset = (preset: any) => {
    const name = prompt("Enter a name for the duplicated preset:", `${preset.name} Copy`);
    if (name && name.trim()) {
      duplicatePreset(preset.id, name.trim());
    }
  };

  const handleDeletePreset = (presetId: string) => {
    if (confirm("Are you sure you want to delete this preset?")) {
      deletePreset(presetId);
    }
  };

  const filtered = AVAILABLE_STRATEGIES.filter((str) => {
    const matchesSearch = str.name.toLowerCase().includes(search.toLowerCase());
    const matchesFilter = activeFilter === "All" || str.status === activeFilter;
    return matchesSearch && matchesFilter;
  });

  return (
    <div className="flex flex-col gap-3 h-full overflow-y-auto pr-1 pb-4 scrollbar-thin scrollbar-thumb-white/5">
      <WorkspacePanel title="Strategy Repository" className="shrink-0">
        <div className="flex flex-col gap-2 font-sans vdl-body">
          <div className="flex flex-col gap-1.5">
            <div className="relative">
              <select
                value={selectedStrategy?.strategyId || ""}
                onChange={(e) => {
                  const val = e.target.value;
                  const found = AVAILABLE_STRATEGIES.find((str) => str.id === val);
                  if (found) {
                    handleSelect(found);
                  }
                }}
                className="w-full bg-card  rounded px-2.5 py-1.5 vdl-body text-slate-200 focus:outline-none focus:border-cyan-neon font-sans font-semibold cursor-pointer appearance-none"
              >
                <option value="" disabled>-- Select Strategy --</option>
                {AVAILABLE_STRATEGIES.map((str) => (
                  <option key={str.id} value={str.id}>
                    {str.name} ({str.version})
                  </option>
                ))}
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-slate-400">
                <SlidersHorizontal className="w-3 h-3" />
              </div>
            </div>
            {selectedStrategy && (
              <div className="bg-card/45 rounded p-2 flex flex-col gap-1 mt-1">
                <div className="flex justify-between items-center vdl-body">
                  <span className="text-slate-500">Status:</span>
                  <span className={`px-1.5 py-0.5 rounded vdl-body font-semibold${
                    selectedStrategy.strategyId === "five_ema_scalping" ? "bg-amber-950/40 text-amber-400" : "bg-emerald-950/40 text-emerald-400"
                  }`}>
                    {selectedStrategy.strategyId === "five_ema_scalping" ? "Testing" : "Validated"}
                  </span>
                </div>
                <div className="flex justify-between items-center vdl-body">
                  <span className="text-slate-500">Promotion State:</span>
                  <span className="text-slate-300 font-sans font-semibold vdl-body text-cyan-neon">
                    {selectedStrategy.strategyId === "five_ema_scalping" ? "Paper Approved" : "Live Approved"}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </WorkspacePanel>

      {/* Preset Library Card */}
      <WorkspacePanel title="Preset Library" className="shrink-0">
        <div className="flex flex-col gap-2.5 font-sans vdl-body">
          {/* Header Action: Save Current Configuration */}
          {!showSaveForm ? (
            <button
              onClick={() => setShowSaveForm(true)}
              className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded vdl-body font-semibold transition-all border border-cyan-500/20 bg-cyan-950/20 text-cyan-400 hover:bg-cyan-950/40 hover:border-cyan-500/40 cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Save Current Config as Preset</span>
            </button>
          ) : (
            <div className="bg-card rounded p-2.5 flex flex-col gap-2">
              <span className="vdl-body font-semibold text-cyan-400">Save Strategy Preset</span>
              <input
                type="text"
                value={newPresetName}
                onChange={(e) => setNewPresetName(e.target.value)}
                placeholder="Preset Name (e.g. 5 EMA Aggressive)"
                className="w-full bg-card  rounded px-2 py-1 vdl-body text-slate-300 focus:outline-none focus:border-cyan-500/40"
              />
              <input
                type="text"
                value={newPresetNotes}
                onChange={(e) => setNewPresetNotes(e.target.value)}
                placeholder="Notes/Description"
                className="w-full bg-card  rounded px-2 py-1 vdl-body text-slate-300 focus:outline-none focus:border-cyan-500/40"
              />
              <input
                type="text"
                value={newPresetTags}
                onChange={(e) => setNewPresetTags(e.target.value)}
                placeholder="Tags (comma-separated)"
                className="w-full bg-card  rounded px-2 py-1 vdl-body text-slate-300 focus:outline-none focus:border-cyan-500/40"
              />
              <div className="flex gap-2 justify-end mt-1 vdl-body font-semibold">
                <button
                  onClick={() => setShowSaveForm(false)}
                  className="px-2 py-1 rounded bg-card  text-slate-400 hover:text-slate-200 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveCurrent}
                  className="px-2 py-1 rounded bg-cyan-950 border border-cyan-800/30 text-cyan-400 hover:bg-cyan-900/30 cursor-pointer"
                >
                  Save Preset
                </button>
              </div>
            </div>
          )}

          {/* Presets List */}
          {presetsLoading ? (
            <div className="flex items-center justify-center py-4 text-slate-500 gap-1.5 vdl-body">
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              <span>Loading presets...</span>
            </div>
          ) : presets.length === 0 ? (
            <div className="text-center py-4 text-slate-500 vdl-body">
              No presets available. Save one above.
            </div>
          ) : (
            <div className="max-h-[180px] overflow-y-auto flex flex-col gap-1.5 pr-1 scrollbar-thin scrollbar-thumb-white/5">
              {presets.map((preset) => (
                <div
                  key={preset.id}
                  className="p-2 bg-card/45 rounded flex flex-col gap-1.5 hover:border-subtle transition-all"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <span className="font-semibold vdl-body text-slate-200 block truncate max-w-[120px]">
                        {preset.name}
                      </span>
                      <span className="vdl-body text-cyan-500/80 font-mono font-semibold">
                        {preset.strategy_id === "five_ema" ? "5 EMA" : preset.strategy_id === "ema" ? "EMA Trend" : "Heikin Ashi"} ({preset.timeframe})
                      </span>
                    </div>
                    {/* Action buttons */}
                    <div className="flex gap-1">
                      <button
                        onClick={() => handleLoadPreset(preset)}
                        title="Load Preset"
                        className="p-1 rounded bg-emerald-950/40 border border-emerald-800/30 text-emerald-400 hover:bg-emerald-900/40 hover:text-emerald-300 transition-all cursor-pointer"
                      >
                        <Zap className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => handleDuplicatePreset(preset)}
                        title="Duplicate Preset"
                        className="p-1 rounded bg-cyan-950/40 border border-cyan-800/30 text-cyan-400 hover:bg-cyan-900/40 hover:text-cyan-300 transition-all cursor-pointer"
                      >
                        <Layers className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => handleDeletePreset(preset.id)}
                        title="Delete Preset"
                        className="p-1 rounded bg-rose-950/40 border border-rose-800/30 text-rose-400 hover:bg-rose-900/40 hover:text-rose-300 transition-all cursor-pointer"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>

                  {preset.notes && (
                    <p className="vdl-body text-slate-400 leading-normal italic line-clamp-1">
                      {preset.notes}
                    </p>
                  )}

                  {preset.tags && preset.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {preset.tags.map((tag) => (
                        <span
                          key={tag}
                          className="text-[7px] font-mono font-semibold text-slate-400 bg-card px-1  rounded"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </WorkspacePanel>

      <WorkspacePanel title="Strategy Details" className="flex-1">
        {activeStrategyMetadata ? (
          <div className="flex flex-col gap-4 text-slate-300 font-sans vdl-body pb-2">
            {/* General Specs */}
            <div className="bg-card/40 rounded p-3 flex flex-col gap-2.5">
              <div className="flex justify-between items-start gap-1">
                <div>
                  <h4 className="text-[12px] font-semibold text-cyan-400">{activeStrategyMetadata.name}</h4>
                  <span className="vdl-body text-slate-400 font-medium bg-card px-1.5 py-0.5  rounded mt-1 inline-block">
                    {activeStrategyMetadata.category}
                  </span>
                </div>
                <span className={`px-2 py-0.5 rounded vdl-body font-semibold shrink-0${
                  activeStrategyMetadata.risk_level === "High" ? "bg-rose-950/40 text-rose-400 border border-rose-800/20" :
                  activeStrategyMetadata.risk_level === "Medium" ? "bg-amber-950/40 text-amber-400 border border-amber-800/20" :
                  "bg-emerald-950/40 text-emerald-400 border border-emerald-800/20"
                }`}>
                  {activeStrategyMetadata.risk_level} Risk
                </span>
              </div>
              
              <p className="text-slate-400 leading-relaxed">{activeStrategyMetadata.description}</p>
              
              <div className="grid grid-cols-2 gap-2 border-t pt-2.5 vdl-body">
                <div className="flex flex-col">
                  <span className="text-slate-500 font-semibold vdl-body">Market regime</span>
                  <span className="text-slate-300 mt-0.5 font-medium">{activeStrategyMetadata.market_type}</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-slate-500 font-semibold vdl-body">Trade frequency</span>
                  <span className="text-slate-300 mt-0.5 font-medium">{activeStrategyMetadata.expected_trade_frequency}</span>
                </div>
                <div className="flex flex-col col-span-2">
                  <span className="text-slate-500 font-semibold vdl-body">Recommended timeframes</span>
                  <div className="flex gap-1.5 mt-1">
                    {activeStrategyMetadata.recommended_timeframes.map((tf) => (
                      <span key={tf} className="font-mono vdl-body font-semibold text-cyan-400 bg-cyan-950/30 px-2 py-0.5 rounded border border-cyan-800/20">
                        {tf}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Entry / Exit Rules */}
            <div className="bg-card/40 rounded p-3 flex flex-col gap-3">
              <h5 className="vdl-body font-semibold text-slate-400 border-b pb-1 flex items-center gap-1.5">
                <TrendingUp className="w-3.5 h-3.5 text-cyan-500/80" />
                <span>Execution & Signal Rules</span>
              </h5>
              <div className="flex flex-col gap-3">
                <div>
                  <span className="text-cyan-400/80 font-semibold vdl-body block">Entry trigger</span>
                  <p className="text-slate-400 mt-0.5 leading-relaxed">{activeStrategyMetadata.entry_logic}</p>
                </div>
                <div>
                  <span className="text-cyan-400/80 font-semibold vdl-body block">Exit rules</span>
                  <p className="text-slate-400 mt-0.5 leading-relaxed">{activeStrategyMetadata.exit_logic}</p>
                </div>
                <div className="grid grid-cols-2 gap-3 border-t pt-2">
                  <div>
                    <span className="text-slate-500 font-semibold vdl-body block">Strike selection</span>
                    <p className="text-slate-400 mt-0.5 leading-snug">{activeStrategyMetadata.strike_selection_logic}</p>
                  </div>
                  <div>
                    <span className="text-slate-500 font-semibold vdl-body block">Expiry selection</span>
                    <p className="text-slate-400 mt-0.5 leading-snug">{activeStrategyMetadata.expiry_selection_logic}</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 border-t pt-2">
                  <div>
                    <span className="text-slate-500 font-semibold vdl-body block">Stop loss logic</span>
                    <p className="text-slate-400 mt-0.5 leading-snug">{activeStrategyMetadata.stop_loss_logic}</p>
                  </div>
                  <div>
                    <span className="text-slate-500 font-semibold vdl-body block">Target profit logic</span>
                    <p className="text-slate-400 mt-0.5 leading-snug">{activeStrategyMetadata.target_logic}</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Parameters Specification */}
            <div className="bg-card/40 rounded p-3 flex flex-col gap-2.5">
              <h5 className="vdl-body font-semibold text-slate-400 border-b pb-1 flex items-center gap-1.5">
                <Settings className="w-3.5 h-3.5 text-cyan-500/80" />
                <span>Supported Parameters</span>
              </h5>
              <div className="flex flex-col gap-2">
                {activeStrategyMetadata.supported_parameters.map((param) => (
                  <div key={param.name} className="p-2 bg-card/60 rounded flex flex-col gap-1">
                    <div className="flex justify-between items-center font-mono">
                      <span className="font-semibold text-cyan-400">{param.name}</span>
                      <div className="flex gap-1.5 vdl-body font-semibold">
                        <span className="bg-card text-slate-400 px-1 py-0.5 rounded ">
                          {param.type}
                        </span>
                        <span className="bg-cyan-950/30 text-cyan-300 px-1 py-0.5 rounded border border-cyan-800/20">
                          Def: {String(param.default)}
                        </span>
                      </div>
                    </div>
                    <p className="text-slate-500 leading-normal vdl-body">{param.description}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Market Conditions */}
            <div className="grid grid-cols-2 gap-2 bg-card/40 rounded p-3">
              <div>
                <span className="text-emerald-400 font-semibold vdl-body block">Best conditions</span>
                <p className="text-slate-400 mt-0.5 leading-normal">{activeStrategyMetadata.best_market_conditions}</p>
              </div>
              <div>
                <span className="text-rose-400 font-semibold vdl-body block">Worst conditions</span>
                <p className="text-slate-400 mt-0.5 leading-normal">{activeStrategyMetadata.worst_market_conditions}</p>
              </div>
            </div>

            {/* Strengths & Weaknesses */}
            <div className="grid grid-cols-2 gap-2.5">
              <div className="bg-card/40 rounded p-3 flex flex-col">
                <span className="text-emerald-400 font-semibold vdl-body block mb-1.5 border-b border-emerald-900/20 pb-0.5">Strengths</span>
                <ul className="list-disc pl-3 text-slate-400 space-y-1 leading-relaxed vdl-body">
                  {activeStrategyMetadata.strengths.map((str, idx) => (
                    <li key={idx}>{str}</li>
                  ))}
                </ul>
              </div>
              <div className="bg-card/40 rounded p-3 flex flex-col">
                <span className="text-rose-400 font-semibold vdl-body block mb-1.5 border-b border-rose-900/20 pb-0.5">Weaknesses</span>
                <ul className="list-disc pl-3 text-slate-400 space-y-1 leading-relaxed vdl-body">
                  {activeStrategyMetadata.weaknesses.map((weak, idx) => (
                    <li key={idx}>{weak}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center text-slate-500 vdl-body py-12 text-center px-4 gap-2">
            <AlertCircle className="w-5 h-5 text-slate-600 animate-pulse" />
            <span>Select a strategy from the repository list above to view technical details.</span>
          </div>
        )}
      </WorkspacePanel>
    </div>
  );
};

// ==========================================
// 2. MAIN PANEL: HISTORICAL CHART & RUN TOOLBAR
// ==========================================
export const BacktestMain: React.FC = () => {
  const theme = useThemeStore((state) => state.theme);
  const [activeTab, setActiveTab] = useState<"overview" | "trades" | "equity" | "drawdown" | "metrics" | "optimization" | "runtime">("overview");
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const tradeHighlightSeriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const tradeMarkersPluginRef = useRef<any>(null);

  const selectedStrategy = useTerminalStore((state) => state.selectedStrategy);
  const addEvent = useEventStore((state) => state.addEvent);

  const v2Config = useBacktestStore((state) => state.v2Config);
  const setV2Config = useBacktestStore((state) => state.setV2Config);
  const runV2Backtest = useBacktestStore((state) => state.runV2Backtest);
  const v2BacktestResult = useBacktestStore((state) => state.v2BacktestResult);
  const v2Status = useBacktestStore((state) => state.v2Status);
  const isBacktestLoading = useBacktestStore((state) => state.isBacktestLoading);
  const selectedTradeId = useBacktestStore((state) => state.selectedTradeId);
  const isReplayMode = useBacktestStore((state) => state.isReplayMode);
  const replayCurrentTime = useBacktestStore((state) => state.replayCurrentTime);

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

    const rootStyle = typeof window !== "undefined" ? getComputedStyle(document.documentElement) : null;
    const bgDeep = rootStyle?.getPropertyValue("--bg-card").trim() || "#0F172A";
    const textMute = rootStyle?.getPropertyValue("--text-mute").trim() || "#94a3b8";
    const borderSubtle = rootStyle?.getPropertyValue("--border-subtle").trim() || "rgba(255,255,255,0.05)";

    const themeColors = {
      background: bgDeep,
      text: textMute,
      grid: borderSubtle,
      border: borderSubtle,
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

    const tradeHighlightSeries = chart.addSeries(AreaSeries, {
      topColor: "rgba(6, 182, 212, 0.15)",
      bottomColor: "rgba(6, 182, 212, 0.01)",
      lineColor: "rgba(6, 182, 212, 0.5)",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
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
      chart.timeScale().fitContent();
    }

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    tradeHighlightSeriesRef.current = tradeHighlightSeries;

    const tradeMarkersPlugin = createSeriesMarkers(candleSeries, []);
    tradeMarkersPluginRef.current = tradeMarkersPlugin;

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

  // Synchronize selected trade highlighting and zoom
  useEffect(() => {
    if (!chartRef.current || !candleSeriesRef.current || !v2BacktestResult) return;

    // 1. Handle progressive candle visibility in Replay Mode
    if (isReplayMode && replayCurrentTime) {
      const filteredPriceData = v2BacktestResult.candles
        .filter(c => c.time <= replayCurrentTime)
        .map((c) => ({
          time: c.time as UTCTimestamp,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }))
        .sort((a, b) => a.time - b.time);
      candleSeriesRef.current.setData(filteredPriceData);
    } else {
      // Revert to all candles if we exit replay mode
      if (v2BacktestResult.candles) {
        const priceData = v2BacktestResult.candles
          .map((c) => ({
            time: c.time as UTCTimestamp,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
          }))
          .sort((a, b) => a.time - b.time);
        candleSeriesRef.current.setData(priceData);
      }
    }

    // 2. Handle progressive marker visibility and descriptive labels
    if (v2BacktestResult.chart_trades) {
      const markers = v2BacktestResult.chart_trades
        .filter((t) => {
          if (isReplayMode && replayCurrentTime) {
            const tradeTime = Math.floor(new Date(t.timestamp).getTime() / 1000);
            return tradeTime <= replayCurrentTime;
          }
          return true;
        })
        .map((t) => {
          const tradeTime = Math.floor(new Date(t.timestamp).getTime() / 1000) as UTCTimestamp;
          const isSelectedEntry = selectedTradeId && t.id === `${selectedTradeId}_entry`;
          const isSelectedExit = selectedTradeId && t.id === `${selectedTradeId}_exit`;
          const isSelected = isSelectedEntry || isSelectedExit;

          let markerText = "";
          if (isSelected) {
            const selectedTrade = v2BacktestResult.trades.find(x => x.position_id === selectedTradeId);
            if (t.type === "BUY") {
              markerText = `🎯 ENTRY ₹${selectedTrade?.entry_premium?.toFixed(2) ?? "0.00"}`;
            } else {
              markerText = `🎯 EXIT ₹${selectedTrade?.exit_premium?.toFixed(2) ?? "0.00"} (${(selectedTrade?.net_pnl ?? 0) >= 0 ? "+" : ""}₹${selectedTrade?.net_pnl?.toFixed(2) ?? "0.00"})`;
            }
          } else {
            markerText = `${t.type} (${t.strike} CE)`;
          }

          return {
            time: tradeTime,
            position: t.type === "BUY" ? ("belowBar" as const) : ("aboveBar" as const),
            color: isSelected 
              ? "#06b6d4" // Bright Cyan for selected trade
              : t.type === "BUY" ? "#10b981" : "#ef4444",
            shape: t.type === "BUY" ? ("arrowUp" as const) : ("arrowDown" as const),
            text: markerText,
          };
        });
      markers.sort((a, b) => (a.time as number) - (b.time as number));
      tradeMarkersPluginRef.current?.setMarkers(markers);
    }

    // 3. Handle Chart Zoom and Auto-scroll behavior
    if (selectedTradeId && v2BacktestResult.trades) {
      const selectedTrade = v2BacktestResult.trades.find(t => t.position_id === selectedTradeId);
      if (selectedTrade) {
        const entryTime = Math.floor(new Date(selectedTrade.entry_time).getTime() / 1000);
        const exitTime = Math.floor(new Date(selectedTrade.exit_time).getTime() / 1000);

        try {
          if (isReplayMode && replayCurrentTime) {
            // Replay Mode: Auto-scroll & keep current candle focused near the center
            const visibleWindow = 40; // show 40 candles total
            const timeStep = 60; // 1-minute steps
            chartRef.current.timeScale().setVisibleRange({
              from: (replayCurrentTime - visibleWindow * timeStep) as UTCTimestamp,
              to: (replayCurrentTime + 10 * timeStep) as UTCTimestamp,
            });
          } else {
            // Standard Mode: Fit entire trade with padding
            const duration = exitTime - entryTime;
            const padding = Math.max(duration * 3, 3600); // at least 1 hour padding or 3x duration
            chartRef.current.timeScale().setVisibleRange({
              from: (entryTime - padding) as UTCTimestamp,
              to: (exitTime + padding) as UTCTimestamp,
            });
          }
        } catch (err) {
          console.warn("Timescale setVisibleRange deferred due to uninitialized state:", err);
        }

        // 4. Set active period area shading dynamically (grows with replayCurrentTime in replay mode)
        if (v2BacktestResult.candles && tradeHighlightSeriesRef.current) {
          const highlightLimit = (isReplayMode && replayCurrentTime) ? replayCurrentTime : exitTime;
          const highlightData = v2BacktestResult.candles
            .filter(c => c.time >= entryTime && c.time <= highlightLimit)
            .map(c => ({
              time: c.time as UTCTimestamp,
              value: c.close
            }))
            .sort((a, b) => a.time - b.time);
          tradeHighlightSeriesRef.current.setData(highlightData);
        }
      }
    } else {
      tradeHighlightSeriesRef.current?.setData([]);
    }
  }, [selectedTradeId, v2BacktestResult, isReplayMode, replayCurrentTime, theme]);

  return (
    <div className="flex flex-col h-full panel overflow-hidden font-sans vdl-body">
      
      {/* Run Parameter Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 bg-card-hover border-b select-none shrink-0 flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <div className="flex flex-col gap-0.5">
            <span className="vdl-body text-slate-500 font-semibold">Active strategy</span>
            <span className="text-cyan-400 font-semibold font-mono">
              {v2Config.strategy_name || "No Strategy Selected"}
            </span>
          </div>

          <div className="h-6 w-px border-l" />

          {/* Date Picker */}
          <div className="flex flex-col gap-0.5">
            <span className="vdl-body text-slate-500 font-semibold">Start date</span>
            <input
              type="date"
              value={v2Config.start_date}
              onChange={(e) => setV2Config({ start_date: e.target.value })}
              className="input font-mono rounded px-1.5 py-0.5 vdl-body bg-deep"
            />
          </div>

          <div className="flex flex-col gap-0.5">
            <span className="vdl-body text-slate-500 font-semibold">End date</span>
            <input
              type="date"
              value={v2Config.end_date}
              onChange={(e) => setV2Config({ end_date: e.target.value })}
              className="input font-mono rounded px-1.5 py-0.5 vdl-body bg-deep"
            />
          </div>
        </div>

        {/* Buttons */}
        <div className="flex items-center gap-2">
          {isBacktestLoading ? (
            <div className="flex items-center gap-2">
              <div className="w-20 bg-slate-800 h-1.5 rounded-full overflow-hidden">
                <div style={{ width: `${v2Status.progress}%` }} className="bg-cyan-neon h-full transition-all duration-300" />
              </div>
              <span className="vdl-body font-mono text-cyan-neon font-semibold">{v2Status.progress}%</span>
            </div>
          ) : (
            <button
              onClick={handleRunBacktest}
              disabled={!selectedStrategy}
              className="btn-primary flex items-center gap-1.5 cursor-pointer"
            >
              <Play className="w-3 h-3 fill-current" />
              Run Backtest
            </button>
          )}
        </div>
      </div>

      {/* Candlestick simulator canvas */}
      <div className="flex-1 min-h-0 relative">
        {isBacktestLoading && (
          <div className="absolute inset-0 bg-card/80 z-10 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-6 h-6 text-cyan-400 animate-spin" />
            <span className="vdl-body text-slate-400 font-mono">Running V2 chronological replay simulation...</span>
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
    <WorkspacePanel title="Backtest Parameters">
      <div className="flex flex-col gap-4 h-full font-sans select-none overflow-y-auto pr-1">
        <FormSection title="Global Configuration">
          <div className="grid grid-cols-2 gap-3">
            <FormField label="Underlying index">
              <select
                value={v2Config.underlying_instrument_key}
                onChange={(e) => setV2Config({ underlying_instrument_key: e.target.value })}
                className="input cursor-pointer font-medium"
              >
                <option value="NSE_INDEX|Nifty 50">NIFTY 50</option>
                <option value="NSE_INDEX|Nifty Bank">BANKNIFTY</option>
                <option value="NSE_INDEX|Nifty Fin Service">FINNIFTY</option>
              </select>
            </FormField>

            <FormField label="Signal source">
              <select
                value={v2Config.signal_source}
                onChange={(e) => setV2Config({ signal_source: e.target.value })}
                className="input cursor-pointer font-medium"
              >
                <option value="SPOT">Spot Price</option>
                <option value="FUTURES">Futures underlying</option>
              </select>
            </FormField>

            <FormField label="Timeframe">
              <select
                value={v2Config.timeframe}
                onChange={(e) => setV2Config({ timeframe: e.target.value })}
                className="input cursor-pointer font-mono font-medium"
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
            </FormField>

            <FormField label="Option preference">
              <select
                value={v2Config.option_type_preference}
                onChange={(e) => setV2Config({ option_type_preference: e.target.value })}
                className="input cursor-pointer font-medium"
              >
                <option value="DYNAMIC">Dynamic CE/PE</option>
                <option value="CE_ONLY">Call Options Only</option>
                <option value="PE_ONLY">Put Options Only</option>
              </select>
            </FormField>

            <FormField label="Strike mode">
              <select
                value={v2Config.strike_mode}
                onChange={(e) => setV2Config({ strike_mode: e.target.value })}
                className="input cursor-pointer font-medium"
              >
                <option value="ATM">ATM (At-The-Money)</option>
                <option value="OTM_1">OTM +1 Strike</option>
                <option value="OTM_2">OTM +2 Strike</option>
                <option value="OTM_3">OTM +3 Strike</option>
                <option value="ITM_1">ITM -1 Strike</option>
                <option value="ITM_2">ITM -2 Strike</option>
                <option value="ITM_3">ITM -3 Strike</option>
              </select>
            </FormField>

            <FormField label="Expiry mode">
              <select
                value={v2Config.expiry_mode}
                onChange={(e) => setV2Config({ expiry_mode: e.target.value })}
                className="input cursor-pointer font-medium"
              >
                <option value="CURRENT_WEEKLY">Current Weekly</option>
                <option value="NEXT_WEEKLY">Next Weekly</option>
                <option value="CURRENT_MONTHLY">Current Monthly</option>
              </select>
            </FormField>

            <FormField label="Initial capital (₹)">
              <input
                type="number"
                value={v2Config.initial_capital}
                onChange={(e) => setV2Config({ initial_capital: Number(e.target.value) })}
                className="input font-mono font-medium"
              />
            </FormField>

            <FormField label="Lot multiplier">
              <input
                type="number"
                value={v2Config.lot_multiplier}
                onChange={(e) => setV2Config({ lot_multiplier: Number(e.target.value) })}
                className="input font-mono font-medium"
              />
            </FormField>
          </div>
        </FormSection>

        {selectedStrategy ? (
          <FormSection title="Strategy Parameters">
            <div className="flex flex-col gap-4">
              {v2Config.strategy_name === "EMA" && (
                <>
                  <FormField
                    label="Fast EMA Period"
                    helpText={`Current: ${v2Config.strategy_params.fastEma || 2}`}
                  >
                    <input
                      type="range"
                      min="2"
                      max="50"
                      value={v2Config.strategy_params.fastEma || 2}
                      onChange={(e) => handleParamChange("fastEma", Number(e.target.value))}
                      className="w-full cursor-pointer transition-all"
                    />
                  </FormField>

                  <FormField
                    label="Slow EMA Period"
                    helpText={`Current: ${v2Config.strategy_params.slowEma || 3}`}
                  >
                    <input
                      type="range"
                      min="3"
                      max="100"
                      value={v2Config.strategy_params.slowEma || 3}
                      onChange={(e) => handleParamChange("slowEma", Number(e.target.value))}
                      className="w-full cursor-pointer transition-all"
                    />
                  </FormField>
                </>
              )}

              {v2Config.strategy_name === "five_ema_scalping" && (
                <>
                  <FormField
                    label="EMA Period"
                    helpText={`Current: ${v2Config.strategy_params.five_ema_period || 5}`}
                  >
                    <input
                      type="range"
                      min="3"
                      max="20"
                      value={v2Config.strategy_params.five_ema_period || 5}
                      onChange={(e) => handleParamChange("five_ema_period", Number(e.target.value))}
                      className="w-full cursor-pointer transition-all"
                    />
                  </FormField>

                  <FormField
                    label="Risk-Reward Ratio"
                    helpText={`Current: ${v2Config.strategy_params.five_ema_rr || 3.0}`}
                  >
                    <input
                      type="range"
                      min="1.5"
                      max="10"
                      step="0.5"
                      value={v2Config.strategy_params.five_ema_rr || 3.0}
                      onChange={(e) => handleParamChange("five_ema_rr", Number(e.target.value))}
                      className="w-full cursor-pointer transition-all"
                    />
                  </FormField>
                </>
              )}

              {/* Commissions & Slippage inputs */}
              <div className="grid grid-cols-2 gap-3 mt-1 pt-3 border-t/30">
                <FormField label="Brokerage flat (₹)">
                  <input
                    type="number"
                    value={v2Config.brokerage_flat}
                    onChange={(e) => setV2Config({ brokerage_flat: Number(e.target.value) })}
                    className="input font-mono font-medium"
                  />
                </FormField>

                <FormField label="Slippage (%)">
                  <input
                    type="number"
                    step="0.01"
                    value={v2Config.slippage_pct}
                    onChange={(e) => setV2Config({ slippage_pct: Number(e.target.value) })}
                    className="input font-mono font-medium"
                  />
                </FormField>
              </div>
            </div>
          </FormSection>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-slate-500 vdl-body text-center px-4 gap-2">
            <AlertCircle className="w-5 h-5 text-slate-600 animate-pulse" />
            <span>Select a strategy from the repository to configure parameter controls.</span>
          </div>
        )}
      </div>
    </WorkspacePanel>
  );
};

// ==========================================
// 4. BOTTOM PANEL: TABBED ANALYSIS RESULTS
// ==========================================
export const BacktestBottom: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"overview" | "trades" | "equity" | "drawdown" | "metrics" | "optimization" | "runtime">("overview");
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
  const selectedTradeId = useBacktestStore((state) => state.selectedTradeId);
  const setSelectedTradeId = useBacktestStore((state) => state.setSelectedTradeId);
  const isReplayMode = useBacktestStore((state) => state.isReplayMode);
  const setIsReplayMode = useBacktestStore((state) => state.setIsReplayMode);
  const setReplayTradeId = useBacktestStore((state) => state.setReplayTradeId);
  const replayCurrentTime = useBacktestStore((state) => state.replayCurrentTime);
  const setReplayCurrentTime = useBacktestStore((state) => state.setReplayCurrentTime);

  const [isPlaying, setIsPlaying] = useState(false);
  const [playSpeed, setPlaySpeed] = useState<1 | 2 | 5 | 10>(1);

  const recentTradesColumns: ColumnDef<any>[] = [
    {
      header: "Time",
      accessorKey: (row) => new Date(row.entry_time).toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        timeZone: "Asia/Kolkata",
      }),
      isMono: true,
    },
    {
      header: "Type",
      accessorKey: (row) => {
        const type = row.contract.includes("PE") ? "PE" : "CE";
        const sideState = type === "PE" ? "Failed" : "Running";
        return <StatusBadge state={sideState} className="!font-sans font-semibold" />;
      },
    },
    {
      header: "Instrument",
      accessorKey: (row) => row.contract.split(" ")[0] || row.contract,
      className: "font-sans font-semibold text-slate-200",
    },
    {
      header: "Strike",
      accessorKey: (row) => {
        const strikeMatch = row.contract.match(new RegExp("\\d{5}"));
        return strikeMatch ? strikeMatch[0] : "-";
      },
      className: "text-center",
      isMono: true,
    },
    {
      header: "Expiry",
      accessorKey: (row) => {
        const parts = row.contract.split(" ");
        return parts.length > 2 ? parts[1] : "-";
      },
      isMono: true,
    },
    {
      header: "Qty",
      accessorKey: "quantity",
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Entry Price",
      accessorKey: (row) => `₹${row.entry_premium.toFixed(2)}`,
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Exit Price",
      accessorKey: (row) => `₹${row.exit_premium.toFixed(2)}`,
      isNumeric: true,
      isMono: true,
    },
    {
      header: "P&L (₹)",
      accessorKey: (row) => {
        const isProfit = row.net_pnl >= 0;
        return (
          <span className={`font-semibold ${isProfit ? "text-emerald-400" : "text-rose-400"}`}>
            ₹{row.net_pnl.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        );
      },
      isNumeric: true,
      isMono: true,
    },
    {
      header: "P&L (%)",
      accessorKey: (row) => {
        const isProfit = row.net_pnl >= 0;
        const pct = (row.net_pnl / (row.entry_premium * row.quantity)) * 100;
        return (
          <span className={`font-semibold ${isProfit ? "text-emerald-400" : "text-rose-400"}`}>
            {pct.toFixed(2)}%
          </span>
        );
      },
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Status",
      accessorKey: (row) => {
        const badgeState = row.net_pnl >= 0 ? "Success" : "Failed";
        return <StatusBadge state={badgeState} />;
      },
      className: "text-center",
    },
  ];

  const tradeLedgerColumns: ColumnDef<any>[] = [
    {
      header: "Contract Details",
      accessorKey: "contract",
      className: "font-semibold text-cyan-neon",
    },
    {
      header: "Entry Time",
      accessorKey: (row) => `${new Date(row.entry_time).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST`,
      isMono: true,
    },
    {
      header: "Exit Time",
      accessorKey: (row) => `${new Date(row.exit_time).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST`,
      isMono: true,
    },
    {
      header: "Entry Premium",
      accessorKey: (row) => `₹${row.entry_premium.toFixed(2)}`,
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Exit Premium",
      accessorKey: (row) => `₹${row.exit_premium.toFixed(2)}`,
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Qty",
      accessorKey: "quantity",
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Gross PnL",
      accessorKey: (row) => (
        <span className={`font-semibold ${row.gross_pnl > 0 ? "text-emerald-400" : "text-rose-400"}`}>
          ₹{row.gross_pnl.toFixed(2)}
        </span>
      ),
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Charges",
      accessorKey: (row) => `₹${row.charges.total_charges.toFixed(2)}`,
      isNumeric: true,
      isMono: true,
      className: "text-slate-500",
    },
    {
      header: "Net PnL",
      accessorKey: (row) => (
        <span className={`font-semibold ${row.net_pnl > 0 ? "text-emerald-400" : "text-rose-400"}`}>
          ₹{row.net_pnl.toFixed(2)}
        </span>
      ),
      isNumeric: true,
      isMono: true,
    },
  ];

  const optimizationColumns: ColumnDef<any>[] = [
    {
      header: "Rank",
      accessorKey: (_, idx) => `#${idx + 1}`,
      className: "text-slate-500 pl-2",
    },
    {
      header: "Parameters (Fast / Slow)",
      accessorKey: (row) => `Fast: ${row.combination.params.fastEma || row.combination.params.fast_period} | Slow: ${row.combination.params.slowEma || row.combination.params.slow_period}`,
      className: "text-cyan-400 font-semibold",
    },
    {
      header: "Net Profit",
      accessorKey: (row) => (
        <span className={`font-semibold ${row.metrics.net_profit >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
          ₹{row.metrics.net_profit.toLocaleString("en-IN")}
        </span>
      ),
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Profit Factor",
      accessorKey: (row) => row.metrics.profit_factor.toFixed(2),
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Expectancy",
      accessorKey: (row) => row.metrics.expectancy.toFixed(2),
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Sharpe",
      accessorKey: (row) => row.metrics.sharpe_ratio.toFixed(2),
      isNumeric: true,
      isMono: true,
      className: "text-cyan-400 font-semibold",
    },
    {
      header: "Sortino",
      accessorKey: (row) => row.metrics.sortino_ratio.toFixed(2),
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Max Drawdown",
      accessorKey: (row) => `${row.metrics.max_drawdown_pct.toFixed(2)}%`,
      isNumeric: true,
      isMono: true,
      className: "text-rose-400",
    },
    {
      header: "Score",
      accessorKey: (row) => row.score.toFixed(1),
      isNumeric: true,
      isMono: true,
      className: "text-cyan-400 font-semibold",
    },
    {
      header: "Sensitivity",
      accessorKey: (row) => {
        if (!v2OptimizationReport) return "-";
        const paramsKey = JSON.stringify(row.combination.params);
        const stability = v2OptimizationReport.stability_findings[paramsKey];
        if (!stability) return "-";
        return (
          <span className={`font-semibold ${
            stability.status === "STABLE" ? "text-emerald-400" : "text-rose-400"
          }`}>
            {stability.status}
          </span>
        );
      },
      className: "text-center pr-2",
    },
  ];

  // Compute trade candles & replay timeline dynamically
  const replayTrade = React.useMemo(() => {
    return v2Result?.trades.find(t => t.position_id === selectedTradeId);
  }, [v2Result, selectedTradeId]);

  const replayTimeline = React.useMemo(() => {
    if (!replayTrade || !v2Result?.candles) return [];
    const entryTime = Math.floor(new Date(replayTrade.entry_time).getTime() / 1000);
    const exitTime = Math.floor(new Date(replayTrade.exit_time).getTime() / 1000);
    return v2Result.candles
      .filter(c => c.time >= entryTime && c.time <= exitTime)
      .map(c => c.time)
      .sort((a, b) => a - b);
  }, [replayTrade, v2Result]);

  // Replay interval timer
  useEffect(() => {
    if (!isPlaying || !isReplayMode || !replayTimeline.length) return;

    const intervalMs = playSpeed === 1 ? 1000 : playSpeed === 2 ? 500 : playSpeed === 5 ? 200 : 100;

    const timer = setInterval(() => {
      const prev = useBacktestStore.getState().replayCurrentTime;
      if (prev === null) {
        if (replayTimeline.length > 0) setReplayCurrentTime(replayTimeline[0]);
      } else {
        const idx = replayTimeline.indexOf(prev);
        if (idx < replayTimeline.length - 1) {
          setReplayCurrentTime(replayTimeline[idx + 1]);
        } else {
          setIsPlaying(false);
        }
      }
    }, intervalMs);

    return () => clearInterval(timer);
  }, [isPlaying, playSpeed, isReplayMode, replayTimeline, setReplayCurrentTime]);

  // Optimization Parameter Ranges (Local Form State)
  const [fastEmaStart, setFastEmaStart] = useState(2);
  // Telemetry logs from backend
  const logs = useBackendTradingStore((state) => state.logs);
  
  // Runtime Telemetry Log Filters
  const [logCategoryFilter, setLogCategoryFilter] = useState<string>("ALL");
  const [logSearchQuery, setLogSearchQuery] = useState<string>("");
  const [expandedLogId, setExpandedLogId] = useState<number | null>(null);

  const [fastEmaEnd, setFastEmaEnd] = useState(5);
  const [fastEmaStep, setFastEmaStep] = useState(1);

  const [slowEmaStart, setSlowEmaStart] = useState(3);
  const [slowEmaEnd, setSlowEmaEnd] = useState(8);
  const [slowEmaStep, setSlowEmaStep] = useState(1);

  const [workerCount, setWorkerCount] = useState(4);
  const [heatmapMetric, setHeatmapMetric] = useState<"net_profit" | "sharpe_ratio" | "profit_factor" | "composite_score">("net_profit");
  const [optTab, setOptTab] = useState<"setup" | "ranked" | "heatmap">("setup");
  const [rankedFilter, setRankedFilter] = useState<"top10" | "top25" | "top50">("top10");

  const getHoldingDuration = (entry: string, exit: string) => {
    const diffMs = new Date(exit).getTime() - new Date(entry).getTime();
    const diffSecs = Math.floor(diffMs / 1000);
    const minutes = Math.floor(diffSecs / 60);
    const seconds = diffSecs % 60;
    if (minutes > 0) return `${minutes}m ${seconds}s`;
    return `${seconds}s`;
  };

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
      localization: {
        timeFormatter: (timestamp: number) => {
          return new Date(timestamp * 1000).toLocaleString("en-IN", {
            timeZone: "Asia/Kolkata",
            hour12: false,
          });
        },
      },
      timeScale: {
        timeVisible: true,
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
      localization: {
        timeFormatter: (timestamp: number) => {
          return new Date(timestamp * 1000).toLocaleString("en-IN", {
            timeZone: "Asia/Kolkata",
            hour12: false,
          });
        },
      },
      timeScale: {
        timeVisible: true,
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
    { id: "runtime" as const, name: "Runtime Logs" },
  ];

  // Helper to extract parameters list from top ranking
  const getRankedList = () => {
    if (!v2OptimizationReport) return [];
    if (rankedFilter === "top25") return v2OptimizationReport.top_25;
    if (rankedFilter === "top50") return v2OptimizationReport.top_50;
    return v2OptimizationReport.top_10;
  };

  return (
    <div className="flex flex-col h-full overflow-hidden vdl-body font-sans">
      
      {/* 0. Trade Forensic Replay Cockpit Layer */}
      {(() => {
        if (!isReplayMode || !replayTrade || !v2Result) return null;

        const totalSteps = replayTimeline.length;
        const currentIndex = replayTimeline.indexOf(replayCurrentTime || 0);
        const currentCandleTime = replayTimeline[currentIndex] || 0;

        // Calculations for progressive variables
        let livePremium = 0;
        let livePnL = 0;
        let maxRunUp = 0;
        let maxDrawdown = 0;
        let liveSpot = 0;
        let liveSpotDelta = 0;
        let liveSpotDeltaPct = 0;
        let elapsedMinutes = 0;

        if (v2Result.candles) {
          const entryTime = Math.floor(new Date(replayTrade.entry_time).getTime() / 1000);
          const exitTime = Math.floor(new Date(replayTrade.exit_time).getTime() / 1000);
          const tradeCandles = v2Result.candles
            .filter(c => c.time >= entryTime && c.time <= exitTime)
            .sort((a, b) => a.time - b.time);

          if (tradeCandles.length > 0) {
            const entrySpot = tradeCandles[0].close;
            const exitSpot = tradeCandles[tradeCandles.length - 1].close;
            const spotMove = exitSpot - entrySpot;
            const premiumMove = replayTrade.exit_premium - replayTrade.entry_premium;
            const tradeDelta = spotMove !== 0 ? (premiumMove / spotMove) : 0.5;

            const currentCandle = tradeCandles[currentIndex] || tradeCandles[0];
            liveSpot = currentCandle?.close || 0;
            liveSpotDelta = liveSpot - entrySpot;
            liveSpotDeltaPct = entrySpot !== 0 ? (liveSpotDelta / entrySpot) * 100 : 0;
            
            // Holding duration calculation in minutes
            const diffSecs = (currentCandleTime > 0 && entryTime > 0) ? (currentCandleTime - entryTime) : 0;
            elapsedMinutes = Math.floor(diffSecs / 60);

            if (currentIndex === totalSteps - 1) {
              livePremium = replayTrade.exit_premium;
              livePnL = replayTrade.gross_pnl;
            } else {
              livePremium = replayTrade.entry_premium + (liveSpot - entrySpot) * tradeDelta;
              livePnL = (livePremium - replayTrade.entry_premium) * replayTrade.quantity;
            }

            // Calculate Adverse/Favorable excursions dynamically
            for (let i = 0; i <= currentIndex; i++) {
              const c = tradeCandles[i];
              let stepPrem = 0;
              if (i === totalSteps - 1) {
                stepPrem = replayTrade.exit_premium;
              } else {
                stepPrem = replayTrade.entry_premium + (c.close - entrySpot) * tradeDelta;
              }
              const stepPnL = (stepPrem - replayTrade.entry_premium) * replayTrade.quantity;
              if (stepPnL > maxRunUp) maxRunUp = stepPnL;
              if (stepPnL < maxDrawdown) maxDrawdown = stepPnL;
            }
          }
        }

        const isWinner = replayTrade.net_pnl > 0;
        const reachedExit = currentIndex === totalSteps - 1;

        return (
          <div className="flex flex-col h-full bg-card/80  p-4 rounded shadow-2xl relative min-h-[300px]">
            {/* HUD Status Header */}
            <div className="flex items-center justify-between border-b pb-2 mb-3.5 select-none">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75${isPlaying ? "bg-amber-400" : "bg-cyan-400"}`}></span>
                  <span className={`relative inline-flex rounded-full h-2 w-2${isPlaying ? "bg-amber-500" : "bg-cyan-500"}`}></span>
                </span>
                <span className="font-mono vdl-body font-semibold text-slate-200">
                  Trade Forensic Replay Cockpit
                </span>
                <span className="px-2 py-0.5 rounded vdl-body font-mono font-semibold bg-card  text-cyan-400 select-text">
                  {replayTrade.contract}
                </span>
              </div>

              <button
                onClick={() => {
                  setIsPlaying(false);
                  setIsReplayMode(false);
                }}
                className="px-2.5 py-1 bg-rose-950/30 hover:bg-rose-900/40 text-rose-400 font-semibold vdl-body rounded border border-rose-800/30 transition-all cursor-pointer"
              >
                Exit Replay
              </button>
            </div>

            {/* Main HUD Body */}
            <div className="grid grid-cols-12 gap-4 flex-1">
              
              {/* COL 1: Playback Console & Control Deck (4 cols) */}
              <div className="col-span-4 bg-card/40 rounded p-3 flex flex-col justify-between select-none">
                <div>
                  <span className="vdl-body text-slate-500 font-semibold block mb-2">Control deck</span>
                  
                  {/* VCR Playback Controls */}
                  <div className="flex items-center gap-2 mb-4">
                    <button
                      onClick={() => {
                        setIsPlaying(false);
                        if (totalSteps > 0) setReplayCurrentTime(replayTimeline[0]);
                      }}
                      className="p-2 bg-card  hover:border-subtle active:bg-card rounded text-slate-300 hover:text-white transition-all cursor-pointer"
                      title="Restart Replay"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                    </button>
                    
                    <button
                      onClick={() => {
                        setIsPlaying(false);
                        const idx = replayTimeline.indexOf(replayCurrentTime || 0);
                        if (idx > 0) setReplayCurrentTime(replayTimeline[idx - 1]);
                      }}
                      className="p-2 bg-card  hover:border-subtle active:bg-card rounded text-slate-300 hover:text-white transition-all cursor-pointer"
                      title="Previous Candle"
                    >
                      <ChevronLeft className="w-3.5 h-3.5" />
                    </button>

                    <button
                      onClick={() => setIsPlaying(!isPlaying)}
                      className={`px-4 py-2 rounded text-slate-950 font-semibold flex items-center gap-1.5 transition-all cursor-pointer${
                        isPlaying ? "bg-amber-400 hover:bg-amber-300" : "bg-cyan-400 hover:bg-cyan-300"
                      }`}
                      title={isPlaying ? "Pause Playback" : "Start Playback"}
                    >
                      {isPlaying ? (
                        <>
                          <Pause className="w-3.5 h-3.5 fill-current" />
                          <span>PAUSE</span>
                        </>
                      ) : (
                        <>
                          <Play className="w-3.5 h-3.5 fill-current" />
                          <span>PLAY</span>
                        </>
                      )}
                    </button>

                    <button
                      onClick={() => {
                        setIsPlaying(false);
                        const idx = replayTimeline.indexOf(replayCurrentTime || 0);
                        if (idx < totalSteps - 1) setReplayCurrentTime(replayTimeline[idx + 1]);
                      }}
                      className="p-2 bg-card  hover:border-subtle active:bg-card rounded text-slate-300 hover:text-white transition-all cursor-pointer"
                      title="Next Candle"
                    >
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  {/* Playback Speed Deck */}
                  <span className="vdl-body text-slate-500 font-semibold block mb-1.5">Speed multiplier</span>
                  <div className="flex gap-1.5 mb-4">
                    {([1, 2, 5, 10] as const).map((speed) => (
                      <button
                        key={speed}
                        onClick={() => setPlaySpeed(speed)}
                        className={`px-3 py-1 font-mono vdl-body font-semibold rounded border transition-all cursor-pointer${
                          playSpeed === speed 
                            ? "bg-cyan-950 text-cyan-400 border-cyan-500/30" 
                            : "bg-card text-slate-500 hover:text-slate-300 hover:border-subtle"
                        }`}
                      >
                        {speed}x
                      </button>
                    ))}
                  </div>
                </div>

                {/* Step / Timeline Progress Indicator */}
                <div className="border-t pt-3">
                  <div className="flex justify-between items-center vdl-body font-mono text-slate-400 mb-1.5">
                    <span>TIMELINE INDEX</span>
                    <span className="font-semibold text-slate-200">
                      STEP {currentIndex + 1} / {totalSteps}
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-card rounded-full overflow-hidden ">
                    <div 
                      className="h-full bg-cyan-400 rounded-full transition-all duration-150"
                      style={{ width: `${totalSteps > 0 ? ((currentIndex + 1) / totalSteps) * 100 : 0}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* COL 2: Live Trade Analytics HUD (5 cols) */}
              <div className="col-span-5 bg-card/20  rounded p-3 flex flex-col justify-between">
                <div>
                  <span className="vdl-body text-slate-500 font-semibold block mb-2 select-none">Live telemetry HUD</span>
                  
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div className="bg-card/40 p-2.5 rounded ">
                      <span className="vdl-body text-slate-500 font-semibold block mb-0.5 select-none">Entry premium</span>
                      <span className="font-mono text-slate-200 font-semibold section">₹{replayTrade.entry_premium.toFixed(2)}</span>
                    </div>

                    <div className={`p-2.5 rounded border transition-all duration-300${
                      livePnL >= 0 ? "bg-emerald-950/20 border-emerald-500/20" : "bg-rose-950/20 border-rose-500/20"
                    }`}>
                      <span className="vdl-body text-slate-500 font-semibold block mb-0.5 select-none">Current premium</span>
                      <span className={`font-mono font-semibold section${livePnL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        ₹{livePremium.toFixed(2)}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div className="bg-card/40 p-2.5 rounded ">
                      <span className="vdl-body text-slate-500 font-semibold block mb-0.5 select-none">Holding duration</span>
                      <span className="font-mono text-slate-200 font-semibold section">{elapsedMinutes} mins</span>
                    </div>

                    <div className="bg-card/40 p-2.5 rounded ">
                      <span className="vdl-body text-slate-500 font-semibold block mb-0.5 select-none">Spot index delta</span>
                      <span className={`font-mono font-semibold section flex items-center gap-1${liveSpotDelta >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {liveSpotDelta >= 0 ? "+" : ""}{liveSpotDelta.toFixed(2)} ({liveSpotDeltaPct.toFixed(2)}%)
                      </span>
                    </div>
                  </div>
                </div>

                {/* Big Unrealized PnL Board */}
                <div className={`p-3 rounded border flex items-center justify-between transition-all duration-300${
                  livePnL >= 0 ? "bg-emerald-950/30 border-emerald-500/30 shadow-emerald-950/20" : "bg-rose-950/30 border-rose-500/30 shadow-rose-950/20"
                }shadow-md`}>
                  <div className="flex flex-col">
                    <span className="vdl-body text-slate-400 font-semibold select-none">Unrealized profit / loss</span>
                    <span className={`font-mono display font-semibold${livePnL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {livePnL >= 0 ? "+" : ""}₹{livePnL.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  {livePnL >= 0 ? (
                    <ArrowUpRight className="w-6 h-6 text-emerald-400" />
                  ) : (
                    <ArrowDownRight className="w-6 h-6 text-rose-400" />
                  )}
                </div>
              </div>

              {/* COL 3: Trade Timeline & Replay Summary (3 cols) */}
              <div className="col-span-3 bg-card/40 rounded p-3 flex flex-col justify-between font-mono">
                <div>
                  <span className="vdl-body text-slate-500 font-semibold block mb-2 select-none">Execution Details</span>
                  
                  <div className="flex flex-col gap-1 vdl-body text-slate-400 border-b pb-2.5 mb-2.5">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Entry Time:</span>
                      <span className="text-slate-300">{new Date(replayTrade.entry_time).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })} IST</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Current Play:</span>
                      <span className="text-cyan-400 font-semibold">{currentCandleTime > 0 ? new Date(currentCandleTime * 1000).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) : "--:--:--"} IST</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Exit Time:</span>
                      <span className="text-slate-300">{new Date(replayTrade.exit_time).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })} IST</span>
                    </div>
                  </div>
                </div>

                {/* Replay Summary Container */}
                <div className="flex-1 flex flex-col justify-end">
                  {!reachedExit ? (
                    <div className="bg-card/60  p-3 rounded flex flex-col items-center justify-center h-24 select-none animate-pulse">
                      <Activity className="w-4 h-4 text-slate-600 mb-1" />
                      <span className="vdl-body text-slate-500 font-semibold">REPLAY RUNNING</span>
                      <span className="vdl-body text-slate-500">Awaiting exit candle...</span>
                    </div>
                  ) : (
                    <div className="bg-card  p-2.5 rounded flex flex-col gap-1.5 animate-fadeIn">
                      <div className="flex justify-between items-center border-b pb-1">
                        <span className="vdl-body text-slate-500 font-semibold">REPLAY SUMMARY</span>
                        <span className={`px-1.5 py-0.5 rounded vdl-body font-semibold${
                          isWinner ? "bg-emerald-950/40 text-emerald-400 border border-emerald-800/30" : "bg-rose-950/40 text-rose-400 border border-rose-800/30"
                        }`}>
                          {isWinner ? "WINNER" : "LOSER"}
                        </span>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-x-2 gap-y-1 vdl-body text-slate-400">
                        <div className="flex justify-between">
                          <span className="text-slate-600">Net Profit:</span>
                          <span className={`font-semibold${isWinner ? "text-emerald-400" : "text-rose-400"}`}>₹{replayTrade.net_pnl.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-600">Charges:</span>
                          <span className="text-rose-400">₹{replayTrade.charges.total_charges.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-600">Max Excurs (MFE):</span>
                          <span className="text-emerald-400 font-semibold">₹{maxRunUp.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-600">Max Advers (MAE):</span>
                          <span className="text-rose-400 font-semibold">₹{maxDrawdown.toFixed(2)}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

            </div>
          </div>
        );
      })()}
      {!isReplayMode && <div className="contents">
          {/* Tabs selectors with high legibility title */}
          <div className="flex items-center justify-between border-b bg-deep/50 px-4 py-2 shrink-0 select-none font-sans">
            <div className="flex items-center gap-6">
              <span className="section font-medium text-slate-300">Backtest ledger & analytics</span>
              
              <SegmentedTabs
                tabs={tabs.map(t => ({ id: t.id, label: t.name }))}
                activeTabId={activeTab}
                onChange={(id) => setActiveTab(id as any)}
              />
            </div>

        {selectedInspectorParams && (
          <div className="flex items-center gap-2 bg-cyan-950/40 border border-cyan-500/20 px-2 py-0.5 rounded vdl-body font-mono text-cyan-300 animate-pulse">
            <Sliders className="w-3 h-3 text-cyan-400" />
            <span>INSPECTING: {JSON.stringify(selectedInspectorParams)}</span>
            <button
              onClick={() => {
                setSelectedInspectorParams(null);
                runV2Backtest(); // Reload original backtest
              }}
              className="vdl-body text-slate-400 hover:text-slate-200 font-semibold ml-1 border-l pl-1 cursor-pointer transition-colors"
            >
              Clear
            </button>
          </div>
        )}
      </div>

      {/* Tabs Container */}
      <div className="flex-1 overflow-y-auto p-4 scrollbar-thin scrollbar-thumb-white/5 scrollbar-track-transparent min-h-0">
            {activeTab === "overview" && (
              <div className="flex flex-col gap-4 select-none w-full">
                
                {/* Hero KPI Strip */}
                <div className="w-full panel p-4 flex flex-col gap-1.5 justify-center font-sans">
                  <div className="grid grid-cols-12 items-center gap-4">
                    {/* Hero metric: Net profit */}
                    <div className="col-span-4 flex flex-col justify-center border-r pr-4">
                      <span className="vdl-body text-slate-500 font-medium">Net profit</span>
                      <span className={`font-mono text-4xl font-semibold tabular-nums${netProfit >= 0 ? "text-emerald-400" : "text-rose-500"}`}>
                        ₹{netProfit.toLocaleString("en-IN")}
                      </span>
                    </div>

                    {/* Secondary Metrics */}
                    <div className="col-span-8 grid grid-cols-4 gap-4 pl-2">
                      <div className="flex flex-col justify-center">
                        <span className="vdl-body text-slate-500 font-medium">Sharpe ratio</span>
                        <span className="text-cyan-neon font-mono display font-semibold tabular-nums">
                          {sharpe.toFixed(2)}
                        </span>
                      </div>
                      <div className="flex flex-col justify-center">
                        <span className="vdl-body text-slate-500 font-medium">Win rate</span>
                        <span className="text-slate-100 font-mono display font-semibold tabular-nums">
                          {winRate.toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex flex-col justify-center">
                        <span className="vdl-body text-slate-500 font-medium">Max drawdown</span>
                        <span className="text-rose-500 font-mono display font-semibold tabular-nums">
                          -{Math.abs(maxDrawdown).toFixed(2)}%
                        </span>
                      </div>
                      <div className="flex flex-col justify-center">
                        <span className="vdl-body text-slate-500 font-medium">Expectancy</span>
                        <span className={`font-mono display font-semibold tabular-nums${
                          (report?.performance?.expectancy || report?.performance?.avg_trade || 0) >= 0 ? "text-emerald-450" : "text-rose-500"
                        }`}>
                          ₹{(report?.performance?.expectancy || report?.performance?.avg_trade || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Bottom Section: Recent Trades table on left, Equity Curve visual on right */}
                <div className="grid grid-cols-12 gap-5 w-full">
                  {/* Recent Trades Section */}
                  <div className="col-span-8 flex flex-col gap-3.5 panel p-4">
                    <div className="flex justify-between items-center border-b pb-2">
                      <span className="section font-medium text-slate-300">Recent trades</span>
                      <button 
                        onClick={() => setActiveTab("trades")}
                        className="vdl-body text-cyan-neon font-semibold hover:text-white transition-colors cursor-pointer"
                      >
                        View full trade ledger &rarr;
                      </button>
                    </div>

                    <div className="overflow-x-auto">
                      <DataTable
                        columns={recentTradesColumns}
                        data={v2Result?.trades.slice(0, 5) || []}
                        emptyState={
                          <span className="text-[12px] font-sans text-slate-500">
                            No recent trades executed in this backtest.
                          </span>
                        }
                      />
                    </div>
                  </div>

                  {/* Equity Curve Visual Card */}
                  <div className="col-span-4 bg-[#111625]  p-4 rounded-md flex flex-col justify-between shadow-sm min-h-[170px]">
                    <div className="flex justify-between items-center mb-2">
                      <span className="vdl-body text-slate-400 font-semibold">Equity Curve</span>
                      <span className="vdl-body font-mono text-slate-500">Compounding growth</span>
                    </div>
                    
                    {/* Glowing Compound curve SVG representation */}
                    <div className="flex-1 flex items-center justify-center">
                      <svg className="w-full h-full min-h-[110px]" viewBox="0 0 500 150">
                        <defs>
                          <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.25"/>
                            <stop offset="100%" stopColor="#3B82F6" stopOpacity="0.0"/>
                          </linearGradient>
                        </defs>
                        {/* Grid lines */}
                        <line x1="0" y1="30" x2="500" y2="30" stroke="rgba(255,255,255,0.02)" strokeWidth="1" />
                        <line x1="0" y1="75" x2="500" y2="75" stroke="rgba(255,255,255,0.02)" strokeWidth="1" />
                        <line x1="0" y1="120" x2="500" y2="120" stroke="rgba(255,255,255,0.02)" strokeWidth="1" />
                        
                        {/* Trend path */}
                        <path
                          d="M 0 135 C 40 138, 80 115, 120 120 C 160 125, 200 95, 240 85 C 280 75, 320 65, 360 62 C 400 58, 440 40, 500 20"
                          fill="none"
                          stroke="#3B82F6"
                          strokeWidth="2.5"
                        />
                        <path
                          d="M 0 135 C 40 138, 80 115, 120 120 C 160 125, 200 95, 240 85 C 280 75, 320 65, 360 62 C 400 58, 440 40, 500 20 L 500 150 L 0 150 Z"
                          fill="url(#equityGradient)"
                        />
                        <circle cx="500" cy="20" r="3.5" fill="#3B82F6" className="animate-pulse" />
                      </svg>
                    </div>
                  </div>
                </div>

              </div>
            )}

            {/* Trade List Tab */}
            {activeTab === "trades" && (
              <div className="flex gap-4 h-full min-h-[300px]">
                <div className="flex-1 overflow-x-auto">
                  <DataTable
                    columns={tradeLedgerColumns}
                    data={v2Result?.trades || []}
                    onRowClick={(row) => setSelectedTradeId(row.position_id)}
                    rowClassName={(row) => selectedTradeId === row.position_id ? "!bg-cyan-500/10" : ""}
                    emptyState={
                      <EmptyState
                        icon={TrendingUp}
                        title="No Backtest Dataset Loaded"
                        description="Click 'Run Backtest' in the parameter cockpit to run simulation."
                      />
                    }
                  />
                </div>

                {/* Trade Inspector Panel */}
                {(() => {
                  if (!selectedTradeId) return null;
                  const selectedTrade = v2Result?.trades.find(t => t.position_id === selectedTradeId);
                  if (!selectedTrade) return null;
                  
                  const tradeIndex = v2Result?.trades.findIndex(t => t.position_id === selectedTradeId) ?? -1;
                  const isWinner = selectedTrade.net_pnl > 0;
                  
                  const entryMarker = v2Result?.chart_trades?.find(x => x.id === `${selectedTrade.position_id}_entry`);
                  const exitMarker = v2Result?.chart_trades?.find(x => x.id === `${selectedTrade.position_id}_exit`);

                  const strike = entryMarker?.strike || "N/A";
                  const expiry = entryMarker?.expiry || "N/A";
                  const optionType = entryMarker?.option_type || "N/A";
                  const buyReason = entryMarker?.reason || "Signal reason not yet recorded";
                  const sellReason = exitMarker?.reason || "Signal reason not yet recorded";
                  const strategyName = v2Config.strategy_name || "EMA Crossover Strategy";

                  return (
                    <div className="w-80 bg-card/45 p-3.5 rounded shadow-lg shrink-0 flex flex-col gap-3 relative min-h-[300px]">
                      {/* Close Button */}
                      <button 
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedTradeId(null);
                        }}
                        className="absolute top-2.5 right-2.5 text-slate-500 hover:text-slate-300 cursor-pointer"
                        title="Close Inspector"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>

                      {/* Inspector Header */}
                      <div className="text-slate-400 font-semibold vdl-body block mb-1 border-b pb-1 flex items-center justify-between">
                        <span>Trade #{tradeIndex + 1} Inspector</span>
                        <span className={`px-1.5 py-0.5 rounded vdl-body font-semibold${
                          isWinner ? "bg-emerald-950/40 text-emerald-400 border border-emerald-800/30" : "bg-rose-950/40 text-rose-400 border border-rose-800/30"
                        }`}>
                          {isWinner ? "WINNER" : "LOSER"}
                        </span>
                      </div>

                      <div className="flex flex-col gap-0.5">
                        <span className="text-[12px] font-semibold text-slate-100">{selectedTrade.contract}</span>
                        <span className={`body font-mono font-semibold${isWinner ? "text-emerald-400" : "text-rose-400"}`}>
                          {isWinner ? "+" : ""}₹{selectedTrade.net_pnl.toFixed(2)} Net PnL
                        </span>
                      </div>

                      {/* Scrollable details container */}
                      <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-2.5 max-h-[340px] scrollbar-thin scrollbar-thumb-white/5">
                        {/* Position Details Group */}
                        <div className="bg-card/30 p-2 rounded  flex flex-col gap-1.5">
                          <span className="text-cyan-400/80 font-semibold vdl-body">Position Details</span>
                          <div className="grid grid-cols-2 gap-x-3 gap-y-1 vdl-body">
                            <div className="flex justify-between">
                              <span className="text-slate-500">Strike:</span>
                              <span className="text-slate-300 font-mono">{strike}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500">Expiry:</span>
                              <span className="text-slate-300 font-mono">{expiry}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500">Type:</span>
                              <span className="text-slate-300 font-mono font-semibold text-cyan-400">{optionType}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500">Qty:</span>
                              <span className="text-slate-300 font-mono">{selectedTrade.quantity}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500">Entry:</span>
                              <span className="text-slate-300 font-mono">₹{selectedTrade.entry_premium.toFixed(2)}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500">Exit:</span>
                              <span className="text-slate-300 font-mono">₹{selectedTrade.exit_premium.toFixed(2)}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500">Gross:</span>
                              <span className={`font-mono font-semibold${selectedTrade.gross_pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                                ₹{selectedTrade.gross_pnl.toFixed(2)}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500">Charges:</span>
                              <span className="text-rose-400 font-mono">₹{selectedTrade.charges.total_charges.toFixed(2)}</span>
                            </div>
                          </div>
                        </div>

                        {/* Execution Timing Group */}
                        <div className="bg-card/30 p-2 rounded  flex flex-col gap-1.5">
                          <span className="text-cyan-400/80 font-semibold vdl-body">Execution Timing</span>
                          <div className="flex flex-col gap-1 vdl-body">
                            <div className="flex justify-between">
                              <span className="text-slate-500">Entry Time:</span>
                              <span className="text-slate-300 font-mono">{new Date(selectedTrade.entry_time).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500">Exit Time:</span>
                              <span className="text-slate-300 font-mono">{new Date(selectedTrade.exit_time).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500">Duration:</span>
                              <span className="text-amber-400 font-mono font-semibold">{getHoldingDuration(selectedTrade.entry_time, selectedTrade.exit_time)}</span>
                            </div>
                          </div>
                        </div>

                        {/* Signals Group */}
                        <div className="bg-card/30 p-2 rounded  flex flex-col gap-1.5">
                          <span className="text-cyan-400/80 font-semibold vdl-body">Signal Information</span>
                          <div className="flex flex-col gap-1.5 vdl-body">
                            <div className="flex justify-between">
                              <span className="text-slate-500">Strategy:</span>
                              <span className="text-slate-300 font-semibold">{strategyName}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500">Signal Type:</span>
                              <span className="text-slate-300 font-mono">{optionType}</span>
                            </div>
                            <div className="flex flex-col gap-0.5 border-t pt-1 mt-0.5">
                              <span className="text-slate-500 vdl-body font-semibold">Buy Reason:</span>
                              <span className="text-slate-400 italic vdl-body bg-card/40 p-1.5 rounded mt-0.5 select-text leading-normal">
                                {buyReason}
                              </span>
                            </div>
                            <div className="flex flex-col gap-0.5">
                              <span className="text-slate-500 vdl-body font-semibold">Sell Reason:</span>
                              <span className="text-slate-400 italic vdl-body bg-card/40 p-1.5 rounded mt-0.5 select-text leading-normal">
                                {sellReason}
                              </span>
                            </div>
                            <div className="flex justify-between border-t pt-1 mt-0.5">
                              <span className="text-slate-500">Entry Signal Time:</span>
                              <span className="text-slate-300 font-mono vdl-body">
                                {entryMarker?.timestamp ? new Date(entryMarker.timestamp).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) + " IST" : "Signal reason not yet recorded"}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500">Exit Signal Time:</span>
                              <span className="text-slate-300 font-mono vdl-body">
                                {exitMarker?.timestamp ? new Date(exitMarker.timestamp).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) + " IST" : "Signal reason not yet recorded"}
                              </span>
                            </div>
                          </div>
                        </div>
                        {/* Dynamic Trade Replay CTA */}
                        <button
                          onClick={() => {
                            setIsReplayMode(true);
                            setReplayTradeId(selectedTradeId);
                            const entryTime = Math.floor(new Date(selectedTrade.entry_time).getTime() / 1000);
                            setReplayCurrentTime(entryTime);
                          }}
                          className="w-full bg-cyan-500 hover:bg-cyan-400 active:bg-cyan-600 text-slate-950 font-semibold py-2 rounded vdl-body flex items-center justify-center gap-1.5 transition-all shadow-md mt-2 cursor-pointer transition-colors"
                        >
                          <Play className="w-3.5 h-3.5 fill-current" />
                          Replay Trade
                        </button>
                      </div>
                    </div>
                  );
                })()}
              </div>
            )}

            {/* Equity Curve Tab */}
            {activeTab === "equity" && (
              <div className="w-full h-36 relative">
                {v2Result ? (
                  <div ref={equityContainerRef} className="w-full h-full" />
                ) : (
                  <div className="empty-state w-full h-full">
                    <span>No active equity curve. Click "Run Backtest" to plot compounding curve.</span>
                  </div>
                )}
              </div>
            )}

            {/* Drawdown Tab */}
            {activeTab === "drawdown" && (
              <div className="w-full h-36 relative">
                {v2Result ? (
                  <div ref={drawdownContainerRef} className="w-full h-full" />
                ) : (
                  <div className="empty-state w-full h-full">
                    <span>No active drawdown curve. Click "Run Backtest" to plot drawdowns.</span>
                  </div>
                )}
              </div>
            )}

            {/* Metrics Tab */}
            {activeTab === "metrics" && (
              !report ? (
                <div className="empty-state py-8">
                  <span>No metrics calculated. Click "Run Backtest" in the parameter cockpit to run simulation.</span>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-4 max-w-3xl font-mono vdl-body select-none">
                  <div className="flex flex-col gap-1.5">
                    <div className="flex justify-between border-b py-1">
                      <span className="text-slate-500">NET PROFIT:</span>
                      <span className="text-emerald-400 font-semibold">₹{report.performance.net_profit.toLocaleString("en-IN")}</span>
                    </div>
                    <div className="flex justify-between border-b py-1">
                      <span className="text-slate-500">GROSS PROFIT:</span>
                      <span className="text-slate-300 font-semibold">₹{report.performance.gross_profit.toLocaleString("en-IN")}</span>
                    </div>
                    <div className="flex justify-between border-b py-1">
                      <span className="text-slate-500">GROSS LOSS:</span>
                      <span className="text-rose-400 font-semibold">₹{report.performance.gross_loss.toLocaleString("en-IN")}</span>
                    </div>
                    <div className="flex justify-between border-b py-1">
                      <span className="text-slate-500">PROFIT FACTOR:</span>
                      <span className="text-slate-300 font-semibold">{report.performance.profit_factor.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between border-b py-1">
                      <span className="text-slate-500">EXPECTANCY:</span>
                      <span className="text-slate-300 font-semibold">₹{report.performance.expectancy.toFixed(2)}</span>
                    </div>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <div className="flex justify-between border-b py-1">
                      <span className="text-slate-500">SHARPE RATIO:</span>
                      <span className="text-cyan-400 font-semibold">{report.sharpe_ratio.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between border-b py-1">
                      <span className="text-slate-500">SORTINO RATIO:</span>
                      <span className="text-cyan-400 font-semibold">{report.sortino_ratio.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between border-b py-1">
                      <span className="text-slate-500">MAX DRAWDOWN:</span>
                      <span className="text-rose-400 font-semibold">-{report.max_drawdown_pct.toFixed(2)}%</span>
                    </div>
                    <div className="flex justify-between border-b py-1">
                      <span className="text-slate-500">WIN RATE / LOSS RATE:</span>
                      <span className="text-slate-300 font-semibold">{report.trade_stats.win_rate.toFixed(1)}% / {report.trade_stats.loss_rate.toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between border-b py-1">
                      <span className="text-slate-500">STREAK WINS / LOSSES:</span>
                      <span className="text-slate-300 font-semibold">{report.performance.max_consecutive_wins} wins / {report.performance.max_consecutive_losses} losses</span>
                    </div>
                  </div>
                </div>
              )
            )}

            {/* Runtime Logs Tab */}
            {activeTab === "runtime" && (
              <div className="flex flex-col gap-3 font-sans h-full min-h-[350px]">
                {/* Filters Header */}
                <div className="flex flex-wrap items-center justify-between gap-2 border-b pb-2 shrink-0 select-none">
                  {/* Category Pills */}
                  <div className="flex flex-wrap gap-1">
                    {["ALL", "SYSTEM", "SIGNAL", "POSITION", "PNL", "METRICS", "ERROR"].map((cat) => {
                      const isActive = logCategoryFilter === cat;
                      let badgeStyle = "text-slate-400 hover:text-slate-300 hover:bg-card border-transparent";
                      if (isActive) {
                        if (cat === "ALL") badgeStyle = "bg-slate-800 text-white border-slate-700";
                        else if (cat === "SYSTEM") badgeStyle = "bg-blue-500/10 text-blue-400 border-blue-500/20";
                        else if (cat === "SIGNAL") badgeStyle = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
                        else if (cat === "POSITION") badgeStyle = "bg-cyan-500/10 text-cyan-400 border-cyan-500/20";
                        else if (cat === "PNL") badgeStyle = "bg-purple-500/10 text-purple-400 border-purple-500/20";
                        else if (cat === "METRICS") badgeStyle = "bg-amber-500/10 text-amber-400 border-amber-500/20";
                        else if (cat === "ERROR") badgeStyle = "bg-rose-500/10 text-rose-400 border-rose-500/20";
                      }
                      return (
                        <button
                          key={cat}
                          onClick={() => {
                            setLogCategoryFilter(cat);
                            setExpandedLogId(null);
                          }}
                          className={`body font-semibold px-2 py-0.5 border rounded transition-all duration-150 cursor-pointer${badgeStyle}`}
                        >
                          {cat}
                        </button>
                      );
                    })}
                  </div>

                  {/* Search input */}
                  <div className="relative">
                    <input
                      type="text"
                      placeholder="Search execution logs..."
                      value={logSearchQuery}
                      onChange={(e) => setLogSearchQuery(e.target.value)}
                      className="vdl-body w-48 bg-card  px-2 py-1 pl-6 rounded text-slate-300 placeholder-slate-500 outline-none focus:border-cyan-500/40 transition-all duration-150"
                    />
                    <svg className="w-3 h-3 absolute left-2 top-2 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                    </svg>
                    {logSearchQuery && (
                      <button
                        onClick={() => setLogSearchQuery("")}
                        className="absolute right-2 top-1 text-slate-500 hover:text-slate-300"
                      >
                        ×
                      </button>
                    )}
                  </div>
                </div>

                {/* Console Output Scroll Box */}
                <div className="flex-1 overflow-y-auto max-h-96 min-h-[300px] font-mono vdl-body text-slate-300 bg-card/80  rounded-lg p-2.5 scrollbar-thin scrollbar-thumb-white/5 scrollbar-track-transparent">
                  {v2Result?.runtime_logs && v2Result.runtime_logs.length > 0 ? (
                    (() => {
                      const filtered = v2Result.runtime_logs.filter(log => {
                        const matchCat = logCategoryFilter === "ALL" || log.category.toUpperCase() === logCategoryFilter.toUpperCase();
                        const matchSearch = !logSearchQuery || 
                          log.message.toLowerCase().includes(logSearchQuery.toLowerCase()) ||
                          log.category.toLowerCase().includes(logSearchQuery.toLowerCase());
                        return matchCat && matchSearch;
                      });

                      if (filtered.length === 0) {
                        return <div className="empty-state">No logs match active filters.</div>;
                      }

                      return filtered.map((log, idx) => {
                        const isExpanded = expandedLogId === idx;
                        const hasMetadata = log.metadata && Object.keys(log.metadata).length > 0;
                        const logTime = new Date(log.timestamp).toLocaleTimeString("en-US", { hour12: false });
                        
                        let catBadge = "text-slate-400 border-slate-700/30 bg-slate-800/10";
                        let textStyle = "text-slate-300";
                        if (log.category === "SYSTEM") {
                          catBadge = "text-blue-400 border-blue-500/20 bg-blue-500/5";
                          textStyle = "text-blue-200/90";
                        } else if (log.category === "SIGNAL") {
                          catBadge = "text-emerald-400 border-emerald-500/20 bg-emerald-500/5";
                          textStyle = "text-emerald-200/90 font-bold";
                        } else if (log.category === "POSITION") {
                          catBadge = "text-cyan-400 border-cyan-500/20 bg-cyan-500/5";
                          textStyle = "text-cyan-200/90";
                        } else if (log.category === "PNL") {
                          catBadge = "text-purple-400 border-purple-500/20 bg-purple-500/5";
                          textStyle = "text-purple-200/90";
                        } else if (log.category === "METRICS") {
                          catBadge = "text-amber-400 border-amber-500/20 bg-amber-500/5";
                          textStyle = "text-amber-200/90 font-bold";
                        } else if (log.category === "ERROR") {
                          catBadge = "text-rose-400 border-rose-500/20 bg-rose-500/5";
                          textStyle = "text-rose-200/90 font-bold";
                        }

                        return (
                          <div key={idx} className="border-b last:border-0">
                            {/* Log Row */}
                            <div 
                              onClick={() => hasMetadata && setExpandedLogId(isExpanded ? null : idx)}
                              className={`flex items-start gap-2.5 py-1 px-1.5 hover:bg-white/5 transition-all duration-100 rounded cursor-pointer select-none${isExpanded ? 'bg-white/5' : ''}`}
                            >
                              {/* Timestamp */}
                              <span className="text-slate-500 shrink-0 select-none vdl-body">{logTime}</span>
                              
                              {/* Category Badge */}
                              <span className={`px-1.5 py-0.5 vdl-body font-semibold border rounded shrink-0 select-none${catBadge}`}>
                                {log.category}
                              </span>

                              {/* Message */}
                              <span className={`flex-1 break-all${textStyle}`}>
                                {log.message}
                              </span>

                              {/* Expansion Indicator */}
                              {hasMetadata && (
                                <span className="text-slate-500 vdl-body shrink-0 font-semibold select-none hover:text-slate-300">
                                  {isExpanded ? "▼ METADATA" : "▶ METADATA"}
                                </span>
                              )}
                            </div>

                            {/* Metadata Expandable Block */}
                            {isExpanded && hasMetadata && (
                              <div className="bg-card border-x border-b p-3 mx-1.5 mb-1.5 rounded-b vdl-body text-slate-400 max-h-48 overflow-y-auto">
                                <div className="text-cyan-400/80 font-semibold vdl-body mb-1.5">Payload Details:</div>
                                <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                                  {Object.entries(log.metadata).map(([key, val]) => (
                                    <div key={key} className="flex border-b py-0.5 last:border-0">
                                      <span className="text-slate-500 font-semibold w-24 shrink-0">{key}:</span>
                                      <span className="text-slate-300 break-all vdl-body">
                                        {typeof val === "object" ? JSON.stringify(val) : String(val)}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      });
                    })()
                  ) : logs && logs.length > 0 ? (
                    // Fallback to legacy string logs
                    logs.map((log, idx) => (
                      <div key={idx} className="py-0.5 border-b last:border-0">{log}</div>
                    ))
                  ) : (
                    <div className="text-slate-500 italic p-6 text-center select-none">No logs available. Click "Run Backtest" or "Run Parameter Sweep" to begin.</div>
                  )}
                </div>
              </div>
            )}

        {/* Optimization Tab */}
        {activeTab === "optimization" && (
          <div className="flex flex-col h-full min-h-0 vdl-body font-sans">
            {/* Tab navigation inside Optimization */}
            <div className="flex gap-1.5 mb-3.5 border-b pb-1 select-none shrink-0">
              <button
                onClick={() => setOptTab("setup")}
                className={`px-3 py-1.5 font-semibold vdl-body rounded-t transition-all cursor-pointer${
                  optTab === "setup" ? "bg-card/60 border-t border-x text-cyan-400" : "text-slate-500 hover:text-slate-300"
                }`}
              >
                Configuration
              </button>
              <button
                onClick={() => setOptTab("ranked")}
                disabled={!v2OptimizationReport}
                className={`px-3 py-1.5 font-semibold vdl-body rounded-t transition-all cursor-pointer disabled:opacity-30${
                  optTab === "ranked" ? "bg-card/60 border-t border-x text-cyan-400" : "text-slate-500 hover:text-slate-300"
                }`}
              >
                Ranked Combinations
              </button>
              <button
                onClick={() => setOptTab("heatmap")}
                disabled={!v2OptimizationReport}
                className={`px-3 py-1.5 font-semibold vdl-body rounded-t transition-all cursor-pointer disabled:opacity-30${
                  optTab === "heatmap" ? "bg-card/60 border-t border-x text-cyan-400" : "text-slate-500 hover:text-slate-300"
                }`}
              >
                Heatmap Analytics
              </button>
            </div>

            {/* Sweep setup panel */}
            {optTab === "setup" && (
              <div className="grid grid-cols-2 gap-4 max-w-2xl select-none">
                <div className="flex flex-col gap-3.5 bg-card/10  p-4 rounded shadow-sm">
                  <span className="text-cyan-400 font-semibold vdl-body block border-b pb-1.5 mb-1.5 flex items-center gap-1.5">
                    <SlidersHorizontal className="w-3.5 h-3.5 text-cyan-400/80" />
                    <span>Fast EMA Sweep Range</span>
                  </span>
                  <div className="grid grid-cols-3 gap-2.5">
                    <div className="flex flex-col gap-1.5">
                      <span className="text-slate-500 vdl-body font-semibold">Min</span>
                      <input
                        type="number"
                        value={fastEmaStart}
                        onChange={(e) => setFastEmaStart(Number(e.target.value))}
                        className="bg-card  hover:border-cyan-500/20 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500/40 transition-all font-mono font-medium vdl-body"
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <span className="text-slate-500 vdl-body font-semibold">Max</span>
                      <input
                        type="number"
                        value={fastEmaEnd}
                        onChange={(e) => setFastEmaEnd(Number(e.target.value))}
                        className="bg-card  hover:border-cyan-500/20 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500/40 transition-all font-mono font-medium vdl-body"
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <span className="text-slate-500 vdl-body font-semibold">Step</span>
                      <input
                        type="number"
                        value={fastEmaStep}
                        onChange={(e) => setFastEmaStep(Number(e.target.value))}
                        className="bg-card  hover:border-cyan-500/20 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500/40 transition-all font-mono font-medium vdl-body"
                      />
                    </div>
                  </div>
                </div>

                <div className="flex flex-col gap-3.5 bg-card/10  p-4 rounded shadow-sm">
                  <span className="text-cyan-400 font-semibold vdl-body block border-b pb-1.5 mb-1.5 flex items-center gap-1.5">
                    <SlidersHorizontal className="w-3.5 h-3.5 text-cyan-400/80" />
                    <span>Slow EMA Sweep Range</span>
                  </span>
                  <div className="grid grid-cols-3 gap-2.5">
                    <div className="flex flex-col gap-1.5">
                      <span className="text-slate-500 vdl-body font-semibold">Min</span>
                      <input
                        type="number"
                        value={slowEmaStart}
                        onChange={(e) => setSlowEmaStart(Number(e.target.value))}
                        className="bg-card  hover:border-cyan-500/20 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500/40 transition-all font-mono font-medium vdl-body"
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <span className="text-slate-500 vdl-body font-semibold">Max</span>
                      <input
                        type="number"
                        value={slowEmaEnd}
                        onChange={(e) => setSlowEmaEnd(Number(e.target.value))}
                        className="bg-card  hover:border-cyan-500/20 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500/40 transition-all font-mono font-medium vdl-body"
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <span className="text-slate-500 vdl-body font-semibold">Step</span>
                      <input
                        type="number"
                        value={slowEmaStep}
                        onChange={(e) => setSlowEmaStep(Number(e.target.value))}
                        className="bg-card  hover:border-cyan-500/20 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500/40 transition-all font-mono font-medium vdl-body"
                      />
                    </div>
                  </div>
                </div>

                <div className="flex justify-between items-center bg-card/10  p-4 rounded col-span-2 mt-2 shadow-sm">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-400 font-semibold vdl-body">Parallel Threads:</span>
                    <input
                      type="number"
                      value={workerCount}
                      onChange={(e) => setWorkerCount(Number(e.target.value))}
                      className="bg-card  hover:border-cyan-500/20 rounded w-16 px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500/40 transition-all font-mono font-medium"
                    />
                  </div>

                  <button
                    onClick={handleRunOptimization}
                    disabled={isOptimizationLoading}
                    className="bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 font-semibold px-5 py-2 rounded transition-all cursor-pointer vdl-body shadow-lg shadow-cyan-500/15"
                  >
                    {isOptimizationLoading ? "Running Sweep..." : "Run Parameter Sweep"}
                  </button>
                </div>
              </div>
            )}

            {/* Ranked combinations */}
            {optTab === "ranked" && v2OptimizationReport && (
              <div className="flex flex-col gap-3">
                <div className="flex justify-between items-center select-none bg-card/20 p-2 rounded ">
                  <div className="flex gap-2">
                    {(["top10", "top25", "top50"] as const).map((f) => (
                      <button
                        key={f}
                        onClick={() => setRankedFilter(f)}
                        className={`px-3 py-1 rounded border vdl-body font-mono cursor-pointer font-semibold transition-all${
                          rankedFilter === f
                            ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400"
                            : "bg-card text-slate-500 hover:text-slate-400"
                        }`}
                      >
                        {f.toUpperCase()}
                      </button>
                    ))}
                  </div>
                  <span className="text-slate-500 vdl-body font-mono">
                    Executed: <span className="text-slate-300 font-semibold">{v2OptimizationReport.run_info.executed_combinations}</span> runs | Skipped: <span className="text-slate-300 font-semibold">{v2OptimizationReport.run_info.skipped_combinations}</span>
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <DataTable
                    columns={optimizationColumns}
                    data={getRankedList()}
                    onRowClick={(row) => handleInspectParams(row.combination.params)}
                    rowClassName={(row) => {
                      const paramsKey = JSON.stringify(row.combination.params);
                      return JSON.stringify(selectedInspectorParams) === paramsKey ? "!bg-cyan-500/10" : "";
                    }}
                    emptyState={
                      <span className="text-[12px] font-sans text-slate-500">
                        No optimization runs completed yet.
                      </span>
                    }
                  />
                </div>
              </div>
            )}

            {/* Heatmap visualization */}
            {optTab === "heatmap" && v2OptimizationReport && (
              <div className="flex flex-col gap-3 text-slate-400">
                <div className="flex justify-between items-center select-none shrink-0 bg-card/20 p-2 rounded ">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-400 font-semibold vdl-body">Heatmap Parameter Metric:</span>
                    <select
                      value={heatmapMetric}
                      onChange={(e: any) => setHeatmapMetric(e.target.value)}
                      className="bg-card  hover:border-cyan-500/20 rounded px-2.5 py-1 text-slate-200 focus:outline-none focus:border-cyan-500/40 transition-all cursor-pointer font-medium"
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
                  <div className="bg-card/45 p-4 rounded flex-1 overflow-x-auto">
                    <div className="flex flex-col gap-1.5 min-w-[300px]">
                      {/* X values label header */}
                      <div className="flex">
                        <div className="w-16 font-mono vdl-body text-slate-500 flex items-center justify-end pr-2.5 font-semibold">
                          Slow \ Fast
                        </div>
                        <div className="flex-1 flex gap-1.5">
                          {v2OptimizationReport.heatmap_data.x_values.map((xVal) => (
                            <div key={xVal} className="flex-1 text-center font-mono font-semibold vdl-body text-cyan-500/80">
                              F:{xVal}
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Matrix Rows */}
                      {v2OptimizationReport.heatmap_data.y_values.map((yVal, yIdx) => (
                        <div key={yVal} className="flex">
                          {/* Y Label */}
                          <div className="w-16 font-mono font-semibold vdl-body text-slate-500 flex items-center justify-end pr-2.5">
                            S:{yVal}
                          </div>
                          
                          {/* Cell row */}
                          <div className="flex-1 flex gap-1.5">
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
                              let cellBg = "bg-card/40";
                              if (cellVal > 0) {
                                const maxVal = Math.max(1, ...v2OptimizationReport.top_10.map(r => r[heatmapMetric] || 1));
                                const pct = Math.min(1, cellVal / maxVal);
                                if (pct > 0.75) cellBg = "bg-cyan-500 text-slate-950 font-bold border-cyan-400";
                                else if (pct > 0.5) cellBg = "bg-cyan-600/80 text-white font-semibold border-cyan-500/30";
                                else if (pct > 0.25) cellBg = "bg-cyan-800/50 text-cyan-300 border-cyan-800/20";
                                else cellBg = "bg-cyan-950/30 text-cyan-400/70";
                              } else if (cellVal < 0) {
                                cellBg = "bg-rose-950/20 text-rose-400/80 border-rose-950/30";
                              }

                              return (
                                <div
                                  key={xVal}
                                  onClick={() => handleInspectParams({ fastEma: xVal, slowEma: yVal })}
                                  title={`Fast: ${xVal}, Slow: ${yVal} | ${heatmapMetric}: ${cellVal}`}
                                  className={`flex-1 aspect-[1.8] rounded border flex items-center justify-center font-mono vdl-body cursor-pointer transition-all hover:scale-105 select-none${cellBg}`}
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
                  <div className="w-60 flex flex-col gap-2.5 shrink-0">
                    <div className="bg-card/10  p-3.5 rounded shadow-sm">
                      <span className="text-slate-400 vdl-body font-semibold block mb-2 border-b pb-1">
                        Cell Parameter Inspector
                      </span>
                      {selectedInspectorParams ? (
                        <div className="flex flex-col gap-2.5">
                          <div className="font-mono text-cyan-400 font-semibold border-b pb-1 select-text">
                            Fast: {selectedInspectorParams.fastEma} | Slow: {selectedInspectorParams.slowEma}
                          </div>
                          {report && (
                            <div className="flex flex-col gap-1.5 select-none">
                              <div className="flex justify-between">
                                <span className="text-slate-500">Net Profit:</span>
                                <span className="text-emerald-400 font-semibold font-mono">₹{report.performance.net_profit.toLocaleString("en-IN")}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-slate-500">Sharpe Ratio:</span>
                                <span className="text-cyan-400 font-semibold font-mono">{report.sharpe_ratio.toFixed(2)}</span>
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
                        <div className="vdl-body text-slate-500 italic select-none">
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
  }
</div>
);
};
