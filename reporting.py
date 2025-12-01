# reporting.py
from datetime import datetime
from io import BytesIO
from textwrap import wrap

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from openpyxl import Workbook

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors

from models import RiskRecord, User, RiskLevel, RiskDecision


# -------------------------------------------------------------------
# PDF – RELATÓRIO DE RISCO
# -------------------------------------------------------------------
def generate_risk_pdf(db: Session, record: RiskRecord) -> StreamingResponse:
    """
    Gera um PDF simples, bonito e fácil de ler para uma análise de risco.

    Estrutura:
      1. Cabeçalho / título
      2. Dados da análise
      3. Dados do cliente
      4. Principais factores de risco
      5. Alertas
      6. Histórico recente do cliente
    """

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_x = 20 * mm
    bottom_margin = 20 * mm
    y = height - 25 * mm

    now_str = datetime.utcnow().strftime("%d/%m/%Y %H:%M (UTC)")

    analyst_name = record.analyst.username if isinstance(record.analyst, User) else "-"
    created_at_str = (
        record.created_at.strftime("%d/%m/%Y %H:%M")
        if record.created_at
        else "-"
    )

    # Decisão e nível (texto legível)
    try:
        level_enum = RiskLevel(record.level)
        level_label = level_enum.value
    except Exception:
        level_label = str(record.level or "")

    if record.decision:
        try:
            decision_enum = RiskDecision(record.decision)
            decision_label = decision_enum.value
        except Exception:
            decision_label = record.decision
    else:
        decision_label = "PENDENTE"

    # Factores (explicação)
    factors: list[str] = []
    if isinstance(record.explanation, dict) and "factors" in record.explanation:
        raw = record.explanation.get("factors") or []
        factors = [str(f) for f in raw]
    elif isinstance(record.explanation, list):
        factors = [str(f) for f in record.explanation]

    # Alertas
    alerts = list(record.alerts or [])

    # Histórico recente (mesmo NIF/passaporte/cartão ou nome)
    identifier = record.nif or record.passport or record.resident_card or record.full_name
    history_records: list[RiskRecord] = []
    if identifier:
        history_records = (
            db.query(RiskRecord)
            .filter(
                (RiskRecord.nif == identifier)
                | (RiskRecord.passport == identifier)
                | (RiskRecord.resident_card == identifier)
                | (RiskRecord.full_name == identifier)
            )
            .order_by(RiskRecord.created_at.desc())
            .limit(5)
            .all()
        )

    # Helpers de desenho ---------------------------------------------------
    def ensure_space(lines: int = 1):
        """Garante espaço, mudando de página se necessário."""
        nonlocal y
        needed = lines * 14 + 10
        if y - needed < bottom_margin:
            c.showPage()
            y_new = height - 25 * mm
            # pequeno cabeçalho na nova página
            c.setFont("Helvetica", 9)
            c.setFillColor(colors.grey)
            c.drawString(
                margin_x,
                y_new,
                f"Check Insurance Risk – Relatório de Risco (continuação)",
            )
            y_new -= 18
            c.setFillColor(colors.black)
            return y_new
        return y

    def draw_title(text: str):
        nonlocal y
        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(colors.HexColor("#1F2937"))  # cinza escuro
        c.drawString(margin_x, y, text)
        y -= 24

    def draw_subtitle(text: str):
        nonlocal y
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.grey)
        c.drawString(margin_x, y, text)
        y -= 18
        c.setFillColor(colors.black)

    def draw_section(text: str):
        nonlocal y
        y = ensure_space(2)
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.HexColor("#111827"))
        c.drawString(margin_x, y, text)
        y -= 4
        c.setStrokeColor(colors.HexColor("#E5E7EB"))
        c.setLineWidth(0.5)
        c.line(margin_x, y, width - margin_x, y)
        y -= 10
        c.setFillColor(colors.black)

    def draw_kv(label: str, value: str):
        nonlocal y
        y = ensure_space(1)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin_x, y, f"{label}:")
        c.setFont("Helvetica", 10)
        c.drawString(margin_x + 80, y, value[:100])
        y -= 14

    def draw_bullet_list(items: list[str], empty_msg: str):
        nonlocal y
        if not items:
            y = ensure_space(1)
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(margin_x, y, empty_msg)
            y -= 14
            return

        c.setFont("Helvetica", 10)
        max_width_chars = 95  # aproximação simples para quebrar linhas
        for item in items:
            wrapped = wrap(item, max_width_chars)
            for i, line in enumerate(wrapped):
                y = ensure_space(1)
                prefix = "• " if i == 0 else "  "
                c.drawString(margin_x, y, prefix + line)
                y -= 14

    # -------------------------------------------------------------------
    # 1. Cabeçalho
    # -------------------------------------------------------------------
    draw_title("Check Insurance Risk – Relatório de Risco")
    draw_subtitle(f"Análise #{record.id}  ·  Gerado em {now_str}")

    # -------------------------------------------------------------------
    # 2. Dados da análise
    # -------------------------------------------------------------------
    draw_section("1. Dados da Análise")

    draw_kv("ID da análise", str(record.id))
    draw_kv("Data / hora", created_at_str)
    draw_kv("Analista", analyst_name or "-")
    draw_kv("Nível de risco", level_label or "-")
    draw_kv("Score de risco", f"{record.score} / 100")
    draw_kv("Decisão", decision_label)
    if record.decision_notes:
        draw_kv("Recomendações", record.decision_notes[:200])

    # -------------------------------------------------------------------
    # 3. Dados do cliente
    # -------------------------------------------------------------------
    draw_section("2. Dados do Cliente")

    draw_kv("Nome completo", record.full_name or "-")
    draw_kv("NIF", record.nif or "-")
    draw_kv("Passaporte", record.passport or "-")
    draw_kv("Cartão de residente", record.resident_card or "-")
    draw_kv("País / Nacionalidade", record.country or "-")

    # -------------------------------------------------------------------
    # 4. Principais factores de risco
    # -------------------------------------------------------------------
    draw_section("3. Principais Factores de Risco")
    draw_bullet_list(
        factors,
        "Sem factores de risco relevantes registados nesta análise.",
    )

    # -------------------------------------------------------------------
    # 5. Alertas
    # -------------------------------------------------------------------
    draw_section("4. Alertas")
    if not alerts:
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(margin_x, y, "Nenhum alerta associado a esta análise.")
        y -= 14
    else:
        for alert in alerts:
            y = ensure_space(2)
            created_str = (
                alert.created_at.strftime("%d/%m/%Y %H:%M")
                if alert.created_at
                else "-"
            )
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(colors.HexColor("#B91C1C"))  # vermelho discreto
            c.drawString(
                margin_x,
                y,
                f"[{alert.type}] {created_str}",
            )
            y -= 12
            c.setFont("Helvetica", 10)
            c.setFillColor(colors.black)
            for line in wrap(alert.message or "", 95):
                y = ensure_space(1)
                c.drawString(margin_x + 10, y, line)
                y -= 14

    # -------------------------------------------------------------------
    # 6. Histórico recente
    # -------------------------------------------------------------------
    draw_section("5. Histórico Recente do Cliente")

    if not history_records:
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(
            margin_x,
            y,
            "Não existem outras análises registadas para este cliente.",
        )
        y -= 14
    else:
        # Cabeçalho da “tabela”
        c.setFont("Helvetica-Bold", 9)
        y = ensure_space(1)
        c.drawString(margin_x, y, "Data")
        c.drawString(margin_x + 90, y, "Score")
        c.drawString(margin_x + 140, y, "Nível")
        c.drawString(margin_x + 220, y, "Decisão")
        y -= 12
        c.setStrokeColor(colors.HexColor("#E5E7EB"))
        c.setLineWidth(0.5)
        c.line(margin_x, y, width - margin_x, y)
        y -= 8

        c.setFont("Helvetica", 9)
        for h in history_records:
            y = ensure_space(1)
            h_date = h.created_at.strftime("%d/%m/%Y %H:%M") if h.created_at else "-"
            try:
                h_level = RiskLevel(h.level).value
            except Exception:
                h_level = h.level or "-"
            if h.decision:
                try:
                    h_dec = RiskDecision(h.decision).value
                except Exception:
                    h_dec = h.decision
            else:
                h_dec = "PENDENTE"

            c.drawString(margin_x, y, h_date)
            c.drawString(margin_x + 90, y, str(h.score))
            c.drawString(margin_x + 140, y, h_level)
            c.drawString(margin_x + 220, y, h_dec[:20])
            y -= 12

    # -------------------------------------------------------------------
    # Rodapé
    # -------------------------------------------------------------------
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)
    c.drawString(
        margin_x,
        bottom_margin - 5 * mm,
        "Relatório gerado automaticamente pelo sistema Check Insurance Risk.",
    )

    c.showPage()
    c.save()

    buffer.seek(0)
    filename = f"relatorio_risco_{record.id}.pdf"

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# -------------------------------------------------------------------
# EXPORTAÇÃO EXCEL (mantido)
# -------------------------------------------------------------------
def export_risk_excel(db: Session) -> StreamingResponse:
    """
    Exporta todos os registos de risco em formato .xlsx usando openpyxl
    (sem pandas, para evitar problemas de build no Render).
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Análises de Risco"

    # Cabeçalho
    headers = [
        "ID",
        "Data Análise",
        "Nome",
        "NIF",
        "Passaporte",
        "Cartão Residente",
        "País",
        "Score",
        "Nível",
        "Decisão",
        "Analista",
    ]
    ws.append(headers)

    # Dados
    records = db.query(RiskRecord).order_by(RiskRecord.created_at.desc()).all()

    for r in records:
        analyst_name = r.analyst.username if isinstance(r.analyst, User) else None
        ws.append(
            [
                r.id,
                r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
                r.full_name,
                r.nif or "",
                r.passport or "",
                r.resident_card or "",
                r.country or "",
                r.score,
                r.level,
                r.decision or "",
                analyst_name or "",
            ]
        )

    # Guardar em memória
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    filename = f"check_insurance_risk_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
