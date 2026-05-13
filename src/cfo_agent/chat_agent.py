from __future__ import annotations

from typing import Any, Dict, List, TypedDict

import pandas as pd
from langgraph.graph import END, StateGraph

from .forecasting import build_scenario_narratives, summarize_forecast_and_anomalies
from .insights import generate_perks_and_insights


class ChatState(TypedDict, total=False):
    company_name: str
    query: str
    kpis: Dict[str, Any]
    monthly_df: pd.DataFrame
    answer: str


def _format_currency(value: float) -> str:
    return f"${value:,.0f}"


def _default_answer(state: ChatState) -> str:
    kpis = state["kpis"]
    insights = generate_perks_and_insights(kpis)
    forecast_summary = summarize_forecast_and_anomalies(state["monthly_df"])
    perks = " ".join(insights["perks"][:3])
    trend = forecast_summary["trend_signal"]
    return (
        f"{state['company_name']} performance snapshot for {kpis['latest_month']}: "
        f"Revenue {_format_currency(kpis['revenue_latest'])}, operating margin {kpis['operating_margin_latest'] * 100:.1f}%, "
        f"and cash runway {kpis['cash_runway_label']}. Trend outlook is {trend}. Key perks: {perks}"
    )


def respond_to_query(state: ChatState) -> ChatState:
    query = state["query"].lower()
    kpis = state["kpis"]
    insights = generate_perks_and_insights(kpis)
    forecast_summary = summarize_forecast_and_anomalies(state["monthly_df"])
    scenarios = build_scenario_narratives(state["monthly_df"])

    if "revenue" in query:
        answer = (
            f"Revenue in {kpis['latest_month']} is {_format_currency(kpis['revenue_latest'])} "
            f"with {kpis['revenue_mom_pct'] * 100:+.1f}% month-over-month movement."
        )
    elif "margin" in query or "profit" in query:
        answer = f"Operating margin is {kpis['operating_margin_latest'] * 100:.1f}% for {kpis['latest_month']}."
    elif "runway" in query or "cash" in query:
        answer = f"Current cash position is {_format_currency(kpis['cash_balance_latest'])} with runway {kpis['cash_runway_label']}."
    elif "budget" in query or "variance" in query:
        answer = (
            f"Revenue variance: {_format_currency(kpis['revenue_budget_variance'])} "
            f"({kpis['revenue_budget_variance_pct'] * 100:+.1f}%). "
            f"OpEx variance: {_format_currency(kpis['opex_budget_variance'])} "
            f"({kpis['opex_budget_variance_pct'] * 100:+.1f}%)."
        )
    elif "forecast" in query or "projection" in query or "trend" in query:
        forecast = forecast_summary["forecast"]
        if not forecast:
            answer = "Insufficient history for forecasting. Add at least two months of financial records."
        else:
            lines = []
            for item in forecast:
                lines.append(
                    f"{item['month']}: revenue forecast {_format_currency(item['revenue_forecast'])}, "
                    f"operating margin forecast {item['operating_margin_forecast'] * 100:.1f}%"
                )
            answer = "3-month outlook: " + " | ".join(lines)
    elif "scenario" in query or "best" in query or "worst" in query or "base" in query:
        answer = (
            f"{scenarios['best']} "
            f"{scenarios['base']} "
            f"{scenarios['worst']}"
        )
    elif "anomaly" in query or "outlier" in query or "abnormal" in query:
        anomalies = forecast_summary["anomalies"]
        if anomalies:
            answer = "Anomaly scan findings: " + " ".join(anomalies)
        else:
            answer = "No statistical anomalies detected in the latest period across revenue, margin, and OpEx."
    elif "perk" in query or "insight" in query or "overall" in query:
        answer = (
            "Top perks: " + " ".join(insights["perks"]) + " "
            "Key risks: " + " ".join(insights["risks"]) + " "
            "Recommended actions: " + " ".join(insights["actions"]) + " "
            f"Forecast trend signal: {forecast_summary['trend_signal']}."
        )
    else:
        answer = _default_answer(state)

    return {"answer": answer}


def build_chat_graph():
    graph = StateGraph(ChatState)
    graph.add_node("respond_to_query", respond_to_query)
    graph.set_entry_point("respond_to_query")
    graph.add_edge("respond_to_query", END)
    return graph.compile()


def answer_finance_question(
    company_name: str,
    query: str,
    kpis: Dict[str, Any],
    monthly_df: pd.DataFrame,
) -> str:
    chat_graph = build_chat_graph()
    result: ChatState = chat_graph.invoke(
        {
            "company_name": company_name,
            "query": query,
            "kpis": kpis,
            "monthly_df": monthly_df,
        }
    )
    return result["answer"]
