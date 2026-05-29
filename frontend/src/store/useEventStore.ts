import { create } from "zustand";

export interface PlatformEvent {
  id: string;
  timestamp: string;
  type: "info" | "success" | "warning" | "error";
  message: string;
  workspace?: string;
}

interface EventState {
  events: PlatformEvent[];
  addEvent: (event: Omit<PlatformEvent, "id" | "timestamp">) => void;
  clearEvents: () => void;
}

const INITIAL_EVENTS: PlatformEvent[] = [
  { id: "1", timestamp: "09:15:02", type: "success", message: "Order Filled - NIFTY 15 MAY 22300 CE Buy @ 123.40 (1 Lot)", workspace: "Scalper" },
  { id: "2", timestamp: "09:15:30", type: "info", message: "Strategy Started - EMA Pullback v4", workspace: "Backtest" },
  { id: "3", timestamp: "09:16:15", type: "info", message: "WebSocket (Upstox) Stream Connected", workspace: "System" },
  { id: "4", timestamp: "09:17:45", type: "warning", message: "Option stream latency peak: 140ms", workspace: "System" },
  { id: "5", timestamp: "09:18:10", type: "success", message: "Live Engine Initialized on Paper Mode", workspace: "Paper Trading" },
  { id: "6", timestamp: "09:19:05", type: "error", message: "Failed to load historical data for MIDCPNIFTY", workspace: "Backtest" },
  { id: "7", timestamp: "09:20:00", type: "success", message: "WebSocket Reconnected", workspace: "System" },
  { id: "8", timestamp: "09:21:12", type: "success", message: "Position Closed - BANKNIFTY CE (P&L: +₹1,250.00)", workspace: "Trading" },
];

export const useEventStore = create<EventState>((set) => ({
  events: INITIAL_EVENTS,
  addEvent: (event) =>
    set((state) => {
      const now = new Date();
      const timestamp = now.toTimeString().split(" ")[0];
      const newEvent: PlatformEvent = {
        ...event,
        id: Math.random().toString(36).substr(2, 9),
        timestamp,
      };
      // Keep last 100 events
      return { events: [newEvent, ...state.events].slice(0, 100) };
    }),
  clearEvents: () => set({ events: [] }),
}));
