# app/reporting.py
import io
from typing import List

from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

import pandas as pd
from sqlalchemy.orm import Session

from .models import RiskRecord


def generate_risk_pdf(db: Session, risk: RiskRecord) -> StreamingResponse:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "RELATÓRIO DE ANÁLISE DE RISCO – CLIENTE / ASSEGURADO")
    y -= 30

    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"ID Análise: {risk.id}")
    y -= 15
    c.drawString(40, y, f"Data: {risk.created_at}")
    y -= 25

    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Resumo Rápido")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Score: {risk.score}")
    y -= 15
    c.drawString(40, y, f"Nível: {risk.level}")
    y -= 15
    c.drawString(40, y, f"Decisão: {risk.decision or '—'}")
    y -= 25

    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Identificação do Assegurado")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Nome: {risk.full_name}")
    y -= 15
    c.drawString(40, y, f"NIF: {risk.nif or '-'}")
    y -= 15
    c.drawString(40, y, f"Passaporte: {risk.passport or '-'}")
    y -= 15
    c.drawString(40, y, f"Cartão Residente: {risk.resident_card or '-'}")
    y -= 15
    c.drawString(40, y, f"Nacionalidade: {risk.country or '-'}")
    y -= 25

    if risk.explanation:
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, "Principais Fatores")
        y -= 20
        c.setFont("Helvetica", 10)
        for factor in risk.explanation:
            if y < 80:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)
            c.drawString(60, y, f"- {factor}")
            y -= 15

    c.setFont("Helvetica", 8)
    c.drawString(
        40,
        40,
        "Relatório gerado por Check Insurance Risk v2.0 – Motor de Análise Multi-Fonte",
    )

    c.showPage()
    c.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=risk_report_{risk.id}.pdf"},
    )


def export_risk_excel(db: Session) -> StreamingResponse:
    qs = db.query(RiskRecord).order_by(RiskRecord.created_at.desc()).all()
    rows: List[dict] = []
    for r in qs:
        rows.append(
            {
                "ID": r.id,
                "Data": r.created_at,
                "Nome": r.full_name,
                "NIF": r.nif,
                "Score": r.score,
                "Nível": r.level,
                "Decisão": r.decision,
            }
        )
    df = pd.DataFrame(rows)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Riscos")
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=risk_export.xlsx"},
    )
