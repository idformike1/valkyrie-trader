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

// Valkyrie Design System V3 imports
import { DataTable, ColumnDef } from "@/design-system/DataTable";
import { StatusBadge } from "@/design-system/StatusBadge";
import { EmptyState } from "@/design-system/EmptyState";

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
      <div className="flex-1 p-2 flex flex-col justify-between overflow-hidden relative">
        <div className="flex justify-between items-center vdl-body font-semibold text-slate-400 border-b pb-1">
          <div className="flex items-center gap-1.5">
            <Radio className="w-3.5 h-3.5 text-[var(--gold-accent)] animate-pulse" />
            <span className="text-[var(--gold-accent)]">Tick chart (40 ticks)</span>
          </div>
          <span className="font-mono">Ltp: ₹{ltp.toFixed(2)}</span>
        </div>

        {/* SVG Drawing for Tick Lines */}
        <div className="flex-1 min-h-[140px] relative mt-2">
          {ticks.length > 1 && (
            <svg viewBox="0 0 480 200" className="w-full h-full text-[var(--gold-accent)] overflow-visible">
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
            <div className="absolute right-1 top-0 bottom-0 flex flex-col justify-between font-mono vdl-body pointer-events-none">
              {trade.targetPrice > 0 && <span className="text-[var(--gold-accent)] bg-[var(--bg-card)] px-1 border border-[var(--border-subtle)] rounded-[var(--radius-sm)]">TGT: {trade.targetPrice.toFixed(1)}</span>}
              {trade.avgEntry > 0 && <span className="text-emerald-400 bg-emerald-950/80 px-1 border border-emerald-800 rounded">AVG: {trade.avgEntry.toFixed(1)}</span>}
              {trade.stopPrice > 0 && <span className="text-rose-400 bg-rose-950/80 px-1 border border-rose-800 rounded">SL: {trade.stopPrice.toFixed(1)}</span>}
            </div>
          )}
        </div>
      </div>

      {/* 2. Order Pad & Hotkeys Panel Side-By-Side */}
      <div className="grid grid-cols-12 gap-2 h-44 shrink-0">
        
        {/* Order Pad Execution Panel (Center Execution) */}
        <div className="col-span-8 p-2 flex flex-col justify-between">
          <div className="flex justify-between items-center vdl-body font-semibold text-slate-500">
            <span>Scalping order pad</span>
            <span className="text-[var(--gold-accent)] font-semibold">Qty: {activeLots} lot(s)</span>
          </div>

          {/* Lot Toggles */}
          <div className="tab-container grid grid-cols-4 select-none">
            {[1, 2, 5, 10].map((lots) => (
              <button
                key={lots}
                onClick={() => setActiveLots(lots)}
                className={`tab-item ${activeLots === lots ? "active" : ""}`}
              >
                {lots} L
              </button>
            ))}
          </div>

          {/* Execution Targets */}
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => handleMarketOrder("BUY")}
              className="btn-buy w-full cursor-pointer text-center"
            >
              Buy Mkt
            </button>
            <button
              onClick={() => handleMarketOrder("SELL")}
              className="btn-sell w-full cursor-pointer text-center"
            >
              Sell Mkt
            </button>
          </div>

          {/* Quick operations */}
          <div className="grid grid-cols-3 gap-1.5">
            <button 
              onClick={handleReverse}
              disabled={trade.side === "FLAT"}
              className="btn-secondary cursor-pointer text-center"
            >
              Reverse
            </button>
            <button 
              onClick={handleFlatten}
              disabled={trade.side === "FLAT"}
              className="btn-secondary cursor-pointer text-center"
            >
              Flatten
            </button>
            <button 
              onClick={handleCancel}
              className="btn-danger cursor-pointer text-center"
            >
              Cancel
            </button>
          </div>
        </div>

        {/* Hotkey Panel (Display status only) */}
        <div className="col-span-4 border-l p-2 flex flex-col justify-between font-mono vdl-body">
          <span className="vdl-body font-semibold text-slate-500 font-sans">Hotkeys status</span>
          
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

          <div className="vdl-body text-slate-500 text-center mt-1 font-sans">
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
    <div className="flex flex-col gap-3 h-full font-sans vdl-body select-none">
      {/* Level 2 DOM Ladder */}
      <div className="flex-1 p-2 flex flex-col justify-between min-h-0">
        <div className="flex justify-between items-center vdl-body font-semibold text-slate-400 border-b pb-1 select-none">
          <span>Level 2 liquidity ladder</span>
          <span className="text-emerald-400 font-mono vdl-body">L2</span>
        </div>

        {/* Liquidity Summary HUD */}
        <div className="grid grid-cols-2 gap-2 bg-card/40 p-2 rounded font-mono vdl-body select-none mt-2 shrink-0">
          <div className="flex flex-col">
            <div className="flex justify-between items-center text-slate-500">
              <span>Bid Total</span>
              <span className="font-semibold text-emerald-400 tabular-nums">{(bidVolumeSum * 100).toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center text-slate-500 mt-1">
              <span>Ask Total</span>
              <span className="font-semibold text-rose-400 tabular-nums">{(askVolumeSum * 100).toLocaleString()}</span>
            </div>
          </div>
          <div className="flex flex-col border-l pl-2">
            <div className="flex justify-between items-center text-slate-500">
              <span>Delta</span>
              <span className={`font-semibold tabular-nums${
                (bidVolumeSum - askVolumeSum) >= 0 ? "text-emerald-400" : "text-rose-500"
              }`}>
                {(bidVolumeSum - askVolumeSum) >= 0 ? "+" : ""}{((bidVolumeSum - askVolumeSum) * 100).toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between items-center text-slate-500 mt-1">
              <span>Imbalance</span>
              <span className={`font-semibold tabular-nums${
                (bidVolumeSum - askVolumeSum) >= 0 ? "text-emerald-400" : "text-rose-500"
              }`}>
                {(bidVolumeSum - askVolumeSum) >= 0 ? "+" : ""}{(((bidVolumeSum - askVolumeSum) / (bidVolumeSum + askVolumeSum || 1)) * 100).toFixed(1)}%
              </span>
            </div>
          </div>
        </div>

        {/* DOM Rows */}
        <div className="flex-1 overflow-y-auto mt-2 font-mono tabular-nums section flex flex-col gap-0.5 pr-1 scrollbar-thin scrollbar-thumb-white/5">
          <div className="grid grid-cols-4 py-1 vdl-body font-semibold text-slate-500 text-center border-b/30">
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
                className={`grid grid-cols-4 py-0.5 items-center text-center relative rounded${
                  isMid ? "bg-[var(--gold-accent)]/10 font-bold border border-[var(--gold-accent)]/20" : ""
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
                <span className="text-emerald-400 text-left pl-2 z-10 font-semibold font-mono section">{row.bid || ""}</span>
                
                {/* Price columns */}
                <span className={`col-span-2 text-center font-semibold font-mono section z-10 ${
                  row.bid ? "text-emerald-500" : row.ask ? "text-rose-500" : "text-[var(--gold-accent)]"
                }`}>
                  ₹{row.price.toFixed(2)}
                </span>
                
                {/* Ask Volume */}
                <span className="text-rose-400 text-right pr-2 z-10 font-semibold font-mono section">{row.ask || ""}</span>
              </div>
            );
          })}
        </div>

        {/* DOM Liquidity Spread Summary */}
        <div className="border-t pt-2 mt-2 flex justify-between items-center vdl-body text-slate-500 select-none">
          <div className="flex gap-1.5 items-center">
            <span>Bids:</span>
            <span className="font-semibold text-emerald-400">{bidVolumeSum}</span>
          </div>
          <div className="flex gap-1.5 items-center">
            <span>Asks:</span>
            <span className="font-semibold text-rose-400">{askVolumeSum}</span>
          </div>
        </div>
      </div>

      {/* Emergency Panic Exit Panel */}
      <div className="panel border-red-500/20 bg-red-950/10 p-3 flex flex-col gap-2 shrink-0 select-none">
        <button 
          onClick={triggerPanicExit}
          className="btn-destructive w-full cursor-pointer text-center"
        >
          🚨 Panic Exit / Flatten All
        </button>
        <span className="vdl-body text-red-400/60 text-center font-mono">
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

  const scalperColumns: ColumnDef<any>[] = [
    {
      header: "Instrument",
      accessorKey: "symbol",
      className: "text-left pl-2 font-sans font-semibold text-slate-200",
    },
    {
      header: "Side",
      accessorKey: (row) => {
        // Map side to an approved system state for standard coloring
        const sideState = row.side === "LONG" ? "Running" : "Failed";
        return <StatusBadge state={sideState} className="!font-sans font-semibold" />;
      },
      className: "text-center",
    },
    {
      header: "Qty",
      accessorKey: "qty",
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Avg Entry",
      accessorKey: (row) => `₹${row.avgEntry.toFixed(2)}`,
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Ltp",
      accessorKey: (row) => `₹${row.ltp.toFixed(2)}`,
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Risk (SL)",
      accessorKey: () => `₹${risk.toFixed(2)}`,
      className: "text-right text-rose-400 font-mono tabular-nums",
    },
    {
      header: "Reward (Tgt)",
      accessorKey: () => `₹${reward.toFixed(2)}`,
      className: "text-right text-[var(--gold-accent)] font-mono tabular-nums",
    },
    {
      header: "R:R Ratio",
      accessorKey: () => rrRatio,
      className: "text-center text-slate-400 font-semibold font-mono",
    },
    {
      header: "Unrealized PnL",
      accessorKey: () => (
        <span className={`font-semibold ${unrealizedPnL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
          {unrealizedPnL >= 0 ? "+" : ""}₹{unrealizedPnL.toFixed(2)}
        </span>
      ),
      isNumeric: true,
      isMono: true,
    },
    {
      header: "Squareoff",
      accessorKey: () => (
        <button
          onClick={handleClosePos}
          className="btn-danger btn-xs cursor-pointer"
        >
          Close
        </button>
      ),
      className: "text-right pr-2",
    },
  ];

  const tableData = pos && pos.side !== "FLAT" ? [pos] : [];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Position Header Banner */}
      <div className="flex items-center justify-between border-b bg-deep/50 px-3 py-1 shrink-0 select-none">
        <span className="font-semibold vdl-body text-slate-500">Scalper Positions Auditor</span>
        <div className="flex gap-4 font-mono tabular-nums vdl-body items-center">
          <div className="flex gap-1.5">
            <span className="text-slate-500">REALIZED:</span>
            <span className={`font-semibold ${realized >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              ₹{realized.toFixed(2)}
            </span>
          </div>
          <div className="flex gap-1.5">
            <span className="text-slate-500">UNREALIZED:</span>
            <span className={`font-semibold ${unrealizedPnL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              ₹{unrealizedPnL.toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        <DataTable
          columns={scalperColumns}
          data={tableData}
          emptyState={
            <EmptyState
              icon={Zap}
              title="No Active Scalping Positions"
              description="Click BUY MKT / SELL MKT to execute an entry."
            />
          }
        />
      </div>
    </div>
  );
};
