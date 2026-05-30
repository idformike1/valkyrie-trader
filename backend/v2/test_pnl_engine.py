import unittest
from datetime import datetime, timedelta
from typing import Dict, Any

from v2.position_models import Position, PositionStatus
from v2.pnl_models import TradeCharges, TradePnL, TradeAccountingResult, BacktestAccountingResult
from v2.cost_models import CostModel, UpstoxCostModel
from v2.pnl_engine import PnLEngine

class TestPnLEngine(unittest.TestCase):

    def setUp(self):
        self.cost_model = UpstoxCostModel()
        self.pnl_engine = PnLEngine(cost_model=self.cost_model)
        self.sample_time = datetime(2025, 4, 15, 9, 30)
        
        # Helper to create a closed position
        self.closed_pos = Position(
            position_id="pos-test-123",
            status=PositionStatus.CLOSED,
            underlying="NIFTY",
            strike=23300.0,
            expiry="2025-04-17",
            option_type="CE",
            instrument_key="NSE_FO|48236|17-04-2025",
            entry_time=self.sample_time,
            entry_premium=133.60,
            quantity=75,
            lot_size=75,
            entry_value=133.60 * 75,
            exit_time=self.sample_time + timedelta(minutes=20),
            exit_premium=134.60,
            exit_value=134.60 * 75,
            broker="Upstox",
            entry_signal="BUY_INTENT"
        )

    # 1. Gross PnL Positive Trade
    def test_gross_pnl_positive(self):
        pos = self.closed_pos.model_copy(update={"entry_premium": 100.0, "exit_premium": 110.0, "quantity": 75})
        gross = self.pnl_engine.calculate_gross_pnl(pos)
        self.assertEqual(gross, 750.0)

    # 2. Gross PnL Negative Trade
    def test_gross_pnl_negative(self):
        pos = self.closed_pos.model_copy(update={"entry_premium": 100.0, "exit_premium": 90.0, "quantity": 75})
        gross = self.pnl_engine.calculate_gross_pnl(pos)
        self.assertEqual(gross, -750.0)

    # 3. Gross PnL Break-even Trade
    def test_gross_pnl_breakeven(self):
        pos = self.closed_pos.model_copy(update={"entry_premium": 100.0, "exit_premium": 100.0, "quantity": 75})
        gross = self.pnl_engine.calculate_gross_pnl(pos)
        self.assertEqual(gross, 0.0)

    # 4. Gross PnL Large Premium Move
    def test_gross_pnl_large_premium_move(self):
        pos = self.closed_pos.model_copy(update={"entry_premium": 10.0, "exit_premium": 850.0, "quantity": 75})
        gross = self.pnl_engine.calculate_gross_pnl(pos)
        self.assertEqual(gross, 63000.0)

    # 5. Upstox Brokerage is Fixed at ₹40
    def test_upstox_brokerage_is_fixed(self):
        brokerage = self.cost_model.calculate_brokerage(self.closed_pos)
        self.assertEqual(brokerage, 40.0)

    # 6. Upstox STT Calculation (0.1% on Sell premium value)
    def test_upstox_stt_calculation(self):
        # Exit premium = 134.60, Qty = 75. Exit value = 10095.0. STT = 10095.0 * 0.001 = 10.095 -> rounded to 10.10
        taxes = self.cost_model.calculate_taxes(self.closed_pos)
        self.assertEqual(taxes["stt"], 10.10)

    # 7. Upstox Exchange Transaction Charges Calculation (0.03553% on both Buy/Sell value)
    def test_upstox_exchange_charges_calculation(self):
        # Buy: 133.60 * 75 = 10020.0. Sell: 134.60 * 75 = 10095.0. Total = 20115.0
        # Charges = 20115.0 * 0.0003553 = 7.14686 -> rounded to 7.15
        taxes = self.cost_model.calculate_taxes(self.closed_pos)
        self.assertEqual(taxes["exchange_charges"], 7.15)

    # 8. Upstox SEBI Charges Calculation (₹10 per crore = 1e-7 of premium turnover on both sides)
    def test_upstox_sebi_charges_calculation(self):
        # Total Turnover = 20115.0. Charges = 20115.0 * 1e-7 = 0.0020115 -> rounded to 0.00
        taxes = self.cost_model.calculate_taxes(self.closed_pos)
        self.assertEqual(taxes["sebi_charges"], 0.00)

    # 9. Upstox Stamp Duty Calculation (0.003% on Buy side premium value)
    def test_upstox_stamp_duty_calculation(self):
        # Buy: 10020.0. Stamp Duty = 10020.0 * 0.00003 = 0.3006 -> rounded to 0.30
        taxes = self.cost_model.calculate_taxes(self.closed_pos)
        self.assertEqual(taxes["stamp_duty"], 0.30)

    # 10. Upstox GST Calculation (18% of Brokerage + Exchange charges + SEBI charges)
    def test_upstox_gst_calculation(self):
        # Brokerage = 40.0, Exchange = 7.15, SEBI = 0.00. Base = 47.15. GST = 47.15 * 0.18 = 8.487 -> rounded to 8.49
        taxes = self.cost_model.calculate_taxes(self.closed_pos)
        self.assertEqual(taxes["gst"], 8.49)

    # 11. Upstox Total Charges Sum
    def test_upstox_total_charges_sum(self):
        charges = self.cost_model.calculate_charges(self.closed_pos)
        expected = round(
            charges.brokerage +
            charges.stt +
            charges.exchange_charges +
            charges.sebi_charges +
            charges.gst +
            charges.stamp_duty,
            2
        )
        self.assertEqual(charges.total_charges, expected)

    # 12. Calculate Charges Throws for Open Position
    def test_calculate_charges_throws_for_open_position(self):
        open_pos = self.closed_pos.model_copy(update={"status": PositionStatus.LONG, "exit_premium": None})
        with self.assertRaises(ValueError):
            self.cost_model.calculate_charges(open_pos)

    # 13. PnLEngine Positive Trade Accounting
    def test_pnl_engine_positive_trade_accounting(self):
        pos = self.closed_pos.model_copy(update={"entry_premium": 100.0, "exit_premium": 110.0, "quantity": 75})
        acc = self.pnl_engine.account_trade(pos)
        self.assertEqual(acc.gross_pnl, 750.0)
        self.assertEqual(acc.charges.brokerage, 40.0)
        self.assertEqual(acc.net_pnl, round(750.0 - acc.charges.total_charges, 2))

    # 14. PnLEngine Negative Trade Accounting
    def test_pnl_engine_negative_trade_accounting(self):
        pos = self.closed_pos.model_copy(update={"entry_premium": 100.0, "exit_premium": 90.0, "quantity": 75})
        acc = self.pnl_engine.account_trade(pos)
        self.assertEqual(acc.gross_pnl, -750.0)
        self.assertEqual(acc.net_pnl, round(-750.0 - acc.charges.total_charges, 2))

    # 15. PnLEngine Break-even Trade Accounting
    def test_pnl_engine_breakeven_trade_accounting(self):
        pos = self.closed_pos.model_copy(update={"entry_premium": 100.0, "exit_premium": 100.0, "quantity": 75})
        acc = self.pnl_engine.account_trade(pos)
        self.assertEqual(acc.gross_pnl, 0.0)
        # Net pnl must be negative because of charges
        self.assertLess(acc.net_pnl, 0.0)
        self.assertEqual(acc.net_pnl, -acc.charges.total_charges)

    # 16. NIFTY Lots Accounting
    def test_nifty_lot_size_accounting(self):
        pos = self.closed_pos.model_copy(update={"underlying": "NIFTY", "lot_size": 75, "quantity": 150})
        acc = self.pnl_engine.account_trade(pos)
        self.assertEqual(acc.quantity, 150)
        self.assertEqual(acc.gross_pnl, round((pos.exit_premium - pos.entry_premium) * 150, 2))

    # 17. BANKNIFTY Lots Accounting
    def test_banknifty_lot_size_accounting(self):
        pos = self.closed_pos.model_copy(update={"underlying": "BANKNIFTY", "lot_size": 15, "quantity": 30})
        acc = self.pnl_engine.account_trade(pos)
        self.assertEqual(acc.quantity, 30)

    # 18. FINNIFTY Lots Accounting
    def test_finnifty_lot_size_accounting(self):
        pos = self.closed_pos.model_copy(update={"underlying": "FINNIFTY", "lot_size": 40, "quantity": 80})
        acc = self.pnl_engine.account_trade(pos)
        self.assertEqual(acc.quantity, 80)

    # 19. Generate Accounting Summary Empty list
    def test_generate_accounting_summary_empty(self):
        res = self.pnl_engine.generate_accounting_summary([])
        self.assertEqual(len(res.trades), 0)
        self.assertEqual(res.total_gross_pnl, 0.0)
        self.assertEqual(res.total_charges, 0.0)
        self.assertEqual(res.total_net_pnl, 0.0)

    # 20. Generate Accounting Summary Multiple Trades
    def test_generate_accounting_summary_multiple_trades(self):
        p1 = self.closed_pos.model_copy(update={"position_id": "p1", "entry_premium": 100.0, "exit_premium": 110.0})
        p2 = self.closed_pos.model_copy(update={"position_id": "p2", "entry_premium": 100.0, "exit_premium": 95.0})
        res = self.pnl_engine.generate_accounting_summary([p1, p2])
        self.assertEqual(len(res.trades), 2)
        
        expected_gross = (110.0 - 100.0) * 75 + (95.0 - 100.0) * 75
        self.assertEqual(res.total_gross_pnl, expected_gross)
        
        expected_charges = res.trades[0].charges.total_charges + res.trades[1].charges.total_charges
        self.assertEqual(res.total_charges, round(expected_charges, 2))
        self.assertEqual(res.total_net_pnl, round(expected_gross - expected_charges, 2))

    # 21. Cost Model Interface Polymorphism
    def test_cost_model_interface_polymorphism(self):
        class ZeroCostModel(CostModel):
            def calculate_brokerage(self, position):
                return 0.0
            def calculate_taxes(self, position):
                return {"stt": 0.0, "exchange_charges": 0.0, "sebi_charges": 0.0, "stamp_duty": 0.0, "gst": 0.0}
            def calculate_charges(self, position):
                return TradeCharges(brokerage=0, stt=0, exchange_charges=0, sebi_charges=0, gst=0, stamp_duty=0, total_charges=0)
        
        custom_engine = PnLEngine(cost_model=ZeroCostModel())
        acc = custom_engine.account_trade(self.closed_pos)
        self.assertEqual(acc.charges.total_charges, 0.0)
        self.assertEqual(acc.net_pnl, acc.gross_pnl)

    # 22. TradeAccountingResult Fields
    def test_trade_accounting_result_fields(self):
        acc = self.pnl_engine.account_trade(self.closed_pos)
        self.assertIsInstance(acc.position_id, str)
        self.assertIsInstance(acc.entry_time, datetime)
        self.assertIsInstance(acc.exit_time, datetime)
        self.assertIsInstance(acc.contract, str)
        self.assertIsInstance(acc.entry_premium, float)
        self.assertIsInstance(acc.exit_premium, float)
        self.assertIsInstance(acc.quantity, int)
        self.assertIsInstance(acc.gross_pnl, float)
        self.assertIsInstance(acc.charges, TradeCharges)
        self.assertIsInstance(acc.net_pnl, float)

    # 23. TradeCharges Fields
    def test_trade_charges_fields(self):
        charges = self.cost_model.calculate_charges(self.closed_pos)
        self.assertIsInstance(charges.brokerage, float)
        self.assertIsInstance(charges.stt, float)
        self.assertIsInstance(charges.exchange_charges, float)
        self.assertIsInstance(charges.sebi_charges, float)
        self.assertIsInstance(charges.gst, float)
        self.assertIsInstance(charges.stamp_duty, float)
        self.assertIsInstance(charges.other_charges, float)
        self.assertIsInstance(charges.total_charges, float)

    # 24. BacktestAccountingResult Fields
    def test_backtest_accounting_result_fields(self):
        res = self.pnl_engine.generate_accounting_summary([self.closed_pos])
        self.assertIsInstance(res.trades, list)
        self.assertIsInstance(res.total_gross_pnl, float)
        self.assertIsInstance(res.total_charges, float)
        self.assertIsInstance(res.total_net_pnl, float)

    # 25. Actual Replay Trade #1 PnL and Charges Validation
    def test_pnl_validation_with_actual_numbers_trade_1(self):
        # Trade #1 Details from replay logs:
        # Buy: 133.60, Sell: 134.60, Qty: 75.
        t1 = self.closed_pos.model_copy(update={"entry_premium": 133.60, "exit_premium": 134.60, "quantity": 75})
        acc = self.pnl_engine.account_trade(t1)
        
        # Gross: (134.60 - 133.60) * 75 = ₹75.00
        self.assertEqual(acc.gross_pnl, 75.00)
        
        # Brokerage = ₹40.00
        # STT = 134.60 * 75 * 0.001 = 10.095 -> 10.10
        # Exchange charges = 20115 * 0.0003553 = 7.146 -> 7.15
        # SEBI charges = 20115 * 1e-7 = 0.002 -> 0.00
        # GST = (40.00 + 7.15 + 0.00) * 0.18 = 8.487 -> 8.49
        # Stamp duty = 133.60 * 75 * 0.00003 = 0.3008 -> 0.30
        # Total charges = 40.00 + 10.10 + 7.15 + 0.00 + 8.49 + 0.30 = 66.04
        self.assertEqual(acc.charges.brokerage, 40.00)
        self.assertEqual(acc.charges.stt, 10.10)
        self.assertEqual(acc.charges.exchange_charges, 7.15)
        self.assertEqual(acc.charges.sebi_charges, 0.00)
        self.assertEqual(acc.charges.gst, 8.49)
        self.assertEqual(acc.charges.stamp_duty, 0.30)
        self.assertEqual(acc.charges.total_charges, 66.04)
        
        # Net = 75.00 - 66.04 = 8.96
        self.assertEqual(acc.net_pnl, 8.96)

    # 26. Actual Replay Trade #7 PnL and Charges Validation
    def test_pnl_validation_with_actual_numbers_trade_7(self):
        # Trade #7 Details:
        # Buy: 112.90, Sell: 133.40, Qty: 75.
        t7 = self.closed_pos.model_copy(update={"entry_premium": 112.90, "exit_premium": 133.40, "quantity": 75})
        acc = self.pnl_engine.account_trade(t7)
        
        # Gross = (133.40 - 112.90) * 75 = 20.50 * 75 = ₹1537.50
        self.assertEqual(acc.gross_pnl, 1537.50)
        
        # Buy value = 8467.50. Sell value = 10005.0. Total turnover = 18472.50
        # Brokerage = ₹40.00
        # STT = 10005.0 * 0.001 = 10.005 -> 10.01
        # Exchange charges = 18472.50 * 0.0003553 = 6.563 -> 6.56
        # SEBI = 18472.50 * 1e-7 = 0.0018 -> 0.00
        # GST = (40.00 + 6.56 + 0.00) * 0.18 = 8.38
        # Stamp = 8467.50 * 0.00003 = 0.254 -> 0.25
        # Total charges = 40.00 + 10.01 + 6.56 + 0.00 + 8.38 + 0.25 = 65.20
        self.assertEqual(acc.charges.brokerage, 40.00)
        self.assertEqual(acc.charges.stt, 10.01)
        self.assertEqual(acc.charges.exchange_charges, 6.56)
        self.assertEqual(acc.charges.gst, 8.38)
        self.assertEqual(acc.charges.stamp_duty, 0.25)
        self.assertEqual(acc.charges.total_charges, 65.20)
        
        # Net = 1537.50 - 65.20 = 1472.30
        self.assertEqual(acc.net_pnl, 1472.30)

    # 27. Actual Replay Trade #11 PnL and Charges Validation
    def test_pnl_validation_with_actual_numbers_trade_11(self):
        # Trade #11 Details:
        # Buy: 84.10, Sell: 110.40, Qty: 75.
        t11 = self.closed_pos.model_copy(update={"entry_premium": 84.10, "exit_premium": 110.40, "quantity": 75})
        acc = self.pnl_engine.account_trade(t11)
        
        # Gross = (110.40 - 84.10) * 75 = 26.30 * 75 = ₹1972.50
        self.assertEqual(acc.gross_pnl, 1972.50)
        
        # Buy value = 6307.50. Sell value = 8280.0. Total turnover = 14587.50
        # Brokerage = ₹40.00
        # STT = 8280.0 * 0.001 = 8.28
        # Exchange charges = 14587.50 * 0.0003553 = 5.183 -> 5.18
        # SEBI = 14587.50 * 1e-7 = 0.0014 -> 0.00
        # GST = (40.00 + 5.18 + 0.00) * 0.18 = 8.132 -> 8.13
        # Stamp = 6307.50 * 0.00003 = 0.189 -> 0.19
        # Total charges = 40.00 + 8.28 + 5.18 + 0.00 + 8.13 + 0.19 = 61.78
        self.assertEqual(acc.charges.brokerage, 40.00)
        self.assertEqual(acc.charges.stt, 8.28)
        self.assertEqual(acc.charges.exchange_charges, 5.18)
        self.assertEqual(acc.charges.gst, 8.13)
        self.assertEqual(acc.charges.stamp_duty, 0.19)
        self.assertEqual(acc.charges.total_charges, 61.78)
        
        # Net = 1972.50 - 61.78 = 1910.72
        self.assertEqual(acc.net_pnl, 1910.72)

    # 28. STT is Zero on Buy side
    def test_stt_is_zero_on_buy(self):
        # We verify that STT is computed only using exit value
        pos_half_sell_zero = self.closed_pos.model_copy(update={"entry_premium": 100.0, "exit_premium": 0.0})
        taxes = self.cost_model.calculate_taxes(pos_half_sell_zero)
        self.assertEqual(taxes["stt"], 0.0)

    # 29. Stamp Duty is Zero on Sell side
    def test_stamp_duty_is_zero_on_sell(self):
        # We verify Stamp Duty is computed only using entry value
        pos_half_buy_zero = self.closed_pos.model_copy(update={"entry_premium": 0.0, "exit_premium": 100.0})
        taxes = self.cost_model.calculate_taxes(pos_half_buy_zero)
        self.assertEqual(taxes["stamp_duty"], 0.0)

    # 30. GST Base Excludes STT and Stamp Duty
    def test_gst_base_excludes_stt_and_stamp_duty(self):
        # Modifying STT and Stamp Duty through exit/entry should not change GST if brokerage and exchange charges remain static
        # (Actually, changing entry/exit changes exchange charges, so let's keep exchange charges constant by keeping total turnover constant)
        # Turnover A: Buy 150, Sell 50. Total turnover = 200, buy = 150
        # Turnover B: Buy 50, Sell 150. Total turnover = 200, buy = 50
        # In both, total exchange charges are same, brokerage is same. So GST must be exactly the same!
        # But STT and Stamp Duty will differ between A and B!
        pA = self.closed_pos.model_copy(update={"entry_premium": 150.0, "exit_premium": 50.0, "quantity": 10})
        pB = self.closed_pos.model_copy(update={"entry_premium": 50.0, "exit_premium": 150.0, "quantity": 10})
        
        tA = self.cost_model.calculate_taxes(pA)
        tB = self.cost_model.calculate_taxes(pB)
        
        # GST must be identical
        self.assertEqual(tA["gst"], tB["gst"])
        # STT and Stamp duty must differ
        self.assertNotEqual(tA["stt"], tB["stt"])
        self.assertNotEqual(tA["stamp_duty"], tB["stamp_duty"])

    # 31. Round Trip Charges on Non-Zero Quantum (minimum charge behavior)
    def test_round_trip_charges_non_zero_quantum(self):
        # Verify extremely small prices still calculate correct positive charges
        p = self.closed_pos.model_copy(update={"entry_premium": 0.05, "exit_premium": 0.05, "quantity": 1})
        charges = self.cost_model.calculate_charges(p)
        self.assertGreater(charges.total_charges, 40.0)

    # 32. Large Quantity Charges (High Volume Scaling)
    def test_large_quantity_charges(self):
        p = self.closed_pos.model_copy(update={"entry_premium": 100.0, "exit_premium": 110.0, "quantity": 10000})
        charges = self.cost_model.calculate_charges(p)
        self.assertGreater(charges.exchange_charges, 100.0)
        self.assertGreater(charges.stt, 1000.0)

if __name__ == "__main__":
    unittest.main()
