"use client";

import React, { useState, useEffect } from "react";
import { 
  Play, Pause, Square, RefreshCw, Cpu, Server, Activity, ShieldAlert,
  Search, Sliders, CheckCircle2, ChevronRight, Terminal, Plus, Trash2,
  Lock, Settings, Layers, ListFilter, SlidersHorizontal, AlertOctagon, HelpCircle
} from "lucide-react";
import { useTerminalStore } from "@/store/useTerminalStore";
import { useEventStore } from "@/store/useEventStore";

// Helper components for Kubernetes/Datadog styled grid boxes
const ControlCard: React.FC<{ title: string; children: React.ReactNode; className?: string }> = ({ title, children, className = "" }) => (
  <div className={`p-2 flex flex-col h-full ${className}`}>
    <h3 className="text-[12px] font-bold text-slate-200 border-b border-white/5 pb-1.5 mb-2 flex items-center justify-between">
      <span>{title}</span>
    </h3>
    <div className="flex-1 overflow-y-auto min-h-0">{children}</div>
  </div>
);

// MOCK ACTIVE RUNTIMES TELEMETRY
interface DeploymentClusterItem {
  id: string;
  strategyName: string;
  version: string;
  accountName: string;
  accountType: "Paper" | "Personal" | "Prop" | "Institutional";
  capitalAllocated: number;
  runtime: string;
  status: "Running" | "Paused" | "Stopped" | "Degraded" | "Failed" | "Archived";
  pnl: number;
  trades: number;
  winRate: number;
  drawdown: number;
  latency: number;
  healthScore: number;
}

const INITIAL_CLUSTERS: DeploymentClusterItem[] = [
  {
    id: "DEP_CLS_01",
    strategyName: "EMA Crossover",
    version: "v2.1",
    accountName: "Falcon Prop Tier-1",
    accountType: "Prop",
    capitalAllocated: 5000000,
    runtime: "4d 18h 12m",
    status: "Running",
    pnl: 142050.00,
    trades: 84,
    winRate: 61.2,
    drawdown: 1.4,
    latency: 14,
    healthScore: 98,
  },
  {
    id: "DEP_CLS_02",
    strategyName: "Mean Reversion B",
    version: "v1.5",
    accountName: "Insti Core Option Fund",
    accountType: "Institutional",
    capitalAllocated: 25000000,
    runtime: "12d 02h 45m",
    status: "Running",
    pnl: -84200.00,
    trades: 112,
    winRate: 48.9,
    drawdown: 3.1,
    exposure: 7500000,
    latency: 11,
    healthScore: 95,
  } as any,
  {
    id: "DEP_CLS_03",
    strategyName: "Grid Master 3",
    version: "v3.0",
    accountName: "Hedge Fund Liquidity Pool",
    accountType: "Institutional",
    capitalAllocated: 15000000,
    runtime: "28d 14h 02m",
    status: "Paused",
    pnl: 458900.00,
    trades: 842,
    winRate: 64.5,
    drawdown: 4.8,
    latency: 18,
    healthScore: 88,
  },
  {
    id: "DEP_CLS_04",
    strategyName: "Arb Scout Pro",
    version: "v1.1",
    accountName: "Personal Retail Brokerage",
    accountType: "Personal",
    capitalAllocated: 1000000,
    runtime: "1d 08h 14m",
    status: "Degraded",
    pnl: 12500.00,
    trades: 41,
    winRate: 51.2,
    drawdown: 2.8,
    latency: 142, // High latency
    healthScore: 68,
  },
  {
    id: "DEP_CLS_05",
    strategyName: "Volatility Rider",
    version: "v2.0",
    accountName: "Paper Alpha Testbed",
    accountType: "Paper",
    capitalAllocated: 500000,
    runtime: "0d 00h 00m",
    status: "Failed",
    pnl: -35000.00,
    trades: 12,
    winRate: 25.0,
    drawdown: 7.2,
    latency: 0,
    healthScore: 10,
  }
];

// ==========================================
// 1. LEFT PANEL: LIVE DEPLOYMENTS
// ==========================================
export const DeploymentsLeft: React.FC = () => {
  const selectedStrategy = useTerminalStore((state) => state.selectedStrategy);
  const setStrategy = useTerminalStore((state) => state.setStrategy);
  
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState<string>("All");

  const handleSelect = (item: DeploymentClusterItem) => {
    setStrategy({
      strategyId: item.id,
      strategyName: item.strategyName,
      version: item.version,
    });
  };

  const filtered = INITIAL_CLUSTERS.filter((c) => {
    const matchesSearch = c.strategyName.toLowerCase().includes(search.toLowerCase());
    const matchesFilter = activeFilter === "All" || c.status === activeFilter;
    return matchesSearch && matchesFilter;
  });

  return (
    <ControlCard title="Live Deployments">
      <div className="flex flex-col gap-2 h-full font-sans text-xs">
        {/* Search */}
        <div className="relative shrink-0">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search active clusters..."
            className="w-full bg-slate-900/60 border border-white/5 rounded pl-8 pr-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-cyan-500/40"
          />
        </div>

        {/* Filter List */}
        <div className="grid grid-cols-2 gap-1.5 shrink-0 select-none text-xs font-bold">
          {["All", "Running", "Paused", "Degraded", "Failed"].map((status) => (
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

        {/* Deployments list */}
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
                  <span className="font-bold uppercase tracking-wider text-xs truncate mr-2">
                    {item.strategyName}
                  </span>
                  <span className="font-mono text-xs text-slate-500 bg-slate-900 px-1 border border-white/5 rounded">
                    {item.version}
                  </span>
                </div>

                <div className="flex justify-between items-center text-xs text-slate-500 select-none">
                  <span className={`status-badge ${
                    item.status === "Running" ? "running" :
                    item.status === "Paused" ? "paused" :
                    item.status === "Degraded" ? "warning animate-pulse" : "failed animate-pulse"
                  }`}>
                    {item.status}
                  </span>
                  <span className="text-xs font-mono">{item.accountType}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </ControlCard>
  );
};

// ==========================================
// 2. MAIN PANEL: DEPLOYMENT GRID & COMMAND BAR
// ==========================================
export const DeploymentsMain: React.FC = () => {
  const selectedStrategy = useTerminalStore((state) => state.selectedStrategy);
  const setMode = useTerminalStore((state) => state.setMode);
  const addEvent = useEventStore((state) => state.addEvent);

  const [clusters, setClusters] = useState<DeploymentClusterItem[]>(INITIAL_CLUSTERS);

  // Set active mode on load
  useEffect(() => {
    setMode("live");
  }, [setMode]);

  const handleAction = (action: string) => {
    if (!selectedStrategy) return;
    addEvent({
      type: action === "STOP" ? "warning" : "info",
      message: `COMMAND DISPATCHED: [${action}] target cluster: ${selectedStrategy.strategyName}`,
      workspace: "Deployments",
    });
  };

  return (
    <div className="flex flex-col h-full overflow-hidden font-sans text-xs">
      
      {/* Kubernetes Command Bar */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-900/50 border-b border-white/5 select-none shrink-0 flex-wrap gap-2">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-slate-500 font-bold uppercase mr-2">Cluster Operations:</span>
          
          <button
            onClick={() => handleAction("DEPLOY")}
            disabled={!selectedStrategy}
            className="btn-buy disabled:opacity-30 cursor-pointer text-center"
          >
            Deploy
          </button>
          
          <button
            onClick={() => handleAction("PAUSE")}
            disabled={!selectedStrategy}
            className="btn-secondary text-amber-500 hover:text-amber-455 disabled:opacity-30 cursor-pointer text-center"
          >
            Pause
          </button>

          <button
            onClick={() => handleAction("RESUME")}
            disabled={!selectedStrategy}
            className="btn-primary disabled:opacity-30 cursor-pointer text-center"
          >
            Resume
          </button>

          <button
            onClick={() => handleAction("STOP")}
            disabled={!selectedStrategy}
            className="btn-destructive disabled:opacity-30 cursor-pointer text-center"
          >
            Stop
          </button>

          <button
            onClick={() => handleAction("RESTART")}
            disabled={!selectedStrategy}
            className="btn-secondary disabled:opacity-30 cursor-pointer text-center"
          >
            Restart
          </button>
        </div>

        <button className="btn-secondary cursor-pointer text-center">
          Bulk Shutdown
        </button>
      </div>

      {/* Main Kubernetes Cluster Grid */}
      <div className="flex-1 overflow-y-auto min-h-0 pr-1 scrollbar-thin scrollbar-thumb-white/5">
        <table className="w-full text-left font-mono text-xs">
          <thead>
            <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-xs tracking-wider">
              <th className="py-2.5 pl-3">Deploy ID</th>
              <th className="py-2.5">Strategy</th>
              <th className="py-2.5">Version</th>
              <th className="py-2.5">Account Target</th>
              <th className="py-2.5 text-right">Capital</th>
              <th className="py-2.5 text-center">Status</th>
              <th className="py-2.5 text-right">Live PnL</th>
              <th className="py-2.5 text-center">Trades</th>
              <th className="py-2.5 text-center">Drawdown</th>
              <th className="py-2.5 text-right pr-3">Health</th>
            </tr>
          </thead>
          <tbody className="text-slate-300 select-none">
            {clusters.map((c) => {
              const isSelected = selectedStrategy?.strategyId === c.id;
              return (
                <tr
                  key={c.id}
                  className={`border-b border-white/[0.02] hover:bg-white/[0.02] cursor-pointer transition-all ${
                    isSelected ? "bg-cyan-500/5 text-cyan-400" : ""
                  }`}
                >
                  <td className="py-2.5 pl-3 text-slate-500 font-bold">{c.id}</td>
                  <td className="py-2.5 font-bold uppercase">{c.strategyName}</td>
                  <td className="py-2.5 text-slate-400">{c.version}</td>
                  <td className="py-2.5 text-slate-400">
                    <span className="text-xs font-sans font-bold bg-slate-900 border border-white/5 px-1 rounded mr-1.5 text-slate-500">
                      {c.accountType}
                    </span>
                    {c.accountName}
                  </td>
                  <td className="py-2.5 text-right">₹{c.capitalAllocated.toLocaleString("en-IN")}</td>
                  <td className="py-2.5 text-center">
                    <span className={`status-badge ${
                      c.status === "Running" ? "running" :
                      c.status === "Paused" ? "paused" :
                      c.status === "Degraded" ? "warning" : "failed"
                    }`}>
                      {c.status}
                    </span>
                  </td>
                  <td className={`py-2.5 text-right font-bold ${c.pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {c.pnl >= 0 ? "+" : ""}₹{c.pnl.toLocaleString("en-IN")}
                  </td>
                  <td className="py-2.5 text-center">{c.trades}</td>
                  <td className="py-2.5 text-center text-rose-400">-{c.drawdown}%</td>
                  <td className="py-2.5 text-right pr-3 font-bold">
                    <span className={c.healthScore >= 90 ? "text-emerald-400" : c.healthScore >= 70 ? "text-amber-400" : "text-rose-400"}>
                      {c.healthScore}%
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ==========================================
// 3. RIGHT PANEL: DEPLOYMENT HEALTH
// ==========================================
export const DeploymentsRight: React.FC = () => {
  const selectedStrategy = useTerminalStore((state) => state.selectedStrategy);

  const healthServices = [
    { name: "Market Feed Feed", state: "HEALTHY", ok: true },
    { name: "WebSocket Gateway", state: "HEALTHY", ok: true },
    { name: "Redis Cache Store", state: "HEALTHY", ok: true },
    { name: "Execution OMS Engine", state: "HEALTHY", ok: true },
    { name: "Risk RMS Engine", state: "HEALTHY", ok: true },
    { name: "Broker Route API", state: "WARNING", ok: false }, // Broker is warning
    { name: "Audit Trail DB", state: "HEALTHY", ok: true },
    { name: "Container Runtime", state: "HEALTHY", ok: true },
  ];

  return (
    <ControlCard title="Deployment Health">
      <div className="flex flex-col gap-3 h-full font-sans text-xs">
        <div className="text-xs text-slate-500 border-b border-white/5 pb-1 select-none">
          KUBERNETES CONTAINER SERVICES
        </div>

        {selectedStrategy ? (
          <div className="flex-1 flex flex-col gap-2 overflow-y-auto pr-1">
            {healthServices.map((srv, idx) => (
              <div key={idx} className="flex justify-between items-center p-2 rounded bg-slate-900/30 border border-white/5">
                <span className="text-slate-400 text-xs font-semibold">{srv.name}</span>
                <span className={`status-badge ${
                  srv.state === "HEALTHY" ? "healthy" :
                  srv.state === "WARNING" ? "warning" : "failed"
                }`}>
                  {srv.state}
                </span>
              </div>
            ))}

            <div className="mt-4 pt-3 border-t border-white/5 select-none">
              <div className="bg-slate-950/60 p-2.5 rounded border border-white/5 flex flex-col gap-1 font-mono text-xs">
                <span className="text-slate-500 uppercase tracking-widest font-bold">Risk Management Telemetry</span>
                <div className="flex justify-between">
                  <span>Margin Usage:</span>
                  <span className="text-cyan-400 font-bold">14.2%</span>
                </div>
                <div className="flex justify-between">
                  <span>Ping RTT latency:</span>
                  <span className="text-emerald-400 font-bold">14ms</span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-500 text-xs text-center px-4">
            Select a target strategy to inspect container systems.
          </div>
        )}
      </div>
    </ControlCard>
  );
};

// ==========================================
// 4. BOTTOM PANEL: TABS & AUDIT TRAIL
// ==========================================
export const DeploymentsBottom: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"execution" | "logs" | "risk" | "audit">("execution");

  const tabs = [
    { id: "execution" as const, name: "Execution Events" },
    { id: "logs" as const, name: "Strategy Logs" },
    { id: "risk" as const, name: "Risk Alerts" },
    { id: "audit" as const, name: "Audit Trail Ledger" },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden text-xs font-sans">
      
      {/* Tab selectors */}
      <div className="flex items-center gap-1 border-b border-white/5 bg-slate-950/20 px-2 shrink-0 select-none">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-3 py-1.5 font-bold text-xs tracking-wide transition-all border-b-2 cursor-pointer ${
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
        
        {/* Execution Events */}
        {activeTab === "execution" && (
          <div className="font-mono text-xs text-slate-400 flex flex-col gap-1 max-w-5xl select-text">
            <span>[13:50:01 INFO] [DEP_CLS_01] Trigger Signal BUY generated - Symbol: NIFTY, Qty: 300</span>
            <span>[13:50:01 INFO] [DEP_CLS_01] Order submitted to broker route gateway target ...</span>
            <span>[13:50:02 SUCCESS] [DEP_CLS_01] Order filled @ ₹22180.20 (Latency: 14ms)</span>
          </div>
        )}

        {/* Strategy Logs */}
        {activeTab === "logs" && (
          <div className="font-mono text-xs text-slate-400 flex flex-col gap-1 max-w-5xl select-text">
            <span>[13:48:10 INFO] EMA 9 cross above EMA 21 matching parameters ...</span>
            <span>[13:50:00 INFO] VWAP volatility threshold crossed (ATR: 2.25) ...</span>
          </div>
        )}

        {/* Risk Alerts */}
        {activeTab === "risk" && (
          <div className="font-mono text-xs text-slate-400 flex flex-col gap-1 select-text">
            <span className="text-amber-400">[13:45:00 WARNING] [DEP_CLS_04] Risk Limit Warning: Broker route latency exceeded 100ms.</span>
            <span className="text-amber-400">[13:48:12 WARNING] [DEP_CLS_02] Capital Utilization Alert: Exposure margins near 75% max limits.</span>
          </div>
        )}

        {/* Audit Trail Ledger */}
        {activeTab === "audit" && (
          <table className="w-full text-left font-mono text-xs">
            <thead>
              <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-xs">
                <th className="py-1 pl-2">Who</th>
                <th className="py-1">What Action</th>
                <th className="py-1">Execution Time</th>
                <th className="py-1 pr-2 text-right">Reason</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              <tr className="border-b border-white/[0.02]">
                <td className="py-1.5 pl-2 text-slate-400">System Risk Engine</td>
                <td className="text-amber-400 font-bold">PAUSE STRATEGY (DEP_CLS_03)</td>
                <td>2026-05-29 13:30</td>
                <td className="text-right pr-2 text-slate-500">Max drawdown target breached</td>
              </tr>
              <tr className="border-b border-white/[0.02]">
                <td className="py-1.5 pl-2 text-slate-400">QuantAnalyst (Operator)</td>
                <td className="text-emerald-400 font-bold">SCALE OUT DEPLOYMENT (DEP_CLS_01)</td>
                <td>2026-05-29 11:22</td>
                <td className="text-right pr-2 text-slate-500">Increased allocation limit to ₹50L</td>
              </tr>
            </tbody>
          </table>
        )}

      </div>
    </div>
  );
};
