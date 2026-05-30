# Accounting Model Freeze

* **Version**: `ACCOUNTING_MODEL_V1`
* **Verification Date**: 2026-05-30
* **Approval Status**: **APPROVED & FROZEN**

---

## Locked Rates & Multipliers

The following parameters are hardcoded and frozen under `ACCOUNTING_MODEL_V1` within the `UpstoxCostModel` class:

| Parameter | Multiplier / Value | Description |
| :--- | :--- | :--- |
| `BROKERAGE_PER_ORDER` | `20.0` | Fixed brokerage fee in INR per order |
| `STT_RATE` | `0.001` | Securities Transaction Tax (0.1% on Sell premium) |
| `EXCHANGE_TRANS_RATE` | `0.0003503` | NSE Transaction fee (0.03503% on premium) |
| `EXCHANGE_IPFT_RATE` | `0.000005` | NSE IPFT fee (0.0005% on premium) |
| `SEBI_TURNOVER_RATE` | `0.0000001` | SEBI turnover fee (₹10/crore on premium) |
| `STAMP_DUTY_RATE` | `0.00003` | Government Stamp Duty (0.003% on Buy premium) |
| `GST_RATE` | `0.18` | Goods & Services Tax (18% on Brokerage + Exchange + SEBI) |

---

## Source References
1. **Upstox Brokerage Rates**: [Upstox F&O Pricing Guide](https://upstox.com/brokerage-charges/)
2. **NSE Transaction & IPFT Charges**: [NSE India F&O Transaction Charges Table](https://www.nseindia.com)
3. **SEBI Fees Circular**: [SEBI Fee Schedule Circular](https://www.sebi.gov.in)
4. **Unified Stamp Duty Schedule**: [Department of Financial Services, Ministry of Finance (Stamp Duty Rules)](https://financialservices.gov.in)
5. **GST Rate Rules**: [Central Board of Indirect Taxes and Customs (CBIC)](https://cbic.gov.in)
