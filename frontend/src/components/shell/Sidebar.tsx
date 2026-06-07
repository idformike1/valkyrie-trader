import React from "react";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useSidebarStore } from "@/store/useSidebarStore";
import { WorkspaceSidebar } from "@/design-system/WorkspaceSidebar";

export const Sidebar: React.FC = () => {
  const isCollapsed = useSidebarStore((state) => state.isCollapsed);
  const toggleCollapsed = useSidebarStore((state) => state.toggleCollapsed);

  return (
    <motion.aside
      animate={{ width: isCollapsed ? 52 : 200 }}
      transition={{ duration: 0.15, ease: "easeOut" }}
      className="h-screen border-r border-subtle bg-deep flex flex-col justify-between select-none shrink-0 overflow-hidden font-sans z-20"
    >
      {/* Valkyrie Brand Header */}
      <div className="h-10 border-b border-subtle bg-deep flex items-center px-4 shrink-0 select-none">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-cyan-neon rounded-sm flex items-center justify-center font-black text-[9px] text-white">V</div>
          {!isCollapsed && (
            <span className="text-[12px] font-black tracking-widest text-main uppercase font-display">
              Valkyrie<span className="text-cyan-neon">_</span>
            </span>
          )}
        </div>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto">
        <WorkspaceSidebar />
      </div>


      {/* Bottom Market Telemetry (visible when expanded) */}
      {!isCollapsed && (
        <div className="p-3 border-t border-subtle bg-deep/50 flex flex-col gap-2 text-[9px] font-mono text-slate-500 select-none">
          <div className="flex items-center justify-between">
            <span className="uppercase text-slate-600 font-bold">Market Status</span>
            <span className="text-emerald-400 font-bold flex items-center gap-1">
              <span className="w-1 h-1 rounded-full bg-emerald-400 animate-pulse" />
              NSE OPEN
            </span>
          </div>
          
          <div className="flex flex-col gap-0.5 border-t border-subtle/50 pt-2">
            <div className="flex justify-between">
              <span className="text-slate-400 font-semibold">NIFTY 50</span>
              <span className="text-slate-300 font-bold">22,389.65</span>
            </div>
            <div className="flex justify-end gap-1 text-[8px]">
              <span className="text-emerald-400 font-bold">+123.40</span>
              <span className="text-emerald-500 font-bold">(+0.55%)</span>
            </div>
          </div>

          <div className="flex flex-col gap-0.5">
            <div className="flex justify-between">
              <span className="text-slate-400 font-semibold">INDIA VIX</span>
              <span className="text-slate-300 font-bold">13.24</span>
            </div>
            <div className="flex justify-end gap-1 text-[8px]">
              <span className="text-rose-400 font-bold">-0.21</span>
              <span className="text-rose-500 font-bold">(-1.56%)</span>
            </div>
          </div>

          <div className="flex flex-col gap-0.5">
            <div className="flex justify-between">
              <span className="text-slate-400 font-semibold">BANKNIFTY</span>
              <span className="text-slate-300 font-bold">48,732.10</span>
            </div>
            <div className="flex justify-end gap-1 text-[8px]">
              <span className="text-emerald-400 font-bold">+256.30</span>
              <span className="text-emerald-500 font-bold">(+0.53%)</span>
            </div>
          </div>
        </div>
      )}

      {/* Collapse Toggle Button */}
      <div className="p-2.5 border-t border-subtle bg-deep">
        <button
          onClick={toggleCollapsed}
          className="w-full flex items-center justify-center py-2 hover:bg-card-hover text-slate-400 hover:text-cyan-neon border border-transparent hover:border-subtle rounded-sm transition-all cursor-pointer"
        >
          {isCollapsed ? (
            <ChevronRight className="w-3.5 h-3.5" />
          ) : (
            <div className="flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-wider text-slate-500">
              <ChevronLeft className="w-3.5 h-3.5" />
              <span>Collapse</span>
            </div>
          )}
        </button>
      </div>
    </motion.aside>
  );
};
export default Sidebar;
