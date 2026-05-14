# Fintolo - Your Monthly Financial Tracker

Fintolo is an AI financial intelligence application that combines a LangGraph pipeline, board-ready reporting, and a modern Gradio dashboard with chatbot support.

It is designed to act like a Senior Financial Analyst + CFO copilot for monthly review, risk detection, and executive storytelling.

## Latest Update (Current State)

- Workflow scaffolded on LangGraph using transaction, user, and card datasets
- New Gradio-based UI with custom dashboard and embedded chatbot
- Upgraded to section-wise LangGraph pipelines for each UI area:
	- Dashboard pipeline
	- Insights pipeline
	- Chatbot pipeline
	- Data Explorer pipeline
- Dedicated LangGraph flow artifacts added:
	- `langgraph_flow.txt`
	- `langgraph_flow.mmd`
	- `langgraph_flow.svg`
- Repository cleaned for GitHub push by excluding large raw CSV files

## Core Features

- Section-specific LangGraph automation pipelines for financial analysis
- KPI computation and executive insight generation
- Fraud/risk signal detection and user health segmentation
- Interactive dashboard charts
- Chatbot for summary, trend, fraud, category, and user-health queries
- Board artifact generation (Markdown, PPTX, PDF)
- Optional SMTP email delivery for generated board pack artifacts

## LangGraph Flow

### Flow files

- Text description: `langgraph_flow.txt`
- Mermaid source: `langgraph_flow.mmd`
- SVG diagram: `langgraph_flow.svg`

### Runtime graph nodes

The current financial intelligence flow is:

1. `load_data`
1. `enrich_data`
1. `compute_spending_kpis`
1. `detect_fraud_signals`
1. `score_financial_health`
1. `segment_users`
1. `generate_insights`
1. `finalize`

### Section pipelines (UI upgrade)

The app now uses separate LangGraph graphs for each major section:

1. Dashboard pipeline
	- Loads shared base result
	- Builds dashboard payload (kpis, monthly/category/fraud/user health frames)
1. Insights pipeline
	- Reuses shared base result
	- Builds executive summary and insight bullets
1. Chatbot pipeline
	- Handles user query routing and response generation
1. Data Explorer pipeline
	- Handles uploaded file preview and CSV parsing

## Datasets Used

Primary files used by the new flow:

- `transactions_data.csv`
- `users_data.csv`
- `cards_data.csv`

The UI/pipeline supports sample loading for large transaction volumes via configurable sampling.

## Project Structure (Key Files)

- `fintolo_flow.py` - LangGraph financial workflow
- `src/fintolo_chat.py` - chatbot query handling over pipeline outputs
- `src/fintolo_section_pipelines.py` - section-wise LangGraph pipelines (dashboard/insights/chatbot/explorer)
- `fintolo_ui.py` - Gradio web UI
- `fintolo_app.py` - legacy Streamlit app (kept for compatibility)
- `src/cfo_agent/` - existing CFO pipeline modules for report/PPTX/PDF/email flows

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run (Recommended UI)

```bash
python fintolo_ui.py
```

The UI now routes each tab through its dedicated LangGraph pipeline while sharing a common base analysis state.

Gradio app link (local):

- `http://127.0.0.1:7860`

Alternate localhost link:

- `http://localhost:7860`

## Run (Legacy Streamlit UI)

```bash
streamlit run fintolo_app.py
```

## Run LangGraph Flow from CLI

```bash
python fintolo_flow.py --txn transactions_data.csv --users users_data.csv --cards cards_data.csv --sample 200000
```

## Existing CFO Report CLI (Markdown/PPTX/PDF/Email)

```bash
python -m src.cfo_agent.main --input data/sample_monthly_financials.csv --company "Your Company" --output-dir output
```

Example with auto-discovery + email:

```bash
python -m src.cfo_agent.main --input-dir data/finance_exports --input-glob "*.csv" --company "Your Company" --send-email --email-to "board1@company.com,board2@company.com" --smtp-host smtp.office365.com --smtp-port 587 --smtp-user finance_bot@company.com --smtp-pass "APP_OR_PAT_PASSWORD" --smtp-sender finance_bot@company.com
```

## Output Artifacts

- Markdown report: `output/cfo_one_pager_<period>.md`
- PPTX board pack: `output/cfo_board_pack_<period>.pptx`
- PDF board pack: `output/cfo_board_pack_<period>.pdf`
- Charts: `output/charts/*.png`

## Security and User Management

Encrypted user store (for legacy Streamlit auth/RBAC flow):

- `data/security/users.enc`
- `data/security/users.key`

Passwords are stored as salted PBKDF2-SHA256 records, and user data is encrypted at rest.

## Automation / Scheduling

- Windows Task Scheduler script: `scripts/register_task_scheduler.ps1`
- Monthly runner: `scripts/run_monthly_report.ps1`
- Airflow DAG: `airflow/dags/cfo_monthly_report_dag.py`
- GitHub Actions workflow: `.github/workflows/month_end_cfo_report.yml`

## Notes

- Large raw CSVs are intentionally excluded from Git tracking due to GitHub file-size limits.
- If you need reproducible shared datasets, use sampled/partitioned files or Git LFS.
