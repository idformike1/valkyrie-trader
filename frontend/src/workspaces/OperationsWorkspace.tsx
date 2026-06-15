"use client";

import React, { useState, useEffect } from "react";
import { 
  Search, ListFilter, Cpu, Server, Activity, ShieldAlert,
  Database, RefreshCw, Terminal, CheckCircle2, ChevronRight,
  Filter, Play, Pause, AlertTriangle, AlertOctagon, HelpCircle
} from "lucide-react";
import { useTerminalStore } from "@/store/useTerminalStore";
import { useEventStore } from "@/store/useEventStore";
import DataTable, { ColumnDef } from "@/design-system/DataTable";
import SegmentedTabs from "@/design-system/SegmentedTabs";
import StatusBadge from "@/design-system/StatusBadge";
import EmptyState from "@/design-system/EmptyState";

// MOCK RUNTIME LOGS RECORD
interface RuntimeLogItem {
  timestamp: string;
  source: string;
  component: string;
  severity: "INFO" | "WARNING" | "ERROR" | "CRITICAL" | "SUCCESS";
  message: string;
  correlationId: string;
}

const INITIAL_LOGS: RuntimeLogItem[] = [
  {
    timestamp: "13:54:10",
    source: "STRATEGY_ENG",
    component: "EMA_CROSS",
    severity: "SUCCESS",
    message: "Signal generated: BUY 150 Qty NIFTY26MAY22200CE",
    correlationId: "c_84920492-a1",
  },
  {
    timestamp: "13:54:10",
    source: "EXECUTION_OMS",
    component: "ORDER_ROUTE",
    severity: "INFO",
    message: "Submitting order to NSE routing engine gateway",
    correlationId: "c_84920492-a1",
  },
  {
    timestamp: "13:54:11",
    source: "RISK_RMS",
    component: "LIMIT_AUDIT",
    severity: "INFO",
    message: "Risk audit passed: Margin requirement ₹16,875 within bounds",
    correlationId: "c_84920492-a1",
  },
  {
    timestamp: "13:54:12",
    source: "BROKER_GATEWAY",
    component: "NSE_FEED",
    severity: "SUCCESS",
    message: "Order filled @ ₹112.50. Target ACK latency: 14ms",
    correlationId: "c_84920492-a1",
  },
  {
    timestamp: "13:54:20",
    source: "INFRASTRUCTURE",
    component: "REDIS_QUEUE",
    severity: "WARNING",
    message: "Redis buffer usage crossed 75% limit. Triggering clear sweep",
    correlationId: "c_90824902-d2",
  },
  {
    timestamp: "13:54:32",
    source: "BROKER_GATEWAY",
    component: "FEED_SOCKET",
    severity: "ERROR",
    message: "WebSocket connection drop detected on feed socket",
    correlationId: "c_74829420-b4",
  },
  {
    timestamp: "13:54:33",
    source: "INFRASTRUCTURE",
    component: "FEED_RECOVERY",
    severity: "CRITICAL",
    message: "Failed socket reconnection. Switching to fallback gateway route",
    correlationId: "c_74829420-b4",
  }
];

// ==========================================
// 1. LEFT PANEL: NAVIGATION & FILTERS
// ==========================================
export const OperationsLeft: React.FC = () => {
  const [activeSection, setActiveSection] = useState("Runtime Logs");
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState<string>("All");

  const sections = [
    { name: "Runtime Logs", count: 7 },
    { name: "Trade Ledger", count: 1 },
    { name: "Strategy Console", count: 3 },
    { name: "System Health", count: 8 },
    { name: "Broker & Feed", count: 3 },
    { name: "Deployments", count: 5 },
  ];

  return (
    <div className="flex flex-col gap-3 h-full font-sans vdl-body">
      {/* Navigation sections */}
      <div className="flex flex-col gap-0.5 border-b pb-2.5 shrink-0">
        <span className="vdl-body text-slate-500 font-semibold mb-1.5 select-none">
          Diagnostic Observability
        </span>
        {sections.map((sec) => (
          <button
            key={sec.name}
            onClick={() => setActiveSection(sec.name)}
            className={`flex justify-between items-center px-2 py-1.5 rounded-[var(--radius-sm)] transition-all cursor-pointer text-left${
              activeSection === sec.name
                ? "bg-[var(--gold-accent)]/10 text-[var(--gold-accent)] font-bold"
                : "text-slate-400 hover:bg-white/5"
            }`}
          >
            <span>{sec.name}</span>
            <span className="font-mono vdl-meta bg-card px-1 rounded text-slate-505">
              {sec.count}
            </span>
          </button>
        ))}
      </div>

      {/* Global Search */}
      <div className="relative shrink-0">
        <Search className="absolute left-2 top-2 h-3.5 w-3.5 text-slate-505" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search logs, correlation IDs..."
          className="w-full bg-card rounded-[var(--radius-sm)] pl-7 pr-2 py-1 vdl-body text-slate-300 focus:outline-none focus:border-[var(--gold-accent)]/40"
        />
      </div>

      {/* Severity Filters */}
      <div className="flex flex-col gap-1 select-none">
        <span className="vdl-body text-slate-500 font-semibold mb-1">
          Severity Level
        </span>
        {["All", "SUCCESS", "INFO", "WARNING", "ERROR", "CRITICAL"].map((sev) => (
          <button
            key={sev}
            onClick={() => setSeverityFilter(sev)}
            className={`flex items-center gap-2 px-2 py-1 rounded-[var(--radius-sm)] transition-all cursor-pointer text-left${
              severityFilter === sev
                ? "bg-[var(--gold-accent)]/10 text-[var(--gold-accent)] font-semibold"
                : "text-slate-400 hover:bg-white/5"
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${
              sev === "SUCCESS" ? "bg-emerald-450" :
              sev === "INFO" ? "bg-slate-400" :
              sev === "WARNING" ? "bg-amber-450" :
              sev === "ERROR" || sev === "CRITICAL" ? "bg-rose-500" : "bg-[var(--gold-accent)]"
            }`} />
            <span className="vdl-body">{sev}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

// ==========================================
// 2. MAIN PANEL: LOG LEDGER
// ==========================================
export const OperationsMain: React.FC = () => {
  const [logs] = useState<RuntimeLogItem[]>(INITIAL_LOGS);
  const [filterQuery, setFilterQuery] = useState("");

  const filteredLogs = logs.filter((log) => {
    if (!filterQuery) return true;
    const query = filterQuery.toLowerCase();
    return (
      log.message.toLowerCase().includes(query) ||
      log.correlationId.toLowerCase().includes(query) ||
      log.source.toLowerCase().includes(query) ||
      log.component.toLowerCase().includes(query)
    );
  });

  const columns: ColumnDef<RuntimeLogItem>[] = [
    {
      header: "Timestamp",
      accessorKey: "timestamp",
      isMono: true,
      className: "text-slate-500",
    },
    {
      header: "Source",
      accessorKey: "source",
      className: "font-semibold text-slate-400",
    },
    {
      header: "Component",
      accessorKey: "component",
      className: "text-slate-400",
    },
    {
      header: "Severity",
      accessorKey: (row) => <StatusBadge state={row.severity} />,
    },
    {
      header: "Message",
      accessorKey: "message",
      className: "text-slate-200 font-sans",
    },
    {
      header: "Correlation ID",
      accessorKey: "correlationId",
      isNumeric: true,
    },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden font-sans vdl-body">
      
      {/* Logs Controls Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 bg-deep/50 border-b select-none shrink-0 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="vdl-body text-slate-500 font-semibold">Log Stream Viewer</span>
          <div className="h-4 w-px bg-white/5" />
          <span className="text-[var(--gold-accent)] font-mono vdl-body font-semibold">Live streams & interfaces</span>
        </div>

        {/* Quick Filter */}
        <div className="relative">
          <Search className="absolute left-2 top-1.5 h-3.5 w-3.5 text-slate-500" />
          <input
            type="text"
            value={filterQuery}
            onChange={(e) => setFilterQuery(e.target.value)}
            placeholder="Filter message or Correlation ID..."
            className="bg-card rounded-[var(--radius-sm)] pl-7 pr-3 py-0.5 vdl-body text-slate-300 focus:outline-none w-56 font-mono"
          />
        </div>
      </div>

      {/* Logs Table viewport */}
      <div className="flex-1 overflow-y-auto min-h-0 pr-1 scrollbar-thin scrollbar-thumb-white/5">
        <DataTable
          columns={columns}
          data={filteredLogs}
        />
      </div>
    </div>
  );
};

// ==========================================
// 3. RIGHT PANEL: SYSTEM HEALTH
// ==========================================
export const OperationsRight: React.FC = () => {
  const healthIndicators = [
    { name: "WebSocket Connection", state: "Connected" },
    { name: "Redis Cache Store", state: "Healthy" },
    { name: "Execution OMS Server", state: "Healthy" },
    { name: "Risk RMS Server", state: "Healthy" },
    { name: "Broker Gateway API", state: "Warning" },
    { name: "Market Tick Feed", state: "Healthy" },
    { name: "Platform Database", state: "Healthy" },
    { name: "Python Strategy Loop", state: "Offline" },
  ];

  return (
    <div className="flex flex-col gap-3 h-full font-sans vdl-body">
      <div className="flex-1 flex flex-col gap-2 overflow-y-auto pr-1">
        {healthIndicators.map((item, idx) => (
          <div key={idx} className="flex justify-between items-center p-2 rounded bg-card-hover/20">
            <span className="text-slate-400 vdl-body font-semibold">{item.name}</span>
            <StatusBadge state={item.state} />
          </div>
        ))}

        <div className="mt-4 pt-3 border-t select-none">
          <div className="bg-card/60 p-2.5 rounded flex flex-col gap-1 font-mono vdl-body">
            <span className="text-slate-500 font-semibold">Network Telemetry</span>
            <div className="flex justify-between">
              <span>Packet Queue Size:</span>
              <span className="text-[var(--gold-accent)] font-semibold">0</span>
            </div>
            <div className="flex justify-between">
              <span>Average Jitter RTT:</span>
              <span className="text-emerald-450 font-semibold">1.4ms</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ==========================================
// 4. BOTTOM PANEL: DIAGNOSTIC LEDGERS
// ==========================================
export const OperationsBottom: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"ledger" | "console" | "broker" | "infra" | "audit">("ledger");

  const tabItems = [
    { id: "ledger", label: "Trade Ledger" },
    { id: "console", label: "Strategy Console" },
    { id: "broker", label: "Broker Events" },
    { id: "infra", label: "Infrastructure Events" },
    { id: "audit", label: "Audit History" },
  ];

  interface TradeItem {
    time: string;
    instrument: string;
    side: "BUY" | "SELL";
    qty: number;
    entry: number;
    exit: number;
    pnl: number;
    owner: string;
    correlationId: string;
  }
  const tradeData: TradeItem[] = [
    {
      time: "13:54:12",
      instrument: "NIFTY26MAY22200CE",
      side: "BUY",
      qty: 150,
      entry: 112.50,
      exit: 132.20,
      pnl: 2955.00,
      owner: "QuantAnalyst",
      correlationId: "c_84920492-a1",
    },
  ];

  const tradeColumns: ColumnDef<TradeItem>[] = [
    {
      header: "Time",
      accessorKey: "time",
      isMono: true,
      className: "text-slate-500",
    },
    {
      header: "Instrument",
      accessorKey: "instrument",
      className: "font-semibold text-slate-200",
    },
    {
      header: "Side",
      accessorKey: (row) => (
        <span className={row.side === "BUY" ? "text-emerald-450 font-semibold" : "text-rose-500 font-semibold"}>
          {row.side}
        </span>
      ),
    },
    {
      header: "Qty",
      accessorKey: "qty",
      isNumeric: true,
      isMono: true,
      className: "text-slate-300",
    },
    {
      header: "Entry",
      accessorKey: (row) => `₹${row.entry.toFixed(2)}`,
      isNumeric: true,
      isMono: true,
      className: "text-slate-350",
    },
    {
      header: "Exit",
      accessorKey: (row) => `₹${row.exit.toFixed(2)}`,
      isNumeric: true,
      isMono: true,
      className: "text-slate-350",
    },
    {
      header: "PnL",
      accessorKey: (row) => (
        <span className={`font-semibold ${row.pnl >= 0 ? "text-emerald-450" : "text-rose-500"}`}>
          {row.pnl >= 0 ? "+" : ""}₹{row.pnl.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
        </span>
      ),
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Owner",
      accessorKey: "owner",
      className: "text-slate-400 font-sans",
    },
    {
      header: "Correlation ID",
      accessorKey: "correlationId",
      isNumeric: true,
      isMono: true,
      className: "text-slate-550",
    },
  ];

  interface AuditItem {
    who: string;
    what: string;
    when: string;
    why: string;
    result: string;
    correlationId: string;
  }
  const auditData: AuditItem[] = [
    {
      who: "QuantAnalyst",
      what: "SCALE OUT (DEP_CLS_01)",
      when: "13:30:12",
      why: "Increased risk allocation bounds",
      result: "SUCCESS",
      correlationId: "c_19284012-f1",
    },
  ];

  const auditColumns: ColumnDef<AuditItem>[] = [
    {
      header: "Who",
      accessorKey: "who",
      className: "text-slate-400 font-sans",
    },
    {
      header: "What",
      accessorKey: (row) => <span className="font-semibold text-[var(--gold-accent)]">{row.what}</span>,
    },
    {
      header: "When",
      accessorKey: "when",
      isMono: true,
      className: "text-slate-350",
    },
    {
      header: "Why",
      accessorKey: "why",
      className: "text-slate-350 font-sans",
    },
    {
      header: "Result",
      accessorKey: (row) => <StatusBadge state={row.result} />,
    },
    {
      header: "Correlation ID",
      accessorKey: "correlationId",
      isNumeric: true,
      isMono: true,
      className: "text-slate-550",
    },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden vdl-body font-sans">
      {/* Tabs selectors */}
      <SegmentedTabs
        tabs={tabItems}
        activeTabId={activeTab}
        onChange={(id) => setActiveTab(id as any)}
      />

      {/* Tabs Viewport */}
      <div className="flex-1 overflow-y-auto p-3 scrollbar-thin scrollbar-thumb-white/5 scrollbar-track-transparent min-h-0">
        
        {/* Trade Ledger */}
        {activeTab === "ledger" && (
          <DataTable
            columns={tradeColumns}
            data={tradeData}
          />
        )}

        {/* Strategy Console */}
        {activeTab === "console" && (
          <div className="font-mono vdl-body text-slate-400 flex flex-col gap-1 max-w-5xl select-text">
            <span>[13:54:10 INFO] EMA 9 crossover above EMA 21 matching parameters ...</span>
            <span><span className="text-emerald-450 font-semibold">[13:54:10 SUCCESS]</span> Signal Generated: BUY 150 Qty NIFTY26MAY22200CE ...</span>
            <span><span className="text-emerald-450 font-semibold">[13:54:12 SUCCESS]</span> Order Filled: 150 Qty @ Avg ₹112.50 ...</span>
          </div>
        )}

        {/* Broker Events */}
        {activeTab === "broker" && (
          <div className="font-mono vdl-body text-slate-400 flex flex-col gap-1 select-text">
            <span>[13:54:10 INFO] Broker Order Accepted - ID: ORD_NSE_904128</span>
            <span>[13:54:12 INFO] Broker Position Opened - Contract: NIFTY26MAY22200CE</span>
            <span><span className="text-amber-450 font-semibold">[13:54:32 WARNING]</span> Gateway Error: Broker feed socket reconnection delayed</span>
          </div>
        )}

        {/* Infrastructure Events */}
        {activeTab === "infra" && (
          <div className="font-mono vdl-body text-slate-400 flex flex-col gap-1 select-text">
            <span><span className="text-emerald-450 font-semibold">[13:50:00 SUCCESS]</span> Redis connection established. Buffer count reset.</span>
            <span><span className="text-amber-450 font-semibold">[13:54:32 WARNING]</span> WebSocket Gateway connection lost. Reconnect logic active.</span>
            <span><span className="text-emerald-450 font-semibold">[13:54:33 SUCCESS]</span> WebSocket Gateway recovered. Reconnection complete in 120ms.</span>
          </div>
        )}

        {/* Audit History */}
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
