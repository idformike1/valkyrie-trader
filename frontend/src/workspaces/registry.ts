import { WorkspaceConfig } from "./types";
import {
  TradingLeft,
  TradingMain,
  TradingRight,
  TradingBottom
} from "./ManualTradingWorkspace";
import {
  ScalperMain,
  ScalperRight,
  ScalperBottom
} from "./ScalperWorkspace";
import {
  BacktestLeft,
  BacktestMain,
  BacktestRight,
  BacktestBottom
} from "./BacktestWorkspace";
import {
  PaperLeft,
  PaperMain,
  PaperRight,
  PaperBottom
} from "./PaperWorkspace";
import {
  DeploymentsLeft,
  DeploymentsMain,
  DeploymentsRight,
  DeploymentsBottom
} from "./DeploymentsWorkspace";
import {
  OperationsLeft,
  OperationsMain,
  OperationsRight,
  OperationsBottom
} from "./OperationsWorkspace";

export const WORKSPACE_REGISTRY: Record<string, WorkspaceConfig> = {
  trading: {
    id: "trading",
    name: "Trading",
    description: "Live option trading console with execution panel and margin logs",
    icon: "TrendingUp",
    panels: {
      left: TradingLeft,
      main: TradingMain,
      right: TradingRight,
      bottom: TradingBottom
    }
  },
  scalper: {
    id: "scalper",
    name: "Scalper",
    description: "Ultra-fast DOM scalping layout with keyboard shortcuts and panic switch",
    icon: "Zap",
    panels: {
      main: ScalperMain,
      right: ScalperRight,
      bottom: ScalperBottom
    }
  },
  backtest: {
    id: "backtest",
    name: "Backtest",
    description: "Simulate EMA/VWAP strategy execution on historical data streams",
    icon: "BarChart2",
    panels: {
      left: BacktestLeft,
      main: BacktestMain,
      right: BacktestRight,
      bottom: BacktestBottom
    }
  },
  deployments: {
    id: "deployments",
    name: "Deployments",
    description: "Monitor container instance profiles and memory levels",
    icon: "Server",
    panels: {
      left: DeploymentsLeft,
      main: DeploymentsMain,
      right: DeploymentsRight,
      bottom: DeploymentsBottom
    }
  },
  paper: {
    id: "paper",
    name: "Paper Trading",
    description: "Deploy options strategies on real-time paper accounts",
    icon: "Layers",
    panels: {
      left: PaperLeft,
      main: PaperMain,
      right: PaperRight,
      bottom: PaperBottom
    }
  },
  operations: {
    id: "operations",
    name: "Operations",
    description: "Trace system health, websocket latency, and ledger audits",
    icon: "Settings",
    panels: {
      left: OperationsLeft,
      main: OperationsMain,
      right: OperationsRight,
      bottom: OperationsBottom
    }
  }
};

export const getWorkspaceConfig = (id: string): WorkspaceConfig | undefined => {
  return WORKSPACE_REGISTRY[id];
};

export const getAllWorkspaces = (): WorkspaceConfig[] => {
  return Object.values(WORKSPACE_REGISTRY);
};
