"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  Play, Activity, Terminal, Shield, Cpu, RefreshCw, BarChart2,
  TrendingUp, Layers, Server, Settings, Zap, ArrowUpRight, ArrowDownRight,
  Sliders, Search, Plus, Trash2, SlidersHorizontal, Lock, CheckCircle2, 
  AlertTriangle, Flame, ShieldAlert, Radio, AlertCircle
} from "lucide-react";
import { useTerminalStore } from "@/store/useTerminalStore";
import { useEventStore } from "@/store/useEventStore";

// ==========================================
// SCALPER LOCAL STATE MANAGER
// ==========================================
interface ActiveScalpingPosition {
  symbol: string;
  side: "LONG" | "SHORT" | "FLAT";
  qty: number;
  avgEntry: number;
  ltp: number;
  stopPrice: number;
  targetPrice: number;
}

// ==========================================
// 1. MAIN PANEL: TICK / VOLUME CHART + EXECUTION PAD + HOTKEYS
// ==========================================
export const ScalperMain: React.FC = () => {
  const selectedInstrument = useTerminalStore((state) => state.selectedInstrument);
  const activeMode = useTerminalStore((state) => state.activeMode);
  const setMode = useTerminalStore((state) => state.setMode);
  const addEvent = useEventStore((state) => state.addEvent);

  const [activeLots, setActiveLots] = useState<number>(1);
  const [ticks, setTicks] = useState<number[]>([]);
  const [ltp, setLtp] = useState<number>(22212.50);
  
  // Active trade details
  const [trade, setTrade] = useState<ActiveScalpingPosition>({
    symbol: "NIFTY 50",
    side: "FLAT",
    qty: 0,
    avgEntry: 0,
    ltp: 22212.50,
    stopPrice: 0,
    targetPrice: 0,
  });

  const [realizedPnL, setRealizedPnL] = useState<number>(0);

  // Set activeMode to "scalper" on load
  useEffect(() => {
    if (activeMode !== "scalper") {
      setMode("scalper");
    }
  }, [activeMode, setMode]);

  // Sync symbol and reset ticks when active instrument changes
  useEffect(() => {
    if (!selectedInstrument) return;
    const base = selectedInstrument.symbol === "BANKNIFTY" ? 46770 : selectedInstrument.symbol === "RELIANCE" ? 2450 : 22210;
    
    // Generate initial ticks
    const initialTicks = Array.from({ length: 40 }, () => base + (Math.random() - 0.5) * 20);
    setTicks(initialTicks);
    setLtp(initialTicks[initialTicks.length - 1]);
    
    setTrade({
      symbol: selectedInstrument.symbol,
      side: "FLAT",
      qty: 0,
      avgEntry: 0,
      ltp: initialTicks[initialTicks.length - 1],
      stopPrice: 0,
      targetPrice: 0,
    });
  }, [selectedInstrument]);

  // Live High-Frequency Tick Generator (every 350ms)
  useEffect(() => {
    const interval = setInterval(() => {
      setTicks((prev) => {
        const next = [...prev];
        const last = next[next.length - 1] || 22210;
        const delta = (Math.random() - 0.5) * 2.5; // High speed random walk
        const newLtp = Number((last + delta).toFixed(2));
        
        next.push(newLtp);
        if (next.length > 40) next.shift();
        
        setLtp(newLtp);

        // Update active position parameters and check executions
        setTrade((currentTrade) => {
          if (currentTrade.side === "FLAT") {
            return { ...currentTrade, ltp: newLtp };
          }

          const updatedTrade = { ...currentTrade, ltp: newLtp };
          
          // Check Stop Loss hit
          if (
            (currentTrade.side === "LONG" && newLtp <= currentTrade.stopPrice) ||
            (currentTrade.side === "SHORT" && newLtp >= currentTrade.stopPrice)
          ) {
            const pnl = currentTrade.side === "LONG"
              ? (currentTrade.stopPrice - currentTrade.avgEntry) * currentTrade.qty
              : (currentTrade.avgEntry - currentTrade.stopPrice) * currentTrade.qty;
            
            setTimeout(() => {
              setRealizedPnL((prev) => prev + pnl);
              addEvent({
                type: "error",
                message: `STOP LOSS TRIGGERED - SL ${currentTrade.symbol} @ ₹${currentTrade.stopPrice.toFixed(2)} | PnL: ₹${pnl.toFixed(2)}`,
                workspace: "Scalper",
              });
            }, 0);

            return {
              ...currentTrade,
              side: "FLAT",
              qty: 0,
              avgEntry: 0,
              ltp: newLtp,
              stopPrice: 0,
              targetPrice: 0,
            };
          }

          // Check Target hit
          if (
            (currentTrade.side === "LONG" && newLtp >= currentTrade.targetPrice) ||
            (currentTrade.side === "SHORT" && newLtp <= currentTrade.targetPrice)
          ) {
            const pnl = currentTrade.side === "LONG"
              ? (currentTrade.targetPrice - currentTrade.avgEntry) * currentTrade.qty
              : (currentTrade.avgEntry - currentTrade.targetPrice) * currentTrade.qty;

            setTimeout(() => {
              setRealizedPnL((prev) => prev + pnl);
              addEvent({
                type: "success",
                message: `TARGET EXECUTED - TAKE PROFIT ${currentTrade.symbol} @ ₹${currentTrade.targetPrice.toFixed(2)} | PnL: ₹${pnl.toFixed(2)}`,
                workspace: "Scalper",
              });
            }, 0);

            return {
              ...currentTrade,
              side: "FLAT",
              qty: 0,
              avgEntry: 0,
              ltp: newLtp,
              stopPrice: 0,
              targetPrice: 0,
            };
          }

          return updatedTrade;
        });

        // Trigger local DOM update tick event
        window.dispatchEvent(new CustomEvent("scalper-tick", { detail: { ltp: newLtp } }));

        return next;
      });
    }, 350);

    return () => clearInterval(interval);
  }, [addEvent]);

  // Order Placement logic
  const handleMarketOrder = (orderSide: "BUY" | "SELL") => {
    if (!selectedInstrument) return;
    const lotMultiplier = selectedInstrument.symbol === "NIFTY 50" ? 50 : selectedInstrument.symbol === "BANKNIFTY" ? 15 : 1;
    const orderQty = activeLots * lotMultiplier;

    setTrade((current) => {
      let nextSide: "LONG" | "SHORT" | "FLAT" = "FLAT";
      let nextQty = 0;
      let nextAvg = 0;
      let nextSL = 0;
      let nextTarget = 0;

      if (current.side === "FLAT") {
        nextSide = orderSide === "BUY" ? "LONG" : "SHORT";
        nextQty = orderQty;
        nextAvg = ltp;
        nextSL = orderSide === "BUY" ? ltp - 15 : ltp + 15;
        nextTarget = orderSide === "BUY" ? ltp + 45 : ltp - 45;
        
        addEvent({
          type: "info",
          message: `SCALPER POSITION OPENED - ${nextSide} ${orderQty} Qty @ ₹${ltp.toFixed(2)}`,
          workspace: "Scalper",
        });
      } else {
        // Adding sizes or reversing position
        if ((current.side === "LONG" && orderSide === "BUY") || (current.side === "SHORT" && orderSide === "SELL")) {
          const totalCost = (current.avgEntry * current.qty) + (ltp * orderQty);
          nextQty = current.qty + orderQty;
          nextAvg = totalCost / nextQty;
          nextSide = current.side;
          nextSL = nextSide === "LONG" ? nextAvg - 15 : nextAvg + 15;
          nextTarget = nextSide === "LONG" ? nextAvg + 45 : nextAvg - 45;
          
          addEvent({
            type: "info",
            message: `SCALPER SIZE ADDED - New Qty: ${nextQty} | Avg: ₹${nextAvg.toFixed(2)}`,
            workspace: "Scalper",
          });
        } else {
          // Reversing or netting off
          const qtyDiff = current.qty - orderQty;
          if (qtyDiff > 0) {
            // Reduce size
            const partialPnL = current.side === "LONG" ? (ltp - current.avgEntry) * orderQty : (current.avgEntry - ltp) * orderQty;
            setRealizedPnL((prev) => prev + partialPnL);
            nextSide = current.side;
            nextQty = qtyDiff;
            nextAvg = current.avgEntry;
            nextSL = current.stopPrice;
            nextTarget = current.targetPrice;
            
            addEvent({
              type: "warning",
              message: `SCALPER SIZE REDUCED - Closed ${orderQty} Qty | Realized PnL: ₹${partialPnL.toFixed(2)}`,
              workspace: "Scalper",
            });
          } else if (qtyDiff === 0) {
            // Closed out
            const finalPnL = current.side === "LONG" ? (ltp - current.avgEntry) * current.qty : (current.avgEntry - ltp) * current.qty;
            setRealizedPnL((prev) => prev + finalPnL);
            
            addEvent({
              type: "success",
              message: `SCALPER POSITION FLATTENED - PnL: ₹${finalPnL.toFixed(2)}`,
              workspace: "Scalper",
            });
          } else {
            // Reversal
            const finalPnL = current.side === "LONG" ? (ltp - current.avgEntry) * current.qty : (current.avgEntry - ltp) * current.qty;
            setRealizedPnL((prev) => prev + finalPnL);
            
            nextSide = current.side === "LONG" ? "SHORT" : "LONG";
            nextQty = Math.abs(qtyDiff);
            nextAvg = ltp;
            nextSL = nextSide === "LONG" ? ltp - 15 : ltp + 15;
            nextTarget = nextSide === "LONG" ? ltp + 45 : ltp - 45;

            addEvent({
              type: "warning",
              message: `SCALPER POSITION REVERSED - ${nextSide} ${nextQty} Qty | Avg: ₹${ltp.toFixed(2)}`,
              workspace: "Scalper",
            });
          }
        }
      }

      const updated = {
        symbol: current.symbol,
        side: nextSide,
        qty: nextQty,
        avgEntry: nextAvg,
        ltp,
        stopPrice: nextSL,
        targetPrice: nextTarget,
      };

      // Emit layout event to update the Position Monitor table at the bottom
      window.dispatchEvent(new CustomEvent("scalper-position-update", { detail: { position: updated, realizedPnL } }));

      return updated;
    });
  };

  const handleFlatten = () => {
    setTrade((current) => {
      if (current.side === "FLAT") return current;
      const finalPnL = current.side === "LONG" ? (ltp - current.avgEntry) * current.qty : (current.avgEntry - ltp) * current.qty;
      setRealizedPnL((prev) => prev + finalPnL);
      
      addEvent({
        type: "success",
        message: `SCALPER EMERGENCY FLATTEN ALL - Position closed @ ₹${ltp.toFixed(2)} | PnL: ₹${finalPnL.toFixed(2)}`,
        workspace: "Scalper",
      });

      const updated = {
        symbol: current.symbol,
        side: "FLAT" as const,
        qty: 0,
        avgEntry: 0,
        ltp,
        stopPrice: 0,
        targetPrice: 0,
      };
      
      window.dispatchEvent(new CustomEvent("scalper-position-update", { detail: { position: updated, realizedPnL: realizedPnL + finalPnL } }));
      return updated;
    });
  };

  const handleCancel = () => {
    setTrade((current) => {
      if (current.side === "FLAT") return current;
      
      addEvent({
        type: "warning",
        message: "SCALPER ORDERS CANCELLED - Active Target & Stop Loss limits cleared",
        workspace: "Scalper",
      });

      const updated = {
        ...current,
        stopPrice: 0,
        targetPrice: 0,
      };
      window.dispatchEvent(new CustomEvent("scalper-position-update", { detail: { position: updated, realizedPnL } }));
      return updated;
    });
  };

  const handleReverse = () => {
    setTrade((current) => {
      if (current.side === "FLAT") return current;
      const finalPnL = current.side === "LONG" ? (ltp - current.avgEntry) * current.qty : (current.avgEntry - ltp) * current.qty;
      setRealizedPnL((prev) => prev + finalPnL);

      const nextSide: "LONG" | "SHORT" | "FLAT" = current.side === "LONG" ? "SHORT" : "LONG";
      const nextSL = nextSide === "LONG" ? ltp - 15 : ltp + 15;
      const nextTarget = nextSide === "LONG" ? ltp + 45 : ltp - 45;

      addEvent({
        type: "warning",
        message: `SCALPER POSITION REVERSED - Switched to ${nextSide} ${current.qty} Qty @ ₹${ltp.toFixed(2)}`,
        workspace: "Scalper",
      });

      const updated = {
        ...current,
        side: nextSide,
        avgEntry: ltp,
        stopPrice: nextSL,
        targetPrice: nextTarget,
      };
      window.dispatchEvent(new CustomEvent("scalper-position-update", { detail: { position: updated, realizedPnL: realizedPnL + finalPnL } }));
      return updated;
    });
  };

  // Sync local changes from bottom position monitor closures
  useEffect(() => {
    const handlePosCloseEvent = () => {
      handleFlatten();
    };
    window.addEventListener("scalper-close-position", handlePosCloseEvent);
    return () => window.removeEventListener("scalper-close-position", handlePosCloseEvent);
  }, [ltp, realizedPnL]);

  // Sync tick updates to positions monitor
  useEffect(() => {
    window.dispatchEvent(new CustomEvent("scalper-position-update", { detail: { position: trade, realizedPnL } }));
  }, [trade, realizedPnL]);

  // SVG Coordinates calculation for high-frequency tick chart
  const minTick = Math.min(...ticks);
  const maxTick = Math.max(...ticks);
  const spread = Math.max(1, maxTick - minTick);
  
  const getSvgY = (val: number) => {
    return 180 - ((val - minTick) / spread) * 140;
  };

  const getSvgX = (idx: number) => {
    return (idx / 39) * 440 + 20;
  };

  const polylinePoints = ticks.map((val, idx) => `${getSvgX(idx)},${getSvgY(val)}`).join(" ");

  return (
    <div className="flex flex-col gap-2 h-full font-sans select-none">
      {/* 1. Tick Chart Panel */}
      <div className="flex-1 bg-slate-950/60 border border-white/5 rounded-lg p-2.5 flex flex-col justify-between overflow-hidden relative">
        <div className="flex justify-between items-center text-[10px] uppercase font-bold text-slate-400 border-b border-white/5 pb-1">
          <div className="flex items-center gap-1.5">
            <Radio className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
            <span className="text-cyan-400">TICK CHART (40 Ticks)</span>
          </div>
          <span className="font-mono">LTP: ₹{ltp.toFixed(2)}</span>
        </div>

        {/* SVG Drawing for Tick Lines */}
        <div className="flex-1 min-h-[140px] relative mt-2">
          {ticks.length > 1 && (
            <svg viewBox="0 0 480 200" className="w-full h-full text-cyan-400 overflow-visible">
              {/* Tick price line */}
              <polyline
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                points={polylinePoints}
                className="filter drop-shadow-[0_0_4px_rgba(6,182,212,0.3)]"
              />

              {/* Position helper lines */}
              {trade.side !== "FLAT" && (
                <>
                  {/* Entry Line (Green) */}
                  {trade.avgEntry > 0 && (
                    <line
                      x1="0"
                      y1={getSvgY(trade.avgEntry)}
                      x2="480"
                      y2={getSvgY(trade.avgEntry)}
                      stroke="#10b981"
                      strokeDasharray="3,3"
                      strokeWidth="1.2"
                    />
                  )}
                  {/* Target Line (Blue) */}
                  {trade.targetPrice > 0 && (
                    <line
                      x1="0"
                      y1={getSvgY(trade.targetPrice)}
                      x2="480"
                      y2={getSvgY(trade.targetPrice)}
                      stroke="#06b6d4"
                      strokeDasharray="4,4"
                      strokeWidth="1.2"
                    />
                  )}
                  {/* Stop Price Line (Red) */}
                  {trade.stopPrice > 0 && (
                    <line
                      x1="0"
                      y1={getSvgY(trade.stopPrice)}
                      x2="480"
                      y2={getSvgY(trade.stopPrice)}
                      stroke="#ef4444"
                      strokeDasharray="4,4"
                      strokeWidth="1.2"
                    />
                  )}
                </>
              )}
            </svg>
          )}

          {/* Value tags on the right */}
          {trade.side !== "FLAT" && (
            <div className="absolute right-1 top-0 bottom-0 flex flex-col justify-between font-mono text-[9px] pointer-events-none">
              {trade.targetPrice > 0 && <span className="text-cyan-400 bg-cyan-950/80 px-1 border border-cyan-800 rounded">TGT: {trade.targetPrice.toFixed(1)}</span>}
              {trade.avgEntry > 0 && <span className="text-emerald-400 bg-emerald-950/80 px-1 border border-emerald-800 rounded">AVG: {trade.avgEntry.toFixed(1)}</span>}
              {trade.stopPrice > 0 && <span className="text-rose-400 bg-rose-950/80 px-1 border border-rose-800 rounded">SL: {trade.stopPrice.toFixed(1)}</span>}
            </div>
          )}
        </div>
      </div>

      {/* 2. Order Pad & Hotkeys Panel Side-By-Side */}
      <div className="grid grid-cols-12 gap-2 h-44 shrink-0">
        
        {/* Order Pad Execution Panel (Center Execution) */}
        <div className="col-span-8 bg-slate-950/60 border border-white/5 rounded-lg p-2.5 flex flex-col justify-between">
          <div className="flex justify-between items-center text-[9px] uppercase font-bold text-slate-500 tracking-wider">
            <span>SCALPING ORDER PAD</span>
            <span className="text-cyan-400 font-bold">Qty: {activeLots} Lot(s)</span>
          </div>

          {/* Lot Toggles */}
          <div className="grid grid-cols-4 gap-1">
            {[1, 2, 5, 10].map((lots) => (
              <button
                key={lots}
                onClick={() => setActiveLots(lots)}
                className={`py-1 rounded font-bold text-xs transition-all cursor-pointer text-center ${
                  activeLots === lots
                    ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30"
                    : "bg-slate-900 border border-white/5 text-slate-400 hover:text-slate-200"
                }`}
              >
                {lots} L
              </button>
            ))}
          </div>

          {/* Execution Targets */}
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => handleMarketOrder("BUY")}
              className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold py-2 rounded text-xs uppercase cursor-pointer text-center shadow-lg shadow-emerald-500/10"
            >
              BUY MKT
            </button>
            <button
              onClick={() => handleMarketOrder("SELL")}
              className="bg-rose-500 hover:bg-rose-400 text-slate-950 font-bold py-2 rounded text-xs uppercase cursor-pointer text-center shadow-lg shadow-rose-500/10"
            >
              SELL MKT
            </button>
          </div>

          {/* Quick operations */}
          <div className="grid grid-cols-3 gap-1.5 text-[9px] font-bold">
            <button 
              onClick={handleReverse}
              disabled={trade.side === "FLAT"}
              className="bg-slate-900 border border-white/5 hover:border-white/10 text-amber-400 py-1.5 rounded uppercase transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer text-center"
            >
              REVERSE
            </button>
            <button 
              onClick={handleFlatten}
              disabled={trade.side === "FLAT"}
              className="bg-slate-900 border border-white/5 hover:border-white/10 text-slate-300 py-1.5 rounded uppercase transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer text-center"
            >
              FLATTEN
            </button>
            <button 
              onClick={handleCancel}
              className="bg-slate-900 border border-white/5 hover:border-white/10 text-rose-400 py-1.5 rounded uppercase transition-all cursor-pointer text-center"
            >
              CANCEL
            </button>
          </div>
        </div>

        {/* Hotkey Panel (Display status only) */}
        <div className="col-span-4 bg-slate-950/60 border border-white/5 rounded-lg p-2.5 flex flex-col justify-between font-mono text-[9px]">
          <span className="text-[9px] uppercase font-bold text-slate-500 tracking-wider font-sans">HOTKEYS STATUS</span>
          
          <div className="flex flex-col gap-1.5 text-slate-300 select-none">
            <div className="flex justify-between items-center">
              <span>Shift+B (Buy Mkt)</span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            </div>
            <div className="flex justify-between items-center">
              <span>Shift+S (Sell Mkt)</span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            </div>
            <div className="flex justify-between items-center">
              <span>Space (Flatten)</span>
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            </div>
            <div className="flex justify-between items-center">
              <span>Esc (Cancel All)</span>
              <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
            </div>
          </div>

          <div className="text-[8px] text-slate-500 uppercase tracking-widest text-center mt-1 font-sans">
            KEYBOARD BINDINGS ACTIVE
          </div>
        </div>
      </div>
    </div>
  );
};

// ==========================================
// 2. RIGHT PANEL: LEVEL 2 DOM & PANIC EMERGENCY
// ==========================================
export const ScalperRight: React.FC = () => {
  const [domLtp, setDomLtp] = useState<number>(22212.50);
  const [bidVolumeSum, setBidVolumeSum] = useState<number>(0);
  const [askVolumeSum, setAskVolumeSum] = useState<number>(0);
  const [domRows, setDomRows] = useState<any[]>([]);

  // Update DOM when ticks update
  useEffect(() => {
    const handleTickEvent = (e: Event) => {
      const currentPrice = (e as CustomEvent).detail.ltp;
      setDomLtp(currentPrice);
      
      // Re-generate Level 2 book spreads
      const spreadLevels = [
        { price: currentPrice + 1.00, ask: 42, bid: null },
        { price: currentPrice + 0.75, ask: 28, bid: null },
        { price: currentPrice + 0.50, ask: 33, bid: null },
        { price: currentPrice + 0.25, ask: 19, bid: null },
        { price: currentPrice, ask: null, bid: null }, // Match mid
        { price: currentPrice - 0.25, ask: null, bid: 15 },
        { price: currentPrice - 0.50, ask: null, bid: 32 },
        { price: currentPrice - 0.75, ask: null, bid: 48 },
        { price: currentPrice - 1.00, ask: null, bid: 25 },
      ];
      setDomRows(spreadLevels);

      // Sum volumes
      const askSum = spreadLevels.reduce((acc, curr) => acc + (curr.ask || 0), 0);
      const bidSum = spreadLevels.reduce((acc, curr) => acc + (curr.bid || 0), 0);
      setAskVolumeSum(askSum);
      setBidVolumeSum(bidSum);
    };

    window.addEventListener("scalper-tick", handleTickEvent);
    
    // Initial values
    handleTickEvent(new CustomEvent("scalper-tick", { detail: { ltp: 22212.50 } }));

    return () => window.removeEventListener("scalper-tick", handleTickEvent);
  }, []);

  // Panic Exit Trigger
  const triggerPanicExit = () => {
    window.dispatchEvent(new CustomEvent("scalper-close-position"));
  };

  return (
    <div className="flex flex-col gap-3 h-full font-sans text-xs select-none">
      {/* Level 2 DOM Ladder */}
      <div className="flex-1 bg-slate-950/60 border border-white/5 rounded-lg p-2.5 flex flex-col justify-between min-h-0">
        <div className="flex justify-between items-center text-[10px] uppercase font-bold text-slate-400 border-b border-white/5 pb-1 select-none">
          <span>LEVEL 2 LIQUIDITY LADDER</span>
          <span className="text-emerald-400 font-mono text-[9px]">L2</span>
        </div>

        {/* DOM Rows */}
        <div className="flex-1 overflow-y-auto mt-2 font-mono tabular-nums text-[10px] flex flex-col gap-0.5 pr-1 scrollbar-thin scrollbar-thumb-white/5">
          <div className="grid grid-cols-4 py-1 text-[8px] font-bold text-slate-500 uppercase tracking-widest text-center border-b border-white/[0.02]">
            <span>Bid Qty</span>
            <span className="col-span-2">Price</span>
            <span>Ask Qty</span>
          </div>

          {domRows.map((row, idx) => {
            const isMid = row.price === domLtp;
            const maxVolume = 60; // Spread normalization limit
            const bidPercentage = row.bid ? (row.bid / maxVolume) * 100 : 0;
            const askPercentage = row.ask ? (row.ask / maxVolume) * 100 : 0;

            return (
              <div 
                key={idx} 
                className={`grid grid-cols-4 py-0.5 items-center text-center relative rounded ${
                  isMid ? "bg-cyan-500/10 font-bold border border-cyan-500/20" : ""
                }`}
              >
                {/* Bid Visual Liquidity Bar */}
                {row.bid && (
                  <div 
                    style={{ width: `${bidPercentage}%` }} 
                    className="absolute left-0 top-0 bottom-0 bg-emerald-500/10 rounded-r border-r border-emerald-500/20 pointer-events-none"
                  />
                )}
                {/* Ask Visual Liquidity Bar */}
                {row.ask && (
                  <div 
                    style={{ width: `${askPercentage}%` }} 
                    className="absolute right-0 top-0 bottom-0 bg-rose-500/10 rounded-l border-l border-rose-500/20 pointer-events-none"
                  />
                )}

                {/* Bid Volume */}
                <span className="text-emerald-400 text-left pl-2 z-10">{row.bid || ""}</span>
                
                {/* Price columns */}
                <span className={`col-span-2 text-center font-bold z-10 ${
                  row.bid ? "text-emerald-500/80" : row.ask ? "text-rose-500/80" : "text-cyan-400"
                }`}>
                  ₹{row.price.toFixed(2)}
                </span>
                
                {/* Ask Volume */}
                <span className="text-rose-400 text-right pr-2 z-10">{row.ask || ""}</span>
              </div>
            );
          })}
        </div>

        {/* DOM Liquidity Spread Summary */}
        <div className="border-t border-white/5 pt-2 mt-2 flex justify-between items-center text-[9px] text-slate-500 select-none">
          <div className="flex gap-1.5 items-center">
            <span>BIDS:</span>
            <span className="font-bold text-emerald-400">{bidVolumeSum}</span>
          </div>
          <div className="flex gap-1.5 items-center">
            <span>ASKS:</span>
            <span className="font-bold text-rose-400">{askVolumeSum}</span>
          </div>
        </div>
      </div>

      {/* Emergency Panic Exit Panel */}
      <div className="bg-red-950/20 border border-red-500/40 p-2.5 rounded-lg flex flex-col gap-1.5 shrink-0 select-none">
        <button 
          onClick={triggerPanicExit}
          className="w-full bg-red-600 hover:bg-red-500 active:bg-red-700 text-white font-bold py-2.5 rounded text-[11px] uppercase tracking-widest transition-all shadow-lg shadow-red-600/30 border border-red-500 cursor-pointer text-center"
        >
          🚨 PANIC EXIT / FLATTEN ALL
        </button>
        <span className="text-[8px] text-red-400/60 text-center uppercase tracking-wider font-mono">
          Immediate square-off and active order purge
        </span>
      </div>
    </div>
  );
};

// ==========================================
// 3. BOTTOM PANEL: POSITION MONITOR
// ==========================================
export const ScalperBottom: React.FC = () => {
  const [pos, setPos] = useState<ActiveScalpingPosition | null>(null);
  const [realized, setRealized] = useState<number>(0);

  // Sync positions from chart updates
  useEffect(() => {
    const handlePosUpdate = (e: Event) => {
      const details = (e as CustomEvent).detail;
      setPos(details.position);
      setRealized(details.realizedPnL);
    };

    window.addEventListener("scalper-position-update", handlePosUpdate);
    return () => window.removeEventListener("scalper-position-update", handlePosUpdate);
  }, []);

  const handleClosePos = () => {
    window.dispatchEvent(new CustomEvent("scalper-close-position"));
  };

  const unrealizedPnL = pos && pos.side !== "FLAT"
    ? pos.side === "LONG"
      ? (pos.ltp - pos.avgEntry) * pos.qty
      : (pos.avgEntry - pos.ltp) * pos.qty
    : 0;

  const risk = pos && pos.side !== "FLAT" && pos.stopPrice > 0
    ? Math.abs(pos.avgEntry - pos.stopPrice) * pos.qty
    : 0;

  const reward = pos && pos.side !== "FLAT" && pos.targetPrice > 0
    ? Math.abs(pos.targetPrice - pos.avgEntry) * pos.qty
    : 0;

  const rrRatio = risk > 0 ? (reward / risk).toFixed(1) : "0.0";

  return (
    <div className="flex flex-col h-full overflow-hidden text-xs font-sans select-none">
      {/* Position Header Banner */}
      <div className="flex items-center justify-between border-b border-white/5 bg-slate-950/20 px-3 py-1 shrink-0 select-none">
        <span className="font-bold text-[9px] text-slate-500 uppercase tracking-widest">Scalper Positions Auditor</span>
        <div className="flex gap-4 font-mono tabular-nums text-[9px] items-center">
          <div className="flex gap-1.5">
            <span className="text-slate-500">REALIZED:</span>
            <span className={`font-bold ${realized >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              ₹{realized.toFixed(2)}
            </span>
          </div>
          <div className="flex gap-1.5">
            <span className="text-slate-500">UNREALIZED:</span>
            <span className={`font-bold ${unrealizedPnL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              ₹{unrealizedPnL.toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* Detail table */}
      <div className="flex-1 overflow-x-auto p-2 scrollbar-thin scrollbar-thumb-white/5 scrollbar-track-transparent">
        <table className="w-full text-left font-mono tabular-nums text-[10px]">
          <thead>
            <tr className="border-b border-white/10 text-slate-500 uppercase select-none text-[8px] tracking-wider text-center">
              <th className="py-1 pl-2 text-left">Instrument</th>
              <th className="py-1">Side</th>
              <th className="py-1">Qty</th>
              <th className="py-1 text-right">Avg Entry</th>
              <th className="py-1 text-right">LTP</th>
              <th className="py-1 text-right">Risk (SL)</th>
              <th className="py-1 text-right">Reward (Tgt)</th>
              <th className="py-1 text-center">R:R Ratio</th>
              <th className="py-1 text-right">Unrealized PnL</th>
              <th className="py-1 text-right pr-2">Squareoff</th>
            </tr>
          </thead>
          <tbody className="text-slate-300 text-center">
            {pos && pos.side !== "FLAT" ? (
              <tr className="hover:bg-white/[0.01]">
                <td className="py-2 pl-2 text-left font-sans font-bold text-slate-200">{pos.symbol}</td>
                <td className="py-2">
                  <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold font-sans ${
                    pos.side === "LONG" ? "bg-emerald-950/40 text-emerald-400" : "bg-rose-950/40 text-rose-400"
                  }`}>
                    {pos.side}
                  </span>
                </td>
                <td className="py-2 font-bold">{pos.qty}</td>
                <td className="py-2 text-right">₹{pos.avgEntry.toFixed(2)}</td>
                <td className="py-2 text-right">₹{pos.ltp.toFixed(2)}</td>
                <td className="py-2 text-right text-rose-400">₹{risk.toFixed(2)}</td>
                <td className="py-2 text-right text-cyan-400">₹{reward.toFixed(2)}</td>
                <td className="py-2 text-center text-slate-400 font-bold">{rrRatio}</td>
                <td className={`py-2 text-right font-bold ${unrealizedPnL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                  {unrealizedPnL >= 0 ? "+" : ""}₹{unrealizedPnL.toFixed(2)}
                </td>
                <td className="py-2 text-right pr-2">
                  <button 
                    onClick={handleClosePos}
                    className="bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded px-2 py-0.5 font-bold font-sans text-[8px] cursor-pointer"
                  >
                    CLOSE
                  </button>
                </td>
              </tr>
            ) : (
              <tr>
                <td colSpan={10} className="py-6 text-center text-slate-500 text-[10px] font-sans">
                  No active scalping positions. Click BUY MKT / SELL MKT to execute.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
