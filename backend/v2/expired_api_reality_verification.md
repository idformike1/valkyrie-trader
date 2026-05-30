# Valkyrie V2 Upstox Expired API Reality Verification Report
Generated on: 2026-05-30T08:52:24.099826
Token Generation Timestamp (IST): 2026-05-30 08:45:39

## TEST 1: PLUS ENTITLEMENT CHECK
- **HTTP Status**: 200
- **Latency**: 220.30 ms
- **Response Status**: Success
- **Raw Response Snippet (First 100 chars)**:
```json
{"status": "success", "data": ["2024-10-03", "2024-10-10", "2024-10-17", "2024-10-24", "2024-10-31", "2024-11-07", "2024-11-14", "2024-11-21", "2024-11-28", "2024-12-05", "2024-12-12", "2024-12-19", "2024-12-26", "2025-01-02", "2025-01-09", "2025-01-...
```
- **Status**: PASS

## TEST 2: EXPIRED EXPIRY DISCOVERY
| Underlying | Expiries Returned | Earliest Expiry | Latest Expiry | Source |
| --- | --- | --- | --- | --- |
| NIFTY | 87 | 2024-10-03 | 2026-05-26 | UPSTOX_EXPIRED_API |
| BANKNIFTY | 26 | 2024-10-01 | 2026-05-26 | UPSTOX_EXPIRED_API |
| FINNIFTY | 27 | 2024-10-01 | 2026-05-26 | UPSTOX_EXPIRED_API |
| MIDCPNIFTY | 27 | 2024-09-30 | 2026-05-26 | UPSTOX_EXPIRED_API |
| SENSEX | 86 | 2024-10-04 | 2026-05-27 | UPSTOX_EXPIRED_API |
| BANKEX | 27 | 2024-09-30 | 2026-05-27 | UPSTOX_EXPIRED_API |

- **Status**: PASS

## TEST 3: HISTORICAL CONTRACT DISCOVERY
- **HTTP Status**: 200
- **API Latency**: 157.23 ms
- **Raw API Response Snippet (First 500 chars)**:
```json
{"status": "success", "data": [{"name": "NIFTY", "segment": "NSE_FO", "exchange": "NSE", "expiry": "2025-04-17", "weekly": true, "instrument_key": "NSE_FO|47983|17-04-2025", "exchange_token": "47983", "trading_symbol": "NIFTY 20400 PE 17 APR 25", "tick_size": 5.0, "lot_size": 75, "instrument_type": "PE", "freeze_quantity": 1800.0, "underlying_key": "NSE_INDEX|Nifty 50", "underlying_type": "INDEX", "underlying_symbol": "NIFTY", "strike_price": 20400.0, "minimum_lot": 75}, {"name": "NIFTY", "segme...
```
- **Status**: PASS

## TEST 4: ATM CONTRACT RESOLUTION
- **Historical Spot (10:00)**: 23316.75
- **Resolved ATM Strike**: 23300.0
- **Resolved Expiry**: 2025-04-17
- **Option Type**: CE
- **Resolved Instrument Key**: NSE_FO|48236|17-04-2025
- **Source Field in Cache**: UPSTOX_EXPIRED_API
- **Status**: PASS

## TEST 5: REAL PREMIUM CANDLE DOWNLOAD
- **Total Rows Downloaded**: 375
- **API Download Latency**: 9627.61 ms

### First 10 Candles:
| Timestamp | Open | High | Low | Close | Volume |
| --- | --- | --- | --- | --- | --- |
| 2025-04-15T09:15:00 | 175.00 | 194.50 | 142.00 | 154.00 | 2166450 |
| 2025-04-15T09:16:00 | 159.69 | 159.69 | 139.50 | 142.65 | 1572600 |
| 2025-04-15T09:17:00 | 144.69 | 153.30 | 144.69 | 148.19 | 1169475 |
| 2025-04-15T09:18:00 | 147.80 | 150.10 | 145.44 | 145.60 | 939525 |
| 2025-04-15T09:19:00 | 145.30 | 148.90 | 143.60 | 143.60 | 796125 |
| 2025-04-15T09:20:00 | 145.05 | 157.19 | 144.75 | 153.30 | 1476525 |
| 2025-04-15T09:21:00 | 153.00 | 155.90 | 149.50 | 149.50 | 1236300 |
| 2025-04-15T09:22:00 | 149.85 | 153.00 | 147.30 | 151.80 | 817125 |
| 2025-04-15T09:23:00 | 151.44 | 152.80 | 146.60 | 146.60 | 724725 |
| 2025-04-15T09:24:00 | 146.75 | 151.10 | 146.35 | 147.65 | 793575 |

### Last 10 Candles:
| Timestamp | Open | High | Low | Close | Volume |
| --- | --- | --- | --- | --- | --- |
| 2025-04-15T15:20:00 | 102.00 | 105.90 | 102.00 | 105.85 | 1124325 |
| 2025-04-15T15:21:00 | 106.00 | 108.05 | 105.35 | 107.95 | 968175 |
| 2025-04-15T15:22:00 | 106.95 | 108.20 | 105.90 | 106.90 | 717675 |
| 2025-04-15T15:23:00 | 106.70 | 107.15 | 103.80 | 107.10 | 702300 |
| 2025-04-15T15:24:00 | 107.35 | 107.85 | 104.55 | 107.70 | 565725 |
| 2025-04-15T15:25:00 | 108.30 | 110.60 | 107.85 | 110.40 | 1183650 |
| 2025-04-15T15:26:00 | 110.40 | 112.65 | 110.40 | 112.65 | 606375 |
| 2025-04-15T15:27:00 | 112.85 | 112.85 | 107.75 | 108.85 | 702375 |
| 2025-04-15T15:28:00 | 108.85 | 110.75 | 107.05 | 110.45 | 721575 |
| 2025-04-15T15:29:00 | 110.95 | 111.25 | 110.00 | 110.60 | 1073925 |

- **Status**: PASS

## TEST 6: CACHE POPULATION
| Underlying | Expiry | Strike | Type | Instrument Key | Source |
| --- | --- | --- | --- | --- | --- |
| NIFTY | 2025-04-17 | 20400.0 | PE | NSE_FO|47983|17-04-2025 | UPSTOX_EXPIRED_API |
| NIFTY | 2025-04-17 | 20400.0 | CE | NSE_FO|47982|17-04-2025 | UPSTOX_EXPIRED_API |
| NIFTY | 2025-04-17 | 20450.0 | PE | NSE_FO|47990|17-04-2025 | UPSTOX_EXPIRED_API |
| NIFTY | 2025-04-17 | 20450.0 | CE | NSE_FO|47988|17-04-2025 | UPSTOX_EXPIRED_API |
| NIFTY | 2025-04-17 | 20500.0 | PE | NSE_FO|47995|17-04-2025 | UPSTOX_EXPIRED_API |
| NIFTY | 2025-04-17 | 20500.0 | CE | NSE_FO|47994|17-04-2025 | UPSTOX_EXPIRED_API |
| NIFTY | 2025-04-17 | 20550.0 | PE | NSE_FO|47997|17-04-2025 | UPSTOX_EXPIRED_API |
| NIFTY | 2025-04-17 | 20550.0 | CE | NSE_FO|47996|17-04-2025 | UPSTOX_EXPIRED_API |
| NIFTY | 2025-04-17 | 20600.0 | PE | NSE_FO|48015|17-04-2025 | UPSTOX_EXPIRED_API |
| NIFTY | 2025-04-17 | 20600.0 | CE | NSE_FO|47998|17-04-2025 | UPSTOX_EXPIRED_API |

- **Status**: PASS

## TEST 7: CACHE HIT TEST
- **Resolved Instrument Key**: NSE_FO|48236|17-04-2025
- **Cache Hit Latency**: 1.1050 ms
- **Cache Hit**: True
- **Status**: PASS

## TEST 8: MULTIPLE CONTRACT TEST
| Mode | Resolved Strike | Type | Instrument Key | Source |
| --- | --- | --- | --- | --- |
| ATM CE | 23300.0 | CE | NSE_FO|48236|17-04-2025 | UPSTOX_EXPIRED_API |
| ATM PE | 23300.0 | PE | NSE_FO|48237|17-04-2025 | UPSTOX_EXPIRED_API |
| OTM_1 CE | 23350.0 | CE | NSE_FO|48241|17-04-2025 | UPSTOX_EXPIRED_API |
| OTM_1 PE | 23250.0 | PE | NSE_FO|48235|17-04-2025 | UPSTOX_EXPIRED_API |
| ITM_1 CE | 23250.0 | CE | NSE_FO|48234|17-04-2025 | UPSTOX_EXPIRED_API |
| ITM_1 PE | 23350.0 | PE | NSE_FO|48247|17-04-2025 | UPSTOX_EXPIRED_API |

- **Status**: PASS

## TEST 9: ANTI-FALLBACK TEST
- **Fallback Contract Generator Calls**: 0
- **Fallback Expiry Generator Calls**: 0
- **Status**: PASS

## TEST 10: ANTI-CSV TEST
- **Legacy CSV Cache Preload Calls**: 0
- **Legacy CSV Cache Lookup Calls**: 0
- **Status**: PASS

## FINAL VALIDATION MATRIX
| Verification Item | Status |
| --- | --- |
| **PLUS Access** | **PASS** |
| **Expired Expiries API** | **PASS** |
| **Expired Contracts API** | **PASS** |
| **Expired Candle API** | **PASS** |
| **Historical Contracts** | **PASS** |
| **Historical Premiums** | **PASS** |
| **SQLite Cache** | **PASS** |
| **Fallback Removal** | **PASS** |
| **CSV Independence** | **PASS** |

### Conclusion: PASS