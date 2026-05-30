from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

class ParameterRange(BaseModel):
    name: str = Field(..., description="The name of the strategy parameter.")
    type: Literal["int", "float", "enum"] = Field(..., description="The type of parameter range.")
    min_val: Optional[float] = Field(default=None, description="Minimum value for numerical ranges.")
    max_val: Optional[float] = Field(default=None, description="Maximum value for numerical ranges.")
    step: Optional[float] = Field(default=None, description="Step size for numerical ranges.")
    options: Optional[List[Any]] = Field(default=None, description="Explicit choices for enum type ranges.")

class ParameterCombination(BaseModel):
    params: Dict[str, Any] = Field(..., description="Concrete parameter mapping (parameter name -> value).")

class OptimizationResult(BaseModel):
    combination: ParameterCombination = Field(..., description="The evaluated parameter combination.")
    net_profit: float = Field(..., description="Net Profit (INR) from the backtest.")
    win_rate: float = Field(..., description="Win Rate Percentage (%).")
    profit_factor: float = Field(..., description="Profit Factor.")
    expectancy: float = Field(..., description="Expectancy (INR).")
    max_drawdown: float = Field(..., description="Maximum drawdown in value (INR).")
    max_drawdown_pct: float = Field(..., description="Maximum drawdown in percentage (%).")
    sharpe_ratio: float = Field(..., description="Calculated Sharpe Ratio.")
    sortino_ratio: float = Field(..., description="Calculated Sortino Ratio.")
    trade_count: int = Field(..., description="Total trades executed.")
    composite_score: float = Field(..., description="Calculated Composite Score.")

class OptimizationRun(BaseModel):
    run_id: str = Field(..., description="Unique run identifier.")
    start_time: str = Field(..., description="Execution start timestamp.")
    end_time: Optional[str] = Field(default=None, description="Execution end timestamp.")
    config: Dict[str, Any] = Field(..., description="Reference base backtest configuration dictionary.")
    total_combinations: int = Field(..., description="Total generated combinations in the grid.")
    executed_combinations: int = Field(..., description="Number of successfully run backtests.")
    skipped_combinations: int = Field(..., description="Number of rejected combinations.")
    skipped_details: Dict[str, str] = Field(default_factory=dict, description="Rejection logs: string representation of parameters -> rejection reason.")
    results: List[OptimizationResult] = Field(default_factory=list, description="Performance results for executed parameter sets.")

class OptimizationReport(BaseModel):
    run_info: OptimizationRun = Field(..., description="Execution summary of the optimization run.")
    top_10: List[OptimizationResult] = Field(default_factory=list, description="Top 10 performing parameter sets.")
    top_25: List[OptimizationResult] = Field(default_factory=list, description="Top 25 performing parameter sets.")
    top_50: List[OptimizationResult] = Field(default_factory=list, description="Top 50 performing parameter sets.")
    heatmap_data: Dict[str, Any] = Field(default_factory=dict, description="Matrix mapping of two parameters to target metrics.")
    stability_findings: Dict[str, Any] = Field(default_factory=dict, description="Sensitivity analysis of neighboring parameters.")
