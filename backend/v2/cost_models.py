import abc
from typing import Dict, Any
from v2.position_models import Position
from v2.pnl_models import TradeCharges

class CostModel(abc.ABC):
    @abc.abstractmethod
    def calculate_charges(self, position: Position) -> TradeCharges:
        """
        Calculates all charges and taxes for a given closed position.
        """
        pass

    @abc.abstractmethod
    def calculate_brokerage(self, position: Position) -> float:
        """
        Calculates brokerage for both entry and exit.
        """
        pass

    @abc.abstractmethod
    def calculate_taxes(self, position: Position) -> Dict[str, float]:
        """
        Calculates individual taxes and statutory fees (STT, Transaction charges, GST, SEBI, Stamp Duty).
        """
        pass

class UpstoxCostModel(CostModel):
    """
    Upstox official NSE F&O Equity Option fee structure:
    - Brokerage: Flat ₹20 per executed order (Entry & Exit = ₹40 total).
    - STT (Securities Transaction Tax): 0.1% on the sell-side premium.
    - Exchange Transaction Charges: 0.03503% NSE transaction fee + 0.0005% IPFT fee (total 0.03553% on premium).
    - SEBI Turnover Fees: ₹10 per crore of premium (0.00001% of premium turnover on both sides).
    - Stamp Duty: 0.003% on buy-side premium.
    - GST: 18% of (Brokerage + Exchange Charges + SEBI charges).
    
    Verified Date: 2026-05-30
    """
    BROKERAGE_PER_ORDER = 20.0
    
    STT_RATE = 0.001                # 0.1% on sell-side premium
    EXCHANGE_TRANS_RATE = 0.0003503  # NSE Transaction fee: 0.03503% of premium
    EXCHANGE_IPFT_RATE = 0.000005    # NSE IPFT fee: 0.0005% of premium (₹0.50 per lakh)
    SEBI_TURNOVER_RATE = 0.0000001   # SEBI turnover fee: ₹10 per crore of premium (0.00001%)
    STAMP_DUTY_RATE = 0.00003        # Stamp duty: 0.003% on buy-side premium
    GST_RATE = 0.18                  # GST: 18% on (brokerage + exchange charges + sebi charges)

    def calculate_brokerage(self, position: Position) -> float:
        # A completed (closed) position has exactly 2 orders (entry and exit)
        return round(self.BROKERAGE_PER_ORDER * 2.0, 2)

    def calculate_taxes(self, position: Position) -> Dict[str, float]:
        if position.exit_premium is None:
            raise ValueError(
                f"Position {position.position_id} is not closed. "
                "exit_premium is required for charges calculation."
            )
            
        qty = position.quantity
        entry_value = position.entry_premium * qty
        exit_value = position.exit_premium * qty
        
        # 1. Securities Transaction Tax (STT) - 0.1% on Sell premium
        stt = round(exit_value * self.STT_RATE, 2)
        
        # 2. Exchange Charges (NSE transaction fee + IPFT)
        total_exchange_rate = self.EXCHANGE_TRANS_RATE + self.EXCHANGE_IPFT_RATE
        exchange_charges = round((entry_value * total_exchange_rate) + (exit_value * total_exchange_rate), 2)
        
        # 3. SEBI turnover fee - ₹10 per crore of premium on both buy/sell
        sebi_charges = round((entry_value * self.SEBI_TURNOVER_RATE) + (exit_value * self.SEBI_TURNOVER_RATE), 2)
        
        # 4. Stamp duty - 0.003% on buy premium
        stamp_duty = round(entry_value * self.STAMP_DUTY_RATE, 2)
        
        # 5. GST - 18% on (Brokerage + Exchange Charges + SEBI charges)
        brokerage = self.calculate_brokerage(position)
        gst_base = brokerage + exchange_charges + sebi_charges
        gst = round(gst_base * self.GST_RATE, 2)
        
        return {
            "stt": stt,
            "exchange_charges": exchange_charges,
            "sebi_charges": sebi_charges,
            "stamp_duty": stamp_duty,
            "gst": gst
        }

    def calculate_charges(self, position: Position) -> TradeCharges:
        brokerage = self.calculate_brokerage(position)
        taxes = self.calculate_taxes(position)
        
        total_charges = round(
            brokerage + 
            taxes["stt"] + 
            taxes["exchange_charges"] + 
            taxes["sebi_charges"] + 
            taxes["gst"] + 
            taxes["stamp_duty"], 
            2
        )
        
        return TradeCharges(
            brokerage=brokerage,
            stt=taxes["stt"],
            exchange_charges=taxes["exchange_charges"],
            sebi_charges=taxes["sebi_charges"],
            gst=taxes["gst"],
            stamp_duty=taxes["stamp_duty"],
            other_charges=0.0,
            total_charges=total_charges
        )
