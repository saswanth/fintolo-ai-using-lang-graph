# Fintolo - Your Monthly Financial Tracker

Fintolo creates an AI agent that acts like a Senior Financial Analyst plus CFO partner and generates board-ready monthly reporting.

It is implemented using LangGraph workflow automation so each monthly run follows a consistent execution pipeline.

It now includes role-based login, persistent encrypted user management, branded PDF board export, and chatbot forecasting with anomaly detection.

## Use Case

Instantly generate monthly performance summaries.

## Embedded Prompt

"Generate a monthly CFO-ready financial one-pager. Include visualizations and summaries for revenue trends, operating margin, cash runway, and budget vs. actuals. Make it suitable for board reporting."

## What It Produces

For each run, the agent creates:

- A markdown one-pager report with executive summary and KPI snapshot
- A PPTX board pack from the same workflow run
- A branded PDF board pack with cover page from the same workflow run
- Optional board email delivery with report attachments
- Revenue trend chart
- Operating margin chart
- Cash runway chart
- Budget vs. actual chart (latest month)

Fintolo also includes a sophisticated Streamlit UI and a chatbot that answers overall perks and insight questions.

Default local app URL after launch: <http://localhost:8501>

## LangGraph Workflow

The automation graph executes the following nodes:

1. `load_data`
1. `analyze_financials`
1. `generate_visuals`
1. `synthesize_narrative`
1. `assemble_report`
1. `export_pptx`
1. `export_pdf`
1. `dispatch_email`

## Input Data Schema (CSV)

Required columns:

- `month`
- `revenue`
- `cogs`
- `operating_expenses`
- `cash_balance`
- `budget_revenue`
- `actual_revenue`
- `budget_opex`
- `actual_opex`

A sample file is included at `data/sample_monthly_financials.csv`.

## Connect Real Monthly Finance Export CSV

You can replace sample input with your real monthly exports in either mode:

1. Direct file mode:

```bash
python -m src.cfo_agent.main --input "data/finance_exports/your_latest_export.csv" --company "Your Company"
```

1. Directory auto-pick mode (recommended for automation):

```bash
python -m src.cfo_agent.main --input-dir data/finance_exports --input-glob "*.csv" --company "Your Company"
```

In directory mode, the workflow automatically selects the most recently modified matching CSV.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Launch Fintolo UI

```bash
streamlit run fintolo_app.py
```

## Role-Based Access, Login, and Persistent User Management

The UI enforces role-based access:

- `admin`: full access (view, generate, email)
- `finance_manager`: operational access (view, generate, email)
- `board_viewer`: read-only dashboards and chatbot

Default demo users for local testing:

- Username `admin`, password `admin123!`
- Username `finance`, password `finance123!`
- Username `board`, password `board123!`

Admin users can create, edit, and delete users from the sidebar user management panel.

User records are persisted in encrypted storage:

- `data/security/users.enc` (encrypted user database)
- `data/security/users.key` (encryption key)

Passwords are stored as salted PBKDF2-SHA256 records, and the user database is encrypted at rest.

The UI includes:

- Branded Fintolo dashboard with interactive visuals
- KPI cards and board-grade narrative insights
- Perks, risk signals, and recommended actions panel
- Embedded chatbot for revenue, margin, runway, budget, and overall insights
- Forecast and anomaly radar panel
- Scenario-based narrative forecasting panel (best, base, worst)
- One-click generation of markdown, PPTX, and PDF outputs
- One-click download buttons for MD, PPTX, PDF, and ZIP bundle

## Run

```bash
python -m src.cfo_agent.main --input data/sample_monthly_financials.csv --company "Your Company" --output-dir output
```

Run with real CSV auto-discovery and email delivery:

```bash
python -m src.cfo_agent.main --input-dir data/finance_exports --input-glob "*.csv" --company "Your Company" --send-email --email-to "board1@company.com,board2@company.com" --smtp-host smtp.office365.com --smtp-port 587 --smtp-user finance_bot@company.com --smtp-pass "APP_OR_PAT_PASSWORD" --smtp-sender finance_bot@company.com
```

Optional arguments:

- `--period Apr_2026`
- `--prompt "custom prompt text"`
- `--input-dir data/finance_exports`
- `--input-glob "*.csv"`
- `--no-pptx` (disables PPTX board pack output)
- `--no-pdf` (disables PDF board pack output)
- `--send-email`
- `--email-to "a@company.com,b@company.com"`
- `--smtp-host`, `--smtp-port`, `--smtp-user`, `--smtp-pass`, `--smtp-sender`
- `--smtp-no-tls`

Environment variable alternatives for SMTP:

- `CFO_EMAIL_TO`
- `CFO_SMTP_HOST`
- `CFO_SMTP_PORT`
- `CFO_SMTP_USER`
- `CFO_SMTP_PASS`
- `CFO_SMTP_SENDER`

## Output Location

- Report: `output/cfo_one_pager_<period>.md`
- PPTX board pack: `output/cfo_board_pack_<period>.pptx`
- PDF board pack: `output/cfo_board_pack_<period>.pdf`
- Charts: `output/charts/*.png`

## Chatbot Intelligence

The chatbot now supports:

- Forecast queries (for example: "Show next quarter revenue forecast")
- Scenario narrative queries (for example: "Give me best/base/worst scenario")
- Anomaly queries (for example: "Any anomalies this month?")
- Trend and risk synthesis alongside existing KPI insight responses

## Scheduling For Automatic Month-End Generation

### Option 1: Windows Task Scheduler

1. Configure environment and dependencies once.
1. Place monthly export CSV files in `data/finance_exports`.
1. Register the task:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/register_task_scheduler.ps1 -TaskName "CFO Monthly One Pager" -RunAt "08:00" -Company "Your Company"
```

This calls `scripts/run_monthly_report.ps1` monthly and generates markdown + PPTX + charts.

### Option 2: Airflow

Use the DAG in `airflow/dags/cfo_monthly_report_dag.py`.

Schedule:

- Cron: `0 8 1 * *` (monthly on day 1 at 08:00)

### Option 3: GitHub Actions

Workflow file:

- `.github/workflows/month_end_cfo_report.yml`

It runs monthly and uploads report artifacts.

## Notes

- The report and PPTX are intentionally formatted for CFO and board-readability.
- For strict month-end timing, tune schedule expressions to your timezone and close calendar.
