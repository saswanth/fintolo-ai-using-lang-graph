"""
╔══════════════════════════════════════════════════════════════════╗
║          FINTOLO  –  LangGraph Financial Analysis Pipeline       ║
║  Datasets: transactions_data.csv  users_data.csv  cards_data.csv ║
╚══════════════════════════════════════════════════════════════════╝

LangGraph StateGraph  (8 nodes, sequential + conditional edges)

         ┌─────────────┐
         │  load_data  │  ← reads sampled transactions + users + cards
         └──────┬──────┘
                │
         ┌──────▼──────┐
         │ enrich_data │  ← join txn ↔ users ↔ cards on client_id / card_id
         └──────┬──────┘
                │
    ┌───────────▼───────────┐
    │ compute_spending_kpis │  ← monthly totals, top merchants, category spend
    └───────────┬───────────┘
                │
    ┌───────────▼───────────┐
    │  detect_fraud_signals │  ← error flags, z-score outliers, card-on-dark-web
    └───────────┬───────────┘
                │
    ┌───────────▼───────────┐
    │ score_financial_health│  ← per-user debt-to-income, credit utilisation
    └───────────┬───────────┘
                │
    ┌───────────▼───────────┐
    │ segment_users         │  ← cluster into: Healthy / At-Risk / Stressed
    └───────────┬───────────┘
                │
    ┌───────────▼───────────┐
    │ generate_insights     │  ← text bullets + KPI summary dict
    └───────────┬───────────┘
                │
         ┌──────▼──────┐
         │   finalize  │  ← package result for UI / chatbot
         └─────────────┘
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict


# ──────────────────────────────────────────────────────────────────
# State schema
# ──────────────────────────────────────────────────────────────────

class FintoloPipelineState(TypedDict, total=False):
    # ── input paths ──
    txn_path: str
    users_path: str
    cards_path: str
    sample_size: int          # max transactions rows to load (performance)

    # ── raw frames ──
    transactions_df: pd.DataFrame
    users_df: pd.DataFrame
    cards_df: pd.DataFrame

    # ── enriched / derived ──
    enriched_df: pd.DataFrame          # txn + user + card cols
    monthly_spend_df: pd.DataFrame     # (year_month, total_spend, txn_count)
    category_spend_df: pd.DataFrame    # (mcc_label, total_spend)
    merchant_top_df: pd.DataFrame      # top 20 merchants by volume
    fraud_flags_df: pd.DataFrame       # flagged suspicious transactions

    # ── aggregates ──
    kpis: Dict[str, Any]
    user_health_df: pd.DataFrame       # per-user health scores
    segments: Dict[str, int]           # {Healthy, At-Risk, Stressed} counts

    # ── narrative ──
    insights: List[str]
    summary: str

    # ── status ──
    errors: List[str]


# ──────────────────────────────────────────────────────────────────
# MCC (merchant category) label mapping  (simplified subset)
# ──────────────────────────────────────────────────────────────────

MCC_LABELS: Dict[int, str] = {
    5411: "Grocery Stores",
    5812: "Restaurants",
    5541: "Service Stations",
    5311: "Department Stores",
    5912: "Drug Stores",
    5999: "Misc. Retail",
    4829: "Wire Transfers",
    7011: "Hotels",
    4111: "Transportation",
    5661: "Shoe Stores",
    5944: "Jewelry Stores",
    5045: "Computers & Electronics",
    7372: "Software",
    8099: "Health Services",
    5732: "Electronics Stores",
    5912: "Pharmacies",
    5200: "Home Improvement",
    5551: "Auto Dealers",
    4814: "Telecom",
    7995: "Gambling",
    5499: "Misc. Food",
}


# ──────────────────────────────────────────────────────────────────
# Node 1 – load_data
# ──────────────────────────────────────────────────────────────────

def load_data(state: FintoloPipelineState) -> FintoloPipelineState:
    """Load all three CSV datasets. Transactions is sampled to `sample_size` rows."""
    errors: List[str] = []

    txn_path = state.get("txn_path", "transactions_data.csv")
    users_path = state.get("users_path", "users_data.csv")
    cards_path = state.get("cards_path", "cards_data.csv")
    sample_size = state.get("sample_size", 200_000)

    # Transactions – large file, load with chunksize and sample
    txn_chunks = []
    rng = np.random.default_rng(42)
    row_count = 0
    for chunk in pd.read_csv(txn_path, chunksize=50_000, low_memory=False):
        if row_count >= sample_size:
            break
        keep = min(len(chunk), sample_size - row_count)
        idx = rng.choice(len(chunk), size=keep, replace=False)
        txn_chunks.append(chunk.iloc[sorted(idx)])
        row_count += keep
    txn_df = pd.concat(txn_chunks, ignore_index=True) if txn_chunks else pd.DataFrame()

    # Parse amount – strip leading '$' and convert
    if "amount" in txn_df.columns:
        txn_df["amount"] = (
            txn_df["amount"].astype(str).str.replace(r"[\$,]", "", regex=True).astype(float)
        )
    if "date" in txn_df.columns:
        txn_df["date"] = pd.to_datetime(txn_df["date"], errors="coerce")

    users_df = pd.read_csv(users_path)
    cards_df = pd.read_csv(cards_path)

    # Normalise credit_limit
    if "credit_limit" in cards_df.columns:
        cards_df["credit_limit"] = (
            cards_df["credit_limit"].astype(str).str.replace(r"[\$,]", "", regex=True).astype(float)
        )
    # Normalise income / debt in users
    for col in ["per_capita_income", "yearly_income", "total_debt"]:
        if col in users_df.columns:
            users_df[col] = (
                users_df[col].astype(str).str.replace(r"[\$,]", "", regex=True).astype(float)
            )

    return {
        **state,
        "transactions_df": txn_df,
        "users_df": users_df,
        "cards_df": cards_df,
        "errors": errors,
    }


# ──────────────────────────────────────────────────────────────────
# Node 2 – enrich_data
# ──────────────────────────────────────────────────────────────────

def enrich_data(state: FintoloPipelineState) -> FintoloPipelineState:
    """Join transactions ← cards ← users to attach user context."""
    txn = state["transactions_df"].copy()
    users = state["users_df"][
        ["id", "gender", "yearly_income", "total_debt", "credit_score", "current_age"]
    ].rename(columns={"id": "client_id"})
    cards = state["cards_df"][
        ["id", "client_id", "card_brand", "card_type", "credit_limit", "card_on_dark_web"]
    ].rename(columns={"id": "card_id"})

    enriched = (
        txn.merge(cards, on=["card_id", "client_id"], how="left")
            .merge(users, on="client_id", how="left")
    )

    # Attach MCC label
    enriched["mcc_label"] = enriched["mcc"].map(MCC_LABELS).fillna("Other")

    # Year-month column
    enriched["year_month"] = enriched["date"].dt.to_period("M").astype(str)

    return {**state, "enriched_df": enriched}


# ──────────────────────────────────────────────────────────────────
# Node 3 – compute_spending_kpis
# ──────────────────────────────────────────────────────────────────

def compute_spending_kpis(state: FintoloPipelineState) -> FintoloPipelineState:
    df = state["enriched_df"]

    # Only positive amounts = actual spending (negatives = credits/refunds)
    spend = df[df["amount"] > 0].copy()

    # Monthly trend
    monthly = (
        spend.groupby("year_month")["amount"]
        .agg(total_spend="sum", txn_count="count")
        .reset_index()
        .sort_values("year_month")
    )

    # Category breakdown
    category = (
        spend.groupby("mcc_label")["amount"]
        .sum()
        .reset_index()
        .rename(columns={"amount": "total_spend"})
        .sort_values("total_spend", ascending=False)
    )

    # Top merchants
    merchant_top = (
        spend.groupby("merchant_id")["amount"]
        .agg(total_spend="sum", txn_count="count")
        .reset_index()
        .sort_values("total_spend", ascending=False)
        .head(20)
    )

    # KPIs
    total_txn = len(spend)
    total_spend_val = spend["amount"].sum()
    avg_txn = spend["amount"].mean()
    unique_users = spend["client_id"].nunique()
    unique_cards = spend["card_id"].nunique()
    chip_rate = (spend["use_chip"].str.contains("Chip", na=False).mean() * 100) if "use_chip" in spend else 0

    kpis = {
        "total_transactions": int(total_txn),
        "total_spend": round(float(total_spend_val), 2),
        "avg_transaction": round(float(avg_txn), 2),
        "unique_users": int(unique_users),
        "unique_cards": int(unique_cards),
        "chip_usage_pct": round(float(chip_rate), 1),
        "top_category": category.iloc[0]["mcc_label"] if not category.empty else "N/A",
        "top_category_spend": round(float(category.iloc[0]["total_spend"]), 2) if not category.empty else 0,
        "months_covered": int(monthly["year_month"].nunique()),
    }

    return {
        **state,
        "monthly_spend_df": monthly,
        "category_spend_df": category,
        "merchant_top_df": merchant_top,
        "kpis": kpis,
    }


# ──────────────────────────────────────────────────────────────────
# Node 4 – detect_fraud_signals
# ──────────────────────────────────────────────────────────────────

def detect_fraud_signals(state: FintoloPipelineState) -> FintoloPipelineState:
    df = state["enriched_df"].copy()

    flags = []

    # 1. Transactions with reported errors
    if "errors" in df.columns:
        error_rows = df[df["errors"].notna() & (df["errors"].astype(str).str.strip() != "")].copy()
        error_rows["flag_reason"] = "Transaction error: " + error_rows["errors"].astype(str)
        flags.append(error_rows)

    # 2. Card on dark web
    if "card_on_dark_web" in df.columns:
        dark_rows = df[df["card_on_dark_web"].astype(str).str.upper() == "YES"].copy()
        dark_rows["flag_reason"] = "Card listed on dark web"
        flags.append(dark_rows)

    # 3. Statistical outliers: amount z-score > 3
    spend = df[df["amount"] > 0].copy()
    if len(spend) > 30:
        mu, sigma = spend["amount"].mean(), spend["amount"].std()
        outliers = spend[np.abs((spend["amount"] - mu) / sigma) > 3].copy()
        outliers["flag_reason"] = "Unusually high amount (z-score > 3)"
        flags.append(outliers)

    fraud_df = (
        pd.concat(flags, ignore_index=True).drop_duplicates(subset=["id"])
        if flags else pd.DataFrame(columns=["id", "flag_reason"])
    )

    kpis = state.get("kpis", {})
    kpis["fraud_flagged_count"] = int(len(fraud_df))
    kpis["fraud_flag_pct"] = round(len(fraud_df) / max(len(df), 1) * 100, 2)

    return {**state, "fraud_flags_df": fraud_df, "kpis": kpis}


# ──────────────────────────────────────────────────────────────────
# Node 5 – score_financial_health
# ──────────────────────────────────────────────────────────────────

def score_financial_health(state: FintoloPipelineState) -> FintoloPipelineState:
    users = state["users_df"].copy()
    cards = state["cards_df"].copy()

    # Per-user total credit limit
    user_credit = (
        cards.groupby("client_id")["credit_limit"].sum().reset_index()
        .rename(columns={"credit_limit": "total_credit_limit"})
    )
    users = users.merge(user_credit, left_on="id", right_on="client_id", how="left")

    # Debt-to-income ratio
    users["dti_ratio"] = (users["total_debt"] / users["yearly_income"].replace(0, np.nan)).clip(0, 5)

    # Credit utilisation (debt vs credit limit)
    users["credit_utilisation"] = (
        users["total_debt"] / users["total_credit_limit"].replace(0, np.nan)
    ).clip(0, 2)

    # Health segment
    def segment(row):
        if row["credit_score"] >= 720 and row["dti_ratio"] <= 0.36:
            return "Healthy"
        if row["credit_score"] >= 620 and row["dti_ratio"] <= 0.60:
            return "At-Risk"
        return "Stressed"

    users["health_segment"] = users.apply(segment, axis=1)

    segments = users["health_segment"].value_counts().to_dict()

    kpis = state.get("kpis", {})
    kpis["avg_credit_score"] = round(float(users["credit_score"].mean()), 1)
    kpis["avg_dti"] = round(float(users["dti_ratio"].mean()), 3)
    kpis["avg_credit_utilisation"] = round(float(users["credit_utilisation"].mean()), 3)
    kpis["pct_healthy"] = round(segments.get("Healthy", 0) / max(len(users), 1) * 100, 1)
    kpis["pct_at_risk"] = round(segments.get("At-Risk", 0) / max(len(users), 1) * 100, 1)
    kpis["pct_stressed"] = round(segments.get("Stressed", 0) / max(len(users), 1) * 100, 1)

    return {**state, "user_health_df": users, "segments": segments, "kpis": kpis}


# ──────────────────────────────────────────────────────────────────
# Node 6 – segment_users  (already computed in node 5, confirm here)
# ──────────────────────────────────────────────────────────────────

def segment_users(state: FintoloPipelineState) -> FintoloPipelineState:
    """Enrich segment labels and add age-band breakdown."""
    users = state["user_health_df"].copy()

    bins = [0, 25, 35, 45, 55, 65, 120]
    labels = ["<25", "25-34", "35-44", "45-54", "55-64", "65+"]
    users["age_band"] = pd.cut(users["current_age"], bins=bins, labels=labels, right=False)

    return {**state, "user_health_df": users}


# ──────────────────────────────────────────────────────────────────
# Node 7 – generate_insights
# ──────────────────────────────────────────────────────────────────

def generate_insights(state: FintoloPipelineState) -> FintoloPipelineState:
    kpis = state["kpis"]
    insights: List[str] = []

    insights.append(
        f"Portfolio covers {kpis['total_transactions']:,} transactions across "
        f"{kpis['months_covered']} months with a total spend of "
        f"${kpis['total_spend']:,.0f}."
    )
    insights.append(
        f"Average transaction value is ${kpis['avg_transaction']:.2f} across "
        f"{kpis['unique_users']:,} unique cardholders."
    )
    insights.append(
        f"Top spending category: **{kpis['top_category']}** "
        f"(${kpis['top_category_spend']:,.0f})."
    )
    insights.append(
        f"Chip transaction rate: {kpis['chip_usage_pct']:.1f}% — "
        + ("strong contactless adoption." if kpis["chip_usage_pct"] >= 60 else "low chip adoption, fraud exposure elevated.")
    )
    insights.append(
        f"{kpis['fraud_flagged_count']:,} transactions flagged for review "
        f"({kpis['fraud_flag_pct']:.2f}% of total)."
    )
    insights.append(
        f"User health: {kpis['pct_healthy']:.1f}% Healthy · "
        f"{kpis['pct_at_risk']:.1f}% At-Risk · "
        f"{kpis['pct_stressed']:.1f}% Stressed."
    )
    insights.append(
        f"Average credit score: {kpis['avg_credit_score']:.0f}. "
        f"Average debt-to-income: {kpis['avg_dti']:.2f}."
    )

    summary = "FINTOLO EXECUTIVE SUMMARY\n" + "\n".join(f"• {i}" for i in insights)
    return {**state, "insights": insights, "summary": summary}


# ──────────────────────────────────────────────────────────────────
# Node 8 – finalize
# ──────────────────────────────────────────────────────────────────

def finalize(state: FintoloPipelineState) -> FintoloPipelineState:
    """Package final state — no-op, used as explicit terminal node."""
    return state


# ──────────────────────────────────────────────────────────────────
# Build & compile the graph
# ──────────────────────────────────────────────────────────────────

def build_graph() -> Any:
    g = StateGraph(FintoloPipelineState)

    g.add_node("load_data", load_data)
    g.add_node("enrich_data", enrich_data)
    g.add_node("compute_spending_kpis", compute_spending_kpis)
    g.add_node("detect_fraud_signals", detect_fraud_signals)
    g.add_node("score_financial_health", score_financial_health)
    g.add_node("segment_users", segment_users)
    g.add_node("generate_insights", generate_insights)
    g.add_node("finalize", finalize)

    g.set_entry_point("load_data")
    g.add_edge("load_data", "enrich_data")
    g.add_edge("enrich_data", "compute_spending_kpis")
    g.add_edge("compute_spending_kpis", "detect_fraud_signals")
    g.add_edge("detect_fraud_signals", "score_financial_health")
    g.add_edge("score_financial_health", "segment_users")
    g.add_edge("segment_users", "generate_insights")
    g.add_edge("generate_insights", "finalize")
    g.add_edge("finalize", END)

    return g.compile()


# ──────────────────────────────────────────────────────────────────
# Public run entrypoint
# ──────────────────────────────────────────────────────────────────

def run_fintolo_pipeline(
    txn_path: str = "transactions_data.csv",
    users_path: str = "users_data.csv",
    cards_path: str = "cards_data.csv",
    sample_size: int = 200_000,
) -> FintoloPipelineState:
    graph = build_graph()
    initial_state: FintoloPipelineState = {
        "txn_path": txn_path,
        "users_path": users_path,
        "cards_path": cards_path,
        "sample_size": sample_size,
        "errors": [],
    }
    return graph.invoke(initial_state)


# ──────────────────────────────────────────────────────────────────
# CLI runner
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser(description="Run the Fintolo LangGraph pipeline.")
    parser.add_argument("--txn", default="transactions_data.csv")
    parser.add_argument("--users", default="users_data.csv")
    parser.add_argument("--cards", default="cards_data.csv")
    parser.add_argument("--sample", type=int, default=200_000)
    args = parser.parse_args()

    print("▶  Running Fintolo pipeline …")
    result = run_fintolo_pipeline(args.txn, args.users, args.cards, args.sample)
    print("\n" + result["summary"])
    print("\nKPIs:")
    print(json.dumps(result["kpis"], indent=2))
