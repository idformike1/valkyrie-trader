from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class StrategyParameterMetadata(BaseModel):
    name: str = Field(..., description="Parameter parameter key identifier")
    type: str = Field(..., description="Parameter data type (int, float, str, bool)")
    default: Any = Field(..., description="Default value if not overridden")
    description: str = Field(..., description="Description of parameter influence")

class StrategyMetadata(BaseModel):
    id: str = Field(..., description="Strategy identifier")
    name: str = Field(..., description="Strategy name for UI presentation")
    category: str = Field(..., description="Trading style categorization")
    description: str = Field(..., description="Detailed description of operation")
    market_type: str = Field(..., description="Target market regime")
    recommended_timeframes: List[str] = Field(..., description="Optimal candlestick resolutions")
    risk_level: str = Field(..., description="Risk profile")
    expected_trade_frequency: str = Field(..., description="Estimated trades per session")
    entry_logic: str = Field(..., description="Entry rule mechanism description")
    exit_logic: str = Field(..., description="Exit trigger rule description")
    strike_selection_logic: str = Field(..., description="strike resolution method description")
    expiry_selection_logic: str = Field(..., description="expiry date filtering description")
    stop_loss_logic: str = Field(..., description="Default risk mitigation stop-loss strategy")
    target_logic: str = Field(..., description="Take profit logic details")
    supported_parameters: List[StrategyParameterMetadata] = Field(..., description="Custom parameters list")
    strengths: List[str] = Field(..., description="Key strategy advantages")
    weaknesses: List[str] = Field(..., description="Key strategy drawbacks")
    best_market_conditions: str = Field(..., description="Ideal environment")
    worst_market_conditions: str = Field(..., description="Unfavorable environment")

# Define the central strategy metadata dictionary
STRATEGY_METADATA_STORE: Dict[str, StrategyMetadata] = {
    "five_ema": StrategyMetadata(
        id="five_ema",
        name="Five EMA Option Scalping",
        category="Scalping / Momentum",
        description="A high-speed options scalping strategy targeting quick price impulses based on deviation from the 5-period Exponential Moving Average (EMA).",
        market_type="Trending / High Volatility",
        recommended_timeframes=["1m", "5m"],
        risk_level="High",
        expected_trade_frequency="High (5-15 trades per session)",
        entry_logic="Enters LONG when a candle's low is completely above the 5 EMA band (representing extreme trend deviation) and subsequently breaks the high of the alert candle.",
        exit_logic="Exits when the price crosses back to the 5 EMA, hits a trailing stop, reaches target, or at the cut-off time.",
        strike_selection_logic="Selects strike dynamically based on ATM or OTM_1 to maximize options premium responsiveness.",
        expiry_selection_logic="Targets the closest weekly expiry contract to exploit high options gamma.",
        stop_loss_logic="Stop loss is placed at the swing low/high of the trigger candle or based on a pre-defined percentage/point value.",
        target_logic="Targets a custom risk-reward ratio (e.g. 1:3) or a trailing SL trigger.",
        supported_parameters=[
            StrategyParameterMetadata(name="five_ema_period", type="int", default=5, description="EMA period to identify trend deviations"),
            StrategyParameterMetadata(name="five_ema_rr", type="float", default=3.0, description="Risk-Reward multiplier for profit target calculation"),
            StrategyParameterMetadata(name="max_candles", type="int", default=10, description="Maximum holding duration in candle bars"),
            StrategyParameterMetadata(name="cut_off_time", type="str", default="15:15", description="Mandatory time of day to square off all open positions")
        ],
        strengths=["Captures high-velocity momentum swings", "Limits downside via tight stops", "Exploits option delta acceleration"],
        weaknesses=["Prone to whipsaws in sideways/consolidating markets", "Highly sensitive to brokerage charges due to trade volume"],
        best_market_conditions="Strong intraday trends, high options volume, post-breakout momentum",
        worst_market_conditions="Tight range-bound chop, low volume sessions"
    ),
    "ema": StrategyMetadata(
        id="ema",
        name="EMA Trend Crossover",
        category="Trend Following",
        description="A systematic trend-following strategy designed to capture medium-term direction shifts by tracking crossovers of fast and slow Exponential Moving Averages.",
        market_type="Trending",
        recommended_timeframes=["5m", "15m"],
        risk_level="Medium",
        expected_trade_frequency="Low to Medium (1-3 trades per day)",
        entry_logic="Enters LONG when the fast EMA crosses above the slow EMA from below.",
        exit_logic="Exits when the fast EMA crosses below the slow EMA, or when the session cutoff time is reached.",
        strike_selection_logic="ATM strike selection by default to maintain stable delta exposure.",
        expiry_selection_logic="Weekly expiry contract to balance time decay (theta) and delta gains.",
        stop_loss_logic="Defined by the crossover point or a fixed percentage of option entry price.",
        target_logic="Held open until a crossover reversal or time cutoff occurs (unlimited target).",
        supported_parameters=[
            StrategyParameterMetadata(name="fast_period", type="int", default=9, description="Fast EMA lookback period"),
            StrategyParameterMetadata(name="slow_period", type="int", default=21, description="Slow EMA lookback period"),
            StrategyParameterMetadata(name="cut_off_time", type="str", default="15:25", description="Mandatory session square-off cutoff time")
        ],
        strengths=["Enjoys big wins during sustained trending runs", "Simple objective entry and exit triggers"],
        weaknesses=["Experiences drawdown streaks during range-bound consolidating periods"],
        best_market_conditions="Sustained, clean intraday directional trends",
        worst_market_conditions="Whipsawing, sideways markets"
    ),
    "heikin_ashi": StrategyMetadata(
        id="heikin_ashi",
        name="Heikin Ashi GAR Strategy",
        category="Reversal / Momentum",
        description="A smoothing momentum strategy using Heikin Ashi candlesticks to filter market noise and capture strong trend extensions and key reversals.",
        market_type="Mean Reverting / Trending",
        recommended_timeframes=["1m", "5m"],
        risk_level="Medium",
        expected_trade_frequency="Medium (2-5 trades per session)",
        entry_logic="Enters when a strong green/red Heikin Ashi candle (flat bottom/top respectively) forms after a period of consolidation or trend shift.",
        exit_logic="Exits when an opposing candle type appears or session cutoff time is hit.",
        strike_selection_logic="Dynamically targets ATM strikes.",
        expiry_selection_logic="Targets current weekly options contract.",
        stop_loss_logic="Dynamic trailing stop loss based on the prior candle's extreme price.",
        target_logic="Trailing exits to ride the full duration of a clean trend.",
        supported_parameters=[
            StrategyParameterMetadata(name="candle_limit", type="int", default=10, description="Maximum holding duration limit in bars"),
            StrategyParameterMetadata(name="cut_off_time", type="str", default="15:25", description="Time of day to exit remaining open positions")
        ],
        strengths=["Noise reduction through Heikin Ashi formula", "Excellent trailing exit efficiency"],
        weaknesses=["Entry signal delays due to averaging calculations can lead to poor entry fills during flash moves"],
        best_market_conditions="Clean trends with consistent follow-through",
        worst_market_conditions="Alternating red/green noise in choppy sideways markets"
    )
}

# Alias mapping to ensure query matches work for various naming conventions
STRATEGY_ALIAS_MAP = {
    "five_ema_scalping": "five_ema",
    "five_ema": "five_ema",
    "ema": "ema",
    "ema_crossover": "ema",
    "heikin_ashi": "heikin_ashi",
    "heikin_ashi_gar": "heikin_ashi"
}

def get_strategy_metadata(strategy_id: str) -> Optional[StrategyMetadata]:
    """
    Get detailed strategy metadata by ID or alias.
    """
    normalized_id = STRATEGY_ALIAS_MAP.get(strategy_id.lower())
    if not normalized_id:
        return None
    return STRATEGY_METADATA_STORE.get(normalized_id)

def get_all_strategy_metadata() -> List[StrategyMetadata]:
    """
    Get a list of all registered strategies.
    """
    return list(STRATEGY_METADATA_STORE.values())
