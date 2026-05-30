import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from v2.position_models import Position, PositionStatus, PositionOpened, PositionHeld, PositionClosed
from v2.position_ledger import PositionLedger

class PositionManager:
    def __init__(self, ledger: Optional[PositionLedger] = None):
        self.ledger = ledger if ledger is not None else PositionLedger()
        self.active_position: Optional[Position] = None

    def handle_event(self, event_type: str, data: Dict[str, Any], timestamp: datetime):
        """
        Processes events (BUY_INTENT, SELL_INTENT, or HOLD)
        and transitions the active position state machine.
        """
        if event_type == "BUY_INTENT":
            self.open_position(data, timestamp)
        elif event_type == "SELL_INTENT":
            self.close_position(data, timestamp)
        elif event_type == "HOLD":
            self.hold_position(data, timestamp)

    def open_position(self, data: Dict[str, Any], timestamp: datetime):
        # Guard: Reject BUY if already LONG (no pyramiding, averaging, duplicate positions)
        if self.active_position is not None:
            raise ValueError("Rejected: BUY signal received while already LONG.")

        position_id = str(uuid.uuid4())
        lot_size = data.get("lot_size", 75)
        quantity = data.get("quantity", lot_size)
        entry_premium = data["premium_price"]
        entry_value = entry_premium * quantity

        pos = Position(
            position_id=position_id,
            status=PositionStatus.LONG,
            underlying=data["underlying"],
            strike=data["strike"],
            expiry=data["expiry"],
            option_type=data["option_type"],
            instrument_key=data["instrument_key"],
            entry_time=timestamp,
            entry_premium=entry_premium,
            quantity=quantity,
            lot_size=lot_size,
            entry_value=entry_value,
            broker="Upstox",
            entry_signal=data.get("signal", "BUY_INTENT"),
            metadata=data.get("metadata", {})
        )

        self.active_position = pos
        self.ledger.add_position(pos)

        # Log opened event
        opened_event = PositionOpened(
            timestamp=timestamp,
            position_id=position_id,
            underlying=pos.underlying,
            strike=pos.strike,
            expiry=pos.expiry,
            option_type=pos.option_type,
            instrument_key=pos.instrument_key,
            entry_premium=entry_premium,
            quantity=quantity
        )
        self.ledger.add_event(opened_event)

    def hold_position(self, data: Dict[str, Any], timestamp: datetime):
        # Guard: Only hold if we are currently LONG
        if self.active_position is None:
            return

        current_premium = data.get("premium_price", self.active_position.entry_premium)

        held_event = PositionHeld(
            timestamp=timestamp,
            position_id=self.active_position.position_id,
            underlying=self.active_position.underlying,
            strike=self.active_position.strike,
            expiry=self.active_position.expiry,
            option_type=self.active_position.option_type,
            instrument_key=self.active_position.instrument_key,
            current_premium=current_premium
        )
        self.ledger.add_event(held_event)

    def close_position(self, data: Dict[str, Any], timestamp: datetime):
        # Guard: Reject SELL if FLAT
        if self.active_position is None:
            raise ValueError("Rejected: SELL signal received while FLAT.")

        pos = self.active_position
        exit_premium = data["premium_price"]
        exit_value = exit_premium * pos.quantity

        # Update position fields (ensuring contract details remain immutable)
        pos.exit_time = timestamp
        pos.exit_premium = exit_premium
        pos.exit_value = exit_value
        pos.exit_signal = data.get("signal", "SELL_INTENT")
        pos.status = PositionStatus.CLOSED
        if "metadata" in data and data["metadata"]:
            pos.metadata.update(data["metadata"])

        # Log closed event
        closed_event = PositionClosed(
            timestamp=timestamp,
            position_id=pos.position_id,
            underlying=pos.underlying,
            strike=pos.strike,
            expiry=pos.expiry,
            option_type=pos.option_type,
            instrument_key=pos.instrument_key,
            exit_premium=exit_premium,
            quantity=pos.quantity
        )
        self.ledger.add_event(closed_event)

        # Wire PnLEngine to create Accounting Record
        from v2.pnl_engine import PnLEngine
        pnl_engine = PnLEngine()
        accounting_record = pnl_engine.account_trade(pos)
        self.ledger.add_accounting_record(accounting_record)

        # Transition active state back to FLAT
        self.active_position = None
