# Valkyrie V2 Historical Contract Master Verification Report
Generated on: 2026-05-30T08:40:20.540273

## TEST 1: EXPIRY CALENDAR RESOLUTION
- **Discovered Expiries Count**: 105
- **First 5 Expiries**: ['2025-01-02', '2025-01-09', '2025-01-16', '2025-01-23', '2025-01-30']
- **Latency**: 272.51 ms
- **Verification**: Verified discovery of historical expiries from provider.
- **Reference Date**: 2025-04-15 (Tuesday)
- **Resolved CURRENT_WEEKLY**: 2025-04-17 (Expected: 2025-04-17)
- **Resolved NEXT_WEEKLY**: 2025-04-24 (Expected: 2025-04-24)

## TEST 2: HISTORICAL SPOT & STRIKE RESOLUTION
- **Historical Spot at 10:00**: 23316.75
- **Resolved ATM Strike**: 23300.0 (Expected: 23300.0)

## TEST 3: CONTRACT RESOLUTION (CACHE MISS FLOW)
- **Resolved Instrument Key**: NSE_FO|6680388
- **Cache Miss Resolution Latency**: 169.38 ms
- **Verification**: Verified cache miss triggers contract discovery and persistence.

## TEST 4: CONTRACT RESOLUTION (CACHE HIT FLOW)
- **Resolved Instrument Key**: NSE_FO|6680388
- **Cache Hit Resolution Latency**: 0.9131 ms
- **Verification**: Verification of O(1) database lookups on cache hit.

## TEST 5: SQLITE PERSISTENCE AUDIT
| Underlying | Expiry Date | Strike | Type | Instrument Key | Source | Discovered At |
| --- | --- | --- | --- | --- | --- | --- |
| NIFTY | 2025-04-17 | 21750.0 | CE | NSE_FO|10028646 | FALLBACK_API | 2026-05-30T08:40:20.985075 |
| NIFTY | 2025-04-17 | 21750.0 | PE | NSE_FO|15640542 | FALLBACK_API | 2026-05-30T08:40:20.985075 |
| NIFTY | 2025-04-17 | 21800.0 | CE | NSE_FO|9224736 | FALLBACK_API | 2026-05-30T08:40:20.985075 |
| NIFTY | 2025-04-17 | 21800.0 | PE | NSE_FO|8193490 | FALLBACK_API | 2026-05-30T08:40:20.985075 |
| NIFTY | 2025-04-17 | 21850.0 | CE | NSE_FO|1124589 | FALLBACK_API | 2026-05-30T08:40:20.985075 |

- **Verification**: Verified records are correctly saved and queryable from SQL schema.