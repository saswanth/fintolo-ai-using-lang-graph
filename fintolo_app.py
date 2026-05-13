from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import io
import zipfile

import pandas as pd
import plotly.express as px
import streamlit as st

from src.cfo_agent.auth import verify_credentials
from src.cfo_agent.chat_agent import answer_finance_question
from src.cfo_agent.data_source import DataSourceError, resolve_input_csv
from src.cfo_agent.forecasting import build_scenario_narratives, summarize_forecast_and_anomalies
from src.cfo_agent.insights import generate_perks_and_insights
from src.cfo_agent.metrics import compute_kpis, validate_and_prepare
from src.cfo_agent.narrative import build_narrative
from src.cfo_agent.user_store import create_or_update_user, delete_user, load_users
from src.cfo_agent.workflow import run_cfo_agent


SAMPLE_CSV = Path("data/sample_monthly_financials.csv")


def load_financial_frame(input_csv: str | None, input_dir: str, input_glob: str) -> tuple[pd.DataFrame, str]:
    try:
        resolved = resolve_input_csv(input_csv=input_csv, input_dir=input_dir, input_glob=input_glob)
    except DataSourceError:
        if SAMPLE_CSV.exists():
            resolved = str(SAMPLE_CSV)
            st.sidebar.warning(
                f"No CSV found in '{input_dir}'. Loaded sample data from {SAMPLE_CSV}. "
                "Drop your monthly export CSV into 'data/finance_exports/' to use real data."
            )
        else:
            st.error(
                f"No CSV files found in '{input_dir}' and sample data is missing. "
                "Please upload a CSV file."
            )
            st.stop()
    raw_df = pd.read_csv(resolved)
    monthly_df = validate_and_prepare(raw_df)
    return monthly_df, resolved


def render_theme() -> None:
    st.set_page_config(page_title="Fintolo | Monthly Financial Tracker", page_icon="F", layout="wide")
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=DM+Serif+Display:ital@0;1&display=swap');
        .stApp {
            background: radial-gradient(circle at 10% 10%, #fff4d1 0%, #f7fbff 45%, #ecfff6 100%);
            font-family: 'Space Grotesk', sans-serif;
        }
        .hero {
            background: linear-gradient(120deg, #002b36 0%, #005f73 45%, #0a9396 100%);
            border-radius: 18px;
            padding: 22px 26px;
            color: #fefcf5;
            margin-bottom: 18px;
        }
        .hero h1 {
            font-family: 'DM Serif Display', serif;
            font-size: 44px;
            margin-bottom: 4px;
        }
        .hero p { font-size: 16px; margin: 0; opacity: 0.95; }
        .kpi-card {
            background: white;
            border-radius: 14px;
            padding: 14px 16px;
            border: 1px solid #d5e6ea;
            box-shadow: 0 10px 22px rgba(0, 43, 54, 0.06);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(resolved_csv: str, company_name: str) -> None:
    role = st.session_state.get("auth", {}).get("role", "board_viewer")
    display_name = st.session_state.get("auth", {}).get("display_name", "User")
    st.markdown(
        f"""
        <div class='hero'>
            <h1>Fintolo</h1>
            <p>Your Monthly Financial Tracker for {company_name}</p>
            <p>Live source: {resolved_csv}</p>
            <p>Signed in as: {display_name} ({role})</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _get_role() -> str:
    return st.session_state.get("auth", {}).get("role", "board_viewer")


def render_kpis(kpis: dict) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"<div class='kpi-card'><strong>Revenue</strong><br>{kpis['revenue_latest']:,.0f}</div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='kpi-card'><strong>Operating Margin</strong><br>{kpis['operating_margin_latest'] * 100:.1f}%</div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='kpi-card'><strong>Cash Balance</strong><br>{kpis['cash_balance_latest']:,.0f}</div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='kpi-card'><strong>Runway</strong><br>{kpis['cash_runway_label']}</div>", unsafe_allow_html=True)


def render_visuals(monthly_df: pd.DataFrame) -> None:
    row1_col1, row1_col2 = st.columns(2)

    revenue_fig = px.line(monthly_df, x="month", y="revenue", markers=True, title="Revenue Trend")
    revenue_fig.update_layout(template="plotly_white")
    row1_col1.plotly_chart(revenue_fig, use_container_width=True)

    margin_fig = px.area(
        monthly_df,
        x="month",
        y=(monthly_df["operating_margin"] * 100),
        title="Operating Margin (%)",
    )
    margin_fig.update_layout(template="plotly_white", yaxis_title="Margin %")
    row1_col2.plotly_chart(margin_fig, use_container_width=True)

    row2_col1, row2_col2 = st.columns(2)

    runway_series = monthly_df["cash_runway_months"].replace(float("inf"), pd.NA).fillna(0)
    runway_fig = px.bar(
        x=monthly_df["month"].dt.strftime("%b %Y"),
        y=runway_series,
        title="Cash Runway (Months)",
    )
    runway_fig.update_layout(template="plotly_white", xaxis_title="Month", yaxis_title="Months")
    row2_col1.plotly_chart(runway_fig, use_container_width=True)

    latest = monthly_df.iloc[-1]
    budget_frame = pd.DataFrame(
        {
            "Category": ["Revenue", "Revenue", "OpEx", "OpEx"],
            "Type": ["Budget", "Actual", "Budget", "Actual"],
            "Amount": [
                latest["budget_revenue"],
                latest["actual_revenue"],
                latest["budget_opex"],
                latest["actual_opex"],
            ],
        }
    )
    budget_fig = px.bar(
        budget_frame,
        x="Category",
        y="Amount",
        color="Type",
        barmode="group",
        title="Budget vs Actual",
    )
    budget_fig.update_layout(template="plotly_white")
    row2_col2.plotly_chart(budget_fig, use_container_width=True)


def render_insights(kpis: dict, company_name: str) -> None:
    st.subheader("Board-Grade Insights")
    narrative = build_narrative(kpis, company_name)
    insights = generate_perks_and_insights(kpis)

    st.write(narrative)

    c1, c2, c3 = st.columns(3)
    c1.markdown("### Perks")
    for item in insights["perks"]:
        c1.write(f"- {item}")

    c2.markdown("### Risk Signals")
    for item in insights["risks"]:
        c2.write(f"- {item}")

    c3.markdown("### Recommended Actions")
    for item in insights["actions"]:
        c3.write(f"- {item}")


def render_forecast_panel(monthly_df: pd.DataFrame) -> None:
    st.subheader("Forecast and Anomaly Radar")
    summary = summarize_forecast_and_anomalies(monthly_df)
    scenarios = build_scenario_narratives(monthly_df)

    forecast = summary["forecast"]
    if forecast:
        frame = pd.DataFrame(forecast)
        fig = px.line(
            frame,
            x="month",
            y="revenue_forecast",
            markers=True,
            title="3-Month Revenue Forecast",
        )
        fig.update_layout(template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

        st.caption(f"Trend signal: {summary['trend_signal']}")
    else:
        st.info("Not enough historical data to build a 3-month forecast.")

    if summary["anomalies"]:
        st.warning("Detected anomalies:")
        for item in summary["anomalies"]:
            st.write(f"- {item}")
    else:
        st.success("No anomalies detected in the latest period.")

    st.markdown("### Scenario Narratives")
    c1, c2, c3 = st.columns(3)
    c1.info(scenarios["best"])
    c2.write(scenarios["base"])
    c3.error(scenarios["worst"])


def render_chatbot(company_name: str, kpis: dict, monthly_df: pd.DataFrame) -> None:
    st.subheader("Fintolo Chatbot")
    st.caption("Ask about revenue, margins, runway, budget variance, overall perks, forecasts, or anomalies.")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    for role, text in st.session_state["chat_history"]:
        with st.chat_message(role):
            st.write(text)

    prompt = st.chat_input("Ask Fintolo for financial insights")
    if prompt:
        st.session_state["chat_history"].append(("user", prompt))
        answer = answer_finance_question(
            company_name=company_name,
            query=prompt,
            kpis=kpis,
            monthly_df=monthly_df,
        )
        st.session_state["chat_history"].append(("assistant", answer))
        st.rerun()


def render_generation_controls(company_name: str, input_csv: str | None, input_dir: str, input_glob: str) -> None:
    st.subheader("Generate Monthly Artifacts")
    role = st.session_state.get("auth", {}).get("role", "board_viewer")
    can_generate = role in {"admin", "finance_manager"}

    output_dir = st.text_input("Output Directory", value="output")
    period_label = st.text_input("Optional Period Label", value="")

    if can_generate:
        send_email = st.checkbox("Email report to board recipients", value=False)
        recipients = st.text_input("Recipients (comma-separated)", value="")
    else:
        send_email = False
        recipients = ""
        st.info("Board viewer role is read-only and cannot generate or send artifacts.")

    if st.button("Generate CFO One-Pager + PPTX + PDF", type="primary", disabled=not can_generate):
        email_settings = {
            "smtp_host": st.secrets.get("CFO_SMTP_HOST", ""),
            "smtp_port": int(st.secrets.get("CFO_SMTP_PORT", 587)),
            "smtp_username": st.secrets.get("CFO_SMTP_USER", ""),
            "smtp_password": st.secrets.get("CFO_SMTP_PASS", ""),
            "sender": st.secrets.get("CFO_SMTP_SENDER", ""),
            "recipients": [item.strip() for item in recipients.split(",") if item.strip()],
            "use_tls": True,
        }

        result = run_cfo_agent(
            input_csv=input_csv,
            input_dir=input_dir,
            input_glob=input_glob,
            output_dir=output_dir,
            company_name=company_name,
            prompt="Generate a monthly CFO-ready financial one-pager.",
            export_pptx=True,
            export_pdf=True,
            send_email=send_email,
            email_settings=email_settings,
            period_label=period_label or None,
        )

        st.success("Artifacts generated successfully.")
        st.write(f"Report: {result['report_path']}")
        if result.get("pptx_path"):
            st.write(f"Board Pack: {result['pptx_path']}")
        if result.get("pdf_path"):
            st.write(f"PDF Pack: {result['pdf_path']}")
        if result.get("email_sent"):
            st.write("Email delivery sent.")

        st.session_state["generated_artifacts"] = {
            "report_path": result.get("report_path"),
            "pptx_path": result.get("pptx_path"),
            "pdf_path": result.get("pdf_path"),
        }


def _read_bytes(path: str | None) -> bytes | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return None
    return file_path.read_bytes()


def render_downloads() -> None:
    st.subheader("Download Artifacts")
    artifacts: Dict[str, Any] = st.session_state.get("generated_artifacts", {})
    if not artifacts:
        st.info("Generate artifacts to enable one-click downloads.")
        return

    report_bytes = _read_bytes(artifacts.get("report_path"))
    pptx_bytes = _read_bytes(artifacts.get("pptx_path"))
    pdf_bytes = _read_bytes(artifacts.get("pdf_path"))

    c1, c2, c3 = st.columns(3)
    if report_bytes:
        c1.download_button(
            "Download One-Pager (MD)",
            data=report_bytes,
            file_name=Path(artifacts["report_path"]).name,
            mime="text/markdown",
        )
    if pptx_bytes:
        c2.download_button(
            "Download Board Pack (PPTX)",
            data=pptx_bytes,
            file_name=Path(artifacts["pptx_path"]).name,
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    if pdf_bytes:
        c3.download_button(
            "Download Board Pack (PDF)",
            data=pdf_bytes,
            file_name=Path(artifacts["pdf_path"]).name,
            mime="application/pdf",
        )

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_handle:
        if report_bytes:
            zip_handle.writestr(Path(artifacts["report_path"]).name, report_bytes)
        if pptx_bytes:
            zip_handle.writestr(Path(artifacts["pptx_path"]).name, pptx_bytes)
        if pdf_bytes:
            zip_handle.writestr(Path(artifacts["pdf_path"]).name, pdf_bytes)

    st.download_button(
        "Download All Artifacts (ZIP)",
        data=archive.getvalue(),
        file_name="fintolo_artifacts.zip",
        mime="application/zip",
    )


def _load_user_config() -> dict:
    return load_users()


def render_user_admin() -> None:
    if _get_role() != "admin":
        return

    st.markdown("### User Management")
    users = _load_user_config()

    with st.expander("Create or Edit User", expanded=False):
        username = st.text_input("Username", key="admin_username")
        display_name = st.text_input("Display Name", key="admin_display_name")
        role = st.selectbox(
            "Role",
            ["admin", "finance_manager", "board_viewer"],
            key="admin_role",
        )
        password = st.text_input("Password", type="password", key="admin_password")

        if st.button("Save User"):
            if not username.strip() or not display_name.strip():
                st.error("Username and display name are required.")
            else:
                create_or_update_user(
                    username=username.strip(),
                    display_name=display_name.strip(),
                    role=role,
                    password=password or None,
                )
                st.success("User saved to encrypted user store.")
                st.rerun()

    with st.expander("Delete User", expanded=False):
        user_list = sorted(users.keys())
        target = st.selectbox("Select user", user_list, key="delete_target")
        if st.button("Delete Selected User"):
            if target == "admin":
                st.error("Deleting the admin user is blocked.")
            else:
                delete_user(target)
                st.success("User deleted from encrypted user store.")
                st.rerun()

    st.caption("Users are persisted in encrypted storage at data/security/users.enc")


def render_login() -> None:
    st.subheader("Fintolo Access")

    if "auth" not in st.session_state:
        st.session_state["auth"] = None

    if st.session_state["auth"]:
        auth = st.session_state["auth"]
        st.success(f"Signed in as {auth['display_name']} ({auth['role']})")
        if st.button("Sign out"):
            st.session_state["auth"] = None
            st.session_state["chat_history"] = []
            st.rerun()
        return

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Sign in"):
        ok, profile = verify_credentials(username, password, _load_user_config())
        if ok and profile:
            st.session_state["auth"] = profile
            st.success("Authentication successful.")
            st.rerun()
        else:
            st.error("Invalid username or password.")

    st.caption("Use app credentials (not SMTP email accounts). Demo logins: admin/admin123!, finance/finance123!, board/board123!.")


def main() -> None:
    render_theme()

    with st.sidebar:
        st.header("Fintolo Controls")
        render_login()

        if not st.session_state.get("auth"):
            st.stop()

        company_name = st.text_input("Company Name", value="Acme Corp")
        input_csv = st.text_input("Input CSV (optional)", value="") or None
        input_dir = st.text_input("Input Directory", value="data/finance_exports")
        input_glob = st.text_input("File Pattern", value="*.csv")
        render_user_admin()

    if not st.session_state.get("auth"):
        st.stop()

    monthly_df, resolved_csv = load_financial_frame(input_csv, input_dir, input_glob)
    kpis = compute_kpis(monthly_df)

    render_header(resolved_csv, company_name)
    render_kpis(kpis)
    render_visuals(monthly_df)
    render_insights(kpis, company_name)
    render_forecast_panel(monthly_df)
    render_generation_controls(company_name, input_csv, input_dir, input_glob)
    render_downloads()
    render_chatbot(company_name, kpis, monthly_df)


if __name__ == "__main__":
    main()
