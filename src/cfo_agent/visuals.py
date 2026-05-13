from __future__ import annotations

from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import pandas as pd


def build_charts(monthly_df: pd.DataFrame, output_dir: str) -> List[str]:
    chart_dir = Path(output_dir) / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)

    paths: List[str] = []

    # Revenue trend chart
    revenue_chart = chart_dir / "revenue_trend.png"
    plt.figure(figsize=(8, 4))
    plt.plot(monthly_df["month"], monthly_df["revenue"], marker="o", linewidth=2)
    plt.title("Revenue Trend")
    plt.ylabel("Revenue")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(revenue_chart, dpi=160)
    plt.close()
    paths.append(str(revenue_chart))

    # Operating margin chart
    margin_chart = chart_dir / "operating_margin.png"
    plt.figure(figsize=(8, 4))
    plt.plot(
        monthly_df["month"],
        monthly_df["operating_margin"] * 100,
        marker="o",
        linewidth=2,
        color="#2E8B57",
    )
    plt.title("Operating Margin (%)")
    plt.ylabel("Margin %")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(margin_chart, dpi=160)
    plt.close()
    paths.append(str(margin_chart))

    # Cash runway chart
    runway_chart = chart_dir / "cash_runway.png"
    runway_values = monthly_df["cash_runway_months"].replace(float("inf"), pd.NA)
    plt.figure(figsize=(8, 4))
    plt.bar(monthly_df["month"].dt.strftime("%b %y"), runway_values.fillna(0), color="#1F77B4")
    plt.title("Cash Runway (Months)")
    plt.ylabel("Months")
    plt.xticks(rotation=30)
    plt.grid(alpha=0.25, axis="y")
    plt.tight_layout()
    plt.savefig(runway_chart, dpi=160)
    plt.close()
    paths.append(str(runway_chart))

    # Budget vs actual chart (latest month)
    latest = monthly_df.iloc[-1]
    budget_chart = chart_dir / "budget_vs_actual.png"
    categories = ["Revenue", "OpEx"]
    budget_vals = [latest["budget_revenue"], latest["budget_opex"]]
    actual_vals = [latest["actual_revenue"], latest["actual_opex"]]

    x_positions = range(len(categories))
    width = 0.35

    plt.figure(figsize=(8, 4))
    plt.bar([x - width / 2 for x in x_positions], budget_vals, width=width, label="Budget")
    plt.bar([x + width / 2 for x in x_positions], actual_vals, width=width, label="Actual")
    plt.xticks(list(x_positions), categories)
    plt.title("Budget vs Actual (Latest Month)")
    plt.ylabel("Amount")
    plt.legend()
    plt.grid(alpha=0.25, axis="y")
    plt.tight_layout()
    plt.savefig(budget_chart, dpi=160)
    plt.close()
    paths.append(str(budget_chart))

    return paths
