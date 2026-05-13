"""
Fintolo Chat Agent  –  LangGraph-backed Q&A over the pipeline result.
Answers natural-language questions about spending, fraud, user health, trends.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict
from langgraph.graph import END, StateGraph
import pandas as pd


# ──────────────────────────────────────────────────────────────────
# Chat state
# ──────────────────────────────────────────────────────────────────

class ChatState(TypedDict, total=False):
    query: str
    pipeline_result: Dict[str, Any]
    response: str
    history: List[Dict[str, str]]   # [{"role": "user"|"assistant", "content": "..."}]


# ──────────────────────────────────────────────────────────────────
# Helper – safe KPI accessor
# ──────────────────────────────────────────────────────────────────

def _k(kpis: Dict, key: str, default: Any = "N/A") -> Any:
    return kpis.get(key, default)


# ──────────────────────────────────────────────────────────────────
# Router helpers
# ──────────────────────────────────────────────────────────────────

def _contains(query: str, *terms: str) -> bool:
    q = query.lower()
    return any(t in q for t in terms)


# ──────────────────────────────────────────────────────────────────
# Respond node
# ──────────────────────────────────────────────────────────────────

def respond_to_query(state: ChatState) -> ChatState:
    query = state.get("query", "").strip()
    result = state.get("pipeline_result", {})
    kpis: Dict[str, Any] = result.get("kpis", {})
    insights: List[str] = result.get("insights", [])

    q = query.lower()

    # ── Summary / overview ──
    if _contains(q, "summary", "overview", "executive", "report", "insights", "tell me about"):
        response = "**Fintolo Executive Summary**\n\n" + "\n\n".join(
            f"▸ {i}" for i in insights
        )

    # ── Spend / spending ──
    elif _contains(q, "total spend", "spending", "how much", "expenditure"):
        monthly: Optional[pd.DataFrame] = result.get("monthly_spend_df")
        top_line = (
            f"**Total spend analysed:** ${_k(kpis,'total_spend',0):,.0f} "
            f"across **{_k(kpis,'total_transactions',0):,}** transactions "
            f"({_k(kpis,'months_covered','?')} months).\n"
        )
        if monthly is not None and not monthly.empty:
            latest = monthly.iloc[-1]
            top_line += (
                f"\n**Latest month ({latest['year_month']}):** "
                f"${latest['total_spend']:,.0f} in {int(latest['txn_count']):,} transactions."
            )
        response = top_line

    # ── Category ──
    elif _contains(q, "categor", "mcc", "type of spend", "where is money"):
        cat_df: Optional[pd.DataFrame] = result.get("category_spend_df")
        if cat_df is not None and not cat_df.empty:
            top5 = cat_df.head(5)
            lines = [f"| {r['mcc_label']} | ${r['total_spend']:,.0f} |" for _, r in top5.iterrows()]
            response = (
                "**Top Spending Categories**\n\n"
                "| Category | Total Spend |\n|---|---|\n" + "\n".join(lines)
            )
        else:
            response = f"Top category: **{_k(kpis,'top_category')}** (${_k(kpis,'top_category_spend',0):,.0f})."

    # ── Fraud ──
    elif _contains(q, "fraud", "flag", "suspicious", "dark web", "error", "risk"):
        fraud_df: Optional[pd.DataFrame] = result.get("fraud_flags_df")
        count = _k(kpis, "fraud_flagged_count", 0)
        pct = _k(kpis, "fraud_flag_pct", 0)
        response = (
            f"**Fraud & Risk Signals**\n\n"
            f"▸ **{count:,}** transactions flagged ({pct:.2f}% of sample).\n"
        )
        if fraud_df is not None and not fraud_df.empty:
            reasons = fraud_df["flag_reason"].value_counts().head(5)
            response += "\n**Top flag reasons:**\n" + "\n".join(
                f"- {r}: {c:,}" for r, c in reasons.items()
            )

    # ── User health ──
    elif _contains(q, "health", "credit score", "debt", "dti", "user", "customer", "stressed"):
        response = (
            f"**User Financial Health**\n\n"
            f"▸ Average credit score: **{_k(kpis,'avg_credit_score','N/A')}**\n"
            f"▸ Average debt-to-income (DTI): **{_k(kpis,'avg_dti','N/A')}**\n"
            f"▸ Average credit utilisation: **{_k(kpis,'avg_credit_utilisation','N/A')}**\n\n"
            f"**Segments:**\n"
            f"- 🟢 Healthy: {_k(kpis,'pct_healthy',0):.1f}%\n"
            f"- 🟡 At-Risk: {_k(kpis,'pct_at_risk',0):.1f}%\n"
            f"- 🔴 Stressed: {_k(kpis,'pct_stressed',0):.1f}%"
        )

    # ── Cards ──
    elif _contains(q, "card", "visa", "mastercard", "chip", "debit", "credit card"):
        response = (
            f"**Card Portfolio**\n\n"
            f"▸ Unique cards in use: **{_k(kpis,'unique_cards',0):,}**\n"
            f"▸ Chip transaction rate: **{_k(kpis,'chip_usage_pct',0):.1f}%**\n\n"
            "Higher chip usage correlates with lower card-present fraud rates."
        )

    # ── Merchants ──
    elif _contains(q, "merchant", "store", "retailer", "vendor"):
        merch: Optional[pd.DataFrame] = result.get("merchant_top_df")
        if merch is not None and not merch.empty:
            top5 = merch.head(5)
            lines = [
                f"| {int(r['merchant_id'])} | ${r['total_spend']:,.0f} | {int(r['txn_count']):,} txns |"
                for _, r in top5.iterrows()
            ]
            response = (
                "**Top Merchants by Spend**\n\n"
                "| Merchant ID | Total Spend | Transactions |\n|---|---|---|\n" + "\n".join(lines)
            )
        else:
            response = "Merchant data is not available in the current run."

    # ── Average / mean ──
    elif _contains(q, "average", "mean", "typical"):
        response = (
            f"**Average Transaction:** ${_k(kpis,'avg_transaction',0):.2f}\n"
            f"**Average Credit Score:** {_k(kpis,'avg_credit_score','N/A')}\n"
            f"**Average DTI Ratio:** {_k(kpis,'avg_dti','N/A')}"
        )

    # ── Trend / monthly ──
    elif _contains(q, "trend", "monthly", "over time", "month", "growth"):
        monthly = result.get("monthly_spend_df")
        if monthly is not None and len(monthly) >= 2:
            first = monthly.iloc[0]
            last = monthly.iloc[-1]
            change = ((last["total_spend"] - first["total_spend"]) / max(first["total_spend"], 1)) * 100
            response = (
                f"**Spending Trend**\n\n"
                f"From **{first['year_month']}** (${first['total_spend']:,.0f}) "
                f"to **{last['year_month']}** (${last['total_spend']:,.0f})\n\n"
                f"Overall change: **{change:+.1f}%** over {len(monthly)} months."
            )
        else:
            response = "Not enough monthly data to compute a trend."

    # ── Help ──
    elif _contains(q, "help", "what can you", "capabilities", "commands"):
        response = (
            "**Fintolo Chatbot — What I can answer:**\n\n"
            "- 📊 **Spending overview** — total spend, transactions, averages\n"
            "- 📁 **Categories** — top MCC spending categories\n"
            "- 🏪 **Merchants** — top merchants by volume\n"
            "- 🚨 **Fraud & risk** — flagged transactions, dark web cards\n"
            "- 💳 **Cards** — chip usage, card portfolio\n"
            "- 👤 **User health** — credit scores, DTI, segments\n"
            "- 📈 **Trends** — monthly spending trajectory\n"
            "- 📋 **Summary** — executive one-liner insight report\n\n"
            "Just ask in plain English!"
        )

    else:
        response = (
            f"I didn't find a specific answer for **\"{query}\"**.\n\n"
            "Try asking about: *spending, fraud, categories, merchants, user health, "
            "credit scores, card chip usage, monthly trends,* or type **help** for the full list."
        )

    history = state.get("history", [])
    history = history + [
        {"role": "user", "content": query},
        {"role": "assistant", "content": response},
    ]
    return {**state, "response": response, "history": history}


# ──────────────────────────────────────────────────────────────────
# Build chat graph
# ──────────────────────────────────────────────────────────────────

def build_chat_graph():
    g = StateGraph(ChatState)
    g.add_node("respond", respond_to_query)
    g.set_entry_point("respond")
    g.add_edge("respond", END)
    return g.compile()


_CHAT_GRAPH = build_chat_graph()


def ask_fintolo(
    query: str,
    pipeline_result: Dict[str, Any],
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    state: ChatState = {
        "query": query,
        "pipeline_result": pipeline_result,
        "history": history or [],
    }
    out = _CHAT_GRAPH.invoke(state)
    return out["response"]
