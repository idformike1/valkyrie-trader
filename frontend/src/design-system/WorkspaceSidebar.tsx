import React from "react";
import { useSidebarStore } from "@/store/useSidebarStore";
import { useTerminalStore } from "@/store/useTerminalStore";
import { getAllWorkspaces } from "@/workspaces/registry";
import { TrendingUp, Zap, BarChart2, Layers, Server, Settings } from "lucide-react";

const iconMap: Record<string, React.ComponentType<any>> = {
  TrendingUp,
  Zap,
  BarChart2,
  Layers,
  Server,
  Settings,
};

interface SidebarItemProps {
  id: string;
  label: string;
  icon: React.ComponentType<any>;
  count?: number;
  isActive: boolean;
  isCollapsed: boolean;
  onClick: () => void;
}

export const WorkspaceSidebarItem: React.FC<SidebarItemProps> = ({
  id,
  label,
  icon: Icon,
  count,
  isActive,
  isCollapsed,
  onClick,
}) => {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center justify-between px-3 py-2 rounded-[4px] transition-all group relative cursor-pointer font-sans text-[12px] ${
        isActive
          ? "bg-card-hover text-cyan-neon font-semibold border-l-2 border-cyan-neon pl-2.5"
          : "bg-transparent text-slate-400 hover:text-main hover:bg-card-hover/40"
      }`}
      title={isCollapsed ? label : undefined}
    >
      <div className="flex items-center gap-2.5">
        <Icon
          className={`w-3.5 h-3.5 shrink-0 transition-transform ${
            isActive ? "scale-105 text-cyan-neon" : "group-hover:scale-102 text-slate-500"
          }`}
        />
        {!isCollapsed && (
          <span className={`tracking-normal text-left truncate ${isActive ? "text-cyan-neon font-semibold" : "text-slate-300"}`}>
            {label}
          </span>
        )}
      </div>

      {!isCollapsed && count !== undefined && count > 0 && (
        <span
          className={`text-[10px] font-mono font-medium px-1 rounded bg-card border border-subtle ${
            isActive ? "text-cyan-neon border-cyan-neon/20 bg-cyan-neon/5" : "text-slate-500"
          }`}
        >
          [{count}]
        </span>
      )}
    </button>
  );
};

interface WorkspaceSidebarProps {
  sections?: {
    title: string;
    items: {
      id: string;
      label: string;
      icon: React.ComponentType<any>;
      count?: number;
    }[];
  }[];
}

export const WorkspaceSidebar: React.FC<WorkspaceSidebarProps> = ({ sections }) => {
  const selectedWorkspace = useTerminalStore((state) => state.selectedWorkspace);
  const setWorkspace = useTerminalStore((state) => state.setWorkspace);
  const isCollapsed = useSidebarStore((state) => state.isCollapsed);

  return (
    <div className="flex flex-col gap-4 py-2 px-2 overflow-y-auto select-none">
      {sections ? (
        sections.map((section, secIdx) => (
          <div key={secIdx} className="flex flex-col gap-1">
            {!isCollapsed && (
              <span className="text-[13px] font-sans font-semibold text-slate-400 px-3 mb-1 select-none">
                {section.title}
              </span>
            )}
            <div className="flex flex-col gap-[4px]">
              {section.items.map((item) => (
                <WorkspaceSidebarItem
                  key={item.id}
                  id={item.id}
                  label={item.label}
                  icon={item.icon}
                  count={item.count}
                  isActive={selectedWorkspace === item.id}
                  isCollapsed={isCollapsed}
                  onClick={() => setWorkspace(item.id)}
                />
              ))}
            </div>
          </div>
        ))
      ) : (
        <div className="flex flex-col gap-1">
          {!isCollapsed && (
            <span className="text-[13px] font-sans font-semibold text-slate-400 px-3 mb-1 select-none">
              Workspaces
            </span>
          )}
          <div className="flex flex-col gap-[4px]">
            {getAllWorkspaces().map((ws) => (
              <WorkspaceSidebarItem
                key={ws.id}
                id={ws.id}
                label={ws.name}
                icon={iconMap[ws.icon] || Settings}
                isActive={selectedWorkspace === ws.id}
                isCollapsed={isCollapsed}
                onClick={() => setWorkspace(ws.id)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};


export default WorkspaceSidebar;
