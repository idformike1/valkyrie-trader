import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  TrendingUp, Zap, BarChart2, Layers, Server, Settings, 
  ChevronLeft, ChevronRight 
} from "lucide-react";
import { useTerminalStore } from "@/store/useTerminalStore";
import { useSidebarStore } from "@/store/useSidebarStore";
import { getAllWorkspaces } from "@/workspaces/registry";

const iconMap: Record<string, React.ComponentType<any>> = {
  TrendingUp,
  Zap,
  BarChart2,
  Layers,
  Server,
  Settings,
};

export const Sidebar: React.FC = () => {
  const selectedWorkspace = useTerminalStore((state) => state.selectedWorkspace);
  const setWorkspace = useTerminalStore((state) => state.setWorkspace);

  const isCollapsed = useSidebarStore((state) => state.isCollapsed);
  const toggleCollapsed = useSidebarStore((state) => state.toggleCollapsed);

  const workspaces = getAllWorkspaces();

  return (
    <motion.aside
      animate={{ width: isCollapsed ? 56 : 220 }}
      transition={{ duration: 0.2, ease: "easeInOut" }}
      className="fixed left-0 top-11 bottom-6 border-r border-white/5 bg-slate-950/80 backdrop-blur-md flex flex-col justify-between select-none z-20 shrink-0 overflow-hidden"
    >
      {/* Navigation Links */}
      <div className="flex-1 py-3 flex flex-col gap-1 px-2">
        {workspaces.map((ws) => {
          const IconComponent = iconMap[ws.icon] || Settings;
          const isActive = selectedWorkspace === ws.id;

          return (
            <button
              key={ws.id}
              onClick={() => setWorkspace(ws.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md transition-all group relative cursor-pointer ${
                isActive
                  ? "bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 font-bold"
                  : "bg-transparent border border-transparent text-slate-400 hover:text-slate-100 hover:bg-white/5"
              }`}
              title={isCollapsed ? ws.name : undefined}
            >
              <IconComponent className={`w-4 h-4 shrink-0 transition-transform ${isActive ? "scale-110" : "group-hover:scale-105"}`} />
              
              <AnimatePresence mode="wait">
                {!isCollapsed && (
                  <motion.span
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -10 }}
                    transition={{ duration: 0.15 }}
                    className="text-xs uppercase tracking-wider text-left overflow-hidden whitespace-nowrap"
                  >
                    {ws.name}
                  </motion.span>
                )}
              </AnimatePresence>

              {/* Active Indicator Bar */}
              {isActive && (
                <span className="absolute left-0 top-1.5 bottom-1.5 w-1 bg-cyan-400 rounded-r" />
              )}
            </button>
          );
        })}
      </div>

      {/* Collapse Toggle Button */}
      <div className="p-2 border-t border-white/5 bg-slate-950/60">
        <button
          onClick={toggleCollapsed}
          className="w-full flex items-center justify-center py-2.5 hover:bg-white/5 text-slate-400 hover:text-cyan-400 border border-transparent hover:border-white/5 rounded-md transition-all cursor-pointer"
        >
          {isCollapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest">
              <ChevronLeft className="w-4 h-4" />
              <span>Collapse</span>
            </div>
          )}
        </button>
      </div>
    </motion.aside>
  );
};
export default Sidebar;
