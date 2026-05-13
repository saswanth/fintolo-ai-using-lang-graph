from __future__ import annotations

import argparse
import os

from .workflow import run_cfo_agent

DEFAULT_PROMPT = (
    "Generate a monthly CFO-ready financial one-pager. Include visualizations and summaries "
    "for revenue trends, operating margin, cash runway, and budget vs. actuals. "
    "Make it suitable for board reporting."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AI CFO analyst LangGraph workflow.")
    parser.add_argument(
        "--input",
        default=None,
        help="Path to monthly financial CSV",
    )
    parser.add_argument(
        "--input-dir",
        default="data/finance_exports",
        help="Directory containing finance export CSV files (latest file is used if --input is omitted)",
    )
    parser.add_argument(
        "--input-glob",
        default="*.csv",
        help="Glob pattern to match CSV files in --input-dir",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory where report and charts are generated",
    )
    parser.add_argument(
        "--company",
        default="Acme Corp",
        help="Company name displayed in the report",
    )
    parser.add_argument(
        "--period",
        default=None,
        help="Optional reporting period label (e.g., Apr_2026)",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Prompt context for the CFO one-pager",
    )
    parser.add_argument(
        "--no-pptx",
        action="store_true",
        help="Disable PPTX board-pack export",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Disable PDF board-pack export",
    )
    parser.add_argument(
        "--send-email",
        action="store_true",
        help="Send generated report and board pack via SMTP",
    )
    parser.add_argument("--email-to", default=None, help="Comma-separated recipient emails")
    parser.add_argument("--smtp-host", default=None, help="SMTP server host")
    parser.add_argument("--smtp-port", type=int, default=None, help="SMTP server port")
    parser.add_argument("--smtp-user", default=None, help="SMTP username")
    parser.add_argument("--smtp-pass", default=None, help="SMTP password")
    parser.add_argument("--smtp-sender", default=None, help="Sender email address")
    parser.add_argument(
        "--smtp-no-tls",
        action="store_true",
        help="Disable STARTTLS for SMTP",
    )
    return parser.parse_args()


def build_email_settings(args: argparse.Namespace) -> dict:
    recipients_raw = args.email_to or os.getenv("CFO_EMAIL_TO", "")
    recipients = [item.strip() for item in recipients_raw.split(",") if item.strip()]

    settings = {
        "smtp_host": args.smtp_host or os.getenv("CFO_SMTP_HOST"),
        "smtp_port": args.smtp_port or int(os.getenv("CFO_SMTP_PORT", "0") or "0"),
        "smtp_username": args.smtp_user or os.getenv("CFO_SMTP_USER"),
        "smtp_password": args.smtp_pass or os.getenv("CFO_SMTP_PASS"),
        "sender": args.smtp_sender or os.getenv("CFO_SMTP_SENDER"),
        "recipients": recipients,
        "use_tls": not args.smtp_no_tls,
    }
    return settings


def main() -> None:
    args = parse_args()
    email_settings = build_email_settings(args)

    result = run_cfo_agent(
        input_csv=args.input,
        input_dir=args.input_dir,
        input_glob=args.input_glob,
        output_dir=args.output_dir,
        company_name=args.company,
        prompt=args.prompt,
        export_pptx=not args.no_pptx,
        export_pdf=not args.no_pdf,
        send_email=args.send_email,
        email_settings=email_settings,
        period_label=args.period,
    )

    print("CFO one-pager generated successfully.")
    print(f"Report: {result['report_path']}")
    print("Charts:")
    for chart in result["chart_paths"]:
        print(f"- {chart}")

    if result.get("pptx_path"):
        print(f"Board Pack: {result['pptx_path']}")
    if result.get("pdf_path"):
        print(f"PDF Pack: {result['pdf_path']}")

    if result.get("email_sent"):
        print("Email delivery completed.")


if __name__ == "__main__":
    main()
