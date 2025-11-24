import base64
import io
from typing import List, Dict

from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def generate_pdf_report(risk_record: Dict) -> Dict:
    """
    Gera um PDF simples com informação do registo de risco.
    Devolve dict com filename e data (base64).
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    text = c.beginText(40, 800)
    text.textLine("Check Insurance Risk - Relatório de Análise")
    text.textLine("")
    for key in [
        "id",
        "full_name",
        "nif",
        "passport",
        "resident_card",
        "risk_level",
        "risk_score",
        "analyzed_at",
        "decision",
    ]:
        if key in risk_record:
            text.textLine(f"{key}: {risk_record[key]}")

    c.drawText(text)
    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return {
        "filename": f"risk_report_{risk_record.get('id', 'unknown')}.pdf",
        "data": base64.b64encode(pdf_bytes).decode("utf-8"),
    }


def export_to_excel(records: List[Dict]) -> Dict:
    """
    Exporta uma lista de registos de risco para Excel simples.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Risk Records"

    if not records:
        wb_bytes = io.BytesIO()
        wb.save(wb_bytes)
        return {
            "filename": "risk_analysis_export.xlsx",
            "data": base64.b64encode(wb_bytes.getvalue()).decode("utf-8"),
        }

    headers = list(records[0].keys())
    ws.append(headers)

    for rec in records:
        ws.append([rec.get(h) for h in headers])

    wb_bytes = io.BytesIO()
    wb.save(wb_bytes)

    return {
        "filename": "risk_analysis_export.xlsx",
        "data": base64.b64encode(wb_bytes.getvalue()).decode("utf-8"),
    }


def generate_dashboard_charts() -> Dict:
    """
    Para já devolve apenas estrutura simples.
    O frontend pode usar isto para futuros gráficos.
    """
    return {
        "charts": [],
        "generated": True,
    }
