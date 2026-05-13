from __future__ import annotations

from typing import Any, Dict, List


def generate_perks_and_insights(kpis: Dict[str, Any]) -> Dict[str, List[str]]:
    perks: List[str] = []
    risks: List[str] = []
    actions: List[str] = []

    rev_mom = kpis["revenue_mom_pct"]
    margin = kpis["operating_margin_latest"]
    runway = kpis["cash_runway_months"]
    rev_var = kpis["revenue_budget_variance_pct"]
    opex_var = kpis["opex_budget_variance_pct"]

    if rev_mom > 0.03:
        perks.append("Revenue growth momentum is strong month-over-month.")
    elif rev_mom >= 0:
        perks.append("Revenue is stable with positive trajectory.")
    else:
        risks.append("Revenue softened month-over-month.")

    if margin >= 0.2:
        perks.append("Operating margin is at a healthy board-grade level.")
    elif margin >= 0.1:
        perks.append("Operating margin remains resilient.")
    else:
        risks.append("Operating margin is under pressure.")

    if runway is None:
        perks.append("Cash profile indicates no immediate runway constraint.")
    elif runway >= 12:
        perks.append("Cash runway provides strong strategic flexibility.")
    elif runway >= 6:
        actions.append("Runway is moderate; monitor discretionary spend weekly.")
    else:
        risks.append("Cash runway is tight and requires near-term intervention.")
        actions.append("Prioritize collection acceleration and non-critical spend pause.")

    if rev_var >= 0:
        perks.append("Revenue outperformed or met budget expectations.")
    else:
        risks.append("Revenue is below budget target.")
        actions.append("Review pipeline conversion and pricing realization gaps.")

    if opex_var <= 0:
        perks.append("Operating expense discipline is aligned with budget.")
    else:
        risks.append("Operating expense overrun versus budget detected.")
        actions.append("Reforecast departmental spend and reset cost guardrails.")

    if not actions:
        actions.append("Sustain current trajectory while protecting margin quality.")

    return {"perks": perks, "risks": risks, "actions": actions}
