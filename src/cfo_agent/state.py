from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

import pandas as pd


class CFOAgentState(TypedDict, total=False):
    input_csv: str
    input_dir: str
    input_glob: str
    output_dir: str
    company_name: str
    period_label: Optional[str]
    prompt: str
    export_pptx: bool
    export_pdf: bool
    send_email: bool
    email_settings: Dict[str, Any]
    raw_df: pd.DataFrame
    monthly_df: pd.DataFrame
    kpis: Dict[str, Any]
    chart_paths: List[str]
    narrative: str
    report_markdown: str
    report_path: str
    pptx_path: Optional[str]
    pdf_path: Optional[str]
    forecast_summary: Dict[str, Any]
    email_sent: bool
