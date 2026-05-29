import React, { useState } from "react";
import { ChevronDown, ChevronUp, Maximize2, Minimize2, ArrowLeftRight } from "lucide-react";

interface PanelProps {
  title: string;
  onCollapseToggle?: () => void;
  isCollapsed?: boolean;
  canCollapse?: boolean;
  children: React.ReactNode;
  className?: string;
}

export const Panel: React.FC<PanelProps> = ({
  title,
  onCollapseToggle,
  isCollapsed = false,
  canCollapse = true,
  children,
  className = "",
}) => {
  const [isMaximized, setIsMaximized] = useState(false);

  if (isCollapsed) {
    return (
      <div className="flex flex-col items-center justify-start bg-slate-950/80 border border-white/5 py-4 w-9 h-full select-none">
        <button
          onClick={onCollapseToggle}
          className="text-slate-400 hover:text-cyan-400 transition-colors p-1"
          title={`Expand ${title}`}
        >
          <ArrowLeftRight className="w-3.5 h-3.5" />
        </button>
        <span
          className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mt-6 cursor-pointer hover:text-slate-300 transition-colors"
          style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
          onClick={onCollapseToggle}
        >
          {title}
        </span>
      </div>
    );
  }

  return (
    <div
      className={`flex flex-col bg-slate-950/20 border border-white/5 rounded-md overflow-hidden transition-all duration-150 h-full ${
        isMaximized
          ? "fixed inset-4 z-40 bg-slate-950/95 border-cyan-500/50 shadow-2xl shadow-cyan-950/20"
          : ""
      } ${className}`}
    >
      {/* Panel Header */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-slate-900/50 border-b border-white/5 select-none shrink-0">
        <span className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">
          {title}
        </span>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setIsMaximized(!isMaximized)}
            className="text-slate-500 hover:text-cyan-400 transition-colors p-0.5"
            title={isMaximized ? "Restore Panel" : "Maximize Panel"}
          >
            {isMaximized ? <Minimize2 className="w-3 h-3" /> : <Maximize2 className="w-3 h-3" />}
          </button>
          {canCollapse && onCollapseToggle && (
            <button
              onClick={onCollapseToggle}
              className="text-slate-500 hover:text-cyan-400 transition-colors p-0.5"
              title="Collapse Panel"
            >
              <ChevronDown className="w-3.5 h-3.5 rotate-90" />
            </button>
          )}
        </div>
      </div>

      {/* Panel Body */}
      <div className="flex-1 overflow-y-auto p-3 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
        {children}
      </div>
    </div>
  );
};
export default Panel;
