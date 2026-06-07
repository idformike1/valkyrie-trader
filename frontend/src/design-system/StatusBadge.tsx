import React from "react";

export type BadgeState =
  | "Running"
  | "Paused"
  | "Failed"
  | "Stopped"
  | "Ready"
  | "Connected"
  | "Disconnected"
  | "Healthy"
  | "Warning"
  | "Degraded"
  | "Offline"
  | "Info"
  | "Success"
  | "Critical"
  | "Error";

interface StatusBadgeProps {
  state: BadgeState | string;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ state, className = "" }) => {
  // Normalize string for safety
  const rawState = state.trim();
  let normalized: BadgeState = "Offline";

  // Map arbitrary strings to approved states
  const lower = rawState.toLowerCase();
  if (lower === "running" || lower === "active") normalized = "Running";
  else if (lower === "paused") normalized = "Paused";
  else if (lower === "failed" || lower === "unhealthy") normalized = "Failed";
  else if (lower === "error") normalized = "Error";
  else if (lower === "critical") normalized = "Critical";
  else if (lower === "stopped" || lower === "inactive") normalized = "Stopped";
  else if (lower === "ready") normalized = "Ready";
  else if (lower === "success") normalized = "Success";
  else if (lower === "connected" || lower === "online") normalized = "Connected";
  else if (lower === "disconnected") normalized = "Disconnected";
  else if (lower === "healthy" || lower === "ok") normalized = "Healthy";
  else if (lower === "warning" || lower === "alert") normalized = "Warning";
  else if (lower === "degraded") normalized = "Degraded";
  else if (lower === "info") normalized = "Info";
  else normalized = "Offline";

  // Tailwind styling mappings for approved states
  const stateStyles: Record<BadgeState, string> = {
    Running: "bg-emerald-500/10 text-emerald-400 border-emerald-500/25",
    Paused: "bg-amber-500/10 text-amber-400 border-amber-500/25",
    Failed: "bg-rose-500/10 text-rose-400 border-rose-500/25",
    Stopped: "bg-slate-500/10 text-slate-400 border-slate-500/25",
    Ready: "bg-emerald-500/10 text-emerald-400 border-emerald-500/25",
    Connected: "bg-emerald-500/10 text-emerald-400 border-emerald-500/25",
    Disconnected: "bg-slate-500/10 text-slate-400 border-slate-500/25",
    Healthy: "bg-emerald-500/10 text-emerald-400 border-emerald-500/25",
    Warning: "bg-amber-500/10 text-amber-400 border-amber-500/25",
    Degraded: "bg-orange-500/10 text-orange-400 border-orange-500/25",
    Offline: "bg-slate-500/10 text-slate-400 border-slate-500/25",
    Info: "bg-slate-500/10 text-slate-405 border-slate-500/20",
    Success: "bg-emerald-500/10 text-emerald-400 border-emerald-500/25",
    Critical: "bg-rose-500/10 text-rose-455 border-rose-500/25",
    Error: "bg-rose-500/10 text-rose-400 border-rose-500/25",
  };

  return (
    <span
      className={`inline-flex items-center gap-[4px] px-[8px] py-[2px] vdl-meta font-semibold border rounded-[4px] select-none ${
        stateStyles[normalized]
      } ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${
        normalized === "Running" || normalized === "Connected" || normalized === "Healthy" || normalized === "Ready" || normalized === "Success"
          ? "bg-emerald-400 animate-pulse"
          : normalized === "Failed" || normalized === "Critical" || normalized === "Error"
          ? "bg-rose-400"
          : normalized === "Warning" || normalized === "Paused"
          ? "bg-amber-400"
          : normalized === "Degraded"
          ? "bg-orange-400"
          : "bg-slate-400"
      }`} />
      {normalized.toUpperCase()}
    </span>
  );
};

export default StatusBadge;
