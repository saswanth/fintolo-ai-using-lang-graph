from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def _to_posix(path: str) -> str:
    return path.replace("\\", "/")


def build_report_markdown(
    company_name: str,
    period_label: str,
    kpis: Dict[str, Any],
    narrative: str,
    chart_paths: List[str],
) -> str:
    chart_map = {Path(p).name: _to_posix(p) for p in chart_paths}

    return f"""# {company_name} - CFO Monthly Performance One-Pager

**Period:** {period_label}

## Executive Summary
{narrative}

## KPI Snapshot
- Revenue: **${kpis['revenue_latest']:,.0f}**
- Revenue Growth (MoM): **{kpis['revenue_mom_pct'] * 100:+.1f}%**
- Operating Margin: **{kpis['operating_margin_latest'] * 100:.1f}%**
- Cash Balance: **${kpis['cash_balance_latest']:,.0f}**
- Cash Runway: **{kpis['cash_runway_label']}**
- Revenue vs Budget: **${kpis['revenue_budget_variance']:,.0f} ({kpis['revenue_budget_variance_pct'] * 100:+.1f}%)**
- OpEx vs Budget: **${kpis['opex_budget_variance']:,.0f} ({kpis['opex_budget_variance_pct'] * 100:+.1f}%)**

## Revenue Trend
![Revenue Trend]({chart_map['revenue_trend.png']})

## Operating Margin
![Operating Margin]({chart_map['operating_margin.png']})

## Cash Runway
![Cash Runway]({chart_map['cash_runway.png']})

## Budget vs Actuals
![Budget vs Actual]({chart_map['budget_vs_actual.png']})

## Board Discussion Prompts
1. Do current revenue and margin trajectories support full-year guidance?
2. Are current OpEx variances strategic (growth investment) or structural (cost drift)?
3. What actions are needed this month to improve runway resilience?
"""


def write_report(output_dir: str, markdown: str, period_label: str) -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    safe_period = period_label.replace(" ", "_")
    report_file = output_path / f"cfo_one_pager_{safe_period}.md"
    report_file.write_text(markdown, encoding="utf-8")
    return str(report_file)
