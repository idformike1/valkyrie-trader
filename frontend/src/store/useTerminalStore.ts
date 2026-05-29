import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface Account {
  id: string;
  name: string;
  type: "live" | "paper";
}

export interface Instrument {
  instrumentKey: string;
  symbol: string;
  exchange: "NSE" | "BSE";
}

export interface Strategy {
  strategyId: string;
  strategyName: string;
  version: string;
}

export type Timeframe = "1m" | "3m" | "5m" | "15m" | "1h" | "1d";

export type ActiveMode = "manual" | "scalper" | "paper" | "backtest" | "live";

interface TerminalState {
  currentAccount: Account;
  selectedInstrument: Instrument | null;
  selectedStrategy: Strategy | null;
  selectedTimeframe: Timeframe;
  selectedWorkspace: string;
  activeMode: ActiveMode;

  // Actions
  setAccount: (account: Account) => void;
  setInstrument: (instrument: Instrument | null) => void;
  setStrategy: (strategy: Strategy | null) => void;
  setTimeframe: (timeframe: Timeframe) => void;
  setWorkspace: (workspaceId: string) => void;
  setMode: (mode: ActiveMode) => void;
  resetTerminalContext: () => void;
}

const DEFAULT_ACCOUNT: Account = {
  id: "paper-default",
  name: "Paper Account",
  type: "paper",
};

const DEFAULT_INSTRUMENT: Instrument = {
  instrumentKey: "NSE_INDEX|NIFTY_50",
  symbol: "NIFTY 50",
  exchange: "NSE",
};

const DEFAULT_STRATEGY: Strategy = {
  strategyId: "ema-pullback",
  strategyName: "EMA Pullback v4",
  version: "v4.2.1",
};

export const useTerminalStore = create<TerminalState>()(
  persist(
    (set) => ({
      currentAccount: DEFAULT_ACCOUNT,
      selectedInstrument: DEFAULT_INSTRUMENT,
      selectedStrategy: DEFAULT_STRATEGY,
      selectedTimeframe: "5m",
      selectedWorkspace: "trading",
      activeMode: "paper",

      setAccount: (account) => set({ currentAccount: account }),
      setInstrument: (instrument) => set({ selectedInstrument: instrument }),
      setStrategy: (strategy) => set({ selectedStrategy: strategy }),
      setTimeframe: (timeframe) => set({ selectedTimeframe: timeframe }),
      setWorkspace: (workspaceId) => set({ selectedWorkspace: workspaceId }),
      setMode: (mode) => set({ activeMode: mode }),
      
      resetTerminalContext: () =>
        set({
          currentAccount: DEFAULT_ACCOUNT,
          selectedInstrument: DEFAULT_INSTRUMENT,
          selectedStrategy: DEFAULT_STRATEGY,
          selectedTimeframe: "5m",
          activeMode: "paper",
        }),
    }),
    {
      name: "valkyrie-terminal-context-storage",
    }
  )
);
