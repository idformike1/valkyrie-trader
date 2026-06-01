import React, { useState } from "react";
import { 
  Layers, Search, Bell, User, CheckCircle2, AlertTriangle, 
  ChevronDown, Globe, Wifi, KeyRound, Sun, Moon
} from "lucide-react";
import { useWorkspaceStore } from "@/store/useWorkspaceStore";
import { useCommandPaletteStore } from "@/store/useCommandPaletteStore";
import { getWorkspaceConfig } from "@/workspaces/registry";
import { useThemeStore } from "@/store/useThemeStore";

import { useTerminalStore } from "@/store/useTerminalStore";

export const Header: React.FC = () => {
  const { theme, setTheme } = useThemeStore();
  const selectedWorkspace = useTerminalStore((state) => state.selectedWorkspace);
  const currentAccount = useTerminalStore((state) => state.currentAccount);
  const setAccount = useTerminalStore((state) => state.setAccount);
  
  const toggleCommandPalette = useCommandPaletteStore((state) => state.toggleOpen);
  const config = getWorkspaceConfig(selectedWorkspace);

  const [showAccountDropdown, setShowAccountDropdown] = useState(false);
  const [showUserDropdown, setShowUserDropdown] = useState(false);

  return (
    <header className="h-10 border-b border-subtle bg-deep flex items-center justify-between px-4 select-none shrink-0 font-sans z-30">
      {/* Left Section: Workspace Selector */}
      <div className="flex items-center gap-2 cursor-pointer">
        <span className="text-[10px] uppercase text-slate-400 tracking-wider font-bold">Workspace</span>
        <button className="flex items-center gap-1.5 px-2.5 py-1 hover:bg-card-hover rounded-sm text-[11px] font-black text-slate-200 uppercase transition-colors">
          <span>{config ? `${config.name} Desk` : "Terminal"}</span>
          <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
        </button>
      </div>

      {/* Center Section: Global Search / Command Palette Trigger */}
      <div className="flex-1 max-w-md mx-6">
        <div 
          onClick={toggleCommandPalette}
          className="flex items-center gap-2 px-3 py-1.5 bg-card border border-subtle rounded-sm cursor-pointer hover:border-cyan-neon/30 hover:bg-card-hover transition-all text-slate-500 hover:text-slate-300 group"
        >
          <Search className="w-3.5 h-3.5 group-hover:text-cyan-neon transition-colors" />
          <span className="text-[11px] text-left flex-1 select-none text-slate-300 font-medium">
            Search workspaces or operations...
          </span>
          <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-[8.5px] font-mono font-bold text-slate-400 bg-deep border border-subtle rounded-sm">
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
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-sm border font-semibold tracking-wide text-[9px] uppercase transition-all cursor-pointer ${
              currentAccount.type === "live"
                ? "bg-rose-500/10 border-rose-500/20 text-rose-455"
                : "bg-amber-500/10 border-amber-500/20 text-amber-455"
            }`}
          >
            <KeyRound className="w-3 h-3" />
            <span>{currentAccount.type === "live" ? "Live Account" : "Paper Mode"}</span>
            <ChevronDown className="w-3 h-3 text-slate-500" />
          </button>

          {showAccountDropdown && (
            <div className="absolute right-0 mt-1 w-44 bg-elevated border border-subtle rounded-sm shadow-md py-1 z-50 font-sans">
              <button
                onClick={() => {
                  setAccount({ id: "paper-default", name: "Paper Account", type: "paper" });
                  setShowAccountDropdown(false);
                }}
                className="w-full text-left px-3 py-1.5 hover:bg-card-hover text-slate-350 hover:text-main flex items-center justify-between text-[10px] font-medium transition-colors cursor-pointer"
              >
                <span>PAPER MODE</span>
                {currentAccount.type === "paper" && <span className="w-1.5 h-1.5 rounded-full bg-amber-455" />}
              </button>
              <button
                onClick={() => {
                  setAccount({ id: "live-default", name: "Live Account", type: "live" });
                  setShowAccountDropdown(false);
                }}
                className="w-full text-left px-3 py-1.5 hover:bg-card-hover text-slate-350 hover:text-main flex items-center justify-between text-[10px] font-medium transition-colors cursor-pointer"
              >
                <span className="text-rose-455 font-semibold">LIVE ACCOUNT</span>
                {currentAccount.type === "live" && <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />}
              </button>
            </div>
          )}
        </div>

        {/* Market Status Indicator */}
        <div className="hidden md:flex items-center gap-1.5 text-[9px] text-slate-400 tracking-wider">
          <Globe className="w-3 h-3 text-cyan-neon" />
          <span className="uppercase text-slate-500 font-semibold">NSE Status:</span>
          <span className="flex items-center gap-1 font-semibold text-emerald-450">
            <span className="w-1 h-1 rounded-full bg-emerald-450 animate-pulse" />
            OPEN
          </span>
        </div>

        {/* WebSocket Connection Status */}
        <div className="hidden lg:flex items-center gap-1.5 text-[9px] text-slate-400 tracking-wider border-l border-subtle pl-4">
          <Wifi className="w-3 h-3 text-cyan-neon" />
          <span className="uppercase text-slate-500 font-semibold">Telemetry Stream:</span>
          <span className="flex items-center gap-1 font-semibold text-emerald-450">
            <span className="w-1 h-1 rounded-full bg-emerald-450" />
            CONNECTED
          </span>
        </div>

        {/* Dynamic Theme Toggle */}
        <button
          onClick={() => setTheme(theme === "navy" ? "light" : "navy")}
          className="text-slate-400 hover:text-main transition-colors p-1 cursor-pointer rounded-sm hover:bg-card-hover border border-transparent hover:border-subtle flex items-center justify-center"
          title={`Switch to ${theme === "navy" ? "Light" : "Navy"} Theme`}
        >
          {theme === "navy" ? (
            <Sun className="w-3.5 h-3.5 text-amber-455" />
          ) : (
            <Moon className="w-3.5 h-3.5 text-indigo-455" />
          )}
        </button>

        {/* Notifications Bell */}
        <button className="relative text-slate-400 hover:text-main transition-colors p-1 cursor-pointer rounded-sm hover:bg-card-hover border border-transparent hover:border-subtle flex items-center justify-center">
          <Bell className="w-3.5 h-3.5" />
          <span className="absolute top-0 right-0 w-2.5 h-2.5 bg-cyan-neon text-[7px] font-bold text-white flex items-center justify-center rounded-full">
            2
          </span>
        </button>

        {/* User Menu */}
        <div className="relative">
          <button
            onClick={() => setShowUserDropdown(!showUserDropdown)}
            className="flex items-center gap-1.5 hover:text-main transition-colors cursor-pointer"
          >
            <div className="w-5 h-5 rounded-sm bg-cyan-neon/10 border border-cyan-neon/20 text-cyan-neon flex items-center justify-center font-bold text-[9px]">
              RM
            </div>
            <ChevronDown className="w-3 h-3 text-slate-500" />
          </button>

          {showUserDropdown && (
            <div className="absolute right-0 mt-1 w-48 bg-elevated border border-subtle rounded-sm shadow-md py-1 z-50 text-[10px] font-sans">
              <div className="px-3 py-1.5 border-b border-subtle text-slate-400">
                <p className="font-semibold text-main">Raju Maharjan</p>
                <p className="text-[8px] text-slate-500 mt-0.5">Trader ID: #VALK-9812</p>
              </div>
              <button className="w-full text-left px-3 py-1.5 hover:bg-card-hover text-slate-350 hover:text-main transition-colors cursor-pointer">Terminal Settings</button>
              <button className="w-full text-left px-3 py-1.5 hover:bg-card-hover text-slate-350 hover:text-main transition-colors cursor-pointer">API Credentials</button>
              <div className="border-t border-subtle my-1" />
              <button className="w-full text-left px-3 py-1.5 hover:bg-rose-500/10 text-rose-455 font-semibold transition-colors cursor-pointer">Halt Engine & Log Out</button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
export default Header;
