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
  execution_model: string;
  walk_forward_enabled?: boolean;
  walk_forward_train_days?: number;
  walk_forward_test_days?: number;
  walk_forward_step_days?: number;
  walk_forward_ranges?: Array<{ name: string; type: string; min_val: number; max_val: number; step: number; options?: string[] }>;
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
    execution_adjusted_profit?: number;
    execution_adjusted_return?: number;
    average_slippage_cost?: number;
    average_spread_cost?: number;
    average_volatility_cost?: number;
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
    explanation?: {
      strategy_name: string;
      entry_reason: string;
      exit_reason: string;
      signal_snapshot: Record<string, any>;
      resolver_snapshot: Record<string, any>;
      risk_snapshot: Record<string, any>;
      market_snapshot: Record<string, any>;
    };
    execution_analysis?: {
      execution_model: string;
      theoretical_entry: number;
      effective_entry: number;
      theoretical_exit: number;
      effective_exit: number;
      spread_cost: number;
      volatility_cost: number;
      pnl_degradation: number;
    };
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
  runtime_logs?: Array<{
    timestamp: string;
    category: string;
    severity: string;
    message: string;
    metadata: Record<string, any>;
  }>;
  robustness_analysis?: {
    robustness_score: number;
    classification: string;
    metrics_stability: {
      profit_stability: number;
      win_rate_stability: number;
      pf_stability: number;
      drawdown_stability: number;
      return_stability: number;
    };
    mode_results: Record<string, {
      net_profit: number;
      win_rate: number;
      profit_factor: number;
      max_drawdown: number;
      net_return: number;
    }>;
  };
  walk_forward_analysis?: {
    walk_forward_score: number;
    classification: string;
    stability: {
      profit_stability: number;
      pf_stability: number;
      drawdown_stability: number;
      robustness_stability: number;
      consistency_score: number;
    };
    windows: Array<{
      window_index: number;
      train_start: string;
      train_end: string;
      test_start: string;
      test_end: string;
      best_params: Record<string, any>;
      train_net_profit: number;
      train_win_rate: number;
      train_profit_factor: number;
      train_max_drawdown: number;
      train_net_return: number;
      train_robustness_score: number;
      train_classification: string;
      test_net_profit: number;
      test_win_rate: number;
      test_profit_factor: number;
      test_max_drawdown: number;
      test_net_return: number;
      test_robustness_score: number;
      test_classification: string;
      test_mode_results: Record<string, {
        net_profit: number;
        win_rate: number;
        profit_factor: number;
        max_drawdown: number;
        net_return: number;
      }>;
    }>;
  };
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

export interface StrategyParameterMetadata {
  name: string;
  type: string;
  default: any;
  description: string;
}

export interface StrategyMetadata {
  id: string;
  name: string;
  category: string;
  description: string;
  market_type: string;
  recommended_timeframes: string[];
  risk_level: string;
  expected_trade_frequency: string;
  entry_logic: string;
  exit_logic: string;
  strike_selection_logic: string;
  expiry_selection_logic: string;
  stop_loss_logic: string;
  target_logic: string;
  supported_parameters: StrategyParameterMetadata[];
  strengths: string[];
  weaknesses: string[];
  best_market_conditions: string;
  worst_market_conditions: string;
}

export interface StrategyPreset {
  id: string;
  name: string;
  strategy_id: string;
  parameters: Record<string, any>;
  risk_management: Record<string, any>;
  strike_selection: Record<string, any>;
  expiry_selection: Record<string, any>;
  timeframe: string;
  notes?: string;
  tags?: string[];
  created_at?: string;
  updated_at?: string;
}

interface BacktestStoreState {
  v2Config: V2Config;
  v2BacktestResult: V2BacktestResult | null;
  v2OptimizationReport: V2OptimizationReport | null;
  v2Status: { state: "IDLE" | "RUNNING" | "COMPLETED" | "FAILED"; progress: number; error: string | null };
  isBacktestLoading: boolean;
  isOptimizationLoading: boolean;
  selectedInspectorParams: Record<string, any> | null;
  selectedTradeId: string | null;
  isReplayMode: boolean;
  replayTradeId: string | null;
  replayCurrentTime: number | null;
  strategiesMetadata: StrategyMetadata[];
  activeStrategyMetadata: StrategyMetadata | null;
  
  // Presets state
  presets: StrategyPreset[];
  presetsLoading: boolean;
  presetsError: string | null;

  setV2Config: (config: Partial<V2Config>) => void;
  runV2Backtest: (overrideConfig?: Partial<V2Config>) => Promise<boolean>;
  runV2Optimization: (ranges: any[], maxWorkers?: number) => Promise<boolean>;
  setSelectedInspectorParams: (params: Record<string, any> | null) => void;
  setSelectedTradeId: (id: string | null) => void;
  setIsReplayMode: (active: boolean) => void;
  setReplayTradeId: (id: string | null) => void;
  setReplayCurrentTime: (time: number | null) => void;
  resetResult: () => void;
  fetchStrategiesMetadata: () => Promise<void>;
  updateActiveStrategyMetadata: (strategyName: string) => void;

  // Presets actions
  fetchPresets: () => Promise<void>;
  createPreset: (preset: Omit<StrategyPreset, "id" | "created_at" | "updated_at"> & { id?: string }) => Promise<StrategyPreset | null>;
  updatePreset: (id: string, updates: Partial<StrategyPreset>) => Promise<StrategyPreset | null>;
  deletePreset: (id: string) => Promise<boolean>;
  duplicatePreset: (id: string, newName: string) => Promise<StrategyPreset | null>;
  loadPreset: (preset: StrategyPreset) => void;
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
  signal_source: "SPOT",
  execution_model: "THEORETICAL",
  walk_forward_enabled: false,
  walk_forward_train_days: 2,
  walk_forward_test_days: 1,
  walk_forward_step_days: 1,
  walk_forward_ranges: []
};

export const useBacktestStore = create<BacktestStoreState>((set, get) => ({
  v2Config: DEFAULT_CONFIG,
  v2BacktestResult: null,
  v2OptimizationReport: null,
  v2Status: { state: "IDLE", progress: 0, error: null },
  isBacktestLoading: false,
  isOptimizationLoading: false,
  selectedInspectorParams: null,
  selectedTradeId: null,
  isReplayMode: false,
  replayTradeId: null,
  replayCurrentTime: null,
  strategiesMetadata: [],
  activeStrategyMetadata: null,

  presets: [],
  presetsLoading: false,
  presetsError: null,

  setV2Config: (config) => {
    set((state) => {
      const nextConfig = { ...state.v2Config, ...config };
      if (config.strategy_name) {
        setTimeout(() => {
          get().updateActiveStrategyMetadata(config.strategy_name!);
        }, 0);
      }
      return { v2Config: nextConfig };
    });
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
  setSelectedTradeId: (id) => set({ selectedTradeId: id }),
  setIsReplayMode: (active) => set({ isReplayMode: active }),
  setReplayTradeId: (id) => set({ replayTradeId: id }),
  setReplayCurrentTime: (time) => set({ replayCurrentTime: time }),
  
  resetResult: () => set({ 
    v2BacktestResult: null, 
    selectedInspectorParams: null, 
    selectedTradeId: null, 
    isReplayMode: false, 
    replayTradeId: null, 
    replayCurrentTime: null 
  }),

  fetchStrategiesMetadata: async () => {
    try {
      const res = await fetch("http://localhost:8081/api/v2/strategies");
      if (res.ok) {
        const data = await res.json();
        set({ strategiesMetadata: data });
        get().updateActiveStrategyMetadata(get().v2Config.strategy_name);
      }
    } catch (err) {
      console.error("Failed to fetch strategies metadata:", err);
    }
  },

  updateActiveStrategyMetadata: (strategyName: string) => {
    const list = get().strategiesMetadata;
    const nameLower = strategyName.toLowerCase();
    let targetId = nameLower;
    if (nameLower === "five_ema_scalping") targetId = "five_ema";
    if (nameLower === "heikin_ashi_gar") targetId = "heikin_ashi";
    if (nameLower === "ema_crossover") targetId = "ema";
    
    const found = list.find((s) => s.id === targetId);
    set({ activeStrategyMetadata: found || null });
  },

  fetchPresets: async () => {
    set({ presetsLoading: true, presetsError: null });
    try {
      const res = await fetch("http://localhost:8081/api/v2/presets");
      if (!res.ok) throw new Error("Failed to fetch presets");
      const data = await res.json();
      set({ presets: data, presetsLoading: false });
    } catch (err: any) {
      set({ presetsLoading: false, presetsError: err.message || "Unknown error" });
      console.error(err);
    }
  },

  createPreset: async (preset) => {
    try {
      const res = await fetch("http://localhost:8081/api/v2/presets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(preset)
      });
      if (!res.ok) throw new Error("Failed to create preset");
      const data = await res.json();
      get().fetchPresets();
      return data;
    } catch (err) {
      console.error(err);
      return null;
    }
  },

  updatePreset: async (id, updates) => {
    try {
      const res = await fetch(`http://localhost:8081/api/v2/presets/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates)
      });
      if (!res.ok) throw new Error("Failed to update preset");
      const data = await res.json();
      get().fetchPresets();
      return data;
    } catch (err) {
      console.error(err);
      return null;
    }
  },

  deletePreset: async (id) => {
    try {
      const res = await fetch(`http://localhost:8081/api/v2/presets/${id}`, {
        method: "DELETE"
      });
      if (!res.ok) throw new Error("Failed to delete preset");
      get().fetchPresets();
      return true;
    } catch (err) {
      console.error(err);
      return false;
    }
  },

  duplicatePreset: async (id, newName) => {
    try {
      const res = await fetch(`http://localhost:8081/api/v2/presets/${id}/duplicate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_name: newName })
      });
      if (!res.ok) throw new Error("Failed to duplicate preset");
      const data = await res.json();
      get().fetchPresets();
      return data;
    } catch (err) {
      console.error(err);
      return null;
    }
  },

  loadPreset: (preset) => {
    set((state) => {
      let strategy_name = preset.strategy_id;
      if (preset.strategy_id === "five_ema") strategy_name = "five_ema_scalping";
      if (preset.strategy_id === "ema") strategy_name = "EMA";
      if (preset.strategy_id === "heikin_ashi") strategy_name = "heikin_ashi_gar";
      if (preset.strategy_id === "heikin_ashi_v2") strategy_name = "heikin_ashi_v2";

      const normalizedParams = { ...preset.parameters };
      if (strategy_name === "EMA") {
        if (normalizedParams.fast_period !== undefined) {
          normalizedParams.fastEma = normalizedParams.fast_period;
        }
        if (normalizedParams.slow_period !== undefined) {
          normalizedParams.slowEma = normalizedParams.slow_period;
        }
      }
      if (strategy_name === "heikin_ashi_gar" || strategy_name === "heikin_ashi_v2") {
        if (normalizedParams.candle_limit !== undefined) {
          normalizedParams.max_candles = normalizedParams.candle_limit;
        }
      }

      const nextConfig = {
        ...state.v2Config,
        strategy_name,
        strategy_params: normalizedParams,
        timeframe: preset.timeframe,
        strike_mode: preset.strike_selection?.mode || "ATM",
        expiry_mode: preset.expiry_selection?.mode || "CURRENT_WEEKLY",
      };

      setTimeout(() => {
        get().updateActiveStrategyMetadata(strategy_name);
      }, 0);

      return { v2Config: nextConfig };
    });
  }
}));
