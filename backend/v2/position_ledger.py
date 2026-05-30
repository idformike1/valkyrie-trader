from typing import List, Dict, Any, Union
from v2.position_models import Position, PositionStatus, PositionOpened, PositionHeld, PositionClosed
from v2.pnl_models import TradeAccountingResult

class PositionLedger:
    def __init__(self):
        self.positions: List[Position] = []
        self.events: List[Union[PositionOpened, PositionHeld, PositionClosed]] = []
        self.accounting_records: List[TradeAccountingResult] = []

    def add_position(self, position: Position):
        self.positions.append(position)

    def add_event(self, event: Union[PositionOpened, PositionHeld, PositionClosed]):
        self.events.append(event)

    def add_accounting_record(self, record: TradeAccountingResult):
        self.accounting_records.append(record)

    def get_open_positions(self) -> List[Position]:
        return [p for p in self.positions if p.status == PositionStatus.LONG]

    def get_closed_positions(self) -> List[Position]:
        return [p for p in self.positions if p.status == PositionStatus.CLOSED]

    def get_position_history(self) -> List[Position]:
        return self.positions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "positions": [p.model_dump() for p in self.positions],
            "events": [
                {
                    "type": type(e).__name__,
                    "data": e.model_dump()
                } for e in self.events
            ],
            "accounting_records": [r.model_dump() for r in self.accounting_records]
        }

    def clear(self):
        self.positions.clear()
        self.events.clear()
        self.accounting_records.clear()

