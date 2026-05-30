from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class TradeStatistics(BaseModel):
    total_trades: int = Field(..., description="Total number of completed trades")
    winning_trades: int = Field(..., description="Number of profitable trades (Net PnL > 0)")
    losing_trades: int = Field(..., description="Number of losing trades (Net PnL < 0)")
    breakeven_trades: int = Field(..., description="Number of break-even trades (Net PnL == 0)")
    win_rate: float = Field(..., description="Win rate percentage (0.0 to 100.0)")
    loss_rate: float = Field(..., description="Loss rate percentage (0.0 to 100.0)")

class PerformanceMetrics(BaseModel):
    gross_profit: float = Field(..., description="Sum of positive net trade profits (INR)")
    gross_loss: float = Field(..., description="Sum of negative net trade losses (INR)")
    net_profit: float = Field(..., description="Net profit (Gross Profit - Absolute Gross Loss) (INR)")
    avg_trade: float = Field(..., description="Average net PnL per trade (INR)")
    avg_win: float = Field(..., description="Average net PnL of winning trades (INR)")
    avg_loss: float = Field(..., description="Average net PnL of losing trades (INR)")
    largest_win: float = Field(..., description="Largest net profit in a single trade (INR)")
    largest_loss: float = Field(..., description="Largest net loss in a single trade (INR)")
    profit_factor: float = Field(..., description="Gross Profit / Absolute Gross Loss")
    expectancy: float = Field(..., description="Expectancy per trade (INR)")
    payoff_ratio: float = Field(..., description="Average Win / Average Loss ratio")
    max_consecutive_wins: int = Field(..., description="Maximum consecutive winning trades streak")
    max_consecutive_losses: int = Field(..., description="Maximum consecutive losing trades streak")
    avg_hold_time_seconds: float = Field(..., description="Average hold time of a position in seconds")
    shortest_hold_time_seconds: float = Field(..., description="Shortest hold time of a position in seconds")
    longest_hold_time_seconds: float = Field(..., description="Longest hold time of a position in seconds")
    exposure_time_seconds: float = Field(..., description="Total time exposed to the market in seconds")

class EquityPoint(BaseModel):
    timestamp: datetime = Field(..., description="Timestamp of the equity valuation point")
    equity_value: float = Field(..., description="Account equity value (INR)")
    trade_id: Optional[str] = Field(None, description="Trade ID that triggered this equity update")

class DrawdownPoint(BaseModel):
    timestamp: datetime = Field(..., description="Timestamp of the drawdown measurement")
    drawdown_value: float = Field(..., description="Drawdown in INR")
    drawdown_pct: float = Field(..., description="Drawdown as a percentage of the peak value (0.0 to 100.0)")
    peak_value: float = Field(..., description="Running peak equity value at this point (INR)")

class MetricsReport(BaseModel):
    initial_capital: float = Field(..., description="Starting backtest capital")
    final_equity: float = Field(..., description="Ending account equity")
    trade_stats: TradeStatistics = Field(..., description="Basic trade statistics")
    performance: PerformanceMetrics = Field(..., description="Advanced performance metrics")
    equity_curve: List[EquityPoint] = Field(..., description="Time series list of equity curve points")
    drawdown_curve: List[DrawdownPoint] = Field(..., description="Time series list of drawdown curve points")
    max_drawdown: float = Field(..., description="Maximum drawdown value in INR")
    max_drawdown_pct: float = Field(..., description="Maximum drawdown percentage (0.0 to 100.0)")
    max_drawdown_duration_seconds: float = Field(..., description="Maximum drawdown recovery duration in seconds")
    absolute_return_pct: float = Field(..., description="Absolute return percentage of capital")
    net_return_pct: float = Field(..., description="Net return percentage of capital")
    capital_growth_pct: float = Field(..., description="Capital growth percentage")
    sharpe_ratio: float = Field(..., description="Sharpe ratio")
    sortino_ratio: float = Field(..., description="Sortino ratio")
    grade: str = Field(..., description="Performance grade (A+, A, B, C, D, F)")
    scorecard: Dict[str, Any] = Field(..., description="Performance scorecard details")
