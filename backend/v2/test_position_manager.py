import unittest
from datetime import datetime, timedelta
from typing import Dict, Any

from v2.position_models import PositionStatus, Position, PositionOpened, PositionHeld, PositionClosed
from v2.position_ledger import PositionLedger
from v2.position_manager import PositionManager
from v2.config import BacktestConfig, StrikeConfig, ExpiryConfig
from v2.types import StrikeMode, ExpiryMode, Timeframe
from v2.replay_engine import HistoricalReplayEngine

class TestPositionStateMachine(unittest.TestCase):

    def setUp(self):
        self.ledger = PositionLedger()
        self.manager = PositionManager(ledger=self.ledger)
        self.sample_time = datetime(2025, 4, 15, 9, 35)
        self.buy_payload = {
            "underlying": "NIFTY",
            "strike": 23300.0,
            "expiry": "2025-04-17",
            "option_type": "CE",
            "instrument_key": "NSE_FO|48236|17-04-2025",
            "premium_price": 133.60,
            "lot_size": 75,
            "quantity": 75,
            "signal": "BUY_INTENT"
        }
        self.sell_payload = {
            "underlying": "NIFTY",
            "strike": 23300.0,
            "expiry": "2025-04-17",
            "option_type": "CE",
            "instrument_key": "NSE_FO|48236|17-04-2025",
            "premium_price": 150.20,
            "signal": "SELL_INTENT"
        }

    # 1. Enums Verification
    def test_position_status_enum(self):
        self.assertEqual(PositionStatus.FLAT, "FLAT")
        self.assertEqual(PositionStatus.LONG, "LONG")
        self.assertEqual(PositionStatus.CLOSED, "CLOSED")

    # 2. Position Model Initialization
    def test_position_model_fields(self):
        pos = Position(
            position_id="test-123",
            status=PositionStatus.LONG,
            underlying="NIFTY",
            strike=23300.0,
            expiry="2025-04-17",
            option_type="CE",
            instrument_key="NSE_FO|test",
            entry_time=self.sample_time,
            entry_premium=100.0,
            quantity=75,
            lot_size=75,
            entry_value=7500.0,
            broker="Upstox",
            entry_signal="BUY_INTENT"
        )
        self.assertEqual(pos.position_id, "test-123")
        self.assertEqual(pos.status, PositionStatus.LONG)
        self.assertEqual(pos.entry_premium, 100.0)
        self.assertIsNone(pos.exit_premium)

    # 3. PositionOpened Event Validation
    def test_position_opened_event_fields(self):
        ev = PositionOpened(
            timestamp=self.sample_time,
            position_id="pos-1",
            underlying="NIFTY",
            strike=23300.0,
            expiry="2025-04-17",
            option_type="CE",
            instrument_key="NSE_FO|test",
            entry_premium=100.0,
            quantity=75
        )
        self.assertEqual(ev.position_id, "pos-1")
        self.assertEqual(ev.entry_premium, 100.0)

    # 4. PositionHeld Event Validation
    def test_position_held_event_fields(self):
        ev = PositionHeld(
            timestamp=self.sample_time,
            position_id="pos-1",
            underlying="NIFTY",
            strike=23300.0,
            expiry="2025-04-17",
            option_type="CE",
            instrument_key="NSE_FO|test",
            current_premium=110.0
        )
        self.assertEqual(ev.current_premium, 110.0)

    # 5. PositionClosed Event Validation
    def test_position_closed_event_fields(self):
        ev = PositionClosed(
            timestamp=self.sample_time,
            position_id="pos-1",
            underlying="NIFTY",
            strike=23300.0,
            expiry="2025-04-17",
            option_type="CE",
            instrument_key="NSE_FO|test",
            exit_premium=120.0,
            quantity=75
        )
        self.assertEqual(ev.exit_premium, 120.0)

    # 6. PositionLedger Initialization
    def test_position_ledger_initialization(self):
        self.assertEqual(len(self.ledger.positions), 0)
        self.assertEqual(len(self.ledger.events), 0)

    # 7. PositionManager Initialization
    def test_position_manager_initialization(self):
        self.assertIsNone(self.manager.active_position)
        self.assertIs(self.manager.ledger, self.ledger)

    # 8. Open Position Transition FLAT -> LONG
    def test_open_position_flat(self):
        self.manager.open_position(self.buy_payload, self.sample_time)
        self.assertIsNotNone(self.manager.active_position)
        self.assertEqual(self.manager.active_position.status, PositionStatus.LONG)
        self.assertEqual(self.manager.active_position.strike, 23300.0)
        self.assertEqual(self.manager.active_position.entry_premium, 133.60)

    # 9. Open Position Logs Event
    def test_open_position_logs_event(self):
        self.manager.open_position(self.buy_payload, self.sample_time)
        self.assertEqual(len(self.ledger.positions), 1)
        self.assertEqual(len(self.ledger.events), 1)
        self.assertIsInstance(self.ledger.events[0], PositionOpened)
        self.assertEqual(self.ledger.events[0].entry_premium, 133.60)

    # 10. Reject BUY While LONG
    def test_reject_buy_while_long(self):
        self.manager.open_position(self.buy_payload, self.sample_time)
        with self.assertRaises(ValueError) as context:
            self.manager.open_position(self.buy_payload, self.sample_time + timedelta(minutes=5))
        self.assertIn("already LONG", str(context.exception))

    # 11. Hold Position LONG -> LONG
    def test_hold_position_while_long(self):
        self.manager.open_position(self.buy_payload, self.sample_time)
        hold_time = self.sample_time + timedelta(minutes=5)
        hold_payload = {"premium_price": 135.0}
        self.manager.hold_position(hold_payload, hold_time)
        self.assertEqual(self.manager.active_position.status, PositionStatus.LONG)

    # 12. Hold Position Logs Event
    def test_hold_position_logs_event(self):
        self.manager.open_position(self.buy_payload, self.sample_time)
        hold_time = self.sample_time + timedelta(minutes=5)
        hold_payload = {"premium_price": 135.0}
        self.manager.hold_position(hold_payload, hold_time)
        self.assertEqual(len(self.ledger.events), 2)
        self.assertIsInstance(self.ledger.events[1], PositionHeld)
        self.assertEqual(self.ledger.events[1].current_premium, 135.0)

    # 13. Hold Position While FLAT is a No-Op
    def test_hold_position_while_flat_no_op(self):
        hold_payload = {"premium_price": 135.0}
        self.manager.hold_position(hold_payload, self.sample_time)
        self.assertEqual(len(self.ledger.events), 0)

    # 14. Close Position LONG -> CLOSED
    def test_close_position_while_long(self):
        self.manager.open_position(self.buy_payload, self.sample_time)
        close_time = self.sample_time + timedelta(minutes=15)
        self.manager.close_position(self.sell_payload, close_time)
        self.assertIsNone(self.manager.active_position)
        
        closed_pos = self.ledger.positions[0]
        self.assertEqual(closed_pos.status, PositionStatus.CLOSED)
        self.assertEqual(closed_pos.exit_premium, 150.20)
        self.assertEqual(closed_pos.exit_time, close_time)

    # 15. Close Position Logs Event
    def test_close_position_logs_event(self):
        self.manager.open_position(self.buy_payload, self.sample_time)
        close_time = self.sample_time + timedelta(minutes=15)
        self.manager.close_position(self.sell_payload, close_time)
        self.assertEqual(len(self.ledger.events), 2)
        self.assertIsInstance(self.ledger.events[1], PositionClosed)
        self.assertEqual(self.ledger.events[1].exit_premium, 150.20)

    # 16. Reject SELL While FLAT
    def test_reject_sell_while_flat(self):
        with self.assertRaises(ValueError) as context:
            self.manager.close_position(self.sell_payload, self.sample_time)
        self.assertIn("while FLAT", str(context.exception))

    # 17. Contract Immutability on Hold
    def test_contract_immutability_on_hold(self):
        self.manager.open_position(self.buy_payload, self.sample_time)
        pos = self.manager.active_position
        
        # Ensure initial state matches entry
        self.assertEqual(pos.strike, 23300.0)
        self.assertEqual(pos.expiry, "2025-04-17")
        self.assertEqual(pos.instrument_key, "NSE_FO|48236|17-04-2025")
        
        # Call hold event (should not modify core contract data)
        self.manager.hold_position({"premium_price": 140.0}, self.sample_time + timedelta(minutes=5))
        self.assertEqual(pos.strike, 23300.0)
        self.assertEqual(pos.expiry, "2025-04-17")
        self.assertEqual(pos.instrument_key, "NSE_FO|48236|17-04-2025")

    # 18. Contract Immutability on Close
    def test_contract_immutability_on_close(self):
        self.manager.open_position(self.buy_payload, self.sample_time)
        pos = self.manager.active_position
        self.manager.close_position(self.sell_payload, self.sample_time + timedelta(minutes=10))
        
        # Retreive from ledger and verify original contract info remains unchanged
        closed_pos = self.ledger.positions[0]
        self.assertEqual(closed_pos.strike, 23300.0)
        self.assertEqual(closed_pos.expiry, "2025-04-17")
        self.assertEqual(closed_pos.instrument_key, "NSE_FO|48236|17-04-2025")

    # 19. Ledger to_dict Schema Export
    def test_ledger_to_dict(self):
        self.manager.open_position(self.buy_payload, self.sample_time)
        d = self.ledger.to_dict()
        self.assertIn("positions", d)
        self.assertIn("events", d)
        self.assertEqual(len(d["positions"]), 1)
        self.assertEqual(len(d["events"]), 1)
        self.assertEqual(d["events"][0]["type"], "PositionOpened")

    # 20. Ledger Clear
    def test_ledger_clear(self):
        self.manager.open_position(self.buy_payload, self.sample_time)
        self.ledger.clear()
        self.assertEqual(len(self.ledger.positions), 0)
        self.assertEqual(len(self.ledger.events), 0)

    # 21. PositionManager handle_event Dispatch
    def test_position_manager_handle_event(self):
        self.manager.handle_event("BUY_INTENT", self.buy_payload, self.sample_time)
        self.assertIsNotNone(self.manager.active_position)
        
        self.manager.handle_event("HOLD", {"premium_price": 134.0}, self.sample_time + timedelta(minutes=5))
        self.assertEqual(len(self.ledger.events), 2)
        
        self.manager.handle_event("SELL_INTENT", self.sell_payload, self.sample_time + timedelta(minutes=10))
        self.assertIsNone(self.manager.active_position)

    # 22. Multiple Alternating Trades
    def test_multiple_alternating_trades(self):
        # Trade 1
        self.manager.handle_event("BUY_INTENT", self.buy_payload, self.sample_time)
        self.manager.handle_event("SELL_INTENT", self.sell_payload, self.sample_time + timedelta(minutes=5))
        # Trade 2
        buy_payload_2 = self.buy_payload.copy()
        buy_payload_2["strike"] = 23350.0
        buy_payload_2["instrument_key"] = "NSE_FO|48241|17-04-2025"
        self.manager.handle_event("BUY_INTENT", buy_payload_2, self.sample_time + timedelta(minutes=10))
        
        self.assertEqual(len(self.ledger.positions), 2)
        self.assertEqual(self.ledger.positions[0].strike, 23300.0)
        self.assertEqual(self.ledger.positions[0].status, PositionStatus.CLOSED)
        self.assertEqual(self.ledger.positions[1].strike, 23350.0)
        self.assertEqual(self.ledger.positions[1].status, PositionStatus.LONG)

    # 23. Replay Integration Runs
    def test_replay_integration_runs(self):
        engine = HistoricalReplayEngine()
        config = BacktestConfig(
            underlying_instrument_key="NSE_INDEX|Nifty 50",
            timeframe=Timeframe.MIN_5,
            start_date="2025-04-15",
            end_date="2025-04-15",
            strategy_name="EMA",
            strategy_params={"fast_period": 2, "slow_period": 3, "cut_off_time": "15:25"},
            option_type_preference="CE_ONLY",
            strike_selection=StrikeConfig(mode=StrikeMode.ATM),
            expiry_selection=ExpiryConfig(mode=ExpiryMode.CURRENT_WEEKLY)
        )
        
        timeline = engine.run(config)
        self.assertIsNotNone(engine.position_manager)
        self.assertIsNotNone(engine.ledger)
        self.assertEqual(len(engine.ledger.positions), 11) # We have 11 completed position lifecycles on this day

    # 24. Replay Integration Open/Hold/Close Verification
    def test_replay_integration_open_hold_close(self):
        engine = HistoricalReplayEngine()
        config = BacktestConfig(
            underlying_instrument_key="NSE_INDEX|Nifty 50",
            timeframe=Timeframe.MIN_5,
            start_date="2025-04-15",
            end_date="2025-04-15",
            strategy_name="EMA",
            strategy_params={"fast_period": 2, "slow_period": 3, "cut_off_time": "15:25"},
            option_type_preference="CE_ONLY",
            strike_selection=StrikeConfig(mode=StrikeMode.ATM),
            expiry_selection=ExpiryConfig(mode=ExpiryMode.CURRENT_WEEKLY)
        )
        
        engine.run(config)
        ledger = engine.ledger
        
        # Verify events log contains PositionOpened, PositionHeld, and PositionClosed
        opened_events = [e for e in ledger.events if isinstance(e, PositionOpened)]
        held_events = [e for e in ledger.events if isinstance(e, PositionHeld)]
        closed_events = [e for e in ledger.events if isinstance(e, PositionClosed)]
        
        self.assertEqual(len(opened_events), 11)
        self.assertGreater(len(held_events), 0)
        self.assertEqual(len(closed_events), 11)

    # 25. Quantity Calculation & Lot Sizes (NIFTY vs BANKNIFTY)
    def test_quantity_calculation_lot_sizes(self):
        # Test NIFTY quantity resolution (lot_size=75, execution.lot_size=2 lots = 150 quantity)
        from v2.config import ExecutionConfig
        engine = HistoricalReplayEngine()
        config = BacktestConfig(
            underlying_instrument_key="NSE_INDEX|Nifty 50",
            timeframe=Timeframe.MIN_5,
            start_date="2025-04-15",
            end_date="2025-04-15",
            strategy_name="EMA",
            strategy_params={"fast_period": 2, "slow_period": 3, "cut_off_time": "15:25"},
            option_type_preference="CE_ONLY",
            strike_selection=StrikeConfig(mode=StrikeMode.ATM),
            expiry_selection=ExpiryConfig(mode=ExpiryMode.CURRENT_WEEKLY),
            execution=ExecutionConfig(lot_size=2)
        )
        
        engine.run(config)
        self.assertEqual(engine.ledger.positions[0].lot_size, 75)
        self.assertEqual(engine.ledger.positions[0].quantity, 150)

    # 26. Multi-Day Replay Ledger Persistence
    def test_multi_day_replay_ledger(self):
        engine = HistoricalReplayEngine()
        config = BacktestConfig(
            underlying_instrument_key="NSE_INDEX|Nifty 50",
            timeframe=Timeframe.MIN_5,
            start_date="2025-04-16",
            end_date="2025-04-17",
            strategy_name="EMA",
            strategy_params={"fast_period": 9, "slow_period": 21, "cut_off_time": "15:15"},
            option_type_preference="CE_ONLY",
            strike_selection=StrikeConfig(mode=StrikeMode.ATM),
            expiry_selection=ExpiryConfig(mode=ExpiryMode.CURRENT_WEEKLY)
        )
        
        engine.run(config)
        # Verify multiple trades executed across 2 days (4 trades total: 3 on 2025-04-16 and 1 on 2025-04-17)
        self.assertEqual(len(engine.ledger.positions), 4)

    # 27. Expiry Boundary Tracking
    def test_expiry_boundary_ledger(self):
        engine = HistoricalReplayEngine()
        config = BacktestConfig(
            underlying_instrument_key="NSE_INDEX|Nifty 50",
            timeframe=Timeframe.MIN_5,
            start_date="2025-04-16", # Warmup on 16th, so we capture 16th & 17th trades
            end_date="2025-04-21", # Mon after expiry
            strategy_name="EMA",
            strategy_params={"fast_period": 9, "slow_period": 21, "cut_off_time": "15:15"},
            option_type_preference="CE_ONLY",
            strike_selection=StrikeConfig(mode=StrikeMode.ATM),
            expiry_selection=ExpiryConfig(mode=ExpiryMode.CURRENT_WEEKLY)
        )
        
        engine.run(config)
        positions = engine.ledger.positions
        self.assertGreater(len(positions), 0)
        
        # Verify first trade has 2025-04-17 expiry and subsequent has 2025-04-24 expiry
        self.assertEqual(positions[0].expiry, "2025-04-17")
        self.assertEqual(positions[-1].expiry, "2025-04-24")

if __name__ == "__main__":
    unittest.main()
