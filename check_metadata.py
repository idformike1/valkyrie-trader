import math

def normal_cdf(x):
    a1 =  0.254829592
    a2 = -0.284496736
    a3 =  1.421413741
    a4 = -1.453152027
    a5 =  1.061405429
    p  =  0.3275911
    sign = 1
    if x < 0:
        sign = -1
    x = abs(x) / math.sqrt(2.0)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return 0.5 * (1.0 + sign * y)

def black_scholes_premium(spot: float, strike: float, days_to_expiry: float, option_type: str, iv: float = 0.15, r: float = 0.07) -> float:
    T = max(days_to_expiry, 0.0001) / 365.0
    d1 = (math.log(spot / strike) + (r + 0.5 * iv ** 2) * T) / (iv * math.sqrt(T))
    d2 = d1 - iv * math.sqrt(T)
    if option_type.upper() == "CE":
        premium = spot * normal_cdf(d1) - strike * math.exp(-r * T) * normal_cdf(d2)
    else:
        premium = strike * math.exp(-r * T) * normal_cdf(-d2) - spot * normal_cdf(-d1)
    return max(premium, 0.5)

def run():
    # ATM Call option with 7 days to expiry
    ce_prem = black_scholes_premium(25000.0, 25000.0, 7.0, "CE")
    pe_prem = black_scholes_premium(25000.0, 25000.0, 7.0, "PE")
    print(f"ATM 7d CE Premium: {ce_prem:.2f}")
    print(f"ATM 7d PE Premium: {pe_prem:.2f}")
    
    # ITM / OTM
    ce_itm = black_scholes_premium(25200.0, 25000.0, 7.0, "CE")
    ce_otm = black_scholes_premium(24800.0, 25000.0, 7.0, "CE")
    print(f"ITM 7d CE (+200): {ce_itm:.2f}")
    print(f"OTM 7d CE (-200): {ce_otm:.2f}")

if __name__ == "__main__":
    run()
