from datetime import datetime
from io import BytesIO

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors

from models import RiskRecord, RiskLevel, RiskDecision
from risk_engine import get_history_for_identifier


def _choose_identifier(record: RiskRecord) -> str:
    """
    Escolhe o melhor identificador para histórico (NIF, passaporte, cartão, nome).
    """
    return (
        record.nif
        or record.passport
        or record.resident_card
        or record.full_name
        or ""
    )


def generate_risk_pdf(db: Session, record: RiskRecord) -> StreamingResponse:
    """
    Gera um PDF simples, bonito e legível com a informação essencial
    da análise de risco.
    """

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Margens
    left = 20 * mm
    top = height - 20 * mm

    # ------------------------------------------------------------------
    # 1. Cabeçalho
    # ------------------------------------------------------------------
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(colors.HexColor("#1E3A8A"))  # azul escuro
    c.drawString(left, top, "Check Insurance Risk")

    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)
    c.drawString(left, top - 15, "Relatório de análise de risco")

    c.drawRightString(
        width - left,
        top,
        datetime.utcnow().strftime("Gerado em %Y-%m-%d %H:%M UTC"),
    )

    y = top - 35

    # ------------------------------------------------------------------
    # 2. Dados do cliente
    # ------------------------------------------------------------------
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, "1. Dados do cliente")
    y -= 12

    c.setFont("Helvetica", 10)
    linhas_cliente = [
        f"Nome: {record.full_name}",
        f"NIF: {record.nif or '-'}",
        f"Passaporte: {record.passport or '-'}",
        f"Cartão de residente: {record.resident_card or '-'}",
        f"País / Nacionalidade: {record.country or '-'}",
    ]
    for linha in linhas_cliente:
        c.drawString(left, y, linha)
        y -= 12

    y -= 8

    # ------------------------------------------------------------------
    # 3. Resumo de risco
    # ------------------------------------------------------------------
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, "2. Resumo de risco")
    y -= 14

    score = record.score or 0
    level = record.level or "LOW"
    decisao = record.decision or "PENDENTE"

    # Caixa com score
    c.setStrokeColor(colors.HexColor("#3B82F6"))
    c.setFillColor(colors.HexColor("#DBEAFE"))
    c.rect(left, y - 35, 60 * mm, 30, fill=1, stroke=1)

    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(left + 5, y - 15, f"{score:.0f}")
    c.setFont("Helvetica", 9)
    c.drawString(left + 5, y - 27, "Score de risco (0–100)")

    # Nível e decisão ao lado
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left + 70 * mm, y - 10, f"Nível: {level}")
    c.drawString(left + 70 * mm, y - 25, f"Decisão: {decisao}")

    y -= 45

    # Legenda simples
    c.setFont("Helvetica", 9)
    c.drawString(left, y, "Legenda níveis:")
    y -= 11
    c.drawString(left + 10, y, "LOW  – risco baixo")
    y -= 11
    c.drawString(left + 10, y, "MEDIUM – risco moderado")
    y -= 11
    c.drawString(left + 10, y, "HIGH – risco elevado")
    y -= 11
    c.drawString(left + 10, y, "CRITICAL – risco muito elevado / bloquear operação")
    y -= 16

    # ------------------------------------------------------------------
    # 4. Principais factores de risco (“pequena IA”)
    # ------------------------------------------------------------------
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, "3. Principais factores identificados")
    y -= 14

    c.setFont("Helvetica", 9)

    explanation = record.explanation or {}
    factors = explanation.get("factors") or explanation.get("fatores") or []
    if factors:
        for f in factors:
            if y < 60:
                c.showPage()
                y = top
                c.setFont("Helvetica-Bold", 12)
                c.drawString(left, y, "3. Principais factores identificados (cont.)")
                y -= 16
                c.setFont("Helvetica", 9)
            c.drawString(left + 10, y, u"• " + str(f))
            y -= 11
    else:
        c.drawString(left + 10, y, "Nenhum factor relevante registado.")
        y -= 14

    y -= 6

    # ------------------------------------------------------------------
    # 5. Histórico do cliente
    # ------------------------------------------------------------------
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, "4. Histórico de análises para este cliente")
    y -= 14
    c.setFont("Helvetica", 9)

    identifier = _choose_identifier(record)
    history_records = []
    if identifier:
        history_records = get_history_for_identifier(db, identifier)

    if not history_records:
        c.drawString(left + 10, y, "Sem histórico adicional registado.")
        y -= 12
    else:
        c.drawString(left + 10, y, "Data        Score    Nível    Decisão")
        y -= 11
        for h in history_records[:10]:
            if y < 50:
                c.showPage()
                y = top
                c.setFont("Helvetica-Bold", 12)
                c.drawString(left, y, "4. Histórico de análises (cont.)")
                y -= 16
                c.setFont("Helvetica", 9)

            dt_str = h.created_at.strftime("%Y-%m-%d") if h.created_at else "-"
            lvl = getattr(h, "level", None) or "-"
            dec = getattr(h, "decision", None) or "-"
            line = f"{dt_str:10}  {h.score:5}    {lvl:7}  {dec}"
            c.drawString(left + 10, y, line)
            y -= 11

    y -= 8

    # ------------------------------------------------------------------
    # 6. Observações / Recomendações
    # ------------------------------------------------------------------
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, "5. Observações do analista")
    y -= 14

    c.setFont("Helvetica", 9)
    notes = record.decision_notes or "Sem observações adicionais."
    for line in notes.splitlines() or ["Sem observações adicionais."]:
        if y < 40:
            c.showPage()
            y = top
            c.setFont("Helvetica-Bold", 12)
            c.drawString(left, y, "5. Observações do analista (cont.)")
            y -= 16
            c.setFont("Helvetica", 9)
        c.drawString(left + 10, y, line)
        y -= 11

    # ------------------------------------------------------------------
    # Finalizar
    # ------------------------------------------------------------------
    c.showPage()
    c.save()
    buffer.seek(0)

    filename = f"relatorio_risco_{record.id}.pdf"

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
