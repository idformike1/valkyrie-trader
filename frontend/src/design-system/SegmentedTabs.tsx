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
}

export const SegmentedTabs: React.FC<SegmentedTabsProps> = ({
  tabs,
  activeTabId,
  onChange,
  className = "",
}) => {
  return (
    <div className={`flex items-center gap-[2px] border-b border-subtle bg-deep/35 px-[8px] flex-shrink-0 select-none ${className}`}>
      {tabs.map((tab) => {
        const isActive = activeTabId === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={`px-[12px] py-[6px] my-[3px] rounded vdl-body transition-all duration-150 cursor-pointer border ${
              isActive
                ? "bg-cyan-500/12 border-cyan-500/30 text-cyan-300 font-semibold shadow-[0_0_8px_rgba(6,182,212,0.15)]"
                : "bg-bg-deep/20 border-subtle/10 text-slate-300 hover:text-cyan-200 hover:bg-white/[0.02] hover:border-subtle/30"
            }`}
          >
            <span className="flex items-center gap-1.5">
              {tab.label}
              {tab.count !== undefined && (
                <span className={`vdl-mono text-[10px] px-1 py-0.2 rounded border ${
                  isActive ? "text-cyan-300 border-cyan-500/30 bg-cyan-500/5" : "text-slate-500 border-subtle bg-card"
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
