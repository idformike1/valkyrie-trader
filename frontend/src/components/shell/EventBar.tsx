import React, { useRef, useEffect } from "react";
import { Terminal, Activity, AlertCircle } from "lucide-react";
import { useEventStore } from "@/store/useEventStore";

export const EventBar: React.FC = () => {
  const events = useEventStore((state) => state.events);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the right (most recent events)
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollLeft = 0; // The newest event is at index 0, prepended.
    }
  }, [events]);

  return (
    <footer className="h-6 border-t border-white/5 bg-slate-950 flex items-center justify-between px-3 text-[10px] select-none shrink-0 fixed bottom-0 left-0 right-0 z-30 font-mono">
      {/* Feed Label */}
      <div className="flex items-center gap-1.5 text-cyan-400 font-bold border-r border-white/5 pr-3 uppercase shrink-0 tracking-wider">
        <Terminal className="w-3 h-3" />
        <span>Live Events</span>
      </div>

      {/* Events Scroll Container */}
      <div 
        ref={containerRef}
        className="flex-1 flex items-center gap-6 overflow-x-auto px-4 h-full scrollbar-none whitespace-nowrap select-text"
      >
        {events.map((evt) => {
          let badgeColor = "text-cyan-400 bg-cyan-950/30 border-cyan-800/30";
          if (evt.type === "success") badgeColor = "text-emerald-400 bg-emerald-950/30 border-emerald-800/30";
          if (evt.type === "warning") badgeColor = "text-amber-400 bg-amber-950/30 border-amber-800/30";
          if (evt.type === "error") badgeColor = "text-rose-400 bg-rose-950/30 border-rose-800/30";

          return (
            <div key={evt.id} className="flex items-center gap-2 border-r border-white/5 pr-6 last:border-0">
              <span className="text-slate-500 font-semibold">{evt.timestamp}</span>
              {evt.workspace && (
                <span className={`text-[8px] font-bold px-1 rounded uppercase border ${badgeColor}`}>
                  {evt.workspace}
                </span>
              )}
              <span className="text-slate-300">{evt.message}</span>
            </div>
          );
        })}
      </div>

      {/* Status Indicators */}
      <div className="flex items-center gap-4 text-slate-500 text-[9px] border-l border-white/5 pl-3 shrink-0">
        <div className="flex items-center gap-1">
          <Activity className="w-3 h-3 text-cyan-400" />
          <span>RAM: 14%</span>
        </div>
        <div className="flex items-center gap-1">
          <AlertCircle className="w-3 h-3 text-emerald-400" />
          <span>SYS STATUS: NOMINAL</span>
        </div>
      </div>
    </footer>
  );
};
export default EventBar;
