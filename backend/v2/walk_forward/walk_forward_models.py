from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class WalkForwardConfig(BaseModel):
    training_window_days: int = Field(..., description="Duration of training phase in days")
    testing_window_days: int = Field(..., description="Duration of out-of-sample testing phase in days")
    step_size_days: int = Field(..., description="Rolling window step size in days")
    min_trades_required: int = Field(default=1, description="Minimum trades required in training/testing to be valid")
    optimization_enabled: bool = Field(default=True, description="Whether to optimize parameters on training window")

class WalkForwardCycle(BaseModel):
    cycle_index: int = Field(..., description="0-indexed cycle indicator")
    train_start: str = Field(..., description="Start date of training window (YYYY-MM-DD)")
    train_end: str = Field(..., description="End date of training window (YYYY-MM-DD)")
    test_start: str = Field(..., description="Start date of testing window (YYYY-MM-DD)")
    test_end: str = Field(..., description="End date of testing window (YYYY-MM-DD)")
    selected_parameters: Dict[str, Any] = Field(..., description="Parameters selected from optimization in training window")
    train_metrics: Dict[str, Any] = Field(default_factory=dict, description="Performance metrics on training window")
    test_metrics: Dict[str, Any] = Field(default_factory=dict, description="Performance metrics on testing window")

class WalkForwardScore(BaseModel):
    overall_score: float = Field(..., description="Weighted Walk Forward Score (0-100)")
    test_profitability: float = Field(..., description="40% component: Out-of-sample profitability score")
    consistency: float = Field(..., description="30% component: Out-of-sample win consistency score")
    drawdown_score: float = Field(..., description="20% component: Out-of-sample drawdown mitigation score")
    parameter_stability: float = Field(..., description="10% component: Parameter stability score")

class WalkForwardReport(BaseModel):
    config: WalkForwardConfig = Field(..., description="Configuration parameters used")
    cycles: List[WalkForwardCycle] = Field(..., description="List of walk forward cycles executed")
    score: WalkForwardScore = Field(..., description="Walk Forward Performance Score")
    stability_analysis: Dict[str, Any] = Field(default_factory=dict, description="Parameter stability insights")
    status: str = Field(..., description="PASS or FAIL status")
