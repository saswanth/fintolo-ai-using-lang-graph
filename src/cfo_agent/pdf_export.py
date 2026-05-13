from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


def export_board_pdf(
    output_dir: str,
    company_name: str,
    period_label: str,
    kpis: Dict[str, Any],
    narrative: str,
    chart_paths: List[str],
) -> str:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    safe_period = period_label.replace(" ", "_")
    pdf_path = output / f"cfo_board_pack_{safe_period}.pdf"

    c = canvas.Canvas(str(pdf_path), pagesize=LETTER)
    width, height = LETTER

    c.setFillColor(colors.HexColor("#0B3A53"))
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#F7F4EA"))
    c.setFont("Helvetica-Bold", 38)
    c.drawString(0.9 * inch, height - 2.2 * inch, "Fintolo")
    c.setFont("Helvetica", 18)
    c.drawString(0.9 * inch, height - 2.8 * inch, "Board Financial Pack")
    c.setFont("Helvetica", 13)
    c.drawString(0.9 * inch, height - 3.2 * inch, company_name)
    c.drawString(0.9 * inch, height - 3.5 * inch, period_label)
    c.showPage()

    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(0.75 * inch, height - 0.8 * inch, "Executive Summary")
    c.setFont("Helvetica", 11)

    text_obj = c.beginText(0.75 * inch, height - 1.2 * inch)
    for line in narrative.split(". "):
        chunk = line.strip()
        if not chunk:
            continue
        if not chunk.endswith("."):
            chunk = chunk + "."
        text_obj.textLine(chunk)
    c.drawText(text_obj)

    c.setFont("Helvetica-Bold", 14)
    c.drawString(0.75 * inch, height - 3.2 * inch, "KPI Snapshot")
    c.setFont("Helvetica", 11)
    metrics = [
        f"Revenue: ${kpis['revenue_latest']:,.0f}",
        f"Revenue Growth MoM: {kpis['revenue_mom_pct'] * 100:+.1f}%",
        f"Operating Margin: {kpis['operating_margin_latest'] * 100:.1f}%",
        f"Cash Balance: ${kpis['cash_balance_latest']:,.0f}",
        f"Cash Runway: {kpis['cash_runway_label']}",
    ]
    y = height - 3.55 * inch
    for metric in metrics:
        c.drawString(0.9 * inch, y, f"- {metric}")
        y -= 0.24 * inch

    c.showPage()

    c.setFont("Helvetica-Bold", 18)
    c.drawString(0.75 * inch, height - 0.8 * inch, "Performance Visuals")

    x_positions = [0.7 * inch, 4.35 * inch]
    y_positions = [height - 4.1 * inch, height - 7.8 * inch]

    for idx, chart in enumerate(chart_paths[:4]):
        path = Path(chart)
        if not path.exists():
            continue
        row = idx // 2
        col = idx % 2
        c.drawImage(
            str(path),
            x_positions[col],
            y_positions[row],
            width=3.2 * inch,
            height=2.5 * inch,
            preserveAspectRatio=True,
            anchor="sw",
        )

    c.save()
    return str(pdf_path)
