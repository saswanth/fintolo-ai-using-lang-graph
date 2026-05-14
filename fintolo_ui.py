"""
╔══════════════════════════════════════════════════════╗
║   F I N T O L O  — Monthly Financial Tracker UI     ║
║   Built with Gradio 4  ·  Powered by LangGraph       ║
╚══════════════════════════════════════════════════════╝
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from fintolo_flow import run_fintolo_pipeline, FintoloPipelineState
from src.fintolo_chat import ask_fintolo

# ─── CSS ─────────────────────────────────────────────────────────
CSS = """
body, .gradio-container { background:#0d1117!important; color:#e6edf3!important; font-family:'Inter','Segoe UI',sans-serif!important; }
.fintolo-header { background:linear-gradient(135deg,#0d1117,#161b22); border-bottom:1px solid #21262d; padding:22px 32px 14px; }
.fintolo-header h1 { font-size:2rem; font-weight:700; background:linear-gradient(90deg,#58a6ff,#bc8cff,#ff7b72); -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin:0; }
.fintolo-header p { color:#8b949e; margin:4px 0 0; }
.kpi-grid { display:grid; grid-template-columns:repeat(6,1fr); gap:10px; margin:14px 0; }
.kpi-card { background:#161b22; border:1px solid #21262d; border-radius:10px; padding:16px; text-align:center; }
.kpi-v { font-size:1.7rem; font-weight:700; }
.kpi-l { font-size:0.72rem; color:#8b949e; text-transform:uppercase; letter-spacing:.5px; margin-top:4px; }
.tab-nav button { background:#161b22!important; color:#8b949e!important; border:1px solid #21262d!important; }
.tab-nav button.selected { background:#1f6feb!important; color:#fff!important; }
textarea,input { background:#161b22!important; border:1px solid #21262d!important; color:#e6edf3!important; border-radius:8px!important; }
button.primary { background:#1f6feb!important; border:none!important; border-radius:8px!important; }
.ok  { color:#3fb950; font-weight:600; }
.err { color:#f85149; font-weight:600; }
"""

# ─── Global cache ─────────────────────────────────────────────────
_result: Optional[FintoloPipelineState] = None
_lock = threading.Lock()

# ─── Plotly dark helper ───────────────────────────────────────────
def _dk(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="#0d1117", plot_bgcolor="#161b22",
        font_color="#e6edf3",
        xaxis=dict(gridcolor="#21262d"), yaxis=dict(gridcolor="#21262d"),
        margin=dict(l=40, r=20, t=46, b=36),
    )
    return fig


def fig_monthly(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["year_month"], y=df["total_spend"],
                          name="Spend", marker_color="#1f6feb", opacity=.85))
    fig.add_trace(go.Scatter(x=df["year_month"], y=df["total_spend"],
                              mode="lines+markers", name="Trend",
                              line=dict(color="#bc8cff", width=2), marker=dict(size=5)))
    fig.update_layout(title="Monthly Spending Trend", xaxis_title="Month", yaxis_title="USD")
    return _dk(fig)


def fig_category(df: pd.DataFrame) -> go.Figure:
    top = df.head(10).sort_values("total_spend")
    fig = go.Figure(go.Bar(
        x=top["total_spend"], y=top["mcc_label"], orientation="h",
        marker=dict(color=top["total_spend"],
                    colorscale=[[0, "#1f6feb"], [.5, "#bc8cff"], [1, "#ff7b72"]]),
    ))
    fig.update_layout(title="Top Spending Categories", xaxis_title="USD")
    return _dk(fig)


def fig_segments(segs: Dict[str, int]) -> go.Figure:
    clr = {"Healthy": "#3fb950", "At-Risk": "#d29922", "Stressed": "#f85149"}
    labels, vals = list(segs.keys()), list(segs.values())
    fig = go.Figure(go.Pie(
        labels=labels, values=vals, hole=.5,
        marker_colors=[clr.get(l, "#58a6ff") for l in labels],
        textinfo="percent+label",
    ))
    fig.update_layout(title="User Health Segments")
    return _dk(fig)


def fig_fraud(df: pd.DataFrame) -> go.Figure:
    if df is None or df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No fraud signals detected", showarrow=False,
                           font_size=15, font_color="#8b949e")
        return _dk(fig)
    r = df["flag_reason"].value_counts().reset_index()
    r.columns = ["reason", "count"]
    fig = px.bar(r, x="count", y="reason", orientation="h",
                 color="count", color_continuous_scale=["#f85149", "#d29922", "#e3b341"])
    fig.update_layout(title="Fraud Flag Breakdown", coloraxis_showscale=False)
    return _dk(fig)


def fig_age(df: pd.DataFrame) -> go.Figure:
    if "age_band" not in df.columns:
        return go.Figure()
    grp = df.groupby(["age_band", "health_segment"]).size().reset_index(name="count")
    cmap = {"Healthy": "#3fb950", "At-Risk": "#d29922", "Stressed": "#f85149"}
    fig = px.bar(grp, x="age_band", y="count", color="health_segment",
                 color_discrete_map=cmap, barmode="stack", title="Health by Age Band")
    fig.update_layout(xaxis_title="Age Band", yaxis_title="Users")
    return _dk(fig)


def fig_credit(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Histogram(
        x=df["credit_score"].dropna(), nbinsx=40,
        marker_color="#58a6ff", opacity=.8,
    ))
    fig.update_layout(title="Credit Score Distribution",
                      xaxis_title="Score", yaxis_title="Users")
    return _dk(fig)


# ─── KPI HTML ────────────────────────────────────────────────────
def kpi_html(kpis: Dict) -> str:
    cards = [
        f'<div class="kpi-card"><div class="kpi-v" style="color:#58a6ff">${kpis.get("total_spend", 0):,.0f}</div><div class="kpi-l">Total Spend</div></div>',
        f'<div class="kpi-card"><div class="kpi-v" style="color:#58a6ff">{kpis.get("total_transactions", 0):,}</div><div class="kpi-l">Transactions</div></div>',
        f'<div class="kpi-card"><div class="kpi-v" style="color:#bc8cff">${kpis.get("avg_transaction", 0):.2f}</div><div class="kpi-l">Avg Transaction</div></div>',
        f'<div class="kpi-card"><div class="kpi-v" style="color:#3fb950">{kpis.get("unique_users", 0):,}</div><div class="kpi-l">Unique Users</div></div>',
        f'<div class="kpi-card"><div class="kpi-v" style="color:#f85149">{kpis.get("fraud_flagged_count", 0):,}</div><div class="kpi-l">Fraud Flagged</div></div>',
        f'<div class="kpi-card"><div class="kpi-v" style="color:#d29922">{kpis.get("avg_credit_score", "N/A")}</div><div class="kpi-l">Avg Credit Score</div></div>',
    ]
    return '<div class="kpi-grid">' + "".join(cards) + "</div>"


# ─── Pipeline runner ─────────────────────────────────────────────
def run_pipeline(txn: str, users: str, cards: str, sample: int):
    global _result
    txn   = (txn   or "").strip() or "transactions_data.csv"
    users = (users or "").strip() or "users_data.csv"
    cards = (cards or "").strip() or "cards_data.csv"

    try:
        r = run_fintolo_pipeline(txn, users, cards, int(sample))
        with _lock:
            _result = r

        k = r.get("kpis", {})
        monthly_df = r.get("monthly_spend_df", pd.DataFrame())
        cat_df     = r.get("category_spend_df", pd.DataFrame())
        segs       = r.get("segments", {})
        fraud_df   = r.get("fraud_flags_df", pd.DataFrame())
        health_df  = r.get("user_health_df", pd.DataFrame())

        status = (
            f'<span class="ok">✔ Pipeline complete — '
            f'{k.get("total_transactions", 0):,} transactions · '
            f'{k.get("months_covered", "?")} months</span>'
        )
        return (
            status,
            kpi_html(k),
            fig_monthly(monthly_df)  if not monthly_df.empty else None,
            fig_category(cat_df)     if not cat_df.empty    else None,
            fig_segments(segs)       if segs                else None,
            fig_fraud(fraud_df),
            fig_age(health_df)       if not health_df.empty else None,
            fig_credit(health_df)    if not health_df.empty else None,
            r.get("summary", ""),
        )

    except Exception as exc:
        err = f'<span class="err">✖ {exc}</span>'
        return (err, "", None, None, None, None, None, None, str(exc))


# ─── Chatbot ─────────────────────────────────────────────────────
_chat_history: List[Dict] = []


def chat_fn(message: str, history: List[Tuple[str, str]]):
    global _chat_history
    if not message.strip():
        return "", history
    if _result is None:
        reply = "⚠️ Run the pipeline first (Pipeline tab → Run Pipeline)."
    else:
        reply = ask_fintolo(message, _result, _chat_history)
        _chat_history.append({"role": "user", "content": message})
        _chat_history.append({"role": "assistant", "content": reply})
    return "", history + [(message, reply)]


# ─── CSV preview ─────────────────────────────────────────────────
def preview_csv(file):
    if file is None:
        return pd.DataFrame()
    try:
        file_path = file if isinstance(file, str) else getattr(file, "name", None)
        if not file_path:
            return pd.DataFrame({"error": ["Unsupported uploaded file payload."]})
        return pd.read_csv(file_path, nrows=200)
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})


# ─── Build UI ────────────────────────────────────────────────────
def build_app():
    with gr.Blocks(css=CSS, title="Fintolo | Financial Tracker") as app:

        gr.HTML("""
        <div class="fintolo-header">
          <h1>&#x2B21; Fintolo</h1>
          <p>Monthly Financial Tracker &nbsp;&middot;&nbsp; Powered by LangGraph AI Pipeline</p>
        </div>""")

        with gr.Tabs():

            # ══ Tab 1 – Pipeline ══════════════════════════════════
            with gr.TabItem("⚙️ Pipeline"):
                gr.Markdown(
                    "### Configure & Run the 8-Node LangGraph Pipeline\n"
                    "Point to your CSV files, choose a sample size, and click **Run Pipeline**. "
                    "The graph will load → enrich → score → fraud-detect → insight in sequence."
                )
                with gr.Row():
                    txn_in   = gr.Textbox(label="Transactions CSV", value="transactions_data.csv")
                    users_in = gr.Textbox(label="Users CSV",         value="users_data.csv")
                    cards_in = gr.Textbox(label="Cards CSV",          value="cards_data.csv")
                sample_sl = gr.Slider(
                    minimum=10_000, maximum=500_000, step=10_000, value=200_000,
                    label="Sample rows (from transactions file)",
                )
                run_btn    = gr.Button("▶  Run Pipeline", variant="primary", size="lg")
                status_out = gr.HTML(value="<p style='color:#8b949e'>Ready — click Run Pipeline to start.</p>")

            # ══ Tab 2 – Dashboard ═════════════════════════════════
            with gr.TabItem("📊 Dashboard"):
                gr.Markdown("### Executive KPI Dashboard")
                kpi_out = gr.HTML(value="<p style='color:#8b949e'>Run the pipeline to populate KPIs.</p>")
                with gr.Row():
                    fig_m  = gr.Plot(label="Monthly Trend")
                    fig_c  = gr.Plot(label="Spending Categories")
                with gr.Row():
                    fig_s  = gr.Plot(label="User Health Segments")
                    fig_f  = gr.Plot(label="Fraud Flags")
                with gr.Row():
                    fig_a  = gr.Plot(label="Age Band Health")
                    fig_cr = gr.Plot(label="Credit Score Distribution")

            # ══ Tab 3 – Insights ══════════════════════════════════
            with gr.TabItem("💡 Insights"):
                gr.Markdown("### AI-Generated Executive Insights")
                summary_out = gr.Textbox(
                    label="Fintolo Executive Summary", lines=16, interactive=False,
                    placeholder="Run the pipeline to generate insights…",
                )

            # ══ Tab 4 – Chatbot ═══════════════════════════════════
            with gr.TabItem("🤖 Fintolo AI Chat"):
                gr.Markdown(
                    "### Ask Fintolo — Your AI Financial Analyst\n"
                    "Ask about spending, fraud, user health, categories, merchants, or trends. "
                    "Type **help** to see all capabilities. Run the pipeline first."
                )
                chatbot = gr.Chatbot(
                    elem_id="chatbot", height=460,
                    bubble_full_width=False, show_label=False,
                )
                with gr.Row():
                    chat_in  = gr.Textbox(
                        placeholder="Ask about your financial data…",
                        show_label=False, scale=9, container=False,
                    )
                    send_btn = gr.Button("Send", variant="primary", scale=1)

                gr.Markdown("**Quick prompts:**")
                with gr.Row():
                    for prompt_text in [
                        "Give me a summary",
                        "Top spending categories",
                        "Show fraud signals",
                        "User health breakdown",
                        "Monthly spending trend",
                        "Help",
                    ]:
                        def _make_click(p):
                            def _fn(h):
                                return chat_fn(p, h or [])
                            return _fn
                        gr.Button(prompt_text, size="sm").click(
                            fn=_make_click(prompt_text),
                            inputs=[chatbot],
                            outputs=[chat_in, chatbot],
                            api_name=False,
                        )

                clear_btn = gr.Button("🗑 Clear Chat", size="sm", variant="secondary")
                chat_in.submit(chat_fn, [chat_in, chatbot], [chat_in, chatbot], api_name=False)
                send_btn.click(chat_fn,  [chat_in, chatbot], [chat_in, chatbot], api_name=False)
                clear_btn.click(lambda: ([], []), outputs=[chatbot], api_name=False)

            # ══ Tab 5 – Data Explorer ════════════════════════════
            with gr.TabItem("🔍 Data Explorer"):
                gr.Markdown("### Upload & Preview any CSV (first 200 rows)")
                with gr.Row():
                    csv_up   = gr.File(label="Upload CSV", file_types=[".csv"], type="filepath", scale=3)
                    prev_btn = gr.Button("Preview", variant="secondary", scale=1)
                preview_tbl = gr.Dataframe(
                    label="Preview", interactive=False, wrap=True,
                )
                prev_btn.click(preview_csv, inputs=[csv_up], outputs=[preview_tbl], api_name=False)

        # ── Wire pipeline ─────────────────────────────────────────
        run_btn.click(
            fn=run_pipeline,
            inputs=[txn_in, users_in, cards_in, sample_sl],
            outputs=[
                status_out, kpi_out,
                fig_m, fig_c, fig_s, fig_f, fig_a, fig_cr,
                summary_out,
            ],
            api_name=False,
        )

    return app


if __name__ == "__main__":
    build_app().launch(
        server_name="127.0.0.1",
        server_port=7860,
        inbrowser=True,
        show_error=True,
    )
