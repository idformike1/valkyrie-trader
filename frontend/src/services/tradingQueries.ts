import { create } from "zustand";
import { tradingApi } from "./tradingApi";
import { BackendSystemStatus, BackendTrade, BackendGttOrder, BackendCandle, StartBacktestRequest } from "./tradingTypes";

export type ConnectionStatus = "DISCONNECTED" | "CONNECTING" | "CONNECTED" | "ERROR";

interface TradingQueriesState {
  status: BackendSystemStatus | null;
  trades: BackendTrade[];
  logs: string[];
  candles: BackendCandle[];
  gttOrders: BackendGttOrder[];
  equityCurve: Array<{ timestamp: string; equity: number }>;

  connectionStatus: ConnectionStatus;
  wsError: string | null;

  isLoading: boolean;
  actionError: string | null;
  successMessage: string | null;

  connectTelemetry: () => void;
  disconnectTelemetry: () => void;

  buy: (
    qty: number,
    target: number,
    targetType: string,
    sl: number,
    slType: string,
    trailingGap: number,
    isScalper: boolean
  ) => Promise<boolean>;
  sell: () => Promise<boolean>;
  panicExit: () => Promise<boolean>;
  createGtt: (
    triggerPrice: number,
    qty: number,
    side: "BUY" | "SELL",
    orderType: string,
    price: number,
    target: number,
    targetType: string,
    sl: number,
    slType: string,
    trailingGap: number,
    direction?: "ABOVE" | "BELOW"
  ) => Promise<boolean>;
  cancelGtt: (id: string) => Promise<boolean>;
  startBacktest: (payload: StartBacktestRequest) => Promise<boolean>;
  clearMessages: () => void;
}

let ws: WebSocket | null = null;
let reconnectTimer: NodeJS.Timeout | null = null;

export const useBackendTradingStore = create<TradingQueriesState>((set, get) => {
  const handleMessage = (event: MessageEvent) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.status) {
        set({
          status: payload.status,
          trades: payload.trades || [],
          logs: payload.logs || [],
          candles: payload.candles || [],
          gttOrders: payload.gtt_orders || [],
          equityCurve: payload.equity_curve || [],
          connectionStatus: "CONNECTED",
          wsError: null,
        });
      }
    } catch (err: any) {
      console.error("Failed to parse telemetry frame:", err);
    }
  };

  const connect = () => {
    if (ws) {
      ws.close();
    }

    set({ connectionStatus: "CONNECTING", wsError: null });
    const wsUrl = process.env.NEXT_PUBLIC_WS_BACKEND_URL || "ws://localhost:8081/ws/telemetry";

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        set({ connectionStatus: "CONNECTED", wsError: null });
      };

      ws.onmessage = handleMessage;

      ws.onerror = (event) => {
        set({ connectionStatus: "ERROR", wsError: "WebSocket connection error occurred." });
      };

      ws.onclose = () => {
        ws = null;
        if (get().connectionStatus !== "DISCONNECTED") {
          set({ connectionStatus: "ERROR", wsError: "Disconnected from backend server. Retrying..." });
          if (reconnectTimer) clearTimeout(reconnectTimer);
          reconnectTimer = setTimeout(() => {
            connect();
          }, 3000);
        }
      };
    } catch (err: any) {
      set({ connectionStatus: "ERROR", wsError: err.message || "Failed to establish socket." });
    }
  };

  return {
    status: null,
    trades: [],
    logs: [],
    candles: [],
    gttOrders: [],
    equityCurve: [],
    connectionStatus: "DISCONNECTED",
    wsError: null,
    isLoading: false,
    actionError: null,
    successMessage: null,

    connectTelemetry: () => {
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        return;
      }
      connect();
    },

    disconnectTelemetry: () => {
      set({ connectionStatus: "DISCONNECTED" });
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) {
        ws.close();
        ws = null;
      }
    },

    clearMessages: () => {
      set({ actionError: null, successMessage: null });
    },

    buy: async (qty, target, targetType, sl, slType, trailingGap, isScalper) => {
      set({ isLoading: true, actionError: null, successMessage: null });
      try {
        const response = await tradingApi.manualBuy({
          qty,
          target,
          target_type: targetType,
          stop_loss: sl,
          stop_loss_type: slType,
          trailing_gap: trailingGap,
          is_scalper: isScalper,
        });
        set({
          isLoading: false,
          successMessage: response.message,
          status: response.status,
        });
        return true;
      } catch (err: any) {
        set({ isLoading: false, actionError: err.message || "Order execution failed" });
        return false;
      }
    },

    sell: async () => {
      set({ isLoading: true, actionError: null, successMessage: null });
      try {
        const response = await tradingApi.manualSell();
        set({
          isLoading: false,
          successMessage: response.message,
          status: response.status,
        });
        return true;
      } catch (err: any) {
        set({ isLoading: false, actionError: err.message || "Position exit failed" });
        return false;
      }
    },

    panicExit: async () => {
      set({ isLoading: true, actionError: null, successMessage: null });
      try {
        const response = await tradingApi.manualPanicExit();
        set({
          isLoading: false,
          successMessage: response.message,
          status: response.status,
        });
        return true;
      } catch (err: any) {
        set({ isLoading: false, actionError: err.message || "Panic square off failed" });
        return false;
      }
    },

    createGtt: async (triggerPrice, qty, side, orderType, price, target, targetType, sl, slType, trailingGap, direction) => {
      set({ isLoading: true, actionError: null, successMessage: null });
      try {
        const response = await tradingApi.createGtt({
          trigger_price: triggerPrice,
          qty,
          side,
          order_type: orderType,
          price,
          target,
          target_type: targetType,
          stop_loss: sl,
          stop_loss_type: slType,
          trailing_gap: trailingGap,
          direction,
        });
        set({
          isLoading: false,
          successMessage: response.message,
          gttOrders: [...get().gttOrders, response.gtt_order],
        });
        return true;
      } catch (err: any) {
        set({ isLoading: false, actionError: err.message || "GTT creation failed" });
        return false;
      }
    },

    cancelGtt: async (id) => {
      set({ isLoading: true, actionError: null, successMessage: null });
      try {
        const response = await tradingApi.cancelGtt(id);
        set({
          isLoading: false,
          successMessage: response.message,
          gttOrders: get().gttOrders.map((o) =>
            o.id === id ? { ...o, status: "CANCELLED" as const } : o
          ),
        });
        return true;
      } catch (err: any) {
        set({ isLoading: false, actionError: err.message || "GTT cancellation failed" });
        return false;
      }
    },

    startBacktest: async (payload) => {
      set({ isLoading: true, actionError: null, successMessage: null });
      try {
        const response = await tradingApi.startBacktest(payload);
        set({
          isLoading: false,
          successMessage: response.message,
          status: response.status,
        });
        return true;
      } catch (err: any) {
        set({ isLoading: false, actionError: err.message || "Backtest start failed" });
        return false;
      }
    },
  };
});
