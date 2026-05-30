# Upstox Expired Instruments API Review

This document audits and details the Upstox v2 Expired Instruments API capabilities, required parameters, rate limits, schema details, and authorization constraints.

---

## 1. API Availability & Plan Requirements

Access to the **Expired Instruments API suite** is restricted to accounts with the **Upstox Plus** plan.
*   **Without Upstox Plus**: API calls fail with status code `401 Unauthorized` and error code `UDAPI1149`.
*   **Historical Candle Retrieval**: Interestingly, retrieving historical OHLC candles for expired option contracts using the **Standard Historical Candle API** (`/v2/historical-candle/{instrumentKey}/...`) does **not** require the Plus plan. Standard API usage is open to all tiers if the user knows the exact, active `instrument_key`.

---

## 2. API Endpoint Directory

All expired instruments endpoints use the base path `https://api.upstox.com/v2/expired-instruments`.

### A. Get Expiries
*   **Path**: `GET /v2/expired-instruments/expiries`
*   **Description**: Retrieves a list of all historical/expired expiry dates for a given underlying instrument.
*   **Query Parameters**:
    *   `instrument_key` (string, Required): Unique identifier of the underlying index or stock (e.g., `NSE_INDEX|Nifty 50`).
*   **Response Schema**:
    ```json
    {
      "status": "success",
      "data": [
        "2025-04-17",
        "2025-04-24",
        "2025-05-08"
      ]
    }
    ```

### B. Get Expired Option Contracts
*   **Path**: `GET /v2/expired-instruments/option/contract`
*   **Description**: Retrieves detailed contract specification details for option contracts that expired on a specific date.
*   **Query Parameters**:
    *   `instrument_key` (string, Required): Underlying index key (e.g., `NSE_INDEX|Nifty 50`).
    *   `expiry_date` (string, Required): The exact expiry date in `YYYY-MM-DD` format (e.g., `2025-04-17`).
*   **Response Schema**:
    ```json
    {
      "status": "success",
      "data": [
        {
          "name": "NIFTY",
          "segment": "NSE_FO",
          "exchange": "NSE",
          "expiry": "2025-04-17",
          "instrument_key": "NSE_FO|50973",
          "exchange_token": "50973",
          "trading_symbol": "NIFTY25APR23300CE",
          "tick_size": 0.05,
          "lot_size": 75,
          "instrument_type": "CE",
          "strike_price": 23300.0,
          "underlying_key": "NSE_INDEX|Nifty 50",
          "weekly": true
        }
      ]
    }
    ```

### C. Get Expired Historical Candle Data
*   **Path**: `GET /v2/expired-instruments/historical-candle/{expired_instrument_key}/{interval}/{to_date}/{from_date}`
*   **Description**: Fetches historical OHLC candle data for expired contracts.
*   **Path Parameters**:
    *   `expired_instrument_key` (string, Required): The key format is identical to standard active key formats (e.g. `NSE_FO|50973`).
    *   `interval` (string, Required): Timeframe (e.g., `1minute`, `30minute`).
    *   `to_date` / `from_date` (string, Required): Date format `YYYY-MM-DD`.

---

## 3. Rate Limits & Headers

*   **Authorization Header**: `Authorization: Bearer {access_token}`
*   **Accept Header**: `Accept: application/json`
*   **Rate Limits**: Expired Instruments APIs follow standard Upstox API limit allocations (typically **120 requests/minute** per endpoint).

---

## 4. Error Code Summary

| Error Code | HTTP Status | Description |
| :--- | :--- | :--- |
| `UDAPI1149` | 401 Unauthorized | API is available exclusively with an Upstox Plus plan subscription. |
| `UDAPI100011` | 400 Bad Request | Invalid instrument key or parameters. |
| `UDAPI100012` | 404 Not Found | Data not found for requested date range or contract. |
