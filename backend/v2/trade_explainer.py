# [ignoring loop detection]
class TradeExplainer:
    """
    Formulates structured human-readable trade entry/exit explanations
    to be displayed directly in the trading desk UI and stored in SQLite.
    """
    @staticmethod
    def explain_entry(strategy_name: str, prev_ema: float, curr_ema: float, spot_price: float, condition: str = "Bullish Breakout") -> str:
        # Format the strategy name cleanly (e.g., 'five_ema' -> '5 EMA')
        display_strategy = "5 EMA"
        if "heikin" in strategy_name.lower():
            display_strategy = "Heikin Ashi"
        elif "ema" in strategy_name.lower():
            display_strategy = "5 EMA"
            
        return (
            f"{display_strategy} crossover detected\n"
            f"Previous EMA: {prev_ema:.2f}\n"
            f"Current EMA: {curr_ema:.2f}\n"
            f"Spot Price: {spot_price:.2f}\n"
            f"Condition: {condition}"
        ).strip()

    @staticmethod
    def explain_exit(reason_type: str, entry_premium: float, exit_premium: float) -> str:
        rr_suffix = ""
        # Map raw exit reasons to user-friendly titles
        display_reason = reason_type
        if reason_type in ["TARGET_LIMIT", "Target Hit"]:
            display_reason = "Target Hit"
            rr_suffix = "\nR:R Achieved"
        elif reason_type in ["STOP_LOSS", "Stop Loss Hit"]:
            display_reason = "Stop Loss Hit"
        elif reason_type in ["SESSION_END", "Intraday Cutoff Trigger"]:
            display_reason = "Intraday Cutoff Trigger"
        elif reason_type in ["MAX_DURATION", "Maximum Holding Reached"]:
            display_reason = "Maximum Holding Reached"

        return (
            f"{display_reason}\n"
            f"Entry Premium: {entry_premium:.2f}\n"
            f"Exit Premium: {exit_premium:.2f}{rr_suffix}"
        ).strip()
