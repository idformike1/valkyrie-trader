import React, { useRef } from "react";
import { useTerminalStore } from "@/store/useTerminalStore";
import { useLayoutStore } from "@/store/useLayoutStore";
import { getWorkspaceConfig } from "@/workspaces/registry";
import Panel from "./Panel";

export const WorkspaceHost: React.FC = () => {
  const activeWorkspaceId = useTerminalStore((state) => state.selectedWorkspace);
  const layout = useLayoutStore((state) => state.layouts[activeWorkspaceId]) || {
    leftWidth: 260,
    rightWidth: 320,
    bottomHeight: 200,
    leftCollapsed: false,
    rightCollapsed: false,
    bottomCollapsed: false,
  };

  const updateSize = useLayoutStore((state) => state.updateSize);
  const toggleCollapse = useLayoutStore((state) => state.toggleCollapse);

  const containerRef = useRef<HTMLDivElement>(null);

  const config = getWorkspaceConfig(activeWorkspaceId);

  if (!config) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-950/20 text-slate-400">
        Workspace not found: {activeWorkspaceId}
      </div>
    );
  }

  const { left: LeftPanel, main: MainPanel, right: RightPanel, bottom: BottomPanel } = config.panels;

  const handleResize = (panel: "left" | "right" | "bottom") => (mouseDownEvent: React.MouseEvent) => {
    mouseDownEvent.preventDefault();
    if (!containerRef.current) return;

    const containerRect = containerRef.current.getBoundingClientRect();

    const handleMouseMove = (mouseMoveEvent: MouseEvent) => {
      let newSize = 0;

      if (panel === "left") {
        newSize = mouseMoveEvent.clientX - containerRect.left;
        // Apply limits
        newSize = Math.max(150, Math.min(newSize, 600));
        updateSize(activeWorkspaceId, "left", newSize);
      } else if (panel === "right") {
        newSize = containerRect.right - mouseMoveEvent.clientX;
        // Apply limits
        newSize = Math.max(150, Math.min(newSize, 600));
        updateSize(activeWorkspaceId, "right", newSize);
      } else if (panel === "bottom") {
        newSize = containerRect.bottom - mouseMoveEvent.clientY;
        // Apply limits
        newSize = Math.max(80, Math.min(newSize, 500));
        updateSize(activeWorkspaceId, "bottom", newSize);
      }
    };

    const handleMouseUp = () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      document.body.classList.remove("cursor-col-resize", "cursor-row-resize");
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
    document.body.classList.add(
      panel === "bottom" ? "cursor-row-resize" : "cursor-col-resize"
    );
  };

  return (
    <div ref={containerRef} className="flex-1 flex flex-col overflow-hidden h-full p-2 gap-2 select-none">
      {/* Top Section: Left + Main + Right Panels */}
      <div className="flex-1 flex flex-row overflow-hidden min-h-0 gap-2 relative">
        {/* Left Panel */}
        {LeftPanel && (
          <div
            style={{
              width: layout.leftCollapsed ? "auto" : `${layout.leftWidth || 260}px`,
              transition: "width 0.15s ease-out",
            }}
            className="flex shrink-0 min-h-0"
          >
            <Panel
              title={`${config.name} Sidebar`}
              isCollapsed={layout.leftCollapsed}
              onCollapseToggle={() => toggleCollapse(activeWorkspaceId, "left")}
            >
              <LeftPanel workspaceId={activeWorkspaceId} />
            </Panel>
          </div>
        )}

        {/* Left Resize Handle */}
        {LeftPanel && !layout.leftCollapsed && (
          <div
            className="w-1 hover:w-1.5 bg-transparent hover:bg-cyan-500/40 cursor-col-resize transition-all shrink-0 self-stretch rounded"
            onMouseDown={handleResize("left")}
          />
        )}

        {/* Main Panel */}
        <div className="flex-1 min-w-0 min-h-0">
          <Panel title={`${config.name} Main Desktop`} canCollapse={false}>
            <MainPanel workspaceId={activeWorkspaceId} />
          </Panel>
        </div>

        {/* Right Resize Handle */}
        {RightPanel && !layout.rightCollapsed && (
          <div
            className="w-1 hover:w-1.5 bg-transparent hover:bg-cyan-500/40 cursor-col-resize transition-all shrink-0 self-stretch rounded"
            onMouseDown={handleResize("right")}
          />
        )}

        {/* Right Panel */}
        {RightPanel && (
          <div
            style={{
              width: layout.rightCollapsed ? "auto" : `${layout.rightWidth || 320}px`,
              transition: "width 0.15s ease-out",
            }}
            className="flex shrink-0 min-h-0"
          >
            <Panel
              title="Execution & Stats"
              isCollapsed={layout.rightCollapsed}
              onCollapseToggle={() => toggleCollapse(activeWorkspaceId, "right")}
            >
              <RightPanel workspaceId={activeWorkspaceId} />
            </Panel>
          </div>
        )}
      </div>

      {/* Bottom Section: Bottom Panel */}
      {BottomPanel && (
        <>
          {/* Bottom Resize Handle */}
          {!layout.bottomCollapsed && (
            <div
              className="h-1 hover:h-1.5 bg-transparent hover:bg-cyan-500/40 cursor-row-resize transition-all shrink-0 w-full rounded"
              onMouseDown={handleResize("bottom")}
            />
          )}

          <div
            style={{
              height: layout.bottomCollapsed ? "32px" : `${layout.bottomHeight || 200}px`,
              transition: "height 0.15s ease-out",
            }}
            className="shrink-0 flex flex-col min-w-0"
          >
            {layout.bottomCollapsed ? (
              <div 
                className="flex items-center justify-between px-3 py-1.5 bg-slate-900/50 border border-white/5 rounded-md cursor-pointer hover:bg-slate-900 transition-all text-[10px] font-bold text-slate-400 uppercase select-none tracking-widest"
                onClick={() => toggleCollapse(activeWorkspaceId, "bottom")}
              >
                <span>{config.name} Ledger / Telemetry</span>
                <span className="text-[9px] text-cyan-400">CLICK TO EXPAND</span>
              </div>
            ) : (
              <Panel
                title={`${config.name} Ledger & Analytics`}
                isCollapsed={false}
                onCollapseToggle={() => toggleCollapse(activeWorkspaceId, "bottom")}
              >
                <BottomPanel workspaceId={activeWorkspaceId} />
              </Panel>
            )}
          </div>
        </>
      )}

      {/* Developer Context HUD */}
      <DevContextHUD />
    </div>
  );
};

const DevContextHUD: React.FC = () => {
  const [isOpen, setIsOpen] = React.useState(false);
  const context = useTerminalStore();

  const simulateInstrumentCycle = () => {
    const instruments = [
      { instrumentKey: "NSE_INDEX|NIFTY_50", symbol: "NIFTY 50", exchange: "NSE" as const },
      { instrumentKey: "NSE_INDEX|BANKNIFTY", symbol: "BANKNIFTY", exchange: "NSE" as const },
      { instrumentKey: "NSE_EQ|RELIANCE", symbol: "RELIANCE", exchange: "NSE" as const },
    ];
    const currentIdx = instruments.findIndex(i => i.symbol === context.selectedInstrument?.symbol);
    const nextIdx = (currentIdx + 1) % instruments.length;
    context.setInstrument(instruments[nextIdx]);
  };

  const simulateStrategyCycle = () => {
    const strategies = [
      { strategyId: "ema-pullback", strategyName: "EMA Pullback v4", version: "v4.2.1" },
      { strategyId: "vwap-reversal", strategyName: "VWAP Reversal v2", version: "v2.0.4" },
    ];
    const currentIdx = strategies.findIndex(s => s.strategyId === context.selectedStrategy?.strategyId);
    const nextIdx = (currentIdx + 1) % strategies.length;
    context.setStrategy(strategies[nextIdx]);
  };

  const simulateTimeframeCycle = () => {
    const timeframes = ["1m", "3m", "5m", "15m", "1h", "1d"] as const;
    const currentIdx = timeframes.indexOf(context.selectedTimeframe);
    const nextIdx = (currentIdx + 1) % timeframes.length;
    context.setTimeframe(timeframes[nextIdx]);
  };

  const simulateModeCycle = () => {
    const modes = ["manual", "scalper", "paper", "backtest", "live"] as const;
    const currentIdx = modes.indexOf(context.activeMode);
    const nextIdx = (currentIdx + 1) % modes.length;
    context.setMode(modes[nextIdx]);
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-8 right-4 z-40 bg-slate-900/90 border border-cyan-500/30 text-cyan-400 font-bold px-2.5 py-1 rounded shadow-lg shadow-cyan-950/20 text-[9px] uppercase tracking-wider hover:bg-slate-800 hover:border-cyan-400/50 transition-all cursor-pointer"
      >
        DEV HUD
      </button>
    );
  }

  return (
    <div className="fixed bottom-8 right-4 z-40 bg-slate-950/95 border border-cyan-500/50 rounded-lg shadow-2xl p-3.5 w-72 text-[10px] font-mono text-slate-300 select-text">
      <div className="flex justify-between items-center border-b border-cyan-500/30 pb-1.5 mb-2.5">
        <span className="text-cyan-400 font-bold uppercase tracking-wider text-[9px]">DEV CONTEXT HUD</span>
        <button onClick={() => setIsOpen(false)} className="text-slate-500 hover:text-slate-200 uppercase text-[8px] font-bold cursor-pointer">CLOSE</button>
      </div>

      <div className="flex flex-col gap-1.5">
        <div className="flex justify-between border-b border-white/[0.02] py-0.5">
          <span className="text-slate-500">Account:</span>
          <span className="text-slate-200 font-semibold">{context.currentAccount.name} ({context.currentAccount.type})</span>
        </div>
        <div className="flex justify-between border-b border-white/[0.02] py-0.5">
          <span className="text-slate-500">Instrument:</span>
          <span className="text-cyan-400 font-semibold">
            {context.selectedInstrument ? `${context.selectedInstrument.symbol} [${context.selectedInstrument.exchange}]` : "NONE"}
          </span>
        </div>
        <div className="flex justify-between border-b border-white/[0.02] py-0.5">
          <span className="text-slate-500">Strategy:</span>
          <span className="text-amber-400 font-semibold">
            {context.selectedStrategy ? `${context.selectedStrategy.strategyName} (${context.selectedStrategy.version})` : "NONE"}
          </span>
        </div>
        <div className="flex justify-between border-b border-white/[0.02] py-0.5">
          <span className="text-slate-500">Timeframe:</span>
          <span className="text-purple-400 font-semibold">{context.selectedTimeframe}</span>
        </div>
        <div className="flex justify-between border-b border-white/[0.02] py-0.5">
          <span className="text-slate-500">Workspace:</span>
          <span className="text-pink-400 font-semibold uppercase">{context.selectedWorkspace}</span>
        </div>
        <div className="flex justify-between border-b border-white/[0.02] py-0.5">
          <span className="text-slate-500">Active Mode:</span>
          <span className="text-emerald-400 font-bold uppercase">{context.activeMode}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-1.5 mt-3 pt-2.5 border-t border-cyan-500/20">
        <button onClick={simulateInstrumentCycle} className="bg-slate-900 hover:bg-slate-800 border border-white/5 py-1 text-center hover:border-cyan-500/40 rounded transition-all text-[8px] uppercase cursor-pointer">
          Cycle Instrument
        </button>
        <button onClick={simulateStrategyCycle} className="bg-slate-900 hover:bg-slate-800 border border-white/5 py-1 text-center hover:border-cyan-500/40 rounded transition-all text-[8px] uppercase cursor-pointer">
          Cycle Strategy
        </button>
        <button onClick={simulateTimeframeCycle} className="bg-slate-900 hover:bg-slate-800 border border-white/5 py-1 text-center hover:border-cyan-500/40 rounded transition-all text-[8px] uppercase cursor-pointer">
          Cycle Timeframe
        </button>
        <button onClick={simulateModeCycle} className="bg-slate-900 hover:bg-slate-800 border border-white/5 py-1 text-center hover:border-cyan-500/40 rounded transition-all text-[8px] uppercase cursor-pointer">
          Cycle Mode
        </button>
        <button onClick={context.resetTerminalContext} className="col-span-2 bg-rose-950/40 border border-rose-800/40 hover:bg-rose-900/40 py-1 text-center text-rose-400 rounded transition-all text-[8px] uppercase font-bold mt-0.5 cursor-pointer">
          Reset All Context
        </button>
      </div>
    </div>
  );
};

export default WorkspaceHost;
