import React from "react";
import { 
  Play, Activity, Terminal, Shield, Cpu, RefreshCw, BarChart2,
  TrendingUp, Layers, Server, Settings, Zap, ArrowUpRight, ArrowDownRight,
  Sliders, Search, Plus, Trash2, SlidersHorizontal, Lock, CheckCircle2, AlertTriangle
} from "lucide-react";

// Helper components for professional aesthetics
const GlowingCard: React.FC<{ title: string; children: React.ReactNode; className?: string }> = ({ title, children, className = "" }) => (
  <div className={`p-2 flex flex-col h-full ${className}`}>
    <h3 className="text-[12px] font-bold text-slate-200 border-b border-white/5 pb-1.5 mb-2 flex items-center justify-between">
      <span>{title}</span>
    </h3>
    <div className="flex-1 overflow-y-auto">{children}</div>
  </div>
);

// MOCK TRADING WORKSPACE PANELS
export const TradingLeft: React.FC = () => (
  <GlowingCard title="Instruments">
    <div className="flex flex-col gap-2 h-full">
      <div className="relative">
        <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" />
        <input 
          type="text" 
          placeholder="Search contracts..." 
          className="w-full bg-slate-900/60 border border-white/5 rounded pl-8 pr-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-cyan-500"
        />
      </div>
      <div className="flex-1 flex flex-col gap-1 overflow-y-auto mt-2 text-xs">
        {[
          { symbol: "NIFTY 15 MAY 22300 CE", price: "123.40", change: "+12.4%", up: true },
          { symbol: "NIFTY 15 MAY 22300 PE", price: "98.15", change: "-8.2%", up: false },
          { symbol: "BANKNIFTY 15 MAY 46700 CE", price: "487.30", change: "+24.5%", up: true },
          { symbol: "BANKNIFTY 15 MAY 46700 PE", price: "312.00", change: "+4.1%", up: true },
          { symbol: "FINNIFTY 15 MAY 20900 CE", price: "215.30", change: "+15.6%", up: true },
        ].map((item, idx) => (
          <div key={idx} className="flex justify-between items-center p-2 rounded bg-white/2 hover:bg-white/5 cursor-pointer border border-transparent hover:border-white/5 transition-all">
            <span className="font-semibold text-slate-200">{item.symbol}</span>
            <div className="text-right">
              <div className="font-mono text-slate-200">₹{item.price}</div>
              <div className={`text-xs font-semibold ${item.up ? "text-emerald-400" : "text-rose-400"}`}>{item.change}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  </GlowingCard>
);

export const TradingMain: React.FC = () => (
  <GlowingCard title="Trading Panel (Framework Shell)">
    <div className="flex flex-col justify-between h-full min-h-[300px]">
      <div className="flex-1 flex flex-col items-center justify-center border border-dashed border-white/10 rounded-lg p-6 bg-slate-950/20">
        <Zap className="w-12 h-12 text-cyan-400/20 mb-3 animate-pulse" />
        <h4 className="text-sm font-semibold text-slate-300">Workspace Host Container</h4>
        <p className="text-xs text-slate-500 text-center mt-1 max-w-sm">
          Workspace layouts are fully registered, responsive, and stateful. Switch workspaces, resize, and collapse panels to test persistence.
        </p>
        <div className="mt-4 flex gap-2">
          <span className="text-xs px-2 py-1 rounded bg-cyan-950 text-cyan-400 border border-cyan-800">Layout Preserved</span>
          <span className="text-xs px-2 py-1 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">State Saved</span>
        </div>
      </div>
    </div>
  </GlowingCard>
);

export const TradingRight: React.FC = () => (
  <GlowingCard title="Order Desk">
    <div className="flex flex-col gap-3 text-xs">
      <div className="grid grid-cols-2 gap-2 bg-slate-900/40 p-1 rounded border border-white/5">
        <button className="bg-cyan-500 text-slate-950 font-bold py-1.5 rounded transition-all text-xs shadow-lg shadow-cyan-500/20">BUY</button>
        <button className="bg-slate-900 text-slate-400 hover:bg-slate-800 py-1.5 rounded transition-all text-xs">SELL</button>
      </div>
      <div className="flex flex-col gap-2 mt-2">
        <label className="text-xs text-slate-400 uppercase tracking-wider">Order Type</label>
        <select className="bg-slate-900 border border-white/10 rounded px-2 py-1.5 text-slate-300">
          <option>MARKET</option>
          <option>LIMIT</option>
          <option>SL-LIMIT</option>
        </select>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400 uppercase">Quantity (Lots)</label>
          <input type="number" defaultValue={1} className="bg-slate-900 border border-white/10 rounded px-2 py-1 text-slate-300 text-center" />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400 uppercase">Trigger Price</label>
          <input type="number" defaultValue={120} className="bg-slate-900 border border-white/10 rounded px-2 py-1 text-slate-300 text-center" />
        </div>
      </div>
      <div className="border-t border-white/5 my-2 pt-3 flex flex-col gap-2">
        <button className="w-full bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-bold py-2 rounded text-xs transition-all uppercase tracking-wider">
          Execute Trade
        </button>
      </div>
    </div>
  </GlowingCard>
);

export const TradingBottom: React.FC = () => (
  <div className="grid grid-cols-4 gap-4 h-full min-h-[120px] text-xs">
    {[
      { label: "Account P&L", value: "+₹32,650.00", sub: "Live Account", trend: true },
      { label: "Unrealized Margin", value: "₹12,450.00", sub: "3 open positions", trend: true },
      { label: "Realized Gains", value: "₹20,200.00", sub: "2 closed today", trend: true },
      { label: "Available Funding", value: "₹12,30,400.00", sub: "Margin power: 10x", trend: null }
    ].map((card, idx) => (
      <div key={idx} className="glass-panel p-3 bg-slate-950/20 border border-white/5 rounded-lg flex flex-col justify-between">
        <span className="text-xs uppercase text-slate-400 tracking-wider">{card.label}</span>
        <div className="flex items-end justify-between mt-1">
          <span className={`text-base font-bold ${card.trend === true ? "text-emerald-400" : card.trend === false ? "text-rose-400" : "text-slate-100"}`}>
            {card.value}
          </span>
          <span className="text-xs text-slate-500">{card.sub}</span>
        </div>
      </div>
    ))}
  </div>
);


// MOCK SCALPER PANELS
export const ScalperMain: React.FC = () => (
  <div className="grid grid-cols-3 gap-4 h-full text-xs">
    {/* DOM - Depth of Market Grid */}
    <div className="col-span-2 glass-panel p-3 border border-white/5 rounded-lg bg-slate-950/30 flex flex-col h-full overflow-hidden">
      <div className="flex justify-between items-center border-b border-white/5 pb-2 mb-2">
        <span className="font-bold text-slate-300">LEVEL 2 DOM (Depth of Market)</span>
        <span className="text-xs bg-rose-500/10 text-rose-400 border border-rose-500/20 px-1.5 py-0.5 rounded font-bold uppercase animate-pulse">Live</span>
      </div>
      <div className="flex-1 overflow-y-auto font-mono text-xs flex flex-col gap-0.5 pr-1">
        {[
          { size: 28, bid: null, price: "223.70", ask: 12, sizeAsk: 12 },
          { size: 37, bid: null, price: "223.65", ask: 17, sizeAsk: 17 },
          { size: 29, bid: null, price: "223.60", ask: 22, sizeAsk: 22 },
          { size: 42, bid: null, price: "223.55", ask: 11, sizeAsk: 11 },
          { size: 12, bid: null, price: "223.50", ask: 20, sizeAsk: 20 },
          { size: 56, bid: 15, price: "223.40", ask: null, sizeAsk: null },
          { size: 42, bid: 12, price: "223.35", ask: null, sizeAsk: null },
          { size: 37, bid: 10, price: "223.30", ask: null, sizeAsk: null },
          { size: 29, bid: 9, price: "223.25", ask: null, sizeAsk: null },
          { size: 28, bid: 8, price: "223.20", ask: null, sizeAsk: null },
        ].map((row, idx) => (
          <div key={idx} className="grid grid-cols-5 py-0.5 border-b border-white/[0.02] text-center items-center">
            <span className="text-emerald-400 text-left pl-2">{row.bid || ""}</span>
            <span className="text-emerald-500/60 text-left text-xs">{row.bid ? `${row.size} Lots` : ""}</span>
            <span className={`font-bold ${row.bid ? "text-emerald-400" : "text-rose-400"} bg-slate-900/60 rounded py-0.5`}>₹{row.price}</span>
            <span className="text-rose-500/60 text-right text-xs">{row.ask ? `${row.sizeAsk} Lots` : ""}</span>
            <span className="text-rose-400 text-right pr-2">{row.ask || ""}</span>
          </div>
        ))}
      </div>
    </div>

    {/* Scalping Order Desk */}
    <div className="col-span-1 flex flex-col gap-3 justify-between">
      <div className="glass-panel p-3 border border-white/5 rounded-lg bg-slate-950/20 flex flex-col gap-2.5">
        <span className="font-bold text-xs tracking-wider text-slate-400 uppercase">ORDER PAD</span>
        <div className="grid grid-cols-3 gap-1">
          {[1, 2, 5, 10].map(lots => (
            <button key={lots} className="bg-slate-900 border border-white/10 py-1 hover:border-cyan-400 rounded text-slate-300 font-semibold">{lots} L</button>
          ))}
          <button className="bg-slate-900 border border-white/10 py-1 hover:border-cyan-400 rounded text-slate-300 font-semibold col-span-2">ALL IN</button>
        </div>
        <div className="grid grid-cols-2 gap-2 mt-1">
          <button className="bg-emerald-500 text-slate-950 font-bold py-2 rounded text-xs uppercase shadow-lg shadow-emerald-500/10">BUY MKT</button>
          <button className="bg-rose-500 text-slate-950 font-bold py-2 rounded text-xs uppercase shadow-lg shadow-rose-500/10">SELL MKT</button>
        </div>
        <button className="bg-white/5 border border-white/10 hover:bg-white/10 text-slate-300 font-bold py-1.5 rounded text-xs uppercase">FLATTEN ALL</button>
      </div>

      <div className="glass-panel p-3 border border-red-500/20 rounded-lg bg-red-950/5 flex flex-col">
        <button className="w-full bg-red-600 hover:bg-red-500 text-white font-bold py-2.5 rounded text-xs uppercase tracking-widest shadow-lg shadow-red-600/20">
          PANIC EXIT
        </button>
        <span className="text-xs text-red-400/60 text-center mt-1.5 uppercase tracking-wider">SQUARES OFF ALL POSITIONS & CANCELS ALL ORDERS</span>
      </div>
    </div>
  </div>
);

export const ScalperRight: React.FC = () => (
  <GlowingCard title="Quick execution settings">
    <div className="flex flex-col gap-4 text-xs">
      <div className="bg-slate-950/40 p-3 rounded-lg border border-white/5 flex flex-col gap-2">
        <span className="text-xs uppercase text-slate-400 tracking-wider">Hotkeys status</span>
        <div className="flex items-center justify-between text-slate-300">
          <span>Shift + B (Buy Market)</span>
          <span className="font-semibold text-emerald-400">ACTIVE</span>
        </div>
        <div className="flex items-center justify-between text-slate-300">
          <span>Shift + S (Sell Market)</span>
          <span className="font-semibold text-emerald-400">ACTIVE</span>
        </div>
        <div className="flex items-center justify-between text-slate-300">
          <span>Space (Flatten All)</span>
          <span className="font-semibold text-rose-400">ACTIVE</span>
        </div>
      </div>
      <div className="flex flex-col gap-2 mt-1">
        <label className="text-xs text-slate-400 uppercase">Scalp Target</label>
        <div className="grid grid-cols-3 gap-1">
          <button className="bg-slate-900 border border-white/5 py-1 text-slate-300 rounded font-semibold text-xs">+2 pts</button>
          <button className="bg-slate-900 border border-white/5 py-1 text-slate-300 rounded font-semibold text-xs">+5 pts</button>
          <button className="bg-cyan-950 border border-cyan-800 text-cyan-400 py-1 rounded font-semibold text-xs">+10 pts</button>
        </div>
      </div>
    </div>
  </GlowingCard>
);

export const ScalperBottom: React.FC = () => (
  <div className="flex items-center justify-between h-full bg-slate-950/10 px-4 py-2 border border-white/5 rounded-lg text-xs">
    <div className="flex gap-6 items-center">
      <div>
        <span className="text-xs text-slate-500 uppercase tracking-wider block">CURRENT ACTIVE POSITION</span>
        <span className="font-bold text-slate-200">BANKNIFTY CE (LONG 5 LOTS)</span>
      </div>
      <div>
        <span className="text-xs text-slate-500 uppercase tracking-wider block">ENTRY PRICE</span>
        <span className="font-bold text-slate-200">₹487.30</span>
      </div>
      <div>
        <span className="text-xs text-slate-500 uppercase tracking-wider block">LTP</span>
        <span className="font-bold text-slate-200">₹498.20</span>
      </div>
      <div>
        <span className="text-xs text-slate-500 uppercase tracking-wider block">R:R</span>
        <span className="font-semibold text-cyan-400">1 : 2.5</span>
      </div>
    </div>
    <div>
      <span className="text-xs text-slate-500 uppercase tracking-wider block text-right">UNREALIZED P&L</span>
      <span className="font-bold text-emerald-400 text-lg glow-green">+₹5,450.00 (+2.22%)</span>
    </div>
  </div>
);


// MOCK BACKTEST PANELS
export const BacktestLeft: React.FC = () => (
  <GlowingCard title="Historical strategies">
    <div className="flex flex-col gap-2 text-xs">
      {[
        { name: "EMA Pullback v4", selected: true, status: "Tested" },
        { name: "VWAP Reversal v2", selected: false, status: "Draft" },
        { name: "ORB Breakout v7", selected: false, status: "Tested" },
        { name: "Momentum Burst v3", selected: false, status: "Tested" },
        { name: "Mean Reversion v5", selected: false, status: "Draft" }
      ].map((strat, idx) => (
        <div key={idx} className={`p-2.5 rounded border cursor-pointer transition-all flex items-center justify-between ${
          strat.selected 
            ? "bg-cyan-950/20 border-cyan-500 text-cyan-400 shadow-sm shadow-cyan-500/5" 
            : "bg-slate-900/30 border-white/5 hover:bg-slate-900/60 text-slate-300"
        }`}>
          <span className="font-semibold">{strat.name}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded uppercase font-bold border ${
            strat.status === "Tested" 
              ? "bg-emerald-950/30 text-emerald-400 border-emerald-800" 
              : "bg-amber-950/30 text-amber-400 border-amber-800"
          }`}>{strat.status}</span>
        </div>
      ))}
      <button className="mt-2 w-full py-2 bg-slate-900 border border-white/10 text-slate-300 hover:border-white/20 rounded font-semibold text-xs flex items-center justify-center gap-1.5">
        <Plus className="w-3.5 h-3.5" /> Create New Strategy
      </button>
    </div>
  </GlowingCard>
);

export const BacktestMain: React.FC = () => (
  <GlowingCard title="Backtest Analysis Workspace">
    <div className="flex flex-col justify-between h-full min-h-[300px]">
      <div className="border border-white/5 rounded-lg p-3 bg-slate-950/40 flex-1 flex flex-col justify-between">
        <div className="flex justify-between items-center text-xs text-slate-400 border-b border-white/5 pb-2">
          <span className="font-mono text-cyan-400">STRATEGY PERFORMANCE SIMULATION</span>
          <span>Date Range: 01 Jan 2024 - 31 May 2024</span>
        </div>
        <div className="flex-1 flex items-center justify-center min-h-[160px]">
          {/* Simulated chart line */}
          <div className="w-full max-w-lg h-32 relative flex items-end">
            <svg viewBox="0 0 400 100" className="w-full h-full text-cyan-400 filter drop-shadow-[0_0_8px_rgba(0,240,255,0.2)]">
              <path 
                fill="none" 
                stroke="currentColor" 
                strokeWidth="2.5" 
                d="M 0,80 L 40,75 L 80,60 L 120,68 L 160,45 L 200,50 L 240,30 L 280,38 L 320,15 L 360,25 L 400,2"
              />
              <path 
                fill="url(#backtest-grad)" 
                d="M 0,80 L 40,75 L 80,60 L 120,68 L 160,45 L 200,50 L 240,30 L 280,38 L 320,15 L 360,25 L 400,2 L 400,100 L 0,100 Z"
              />
              <defs>
                <linearGradient id="backtest-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="rgb(6, 182, 212)" stopOpacity="0.15" />
                  <stop offset="100%" stopColor="rgb(6, 182, 212)" stopOpacity="0.0" />
                </linearGradient>
              </defs>
            </svg>
          </div>
        </div>
        <div className="flex gap-4 border-t border-white/5 pt-2 text-xs text-slate-400">
          <div><span className="text-xs block text-slate-500">Benchmark Return</span><span className="font-semibold text-slate-300">+12.4%</span></div>
          <div><span className="text-xs block text-slate-500">Alpha Generated</span><span className="font-semibold text-emerald-400">+6.3%</span></div>
          <div><span className="text-xs block text-slate-500">Sharpe Ratio</span><span className="font-semibold text-slate-300">1.87</span></div>
        </div>
      </div>
    </div>
  </GlowingCard>
);

export const BacktestRight: React.FC = () => (
  <GlowingCard title="Strategy parameters">
    <div className="flex flex-col gap-3 text-xs">
      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-slate-400">EMA Fast Period</label>
        <input type="number" defaultValue={9} className="bg-slate-900 border border-white/10 rounded px-2.5 py-1 text-slate-200" />
      </div>
      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-slate-400">EMA Slow Period</label>
        <input type="number" defaultValue={21} className="bg-slate-900 border border-white/10 rounded px-2.5 py-1 text-slate-200" />
      </div>
      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-slate-400">Pullback threshold (%)</label>
        <input type="number" defaultValue={0.5} className="bg-slate-900 border border-white/10 rounded px-2.5 py-1 text-slate-200" />
      </div>
      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-slate-400">ATR Period</label>
        <input type="number" defaultValue={14} className="bg-slate-900 border border-white/10 rounded px-2.5 py-1 text-slate-200" />
      </div>
      <button className="w-full mt-3 py-2 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold rounded flex items-center justify-center gap-1.5 uppercase text-xs tracking-wider shadow-lg shadow-cyan-500/10">
        <Play className="w-3.5 h-3.5 fill-slate-950" /> Run Backtest
      </button>
    </div>
  </GlowingCard>
);

export const BacktestBottom: React.FC = () => (
  <div className="grid grid-cols-5 gap-4 h-full min-h-[120px] text-xs">
    {[
      { label: "Total Return", value: "+18.74%", sub: "Over 5 Months", trend: true },
      { label: "CAGR", value: "24.31%", sub: "Annualized Rate", trend: true },
      { label: "Win Rate", value: "62.29%", sub: "156 Total Trades", trend: true },
      { label: "Profit Factor", value: "1.87", sub: "Ratio Gross Profit/Loss", trend: null },
      { label: "Max Drawdown", value: "-8.32%", sub: "Peak to Trough", trend: false }
    ].map((card, idx) => (
      <div key={idx} className="glass-panel p-3 bg-slate-950/20 border border-white/5 rounded-lg flex flex-col justify-between">
        <span className="text-xs uppercase text-slate-400 tracking-wider">{card.label}</span>
        <div className="flex items-end justify-between mt-1">
          <span className={`text-base font-bold ${card.trend === true ? "text-emerald-400" : card.trend === false ? "text-rose-400" : "text-slate-100"}`}>
            {card.value}
          </span>
          <span className="text-xs text-slate-500">{card.sub}</span>
        </div>
      </div>
    ))}
  </div>
);


// MOCK PAPER TRADING PANELS
export const PaperLeft: React.FC = () => (
  <GlowingCard title="Deploy configuration">
    <div className="flex flex-col gap-3 text-xs">
      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-slate-400 uppercase">Target Strategy</label>
        <select className="bg-slate-900 border border-white/10 rounded px-2 py-1.5 text-slate-300">
          <option>EMA Pullback v4</option>
          <option>VWAP Reversal v2</option>
        </select>
      </div>
      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-slate-400 uppercase">Underlying Index</label>
        <select className="bg-slate-900 border border-white/10 rounded px-2 py-1.5 text-slate-300">
          <option>BANKNIFTY</option>
          <option>NIFTY</option>
        </select>
      </div>
      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-slate-400 uppercase">Timeframe</label>
        <select className="bg-slate-900 border border-white/10 rounded px-2 py-1.5 text-slate-300">
          <option>5m</option>
          <option>1m</option>
          <option>15m</option>
        </select>
      </div>
      <button className="w-full mt-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold py-2 rounded text-xs uppercase tracking-wider shadow-lg shadow-emerald-500/10">
        Deploy Strategy
      </button>
    </div>
  </GlowingCard>
);

export const PaperMain: React.FC = () => (
  <GlowingCard title="Virtual Paper Stream">
    <div className="flex-1 flex flex-col justify-between h-full min-h-[300px]">
      <div className="flex justify-between items-center text-xs px-2 mb-2">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          <span className="font-semibold text-slate-300">BANKNIFTY CE Option Price Flow</span>
        </div>
        <span className="font-mono text-cyan-400">PAPER SESSION ID: #8792</span>
      </div>
      <div className="flex-1 border border-white/5 bg-slate-950/20 rounded-lg flex items-center justify-center p-4">
        <div className="w-full h-40 flex items-center justify-center">
          {/* Simulated chart */}
          <div className="w-full max-w-md h-full flex flex-col justify-end">
            <div className="w-full flex items-end justify-between h-3/4 px-4 font-mono text-xs text-slate-500">
              <div className="w-4 bg-emerald-400/20 border-t border-emerald-400 h-10" />
              <div className="w-4 bg-rose-400/20 border-t border-rose-400 h-8" />
              <div className="w-4 bg-emerald-400/20 border-t border-emerald-400 h-16" />
              <div className="w-4 bg-emerald-400/20 border-t border-emerald-400 h-20" />
              <div className="w-4 bg-rose-400/20 border-t border-rose-400 h-12" />
              <div className="w-4 bg-emerald-400/20 border-t border-emerald-400 h-28" />
              <div className="w-4 bg-emerald-400/20 border-t border-emerald-400 h-32" />
            </div>
            <div className="border-t border-white/5 w-full mt-2" />
          </div>
        </div>
      </div>
    </div>
  </GlowingCard>
);

export const PaperRight: React.FC = () => (
  <GlowingCard title="Active strategy bots">
    <div className="flex flex-col gap-2 text-xs">
      {[
        { name: "EMA Pullback v4", symbol: "BANKNIFTY", status: "Running", pnl: "+₹8,430.00", up: true },
        { name: "VWAP Reversal v2", symbol: "NIFTY", status: "Stopped", pnl: "+₹10,000.00", up: true },
      ].map((bot, idx) => (
        <div key={idx} className="bg-slate-900/40 p-2.5 rounded border border-white/5 flex flex-col gap-1.5 hover:border-white/10 transition-all">
          <div className="flex justify-between items-center">
            <span className="font-semibold text-slate-200">{bot.name}</span>
            <span className={`status-badge ${bot.status === "Running" ? "running" : "inactive"}`}>{bot.status}</span>
          </div>
          <div className="flex justify-between text-xs text-slate-400">
            <span>{bot.symbol}</span>
            <span className={bot.up ? "text-emerald-400 font-semibold" : "text-rose-400 font-semibold"}>{bot.pnl}</span>
          </div>
        </div>
      ))}
    </div>
  </GlowingCard>
);

export const PaperBottom: React.FC = () => (
  <div className="grid grid-cols-4 gap-4 h-full min-h-[120px] text-xs">
    {[
      { label: "Paper Mode Balance", value: "₹1,000,000.00", sub: "Virtual Funds", trend: null },
      { label: "Unrealized PnL", value: "+₹24,560.00", sub: "Floating", trend: true },
      { label: "Realized PnL", value: "+₹18,430.00", sub: "Settled Trades", trend: true },
      { label: "Paper Margin Used", value: "₹1,20,400.00", sub: "Free power: 88%", trend: null }
    ].map((card, idx) => (
      <div key={idx} className="glass-panel p-3 bg-slate-950/20 border border-white/5 rounded-lg flex flex-col justify-between">
        <span className="text-xs uppercase text-slate-400 tracking-wider">{card.label}</span>
        <div className="flex items-end justify-between mt-1">
          <span className={`text-base font-bold ${card.trend === true ? "text-emerald-400" : card.trend === false ? "text-rose-400" : "text-slate-100"}`}>
            {card.value}
          </span>
          <span className="text-xs text-slate-500">{card.sub}</span>
        </div>
      </div>
    ))}
  </div>
);


// MOCK DEPLOYMENTS PANELS
export const DeploymentsLeft: React.FC = () => (
  <GlowingCard title="Environments">
    <div className="flex flex-col gap-2 text-xs">
      {[
        { name: "Live Production-A", desc: "Running Live Strategies", active: true },
        { name: "Live Production-B", desc: "Idle - Backup Node", active: false },
        { name: "Paper Testing Sand", desc: "Simulation Sandbox", active: false },
      ].map((env, idx) => (
        <div key={idx} className={`p-2.5 rounded border cursor-pointer transition-all flex flex-col gap-0.5 ${
          env.active 
            ? "bg-cyan-950/20 border-cyan-500 text-cyan-400" 
            : "bg-slate-900/30 border-white/5 hover:bg-slate-900/60 text-slate-300"
        }`}>
          <span className="font-semibold">{env.name}</span>
          <span className="text-xs text-slate-400">{env.desc}</span>
        </div>
      ))}
    </div>
  </GlowingCard>
);

export const DeploymentsMain: React.FC = () => (
  <GlowingCard title="Strategy Deployment Hub">
    <div className="flex flex-col justify-between h-full min-h-[300px]">
      <div className="flex-1 flex flex-col items-center justify-center p-6 border border-dashed border-white/10 bg-slate-950/20 rounded-lg">
        <Server className="w-10 h-10 text-cyan-400/20 mb-2 animate-bounce" />
        <h4 className="text-sm font-semibold text-slate-300">Deployment Registry</h4>
        <p className="text-xs text-slate-500 text-center mt-1 max-w-sm">
          Select strategies, run configurations, and deploy directly into dedicated live containers. View instances health and memory profiles.
        </p>
      </div>
    </div>
  </GlowingCard>
);

export const DeploymentsBottom: React.FC = () => (
  <div className="glass-panel p-3 border border-white/5 rounded-lg bg-slate-950/30 h-full overflow-hidden text-xs">
    <div className="flex items-center gap-2 border-b border-white/5 pb-2 mb-2 text-cyan-400 font-bold uppercase tracking-wider text-xs">
      <Server className="w-3.5 h-3.5" /> Engine deployment host telemetry
    </div>
    <div className="grid grid-cols-3 gap-4">
      <div className="bg-slate-900/30 p-2.5 rounded border border-white/5">
        <span className="text-xs text-slate-500 block">CPU STABILITY</span>
        <span className="font-mono font-semibold text-slate-200">14.2% Load</span>
      </div>
      <div className="bg-slate-900/30 p-2.5 rounded border border-white/5">
        <span className="text-xs text-slate-500 block">RAM ALLOCATION</span>
        <span className="font-mono font-semibold text-slate-200">1.2 GB / 8 GB</span>
      </div>
      <div className="bg-slate-900/30 p-2.5 rounded border border-white/5">
        <span className="text-xs text-slate-500 block">NETWORK LATENCY</span>
        <span className="font-mono font-semibold text-emerald-400">14ms average</span>
      </div>
    </div>
  </div>
);


// MOCK OPERATIONS PANELS
export const OperationsLeft: React.FC = () => (
  <GlowingCard title="Operations Center">
    <div className="flex flex-col gap-2 text-xs">
      {[
        { name: "Runtime Logs", active: true },
        { name: "Trade Ledger", active: false },
        { name: "Strategy Console", active: false },
        { name: "System Health", active: false }
      ].map((opt, idx) => (
        <div key={idx} className={`p-2 px-3 rounded border cursor-pointer transition-all flex items-center gap-2 ${
          opt.active 
            ? "bg-cyan-950/20 border-cyan-500 text-cyan-400 font-semibold" 
            : "bg-slate-900/30 border-white/5 hover:bg-slate-900/60 text-slate-300"
        }`}>
          <div className={`w-1.5 h-1.5 rounded-full ${opt.active ? "bg-cyan-400" : "bg-transparent border border-slate-500"}`} />
          {opt.name}
        </div>
      ))}
    </div>
  </GlowingCard>
);

export const OperationsMain: React.FC = () => (
  <GlowingCard title="Runtime Event Logs Logger">
    <div className="flex flex-col justify-between h-full min-h-[300px]">
      <div className="flex-1 bg-slate-950/60 border border-white/5 p-3 rounded font-mono text-xs text-slate-300 flex flex-col gap-1.5 overflow-y-auto">
        <div><span className="text-slate-500">[09:21:15]</span> <span className="text-cyan-400">[INFO]</span> Buy Order Filled - BANKNIFTY 15 MAY 46700 CE</div>
        <div><span className="text-slate-500">[09:21:14]</span> <span className="text-emerald-400">[TRADE]</span> Sell Order Filled - NIFTY 15 MAY 22300 CE</div>
        <div><span className="text-slate-500">[09:21:10]</span> <span className="text-amber-400">[WARN]</span> WebSocket connection latencies peaked at 180ms</div>
        <div><span className="text-slate-500">[09:21:05]</span> <span className="text-cyan-400">[INFO]</span> Executing standard order routing through Upstox Gateway</div>
        <div><span className="text-slate-500">[09:20:48]</span> <span className="text-emerald-400">[TRADE]</span> Position Closed - BOT-B (VWAP v2) P&L: +₹1,250.00</div>
      </div>
    </div>
  </GlowingCard>
);

export const OperationsRight: React.FC = () => (
  <GlowingCard title="System components health">
    <div className="flex flex-col gap-2.5 text-xs">
      {[
        { name: "WebSocket Gateway", status: "Healthy", color: "text-emerald-400 bg-emerald-950/20 border-emerald-800" },
        { name: "Redis Cache Store", status: "Healthy", color: "text-emerald-400 bg-emerald-950/20 border-emerald-800" },
        { name: "Order Engine Node", status: "Healthy", color: "text-emerald-400 bg-emerald-950/20 border-emerald-800" },
        { name: "Live Database Store", status: "Healthy", color: "text-emerald-400 bg-emerald-950/20 border-emerald-800" },
        { name: "Strategy Daemon Engine", status: "Healthy", color: "text-emerald-400 bg-emerald-950/20 border-emerald-800" }
      ].map((comp, idx) => (
        <div key={idx} className="flex justify-between items-center p-2 rounded bg-slate-900/30 border border-white/5">
          <span className="text-slate-300 font-semibold">{comp.name}</span>
          <span className="status-badge success">{comp.status}</span>
        </div>
      ))}
    </div>
  </GlowingCard>
);

export const OperationsBottom: React.FC = () => (
  <div className="glass-panel p-3 border border-white/5 rounded-lg bg-slate-950/30 h-full overflow-hidden text-xs">
    <span className="text-xs text-slate-500 font-bold uppercase block mb-1">Trace Ledger Transaction Auditor</span>
    <table className="w-full text-left font-mono text-xs">
      <thead>
        <tr className="border-b border-white/10 text-slate-400">
          <th className="py-1">TIMESTAMP</th>
          <th className="py-1">INSTRUMENT</th>
          <th className="py-1">SIDE</th>
          <th className="py-1">QTY</th>
          <th className="py-1">PRICE</th>
          <th className="py-1">P&L</th>
        </tr>
      </thead>
      <tbody className="text-slate-300">
        <tr className="border-b border-white/[0.02]">
          <td className="py-1 text-slate-500">09:21:14</td>
          <td>BANKNIFTY CE</td>
          <td className="text-emerald-400 font-bold">BUY</td>
          <td>5 Lots</td>
          <td>498.20</td>
          <td className="text-emerald-400 font-semibold">+₹1,250.00</td>
        </tr>
        <tr>
          <td className="py-1 text-slate-500">09:20:48</td>
          <td>NIFTY PE</td>
          <td className="text-rose-400 font-bold">SELL</td>
          <td>5 Lots</td>
          <td>132.40</td>
          <td className="text-emerald-400 font-semibold">+₹2,180.00</td>
        </tr>
      </tbody>
    </table>
  </div>
);
