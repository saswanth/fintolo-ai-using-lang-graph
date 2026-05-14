from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from fintolo_flow import FintoloPipelineState, run_fintolo_pipeline
from src.fintolo_chat import ask_fintolo


class DashboardState(TypedDict, total=False):
    txn_path: str
    users_path: str
    cards_path: str
    sample_size: int
    base_result: FintoloPipelineState
    dashboard_payload: Dict[str, Any]


class InsightsState(TypedDict, total=False):
    txn_path: str
    users_path: str
    cards_path: str
    sample_size: int
    base_result: FintoloPipelineState
    insights_payload: Dict[str, Any]


class ChatbotState(TypedDict, total=False):
    query: str
    base_result: FintoloPipelineState
    history: List[Dict[str, str]]
    response: str


class ExplorerState(TypedDict, total=False):
    file: Any
    preview_df: pd.DataFrame


def _load_base_for_dashboard(state: DashboardState) -> DashboardState:
    if state.get("base_result"):
        return state

    base = run_fintolo_pipeline(
        txn_path=state.get("txn_path", "transactions_data.csv"),
        users_path=state.get("users_path", "users_data.csv"),
        cards_path=state.get("cards_path", "cards_data.csv"),
        sample_size=int(state.get("sample_size", 200_000)),
    )
    return {**state, "base_result": base}


def _build_dashboard_payload(state: DashboardState) -> DashboardState:
    base = state["base_result"]
    payload = {
        "kpis": base.get("kpis", {}),
        "monthly_spend_df": base.get("monthly_spend_df", pd.DataFrame()),
        "category_spend_df": base.get("category_spend_df", pd.DataFrame()),
        "segments": base.get("segments", {}),
        "fraud_flags_df": base.get("fraud_flags_df", pd.DataFrame()),
        "user_health_df": base.get("user_health_df", pd.DataFrame()),
    }
    return {**state, "dashboard_payload": payload}


def _load_base_for_insights(state: InsightsState) -> InsightsState:
    if state.get("base_result"):
        return state

    base = run_fintolo_pipeline(
        txn_path=state.get("txn_path", "transactions_data.csv"),
        users_path=state.get("users_path", "users_data.csv"),
        cards_path=state.get("cards_path", "cards_data.csv"),
        sample_size=int(state.get("sample_size", 200_000)),
    )
    return {**state, "base_result": base}


def _build_insights_payload(state: InsightsState) -> InsightsState:
    base = state["base_result"]
    payload = {
        "summary": base.get("summary", ""),
        "insights": base.get("insights", []),
    }
    return {**state, "insights_payload": payload}


def _respond_chatbot(state: ChatbotState) -> ChatbotState:
    query = (state.get("query") or "").strip()
    base_result = state.get("base_result")
    history = state.get("history") or []

    if not query:
        return {**state, "response": ""}

    if not base_result:
        return {**state, "response": "⚠️ Run the pipeline first (Pipeline tab -> Run Pipeline)."}

    response = ask_fintolo(query, base_result, history)
    return {**state, "response": response}


def _build_explorer_preview(state: ExplorerState) -> ExplorerState:
    file_value = state.get("file")
    if file_value is None:
        return {**state, "preview_df": pd.DataFrame()}

    try:
        file_path = file_value if isinstance(file_value, str) else getattr(file_value, "name", None)
        if not file_path:
            return {**state, "preview_df": pd.DataFrame({"error": ["Unsupported uploaded file payload."]})}

        preview_df = pd.read_csv(file_path, nrows=200)
        return {**state, "preview_df": preview_df}
    except Exception as exc:
        return {**state, "preview_df": pd.DataFrame({"error": [str(exc)]})}


def build_dashboard_graph():
    g = StateGraph(DashboardState)
    g.add_node("load_base", _load_base_for_dashboard)
    g.add_node("build_dashboard_payload", _build_dashboard_payload)
    g.set_entry_point("load_base")
    g.add_edge("load_base", "build_dashboard_payload")
    g.add_edge("build_dashboard_payload", END)
    return g.compile()


def build_insights_graph():
    g = StateGraph(InsightsState)
    g.add_node("load_base", _load_base_for_insights)
    g.add_node("build_insights_payload", _build_insights_payload)
    g.set_entry_point("load_base")
    g.add_edge("load_base", "build_insights_payload")
    g.add_edge("build_insights_payload", END)
    return g.compile()


def build_chatbot_graph():
    g = StateGraph(ChatbotState)
    g.add_node("respond", _respond_chatbot)
    g.set_entry_point("respond")
    g.add_edge("respond", END)
    return g.compile()


def build_explorer_graph():
    g = StateGraph(ExplorerState)
    g.add_node("preview", _build_explorer_preview)
    g.set_entry_point("preview")
    g.add_edge("preview", END)
    return g.compile()


_DASHBOARD_GRAPH = build_dashboard_graph()
_INSIGHTS_GRAPH = build_insights_graph()
_CHATBOT_GRAPH = build_chatbot_graph()
_EXPLORER_GRAPH = build_explorer_graph()


def run_dashboard_pipeline(
    txn_path: str,
    users_path: str,
    cards_path: str,
    sample_size: int,
    base_result: Optional[FintoloPipelineState] = None,
) -> Dict[str, Any]:
    out = _DASHBOARD_GRAPH.invoke(
        {
            "txn_path": txn_path,
            "users_path": users_path,
            "cards_path": cards_path,
            "sample_size": sample_size,
            "base_result": base_result,
        }
    )
    return {
        "base_result": out.get("base_result"),
        "dashboard_payload": out.get("dashboard_payload", {}),
    }


def run_insights_pipeline(
    txn_path: str,
    users_path: str,
    cards_path: str,
    sample_size: int,
    base_result: Optional[FintoloPipelineState] = None,
) -> Dict[str, Any]:
    out = _INSIGHTS_GRAPH.invoke(
        {
            "txn_path": txn_path,
            "users_path": users_path,
            "cards_path": cards_path,
            "sample_size": sample_size,
            "base_result": base_result,
        }
    )
    return {
        "base_result": out.get("base_result"),
        "insights_payload": out.get("insights_payload", {}),
    }


def run_chatbot_pipeline(
    query: str,
    base_result: Optional[FintoloPipelineState],
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    out = _CHATBOT_GRAPH.invoke(
        {
            "query": query,
            "base_result": base_result,
            "history": history or [],
        }
    )
    return out.get("response", "")


def run_data_explorer_pipeline(file_value: Any) -> pd.DataFrame:
    out = _EXPLORER_GRAPH.invoke({"file": file_value})
    return out.get("preview_df", pd.DataFrame())
