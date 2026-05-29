"use client";

import React, { useEffect, useState, useRef } from "react";
import { 
  Play, Square, AlertOctagon, RefreshCw, Layers, TrendingUp, DollarSign, 
  Activity, Award, Percent, Clipboard, Target, Shield, Zap, XCircle, Trash2
} from "lucide-react";
import { createChart, IChartApi, ISeriesApi, CandlestickData, CandlestickSeries } from "lightweight-charts";

const BACKEND_HTTP = "http://localhost:8081";
const BACKEND_WS = "ws://localhost:8081/ws/telemetry";

const DEFAULT_SYSTEM_STATUS: SystemStatus = {
  state: "DISCONNECTED",
  mode: "PAPER",
  balance: 100000.0,
  initial_balance: 100000.0,
  position: null,
  instrument_key: null,
  trading_symbol: null,
  strike: null,
  expiry: null,
  option_type: null,
  exchange: "NSE",
  index_name: "NIFTY",
  live_protection: false,
  is_real_execution: false,
  lot_size: 1,
  lot_size_multiplier: 75,
  spot_price: 0.0,
  total_pnl: 0.0,
  return_percent: 0.0,
  max_drawdown: 0.0,
  profit_factor: 0.0,
  total_trades: 0,
  win_rate: 0.0,
  chart_interval: "1minute",
  chart_type: "heikin_ashi"
};

interface Trade {
  id: number;
  session_id: number;
  instrument_key: string;
  trading_symbol: string;
  type: string;
  price: number;
  quantity: number;
  sl: number;
  target: number;
  reason: string;
  pnl: number;
  timestamp: string;
  upstox_order_id: string;
}

interface GttOrder {
  id: string;
  trigger_price: number;
  side: string;
  qty: number;
  order_type: string;
  price: number;
  target: number;
  target_type: string;
  stop_loss: number;
  stop_loss_type: string;
  trailing_gap: number;
  direction: string;
  status: string;
  timestamp: string;
}

interface SystemStatus {
  state: string;
  mode: string;
  balance: number;
  initial_balance: number;
  position: any;
  instrument_key: string | null;
  trading_symbol: string | null;
  strike: number | null;
  expiry: string | null;
  option_type: string | null;
  exchange: string;
  index_name: string;
  live_protection: boolean;
  is_real_execution: boolean;
  lot_size: number;
  lot_size_multiplier: number;
  spot_price: number;
  total_pnl: number;
  return_percent: number;
  max_drawdown: number;
  profit_factor: number;
  total_trades: number;
  win_rate: number;
  chart_interval: string;
  chart_type: string;
  nifty_spot?: number;
  
  // Scalper
  scalper_instrument_key?: string | null;
  scalper_trading_symbol?: string | null;
  scalper_lot_multiplier?: number;
  scalper_option_type?: string | null;
  scalper_strike?: string | null;
  scalper_spot_price?: number;
}

export default function ValkyrieCommandRoom() {
  // Connection states
  const [wsConnected, setWsConnected] = useState(false);
  const [telemetry, setTelemetry] = useState<{
    status: SystemStatus;
    trades: Trade[];
    logs: string[];
    candles: any[];
    gtt_orders: GttOrder[];
  } | null>(null);

  // Form selections
  const [indexName, setIndexName] = useState("NIFTY");
  const [exchange, setExchange] = useState("NSE");
  const [expiries, setExpiries] = useState<string[]>([]);
  const [selectedExpiry, setSelectedExpiry] = useState("");
  const [optionType, setOptionType] = useState("CE");
  const [strikes, setStrikes] = useState<number[]>([]);
  const [selectedStrike, setSelectedStrike] = useState("ATM");
  const [spotPrice, setSpotPrice] = useState(0.0);
  const [atmStrike, setAtmStrike] = useState(0.0);

  // Config parameters
  const [mode, setMode] = useState("PAPER");
  const [lotSize, setLotSize] = useState(1);
  const [liveProtection, setLiveProtection] = useState(false);
  const [timeframe, setTimeframe] = useState("1minute");
  const [candleType, setCandleType] = useState("heikin_ashi");
  const [maxCandles, setMaxCandles] = useState(10);
  const [cutoffTime, setCutoffTime] = useState("15:15");
  const [initialBalance, setInitialBalance] = useState(100000);
  const [brokerageFlat, setBrokerageFlat] = useState(20.0);
  const [slippagePct, setSlippagePct] = useState(0.05);

  // Strategy selections
  const [strategy, setStrategy] = useState("heikin_ashi_gar");
  const [fiveEmaPeriod, setFiveEmaPeriod] = useState(5);
  const [fiveEmaRr, setFiveEmaRr] = useState(3.0);

  // Tab configurations
  const [activeOrderTab, setActiveOrderTab] = useState<"standard" | "gtt">("standard");

  // Standard/Scalper order fields
  const [orderQty, setOrderQty] = useState(1);
  const [orderTarget, setOrderTarget] = useState(20.0);
  const [orderTargetType, setOrderTargetType] = useState("points");
  const [orderStopLoss, setOrderStopLoss] = useState(10.0);
  const [orderStopLossType, setOrderStopLossType] = useState("points");
  const [orderTrailingGap, setOrderTrailingGap] = useState(0.0);
  const [isScalperMode, setIsScalperMode] = useState(false);

  // GTT order fields
  const [gttTriggerPrice, setGttTriggerPrice] = useState(100.0);
  const [gttSide, setGttSide] = useState("BUY");
  const [gttOrderType, setGttOrderType] = useState("MARKET");
  const [gttLimitPrice, setGttLimitPrice] = useState(100.0);

  // Chart References
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<any>(null);
  const logTerminalRef = useRef<HTMLDivElement>(null);

  // Load expiries & strikes on index/exchange change
  useEffect(() => {
    fetchMetadata();
  }, [indexName, exchange]);

  // Load strikes when expiry or option type changes
  useEffect(() => {
    if (selectedExpiry) {
      fetchStrikes();
    }
  }, [selectedExpiry, optionType, indexName, exchange]);

  const fetchMetadata = async () => {
    try {
      const res = await fetch(`${BACKEND_HTTP}/api/options/metadata?index=${indexName}&exchange=${exchange}`);
      if (res.ok) {
        const data = await res.json();
        setExpiries(data.expiries || []);
        if (data.expiries && data.expiries.length > 0) {
          setSelectedExpiry(data.expiries[0]);
        }
        setSpotPrice(data.spot_price || 0.0);
        setAtmStrike(data.atm_strike || 0.0);
        setStrikes(data.strikes || []);
      }
    } catch (e) {
      console.error("Failed to load metadata", e);
    }
  };

  const fetchStrikes = async () => {
    try {
      const res = await fetch(`${BACKEND_HTTP}/api/strikes?expiry=${selectedExpiry}&type=${optionType}&index=${indexName}&exchange=${exchange}`);
      if (res.ok) {
        const data = await res.json();
        setStrikes(data || []);
      }
    } catch (e) {
      console.error("Failed to load strikes", e);
    }
  };

  // Connect WebSocket for real-time telemetry updates
  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimer: any;

    const connectWs = () => {
      ws = new WebSocket(BACKEND_WS);

      ws.onopen = () => {
        setWsConnected(true);
        console.log("WebSocket stream connected");
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setTelemetry(data);
        } catch (e) {
          console.error("Error parsing WS telemetry message", e);
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        console.log("WebSocket stream closed. Attempting reconnect...");
        reconnectTimer = setTimeout(connectWs, 3000);
      };

      ws.onerror = (e) => {
        console.error("WebSocket error", e);
        ws.close();
      };
    };

    connectWs();

    return () => {
      if (ws) ws.close();
      clearTimeout(reconnectTimer);
    };
  }, []);

  // Poll HTTP telemetry as a backup if WS drops
  useEffect(() => {
    const interval = setInterval(async () => {
      if (!wsConnected) {
        try {
          const res = await fetch(`${BACKEND_HTTP}/telemetry`);
          if (res.ok) {
            const data = await res.json();
            setTelemetry(data);
          }
        } catch (e) {
          console.warn("Telemetry poll failed", e);
        }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [wsConnected]);

  // Sync state with active telemetry configurations
  useEffect(() => {
    if (telemetry?.status) {
      const st = telemetry.status;
      setMode(st.mode !== "NONE" ? st.mode : "PAPER");
      setLiveProtection(st.live_protection);
      setTimeframe(st.chart_interval);
      setCandleType(st.chart_type);
    }
  }, [telemetry?.status?.mode]);

  // Create lightweight-charts component
  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Initialize chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "#94a3b8",
        fontSize: 12,
        fontFamily: "Outfit, sans-serif"
      },
      grid: {
        vertLines: { color: "rgba(255, 255, 255, 0.03)" },
        horzLines: { color: "rgba(255, 255, 255, 0.03)" }
      },
      crosshair: {
        mode: 1,
        vertLine: { color: "rgba(0, 240, 255, 0.4)", width: 1, style: 3 },
        horzLine: { color: "rgba(0, 240, 255, 0.4)", width: 1, style: 3 }
      },
      timeScale: {
        borderColor: "rgba(255, 255, 255, 0.08)",
        timeVisible: true,
        secondsVisible: false
      },
      rightPriceScale: {
        borderColor: "rgba(255, 255, 255, 0.08)"
      }
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#00f5d4",
      downColor: "#ff5c8a",
      borderUpColor: "#00f5d4",
      borderDownColor: "#ff5c8a",
      wickUpColor: "#00f5d4",
      wickDownColor: "#ff5c8a"
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;

    // Resize handler
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.resize(chartContainerRef.current.clientWidth, 350);
      }
    };
    window.addEventListener("resize", handleResize);
    handleResize();

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.removeSeries(candleSeries);
      chart.remove();
    };
  }, []);

  // Update chart series data on candles change
  useEffect(() => {
    if (candleSeriesRef.current && telemetry?.candles) {
      // Map candles time format
      const formattedCandles: CandlestickData[] = telemetry.candles.map(c => ({
        time: c.time as any,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close
      }));
      candleSeriesRef.current.setData(formattedCandles);
    }
  }, [telemetry?.candles]);

  // Auto-scroll logs
  useEffect(() => {
    if (logTerminalRef.current) {
      logTerminalRef.current.scrollTop = logTerminalRef.current.scrollHeight;
    }
  }, [telemetry?.logs]);

  // Start Engine Action
  const handleStartEngine = async () => {
    try {
      const body = {
        mode,
        lot_size: lotSize,
        live_protection: liveProtection,
        expiry: selectedExpiry,
        option_type: optionType,
        strike: selectedStrike,
        exchange,
        index_name: indexName,
        strategy,
        five_ema_period: fiveEmaPeriod,
        five_ema_rr: fiveEmaRr,
        max_candles: maxCandles,
        cutoff_time: cutoffTime,
        initial_balance: initialBalance,
        brokerage_flat: brokerageFlat,
        slippage_pct: slippagePct,
        live_trading: liveProtection
      };

      const res = await fetch(`${BACKEND_HTTP}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || data.error || "Initialization failed");
      }
    } catch (e) {
      console.error(e);
      alert("Failed to connect to Strategy Daemon");
    }
  };

  // Stop Engine Action
  const handleStopEngine = async () => {
    try {
      const res = await fetch(`${BACKEND_HTTP}/stop`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || data.error || "Halt failed");
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Update Dynamic Target Action
  const handleUpdateTarget = async () => {
    try {
      const body = {
        expiry: selectedExpiry,
        option_type: optionType,
        strike: selectedStrike,
        exchange,
        index_name: indexName
      };
      const res = await fetch(`${BACKEND_HTTP}/api/standard/update_target`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || data.error || "Target update failed");
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Manual Buy Order Execution
  const handleManualBuy = async () => {
    try {
      const body = {
        qty: orderQty,
        target: orderTarget,
        target_type: orderTargetType,
        stop_loss: orderStopLoss,
        stop_loss_type: orderStopLossType,
        trailing_gap: orderTrailingGap,
        is_scalper: isScalperMode
      };
      const res = await fetch(`${BACKEND_HTTP}/manual/buy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || data.error || "Buy Order Rejected");
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Manual Sell Order Execution
  const handleManualSell = async () => {
    try {
      const res = await fetch(`${BACKEND_HTTP}/manual/sell`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || data.error || "Sell Order Failed");
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Panic Exit Action
  const handlePanicExit = async () => {
    try {
      const res = await fetch(`${BACKEND_HTTP}/manual/panic_exit`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        alert("Panic exit failed.");
      }
    } catch (e) {
      console.error(e);
    }
  };

  // GTT Order Creation
  const handleCreateGtt = async () => {
    try {
      const body = {
        trigger_price: gttTriggerPrice,
        qty: orderQty,
        side: gttSide,
        order_type: gttOrderType,
        price: gttLimitPrice,
        target: orderTarget,
        target_type: orderTargetType,
        stop_loss: orderStopLoss,
        stop_loss_type: orderStopLossType,
        trailing_gap: orderTrailingGap
      };
      const res = await fetch(`${BACKEND_HTTP}/manual/gtt/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || data.error || "GTT order rejection");
      } else {
        alert("GTT Order set successfully.");
      }
    } catch (e) {
      console.error(e);
    }
  };

  // GTT Order Cancellation
  const handleCancelGtt = async (gttId: string) => {
    try {
      const res = await fetch(`${BACKEND_HTTP}/manual/gtt/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: gttId })
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || "GTT cancellation failed.");
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Chart config trigger (Interval/Type change)
  const handleChartConfigUpdate = async (newInterval: string, newType: string) => {
    setTimeframe(newInterval);
    setCandleType(newType);
    try {
      await fetch(`${BACKEND_HTTP}/api/chart/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ interval: newInterval, candle_type: newType })
      });
    } catch (e) {
      console.error(e);
    }
  };

  const getLogClass = (log: string) => {
    if (log.includes("[TRADE]")) return "line-trade";
    if (log.includes("[ERROR]")) return "line-error";
    if (log.includes("[ORDER]")) return "line-order";
    if (log.includes("[WARNING]")) return "line-warning";
    return "line-info";
  };

  const sys = telemetry?.status || DEFAULT_SYSTEM_STATUS;
  const trades = telemetry?.trades || [];
  const logs = telemetry?.logs || [];
  const gttOrders = telemetry?.gtt_orders || [];

  return (
    <div className="flex flex-col min-h-screen">
      {/* HEADER SECTION */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-subtle glass-panel rounded-none">
        <div className="flex items-center gap-3">
          <Layers className="text-cyan-neon w-8 h-8" />
          <div>
            <h1 className="text-xl font-bold tracking-wider text-main uppercase">
              Valkyrie <span className="text-cyan-neon">Command Room</span>
            </h1>
            <p className="text-xs text-text-mute">Modular Next.js / Python Algorithmic Trading Suite</p>
          </div>
        </div>

        {/* HUD STREAM STATE */}
        <div className="flex items-center gap-6">
          <div className="flex items-center text-sm">
            <span className={`pulse-indicator ${
              sys.state === "LIVE_MONITORING" ? "pulse-live" : 
              sys.state === "PROCESSING" || sys.state === "RUNNING_BACKTEST" ? "pulse-active" : 
              "pulse-idle"
            }`} />
            <span className="text-xs tracking-widest text-text-mute uppercase mr-1">STATE:</span>
            <span className="font-bold tracking-wider text-cyan-neon uppercase">{sys.state}</span>
          </div>

          <div className="flex items-center gap-2 border-l border-subtle pl-6 text-sm">
            <span className="text-xs tracking-widest text-text-mute uppercase">STREAM:</span>
            <span className={`font-semibold ${wsConnected ? "text-green-neon" : "text-red-neon"}`}>
              {wsConnected ? "CONNECTED" : "DISCONNECTED"}
            </span>
          </div>
        </div>
      </header>

      {/* DASHBOARD CONTAINER */}
      <main className="flex-1 grid grid-cols-1 xl:grid-cols-4 gap-6 p-6">
        
        {/* LEFT COLUMN: CONTROL & SETTINGS (1 Span) */}
        <div className="xl:col-span-1 flex flex-col gap-6">
          
          {/* RUN ENGINE PANEL */}
          <section className="glass-panel p-5 flex flex-col gap-4">
            <h2 className="text-sm font-bold tracking-wider uppercase text-cyan-neon flex items-center gap-2 border-b border-subtle pb-2">
              <Activity className="w-4 h-4" /> Running Engine Controls
            </h2>

            <div className="flex flex-col gap-3">
              <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                EXECUTION MODE
                <select value={mode} onChange={(e) => setMode(e.target.value)}>
                  <option value="BACKTEST">BACKTEST</option>
                  <option value="PAPER">PAPER TRADING</option>
                  <option value="LIVE">LIVE STRATEGY</option>
                  <option value="MANUAL">MANUAL DESK</option>
                </select>
              </label>

              <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                  LOTS (LOT SIZE)
                  <input type="number" min="1" value={lotSize} onChange={(e) => setLotSize(parseInt(e.target.value) || 1)} />
                </label>

                <label className="flex items-center gap-2 mt-5 text-xs text-text-mute select-none cursor-pointer">
                  <input type="checkbox" checked={liveProtection} onChange={(e) => setLiveProtection(e.target.checked)} />
                  LIVE EXECUTION
                </label>
              </div>

              {mode === "BACKTEST" && (
                <div className="border-t border-subtle pt-3 flex flex-col gap-3">
                  <div className="grid grid-cols-2 gap-3">
                    <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                      START DATE
                      <input type="date" onChange={(e) => {}} />
                    </label>
                    <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                      END DATE
                      <input type="date" onChange={(e) => {}} />
                    </label>
                  </div>
                </div>
              )}

              <div className="flex gap-3 mt-2">
                {sys.state === "IDLE" || sys.state === "COMPLETED" || sys.state === "FAILED" || sys.state === "DISCONNECTED" ? (
                  <button onClick={handleStartEngine} className="flex-1 py-2.5 bg-cyan-neon hover:bg-cyan-neon/80 text-text-dark font-bold uppercase flex items-center justify-center gap-2 shadow-lg shadow-cyan-neon/20">
                    <Play className="w-4 h-4 fill-text-dark" /> Launch
                  </button>
                ) : (
                  <button onClick={handleStopEngine} className="flex-1 py-2.5 bg-red-neon hover:bg-red-neon/80 text-text-main font-bold uppercase flex items-center justify-center gap-2 shadow-lg shadow-red-neon/20">
                    <Square className="w-4 h-4 fill-text-main" /> Halt Engine
                  </button>
                )}
              </div>
            </div>
          </section>

          {/* TARGET CONFLICT REGISTRY */}
          <section className="glass-panel p-5 flex flex-col gap-4">
            <h2 className="text-sm font-bold tracking-wider uppercase text-cyan-neon flex items-center gap-2 border-b border-subtle pb-2">
              <Target className="w-4 h-4" /> Target Config Registry
            </h2>

            <div className="flex flex-col gap-3">
              <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                  UNDERLYING INDEX
                  <select value={indexName} onChange={(e) => setIndexName(e.target.value)}>
                    <option value="NIFTY">NIFTY 50</option>
                    <option value="BANKNIFTY">NIFTY BANK</option>
                    <option value="FINNIFTY">NIFTY FIN SERVICE</option>
                    <option value="MIDCPNIFTY">MIDCP NIFTY</option>
                    <option value="SENSEX">SENSEX</option>
                    <option value="BANKEX">BANKEX</option>
                  </select>
                </label>

                <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                  EXCHANGE
                  <select value={exchange} onChange={(e) => setExchange(e.target.value)}>
                    <option value="NSE">NSE</option>
                    <option value="BSE">BSE</option>
                  </select>
                </label>
              </div>

              <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                CONTRACT EXPIRY
                <select value={selectedExpiry} onChange={(e) => setSelectedExpiry(e.target.value)}>
                  {expiries.map(exp => (
                    <option key={exp} value={exp}>{exp}</option>
                  ))}
                </select>
              </label>

              <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                  OPTION TYPE
                  <select value={optionType} onChange={(e) => setOptionType(e.target.value)}>
                    <option value="CE">CALL (CE)</option>
                    <option value="PE">PUT (PE)</option>
                  </select>
                </label>

                <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                  STRIKE PRICE
                  <select value={selectedStrike} onChange={(e) => setSelectedStrike(e.target.value)}>
                    <option value="ATM">ATM (₹{atmStrike || "Loading"})</option>
                    {strikes.map(stk => (
                      <option key={stk} value={stk}>{stk}</option>
                    ))}
                  </select>
                </label>
              </div>

              {sys.state !== "IDLE" && (
                <button onClick={handleUpdateTarget} className="py-2 mt-2 bg-transparent hover:bg-white/5 border border-cyan-neon/30 hover:border-cyan-neon text-cyan-neon font-semibold flex items-center justify-center gap-2">
                  <RefreshCw className="w-4 h-4" /> Hot-Swap Target
                </button>
              )}
            </div>
          </section>

          {/* TELEMETRY HUD STATS */}
          <section className="glass-panel p-5 flex flex-col gap-4">
            <h2 className="text-sm font-bold tracking-wider uppercase text-cyan-neon flex items-center gap-2 border-b border-subtle pb-2">
              <TrendingUp className="w-4 h-4" /> Telemetry HUD Metrics
            </h2>

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white/2 border border-subtle p-3 rounded-lg">
                <span className="text-[10px] tracking-wider text-text-mute uppercase flex items-center gap-1">
                  <DollarSign className="w-3 h-3 text-cyan-neon" /> Net P&L
                </span>
                <p className={`text-lg font-bold mt-1 ${sys.total_pnl >= 0 ? "text-green-neon" : "text-red-neon"}`}>
                  ₹{sys.total_pnl?.toFixed(2) || "0.00"}
                </p>
              </div>

              <div className="bg-white/2 border border-subtle p-3 rounded-lg">
                <span className="text-[10px] tracking-wider text-text-mute uppercase flex items-center gap-1">
                  <Percent className="w-3 h-3 text-cyan-neon" /> Return
                </span>
                <p className={`text-lg font-bold mt-1 ${sys.return_percent >= 0 ? "text-green-neon" : "text-red-neon"}`}>
                  {sys.return_percent?.toFixed(2) || "0.00"}%
                </p>
              </div>

              <div className="bg-white/2 border border-subtle p-3 rounded-lg">
                <span className="text-[10px] tracking-wider text-text-mute uppercase flex items-center gap-1">
                  <Award className="w-3 h-3 text-cyan-neon" /> Win Rate
                </span>
                <p className="text-lg font-bold mt-1 text-main">
                  {sys.win_rate?.toFixed(1) || "0.0"}%
                </p>
              </div>

              <div className="bg-white/2 border border-subtle p-3 rounded-lg">
                <span className="text-[10px] tracking-wider text-text-mute uppercase flex items-center gap-1">
                  <Shield className="w-3 h-3 text-cyan-neon" /> Max DD
                </span>
                <p className="text-lg font-bold mt-1 text-red-neon">
                  ₹{sys.max_drawdown?.toFixed(2) || "0.00"}
                </p>
              </div>
            </div>
          </section>
        </div>

        {/* MIDDLE COLUMN: CHART & ACTIVE METADATA ROOM (2 Spans) */}
        <div className="xl:col-span-2 flex flex-col gap-6">
          
          {/* MAIN CHARTS AND INTERVAL SELECT */}
          <section className="glass-panel p-5 flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-subtle pb-3">
              <div className="flex items-center gap-2">
                <Activity className="text-cyan-neon w-5 h-5" />
                <h2 className="text-sm font-bold tracking-wider uppercase">
                  Option Contract Real-Time Chart: <span className="text-cyan-neon">{sys.trading_symbol || "No Feed Connected"}</span>
                </h2>
              </div>

              <div className="flex items-center gap-2">
                <select 
                  className="text-xs py-1"
                  value={timeframe} 
                  onChange={(e) => handleChartConfigUpdate(e.target.value, candleType)}
                >
                  <option value="10s">10 SEC</option>
                  <option value="30s">30 SEC</option>
                  <option value="1minute">1 MINUTE</option>
                  <option value="5minute">5 MINUTE</option>
                  <option value="15minute">15 MINUTE</option>
                </select>

                <select 
                  className="text-xs py-1"
                  value={candleType} 
                  onChange={(e) => handleChartConfigUpdate(timeframe, e.target.value)}
                >
                  <option value="heikin_ashi">HEIKIN ASHI</option>
                  <option value="candlestick">CANDLESTICK</option>
                </select>
              </div>
            </div>

            {/* CHART ELEMENT CONTAINER */}
            <div className="relative w-full h-[350px] bg-black/40 rounded-lg overflow-hidden border border-subtle">
              <div ref={chartContainerRef} className="w-full h-full" />
              {(!telemetry?.candles || telemetry.candles.length === 0) && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/60 backdrop-blur-sm z-10">
                  <p className="text-xs text-text-mute tracking-widest uppercase">Waiting for Tick Stream / Loading Candles...</p>
                </div>
              )}
            </div>
          </section>

          {/* ACTIVE POSITION HUD */}
          <section className="glass-panel p-5">
            <h2 className="text-sm font-bold tracking-wider uppercase text-cyan-neon border-b border-subtle pb-2 mb-3">
              Active Trade Desk Position
            </h2>

            {sys.position ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-2 border border-subtle rounded bg-white/1">
                  <span className="text-[10px] text-text-mute uppercase block">INSTRUMENT</span>
                  <span className="font-bold text-sm text-main">{sys.trading_symbol}</span>
                </div>
                <div className="p-2 border border-subtle rounded bg-white/1">
                  <span className="text-[10px] text-text-mute uppercase block">ENTRY PRICE</span>
                  <span className="font-bold text-sm text-main">₹{sys.position.entry_price?.toFixed(2)}</span>
                </div>
                <div className="p-2 border border-subtle rounded bg-white/1">
                  <span className="text-[10px] text-text-mute uppercase block">STOP LOSS</span>
                  <span className="font-bold text-sm text-red-neon">₹{sys.position.stop_loss?.toFixed(2) || "0.00"}</span>
                </div>
                <div className="p-2 border border-subtle rounded bg-white/1">
                  <span className="text-[10px] text-text-mute uppercase block">TARGET PRICE</span>
                  <span className="font-bold text-sm text-green-neon">₹{sys.position.target_price?.toFixed(2) || "0.00"}</span>
                </div>
              </div>
            ) : (
              <div className="h-16 flex items-center justify-center border border-dashed border-subtle rounded-lg">
                <p className="text-xs text-text-mute uppercase tracking-widest">No active open positions</p>
              </div>
            )}
          </section>

          {/* EVENT LOGS TERMINAL */}
          <section className="glass-panel p-5 flex flex-col gap-3">
            <div className="flex items-center justify-between border-b border-subtle pb-2">
              <h2 className="text-sm font-bold tracking-wider uppercase text-cyan-neon">System Console logs</h2>
              <span className="text-[10px] tracking-wider text-text-mute uppercase">Live Feed</span>
            </div>

            <div ref={logTerminalRef} className="terminal-log">
              {logs.length === 0 ? (
                <div className="text-text-mute opacity-50 italic">Console initialized. Ready.</div>
              ) : (
                logs.map((log, index) => (
                  <div key={index} className={`terminal-line ${getLogClass(log)}`}>
                    {log}
                  </div>
                ))
              )}
            </div>
          </section>
        </div>

        {/* RIGHT COLUMN: ORDER DESK & GTT (1 Span) */}
        <div className="xl:col-span-1 flex flex-col gap-6">
          
          {/* PANEL TABS */}
          <section className="glass-panel p-5 flex flex-col gap-4">
            <div className="flex border-b border-subtle mb-1">
              <button 
                onClick={() => setActiveOrderTab("standard")} 
                className={`tab-btn flex-1 py-2 font-bold uppercase tracking-wider text-xs ${activeOrderTab === "standard" ? "active" : ""}`}
              >
                Order Pad
              </button>
              <button 
                onClick={() => setActiveOrderTab("gtt")} 
                className={`tab-btn flex-1 py-2 font-bold uppercase tracking-wider text-xs ${activeOrderTab === "gtt" ? "active" : ""}`}
              >
                GTT Bracket
              </button>
            </div>

            {/* TAB CONTAINER: STANDARD ORDER DESK */}
            {activeOrderTab === "standard" ? (
              <div className="flex flex-col gap-4">
                <div className="grid grid-cols-2 gap-3">
                  <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                    LOTS (ORDER QTY)
                    <input type="number" min="1" value={orderQty} onChange={(e) => setOrderQty(parseInt(e.target.value) || 1)} />
                  </label>
                  <label className="flex items-center gap-2 mt-5 text-xs text-text-mute select-none cursor-pointer">
                    <input type="checkbox" checked={isScalperMode} onChange={(e) => setIsScalperMode(e.target.checked)} />
                    SCALPER EXEC
                  </label>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                    TARGET LIMIT
                    <input type="number" step="0.5" value={orderTarget} onChange={(e) => setOrderTarget(parseFloat(e.target.value) || 0)} />
                  </label>
                  <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                    TARGET UNIT
                    <select value={orderTargetType} onChange={(e) => setOrderTargetType(e.target.value)}>
                      <option value="points">Points (Abs)</option>
                      <option value="percent">Percentage (%)</option>
                    </select>
                  </label>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                    STOP LOSS (SL)
                    <input type="number" step="0.5" value={orderStopLoss} onChange={(e) => setOrderStopLoss(parseFloat(e.target.value) || 0)} />
                  </label>
                  <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                    SL UNIT
                    <select value={orderStopLossType} onChange={(e) => setOrderStopLossType(e.target.value)}>
                      <option value="points">Points (Abs)</option>
                      <option value="percent">Percentage (%)</option>
                    </select>
                  </label>
                </div>

                <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                  TRAILING SL GAP (POINTS)
                  <input type="number" step="0.5" value={orderTrailingGap} onChange={(e) => setOrderTrailingGap(parseFloat(e.target.value) || 0)} />
                </label>

                <div className="grid grid-cols-2 gap-3 mt-2">
                  <button onClick={handleManualBuy} className="py-3 bg-green-neon hover:bg-green-neon/80 text-text-dark font-bold uppercase flex items-center justify-center gap-1.5">
                    <Zap className="w-4 h-4 fill-text-dark" /> Buy Order
                  </button>
                  <button onClick={handleManualSell} className="py-3 bg-red-neon/30 hover:bg-red-neon/50 border border-red-neon text-red-neon font-bold uppercase flex items-center justify-center gap-1.5">
                    <XCircle className="w-4 h-4" /> Square Off
                  </button>
                </div>
              </div>
            ) : (
              /* TAB CONTAINER: GTT BRACKETS ORDER DESK */
              <div className="flex flex-col gap-4">
                <div className="grid grid-cols-2 gap-3">
                  <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                    TRIGGER PRICE
                    <input type="number" step="0.5" value={gttTriggerPrice} onChange={(e) => setGttTriggerPrice(parseFloat(e.target.value) || 0)} />
                  </label>
                  <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                    LOTS (ORDER QTY)
                    <input type="number" min="1" value={orderQty} onChange={(e) => setOrderQty(parseInt(e.target.value) || 1)} />
                  </label>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                    TRIGGER DIRECTION
                    <select value={gttSide} onChange={(e) => setGttSide(e.target.value)}>
                      <option value="BUY">BUY SIDE</option>
                      <option value="SELL">SELL SIDE</option>
                    </select>
                  </label>
                  <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                    ORDER TYPE
                    <select value={gttOrderType} onChange={(e) => setGttOrderType(e.target.value)}>
                      <option value="MARKET">MARKET</option>
                      <option value="LIMIT">LIMIT</option>
                    </select>
                  </label>
                </div>

                {gttOrderType === "LIMIT" && (
                  <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                    LIMIT ENTRY PRICE
                    <input type="number" step="0.5" value={gttLimitPrice} onChange={(e) => setGttLimitPrice(parseFloat(e.target.value) || 0)} />
                  </label>
                )}

                <div className="border-t border-subtle pt-3 flex flex-col gap-3">
                  <p className="text-[10px] text-text-mute font-bold uppercase tracking-widest mb-1">Exit brackets</p>
                  
                  <div className="grid grid-cols-2 gap-3">
                    <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                      TARGET EXIT
                      <input type="number" step="0.5" value={orderTarget} onChange={(e) => setOrderTarget(parseFloat(e.target.value) || 0)} />
                    </label>
                    <label className="flex flex-col gap-1.5 text-xs text-text-mute">
                      STOP LOSS EXIT
                      <input type="number" step="0.5" value={orderStopLoss} onChange={(e) => setOrderStopLoss(parseFloat(e.target.value) || 0)} />
                    </label>
                  </div>
                </div>

                <button onClick={handleCreateGtt} className="py-3 mt-2 bg-cyan-neon hover:bg-cyan-neon/80 text-text-dark font-bold uppercase flex items-center justify-center gap-1.5">
                  <Play className="w-4 h-4 fill-text-dark" /> Set GTT Order
                </button>
              </div>
            )}
            
            {/* EMERGENCY BLINKING PANIC SQUARE-OFF */}
            <button 
              onClick={handlePanicExit} 
              className="py-3 bg-red-neon hover:bg-red-neon/80 text-text-dark font-extrabold uppercase flex items-center justify-center gap-2 border-2 border-red-neon shadow-lg shadow-red-neon/30 animate-pulse mt-2"
            >
              <AlertOctagon className="w-5 h-5 fill-text-dark" /> Emergency Panic Exit
            </button>
          </section>

          {/* ACTIVE GTT BRACKETS */}
          <section className="glass-panel p-5 flex flex-col gap-3">
            <h2 className="text-sm font-bold tracking-wider uppercase text-cyan-neon border-b border-subtle pb-2">
              Active GTT Orders ({gttOrders.filter(o => o.status === "PENDING").length})
            </h2>

            <div className="max-h-[160px] overflow-y-auto flex flex-col gap-2">
              {gttOrders.filter(o => o.status === "PENDING").length === 0 ? (
                <div className="h-12 flex items-center justify-center text-[10px] text-text-mute uppercase tracking-widest border border-dashed border-subtle rounded">
                  No active GTT orders
                </div>
              ) : (
                gttOrders.filter(o => o.status === "PENDING").map((order) => (
                  <div key={order.id} className="flex items-center justify-between border border-subtle p-2 rounded bg-white/1 text-xs">
                    <div>
                      <p className="font-semibold text-main">
                        {order.side} {order.qty} Lots @ ₹{order.trigger_price}
                      </p>
                      <p className="text-[10px] text-text-mute">
                        SL: {order.stop_loss} | Target: {order.target}
                      </p>
                    </div>
                    <button 
                      onClick={() => handleCancelGtt(order.id)} 
                      className="p-1 text-red-neon hover:bg-red-neon/10 rounded"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </section>

          {/* CLOSED TRADES HISTORY */}
          <section className="glass-panel p-5 flex flex-col gap-3">
            <h2 className="text-sm font-bold tracking-wider uppercase text-cyan-neon border-b border-subtle pb-2">
              Closed Trade Ledger
            </h2>

            <div className="max-h-[220px] overflow-y-auto flex flex-col gap-2">
              {trades.length === 0 ? (
                <div className="h-16 flex items-center justify-center text-[10px] text-text-mute uppercase tracking-widest border border-dashed border-subtle rounded">
                  No trades registered
                </div>
              ) : (
                trades.map((trade) => (
                  <div key={trade.id} className="border border-subtle p-2.5 rounded bg-white/1 text-xs">
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-bold text-main">{trade.trading_symbol}</span>
                      <span className={`font-bold ${trade.pnl >= 0 ? "text-green-neon" : "text-red-neon"}`}>
                        {trade.pnl >= 0 ? "+" : ""}₹{trade.pnl.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between text-[10px] text-text-mute">
                      <span>Side: {trade.type} | Lots: {trade.quantity / sys.lot_size_multiplier}</span>
                      <span>Reason: {trade.reason}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
        
      </main>

      {/* FOOTER SYSTEM STATS */}
      <footer className="px-6 py-3 border-t border-subtle glass-panel rounded-none text-center text-xs text-text-mute flex items-center justify-between">
        <span>Valkyrie Desktop CLI Engine v2.0.0</span>
        <span className="text-[10px]">Security Protocol: MIS Intraday Execution Loop Active</span>
      </footer>
    </div>
  );
}
