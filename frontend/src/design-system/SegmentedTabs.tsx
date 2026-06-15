import React from "react";

export interface TabItem {
  id: string;
  label: string;
  count?: number;
}

interface SegmentedTabsProps {
  tabs: TabItem[];
  activeTabId: string;
  onChange: (id: string) => void;
  className?: string;
  variant?: "workspace" | "local" | "segmented";
}

export const SegmentedTabs: React.FC<SegmentedTabsProps> = ({
  tabs,
  activeTabId,
  onChange,
  className = "",
  variant = "local",
}) => {
  const isWorkspace = variant === "workspace";
  
  return (
    <div className={`tab-container ${isWorkspace ? "workspace-tabs" : ""} ${className}`}>
      {tabs.map((tab) => {
        const isActive = activeTabId === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={`tab-item ${isActive ? "active" : ""}`}
          >
            <span className="flex items-center gap-1.5">
              {tab.label}
              {tab.count !== undefined && (
                <span className={`font-mono text-[9px] px-1 py-[1px] rounded-[var(--radius-sm)] border ${
                  isActive ? "text-[var(--text-main)] border-[var(--gold-accent)]/30 bg-[var(--bg-card)]/5" : "text-slate-500 border-subtle bg-card"
                }`}>
                  [{tab.count}]
                </span>
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
};

export default SegmentedTabs;
