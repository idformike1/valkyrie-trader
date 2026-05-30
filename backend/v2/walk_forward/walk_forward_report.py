import os
from datetime import datetime
from typing import List

from v2.walk_forward.walk_forward_models import WalkForwardReport, WalkForwardCycle

def _format_metrics(metrics: dict) -> str:
    if not metrics:
        return "-"
    lines = []
    for k, v in metrics.items():
        lines.append(f"{k.replace('_', ' ').title()}: {v:.2f}")
    return " | ".join(lines)

def generate_markdown_report(report: WalkForwardReport, output_path: str) -> None:
    """Writes a human‑readable markdown report for the walk‑forward run.

    The report includes window details, selected EMA parameters, training & testing
    metrics, the aggregated WalkForwardScore and a PASS/FAIL status.
    """
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
    lines: List[str] = []
    lines.append("# Walk Forward Validation Report")
    lines.append("")
    lines.append(f"Generated on: {now}")
    lines.append("")
    lines.append("## Configuration")
    cfg = report.config
    lines.append(f"- Training window days: {cfg.training_window_days}")
    lines.append(f"- Testing window days: {cfg.testing_window_days}")
    lines.append(f"- Step size days: {cfg.step_size_days}")
    lines.append(f"- Minimum trades required: {cfg.min_trades_required}")
    lines.append(f"- Optimization enabled: {cfg.optimization_enabled}")
    lines.append("")
    lines.append("## Cycles")
    for cyc in report.cycles:
        lines.append(f"### Cycle {cyc.cycle_index + 1}")
        lines.append(f"- Training: {cyc.train_start} → {cyc.train_end}")
        lines.append(f"- Testing: {cyc.test_start} → {cyc.test_end}")
        lines.append(f"- Selected Parameters: {cyc.selected_parameters or 'None'}")
        lines.append(f"- Training Metrics: {_format_metrics(cyc.train_metrics)}")
        lines.append(f"- Testing Metrics: {_format_metrics(cyc.test_metrics)}")
        lines.append("")
    lines.append("## Walk Forward Score")
    sc = report.score
    lines.append(f"- Overall Score (100): {sc.overall_score}")
    lines.append(f"- Test Profitability (40%): {sc.test_profitability}")
    lines.append(f"- Consistency (30%): {sc.consistency}")
    lines.append(f"- Drawdown Score (20%): {sc.drawdown_score}")
    lines.append(f"- Parameter Stability (10%): {sc.parameter_stability}")
    lines.append("")
    lines.append(f"**Status:** **{report.status}**")
    lines.append("")
    # Write file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Walk Forward report written to {output_path}")
