import { create } from "zustand";

export interface SimulatedPosition {
  symbol: string;
  side: "LONG" | "SHORT";
  qty: number;
  avgPrice: number;
  ltp: number;
  pnl: number;
  owner: string;
}

export interface SimulatedOrder {
  orderId: string;
  symbol: string;
  type: "MARKET" | "LIMIT";
  side: "BUY" | "SELL";
  status: "COMPLETE" | "PENDING" | "CANCELLED";
  qty: number;
  price: number;
  timestamp: string;
}

export interface SimulatedTrade {
  tradeId: string;
  symbol: string;
  side: "BUY" | "SELL";
  entry: number;
  exit: number | null;
  pnl: number | null;
  qty: number;
  timestamp: string;
}

export interface SimulatedHolding {
  instrument: string;
  qty: number;
  avgCost: number;
  marketValue: number;
  pnl: number;
}

interface SimulatedDataState {
  positions: SimulatedPosition[];
  orders: SimulatedOrder[];
  trades: SimulatedTrade[];
  holdings: SimulatedHolding[];
  
  // Financial summaries
  realizedPnL: number;
  brokerage: number;

  // Actions
  placeOrder: (params: {
    symbol: string;
    side: "BUY" | "SELL";
    type: "MARKET" | "LIMIT";
    qty: number;
    price: number;
    productType: "MIS" | "NRML" | "CNC";
  }) => void;
  closePosition: (symbol: string) => void;
  updateLTP: (symbol: string, ltp: number) => void;
  resetSimulatedData: () => void;
}

const INITIAL_POSITIONS: SimulatedPosition[] = [
  { symbol: "BANKNIFTY", side: "LONG", qty: 75, avgPrice: 46700.00, ltp: 46772.50, pnl: 5437.50, owner: "System Bot" },
  { symbol: "NIFTY 50", side: "SHORT", qty: 100, avgPrice: 22230.00, ltp: 22217.00, pnl: 1300.00, owner: "Manual" },
];

const INITIAL_HOLDINGS: SimulatedHolding[] = [
  { instrument: "RELIANCE", qty: 50, avgCost: 2420.00, marketValue: 122500.00, pnl: 1500.00 },
  { instrument: "TCS", qty: 20, avgCost: 3850.00, marketValue: 79200.00, pnl: 2200.00 },
  { instrument: "INFOSYS", qty: 40, avgCost: 1450.00, marketValue: 56800.00, pnl: -1200.00 },
];

const INITIAL_ORDERS: SimulatedOrder[] = [
  { orderId: "ORD-98212", symbol: "BANKNIFTY", type: "MARKET", side: "BUY", status: "COMPLETE", qty: 75, price: 46700.00, timestamp: "09:20:45" },
  { orderId: "ORD-98211", symbol: "NIFTY 50", type: "LIMIT", side: "SELL", status: "COMPLETE", qty: 100, price: 22230.00, timestamp: "09:18:12" },
];

const INITIAL_TRADES: SimulatedTrade[] = [
  { tradeId: "TRD-88201", symbol: "BANKNIFTY", side: "BUY", entry: 46700.00, exit: null, pnl: null, qty: 75, timestamp: "09:20:45" },
  { tradeId: "TRD-88200", symbol: "NIFTY 50", side: "SELL", entry: 22230.00, exit: null, pnl: null, qty: 100, timestamp: "09:18:12" },
];

export const useSimulatedDataStore = create<SimulatedDataState>((set, get) => ({
  positions: INITIAL_POSITIONS,
  orders: INITIAL_ORDERS,
  trades: INITIAL_TRADES,
  holdings: INITIAL_HOLDINGS,
  realizedPnL: 8250.00,
  brokerage: 120.00,

  placeOrder: ({ symbol, side, type, qty, price, productType }) => {
    const timestamp = new Date().toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" });
    const orderId = `ORD-${Math.floor(100000 + Math.random() * 900000)}`;
    const tradeId = `TRD-${Math.floor(100000 + Math.random() * 900000)}`;

    const newOrder: SimulatedOrder = {
      orderId,
      symbol,
      type,
      side,
      status: "COMPLETE",
      qty,
      price,
      timestamp,
    };

    const newTrade: SimulatedTrade = {
      tradeId,
      symbol,
      side,
      entry: price,
      exit: null,
      pnl: null,
      qty,
      timestamp,
    };

    set((state) => {
      const updatedOrders = [newOrder, ...state.orders];
      const updatedTrades = [newTrade, ...state.trades];
      
      // Calculate order brokerage charge (flat rate)
      const newBrokerage = state.brokerage + 20.00;

      // Update positions
      let updatedPositions = [...state.positions];
      const existingPosIdx = updatedPositions.findIndex((p) => p.symbol === symbol);

      if (existingPosIdx > -1) {
        const pos = updatedPositions[existingPosIdx];
        
        // If opposite sides, reduce position size (netting off)
        if ((pos.side === "LONG" && side === "SELL") || (pos.side === "SHORT" && side === "BUY")) {
          const qtyDiff = pos.qty - qty;
          
          if (qtyDiff > 0) {
            // Partial squareoff
            const tradePnL = pos.side === "LONG" 
              ? (price - pos.avgPrice) * qty 
              : (pos.avgPrice - price) * qty;

            pos.qty = qtyDiff;
            pos.pnl = pos.side === "LONG"
              ? (pos.ltp - pos.avgPrice) * pos.qty
              : (pos.avgPrice - pos.ltp) * pos.qty;

            return {
              orders: updatedOrders,
              trades: updatedTrades,
              positions: updatedPositions,
              realizedPnL: state.realizedPnL + tradePnL,
              brokerage: newBrokerage
            };
          } else if (qtyDiff === 0) {
            // Full squareoff
            const tradePnL = pos.side === "LONG" 
              ? (price - pos.avgPrice) * qty 
              : (pos.avgPrice - price) * qty;

            updatedPositions = updatedPositions.filter((p) => p.symbol !== symbol);

            return {
              orders: updatedOrders,
              trades: updatedTrades,
              positions: updatedPositions,
              realizedPnL: state.realizedPnL + tradePnL,
              brokerage: newBrokerage
            };
          } else {
            // Position reversed
            const tradePnL = pos.side === "LONG"
              ? (price - pos.avgPrice) * pos.qty
              : (pos.avgPrice - price) * pos.qty;

            pos.side = pos.side === "LONG" ? "SHORT" : "LONG";
            pos.qty = Math.abs(qtyDiff);
            pos.avgPrice = price;
            pos.pnl = 0;

            return {
              orders: updatedOrders,
              trades: updatedTrades,
              positions: updatedPositions,
              realizedPnL: state.realizedPnL + tradePnL,
              brokerage: newBrokerage
            };
          }
        } else {
          // Same side, increase average price
          const totalCost = (pos.avgPrice * pos.qty) + (price * qty);
          pos.qty += qty;
          pos.avgPrice = totalCost / pos.qty;
          pos.pnl = pos.side === "LONG"
            ? (pos.ltp - pos.avgPrice) * pos.qty
            : (pos.avgPrice - pos.ltp) * pos.qty;
        }
      } else {
        // Create new position
        const ltp = price;
        updatedPositions.push({
          symbol,
          side: side === "BUY" ? "LONG" : "SHORT",
          qty,
          avgPrice: price,
          ltp,
          pnl: 0,
          owner: "Manual",
        });
      }

      return {
        orders: updatedOrders,
        trades: updatedTrades,
        positions: updatedPositions,
        brokerage: newBrokerage,
      };
    });
  },

  closePosition: (symbol) => {
    const pos = get().positions.find((p) => p.symbol === symbol);
    if (!pos) return;

    get().placeOrder({
      symbol,
      side: pos.side === "LONG" ? "SELL" : "BUY",
      type: "MARKET",
      qty: pos.qty,
      price: pos.ltp,
      productType: "MIS",
    });
  },

  updateLTP: (symbol, ltp) => {
    set((state) => {
      const updatedPositions = state.positions.map((pos) => {
        if (pos.symbol === symbol) {
          const pnl = pos.side === "LONG"
            ? (ltp - pos.avgPrice) * pos.qty
            : (pos.avgPrice - ltp) * pos.qty;

          return { ...pos, ltp, pnl };
        }
        return pos;
      });

      return { positions: updatedPositions };
    });
  },

  resetSimulatedData: () => {
    set({
      positions: INITIAL_POSITIONS,
      orders: INITIAL_ORDERS,
      trades: INITIAL_TRADES,
      holdings: INITIAL_HOLDINGS,
      realizedPnL: 8250.00,
      brokerage: 120.00,
    });
  },
}));
