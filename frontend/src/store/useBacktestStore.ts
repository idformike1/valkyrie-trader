import { create } from "zustand";

export interface V2Config {
  underlying_instrument_key: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  strategy_name: string;
  strategy_params: Record<string, any>;
  option_type_preference: string;
  strike_mode: string;
  expiry_mode: string;
  initial_capital: number;
  lot_multiplier: number;
  brokerage_flat: number;
  slippage_pct: number;
  signal_source: string;
}

export interface V2BacktestResult {
  report: {
    initial_capital: number;
    final_equity: number;
    trade_stats: {
      total_trades: number;
      winning_trades: number;
      losing_trades: number;
      breakeven_trades: number;
      win_rate: number;
      loss_rate: number;
    };
    performance: {
      gross_profit: number;
      gross_loss: number;
      net_profit: number;
      avg_trade: number;
      avg_win: number;
      avg_loss: number;
      largest_win: number;
      largest_loss: number;
      profit_factor: number;
      expectancy: number;
      payoff_ratio: number;
      max_consecutive_wins: number;
      max_consecutive_losses: number;
      avg_hold_time_seconds: number;
      shortest_hold_time_seconds: number;
      longest_hold_time_seconds: number;
      exposure_time_seconds: number;
    };
    equity_curve: Array<{ timestamp: string; equity_value: number; trade_id?: string }>;
    drawdown_curve: Array<{ timestamp: string; drawdown_value: number; drawdown_pct: number; peak_value: number }>;
    max_drawdown: number;
    max_drawdown_pct: number;
    max_drawdown_duration_seconds: number;
    absolute_return_pct: number;
    net_return_pct: number;
    capital_growth_pct: number;
    sharpe_ratio: number;
    sortino_ratio: number;
    grade: string;
    scorecard: Record<string, any>;
  };
  trades: Array<{
    position_id: string;
    entry_time: string;
    exit_time: string;
    contract: string;
    entry_premium: number;
    exit_premium: number;
    quantity: number;
    gross_pnl: number;
    charges: {
      brokerage: number;
      stt: number;
      exchange_charges: number;
      sebi_charges: number;
      gst: number;
      stamp_duty: number;
      total_charges: number;
    };
    net_pnl: number;
  }>;
  candles: Array<{ time: number; open: number; high: number; low: number; close: number }>;
  chart_trades: Array<{
    id: string;
    timestamp: string;
    type: "BUY" | "SELL";
    price: number;
    quantity: number;
    pnl: number;
    reason: string;
    strike: number;
    expiry: string;
    option_type: string;
  }>;
}

export interface OptimizationResult {
  combination: { params: Record<string, any> };
  net_profit: number;
  win_rate: number;
  profit_factor: number;
  expectancy: number;
  max_drawdown: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  trade_count: number;
  composite_score: number;
}

export interface V2OptimizationReport {
  run_info: {
    run_id: string;
    start_time: string;
    end_time: string;
    config: Record<string, any>;
    total_combinations: number;
    executed_combinations: number;
    skipped_combinations: number;
    skipped_details: Record<string, string>;
  };
  top_10: OptimizationResult[];
  top_25: OptimizationResult[];
  top_50: OptimizationResult[];
  heatmap_data: {
    x_param: string;
    y_param: string;
    metric: string;
    x_values: any[];
    y_values: any[];
    matrix: Array<Array<number | null>>;
  };
  stability_findings: Record<string, {
    avg_neighbor_profit: number;
    std_neighbor_profit: number;
    avg_neighbor_composite_score: number;
    drop_pct: number;
    status: string;
  }>;
}

interface BacktestStoreState {
  v2Config: V2Config;
  v2BacktestResult: V2BacktestResult | null;
  v2OptimizationReport: V2OptimizationReport | null;
  v2Status: { state: "IDLE" | "RUNNING" | "COMPLETED" | "FAILED"; progress: number; error: string | null };
  isBacktestLoading: boolean;
  isOptimizationLoading: boolean;
  selectedInspectorParams: Record<string, any> | null;

  setV2Config: (config: Partial<V2Config>) => void;
  runV2Backtest: (overrideConfig?: Partial<V2Config>) => Promise<boolean>;
  runV2Optimization: (ranges: any[], maxWorkers?: number) => Promise<boolean>;
  setSelectedInspectorParams: (params: Record<string, any> | null) => void;
  resetResult: () => void;
}

const DEFAULT_CONFIG: V2Config = {
  underlying_instrument_key: "NSE_INDEX|Nifty 50",
  timeframe: "5m",
  start_date: "2025-04-15",
  end_date: "2025-05-14",
  strategy_name: "EMA",
  strategy_params: { fastEma: 2, slowEma: 3, cut_off_time: "15:25" },
  option_type_preference: "CE_ONLY",
  strike_mode: "ATM",
  expiry_mode: "CURRENT_WEEKLY",
  initial_capital: 100000,
  lot_multiplier: 1,
  brokerage_flat: 20.0,
  slippage_pct: 0.05,
  signal_source: "SPOT"
};

export const useBacktestStore = create<BacktestStoreState>((set, get) => ({
  v2Config: DEFAULT_CONFIG,
  v2BacktestResult: null,
  v2OptimizationReport: null,
  v2Status: { state: "IDLE", progress: 0, error: null },
  isBacktestLoading: false,
  isOptimizationLoading: false,
  selectedInspectorParams: null,

  setV2Config: (config) => {
    set((state) => ({
      v2Config: { ...state.v2Config, ...config }
    }));
  },

  runV2Backtest: async (overrideConfig) => {
    set({ isBacktestLoading: true, v2Status: { state: "RUNNING", progress: 10, error: null } });
    const targetConfig = { ...get().v2Config, ...overrideConfig };
    
    try {
      const res = await fetch("http://localhost:8081/api/v2/backtest/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(targetConfig)
      });
      
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to run V2 backtest");
      }
      
      const data = await res.json();
      set({
        v2BacktestResult: data,
        isBacktestLoading: false,
        v2Status: { state: "COMPLETED", progress: 100, error: null }
      });
      return true;
    } catch (err: any) {
      set({
        isBacktestLoading: false,
        v2Status: { state: "FAILED", progress: 0, error: err.message || "Unknown error" }
      });
      return false;
    }
  },

  runV2Optimization: async (ranges, maxWorkers = 4) => {
    set({ isOptimizationLoading: true });
    
    try {
      const payload = {
        base_config: get().v2Config,
        ranges,
        max_workers: maxWorkers
      };

      const res = await fetch("http://localhost:8081/api/v2/optimization/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to run parameter optimization sweep");
      }

      const data = await res.json();
      set({
        v2OptimizationReport: data,
        isOptimizationLoading: false
      });
      return true;
    } catch (err: any) {
      set({ isOptimizationLoading: false });
      console.error(err);
      return false;
    }
  },

  setSelectedInspectorParams: (params) => set({ selectedInspectorParams: params }),
  
  resetResult: () => set({ v2BacktestResult: null, selectedInspectorParams: null })
}));
