import math
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from v2.position_models import Position, PositionStatus
from v2.pnl_models import TradeAccountingResult
from v2.metrics_models import (
    TradeStatistics,
    PerformanceMetrics,
    EquityPoint,
    DrawdownPoint,
    MetricsReport
)

class MetricsEngine:
    def __init__(self, initial_capital: float = 100000.0, risk_free_rate_annual: float = 0.065):
        self.initial_capital = initial_capital
        self.risk_free_rate_annual = risk_free_rate_annual

    def calculate_metrics(self, positions: List[Position], trades: List[TradeAccountingResult]) -> MetricsReport:
        # Filter to closed positions and completed trades
        closed_positions = [pos for pos in positions if pos.status == PositionStatus.CLOSED]
        closed_trades = [t for t in trades if t.exit_time is not None]
        
        # Sort trades by exit time
        sorted_trades = sorted(closed_trades, key=lambda t: t.exit_time)
        
        # 1. Basic Trade Statistics
        total_trades = len(sorted_trades)
        winning_trades = sum(1 for t in sorted_trades if t.net_pnl > 0)
        losing_trades = sum(1 for t in sorted_trades if t.net_pnl < 0)
        breakeven_trades = sum(1 for t in sorted_trades if t.net_pnl == 0)
        
        win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0
        loss_rate = (losing_trades / total_trades * 100.0) if total_trades > 0 else 0.0

        # 2. Profitability Metrics
        gross_profit = sum(t.net_pnl for t in sorted_trades if t.net_pnl > 0)
        gross_loss = sum(abs(t.net_pnl) for t in sorted_trades if t.net_pnl < 0)
        net_profit = sum(t.net_pnl for t in sorted_trades)
        
        avg_trade = (net_profit / total_trades) if total_trades > 0 else 0.0
        avg_win = (gross_profit / winning_trades) if winning_trades > 0 else 0.0
        avg_loss = (gross_loss / losing_trades) if losing_trades > 0 else 0.0
        
        largest_win = max((t.net_pnl for t in sorted_trades), default=0.0)
        largest_loss = min((t.net_pnl for t in sorted_trades), default=0.0)

        # 3. Profit Factor
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)
        if gross_loss == 0 and gross_profit > 0:
            profit_factor = 99.9  # Cap at high value if no losses

        # 4. Expectancy
        # Formula: (WinRate/100 * AvgWin) - (LossRate/100 * AvgLoss)
        expectancy = ((win_rate / 100.0) * avg_win) - ((loss_rate / 100.0) * avg_loss)

        # 5. Payoff Ratio
        payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else (avg_win if avg_win > 0 else 1.0)

        # 6. Consecutive Streaks
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_win_streak = 0
        current_loss_streak = 0
        
        for t in sorted_trades:
            if t.net_pnl > 0:
                current_win_streak += 1
                current_loss_streak = 0
                max_consecutive_wins = max(max_consecutive_wins, current_win_streak)
            elif t.net_pnl < 0:
                current_loss_streak += 1
                current_win_streak = 0
                max_consecutive_losses = max(max_consecutive_losses, current_loss_streak)
            else:
                current_win_streak = 0
                current_loss_streak = 0

        # 7. Time Metrics & Exposure Time (Interval Merging to avoid double counting overlaps)
        hold_times = []
        intervals = []
        for pos in closed_positions:
            if pos.entry_time and pos.exit_time:
                duration = (pos.exit_time - pos.entry_time).total_seconds()
                hold_times.append(duration)
                intervals.append((pos.entry_time, pos.exit_time))
                
        avg_hold_time = statistics.mean(hold_times) if hold_times else 0.0
        shortest_hold_time = min(hold_times, default=0.0)
        longest_hold_time = max(hold_times, default=0.0)
        
        exposure_time = 0.0
        if intervals:
            intervals.sort(key=lambda x: x[0])
            merged = []
            current_start, current_end = intervals[0]
            for start, end in intervals[1:]:
                if start <= current_end:
                    current_end = max(current_end, end)
                else:
                    merged.append((current_start, current_end))
                    current_start, current_end = start, end
            merged.append((current_start, current_end))
            exposure_time = sum((end - start).total_seconds() for start, end in merged)

        # 8. Equity Curve Builder
        equity_curve = []
        
        # Prepend start point
        if total_trades > 0:
            start_ts = sorted_trades[0].entry_time - timedelta(seconds=1)
            equity_curve.append(EquityPoint(timestamp=start_ts, equity_value=self.initial_capital, trade_id=None))
            
        running_equity = self.initial_capital
        for t in sorted_trades:
            running_equity += t.net_pnl
            equity_curve.append(EquityPoint(timestamp=t.exit_time, equity_value=running_equity, trade_id=t.position_id))
            
        if not equity_curve:
            equity_curve.append(EquityPoint(timestamp=datetime.now(), equity_value=self.initial_capital, trade_id=None))

        # 9. Drawdown Engine (Peak-to-recovery duration)
        drawdown_curve = []
        running_peak = self.initial_capital
        peak_timestamp = equity_curve[0].timestamp if equity_curve else datetime.now()
        max_drawdown = 0.0
        max_drawdown_pct = 0.0
        max_drawdown_duration = 0.0
        
        for ep in equity_curve:
            # Duration since current peak was reached (drawdown duration up to this point/recovery)
            duration = (ep.timestamp - peak_timestamp).total_seconds()
            max_drawdown_duration = max(max_drawdown_duration, duration)

            if ep.equity_value > running_peak:
                running_peak = ep.equity_value
                peak_timestamp = ep.timestamp
                
            dd = running_peak - ep.equity_value
            dd_pct = (dd / running_peak * 100.0) if running_peak > 0 else 0.0
            
            max_drawdown = max(max_drawdown, dd)
            max_drawdown_pct = max(max_drawdown_pct, dd_pct)
            
            drawdown_curve.append(DrawdownPoint(
                timestamp=ep.timestamp,
                drawdown_value=dd,
                drawdown_pct=dd_pct,
                peak_value=running_peak
            ))

        # 10. Return Metrics & CAGR
        # 10. Return Metrics & CAGR
        final_equity = running_equity
        if self.initial_capital > 0:
            absolute_return_pct = ((final_equity - self.initial_capital) / self.initial_capital) * 100.0
        else:
            absolute_return_pct = 0.0
        net_return_pct = absolute_return_pct
        capital_growth_pct = absolute_return_pct
        
        if total_trades > 0:
            start_time = min(t.entry_time for t in sorted_trades)
            end_time = max(t.exit_time for t in sorted_trades)
            duration_days = (end_time - start_time).total_seconds() / 86400.0
            years = duration_days / 365.25
            
            if final_equity <= 0:
                cagr = -100.0
            elif years >= (1.0 / 365.25) and self.initial_capital > 0:  # At least 1 day duration to annualize CAGR
                cagr = ((final_equity / self.initial_capital) ** (1.0 / years) - 1.0) * 100.0
            else:
                cagr = absolute_return_pct
        else:
            cagr = 0.0

        # 11. Sharpe & Sortino Calculations
        # Group net trade PnLs by day
        daily_pnls = {}
        for t in sorted_trades:
            day_str = t.exit_time.strftime("%Y-%m-%d")
            daily_pnls[day_str] = daily_pnls.get(day_str, 0.0) + t.net_pnl
            
        unique_days = sorted(list(daily_pnls.keys()))
        
        if len(unique_days) > 1:
            # Multi-day Sharpe and Sortino (annualized daily method over weekdays to include flat days)
            start_date = min(t.entry_time for t in sorted_trades).date()
            end_date = max(t.exit_time for t in sorted_trades).date()
            
            all_days_pnls = []
            curr_date = start_date
            while curr_date <= end_date:
                if curr_date.weekday() < 5:  # Monday to Friday
                    day_str = curr_date.strftime("%Y-%m-%d")
                    all_days_pnls.append(daily_pnls.get(day_str, 0.0))
                curr_date += timedelta(days=1)
                
            if self.initial_capital > 0:
                daily_returns = [pnl / self.initial_capital for pnl in all_days_pnls]
            else:
                daily_returns = [0.0 for pnl in all_days_pnls]
            avg_daily_ret = statistics.mean(daily_returns)
            std_daily_ret = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0.0
            
            # Risk free rate (daily)
            daily_rf = self.risk_free_rate_annual / 252.0
            
            # Sharpe
            if std_daily_ret > 0:
                sharpe_ratio = ((avg_daily_ret - daily_rf) / std_daily_ret) * math.sqrt(252)
            else:
                sharpe_ratio = 0.0
                
            # Downside deviation
            downside_returns = [min(0.0, r - daily_rf) for r in daily_returns]
            downside_dev = math.sqrt(sum(r**2 for r in downside_returns) / len(downside_returns))
            
            # Sortino
            if downside_dev > 0:
                sortino_ratio = ((avg_daily_ret - daily_rf) / downside_dev) * math.sqrt(252)
            else:
                sortino_ratio = 0.0
        else:
            # Single-day backtest or single trade fallback: Trade-by-trade method
            if self.initial_capital > 0:
                trade_returns = [t.net_pnl / self.initial_capital for t in sorted_trades]
            else:
                trade_returns = [0.0 for t in sorted_trades]
            avg_trade_ret = statistics.mean(trade_returns) if trade_returns else 0.0
            std_trade_ret = statistics.stdev(trade_returns) if len(trade_returns) > 1 else 0.0
            
            # Sharpe (Assuming Rf = 0.0 per trade)
            if std_trade_ret > 0:
                sharpe_ratio = avg_trade_ret / std_trade_ret
            else:
                sharpe_ratio = 0.0
                
            # Downside deviation
            downside_trade_returns = [min(0.0, r) for r in trade_returns]
            downside_dev = math.sqrt(sum(r**2 for r in downside_trade_returns) / len(downside_trade_returns)) if downside_trade_returns else 0.0
            
            if downside_dev > 0:
                sortino_ratio = avg_trade_ret / downside_dev
            else:
                sortino_ratio = 0.0

        # 12. Scorecard & Grading Logic
        grade = "F"
        if net_profit > 0 and total_trades > 0:
            # Score components (1 to 4 scale)
            wr_score = 4 if win_rate >= 60 else (3 if win_rate >= 50 else (2 if win_rate >= 40 else 1))
            pf_score = 4 if profit_factor >= 2.0 else (3 if profit_factor >= 1.5 else (2 if profit_factor >= 1.1 else 1))
            sharpe_score = 4 if sharpe_ratio >= 2.0 else (3 if sharpe_ratio >= 1.5 else (2 if sharpe_ratio >= 1.0 else 1))
            dd_score = 4 if max_drawdown_pct <= 5 else (3 if max_drawdown_pct <= 10 else (2 if max_drawdown_pct <= 20 else 1))
            
            avg_score = (wr_score + pf_score + sharpe_score + dd_score) / 4.0
            
            if avg_score >= 3.5:
                grade = "A+"
            elif avg_score >= 3.0:
                grade = "A"
            elif avg_score >= 2.5:
                grade = "B"
            elif avg_score >= 2.0:
                grade = "C"
            elif avg_score >= 1.0:
                grade = "D"
            else:
                grade = "F"
                
        scorecard = {
            "total_trades": total_trades,
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "expectancy_inr": round(expectancy, 2),
            "net_profit_inr": round(net_profit, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "cagr_pct": round(cagr, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "sortino_ratio": round(sortino_ratio, 2)
        }

        # Pack report
        return MetricsReport(
            initial_capital=self.initial_capital,
            final_equity=final_equity,
            trade_stats=TradeStatistics(
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                breakeven_trades=breakeven_trades,
                win_rate=round(win_rate, 2),
                loss_rate=round(loss_rate, 2)
            ),
            performance=PerformanceMetrics(
                gross_profit=round(gross_profit, 2),
                gross_loss=round(gross_loss, 2),
                net_profit=round(net_profit, 2),
                avg_trade=round(avg_trade, 2),
                avg_win=round(avg_win, 2),
                avg_loss=round(avg_loss, 2),
                largest_win=round(largest_win, 2),
                largest_loss=round(largest_loss, 2),
                profit_factor=round(profit_factor, 2),
                expectancy=round(expectancy, 2),
                payoff_ratio=round(payoff_ratio, 2),
                max_consecutive_wins=max_consecutive_wins,
                max_consecutive_losses=max_consecutive_losses,
                avg_hold_time_seconds=round(avg_hold_time, 2),
                shortest_hold_time_seconds=round(shortest_hold_time, 2),
                longest_hold_time_seconds=round(longest_hold_time, 2),
                exposure_time_seconds=round(exposure_time, 2)
            ),
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve,
            max_drawdown=round(max_drawdown, 2),
            max_drawdown_pct=round(max_drawdown_pct, 2),
            max_drawdown_duration_seconds=round(max_drawdown_duration, 2),
            absolute_return_pct=round(absolute_return_pct, 2),
            net_return_pct=round(net_return_pct, 2),
            capital_growth_pct=round(capital_growth_pct, 2),
            cagr=round(cagr, 2),
            sharpe_ratio=round(sharpe_ratio, 2),
            sortino_ratio=round(sortino_ratio, 2),
            grade=grade,
            scorecard=scorecard
        )
