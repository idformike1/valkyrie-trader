import sys
import unittest
from datetime import datetime, timedelta

# Bootstrap backend path
sys.path.insert(0, "/Users/rajumaharjan/Documents/Anit Gravity Projects/Valkyrie/backend")

# Resolve circular import name shadowing by cleaning sys.path
sys.path = [p for p in sys.path if "backend/v2" not in p]

import backend.app as app
from v2.config import BacktestConfig
from v2.position_ledger import PositionLedger
from v2.position_manager import PositionManager
from v2.realtime_signal_runner import RealtimeSignalRunner
from v2.telemetry_logger import TelemetryLogger, RuntimeLog
from v2.position_models import Position, PositionStatus
from v2.pnl_models import TradeAccountingResult, TradeCharges

class TestV2TelemetryFoundation(unittest.TestCase):
    def setUp(self):
        # Reset FastAPI global variables
        app.TRADE_LOGS = []
        app.EVENT_LOGS = []
        app.EQUITY_CURVE = []
        app.SYSTEM_STATUS = {
            "state": "IDLE",
            "mode": None,
            "balance": 100000.0,
            "initial_balance": 100000.0,
            "position": None,
            "instrument_key": "NSE_INDEX|Nifty 50",
            "index_name": "NIFTY",
            "engine": "v1",
            "session_id": None
        }
        app.current_v2_runner = None
        TelemetryLogger.set_live_mode(True)
        TelemetryLogger.start_session()

    def tearDown(self):
        TelemetryLogger.set_live_mode(False)
        TelemetryLogger.clear_session()
        app.current_v2_runner = None

    def test_v2_telemetry_bridge_mapping(self):
        """
        Validates that update_telemetry_metrics() maps V2 runner data
        correctly to standard V1 global metrics variables.
        """
        # Create a mock config
        config = BacktestConfig(**{
            "underlying_instrument_key": "NIFTY",
            "timeframe": "1m",
            "start_date": "2026-06-02",
            "end_date": "2026-06-02",
            "strategy_name": "five_ema_scalping",
            "strategy_params": {
                "ema_period": 5,
                "rr_ratio": 3.0,
                "cut_off_time": "15:15"
            },
            "option_type_preference": "DYNAMIC",
            "strike_selection": {"mode": "ATM"},
            "expiry_selection": {"mode": "CURRENT_WEEKLY", "roll_threshold_hours": 2.0},
            "risk_management": {
                "target_type": "points",
                "target_value": 30.0,
                "stop_loss_type": "points",
                "stop_loss_value": 15.0,
                "trailing_sl_gap": 5.0,
                "max_holding_candles": 15,
                "cutoff_time": "15:15"
            },
            "execution": {
                "brokerage_flat": 20.0,
                "slippage_pct": 0.0,
                "lot_size": 1,
                "initial_balance": 100000.0
            }
        })

        ledger = PositionLedger()
        pm = PositionManager(ledger=ledger)
        runner = RealtimeSignalRunner(config, pm)
        app.current_v2_runner = runner
        app.CURRENT_SESSION_ID = 999

        # Simulate logs, open positions, closed positions
        TelemetryLogger.log("SIGNAL", "INFO", "Triggered BUY signal at spot 18200")
        TelemetryLogger.log("POSITION", "INFO", "Opened option contract NIFTY2660418200CE")

        # 1. Create a Closed Position and TradeAccountingResult
        pos1 = Position(
            position_id="test-pos-1",
            underlying="NIFTY",
            strike=18200.0,
            option_type="CE",
            expiry="2026-06-04",
            entry_premium=100.0,
            quantity=75,
            entry_time=datetime(2026, 6, 2, 9, 30),
            exit_premium=120.0,
            exit_time=datetime(2026, 6, 2, 9, 45),
            status=PositionStatus.CLOSED,
            exit_reason="Target Hit",
            instrument_key="NIFTY_2026-06-04_18200_CE",
            lot_size=75,
            entry_value=7500.0,
            exit_value=9000.0,
            broker="PAPER",
            entry_signal="BUY",
            exit_signal="Target Hit"
        )
        ledger.add_position(pos1)
        
        charge1 = TradeCharges(
            brokerage=20.0,
            gst=3.6,
            stt=15.0,
            exchange_charges=4.2,
            sebi_charges=0.1,
            stamp_duty=0.5,
            total_charges=43.4
        )
        acc1 = TradeAccountingResult(
            position_id="test-pos-1",
            entry_time=pos1.entry_time,
            exit_time=pos1.exit_time,
            contract="NIFTY 18200.0 CE (2026-06-04)",
            entry_premium=100.0,
            exit_premium=120.0,
            quantity=75,
            gross_pnl=1500.0,
            charges=charge1,
            net_pnl=1456.6
        )
        ledger.add_accounting_record(acc1)

        # 2. Create an Open Active Position
        pos2 = Position(
            position_id="test-pos-2",
            underlying="NIFTY",
            strike=18250.0,
            option_type="CE",
            expiry="2026-06-04",
            entry_premium=85.0,
            quantity=75,
            entry_time=datetime(2026, 6, 2, 10, 0),
            status=PositionStatus.LONG,
            instrument_key="NIFTY_2026-06-04_18250_CE",
            lot_size=75,
            entry_value=6375.0,
            broker="PAPER",
            entry_signal="BUY"
        )
        ledger.add_position(pos2)
        pm.active_position = pos2
        pos2.metadata["last_premium"] = 92.0
        pos2.metadata["highest_premium"] = 95.0

        # Invoke Telemetry update bridge
        app.update_telemetry_metrics()

        # --- VALIDATE MAPPING ---

        # A. Logs
        self.assertEqual(len(app.EVENT_LOGS), 2)
        self.assertIn("[SIGNAL:INFO]", app.EVENT_LOGS[0])
        self.assertIn("Triggered BUY signal", app.EVENT_LOGS[0])

        # B. Positions (Active Position HUD)
        self.assertIsNotNone(app.SYSTEM_STATUS["position"])
        active_hud = app.SYSTEM_STATUS["position"]
        self.assertEqual(active_hud["instrument_key"], "NIFTY_2026-06-04_18250_CE")
        self.assertEqual(active_hud["entry_price"], 85.0)
        self.assertEqual(active_hud["ltp"], 92.0)
        self.assertEqual(active_hud["pnl"], 525.0) # (92 - 85) * 75
        self.assertEqual(active_hud["stop_loss"], 70.0) # 85 - 15 (points)
        self.assertEqual(active_hud["target_price"], 115.0) # 85 + 30 (points)
        self.assertEqual(active_hud["highest_price"], 95.0)

        # C. Trades (TRADE_LOGS)
        # We expect 3 records:
        # 1. BUY for pos1
        # 2. EXIT for pos1
        # 3. BUY for pos2 (open)
        self.assertEqual(len(app.TRADE_LOGS), 3)
        self.assertEqual(app.TRADE_LOGS[0]["type"], "BUY")
        self.assertEqual(app.TRADE_LOGS[0]["price"], 100.0)
        self.assertEqual(app.TRADE_LOGS[1]["type"], "EXIT")
        self.assertEqual(app.TRADE_LOGS[1]["price"], 120.0)
        self.assertEqual(app.TRADE_LOGS[1]["pnl"], 1456.6)
        self.assertEqual(app.TRADE_LOGS[1]["reason"], "Target Hit")
        self.assertEqual(app.TRADE_LOGS[2]["type"], "BUY")
        self.assertEqual(app.TRADE_LOGS[2]["price"], 85.0)

        # D. Metrics
        self.assertEqual(app.SYSTEM_STATUS["total_trades"], 1) # 1 completed trade
        self.assertEqual(app.SYSTEM_STATUS["win_rate"], 100.0)
        self.assertEqual(app.SYSTEM_STATUS["total_pnl"], 1456.6)
        self.assertEqual(app.SYSTEM_STATUS["balance"], 101456.6)
        self.assertEqual(app.SYSTEM_STATUS["return_percent"], 1.4566)

        # E. Equity Curve
        self.assertEqual(len(app.EQUITY_CURVE), 2)
        self.assertEqual(app.EQUITY_CURVE[0]["equity"], 100000.0)
        self.assertEqual(app.EQUITY_CURVE[1]["equity"], 101456.6)

        print("\n\u2705 All V2 Telemetry Foundation bridge assertions passed successfully!")

    def test_pause_resume_endpoints(self):
        """
        Validates the /pause and /resume engine endpoint logic.
        """
        from v2.config import BacktestConfig
        from v2.position_ledger import PositionLedger
        from v2.position_manager import PositionManager
        from v2.realtime_signal_runner import RealtimeSignalRunner
        
        config = BacktestConfig(**{
            "underlying_instrument_key": "NIFTY",
            "timeframe": "1m",
            "start_date": "2026-06-02",
            "end_date": "2026-06-02",
            "strategy_name": "five_ema_scalping",
            "strategy_params": {
                "ema_period": 5,
                "rr_ratio": 3.0,
                "cut_off_time": "15:15"
            },
            "option_type_preference": "DYNAMIC",
            "strike_selection": {"mode": "ATM"},
            "expiry_selection": {"mode": "CURRENT_WEEKLY", "roll_threshold_hours": 2.0},
            "risk_management": {
                "target_type": "none",
                "target_value": 0.0,
                "stop_loss_type": "none",
                "stop_loss_value": 0.0,
                "trailing_sl_gap": 0.0,
                "max_holding_candles": 15,
                "cutoff_time": "15:15"
            },
            "execution": {
                "brokerage_flat": 20.0,
                "slippage_pct": 0.0,
                "lot_size": 1,
                "initial_balance": 100000.0
            }
        })
        
        ledger = PositionLedger()
        pm = PositionManager(ledger=ledger)
        runner = RealtimeSignalRunner(config, pm)
        app.current_v2_runner = runner
        
        # 1. Assert initial state is not paused
        self.assertFalse(runner.is_paused)
        
        # 2. Invoke pause endpoint
        res = app.pause_engine()
        self.assertEqual(res["status"]["state"], "PAUSED")
        self.assertTrue(runner.is_paused)
        
        # 3. Verify on_candle does nothing when paused
        action, data = runner.on_candle({"timestamp": "2026-06-02T10:00:00Z", "close": 18200.0})
        self.assertEqual(action, "HOLD")
        self.assertEqual(data, {})
        
        # 4. Invoke resume endpoint
        res = app.resume_engine_route()
        self.assertEqual(res["status"]["state"], "LIVE_MONITORING")
        self.assertFalse(runner.is_paused)
        
        print("\n\u2705 Pause and Resume endpoint assertions passed successfully!")

if __name__ == "__main__":
    unittest.main()
