"use client";

import React, { useState, useEffect } from "react";
import { 
  Search, ListFilter, Cpu, Server, Activity, ShieldAlert,
  Database, RefreshCw, Terminal, CheckCircle2, ChevronRight,
  Filter, Play, Pause, AlertTriangle, AlertOctagon, HelpCircle
} from "lucide-react";
import { useTerminalStore } from "@/store/useTerminalStore";
import { useEventStore } from "@/store/useEventStore";

// Helper components for high-density diagnostics dashboard
const DiagnosticCard: React.FC<{ title: string; children: React.ReactNode; className?: string }> = ({ title, children, className = "" }) => (
  <div className={`panel flex flex-col h-full ${className}`}>
    <div className="panel-header">
      <span className="text-sm font-medium text-slate-200">{title}</span>
    </div>
    <div className="flex-1 overflow-y-auto min-h-0 p-3">{children}</div>
  </div>
);

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
    { name: "Trade Ledger", count: 4 },
    { name: "Strategy Console", count: 2 },
    { name: "System Health", count: 8 },
    { name: "Broker & Feed", count: 3 },
    { name: "Deployments", count: 5 },
  ];

  return (
    <DiagnosticCard title="Navigation & Filters">
      <div className="flex flex-col gap-3 h-full font-sans text-xs">
        
        {/* Navigation sections */}
        <div className="flex flex-col gap-0.5 border-b border-white/5 pb-2.5 shrink-0">
          <span className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-1.5 select-none">
            Diagnostic Observability
          </span>
          {sections.map((sec) => (
            <button
              key={sec.name}
              onClick={() => setActiveSection(sec.name)}
              className={`flex justify-between items-center px-2 py-1.5 rounded transition-all cursor-pointer text-left ${
                activeSection === sec.name
                  ? "bg-cyan-500/10 text-cyan-400 font-bold"
                  : "text-slate-400 hover:bg-white/5"
              }`}
            >
              <span>{sec.name}</span>
              <span className="font-mono text-xs bg-slate-900 px-1 border border-white/5 rounded text-slate-500">
                {sec.count}
              </span>
            </button>
          ))}
        </div>

        {/* Global Search */}
        <div className="relative shrink-0">
          <Search className="absolute left-2 top-2 h-3.5 w-3.5 text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search logs, correlation IDs..."
            className="w-full bg-slate-900/60 border border-white/5 rounded pl-7 pr-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-cyan-500/40"
          />
        </div>

        {/* Severity Filters */}
        <div className="flex flex-col gap-1 select-none">
          <span className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-1">
            Severity Filter
          </span>
          <div className="grid grid-cols-2 gap-1.5 text-xs font-bold">
            {["All", "INFO", "WARNING", "ERROR", "CRITICAL", "SUCCESS"].map((sev) => (
              <button
                key={sev}
                onClick={() => setSeverityFilter(sev)}
                className={`py-1 rounded transition-all cursor-pointer text-center border truncate px-1 ${
                  severityFilter === sev
                    ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400"
                    : "bg-slate-900 border-white/5 text-slate-500 hover:text-slate-300"
                }`}
              >
                {sev}
              </button>
            ))}
          </div>
        </div>

      </div>
    </DiagnosticCard>
  );
};

// ==========================================
// 2. MAIN PANEL: RUNTIME LOGS GRID
// ==========================================
export const OperationsMain: React.FC = () => {
  const [logs, setLogs] = useState<RuntimeLogItem[]>(INITIAL_LOGS);
  const [filterQuery, setFilterQuery] = useState("");

  const filteredLogs = logs.filter((log) => {
    const matchesSearch = log.message.toLowerCase().includes(filterQuery.toLowerCase()) || 
                          log.correlationId.toLowerCase().includes(filterQuery.toLowerCase());
    return matchesSearch;
  });

  return (
    <div className="flex flex-col h-full overflow-hidden font-sans text-xs">
      
      {/* Logs Controls Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-900/50 border-b border-white/5 select-none shrink-0 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 font-bold uppercase">Log Stream Viewer</span>
          <div className="h-4 w-px bg-white/5" />
          <span className="text-cyan-400 font-mono text-xs font-bold">LIVE STREAMS INTERFACES</span>
        </div>

        {/* Quick Filter */}
        <div className="relative">
          <Search className="absolute left-2 top-1.5 h-3.5 w-3.5 text-slate-500" />
          <input
            type="text"
            value={filterQuery}
            onChange={(e) => setFilterQuery(e.target.value)}
            placeholder="Filter message or Correlation ID..."
            className="bg-slate-900 border border-white/5 rounded pl-7 pr-3 py-0.5 text-xs text-slate-300 focus:outline-none w-56 font-mono"
          />
        </div>
      </div>

      {/* Logs Table viewport */}
      <div className="flex-1 overflow-y-auto min-h-0 pr-1 scrollbar-thin scrollbar-thumb-white/5">
        <table className="w-full text-left font-mono text-xs">
          <thead>
            <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-xs tracking-wider">
              <th className="py-2.5 pl-3">Timestamp</th>
              <th className="py-2.5">Source</th>
              <th className="py-2.5">Component</th>
              <th className="py-2.5">Severity</th>
              <th className="py-2.5">Message</th>
              <th className="py-2.5 pr-3 text-right">Correlation ID</th>
            </tr>
          </thead>
          <tbody className="text-slate-300 select-none">
            {filteredLogs.map((log, index) => (
              <tr
                key={index}
                className="border-b border-white/[0.02] hover:bg-white/[0.02] cursor-pointer transition-all"
              >
                <td className="py-2 pl-3 text-slate-500">{log.timestamp}</td>
                <td className="py-2 font-bold text-slate-400">{log.source}</td>
                <td className="py-2 text-slate-400">{log.component}</td>
                <td className="py-2">
                  <span className={`status-badge ${
                    log.severity === "SUCCESS" ? "success" :
                    log.severity === "INFO" ? "connected" :
                    log.severity === "WARNING" ? "warning" :
                    log.severity === "ERROR" ? "failed" : "failed animate-pulse"
                  }`}>
                    {log.severity}
                  </span>
                </td>
                <td className="py-2 text-slate-200">{log.message}</td>
                <td className="py-2 text-right pr-3 text-slate-500 text-xs">{log.correlationId}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ==========================================
// 3. RIGHT PANEL: SYSTEM HEALTH
// ==========================================
export const OperationsRight: React.FC = () => {
  const healthIndicators = [
    { name: "WebSocket Connection", state: "HEALTHY", ok: true },
    { name: "Redis Cache Store", state: "HEALTHY", ok: true },
    { name: "Execution OMS Server", state: "HEALTHY", ok: true },
    { name: "Risk RMS Server", state: "HEALTHY", ok: true },
    { name: "Broker Gateway API", state: "WARNING", ok: false }, // broker gateway warning
    { name: "Market Tick Feed", state: "HEALTHY", ok: true },
    { name: "Platform Database", state: "HEALTHY", ok: true },
    { name: "Python Strategy Loop", state: "OFFLINE", ok: false }, // strategy engine offline
  ];

  return (
    <DiagnosticCard title="System Health">
      <div className="flex flex-col gap-3 h-full font-sans text-xs">
        <div className="text-xs text-slate-500 border-b border-white/5 pb-1 select-none">
          OBSERVABILITY SYSTEMS CHECKS
        </div>

        <div className="flex-1 flex flex-col gap-2 overflow-y-auto pr-1">
          {healthIndicators.map((item, idx) => (
            <div key={idx} className="flex justify-between items-center p-2 rounded bg-slate-900/30 border border-white/5">
              <span className="text-slate-400 text-xs font-semibold">{item.name}</span>
              <span className={`status-badge ${
                item.state === "HEALTHY" ? "healthy" :
                item.state === "WARNING" ? "warning animate-pulse" :
                item.state === "OFFLINE" ? "offline" : "failed"
              }`}>
                {item.state}
              </span>
            </div>
          ))}

          <div className="mt-4 pt-3 border-t border-white/5 select-none">
            <div className="bg-slate-950/60 p-2.5 rounded border border-white/5 flex flex-col gap-1 font-mono text-xs">
              <span className="text-slate-500 uppercase tracking-widest font-bold">Network Telemetry</span>
              <div className="flex justify-between">
                <span>Packet Queue Size:</span>
                <span className="text-cyan-400 font-bold">0</span>
              </div>
              <div className="flex justify-between">
                <span>Average Jitter RTT:</span>
                <span className="text-emerald-400 font-bold">1.4ms</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DiagnosticCard>
  );
};

// ==========================================
// 4. BOTTOM PANEL: DIAGNOSTIC LEDGERS
// ==========================================
export const OperationsBottom: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"ledger" | "console" | "broker" | "infra" | "audit">("ledger");

  const tabs = [
    { id: "ledger" as const, name: "Trade Ledger" },
    { id: "console" as const, name: "Strategy Console" },
    { id: "broker" as const, name: "Broker Events" },
    { id: "infra" as const, name: "Infrastructure Events" },
    { id: "audit" as const, name: "Audit History" },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden text-xs font-sans">
      
      {/* Tabs selectors */}
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
        
        {/* Trade Ledger */}
        {activeTab === "ledger" && (
          <table className="w-full text-left font-mono text-xs">
            <thead>
              <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-xs">
                <th className="py-1 pl-2">Time</th>
                <th className="py-1">Instrument</th>
                <th className="py-1">Side</th>
                <th className="py-1 text-center">Qty</th>
                <th className="py-1 text-right">Entry</th>
                <th className="py-1 text-right">Exit</th>
                <th className="py-1 text-right">PnL</th>
                <th className="py-1">Owner</th>
                <th className="py-1 pr-2 text-right">Correlation ID</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              <tr className="border-b border-white/[0.02]">
                <td className="py-1.5 pl-2 text-slate-500">13:54:12</td>
                <td className="py-1.5 font-bold">NIFTY26MAY22200CE</td>
                <td className="py-1.5 text-emerald-400 font-bold">BUY</td>
                <td className="py-1.5 text-center">150</td>
                <td className="py-1.5 text-right">₹112.50</td>
                <td className="py-1.5 text-right">₹132.20</td>
                <td className="py-1.5 text-right text-emerald-400 font-bold">+₹2,955.00</td>
                <td>QuantAnalyst</td>
                <td className="py-1.5 text-right pr-2 text-slate-500 text-xs">c_84920492-a1</td>
              </tr>
            </tbody>
          </table>
        )}

        {/* Strategy Console */}
        {activeTab === "console" && (
          <div className="font-mono text-xs text-slate-400 flex flex-col gap-1 max-w-5xl select-text">
            <span>[13:54:10 INFO] EMA 9 crossover above EMA 21 matching parameters ...</span>
            <span>[13:54:10 SUCCESS] Signal Generated: BUY 150 Qty NIFTY26MAY22200CE ...</span>
            <span>[13:54:12 SUCCESS] Order Filled: 150 Qty @ Avg ₹112.50 ...</span>
          </div>
        )}

        {/* Broker Events */}
        {activeTab === "broker" && (
          <div className="font-mono text-xs text-slate-400 flex flex-col gap-1 select-text">
            <span>[13:54:10 INFO] Broker Order Accepted - ID: ORD_NSE_904128</span>
            <span>[13:54:12 INFO] Broker Position Opened - Contract: NIFTY26MAY22200CE</span>
            <span>[13:54:32 WARNING] Gateway Error: Broker feed socket reconnection delayed</span>
          </div>
        )}

        {/* Infrastructure Events */}
        {activeTab === "infra" && (
          <div className="font-mono text-xs text-slate-400 flex flex-col gap-1 select-text">
            <span>[13:50:00 SUCCESS] Redis connection established. Buffer count reset.</span>
            <span>[13:54:32 WARNING] WebSocket Gateway connection lost. Reconnect logic active.</span>
            <span>[13:54:33 SUCCESS] WebSocket Gateway recovered. Reconnection complete in 120ms.</span>
          </div>
        )}

        {/* Audit History */}
        {activeTab === "audit" && (
          <table className="w-full text-left font-mono text-xs">
            <thead>
              <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-xs">
                <th className="py-1 pl-2">Who</th>
                <th className="py-1">What</th>
                <th className="py-1">When</th>
                <th className="py-1">Why</th>
                <th className="py-1">Result</th>
                <th className="py-1 pr-2 text-right">Correlation ID</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              <tr className="border-b border-white/[0.02]">
                <td className="py-1.5 pl-2 text-slate-400">QuantAnalyst</td>
                <td className="font-bold text-cyan-400">SCALE OUT (DEP_CLS_01)</td>
                <td>13:30:12</td>
                <td>Increased risk allocation bounds</td>
                <td className="text-emerald-400">SUCCESS</td>
                <td className="py-1.5 text-right pr-2 text-slate-500 text-xs">c_19284012-f1</td>
              </tr>
            </tbody>
          </table>
        )}

      </div>
    </div>
  );
};
