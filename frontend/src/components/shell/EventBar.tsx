import React, { useRef, useEffect, useState } from "react";
import { Terminal, Activity, AlertCircle, ChevronUp, ChevronDown } from "lucide-react";
import { useEventStore } from "@/store/useEventStore";

export const EventBar: React.FC = () => {
  const events = useEventStore((state) => state.events);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [unreadCount, setUnreadCount] = useState(events.length);

  useEffect(() => {
    setUnreadCount(events.length);
  }, [events.length]);

  // Auto-scroll to the top of logs in expanded view
  useEffect(() => {
    if (containerRef.current && isExpanded) {
      containerRef.current.scrollTop = 0;
    }
  }, [events, isExpanded]);

  // Keyboard shortcut Ctrl + ` to toggle expanded state
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "`") {
        setIsExpanded(prev => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <footer 
      className={`border-t border-subtle bg-deep flex flex-col px-3 text-xs select-none shrink-0 fixed bottom-0 left-0 right-0 z-30 font-mono transition-all duration-200 ${
        isExpanded ? "h-32" : "h-6"
      }`}
      onMouseEnter={() => setIsExpanded(true)}
      onMouseLeave={() => setIsExpanded(false)}
      onClick={() => setIsExpanded(!isExpanded)}
    >
      {/* Collapsed Top Header Ticker Row */}
      <div className="h-6 flex items-center justify-between w-full cursor-pointer">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-450 shadow-[0_0_6px_rgba(52,211,153,0.4)] animate-pulse" />
          <span className="text-slate-300 font-bold text-xs font-sans">System Healthy</span>
          <span className="text-slate-500 font-sans">|</span>
          <span className="text-cyan-neon font-bold text-xs">{unreadCount} Events</span>
        </div>

        <div className="flex items-center gap-4 text-slate-500 text-xs pl-3">
          <div className="flex items-center gap-1">
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
            <span>RAM: 14%</span>
          </div>
          {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
        </div>
      </div>

      {/* Expanded Log Entries Container */}
      {isExpanded && (
        <div className="flex-1 border-t border-subtle py-2 overflow-hidden flex flex-col min-h-0">
          <div 
            ref={containerRef}
            className="flex-1 flex flex-col gap-1.5 overflow-y-auto pr-1 select-text scrollbar-thin scrollbar-thumb-white/5 scrollbar-track-transparent"
          >
            {events.map((evt) => {
              let badgeColor = "text-cyan-450 bg-cyan-950/30 border-cyan-800/30";
              if (evt.type === "success") badgeColor = "text-emerald-450 bg-emerald-950/30 border-emerald-800/30";
              if (evt.type === "warning") badgeColor = "text-amber-455 bg-amber-950/30 border-amber-800/30";
              if (evt.type === "error") badgeColor = "text-rose-455 bg-rose-950/30 border-rose-800/30";

              return (
                <div key={evt.id} className="flex items-center gap-3 text-xs leading-tight font-mono tabular-nums">
                  <span className="text-slate-500 font-semibold">{evt.timestamp}</span>
                  {evt.workspace && (
                    <span className={`text-xs font-bold px-1 rounded uppercase border ${badgeColor}`}>
                      {evt.workspace}
                    </span>
                  )}
                  <span className="text-slate-300">{evt.message}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </footer>
  );
};
export default EventBar;
