from __future__ import annotations

from datetime import datetime
from pathlib import Path
import subprocess

from airflow import DAG
from airflow.operators.python import PythonOperator

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_cfo_report() -> None:
    cmd = [
        "python",
        "-m",
        "src.cfo_agent.main",
        "--company",
        "Your Company",
        "--input-dir",
        "data/finance_exports",
        "--input-glob",
        "*.csv",
        "--output-dir",
        "output",
    ]
    subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True)


with DAG(
    dag_id="cfo_monthly_report",
    start_date=datetime(2026, 1, 1),
    schedule="0 8 1 * *",
    catchup=False,
    tags=["finance", "cfo", "monthly"],
) as dag:
    generate_report = PythonOperator(
        task_id="generate_cfo_report",
        python_callable=run_cfo_report,
    )

    generate_report
