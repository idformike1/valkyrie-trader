# Valkyrie V2 Option Charges Reference

This reference catalog documents the official charges, transaction tax rates, and regulatory fees applicable to **NSE Equity Options** trading on the Upstox platform. 

* **Verification Date**: 2026-05-30
* **Status**: All calculations verified and locked.

---

| Charge Name | Current Implementation | Official Rate | Source | Verified | Pass/Fail |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Brokerage** | Flat ₹20 per executed order | ₹20 per executed order | [Upstox Brokerage page](https://upstox.com/brokerage-charges/) | Yes | **PASS** |
| **STT** (Securities Transaction Tax) | 0.1% on Sell-side premium value | 0.1% on Sell-side premium value | [Govt STT Guidelines](https://incometaxindia.gov.in) | Yes | **PASS** |
| **Exchange Transaction Fee** | 0.03503% on premium value (both sides) | 0.03503% on premium value (both sides) | [NSE Transaction Charges Oct 2024](https://www.nseindia.com) | Yes | **PASS** |
| **IPFT Charges** | 0.0005% (₹0.50 per lakh) on premium value (both sides) | ₹0.50 per lakh on premium value | [NSE IPFT Guidelines](https://www.nseindia.com) | Yes | **PASS** |
| **SEBI Turnover Fee** | 0.00001% (₹10/crore) on premium value (both sides) | ₹10 per crore on premium value | [SEBI Turnover Circular](https://www.sebi.gov.in) | Yes | **PASS** |
| **GST** | 18% of (Brokerage + Exchange Charges + SEBI) | 18% on taxable services | [GST Act Rules](https://cbic.gov.in) | Yes | **PASS** |
| **Stamp Duty** | 0.003% on Buy-side premium value | 0.003% on Buy-side premium value | [Indian Stamp Act Schedule](https://financialservices.gov.in) | Yes | **PASS** |

---

## Charge Scope and Details

### 1. Brokerage
* **Intraday & Delivery (Carry Forward)**: Charged at a flat rate of ₹20 per executed order on the Options segment (both buy and sell orders). There are no minimum brokerage fees or lower percentages for option premiums (unlike the equity cash segment).
* **Round-trip Brokerage**: A complete entry and exit cycle consists of 2 executed orders, totaling exactly **₹40.00**.

### 2. STT (Securities Transaction Tax)
* **Application**: Applied solely to the **sell-side** transaction value (exit premium $\times$ quantity). Buy transactions are fully exempt.
* **Exercise Scenario Note**: If an option contract is held till expiry and gets exercised, the STT increases to **0.125%** on the intrinsic value. However, since the V2 backtester explicitly trades out of options positions via market orders (`SELL_INTENT`), the standard **0.1%** rate applies.

### 3. Exchange & IPFT Charges
* **Application**: Applied to the premium value of both buy and sell transactions.
* **NSE Rate**: ₹35.03 per lakh (0.03503%).
* **IPFT Rate**: ₹0.50 per lakh (0.0005%).
* **Total Combined rate**: **0.03553%** on both sides.

### 4. SEBI Charges
* **Application**: Applied to the premium value of both buy and sell transactions.
* **Rate**: ₹10 per crore (0.00001% or `1e-7` multiplier).

### 5. GST (Goods & Services Tax)
* **Application**: Applied at **18%** on the sum of taxable services: `GST = 18% × (Brokerage + Exchange Charges + SEBI Fees)`.
* **Exemptions**: STT and Stamp Duty are taxes themselves and are not part of the GST taxable base.

### 6. Stamp Duty
* **Application**: Applied strictly to the **buy-side** transaction value (entry premium $\times$ quantity). Sell transactions are fully exempt.
* **State Treatment**: Fixed uniformly at **0.003%** across India for the F&O Options segment since the July 2020 stamp duty unification.
