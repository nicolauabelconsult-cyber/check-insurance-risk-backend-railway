from __future__ import annotations

from datetime import datetime
from io import BytesIO
import hashlib
import os
from typing import Any

import qrcode

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

from app.settings import settings
from app.models import Risk


# -----------------------------
# Helpers: semântica bancária
# -----------------------------

def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def score_to_level(score: int) -> str:
    # thresholds ajustáveis por política
    if score >= 70:
        return "ALTO"
    if score >= 40:
        return "MÉDIO"
    return "BAIXO"


def score_interpretation_pt(score: int) -> str:
    level = score_to_level(score)
    if level == "ALTO":
        return "Acima do limiar institucional. Recomenda-se diligência reforçada (EDD) e validação humana."
    if level == "MÉDIO":
        return "Risco moderado. Poderá exigir verificações adicionais e validação documental."
    return "Risco reduzido. Recomenda-se monitorização padrão conforme política interna."


def make_integrity_hash(risk: Risk) -> str:
    raw = f"{risk.id}|{risk.entity_id}|{risk.score}|{getattr(risk.status,'value',risk.status)}|{risk.created_at}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_server_signature(integrity_hash: str) -> str:
    secret = getattr(settings, "PDF_SECRET_KEY", None) or os.getenv("PDF_SECRET_KEY") or "change-me"
    raw = f"{integrity_hash}|{secret}"
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
    Opcional: logo se existir.
    Define em env: PDF_LOGO_PATH=/opt/render/project/src/app/assets/logo.png
    IMPORTANTE: nunca pode rebentar o PDF se o ficheiro não existir.
    """
    path = getattr(settings, "PDF_LOGO_PATH", None) or os.getenv("PDF_LOGO_PATH")
    if not path:
        return None
    try:
        if not os.path.exists(path):
            return None
        return Image(path, width=22 * mm, height=22 * mm)
    except Exception:
        return None


def _footer(c: canvas.Canvas, doc):
    c.saveState()
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)

    c.drawString(18 * mm, 12 * mm, "Documento confidencial. Distribuição não autorizada é proibida.")
    c.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Página {doc.page}")
    c.restoreState()


def _pretty_url(url: str, font_name: str, font_size: int) -> str:
    lines = simpleSplit(url, font_name, font_size, 120 * mm)
    lines = lines[:3]
    return "<br/>".join(lines)


# ---------------------------------
# PDF institucional (banco-ready)
# ---------------------------------

def build_risk_pdf_institutional(
    risk: Risk,
    analyst_name: str,
    generated_at: datetime,
    integrity_hash: str,
    server_signature: str,
    verify_url: str,
    underwriting: dict | None = None,
) -> bytes:
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Check Insurance Risk - Relatório de Risco",
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
    normal = ParagraphStyle("N", parent=styles["Normal"], fontSize=9, leading=12)
    small_grey = ParagraphStyle("SG", parent=styles["Normal"], fontSize=7.8, textColor=colors.grey, leading=10)

    elements: list[Any] = []

    # ---------- Cabeçalho ----------
    logo = _maybe_logo()
    header_left = []
    if logo:
        header_left.append(logo)
    header_left.append(Paragraph("<b>CHECK INSURANCE RISK</b><br/>KYC • AML • PEP • Due Diligence", small_grey))

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

    # ---------- Metadados do relatório ----------
    report_no = make_report_number(risk)
    score_int = _safe_int(getattr(risk, "score", 0), 0)
    risk_level = score_to_level(score_int)

    app_version = getattr(settings, "APP_VERSION", "v1.0")
    app_env = getattr(settings, "APP_ENV", "Production")
    system_version = f"{app_version} ({app_env})"

    meta = [
        ["Número do Relatório", report_no],
        ["ID da Análise", str(risk.id)],
        ["Entidade (Tenant)", str(risk.entity_id)],
        ["Analista", analyst_name],
        ["Gerado em (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S")],
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

    # ---------- Resumo do risco ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("1. Identificação e Resumo de Risco", H2))

    overview = [
        ["Nome pesquisado", risk.query_name or ""],
        ["Nacionalidade", risk.query_nationality or ""],
        ["BI", risk.query_bi or ""],
        ["Passaporte", risk.query_passport or ""],
        ["Estado", getattr(risk.status, "value", str(risk.status))],
        ["Score", str(getattr(risk, "score", ""))],
        ["Nível de risco", risk_level],
        ["Interpretação", score_interpretation_pt(score_int)],
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

    # ---------- Match de compliance (PEP/Sanções) ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("2. Resultados de Compliance (PEP/Sanções)", H2))

    matches = risk.matches or []
    if not matches:
        elements.append(Paragraph("Não foram identificados alertas nas fontes de compliance configuradas.", normal))
    else:
        rows = [["Fonte", "Tipo", "Correspondência", "Confiança", "Detalhe / Observação"]]
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
                    str(m.get("category", m.get("type", "PEP"))),
                    "SIM" if m.get("match") else "NÃO",
                    conf,
                    str(m.get("note", m.get("details", ""))),
                ]
            )

        mt = Table(rows, colWidths=[28 * mm, 22 * mm, 22 * mm, 22 * mm, 86 * mm])
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

        elements.append(Spacer(1, 4))
        elements.append(
            Paragraph(
                "Nota: correspondências em compliance exigem validação humana antes de decisão final.",
                small_grey,
            )
        )

    # ---------- Underwriting (seguro) ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("3. Underwriting (Indicadores para Aceitação de Apólice)", H2))

    if underwriting is None:
        elements.append(
            Paragraph(
                "Módulo de underwriting ainda não está activo neste ambiente. Estrutura preparada para carregar dados (Excel/DB) e calcular KPIs.",
                normal,
            )
        )
    else:
        uw_score = underwriting.get("uw_score")
        uw_decision = underwriting.get("uw_decision")
        uw_summary = underwriting.get("uw_summary")
        uw_kpis = underwriting.get("uw_kpis") or {}
        uw_factors = underwriting.get("uw_factors") or []

        # KPIs principais (tabela)
        kpi_rows = [["Indicador", "Valor"]]
        for key, val in uw_kpis.items():
            kpi_rows.append([str(key), str(val)])

        kpi_table = Table(kpi_rows, colWidths=[70 * mm, 110 * mm])
        kpi_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1F44")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )

        decision_block = [
            ["Score Underwriting", str(uw_score)],
            ["Decisão sugerida", str(uw_decision)],
        ]
        decision_table = Table(decision_block, colWidths=[50 * mm, 130 * mm])
        decision_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )

        elements.append(decision_table)
        elements.append(Spacer(1, 6))
        if uw_summary:
            elements.append(Paragraph(f"<b>Resumo:</b> {uw_summary}", normal))
            elements.append(Spacer(1, 6))

        elements.append(Paragraph("<b>KPIs:</b>", normal))
        elements.append(kpi_table)

        elements.append(Spacer(1, 6))
        if uw_factors:
            elements.append(Paragraph("<b>Fatores de decisão (explicabilidade):</b>", normal))
            for f in uw_factors[:12]:
                elements.append(Paragraph(f"• {str(f)}", normal))

    # ---------- Sumário narrativo ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("4. Sumário da Avaliação", H2))
    elements.append(Paragraph(risk.summary or "-", normal))

    # ---------- Metodologia & Disclaimer ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("5. Metodologia e Limitações", H2))
    methodology = (
        "Este relatório é gerado por processo automático de triagem (KYC/AML/PEP) e, quando disponível, por indicadores de underwriting. "
        "Os resultados são indicativos e não substituem validação humana, documentação suporte e políticas internas do segurador. "
        "Em caso de alertas (PEP/Sanções), recomenda-se diligência reforçada (EDD)."
    )
    elements.append(Paragraph(methodology, normal))

    # ---------- Verificação pública (hash + QR) ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("6. Verificação do Documento (Integridade)", H2))

    qr = _qr_image(verify_url)
    pretty_url = _pretty_url(verify_url, normal.fontName, int(normal.fontSize))

    ver_table = Table(
        [[qr, Paragraph(f"<b>URL de verificação:</b><br/>{pretty_url}", normal)]],
        colWidths=[40 * mm, 140 * mm],
    )
    ver_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    elements.append(ver_table)

    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"<b>Hash de Integridade:</b> {integrity_hash}", small_grey))
    elements.append(Paragraph(f"<b>Assinatura do Servidor (simplificada):</b> {server_signature}", small_grey))

    # Build com rodapé/paginação
    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)

    buffer.seek(0)
    return buffer.read()
