import React, { useState } from "react";
import { 
  Layers, Search, Bell, User, CheckCircle2, AlertTriangle, 
  ChevronDown, Globe, Wifi, KeyRound
} from "lucide-react";
import { useWorkspaceStore } from "@/store/useWorkspaceStore";
import { useCommandPaletteStore } from "@/store/useCommandPaletteStore";
import { getWorkspaceConfig } from "@/workspaces/registry";

import { useTerminalStore } from "@/store/useTerminalStore";

export const Header: React.FC = () => {
  const selectedWorkspace = useTerminalStore((state) => state.selectedWorkspace);
  const currentAccount = useTerminalStore((state) => state.currentAccount);
  const setAccount = useTerminalStore((state) => state.setAccount);
  
  const toggleCommandPalette = useCommandPaletteStore((state) => state.toggleOpen);
  const config = getWorkspaceConfig(selectedWorkspace);

  const [showAccountDropdown, setShowAccountDropdown] = useState(false);
  const [showUserDropdown, setShowUserDropdown] = useState(false);

  return (
    <header className="h-11 border-b border-white/5 bg-slate-950/80 backdrop-blur-md flex items-center justify-between px-4 select-none shrink-0 fixed top-0 left-0 right-0 z-30">
      {/* Left Section: Logo & Title */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 cursor-pointer">
          <div className="relative flex items-center justify-center w-5.5 h-5.5 bg-cyan-500/10 border border-cyan-500/30 rounded-md shadow-[0_0_10px_rgba(6,182,212,0.15)]">
            <Layers className="w-3.5 h-3.5 text-cyan-400" />
            <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
          </div>
          <span className="font-bold text-xs uppercase tracking-wider text-slate-100">
            Valkyrie<span className="text-cyan-400">.</span>
          </span>
        </div>

        <div className="h-4 w-px bg-white/5" />

        <div className="flex items-center gap-1.5">
          <span className="text-[10px] uppercase text-slate-500 tracking-wider">Workspace:</span>
          <span className="text-[11px] font-bold text-cyan-400 uppercase tracking-wide">
            {config ? `${config.name} Desk` : "Valkyrie Terminal"}
          </span>
        </div>
      </div>

      {/* Center Section: Global Search / Command Palette Trigger */}
      <div className="flex-1 max-w-md mx-6">
        <div 
          onClick={toggleCommandPalette}
          className="flex items-center gap-2 px-3 py-1 bg-slate-900/60 border border-white/5 rounded-md cursor-pointer hover:border-cyan-500/30 hover:bg-slate-900/90 transition-all text-slate-500 hover:text-slate-400 group"
        >
          <Search className="w-3.5 h-3.5 group-hover:text-cyan-400 transition-colors" />
          <span className="text-xs text-left flex-1 select-none text-[11px]">
            Search workspaces or operations...
          </span>
          <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-[9px] font-mono font-bold text-slate-500 bg-slate-950/80 border border-white/5 rounded shadow-inner">
            Ctrl + K
          </kbd>
        </div>
      </div>

      {/* Right Section: Telemetry HUD & Profile Menu */}
      <div className="flex items-center gap-4 text-xs">
        {/* Account Selector */}
        <div className="relative">
          <button
            onClick={() => setShowAccountDropdown(!showAccountDropdown)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded border font-semibold tracking-wide text-[10px] uppercase transition-all ${
              currentAccount.type === "live"
                ? "bg-rose-500/10 border-rose-500/30 text-rose-400 shadow-md shadow-rose-950/10"
                : "bg-amber-500/10 border-amber-500/30 text-amber-400"
            }`}
          >
            <KeyRound className="w-3 h-3" />
            <span>{currentAccount.type === "live" ? "Live Account" : "Paper Mode"}</span>
            <ChevronDown className="w-3 h-3 text-slate-500" />
          </button>

          {showAccountDropdown && (
            <div className="absolute right-0 mt-1.5 w-40 bg-slate-950 border border-white/10 rounded-md shadow-xl py-1 z-50 animate-in fade-in slide-in-from-top-1 duration-100">
              <button
                onClick={() => {
                  setAccount({ id: "paper-default", name: "Paper Account", type: "paper" });
                  setShowAccountDropdown(false);
                }}
                className="w-full text-left px-3 py-1.5 hover:bg-white/5 text-slate-300 hover:text-white flex items-center justify-between text-[11px]"
              >
                <span>PAPER ACCOUNT</span>
                {currentAccount.type === "paper" && <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />}
              </button>
              <button
                onClick={() => {
                  setAccount({ id: "live-default", name: "Live Account", type: "live" });
                  setShowAccountDropdown(false);
                }}
                className="w-full text-left px-3 py-1.5 hover:bg-white/5 text-slate-300 hover:text-white flex items-center justify-between text-[11px]"
              >
                <span className="text-rose-400 font-semibold">LIVE ACCOUNT</span>
                {currentAccount.type === "live" && <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />}
              </button>
            </div>
          )}
        </div>

        {/* Market Status Indicator */}
        <div className="hidden md:flex items-center gap-1.5 text-[10px] text-slate-400 tracking-wider">
          <Globe className="w-3.5 h-3.5 text-cyan-400" />
          <span className="uppercase text-slate-500">NSE Status:</span>
          <span className="flex items-center gap-1 font-semibold text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
            OPEN
          </span>
        </div>

        {/* WebSocket Connection Status */}
        <div className="hidden lg:flex items-center gap-1.5 text-[10px] text-slate-400 tracking-wider border-l border-white/5 pl-4">
          <Wifi className="w-3.5 h-3.5 text-cyan-400" />
          <span className="uppercase text-slate-500">Telemetry Stream:</span>
          <span className="flex items-center gap-1 font-semibold text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            CONNECTED
          </span>
        </div>

        {/* Notifications Bell */}
        <button className="relative text-slate-400 hover:text-slate-100 transition-colors p-1 cursor-pointer">
          <Bell className="w-4 h-4" />
          <span className="absolute -top-0.5 -right-0.5 w-3 h-3 bg-cyan-500 text-[8px] font-bold text-slate-950 flex items-center justify-center rounded-full">
            2
          </span>
        </button>

        {/* User Menu */}
        <div className="relative">
          <button
            onClick={() => setShowUserDropdown(!showUserDropdown)}
            className="flex items-center gap-1.5 hover:text-white transition-colors cursor-pointer"
          >
            <div className="w-5.5 h-5.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 flex items-center justify-center font-bold text-[10px]">
              RM
            </div>
            <ChevronDown className="w-3 h-3 text-slate-500" />
          </button>

          {showUserDropdown && (
            <div className="absolute right-0 mt-1.5 w-48 bg-slate-950 border border-white/10 rounded-md shadow-xl py-1.5 z-50 text-[11px]">
              <div className="px-3 py-2 border-b border-white/5 text-slate-400">
                <p className="font-semibold text-slate-200">Raju Maharjan</p>
                <p className="text-[10px] text-slate-500 mt-0.5">Trader ID: #VALK-9812</p>
              </div>
              <button className="w-full text-left px-3 py-1.5 hover:bg-white/5 text-slate-300">Terminal Settings</button>
              <button className="w-full text-left px-3 py-1.5 hover:bg-white/5 text-slate-300">API Credentials</button>
              <div className="border-t border-white/5 my-1" />
              <button className="w-full text-left px-3 py-1.5 hover:bg-rose-500/10 text-rose-400">Halt Engine & Log Out</button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
export default Header;
