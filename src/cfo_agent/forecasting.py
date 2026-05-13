from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd


def _safe_pct(delta: float, base: float) -> float:
    return 0.0 if base == 0 else delta / base


def compute_forecast(monthly_df: pd.DataFrame, periods: int = 3) -> List[Dict[str, Any]]:
    if len(monthly_df) < 2:
        return []

    x = np.arange(len(monthly_df))
    forecast_records: List[Dict[str, Any]] = []

    revenue_coeff = np.polyfit(x, monthly_df["revenue"].astype(float), 1)
    margin_coeff = np.polyfit(x, monthly_df["operating_margin"].astype(float), 1)

    last_month = monthly_df.iloc[-1]["month"]
    for offset in range(1, periods + 1):
        index = len(monthly_df) + offset - 1
        revenue_pred = float(np.polyval(revenue_coeff, index))
        margin_pred = float(np.polyval(margin_coeff, index))
        revenue_pred = max(0.0, revenue_pred)
        margin_pred = max(-1.0, min(1.0, margin_pred))

        month = (last_month + pd.DateOffset(months=offset)).strftime("%b %Y")
        forecast_records.append(
            {
                "month": month,
                "revenue_forecast": revenue_pred,
                "operating_margin_forecast": margin_pred,
            }
        )

    return forecast_records


def detect_anomalies(monthly_df: pd.DataFrame) -> List[str]:
    findings: List[str] = []
    if len(monthly_df) < 4:
        return findings

    for metric, label in [
        ("revenue", "Revenue"),
        ("operating_margin", "Operating margin"),
        ("actual_opex", "Actual OpEx"),
    ]:
        series = monthly_df[metric].astype(float)
        mean = float(series.mean())
        std = float(series.std(ddof=0))
        if std == 0:
            continue

        z_scores = (series - mean) / std
        latest_z = float(z_scores.iloc[-1])
        latest_value = float(series.iloc[-1])
        latest_month = monthly_df.iloc[-1]["month"].strftime("%b %Y")

        if abs(latest_z) >= 2.0:
            direction = "above" if latest_z > 0 else "below"
            findings.append(
                f"{label} in {latest_month} is an anomaly ({direction} normal range, z={latest_z:.2f}, value={latest_value:,.2f})."
            )

    return findings


def summarize_forecast_and_anomalies(monthly_df: pd.DataFrame) -> Dict[str, Any]:
    forecast = compute_forecast(monthly_df, periods=3)
    anomalies = detect_anomalies(monthly_df)

    trend_signal = "stable"
    if forecast:
        rev_delta = forecast[-1]["revenue_forecast"] - float(monthly_df.iloc[-1]["revenue"])
        rev_pct = _safe_pct(rev_delta, float(monthly_df.iloc[-1]["revenue"]))
        if rev_pct > 0.05:
            trend_signal = "accelerating"
        elif rev_pct < -0.03:
            trend_signal = "cooling"

    return {
        "forecast": forecast,
        "anomalies": anomalies,
        "trend_signal": trend_signal,
    }


def build_scenario_narratives(monthly_df: pd.DataFrame) -> Dict[str, Any]:
    forecast = compute_forecast(monthly_df, periods=3)
    if not forecast:
        return {
            "best": "Insufficient history to estimate best-case scenario.",
            "base": "Insufficient history to estimate base-case scenario.",
            "worst": "Insufficient history to estimate worst-case scenario.",
            "assumptions": {
                "best_growth_uplift": 0.0,
                "base_growth_uplift": 0.0,
                "worst_growth_uplift": 0.0,
            },
        }

    latest_revenue = float(monthly_df.iloc[-1]["revenue"])
    latest_margin = float(monthly_df.iloc[-1]["operating_margin"])
    terminal = forecast[-1]

    base_revenue = float(terminal["revenue_forecast"])
    base_margin = float(terminal["operating_margin_forecast"])

    best_revenue = base_revenue * 1.08
    best_margin = min(1.0, base_margin + 0.02)

    worst_revenue = base_revenue * 0.92
    worst_margin = max(-1.0, base_margin - 0.03)

    rev_base_pct = _safe_pct(base_revenue - latest_revenue, latest_revenue) * 100
    rev_best_pct = _safe_pct(best_revenue - latest_revenue, latest_revenue) * 100
    rev_worst_pct = _safe_pct(worst_revenue - latest_revenue, latest_revenue) * 100

    return {
        "best": (
            f"Best case: revenue reaches ${best_revenue:,.0f} over the next 3 months "
            f"({rev_best_pct:+.1f}% vs current run-rate) with operating margin near {best_margin * 100:.1f}% "
            "assuming stronger conversion and tight spend control."
        ),
        "base": (
            f"Base case: revenue trends to ${base_revenue:,.0f} ({rev_base_pct:+.1f}%) with operating margin "
            f"around {base_margin * 100:.1f}% under current trajectory."
        ),
        "worst": (
            f"Worst case: revenue softens to ${worst_revenue:,.0f} ({rev_worst_pct:+.1f}%) and operating margin "
            f"compresses to {worst_margin * 100:.1f}% if demand slows and costs stay elevated."
        ),
        "assumptions": {
            "best_growth_uplift": 0.08,
            "base_growth_uplift": 0.00,
            "worst_growth_uplift": -0.08,
        },
    }
