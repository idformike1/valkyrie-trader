export interface BackendPosition {
  instrument_key: string;
  entry_price: number;
  timestamp: string;
  stop_loss: number;
  target_price: number;
  is_scalper: boolean;
  trailing_gap: number;
  highest_price: number;
  total_qty: number;
}

export interface BackendSystemStatus {
  state: string;
  mode: string;
  balance: number;
  initial_balance: number;
  position: BackendPosition | null;
  instrument_key: string | null;
  trading_symbol: string | null;
  strike: number | null;
  expiry: string | null;
  option_type: "CE" | "PE" | null;
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
  scalper_instrument_key: string | null;
  scalper_trading_symbol: string | null;
  scalper_lot_multiplier: number;
  scalper_option_type: string | null;
  scalper_strike: number | null;
  scalper_spot_price: number;
  sharpe_ratio?: number;
}

export interface BackendTrade {
  id?: number | string;
  session_id?: number;
  instrument_key: string;
  trading_symbol: string;
  type: "BUY" | "EXIT";
  price: number;
  quantity: number;
  sl: number;
  target: number;
  reason: string;
  pnl: number;
  timestamp: string;
  upstox_order_id?: string;
}

export interface BackendCandle {
  timestamp: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface BackendGttOrder {
  id: string;
  trigger_price: number;
  side: "BUY" | "SELL";
  qty: number;
  order_type: string;
  price: number;
  target: number;
  target_type: string;
  stop_loss: number;
  stop_loss_type: string;
  trailing_gap: number;
  direction: "ABOVE" | "BELOW";
  status: "PENDING" | "TRIGGERED" | "CANCELLED";
  timestamp: string;
}

export interface TelemetryPayload {
  status: BackendSystemStatus;
  trades: BackendTrade[];
  logs: string[];
  candles: BackendCandle[];
  gtt_orders: BackendGttOrder[];
  equity_curve?: Array<{ timestamp: string; equity: number }>;
}

export interface BuyOrderRequest {
  qty: number;
  target: number;
  target_type: string;
  stop_loss: number;
  stop_loss_type: string;
  trailing_gap: number;
  is_scalper: boolean;
}

export interface GttOrderRequest {
  trigger_price: number;
  qty: number;
  side: "BUY" | "SELL";
  order_type: string;
  price: number;
  target: number;
  target_type: string;
  stop_loss: number;
  stop_loss_type: string;
  trailing_gap: number;
  direction?: "ABOVE" | "BELOW";
}

export interface StartBacktestRequest {
  mode: "BACKTEST";
  strategy: string;
  lot_size?: number;
  expiry?: string;
  option_type?: string;
  strike?: string;
  exchange?: string;
  index_name?: string;
  start_date?: string;
  end_date?: string;
  timeframe?: string;
  max_candles?: number;
  cutoff_time?: string;
  brokerage_flat?: number;
  slippage_pct?: number;
  initial_balance?: number;
  five_ema_period?: number;
  five_ema_rr?: number;
}
