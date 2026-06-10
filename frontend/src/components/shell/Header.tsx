import React, { useState, useEffect } from "react";
import { 
  Layers, Search, Bell, User, CheckCircle2, AlertTriangle, 
  ChevronDown, Globe, Wifi, KeyRound, Sun, Moon, Shield,
  X, ExternalLink
} from "lucide-react";
import { useWorkspaceStore } from "@/store/useWorkspaceStore";
import { useCommandPaletteStore } from "@/store/useCommandPaletteStore";
import { getWorkspaceConfig, getAllWorkspaces } from "@/workspaces/registry";
import { useThemeStore } from "@/store/useThemeStore";
import { useTerminalStore } from "@/store/useTerminalStore";
import { useBackendTradingStore } from "@/services/tradingQueries";
import { Button } from "@/components/ui/material-design-3-button";

export const Header: React.FC = () => {
  const { theme, setTheme } = useThemeStore();
  const selectedWorkspace = useTerminalStore((state) => state.selectedWorkspace);
  const setWorkspace = useTerminalStore((state) => state.setWorkspace);
  const currentAccount = useTerminalStore((state) => state.currentAccount);
  const setAccount = useTerminalStore((state) => state.setAccount);
  
  const toggleCommandPalette = useCommandPaletteStore((state) => state.toggleOpen);
  const config = getWorkspaceConfig(selectedWorkspace);
  const workspaces = getAllWorkspaces();

  const [showWorkspaceDropdown, setShowWorkspaceDropdown] = useState(false);
  const [showAccountDropdown, setShowAccountDropdown] = useState(false);
  const [showUserDropdown, setShowUserDropdown] = useState(false);

  const status = useBackendTradingStore((state) => state.status);
  const connectionStatus = useBackendTradingStore((state) => state.connectionStatus);

  const [isAuthLoading, setIsAuthLoading] = useState(false);
  const isUpstoxConnected = status?.broker_auth === "Valid";
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authCode, setAuthCode] = useState("");
  const [rawTokenInput, setRawTokenInput] = useState("");
  const [authUrl, setAuthUrl] = useState("");

  // Check for oauth code in URL query params on load
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get("code");
    if (code) {
      // Clear the code from URL immediately to keep it clean and prevent double-submission
      const newUrl = window.location.pathname;
      window.history.replaceState({}, document.title, newUrl);
      
      // Submit code to backend
      const handleAuthCallback = async () => {
        setIsAuthLoading(true);
        try {
          const { tradingApi } = await import("@/services/tradingApi");
          const res = await tradingApi.submitUpstoxCallback(code);
          if (res.status === "success") {
            alert("✅ Upstox connected successfully!");
            window.location.reload();
          } else {
            alert("❌ Upstox connection failed: " + res.message);
          }
        } catch (err: any) {
          alert("❌ Upstox connection failed: " + err.message);
        } finally {
          setIsAuthLoading(false);
        }
      };
      handleAuthCallback();
    }
  }, []);

  const handleConnectDisconnect = async () => {
    setIsAuthLoading(true);
    try {
      const { tradingApi } = await import("@/services/tradingApi");
      if (isUpstoxConnected) {
        const res = await tradingApi.disconnectUpstox();
        if (res.status === "success") {
          alert("🔌 Disconnected from Upstox.");
          window.location.reload();
        }
      } else {
        // Try reconnecting using the stored token first!
        try {
          const res = await tradingApi.reconnectUpstox();
          if (res.status === "success") {
            alert("✅ Reconnected using stored token!");
            window.location.reload();
            return;
          }
        } catch (reconnectErr) {
          console.log("No valid stored token to reconnect, opening login flow.");
        }

        // Fetch the auth URL and show the authorization modal
        try {
          const res = await tradingApi.getUpstoxAuthUrl();
          if (res.url) {
            setAuthUrl(res.url);
          }
        } catch (err: any) {
          console.error("Failed to load auth URL:", err);
        }
        setShowAuthModal(true);
      }
    } catch (err: any) {
      alert("Error: " + err.message);
    } finally {
      setIsAuthLoading(false);
    }
  };

  const handleSubmitCode = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!authCode.trim()) return;
    setIsAuthLoading(true);
    try {
      const { tradingApi } = await import("@/services/tradingApi");
      const res = await tradingApi.submitUpstoxCallback(authCode.trim());
      if (res.status === "success") {
        alert("✅ Connected to Upstox successfully!");
        setShowAuthModal(false);
        window.location.reload();
      } else {
        alert("❌ Upstox connection failed: " + res.message);
      }
    } catch (err: any) {
      alert("❌ Upstox connection failed: " + err.message);
    } finally {
      setIsAuthLoading(false);
    }
  };

  const handleSubmitRawToken = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rawTokenInput.trim()) return;
    setIsAuthLoading(true);
    try {
      const { tradingApi } = await import("@/services/tradingApi");
      const res = await tradingApi.submitRawToken(rawTokenInput.trim());
      if (res.status === "success") {
        alert("✅ Access token saved successfully!");
        setShowAuthModal(false);
        window.location.reload();
      } else {
        alert("❌ Upstox connection failed: " + res.message);
      }
    } catch (err: any) {
      alert("❌ Upstox connection failed: " + err.message);
    } finally {
      setIsAuthLoading(false);
    }
  };

  // Live index ticker state
  const [tickerData, setTickerData] = useState({
    nifty: { price: 23395.55, change: 153.45, pct: 0.66 },
    banknifty: { price: 55477.40, change: 282.90, pct: 0.51 },
    vix: { price: 15.49, change: -0.09, pct: -0.58 }
  });

  useEffect(() => {
    const fetchIndices = async () => {
      try {
        const { tradingApi } = await import("@/services/tradingApi");
        const res = await tradingApi.getMarketIndices();
        if (res.status === "success" && res.data) {
          setTickerData(res.data);
        }
      } catch (err) {
        // Fallback silently
      }
    };
    fetchIndices();
    const timer = setInterval(fetchIndices, 3000);
    return () => clearInterval(timer);
  }, []);

  // Dynamic positions P&L for header account indicator
  const [headerPnl, setHeaderPnl] = useState<number>(0);
  useEffect(() => {
    const fetchHeaderPnl = async () => {
      try {
        const { tradingApi } = await import("@/services/tradingApi");
        const res = await tradingApi.getBrokerPositions();
        if (res.status === "success" && Array.isArray(res.data)) {
          const unrealised = res.data.reduce((acc: number, pos: any) => acc + Number(pos.unrealised || 0), 0);
          const realised = res.data.reduce((acc: number, pos: any) => acc + Number(pos.realised || 0), 0);
          setHeaderPnl(unrealised + realised);
        }
      } catch (err) {
        // Fallback silently
      }
    };
    fetchHeaderPnl();
    const interval = setInterval(fetchHeaderPnl, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      {status?.broker_auth === "Expired" && (
        <div className="w-full bg-gradient-to-r from-red-950 via-rose-900 to-red-950 border-b border-red-500/20 py-1.5 px-4 text-center select-none flex items-center justify-center gap-2 shrink-0 animate-pulse z-50">
          <span className="body font-semibold text-rose-100 font-sans flex items-center gap-1.5">
            ⚠ Broker Authentication Expired. Live quotes unavailable. Reconnect Upstox to resume live execution.
          </span>
        </div>
      )}
      <header className="h-10 border-b border-subtle bg-deep flex items-center justify-between px-4 select-none shrink-0 font-sans z-30">
        {/* 1. Workspace navigation */}
        <div className="flex items-center gap-2.5 shrink-0 relative">
          <div className="flex items-center gap-1.5 select-none">
            <div className="w-5 h-5 bg-cyan-neon rounded-sm flex items-center justify-center font-semibold body text-white">V</div>
            <span className="body font-semibold text-slate-100 font-display">
              Valkyrie<span className="text-cyan-neon">_</span>
            </span>
          </div>
          <div className="h-4 w-[1px] bg-white/10" />

          {/* Combined Workspace Selector & Trigger */}
          <div className="relative">
            <Button
              onClick={() => setShowWorkspaceDropdown(!showWorkspaceDropdown)}
              variant="ghost"
              className="flex items-center gap-1.5 px-2 py-1 text-cyan-neon font-sans font-semibold cursor-pointer"
              title="Switch Workspace"
            >
              <span className="body">
                {workspaces.find((ws) => ws.id === selectedWorkspace)?.name || selectedWorkspace}
              </span>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            </Button>

            {showWorkspaceDropdown && (
              <>
                <div 
                  className="fixed inset-0 z-40" 
                  onClick={() => setShowWorkspaceDropdown(false)}
                />
                <div className="absolute left-0 mt-1.5 w-44 bg-deep border border-subtle rounded shadow-lg py-1 z-50 font-sans">
                  {workspaces.map((ws) => {
                    const isActive = selectedWorkspace === ws.id;
                    return (
                      <button
                        key={ws.id}
                        onClick={() => {
                          setWorkspace(ws.id);
                          setShowWorkspaceDropdown(false);
                        }}
                        className={`w-full text-left px-3 py-1.5 body font-semibold transition-all cursor-pointer flex items-center justify-between${
                          isActive 
                            ? "text-cyan-neon bg-cyan-500/10 font-semibold" 
                            : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.02]"
                        }`}
                      >
                        <span>{ws.name}</span>
                        {isActive && <span className="w-1 h-1 rounded-full bg-cyan-neon" />}
                      </button>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Visually Prominent Search Bar */}
        <div 
          onClick={toggleCommandPalette}
          className="w-64 flex items-center gap-2 px-3 py-1 bg-deep/40 border border-subtle rounded-md hover:border-cyan-neon/30 hover:bg-deep/60 transition-all text-slate-400 cursor-pointer select-none mx-4"
        >
          <Search className="w-3.5 h-3.5 text-slate-500" />
          <span className="body text-slate-500 font-medium flex-1 text-left">Search commands & symbols...</span>
          <kbd className="text-[9px] font-mono bg-card border border-subtle px-1.5 py-0.5 rounded text-slate-500">⌘K</kbd>
        </div>

        {/* 2. Market indices & 3. Account state */}
        <div className="flex-1 flex justify-center items-center gap-6 mx-2">
          <div className="flex items-center gap-4 body font-mono select-none tabular-nums">
            <div className="flex items-center gap-1.5">
              <span className="text-slate-500 font-semibold font-sans">NIFTY</span>
              <span className={`font-semibold${tickerData.nifty.change >= 0 ? "text-emerald-400" : "text-rose-500"}`}>
                {tickerData.nifty.price.toFixed(2)}
              </span>
              <span className={`font-semibold${tickerData.nifty.change >= 0 ? "text-emerald-400" : "text-rose-500"}`}>
                {tickerData.nifty.change >= 0 ? "+" : ""}{tickerData.nifty.pct.toFixed(2)}%
              </span>
            </div>
            <div className="flex items-center gap-1.5 border-l border-subtle pl-4">
              <span className="text-slate-500 font-semibold font-sans">BANKNIFTY</span>
              <span className={`font-semibold${tickerData.banknifty.change >= 0 ? "text-emerald-400" : "text-rose-500"}`}>
                {tickerData.banknifty.price.toFixed(2)}
              </span>
              <span className={`font-semibold${tickerData.banknifty.change >= 0 ? "text-emerald-400" : "text-rose-500"}`}>
                {tickerData.banknifty.change >= 0 ? "+" : ""}{tickerData.banknifty.pct.toFixed(2)}%
              </span>
            </div>
            <div className="flex items-center gap-1.5 border-l border-subtle pl-4">
              <span className="text-slate-500 font-semibold font-sans">VIX</span>
              <span className={`font-semibold${tickerData.vix.change >= 0 ? "text-emerald-400" : "text-rose-500"}`}>
                {tickerData.vix.price.toFixed(2)}
              </span>
              <span className={`font-semibold${tickerData.vix.change >= 0 ? "text-emerald-400" : "text-rose-500"}`}>
                {tickerData.vix.pct.toFixed(2)}%
              </span>
            </div>
            {/* Account Indicator */}
            <div className="flex items-center gap-1.5 border-l border-subtle pl-4 font-sans body font-semibold">
              <span className={currentAccount.type === "live" ? "text-rose-500" : "text-amber-500"}>
                {currentAccount.type === "live" ? "LIVE" : "PAPER"}
              </span>
              <span className={`font-mono tabular-nums font-semibold${
                headerPnl > 0 ? "text-emerald-400" : headerPnl < 0 ? "text-rose-500" : "text-slate-300"
              }`}>
                {headerPnl >= 0 ? "+" : ""}₹{headerPnl.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
          </div>
        </div>

        {/* 4. System telemetry & user actions */}
        <div className="flex items-center gap-4 body">
          {/* Account Selector */}
          <div className="relative">
            <Button
              onClick={() => setShowAccountDropdown(!showAccountDropdown)}
              variant="outline"
              className={`flex items-center gap-1.5 px-2.5 py-1 font-semibold body transition-all cursor-pointer ${
                currentAccount.type === "live"
                  ? "bg-rose-500/10 border-rose-500/20 text-rose-455 hover:bg-rose-500/20"
                  : "bg-amber-500/10 border-amber-500/20 text-amber-455 hover:bg-amber-500/20"
              }`}
            >
              <KeyRound className="w-3.5 h-3.5" />
              <span>{currentAccount.type === "live" ? "Live Account" : "Paper Mode"}</span>
              <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
            </Button>

            {showAccountDropdown && (
              <div className="absolute right-0 mt-1 w-44 bg-elevated border border-subtle rounded-sm shadow-md py-1 z-50 font-sans">
                <button
                  onClick={() => {
                    setAccount({ id: "paper-default", name: "Paper Account", type: "paper" });
                    setShowAccountDropdown(false);
                  }}
                  className="w-full text-left px-3 py-1.5 hover:bg-card-hover text-slate-350 hover:text-main flex items-center justify-between body font-medium transition-colors cursor-pointer"
                >
                  <span>PAPER MODE</span>
                  {currentAccount.type === "paper" && <span className="w-1.5 h-1.5 rounded-full bg-amber-455" />}
                </button>
                <button
                  onClick={() => {
                    setAccount({ id: "live-default", name: "Live Account", type: "live" });
                    setShowAccountDropdown(false);
                  }}
                  className="w-full text-left px-3 py-1.5 hover:bg-card-hover text-slate-350 hover:text-main flex items-center justify-between body font-medium transition-colors cursor-pointer"
                >
                  <span className="text-rose-455 font-semibold">LIVE ACCOUNT</span>
                  {currentAccount.type === "live" && <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />}
                </button>
              </div>
            )}
          </div>

          {/* Upstox Connection Control Button */}
          <Button
            onClick={handleConnectDisconnect}
            disabled={isAuthLoading || !status}
            variant="outline"
            className={`flex items-center gap-1 px-2 py-0.5 font-semibold text-[10px] uppercase tracking-wider transition-all cursor-pointer disabled:opacity-50 select-none ${
              !status
                ? "bg-slate-800/10 border-slate-700/30 text-slate-500 cursor-not-allowed"
                : isUpstoxConnected
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20"
                : "bg-cyan-neon/10 border-cyan-neon/30 text-cyan-neon hover:bg-cyan-neon/20 hover:scale-[1.02] active:scale-[0.98]"
            }`}
            title={
              !status 
                ? "Checking Upstox Connection Status..." 
                : isUpstoxConnected 
                ? "Disconnect from Upstox API" 
                : "Authenticate & Connect with Upstox API"
            }
          >
            <Globe className={`w-3 h-3 ${!status ? "animate-spin" : isUpstoxConnected ? "" : "animate-pulse"}`} />
            <span>
              {isAuthLoading 
                ? "Auth..." 
                : !status 
                ? "Checking..." 
                : isUpstoxConnected 
                ? "Upstox Connected" 
                : "Connect Upstox"}
            </span>
          </Button>

          {/* Compact Telemetry HUD */}
          <div className="flex items-center gap-2 bg-deep/20 border border-subtle py-1 px-2.5 rounded text-[10px] font-mono text-slate-500 select-none">
            <span className="flex items-center gap-1" title={`GUI: ${connectionStatus}`}>
              <span className={`w-1.5 h-1.5 rounded-full${connectionStatus === "CONNECTED" ? "bg-emerald-500" : "bg-rose-500 animate-pulse"}`} />
              <span>GUI</span>
            </span>
            <span className="flex items-center gap-1 pl-2 border-l border-subtle" title={`AUTH: ${status?.broker_auth}`}>
              <span className={`w-1.5 h-1.5 rounded-full${status?.broker_auth === "Valid" ? "bg-emerald-500" : "bg-rose-500 animate-pulse"}`} />
              <span>AUTH</span>
            </span>
            <span className="flex items-center gap-1 pl-2 border-l border-subtle" title={`FEED: ${status?.market_feed}`}>
              <span className={`w-1.5 h-1.5 rounded-full${
                status?.market_feed === "Live" ? "bg-emerald-500" :
                status?.market_feed === "Mock" ? "bg-amber-500" :
                "bg-rose-500 animate-pulse"
              }`} />
              <span className={status?.market_feed === "Mock" ? "text-amber-400" : ""}>
                {status?.market_feed === "Mock" ? "MOCK" : "FEED"}
              </span>
            </span>
            <span className="flex items-center gap-1 pl-2 border-l border-subtle" title={`ENG: ${status?.execution_engine}`}>
              <span className={`w-1.5 h-1.5 rounded-full${
                status?.execution_engine === "Running" ? "bg-emerald-500" :
                status?.execution_engine === "Paused" ? "bg-amber-500 animate-pulse" :
                "bg-rose-500"
              }`} />
              <span>ENG</span>
            </span>
          </div>

          {/* Dynamic Theme Toggle */}
          <button
            onClick={() => setTheme(theme === "navy" ? "light" : theme === "light" ? "blackstone" : "navy")}
            className="text-slate-400 hover:text-main transition-colors p-1 cursor-pointer rounded-sm hover:bg-card-hover border border-transparent hover:border-subtle flex items-center justify-center"
            title={`Switch Theme (Current: ${theme})`}
          >
            {theme === "navy" ? (
              <Sun className="w-3.5 h-3.5 text-amber-455" />
            ) : theme === "light" ? (
              <Moon className="w-3.5 h-3.5 text-indigo-455" />
            ) : (
              <Shield className="w-3.5 h-3.5 text-yellow-600" />
            )}
          </button>

          {/* Notifications Bell */}
          <button className="relative text-slate-400 hover:text-main transition-colors p-1 cursor-pointer rounded-sm hover:bg-card-hover border border-transparent hover:border-subtle flex items-center justify-center">
            <Bell className="w-3.5 h-3.5" />
            <span className="absolute top-0 right-0 w-2.5 h-2.5 bg-cyan-neon body font-semibold text-white flex items-center justify-center rounded-full">
              2
            </span>
          </button>

          {/* User Menu */}
          <div className="relative">
            <button
              onClick={() => setShowUserDropdown(!showUserDropdown)}
              className="flex items-center gap-1.5 hover:text-main transition-colors cursor-pointer"
            >
              <div className="w-5 h-5 rounded-sm bg-cyan-neon/10 border border-cyan-neon/20 text-cyan-neon flex items-center justify-center font-semibold body">
                RM
              </div>
              <ChevronDown className="w-3 h-3 text-slate-500" />
            </button>

            {showUserDropdown && (
              <div className="absolute right-0 mt-1 w-48 bg-elevated border border-subtle rounded-sm shadow-md py-1 z-50 body font-sans">
                <div className="px-3 py-1.5 border-b border-subtle text-slate-400">
                  <p className="font-semibold text-main">Raju Maharjan</p>
                  <p className="text-[10px] text-slate-500 mt-0.5">Trader ID: #VALK-9812</p>
                </div>
                <button className="w-full text-left px-3 py-1.5 hover:bg-card-hover text-slate-355 hover:text-main transition-colors cursor-pointer">Terminal Settings</button>
                <button className="w-full text-left px-3 py-1.5 hover:bg-card-hover text-slate-355 hover:text-main transition-colors cursor-pointer">API Credentials</button>
                <div className="border-t border-subtle my-1" />
                <button className="w-full text-left px-3 py-1.5 hover:bg-rose-500/10 text-rose-455 font-semibold transition-colors cursor-pointer">Halt Engine & Log Out</button>
              </div>
            )}
        </div>
      </div>
    </header>

    {/* Upstox Authentication Modal */}
    {showAuthModal && (
      <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm">
        <div className="w-full max-w-lg bg-[#0e131f] border border-slate-800 rounded-lg shadow-2xl p-6 relative font-sans text-slate-200">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-4">
            <div className="flex items-center gap-2">
              <Globe className="w-5 h-5 text-cyan-neon" />
              <h3 className="text-base font-semibold text-main uppercase tracking-wider">Upstox Broker Authorization</h3>
            </div>
            <button
              onClick={() => setShowAuthModal(false)}
              className="text-slate-400 hover:text-slate-200 transition-colors p-1 rounded-full hover:bg-slate-800"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Instruction Steps */}
          <div className="space-y-4 mb-6 text-xs text-slate-400">
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-md p-3 text-amber-400 font-medium leading-relaxed">
              ⚠️ <strong>Note on Redirects:</strong> After authorizing, you might see a connection error page (e.g. <code>127.0.0.1</code> or <code>localhost</code> refused connection). <strong>This is normal!</strong> The address bar still contains your code. Just copy the code value from the address bar URL.
            </div>

            <div className="flex flex-col gap-2">
              <p className="font-semibold text-slate-300">Follow these steps to connect:</p>
              <ol className="list-decimal list-inside space-y-2 leading-relaxed">
                <li>
                  Click the link to open the login page in a new tab:{" "}
                  <a
                    href={authUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-cyan-neon hover:underline font-semibold ml-1 bg-cyan-neon/10 px-2 py-0.5 rounded"
                  >
                    Login to Upstox <ExternalLink className="w-3 h-3" />
                  </a>
                </li>
                <li>Log in securely using your Upstox credentials (mobile number, OTP, PIN).</li>
                <li>Copy the temporary authorization code (the value after <code>code=</code> in the address bar).</li>
              </ol>
            </div>
          </div>

          {/* Submissions Section */}
          <div className="space-y-5">
            {/* Form 1: Authorization Code */}
            <form onSubmit={handleSubmitCode} className="border-t border-slate-800/60 pt-4">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                1. Paste Authorization Code
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="e.g. XXXXXX"
                  value={authCode}
                  onChange={(e) => setAuthCode(e.target.value)}
                  className="flex-1 bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-xs text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-cyan-neon"
                />
                <button
                  type="submit"
                  disabled={isAuthLoading || !authCode.trim()}
                  className="px-4 py-1.5 bg-cyan-neon/20 hover:bg-cyan-neon/30 text-cyan-neon border border-cyan-neon/30 rounded text-xs font-semibold uppercase tracking-wider transition-colors disabled:opacity-50"
                >
                  Submit Code
                </button>
              </div>
            </form>

            {/* Form 2: Direct Access Token */}
            <form onSubmit={handleSubmitRawToken} className="border-t border-slate-800/60 pt-4">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Alternative: Paste Access Token Directly
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Enter raw access token"
                  value={rawTokenInput}
                  onChange={(e) => setRawTokenInput(e.target.value)}
                  className="flex-1 bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-xs text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-cyan-neon"
                />
                <button
                  type="submit"
                  disabled={isAuthLoading || !rawTokenInput.trim()}
                  className="px-4 py-1.5 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/30 rounded text-xs font-semibold uppercase tracking-wider transition-colors disabled:opacity-50"
                  title="Directly save token to token.txt"
                >
                  Save Token
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    )}
    </>
  );
};
export default Header;
