from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class MonteCarloConfig(BaseModel):
    """Configuration for Monte Carlo simulations."""
    simulation_count: int = Field(..., description="Number of Monte Carlo runs")
    random_seed: Optional[int] = Field(None, description="Seed for reproducibility")
    slippage_variation_pct: float = Field(0.0, description="Maximum negative slippage percent to apply to trade PnL")
    commission_variation_pct: float = Field(0.0, description="Maximum increase in commission as percent of original charges")
    trade_order_shuffle: bool = Field(False, description="Randomly shuffle trade execution order")
    skip_trade_probability: float = Field(0.0, description="Probability of omitting a trade in a simulation (0‑1)")
    position_size_variation_pct: float = Field(0.0, description="Maximum variation percentage applied to trade quantity")
    combined_stress_test: bool = Field(False, description="Apply all variations simultaneously")

class SimulationMetrics(BaseModel):
    net_profit: float = Field(..., description="Total net profit of the simulation")
    max_drawdown_pct: float = Field(..., description="Maximum drawdown as percent of peak equity")
    profit_factor: float = Field(..., description="Profit factor (gross profit / gross loss)")
    win_rate: float = Field(..., description="Winning trades / total trades (0‑1)")
    trade_count: int = Field(..., description="Number of trades executed in the simulation")

class MonteCarloScore(BaseModel):
    overall_score: float = Field(..., description="Weighted overall Monte Carlo score out of 100")
    survival: float = Field(..., description="Survival component (40%)")
    drawdown_stability: float = Field(..., description="Drawdown stability component (30%)")
    profit_stability: float = Field(..., description="Profit stability component (20%)")
    risk_of_ruin: float = Field(..., description="Risk of ruin component (10%)")

class MonteCarloReport(BaseModel):
    config: MonteCarloConfig
    simulations: List[SimulationMetrics]
    robustness_metrics: Dict[str, Any]
    survival_analysis: Dict[str, Any]
    risk_of_ruin_score: float
    score: MonteCarloScore
    histogram_data: Dict[str, List[float]]
