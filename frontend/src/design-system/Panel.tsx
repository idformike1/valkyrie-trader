import React, { useState } from "react";
import { ChevronDown, ChevronUp, ArrowLeftRight, Maximize2, Minimize2 } from "lucide-react";
import { PANEL_PADDING, BORDER_RADIUS } from "./tokens";

interface PanelProps {
  title?: string;
  variant?: "compact" | "standard" | "large" | "none";
  canCollapse?: boolean;
  isCollapsed?: boolean;
  onCollapseToggle?: () => void;
  children: React.ReactNode;
  className?: string;
  actions?: React.ReactNode;
}

export const Panel: React.FC<PanelProps> = ({
  title,
  variant = "standard",
  canCollapse = false,
  isCollapsed = false,
  onCollapseToggle,
  children,
  className = "",
  actions,
}) => {
  const [isMaximized, setIsMaximized] = useState(false);

  // Spacing and radii maps based on tokens
  const paddingMap = {
    none: "p-0",
    compact: "p-[12px]",
    standard: "p-[16px]",
    large: "p-[24px]",
  };

  const paddingClass = paddingMap[variant];
  const borderRadiusClass = "panel"; // approved radius for standard components

  if (isCollapsed && onCollapseToggle) {
    return (
      <div 
        onClick={onCollapseToggle}
        className={`flex flex-col items-center justify-start bg-bg-base border border-subtle py-4 w-9 h-full select-none cursor-pointer hover:bg-card-hover transition-colors ${borderRadiusClass}`}
      >
        <button
          onClick={(e) => {
            e.stopPropagation();
            onCollapseToggle();
          }}
          className="text-slate-400 hover:text-cyan-neon transition-colors p-1"
          title={`Expand ${title || "Panel"}`}
        >
          <ArrowLeftRight className="w-3.5 h-3.5" />
        </button>
        {title && (
          <span
            className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mt-6"
            style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
          >
            {title}
          </span>
        )}
      </div>
    );
  }

  return (
    <div
      className={`flex flex-col overflow-hidden transition-all duration-150 bg-bg-base border border-subtle ${borderRadiusClass} ${
        isMaximized
          ? "fixed inset-4 z-40 bg-bg-base shadow-lg shadow-black/50"
          : "h-[calc(100%-12px)] w-[calc(100%-12px)]"
      } ${className}`}
    >
      {/* Panel Header */}
      {title && (
        <div className={`panel-header flex items-center justify-between py-1.5 bg-deep border-b border-subtle shrink-0 ${
          variant === "compact" ? "px-3" : "px-4"
        }`}>
          <h3 className="vdl-section text-main select-none">
            {title}
          </h3>
          <div className="flex items-center gap-2">
            {actions}
            <button
              onClick={() => setIsMaximized(!isMaximized)}
              className="text-slate-500 hover:text-cyan-neon p-1 transition-colors"
              title={isMaximized ? "Restore" : "Maximize"}
            >
              {isMaximized ? (
                <Minimize2 className="w-3.5 h-3.5" />
              ) : (
                <Maximize2 className="w-3.5 h-3.5" />
              )}
            </button>
            {canCollapse && onCollapseToggle && (
              <button
                onClick={onCollapseToggle}
                className="text-slate-500 hover:text-cyan-neon p-1 transition-colors"
                title="Collapse"
              >
                <ChevronUp className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Panel Body (Direct content rendering, eliminating redundant grey headers) */}
      <div className={`flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent ${paddingClass}`}>
        {children}
      </div>
    </div>
  );
};

export default Panel;
