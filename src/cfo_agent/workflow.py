from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd
from langgraph.graph import END, StateGraph

from .data_source import resolve_input_csv
from .email_delivery import send_board_email
from .forecasting import summarize_forecast_and_anomalies
from .metrics import compute_kpis, validate_and_prepare
from .narrative import build_narrative
from .pdf_export import export_board_pdf
from .pptx_export import export_board_pack
from .report import build_report_markdown, write_report
from .state import CFOAgentState
from .visuals import build_charts


def load_data(state: CFOAgentState) -> CFOAgentState:
    input_csv = resolve_input_csv(
        input_csv=state.get("input_csv"),
        input_dir=state.get("input_dir"),
        input_glob=state.get("input_glob", "*.csv"),
    )
    raw_df = pd.read_csv(input_csv)
    monthly_df = validate_and_prepare(raw_df)
    return {"input_csv": input_csv, "raw_df": raw_df, "monthly_df": monthly_df}


def analyze_financials(state: CFOAgentState) -> CFOAgentState:
    kpis = compute_kpis(state["monthly_df"])
    forecast_summary = summarize_forecast_and_anomalies(state["monthly_df"])
    return {"kpis": kpis, "forecast_summary": forecast_summary}


def generate_visuals(state: CFOAgentState) -> CFOAgentState:
    chart_paths = build_charts(state["monthly_df"], state["output_dir"])
    return {"chart_paths": chart_paths}


def synthesize_narrative(state: CFOAgentState) -> CFOAgentState:
    narrative = build_narrative(state["kpis"], state["company_name"])
    return {"narrative": narrative}


def assemble_report(state: CFOAgentState) -> CFOAgentState:
    monthly_df = state["monthly_df"]
    period_label = state.get("period_label") or monthly_df.iloc[-1]["month"].strftime("%b_%Y")

    markdown = build_report_markdown(
        company_name=state["company_name"],
        period_label=period_label,
        kpis=state["kpis"],
        narrative=state["narrative"],
        chart_paths=state["chart_paths"],
    )
    report_path = write_report(state["output_dir"], markdown, period_label)

    return {
        "period_label": period_label,
        "report_markdown": markdown,
        "report_path": report_path,
    }


def export_pptx(state: CFOAgentState) -> CFOAgentState:
    if not state.get("export_pptx", True):
        return {"pptx_path": None}

    pptx_path = export_board_pack(
        output_dir=state["output_dir"],
        company_name=state["company_name"],
        period_label=state["period_label"],
        kpis=state["kpis"],
        narrative=state["narrative"],
        chart_paths=state["chart_paths"],
    )
    return {"pptx_path": pptx_path}


def export_pdf(state: CFOAgentState) -> CFOAgentState:
    if not state.get("export_pdf", True):
        return {"pdf_path": None}

    pdf_path = export_board_pdf(
        output_dir=state["output_dir"],
        company_name=state["company_name"],
        period_label=state["period_label"],
        kpis=state["kpis"],
        narrative=state["narrative"],
        chart_paths=state["chart_paths"],
    )
    return {"pdf_path": pdf_path}


def dispatch_email(state: CFOAgentState) -> CFOAgentState:
    if not state.get("send_email", False):
        return {"email_sent": False}

    email_settings = state.get("email_settings") or {}
    required = [
        "smtp_host",
        "smtp_port",
        "smtp_username",
        "smtp_password",
        "sender",
        "recipients",
    ]
    missing = [key for key in required if not email_settings.get(key)]
    if missing:
        missing_label = ", ".join(sorted(missing))
        raise ValueError(f"Missing email settings: {missing_label}")

    subject = (
        f"{state['company_name']} CFO Monthly One-Pager - {state['period_label']}"
    )
    body = (
        "Attached are the latest CFO-ready monthly reporting artifacts:\n"
        f"- One-pager: {Path(state['report_path']).name}\n"
        f"- Board pack: {Path(state['pptx_path']).name if state.get('pptx_path') else 'Not generated'}\n"
        f"- PDF pack: {Path(state['pdf_path']).name if state.get('pdf_path') else 'Not generated'}\n"
    )
    attachments = [state["report_path"]]
    if state.get("pptx_path"):
        attachments.append(state["pptx_path"])
    if state.get("pdf_path"):
        attachments.append(state["pdf_path"])

    send_board_email(
        smtp_host=email_settings["smtp_host"],
        smtp_port=int(email_settings["smtp_port"]),
        smtp_username=email_settings["smtp_username"],
        smtp_password=email_settings["smtp_password"],
        sender=email_settings["sender"],
        recipients=email_settings["recipients"],
        subject=subject,
        body=body,
        attachments=attachments,
        use_tls=bool(email_settings.get("use_tls", True)),
    )
    return {"email_sent": True}


def build_cfo_agent_graph():
    graph = StateGraph(CFOAgentState)

    graph.add_node("load_data", load_data)
    graph.add_node("analyze_financials", analyze_financials)
    graph.add_node("generate_visuals", generate_visuals)
    graph.add_node("synthesize_narrative", synthesize_narrative)
    graph.add_node("assemble_report", assemble_report)
    graph.add_node("export_pptx", export_pptx)
    graph.add_node("export_pdf", export_pdf)
    graph.add_node("dispatch_email", dispatch_email)

    graph.set_entry_point("load_data")
    graph.add_edge("load_data", "analyze_financials")
    graph.add_edge("analyze_financials", "generate_visuals")
    graph.add_edge("generate_visuals", "synthesize_narrative")
    graph.add_edge("synthesize_narrative", "assemble_report")
    graph.add_edge("assemble_report", "export_pptx")
    graph.add_edge("export_pptx", "export_pdf")
    graph.add_edge("export_pdf", "dispatch_email")
    graph.add_edge("dispatch_email", END)

    return graph.compile()


def run_cfo_agent(
    input_csv: str | None,
    output_dir: str,
    company_name: str,
    prompt: str,
    input_dir: str | None = None,
    input_glob: str = "*.csv",
    export_pptx: bool = True,
    export_pdf: bool = True,
    send_email: bool = False,
    email_settings: Dict[str, Any] | None = None,
    period_label: str | None = None,
) -> CFOAgentState:
    agent = build_cfo_agent_graph()

    initial_state: CFOAgentState = {
        "input_csv": str(Path(input_csv)) if input_csv else None,
        "input_dir": str(Path(input_dir)) if input_dir else None,
        "input_glob": input_glob,
        "output_dir": str(Path(output_dir)),
        "company_name": company_name,
        "prompt": prompt,
        "export_pptx": export_pptx,
        "export_pdf": export_pdf,
        "send_email": send_email,
        "email_settings": email_settings or {},
        "period_label": period_label,
    }

    result: CFOAgentState = agent.invoke(initial_state)
    return result
