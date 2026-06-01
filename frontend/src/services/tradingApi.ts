import { BuyOrderRequest, GttOrderRequest, TelemetryPayload, StartBacktestRequest } from "./tradingTypes";

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8081";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });

  if (!response.ok) {
    const errorText = await response.text();
    let errorMessage = "Request failed";
    try {
      const parsed = JSON.parse(errorText);
      errorMessage = parsed.detail || parsed.message || errorMessage;
    } catch {
      errorMessage = errorText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json() as Promise<T>;
}

export const tradingApi = {
  getTelemetry: () => request<TelemetryPayload>("/telemetry"),
  
  manualBuy: (payload: BuyOrderRequest) =>
    request<{ message: string; status: any }>("/manual/buy", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  manualSell: () =>
    request<{ message: string; status: any }>("/manual/sell", {
      method: "POST",
    }),

  manualPanicExit: () =>
    request<{ message: string; status: any }>("/manual/panic_exit", {
      method: "POST",
    }),

  createGtt: (payload: GttOrderRequest) =>
    request<{ message: string; gtt_order: any }>("/manual/gtt/create", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  cancelGtt: (id: string) =>
    request<{ message: string }>("/manual/gtt/cancel", {
      method: "POST",
      body: JSON.stringify({ id }),
    }),

  startBacktest: (payload: StartBacktestRequest) =>
    request<{ message: string; status: any }>("/start", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getBrokerProfile: () => request<any>("/api/broker/profile"),
  getBrokerFunds: () => request<any>("/api/broker/funds"),
  getBrokerPositions: () => request<any>("/api/broker/positions"),
  getBrokerOrders: () => request<any>("/api/broker/orders"),
  getBrokerTrades: () => request<any>("/api/broker/trades"),
  getBrokerHoldings: () => request<any>("/api/broker/holdings"),
  getBrokerMargin: (payload: { instrument_key: string; quantity: number; transaction_type: string; product: string }) =>
    request<any>("/api/broker/margin", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getBrokerQuotes: (instrumentKey: string) =>
    request<any>(`/api/broker/quotes?instrument_key=${encodeURIComponent(instrumentKey)}`),

  getBrokerCandles: (instrumentKey: string, timeframe = "1m", days = 3) =>
    request<any>(`/api/broker/candles?instrument_key=${encodeURIComponent(instrumentKey)}&timeframe=${timeframe}&days=${days}`),

  getBrokerInstrumentInfo: (instrumentKey: string) =>
    request<any>(`/api/broker/instrument_info?instrument_key=${encodeURIComponent(instrumentKey)}`),


  placeBrokerOrder: (payload: {
    instrument_key: string;
    quantity: number;
    transaction_type: "BUY" | "SELL";
    order_type: "MARKET" | "LIMIT";
    product: string;
    price?: number;
    trigger_price?: number;
  }) =>
    request<any>("/api/broker/place_order", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
