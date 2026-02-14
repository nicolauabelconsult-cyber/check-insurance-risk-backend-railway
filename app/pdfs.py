from __future__ import annotations

from datetime import datetime
from io import BytesIO
import hashlib
import os

import qrcode

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)

from app.settings import settings
from app.models import Risk


# -----------------------------
# Helpers: semântica "banco"
# -----------------------------

def score_to_level(score: int) -> str:
    # Ajusta thresholds conforme política do banco
    if score >= 70:
        return "ALTO"
    if score >= 40:
        return "MÉDIO"
    return "BAIXO"


def score_interpretation(score: int) -> str:
    level = score_to_level(score)
    if level == "ALTO":
        return "Acima do limiar institucional. Recomenda-se diligência reforçada (EDD)."
    if level == "MÉDIO":
        return "Risco moderado. Podem ser necessários controlos adicionais."
    return "Risco baixo. Recomenda-se monitorização padrão."


def make_integrity_hash(risk: Risk) -> str:
    raw = f"{risk.id}|{risk.entity_id}|{risk.score}|{risk.status}|{risk.created_at}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_server_signature(integrity_hash: str) -> str:
    raw = f"{integrity_hash}|{settings.PDF_SECRET_KEY}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_report_number(risk: Risk) -> str:
    dt = risk.created_at or datetime.utcnow()
    ymd = dt.strftime("%Y%m%d")
    short = str(risk.id).split("-")[0].upper()
    return f"CIR-{ymd}-{short}"


def _qr_image(verify_url: str) -> Image:
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(verify_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)

    return Image(bio, width=35 * mm, height=35 * mm)


def _maybe_logo() -> Image | None:
    """
    Opcional: coloca um logo no header se existir.
    Define em env: PDF_LOGO_PATH=/opt/render/project/src/app/assets/logo.png
    """
    path = getattr(settings, "PDF_LOGO_PATH", None) or os.getenv("PDF_LOGO_PATH")
    if not path:
        return None
    if not os.path.exists(path):
        return None
    return Image(path, width=22 * mm, height=22 * mm)


def _footer(c: canvas.Canvas, doc):
    c.saveState()
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)

    c.drawString(
        18 * mm,
        12 * mm,
        "Documento confidencial. A distribuição não autorizada é proibida."
    )
    c.drawRightString(
        A4[0] - 18 * mm,
        12 * mm,
        f"Página {doc.page}"
    )
    c.restoreState()


def _money(v) -> str:
    if v is None:
        return "-"
    try:
        return f"{int(v):,}".replace(",", ".") + " AOA"
    except Exception:
        return str(v)


# ---------------------------------
# PDF Institucional (PT) - vFinal
# ---------------------------------

def build_risk_pdf_institutional(
    risk: Risk,
    analyst_name: str,
    generated_at: datetime,
    integrity_hash: str,
    server_signature: str,
    verify_url: str,
    underwriting: dict | None = None,   # ← pronto para crescimento (Excel/API depois)
) -> bytes:
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Check Insurance Risk - Relatório de Avaliação",
        author="Check Insurance Risk",
    )

    styles = getSampleStyleSheet()

    H1 = ParagraphStyle(
        "H1",
        parent=styles["Title"],
        fontSize=16,
        textColor=colors.HexColor("#0A1F44"),
        spaceAfter=6,
    )
    H2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=11,
        textColor=colors.HexColor("#0A1F44"),
        spaceBefore=10,
        spaceAfter=6,
    )
    normal = ParagraphStyle(
        "N",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
    )
    small_grey = ParagraphStyle(
        "SG",
        parent=styles["Normal"],
        fontSize=7.8,
        textColor=colors.grey,
        leading=10,
    )

    elements: list = []

    # ---------- Header ----------
    logo = _maybe_logo()
    header_left = []
    if logo:
        header_left.append(logo)
    header_left.append(
        Paragraph("<b>CHECK INSURANCE RISK</b><br/>KYC • AML • PEP • Due Diligence", small_grey)
    )

    header_table = Table(
        [[header_left, Paragraph("<b>Relatório de Avaliação de Risco</b>", H1)]],
        colWidths=[70 * mm, 110 * mm],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#0A1F44")),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 8))

    # ---------- Meta ----------
    report_no = make_report_number(risk)
    score_int = int(risk.score) if str(risk.score).isdigit() else 0
    risk_level = score_to_level(score_int)

    app_version = getattr(settings, "APP_VERSION", "v1.0")
    app_env = getattr(settings, "APP_ENV", "Production")
    system_version = f"{app_version} ({app_env})"

    meta = [
        ["Nº do Relatório", report_no],
        ["Risk ID", str(risk.id)],
        ["Entidade (Tenant)", str(risk.entity_id)],
        ["Analista", analyst_name],
        ["Data/Hora (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S")],
        ["Versão do Sistema", system_version],
    ]
    meta_table = Table(meta, colWidths=[50 * mm, 130 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(meta_table)

    # ---------- Visão Geral ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("1) Visão Geral do Caso", H2))

    overview = [
        ["Nome Consultado", risk.query_name or ""],
        ["Nacionalidade", risk.query_nationality or ""],
        ["BI", risk.query_bi or ""],
        ["Passaporte", risk.query_passport or ""],
        ["Estado", getattr(risk.status, "value", str(risk.status))],
        ["Score", str(risk.score)],
        ["Nível de Risco", risk_level],
        ["Interpretação", score_interpretation(score_int)],
    ]
    ov_table = Table(overview, colWidths=[50 * mm, 130 * mm])
    ov_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(ov_table)

    # ---------- Achados Compliance (PEP / Sanções) ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("2) Achados de Compliance (PEP / Sanções / Watchlists)", H2))

    matches = risk.matches or []
    if not matches:
        elements.append(Paragraph("Sem correspondências registadas pelo motor de screening.", normal))
    else:
        rows = [["Fonte", "Tipo", "Match", "Confiança", "Motivo/Notas"]]
        for m in matches:
            conf = ""
            if m.get("confidence") is not None:
                try:
                    conf = f"{float(m.get('confidence', 0)) * 100:.0f}%"
                except Exception:
                    conf = str(m.get("confidence"))

            rows.append(
                [
                    str(m.get("source", "")),
                    str(m.get("category", m.get("type", ""))),  # PEP / SANCTION / WATCHLIST
                    "SIM" if m.get("match") else "NÃO",
                    conf,
                    str(m.get("note", "")),
                ]
            )

        mt = Table(rows, colWidths=[32 * mm, 25 * mm, 16 * mm, 22 * mm, 85 * mm])
        mt.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1F44")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.3),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        elements.append(mt)

    # ---------- Underwriting (pronto para Excel/API) ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("3) Indicadores de Subscrição (Underwriting)", H2))

    uw = underwriting or {}
    # estrutura preparada para crescimento
    uw_rows = [
        ["Indicador", "Valor", "Impacto/Leitura"],
        ["Pagamentos em atraso (30/90 dias)", str(uw.get("late_payments_30_90", "-")), str(uw.get("late_payments_note", "-"))],
        ["Taxa de pagamento (últimos 12 meses)", str(uw.get("payment_rate_12m", "-")), str(uw.get("payment_rate_note", "-"))],
        ["Sinistros (últimos 24 meses)", str(uw.get("claims_24m", "-")), str(uw.get("claims_24m_note", "-"))],
        ["Montante pago em sinistros", _money(uw.get("claims_paid_total")), str(uw.get("claims_paid_note", "-"))],
        ["Apólices activas", str(uw.get("active_policies", "-")), str(uw.get("active_policies_note", "-"))],
        ["Cancelamentos/Rescisões", str(uw.get("cancellations", "-")), str(uw.get("cancellations_note", "-"))],
        ["Flags de fraude", str(uw.get("fraud_flags", "-")), str(uw.get("fraud_flags_note", "-"))],
    ]

    uw_table = Table(uw_rows, colWidths=[60 * mm, 45 * mm, 75 * mm])
    uw_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1F44")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("FONTSIZE", (0, 0), (-1, -1), 8.3),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(uw_table)

    # ---------- Sumário ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("4) Sumário Executivo", H2))
    elements.append(Paragraph(risk.summary or "-", normal))

    # ---------- Metodologia ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("5) Metodologia & Nota Legal", H2))
    methodology = (
        "Este relatório foi gerado por um processo automatizado de triagem (screening) com base em fontes configuradas "
        "(PEP, Sanções e Watchlists) e indicadores internos de subscrição (quando disponíveis). "
        "O score representa uma avaliação indicativa de risco de compliance e underwriting, não constituindo decisão legal. "
        "A instituição deve aplicar as suas políticas internas, validação humana e diligência reforçada (EDD) quando aplicável."
    )
    elements.append(Paragraph(methodology, normal))

    # ---------- Verificação ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("6) Verificação Pública do Documento", H2))

    qr = _qr_image(verify_url)
    url_lines = simpleSplit(verify_url, normal.fontName, normal.fontSize, 120 * mm)
    url_lines = url_lines[:3]
    pretty_url = "<br/>".join(url_lines)

    ver_table = Table(
        [[qr, Paragraph(f"<b>URL de Verificação:</b><br/>{pretty_url}", normal)]],
        colWidths=[40 * mm, 140 * mm],
    )
    ver_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    elements.append(ver_table)

    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"<b>Hash de Integridade:</b> {integrity_hash}", small_grey))
    elements.append(Paragraph(f"<b>Assinatura do Servidor:</b> {server_signature}", small_grey))

    # Build com rodapé/paginação
    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)

    buffer.seek(0)
    return buffer.read()
