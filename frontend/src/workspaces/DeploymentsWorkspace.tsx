"use client";

import React, { useState, useEffect } from "react";
import { 
  Play, Pause, Square, RefreshCw, Cpu, Server, Activity, ShieldAlert,
  Search, Sliders, CheckCircle2, ChevronRight, Terminal, Plus, Trash2,
  Lock, Settings, Layers, ListFilter, SlidersHorizontal, AlertOctagon, HelpCircle
} from "lucide-react";
import { useTerminalStore } from "@/store/useTerminalStore";
import { useEventStore } from "@/store/useEventStore";
import DataTable, { ColumnDef } from "@/design-system/DataTable";
import SegmentedTabs from "@/design-system/SegmentedTabs";
import StatusBadge from "@/design-system/StatusBadge";
import EmptyState from "@/design-system/EmptyState";

// ACTIVE RUNTIMES TELEMETRY
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
    latency: 11,
    healthScore: 95,
  },
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
    latency: 142,
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
    <div className="flex flex-col gap-2 h-full font-sans vdl-body">
      {/* Search */}
      <div className="relative shrink-0">
        <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search active clusters..."
          className="w-full bg-card  rounded-[var(--radius-sm)] pl-8 pr-3 py-1.5 vdl-body text-slate-350 focus:outline-none focus:border-[var(--gold-accent)]/40"
        />
      </div>

      {/* Filter List */}
      <div className="tab-container grid grid-cols-5 shrink-0 select-none">
        {["All", "Running", "Paused", "Degraded", "Failed"].map((status) => (
          <button
            key={status}
            onClick={() => setActiveFilter(status)}
            className={`tab-item ${activeFilter === status ? "active" : ""}`}
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
              className={`p-2.5 rounded border transition-all cursor-pointer flex flex-col gap-1.5 relative${
                isSelected
                  ? "bg-[var(--gold-accent)]/10 border-[var(--gold-accent)]/30 text-[var(--gold-accent)]"
                  : "bg-card/40 hover:bg-card-hover/40 text-slate-300"
              }`}
            >
              <div className="flex justify-between items-start">
                <span className="font-semibold vdl-body truncate mr-2">
                  {item.strategyName}
                </span>
                <span className="font-mono vdl-meta text-slate-500 bg-card px-1 rounded">
                  {item.version}
                </span>
              </div>

              <div className="flex justify-between items-center vdl-meta text-slate-500 select-none">
                <StatusBadge state={item.status} />
                <span className="vdl-mono">{item.accountType}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ==========================================
// 2. MAIN PANEL: DEPLOYMENT GRID & COMMAND BAR
// ==========================================
export const DeploymentsMain: React.FC = () => {
  const selectedStrategy = useTerminalStore((state) => state.selectedStrategy);
  const setStrategy = useTerminalStore((state) => state.setStrategy);
  const setMode = useTerminalStore((state) => state.setMode);
  const addEvent = useEventStore((state) => state.addEvent);

  const [clusters] = useState<DeploymentClusterItem[]>(INITIAL_CLUSTERS);

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

  const handleRowSelect = (row: DeploymentClusterItem) => {
    setStrategy({
      strategyId: row.id,
      strategyName: row.strategyName,
      version: row.version,
    });
  };

  const columns: ColumnDef<DeploymentClusterItem>[] = [
    {
      header: "Deploy ID",
      accessorKey: "id",
      isMono: true,
      className: "text-slate-500 font-semibold",
    },
    {
      header: "Strategy",
      accessorKey: "strategyName",
      className: "font-semibold text-slate-200",
    },
    {
      header: "Version",
      accessorKey: "version",
      isMono: true,
      className: "text-slate-400",
    },
    {
      header: "Account Target",
      accessorKey: (row) => (
        <div className="flex items-center gap-2">
          <span className="vdl-meta font-semibold bg-card px-1 rounded text-slate-505 shrink-0">
            {row.accountType}
          </span>
          <span className="text-slate-350">{row.accountName}</span>
        </div>
      ),
    },
    {
      header: "Capital",
      accessorKey: (row) => `₹${row.capitalAllocated.toLocaleString("en-IN")}`,
      isNumeric: true,
      isMono: true,
      className: "text-slate-300",
    },
    {
      header: "Status",
      accessorKey: (row) => <StatusBadge state={row.status} />,
      className: "text-center",
    },
    {
      header: "Live PnL",
      accessorKey: (row) => (
        <span className={`font-semibold ${row.pnl >= 0 ? "text-emerald-450" : "text-rose-500"}`}>
          {row.pnl >= 0 ? "+" : ""}₹{row.pnl.toLocaleString("en-IN")}
        </span>
      ),
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Trades",
      accessorKey: "trades",
      isNumeric: true,
      isMono: true,
      className: "text-slate-300",
    },
    {
      header: "Drawdown",
      accessorKey: (row) => `-${row.drawdown}%`,
      isNumeric: true,
      isMono: true,
      className: "text-rose-500",
    },
    {
      header: "Health",
      accessorKey: (row) => (
        <span className={row.healthScore >= 90 ? "text-emerald-450 font-semibold" : row.healthScore >= 70 ? "text-amber-500 font-semibold" : "text-rose-500 font-semibold"}>
          {row.healthScore}%
        </span>
      ),
      isNumeric: true,
      isMono: true,
    },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden font-sans vdl-body">
      
      {/* Kubernetes Command Bar */}
      <div className="flex items-center justify-between px-3 py-2 bg-deep/50 border-b select-none shrink-0 flex-wrap gap-2">
        <div className="flex items-center gap-1.5">
          <span className="vdl-body text-slate-500 font-semibold mr-2">Cluster Operations:</span>
          
          <button
            onClick={() => handleAction("DEPLOY")}
            disabled={!selectedStrategy}
            className="btn-buy btn-sm cursor-pointer text-center"
          >
            Deploy
          </button>
          
          <button
            onClick={() => handleAction("PAUSE")}
            disabled={!selectedStrategy}
            className="btn-secondary btn-sm cursor-pointer text-center"
          >
            Pause
          </button>

          <button
            onClick={() => handleAction("RESUME")}
            disabled={!selectedStrategy}
            className="btn-primary btn-sm cursor-pointer text-center"
          >
            Resume
          </button>

          <button
            onClick={() => handleAction("STOP")}
            disabled={!selectedStrategy}
            className="btn-destructive btn-sm cursor-pointer text-center"
          >
            Stop
          </button>

          <button
            onClick={() => handleAction("RESTART")}
            disabled={!selectedStrategy}
            className="btn-secondary btn-sm cursor-pointer text-center"
          >
            Restart
          </button>
        </div>

        <button className="btn-danger btn-sm cursor-pointer text-center">
          Bulk Shutdown
        </button>
      </div>

      {/* Main Kubernetes Cluster Grid */}
      <div className="flex-1 overflow-y-auto min-h-0 pr-1 scrollbar-thin scrollbar-thumb-white/5">
        <DataTable
          columns={columns}
          data={clusters}
          onRowClick={handleRowSelect}
          rowClassName={(row) => selectedStrategy?.strategyId === row.id ? "bg-[var(--gold-accent)]/10 text-[var(--gold-accent)] font-semibold border-[var(--gold-accent)]/30" : ""}
        />
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
    { name: "Market Feed Feed", state: "Healthy" },
    { name: "WebSocket Gateway", state: "Healthy" },
    { name: "Redis Cache Store", state: "Healthy" },
    { name: "Execution OMS Engine", state: "Healthy" },
    { name: "Risk RMS Engine", state: "Healthy" },
    { name: "Broker Route API", state: "Warning" },
    { name: "Audit Trail DB", state: "Healthy" },
    { name: "Container Runtime", state: "Healthy" },
  ];

  return (
    <div className="flex flex-col gap-3 h-full font-sans vdl-body">
      {selectedStrategy ? (
        <div className="flex-1 flex flex-col gap-2 overflow-y-auto pr-1">
          {healthServices.map((srv, idx) => (
            <div key={idx} className="flex justify-between items-center p-2 rounded bg-card-hover/20">
              <span className="text-slate-400 vdl-body font-semibold">{srv.name}</span>
              <StatusBadge state={srv.state} />
            </div>
          ))}

          <div className="mt-4 pt-3 border-t select-none">
            <div className="bg-card/60 p-2.5 rounded flex flex-col gap-1 font-mono vdl-body">
              <span className="text-slate-500 font-semibold">Risk Management Telemetry</span>
              <div className="flex justify-between">
                <span>Margin Usage:</span>
                <span className="text-[var(--gold-accent)] font-semibold">14.2%</span>
              </div>
              <div className="flex justify-between">
                <span>Ping RTT latency:</span>
                <span className="text-emerald-450 font-semibold">14ms</span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-slate-500 vdl-body text-center px-4">
          Select a target strategy to inspect container systems.
        </div>
      )}
    </div>
  );
};

// ==========================================
// 4. BOTTOM PANEL: TABS & AUDIT TRAIL
// ==========================================
export const DeploymentsBottom: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"execution" | "logs" | "risk" | "audit">("execution");

  const tabItems = [
    { id: "execution", label: "Execution Events" },
    { id: "logs", label: "Strategy Logs" },
    { id: "risk", label: "Risk Alerts" },
    { id: "audit", label: "Audit Trail Ledger" },
  ];

  interface AuditItem {
    who: string;
    action: string;
    time: string;
    reason: string;
    type: "PAUSE" | "SCALE";
  }
  const auditData: AuditItem[] = [
    {
      who: "System Risk Engine",
      action: "PAUSE STRATEGY (DEP_CLS_03)",
      time: "2026-05-29 13:30",
      reason: "Max drawdown target breached",
      type: "PAUSE",
    },
    {
      who: "QuantAnalyst (Operator)",
      action: "SCALE OUT DEPLOYMENT (DEP_CLS_01)",
      time: "2026-05-29 11:22",
      reason: "Increased allocation limit to ₹50L",
      type: "SCALE",
    },
  ];

  const auditColumns: ColumnDef<AuditItem>[] = [
    {
      header: "Who",
      accessorKey: "who",
      className: "text-slate-400 font-sans",
    },
    {
      header: "What Action",
      accessorKey: (row) => (
        <span className={row.type === "PAUSE" ? "text-amber-400 font-semibold" : "text-emerald-450 font-semibold"}>
          {row.action}
        </span>
      ),
    },
    {
      header: "Execution Time",
      accessorKey: "time",
      isMono: true,
      className: "text-slate-350",
    },
    {
      header: "Reason",
      accessorKey: "reason",
      isNumeric: true,
      className: "text-slate-550 font-sans",
    },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden vdl-body font-sans">
      
      {/* Tab selectors */}
      <SegmentedTabs
        tabs={tabItems}
        activeTabId={activeTab}
        onChange={(id) => setActiveTab(id as any)}
      />

      {/* Tabs Viewport */}
      <div className="flex-1 overflow-y-auto p-3 scrollbar-thin scrollbar-thumb-white/5 scrollbar-track-transparent min-h-0">
        
        {/* Execution Events */}
        {activeTab === "execution" && (
          <div className="font-mono vdl-body text-slate-400 flex flex-col gap-1 max-w-5xl select-text">
            <span>[13:50:01 INFO] [DEP_CLS_01] Trigger Signal BUY generated - Symbol: NIFTY, Qty: 300</span>
            <span>[13:50:01 INFO] [DEP_CLS_01] Order submitted to broker route gateway target ...</span>
            <span><span className="text-emerald-400 font-semibold">[13:50:02 SUCCESS]</span> [DEP_CLS_01] Order filled @ ₹22180.20 (Latency: 14ms)</span>
          </div>
        )}

        {/* Strategy Logs */}
        {activeTab === "logs" && (
          <div className="font-mono vdl-body text-slate-400 flex flex-col gap-1 max-w-5xl select-text">
            <span>[13:48:10 INFO] EMA 9 cross above EMA 21 matching parameters ...</span>
            <span>[13:50:00 INFO] VWAP volatility threshold crossed (ATR: 2.25) ...</span>
          </div>
        )}

        {/* Risk Alerts */}
        {activeTab === "risk" && (
          <div className="font-mono vdl-body text-slate-450 flex flex-col gap-1 select-text">
            <span className="text-amber-400 font-semibold">[13:45:00 WARNING] [DEP_CLS_04] Risk Limit Warning: Broker route latency exceeded 100ms.</span>
            <span className="text-amber-400 font-semibold">[13:48:12 WARNING] [DEP_CLS_02] Capital Utilization Alert: Exposure margins near 75% max limits.</span>
          </div>
        )}

        {/* Audit Trail Ledger */}
        {activeTab === "audit" && (
          <DataTable
            columns={auditColumns}
            data={auditData}
          />
        )}

      </div>
    </div>
  );
};
