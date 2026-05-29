"use client";

import React, { useState, useEffect } from "react";
import { 
  Play, Pause, Square, Activity, Server, Zap, Shield, AlertTriangle, 
  Search, Sliders, CheckCircle2, ChevronRight, BarChart2, Cpu, 
  Database, RefreshCw, Terminal, TrendingUp, HelpCircle
} from "lucide-react";
import { useTerminalStore } from "@/store/useTerminalStore";
import { useEventStore } from "@/store/useEventStore";

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
      isPositive === true ? "text-emerald-400" : isPositive === false ? "text-rose-400" : "text-slate-200"
    }`}>{value}</span>
    {subText && <span className="text-[9px] text-slate-500 font-mono">{subText}</span>}
  </div>
);

// MOCK DEPLOYMENTS DATA
interface DeploymentItem {
  id: string;
  name: string;
  version: string;
  status: "Ready For Paper" | "Running" | "Paused" | "Failed" | "Archived";
  promotionState: "Paper Approved" | "Live Approved" | "Draft";
  capitalAllocated: number;
  runtime: string;
  tradeCount: number;
  pnl: number;
  winRate: number;
  drawdown: number;
  exposure: number;
}

const INITIAL_DEPLOYMENTS: DeploymentItem[] = [
  {
    id: "dep_ema",
    name: "EMA Crossover",
    version: "v2.1",
    status: "Running",
    promotionState: "Paper Approved",
    capitalAllocated: 500000,
    runtime: "12d 04h 22m",
    tradeCount: 142,
    pnl: 18450.25,
    winRate: 58.4,
    drawdown: 3.2,
    exposure: 150000,
  },
  {
    id: "dep_mean",
    name: "Bollinger Mean Reversion",
    version: "v1.0",
    status: "Ready For Paper",
    promotionState: "Draft",
    capitalAllocated: 250000,
    runtime: "0d 00h 00m",
    tradeCount: 0,
    pnl: 0.00,
    winRate: 0.0,
    drawdown: 0.0,
    exposure: 0,
  },
  {
    id: "dep_vwap",
    name: "VWAP Breakout Signal",
    version: "v3.4",
    status: "Paused",
    promotionState: "Paper Approved",
    capitalAllocated: 750000,
    runtime: "28d 18h 05m",
    tradeCount: 342,
    pnl: -4250.00,
    winRate: 49.1,
    drawdown: 8.4,
    exposure: 0,
  },
  {
    id: "dep_macd",
    name: "MACD Momentum Trigger",
    version: "v1.2",
    status: "Failed",
    promotionState: "Draft",
    capitalAllocated: 300000,
    runtime: "4d 12h 10m",
    tradeCount: 18,
    pnl: -14500.00,
    winRate: 33.3,
    drawdown: 12.5,
    exposure: 0,
  }
];

// ==========================================
// 1. LEFT PANEL: DEPLOYMENT CENTER
// ==========================================
export const PaperLeft: React.FC = () => {
  const selectedStrategy = useTerminalStore((state) => state.selectedStrategy);
  const setStrategy = useTerminalStore((state) => state.setStrategy);
  
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState<string>("All");

  const handleSelect = (item: DeploymentItem) => {
    setStrategy({
      strategyId: item.id,
      strategyName: item.name,
      version: item.version,
    });
  };

  const filtered = INITIAL_DEPLOYMENTS.filter((dep) => {
    const matchesSearch = dep.name.toLowerCase().includes(search.toLowerCase());
    const matchesFilter = activeFilter === "All" || dep.status === activeFilter;
    return matchesSearch && matchesFilter;
  });

  return (
    <MissionCard title="Deployment Center">
      <div className="flex flex-col gap-2 h-full font-sans text-xs">
        {/* Search */}
        <div className="relative shrink-0">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search deployments..."
            className="w-full bg-slate-900/60 border border-white/5 rounded pl-8 pr-3 py-1.5 text-[11px] text-slate-300 focus:outline-none focus:border-cyan-500/40"
          />
        </div>

        {/* Filter List */}
        <div className="grid grid-cols-2 gap-1 shrink-0 select-none text-[9px] font-bold">
          {["All", "Running", "Paused", "Failed", "Ready For Paper"].map((status) => (
            <button
              key={status}
              onClick={() => setActiveFilter(status)}
              className={`py-1 rounded transition-all cursor-pointer text-center border truncate px-1 ${
                activeFilter === status
                  ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400"
                  : "bg-slate-900 border-white/5 text-slate-500 hover:text-slate-300"
              }`}
            >
              {status}
            </button>
          ))}
        </div>

        {/* Strategy list */}
        <div className="flex-1 overflow-y-auto flex flex-col gap-1.5 mt-2 pr-1 scrollbar-thin scrollbar-thumb-white/5">
          {filtered.map((item) => {
            const isSelected = selectedStrategy?.strategyId === item.id;
            return (
              <div
                key={item.id}
                onClick={() => handleSelect(item)}
                className={`p-2.5 rounded border transition-all cursor-pointer flex flex-col gap-1 relative ${
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
                    {item.version}
                  </span>
                </div>

                <div className="flex justify-between items-center text-[10px] text-slate-500 select-none">
                  <span className={`flex items-center gap-1 text-[9px] font-bold ${
                    item.status === "Running" ? "text-emerald-400" :
                    item.status === "Paused" ? "text-amber-400" :
                    item.status === "Failed" ? "text-rose-400" : "text-slate-400"
                  }`}>
                    <span className={`w-1 h-1 rounded-full ${
                      item.status === "Running" ? "bg-emerald-400 animate-pulse" :
                      item.status === "Paused" ? "bg-amber-400" :
                      item.status === "Failed" ? "bg-rose-400 animate-ping" : "bg-slate-500"
                    }`} />
                    {item.status}
                  </span>
                  <span className="text-[9px] font-mono">Run: {item.runtime.split(" ")[0]}</span>
                </div>
              </div>
            );
          })}
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
  const currentAccount = useTerminalStore((state) => state.currentAccount);
  const addEvent = useEventStore((state) => state.addEvent);

  const [activeDep, setActiveDep] = useState<DeploymentItem | null>(null);
  const [allocation, setAllocation] = useState(500000);

  // Sync details when active strategy swaps
  useEffect(() => {
    if (!selectedStrategy) return;
    const match = INITIAL_DEPLOYMENTS.find((d) => d.id === selectedStrategy.strategyId);
    if (match) {
      setActiveDep(match);
      setAllocation(match.capitalAllocated);
    }
  }, [selectedStrategy]);

  const handleDeploy = () => {
    if (!activeDep) return;
    setActiveDep({ ...activeDep, status: "Running" });
    addEvent({
      type: "success",
      message: `DEPLOYED STRATEGY: ${activeDep.name} on account ${currentAccount?.name || "Paper Account"}`,
      workspace: "Paper",
    });
  };

  const handlePause = () => {
    if (!activeDep) return;
    setActiveDep({ ...activeDep, status: "Paused" });
    addEvent({
      type: "info",
      message: `PAUSED STRATEGY: ${activeDep.name} execution loops suspended`,
      workspace: "Paper",
    });
  };

  const handleStop = () => {
    if (!activeDep) return;
    setActiveDep({ ...activeDep, status: "Ready For Paper" });
    addEvent({
      type: "warning",
      message: `TERMINATED STRATEGY: ${activeDep.name} closed position exposure`,
      workspace: "Paper",
    });
  };

  return (
    <div className="flex flex-col h-full bg-slate-950/60 border border-white/5 rounded-lg overflow-hidden font-sans text-xs">
      
      {/* Top Controls Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-900/50 border-b border-white/5 select-none shrink-0 flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <div className="flex flex-col gap-0.5">
            <span className="text-[8px] text-slate-500 font-bold uppercase">Deployment Target</span>
            <span className="text-cyan-400 font-bold font-mono">
              {activeDep ? `${activeDep.name} ${activeDep.version}` : "No Target Selected"}
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
              disabled={activeDep?.status === "Running"}
              className="bg-slate-900/80 border border-white/10 rounded px-1.5 py-0.5 w-24 text-[10px] text-slate-300 focus:outline-none font-mono disabled:opacity-50"
            />
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleDeploy}
            disabled={!activeDep || activeDep.status === "Running"}
            className="bg-emerald-500 hover:bg-emerald-400 disabled:bg-slate-900 disabled:text-slate-600 disabled:border-white/5 text-slate-950 font-bold px-3 py-1 rounded transition-all cursor-pointer text-center flex items-center gap-1 uppercase text-[10px] border border-transparent"
          >
            <Play className="w-3 h-3 fill-slate-950" />
            Deploy
          </button>
          
          <button
            onClick={handlePause}
            disabled={!activeDep || activeDep.status !== "Running"}
            className="bg-amber-500 hover:bg-amber-400 disabled:bg-slate-900 disabled:text-slate-600 disabled:border-white/5 text-slate-950 font-bold px-3 py-1 rounded transition-all cursor-pointer text-center flex items-center gap-1 uppercase text-[10px] border border-transparent"
          >
            <Pause className="w-3 h-3 fill-slate-950" />
            Pause
          </button>

          <button
            onClick={handleStop}
            disabled={!activeDep || (activeDep.status !== "Running" && activeDep.status !== "Paused")}
            className="bg-rose-500 hover:bg-rose-400 disabled:bg-slate-900 disabled:text-slate-600 disabled:border-white/5 text-slate-950 font-bold px-3 py-1 rounded transition-all cursor-pointer text-center flex items-center gap-1 uppercase text-[10px] border border-transparent"
          >
            <Square className="w-3 h-3 fill-slate-950" />
            Stop
          </button>
        </div>
      </div>

      {/* Main Operational Dials Grid */}
      <div className="flex-1 p-3 overflow-y-auto min-h-0">
        {activeDep ? (
          <div className="flex flex-col gap-4">
            
            {/* Status overview cards */}
            <div className="grid grid-cols-4 gap-3">
              <TelemetryDial 
                label="Strategy Status" 
                value={activeDep.status} 
                subText={`Target: ${currentAccount?.name || "Paper Account"}`}
                isPositive={activeDep.status === "Running" ? true : activeDep.status === "Paused" ? undefined : false}
              />
              <TelemetryDial 
                label="Runtime Counter" 
                value={activeDep.status === "Running" ? "12d 04h 22m" : "0d 00h 00m"} 
                subText="Uptime benchmark" 
              />
              <TelemetryDial 
                label="Simulation Trades" 
                value={activeDep.tradeCount} 
                subText="Total orders closed" 
              />
              <TelemetryDial 
                label="Paper Capital Allocated" 
                value={`₹${allocation.toLocaleString("en-IN")}`} 
                subText={`Exposure: ₹${activeDep.exposure.toLocaleString("en-IN")}`} 
              />
            </div>

            {/* Performance Indicators */}
            <div className="grid grid-cols-3 gap-3">
              <TelemetryDial 
                label="Forward P&L" 
                value={`${activeDep.pnl >= 0 ? "+" : ""}₹${activeDep.pnl.toLocaleString("en-IN")}`} 
                subText="Net simulation yield"
                isPositive={activeDep.pnl >= 0}
              />
              <TelemetryDial 
                label="Simulation Win Rate" 
                value={`${activeDep.winRate}%`} 
                subText="Expectancy: +₹214.50" 
                isPositive={activeDep.winRate >= 50}
              />
              <TelemetryDial 
                label="Drawdown Peak" 
                value={`-${activeDep.drawdown}%`} 
                subText="Max tolerance limit: 10.0%" 
                isPositive={false}
              />
            </div>

            {/* Operational HUD */}
            <div className="bg-slate-950/40 border border-white/5 rounded p-3 font-mono text-[10px] text-slate-400 flex flex-col gap-2">
              <span className="text-[8px] font-bold text-slate-500 uppercase tracking-widest border-b border-white/5 pb-1">
                Active Exposure Positions
              </span>
              <div className="flex justify-between items-center py-1">
                <span>NIFTY26MAY22200CE</span>
                <span className="text-emerald-400 font-bold">LONG 150 Qty @ Avg ₹112.50 (LTP: ₹132.20)</span>
              </div>
              <div className="flex justify-between items-center py-1 border-t border-white/[0.02]">
                <span>Risk Stop loss trigger</span>
                <span className="text-rose-400 font-bold">Limit SL: ₹98.00 (Active Risk: ₹2,175)</span>
              </div>
            </div>

          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 text-[10px] text-center gap-2 select-none">
            <Cpu className="w-8 h-8 text-slate-700 animate-bounce" />
            <span>Select a deployment strategy target from the Left Panel to initialize dashboard telemetry.</span>
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

  const mockStatuses = [
    { label: "Market Feed Feed", val: "ONLINE", ok: true },
    { label: "WebSocket Gateway", val: "CONNECTED", ok: true },
    { label: "Signal Engine Loop", val: "RUNNING", ok: true },
    { label: "Order Simulator", val: "READY", ok: true },
    { label: "Redis Queue Gateway", val: "CONNECTED", ok: true },
    { label: "Matching latency", val: "14ms", ok: true },
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
                  stat.ok ? "bg-emerald-950/40 text-emerald-400" : "bg-rose-950/40 text-rose-400"
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
                  <span className="text-cyan-400 font-bold">1.2s</span>
                </div>
                <div className="flex justify-between">
                  <span>Slippage Index:</span>
                  <span className="text-emerald-400 font-bold">0.01%</span>
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
  const [activeTab, setActiveTab] = useState<"positions" | "orders" | "trades" | "logs" | "events" | "promotion">("positions");

  const tabs = [
    { id: "positions" as const, name: "Positions" },
    { id: "orders" as const, name: "Simulation Orders" },
    { id: "trades" as const, name: "Trades List" },
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
                <th className="py-1 text-right pr-2">PnL</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              <tr className="border-b border-white/[0.02]">
                <td className="py-1.5 pl-2 text-slate-200">NIFTY26MAY22200CE</td>
                <td className="py-1.5 text-emerald-400">LONG</td>
                <td className="py-1.5 text-center">150</td>
                <td className="py-1.5 text-right">₹112.50</td>
                <td className="py-1.5 text-right">₹132.20</td>
                <td className="py-1.5 text-right pr-2 text-emerald-400 font-bold">+₹2,955.00</td>
              </tr>
            </tbody>
          </table>
        )}

        {/* Orders tab */}
        {activeTab === "orders" && (
          <table className="w-full text-left font-mono text-[10px]">
            <thead>
              <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-[8px]">
                <th className="py-1 pl-2">Order ID</th>
                <th className="py-1">Instrument</th>
                <th className="py-1">Side</th>
                <th className="py-1 text-right">Price</th>
                <th className="py-1 text-center">Qty</th>
                <th className="py-1 text-right pr-2">Status</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              <tr className="border-b border-white/[0.02]">
                <td className="py-1.5 pl-2 text-slate-500">ORD_94812</td>
                <td className="py-1.5">NIFTY26MAY22200CE</td>
                <td className="py-1.5 text-emerald-400 font-bold">BUY</td>
                <td className="py-1.5 text-right">₹112.50</td>
                <td className="py-1.5 text-center">150</td>
                <td className="py-1.5 text-right pr-2 text-emerald-400">FILLED</td>
              </tr>
            </tbody>
          </table>
        )}

        {/* Trades list tab */}
        {activeTab === "trades" && (
          <table className="w-full text-left font-mono text-[10px]">
            <thead>
              <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-[8px]">
                <th className="py-1 pl-2">Trade ID</th>
                <th className="py-1">Instrument</th>
                <th className="py-1">Side</th>
                <th className="py-1 text-right">Price</th>
                <th className="py-1 text-center">Qty</th>
                <th className="py-1 text-right pr-2">Execution Time</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              <tr className="border-b border-white/[0.02]">
                <td className="py-1.5 pl-2 text-slate-500">TRD_2841</td>
                <td className="py-1.5">NIFTY26MAY22200CE</td>
                <td className="py-1.5 text-emerald-400 font-bold">BUY</td>
                <td className="py-1.5 text-right">₹112.50</td>
                <td className="py-1.5 text-center">150</td>
                <td className="py-1.5 text-right pr-2">13:42:10</td>
              </tr>
            </tbody>
          </table>
        )}

        {/* Strategy Logs tab */}
        {activeTab === "logs" && (
          <div className="font-mono text-[9px] text-slate-400 flex flex-col gap-1 max-w-5xl select-text">
            <span>[13:45:00 INFO] Signal Engine generated BUY trigger for NIFTY CE spread...</span>
            <span>[13:45:01 SUCCESS] Simulated Order placement target sent to paper engine...</span>
            <span>[13:45:01 SUCCESS] Simulated position created - Qty: 150 @ Avg ₹112.50...</span>
            <span>[13:45:10 INFO] Market Feed Heartbeat active - drift latency: 14ms...</span>
          </div>
        )}

        {/* Events Ticker tab */}
        {activeTab === "events" && (
          <div className="font-mono text-[9px] text-slate-400 flex flex-col gap-1 select-text">
            <span>[13:40:02 INFO] WebSocket pipeline connection established successfully.</span>
            <span>[13:41:00 SUCCESS] Broker API heartbeat verified.</span>
            <span>[13:44:22 WARNING] Feed drift alert: packet queue delayed by 40ms. Auto-recovered.</span>
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
                <span className="text-slate-400">✓ Runtime Target (Req: &gt; 14 Days)</span>
                <span className="text-emerald-400 font-bold font-mono">12 Days (InProgress)</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                <span className="text-slate-400">✓ Trade Count Target (Req: &gt; 100)</span>
                <span className="text-emerald-400 font-bold font-mono">142 Trades (Passed)</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                <span className="text-slate-400">✓ Slippage Limit Check (Req: &lt; 0.05%)</span>
                <span className="text-emerald-400 font-bold font-mono">0.01% (Passed)</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-white/[0.02]">
                <span className="text-slate-400">✓ Drawdown Tolerance (Req: &lt; 10%)</span>
                <span className="text-emerald-400 font-bold font-mono">3.2% (Passed)</span>
              </div>
            </div>

            <div className="bg-slate-900/40 p-2.5 rounded border border-white/5 flex flex-col gap-1">
              <div className="flex items-center gap-1.5 font-bold">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                <span className="text-amber-400">STATUS: NOT ELIGIBLE FOR PRODUCTION</span>
              </div>
              <span className="text-[10px] text-slate-500">
                Strategy needs 2 more active trading days to satisfy the 14-day live paper test policy before production promotion is unlocked.
              </span>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};
