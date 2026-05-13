from __future__ import annotations

from typing import Any, Dict

import pandas as pd


REQUIRED_COLUMNS = {
    "month",
    "revenue",
    "cogs",
    "operating_expenses",
    "cash_balance",
    "budget_revenue",
    "actual_revenue",
    "budget_opex",
    "actual_opex",
}


class DataValidationError(ValueError):
    pass


def validate_and_prepare(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise DataValidationError(f"Missing required columns: {missing_list}")

    prepared = df.copy()
    prepared["month"] = pd.to_datetime(prepared["month"])
    prepared = prepared.sort_values("month").reset_index(drop=True)

    prepared["operating_income"] = (
        prepared["revenue"] - prepared["cogs"] - prepared["operating_expenses"]
    )
    prepared["operating_margin"] = prepared["operating_income"] / prepared["revenue"]
    prepared["burn_rate"] = (
        prepared["operating_expenses"] - prepared["revenue"]
    ).clip(lower=0)
    prepared["cash_runway_months"] = prepared.apply(
        lambda row: float("inf") if row["burn_rate"] == 0 else row["cash_balance"] / row["burn_rate"],
        axis=1,
    )

    prepared["revenue_variance"] = prepared["actual_revenue"] - prepared["budget_revenue"]
    prepared["revenue_variance_pct"] = prepared["revenue_variance"] / prepared["budget_revenue"]
    prepared["opex_variance"] = prepared["actual_opex"] - prepared["budget_opex"]
    prepared["opex_variance_pct"] = prepared["opex_variance"] / prepared["budget_opex"]

    return prepared


def compute_kpis(monthly_df: pd.DataFrame) -> Dict[str, Any]:
    latest = monthly_df.iloc[-1]
    previous = monthly_df.iloc[-2] if len(monthly_df) > 1 else latest

    revenue_mom = (
        (latest["revenue"] - previous["revenue"]) / previous["revenue"]
        if previous["revenue"] != 0
        else 0.0
    )

    runway = latest["cash_runway_months"]
    if runway == float("inf"):
        runway_label = "Sufficient (no net burn)"
    else:
        runway_label = f"{runway:.1f} months"

    return {
        "latest_month": latest["month"].strftime("%b %Y"),
        "revenue_latest": float(latest["revenue"]),
        "revenue_mom_pct": float(revenue_mom),
        "operating_margin_latest": float(latest["operating_margin"]),
        "cash_balance_latest": float(latest["cash_balance"]),
        "cash_runway_months": float(runway) if runway != float("inf") else None,
        "cash_runway_label": runway_label,
        "revenue_budget_variance": float(latest["revenue_variance"]),
        "revenue_budget_variance_pct": float(latest["revenue_variance_pct"]),
        "opex_budget_variance": float(latest["opex_variance"]),
        "opex_budget_variance_pct": float(latest["opex_variance_pct"]),
    }
