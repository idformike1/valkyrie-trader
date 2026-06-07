import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Monitor, Terminal, Trash2, ShieldAlert, Cpu } from "lucide-react";
import { useTerminalStore } from "@/store/useTerminalStore";
import { useSidebarStore } from "@/store/useSidebarStore";
import { useLayoutStore } from "@/store/useLayoutStore";
import { useCommandPaletteStore } from "@/store/useCommandPaletteStore";
import { useEventStore } from "@/store/useEventStore";
import { getAllWorkspaces } from "@/workspaces/registry";

interface CommandItem {
  id: string;
  name: string;
  category: "Navigation" | "System Operations";
  icon: React.ComponentType<any>;
  shortcut?: string;
  action: () => void;
}

export const CommandPalette: React.FC = () => {
  const isOpen = useCommandPaletteStore((state) => state.isOpen);
  const setOpen = useCommandPaletteStore((state) => state.setOpen);

  const setWorkspace = useTerminalStore((state) => state.setWorkspace);
  const toggleSidebar = useSidebarStore((state) => state.toggleCollapsed);
  const resetLayout = useLayoutStore((state) => state.resetLayout);
  const addEvent = useEventStore((state) => state.addEvent);

  const [search, setSearch] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const workspaces = getAllWorkspaces();

  // Define commands
  const commands: CommandItem[] = [
    ...workspaces.map((ws) => ({
      id: `open-${ws.id}`,
      name: `Open ${ws.name} Workspace`,
      category: "Navigation" as const,
      icon: Monitor,
      action: () => {
        setWorkspace(ws.id);
        addEvent({ type: "info", message: `Workspace switched to ${ws.name}`, workspace: "System" });
      },
    })),
    {
      id: "toggle-sidebar",
      name: "Toggle Navigation Sidebar",
      category: "System Operations" as const,
      icon: Terminal,
      shortcut: "S",
      action: () => {
        toggleSidebar();
      },
    },
    {
      id: "reset-layout",
      name: "Reset Current Workspace Panel Sizes",
      category: "System Operations" as const,
      icon: Trash2,
      action: () => {
        const activeId = useTerminalStore.getState().selectedWorkspace;
        resetLayout(activeId);
        addEvent({ type: "warning", message: `Layout reset for workspace: ${activeId}`, workspace: "Layout" });
      },
    },
    {
      id: "mock-order-fill",
      name: "Simulate Test Order Fill Event",
      category: "System Operations" as const,
      icon: Cpu,
      shortcut: "F",
      action: () => {
        addEvent({
          type: "success",
          message: "TEST ORDER FILLED - NIFTY 15 MAY 22300 CE Buy @ 123.40 (1 Lot)",
          workspace: "Scalper",
        });
      },
    },
    {
      id: "mock-system-error",
      name: "Simulate Strategy Latency Alert",
      category: "System Operations" as const,
      icon: ShieldAlert,
      action: () => {
        addEvent({
          type: "error",
          message: "Strategy latency breach: peak 250ms on order gateway",
          workspace: "System",
        });
      },
    },
  ];

  // Filter commands
  const filteredCommands = commands.filter((cmd) =>
    cmd.name.toLowerCase().includes(search.toLowerCase()) ||
    cmd.category.toLowerCase().includes(search.toLowerCase())
  );

  // Auto-focus input on open
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setSelectedIndex(0);
      setSearch("");
    }
  }, [isOpen]);

  // Handle keyboard events (Ctrl+K globally, and arrows inside palette)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(!isOpen);
      }

      if (!isOpen) return;

      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % filteredCommands.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + filteredCommands.length) % filteredCommands.length);
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (filteredCommands[selectedIndex]) {
          filteredCommands[selectedIndex].action();
          setOpen(false);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, filteredCommands, selectedIndex]);

  const executeCommand = (cmd: CommandItem) => {
    cmd.action();
    setOpen(false);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
            className="fixed inset-0 bg-black/85 backdrop-blur-sm"
          />

          {/* Palette Box */}
          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: -10 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="w-full max-w-lg bg-deep border border-subtle rounded-xl shadow-2xl overflow-hidden z-10 flex flex-col font-sans"
          >
            {/* Search Input */}
            <div className="flex items-center gap-3 px-4 py-3.5 border-b border-subtle bg-card/30">
              <Search className="w-4 h-4 text-slate-500" />
              <input
                ref={inputRef}
                type="text"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setSelectedIndex(0);
                }}
                placeholder="Search workspaces or type a system operation..."
                className="w-full bg-transparent border-0 text-slate-200 placeholder-slate-500 text-xs focus:outline-none focus:ring-0 p-0"
              />
              <span className="text-[10px] text-slate-500 font-mono uppercase bg-card border border-subtle px-2 py-0.5 rounded shrink-0">
                ESC to close
              </span>
            </div>

            {/* Command List */}
            <div className="flex-1 max-h-[320px] overflow-y-auto p-2 flex flex-col gap-1.5 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
              {filteredCommands.length > 0 ? (
                // Group commands by category
                ["Navigation", "System Operations"].map((cat) => {
                  const itemsInCat = filteredCommands.filter((c) => c.category === cat);
                  if (itemsInCat.length === 0) return null;

                  return (
                    <div key={cat} className="flex flex-col gap-1">
                      <div className="text-[9px] font-bold text-slate-500 uppercase tracking-widest px-3 py-1.5 mt-1 border-b border-white/[0.02]">
                        {cat}
                      </div>
                      {itemsInCat.map((cmd) => {
                        // Find global index in filtered list to determine active styling
                        const globalIdx = filteredCommands.indexOf(cmd);
                        const isActive = globalIdx === selectedIndex;
                        const CmdIcon = cmd.icon;

                        return (
                          <button
                            key={cmd.id}
                            onClick={() => executeCommand(cmd)}
                            onMouseEnter={() => setSelectedIndex(globalIdx)}
                            className={`w-full flex items-center justify-between px-3 py-2 rounded-md transition-all text-left text-xs relative cursor-pointer ${
                              isActive
                                ? "bg-cyan-500/10 text-cyan-400 font-semibold"
                                : "text-slate-400 hover:text-slate-200"
                            }`}
                          >
                            <div className="flex items-center gap-3">
                              <CmdIcon className={`w-3.5 h-3.5 ${isActive ? "text-cyan-400" : "text-slate-500"}`} />
                              <span>{cmd.name}</span>
                            </div>
                            {cmd.shortcut && (
                              <span className="text-[9px] font-mono font-bold text-slate-500 bg-card/60 px-1.5 py-0.5 rounded border border-subtle">
                                {cmd.shortcut}
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  );
                })
              ) : (
                <div className="text-center py-6 text-xs text-slate-500">
                  No matching commands or categories found.
                </div>
              )}
            </div>

            {/* Footer / Shortcut Helper */}
            <div className="px-4 py-2 bg-card/30 border-t border-subtle flex justify-between items-center text-[10px] text-slate-500 select-none">
              <span>Use Arrow keys to navigate, Enter to select</span>
              <span className="font-semibold text-slate-600">Valkyrie Shell v1.0.0</span>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
export default CommandPalette;
