import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from v2.config import BacktestConfig
from v2.replay_engine import HistoricalReplayEngine
from v2.metrics_engine import MetricsEngine
from v2.replay_models import ReplayTimeline
from v2.metrics_models import MetricsReport, EquityPoint, DrawdownPoint
from v2.pnl_models import TradeAccountingResult
from v2.position_models import Position

logger = logging.getLogger("Valkyrie.BacktestRunner")

class BacktestResult(BaseModel):
    """
    Unified result schema representing a completed V2 Option backtest.
    Contains the full trade audit records, position lifecycles, replay timelines,
    performance statistics, and run metadata.
    """
    report: MetricsReport = Field(..., description="Metrics scorecard and summary performance statistics.")
    trades: List[TradeAccountingResult] = Field(..., description="Detailed ledger trade records with exact transaction costs and PnL.")
    positions: List[Position] = Field(..., description="Complete historical trace of position lifecycle states.")
    replay_timeline: ReplayTimeline = Field(..., description="Chronological record of spot price, signals, and transaction intents.")
    equity_curve: List[EquityPoint] = Field(..., description="Time-series log of account equity progression.")
    drawdown_curve: List[DrawdownPoint] = Field(..., description="Time-series log of account drawdown progression.")
    metadata: Dict[str, Any] = Field(..., description="Orchestration metadata of the backtest runner execution.")

class BacktestRunner:
    """
    Production-grade orchestrator for executing high-fidelity historical backtests.
    """
    @staticmethod
    def run(config: BacktestConfig) -> BacktestResult:
        logger.info(
            f"[Backtest Runner] Initiating backtest for strategy '{config.strategy_name or 'dynamic_rule'}' "
            f"on underlying '{config.underlying_instrument_key}' spanning {config.start_date} to {config.end_date}."
        )
        
        # 1. Execute HistoricalReplayEngine
        replay_engine = HistoricalReplayEngine()
        replay_timeline = replay_engine.run(config)
        
        # 2. Extract Position manager ledger results
        ledger = replay_engine.ledger
        positions = ledger.positions
        trades = ledger.accounting_records
        
        # 3. Generate performance report via MetricsEngine
        initial_capital = config.execution.initial_balance
        metrics_engine = MetricsEngine(initial_capital=initial_capital)
        report = metrics_engine.calculate_metrics(positions, trades)
        
        # 4. Pack unified BacktestResult Pydantic schema
        metadata = {
            "strategy_name": config.strategy_name or "dynamic_rule",
            "underlying": config.underlying_instrument_key,
            "start_date": config.start_date,
            "end_date": config.end_date,
            "timeframe": str(config.timeframe),
            "initial_capital": initial_capital,
            "final_equity": report.final_equity,
            "net_profit": report.performance.net_profit,
            "total_trades": report.trade_stats.total_trades,
            "win_rate_pct": report.trade_stats.win_rate,
            "grade": report.grade,
            "execution_timestamp": datetime.now().isoformat()
        }
        
        return BacktestResult(
            report=report,
            trades=trades,
            positions=positions,
            replay_timeline=replay_timeline,
            equity_curve=report.equity_curve,
            drawdown_curve=report.drawdown_curve,
            metadata=metadata
        )
