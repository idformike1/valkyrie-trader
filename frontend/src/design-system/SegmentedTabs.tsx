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
            className={`px-[12px] py-[8px] vdl-body border-b-[2px] transition-all duration-150 cursor-pointer ${
              isActive
                ? "color-cyan-neon border-cyan-neon font-semibold text-cyan-neon"
                : "text-slate-400 border-transparent hover:text-slate-200"
            }`}
          >
            <span className="flex items-center gap-1.5">
              {tab.label}
              {tab.count !== undefined && (
                <span className={`vdl-mono text-[10px] px-1 py-0.2 rounded bg-card border border-subtle ${
                  isActive ? "text-cyan-neon border-cyan-neon/20 bg-cyan-neon/5" : "text-slate-500"
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
