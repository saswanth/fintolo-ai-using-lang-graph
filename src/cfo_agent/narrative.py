from __future__ import annotations

from typing import Any, Dict


def _performance_signal(kpis: Dict[str, Any]) -> str:
    margin = kpis["operating_margin_latest"]
    rev_mom = kpis["revenue_mom_pct"]

    if margin >= 0.20 and rev_mom > 0:
        return "Strong"
    if margin >= 0.10 and rev_mom >= -0.02:
        return "Stable"
    return "Needs Attention"


def build_narrative(kpis: Dict[str, Any], company_name: str) -> str:
    signal = _performance_signal(kpis)

    runway_note = (
        f"Cash runway is approximately {kpis['cash_runway_months']:.1f} months."
        if kpis["cash_runway_months"] is not None
        else "Business is cash-flow positive with no immediate runway constraint."
    )

    return (
        f"{company_name} delivered a {signal.lower()} monthly close in {kpis['latest_month']}. "
        f"Revenue closed at ${kpis['revenue_latest']:,.0f} "
        f"({kpis['revenue_mom_pct'] * 100:+.1f}% MoM), while operating margin was "
        f"{kpis['operating_margin_latest'] * 100:.1f}%. "
        f"{runway_note} "
        f"Revenue variance to budget was ${kpis['revenue_budget_variance']:,.0f} "
        f"({kpis['revenue_budget_variance_pct'] * 100:+.1f}%), and OpEx variance was "
        f"${kpis['opex_budget_variance']:,.0f} ({kpis['opex_budget_variance_pct'] * 100:+.1f}%)."
    )
