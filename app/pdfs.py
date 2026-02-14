from __future__ import annotations

from datetime import datetime
from io import BytesIO
import hashlib
import os
from typing import Any, Dict, List, Optional

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
# Helpers: bank-grade semantics
# -----------------------------

def score_to_level(score: int) -> str:
    # Ajusta thresholds conforme política do banco/seguradora
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
        return "Risco moderado. Recomenda-se validações adicionais e monitorização reforçada."
    return "Risco baixo. Aplicável diligência padrão e monitorização normal."


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


def _maybe_logo() -> Optional[Image]:
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

    c.drawString(18 * mm, 12 * mm, "Documento confidencial. Distribuição não autorizada é proibida.")
    c.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Página {doc.page}")

    c.restoreState()


def _money(v: Any) -> str:
    if v is None or v == "":
        return "-"
    try:
        # Não inventar moeda; apenas formatar
        return f"{int(v):,}".replace(",", ".")
    except Exception:
        return str(v)


def _date(v: Any) -> str:
    if not v:
        return "-"
    try:
        if hasattr(v, "strftime"):
            return v.strftime("%Y-%m-%d")
    except Exception:
        pass
    return str(v)


# ---------------------------------
# Main: build institutional PDF v3
# ---------------------------------

def build_risk_pdf_institutional(
    risk: Risk,
    analyst_name: str,
    generated_at: datetime,
    integrity_hash: str,
    server_signature: str,
    verify_url: str,
    policies: Optional[List[Dict[str, Any]]] = None,
    underwriting_kpis: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    policies: lista de apólices/histórico do seguro (DB agora; Excel->DB depois)
    underwriting_kpis: dict com indicadores calculados (hoje pode ser vazio)
    """
    policies = policies or []
    underwriting_kpis = underwriting_kpis or {}

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

    elements = []

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

    # ---------- Report Meta ----------
    report_no = make_report_number(risk)
    score_int = int(risk.score) if str(risk.score).isdigit() else 0
    risk_level = score_to_level(score_int)

    app_version = getattr(settings, "APP_VERSION", "v1.0")
    app_env = getattr(settings, "APP_ENV", "Production")
    system_version = f"{app_version} ({app_env})"

    meta = [
        ["Nº do Relatório", report_no],
        ["ID da Análise", str(risk.id)],
        ["Entidade (Tenant)", str(risk.entity_id)],
        ["Analista", analyst_name],
        ["Gerado em (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S")],
        ["Versão do Sistema", system_version],
    ]
    meta_table = Table(meta, colWidths=[45 * mm, 135 * mm])
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

    # ---------- 1) Visão Geral ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("1) Visão Geral do Risco", H2))

    overview = [
        ["Nome Consultado", risk.query_name or ""],
        ["Nacionalidade", risk.query_nationality or ""],
        ["BI", risk.query_bi or ""],
        ["Passaporte", risk.query_passport or ""],
        ["Estado", getattr(risk.status, "value", str(risk.status))],
        ["Score", str(risk.score)],
        ["Nível de Risco", risk_level],
        ["Interpretação", score_interpretation_pt(score_int)],
    ]
    ov_table = Table(overview, colWidths=[45 * mm, 135 * mm])
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

    # ---------- 2) Controlo de Apólices ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("2) Controlo de Apólices e Histórico de Seguro", H2))

    if not policies:
        elements.append(Paragraph("Sem dados de apólices/histórico disponíveis nesta fase.", normal))
    else:
        rows = [[
            "Nº Apólice",
            "Ramo",
            "Tipo/Produto",
            "Estado",
            "Início",
            "Fim",
            "Prémio",
            "Capital",
            "Observações"
        ]]

        for p in policies[:20]:
            rows.append([
                str(p.get("policy_no", "-")),
                str(p.get("branch", "-")),
                str(p.get("product_type", "-")),
                str(p.get("status", "-")),
                _date(p.get("start_date")),
                _date(p.get("end_date")),
                _money(p.get("premium")),
                _money(p.get("sum_insured")),
                str(p.get("note", p.get("observations", "-")) or "-"),
            ])

        pol_table = Table(
            rows,
            colWidths=[26*mm, 18*mm, 22*mm, 18*mm, 16*mm, 16*mm, 18*mm, 18*mm, 28*mm],
            repeatRows=1,
        )
        pol_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1F44")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.8),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(pol_table)

    # ---------- 3) Indicadores Underwriting ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("3) Indicadores de Subscrição (Underwriting)", H2))

    def k(key: str, default: str = "-") -> Any:
        v = underwriting_kpis.get(key)
        return default if v is None or v == "" else v

    uw_rows = [
        ["Indicador", "Valor", "Impacto/Leitura"],
        ["Pagamentos em atraso (30/90 dias)", str(k("late_payments_30_90", "-")), str(k("late_payments_impact", "-"))],
        ["Taxa de pagamento (últimos 12 meses)", str(k("payment_rate_12m", "-")), str(k("payment_rate_impact", "-"))],
        ["Sinistros (últimos 24 meses)", str(k("claims_24m", "-")), str(k("claims_impact", "-"))],
        ["Montante pago em sinistros", str(k("claims_paid_total", "-")), str(k("claims_paid_impact", "-"))],
        ["Apólices activas", str(k("active_policies", "-")), str(k("active_policies_impact", "-"))],
        ["Cancelamentos/Rescisões", str(k("cancellations", "-")), str(k("cancellations_impact", "-"))],
        ["Flags de fraude", str(k("fraud_flags", "-")), str(k("fraud_flags_impact", "-"))],
    ]

    uw_table = Table(uw_rows, colWidths=[70*mm, 35*mm, 75*mm], repeatRows=1)
    uw_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1F44")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    elements.append(uw_table)

    # ---------- 4) Correspondências (Compliance) ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("4) Resultados de Compliance (PEP / Sanções / Watchlists)", H2))

    matches = risk.matches or []
    if not matches:
        elements.append(Paragraph("Sem correspondências registadas pelo motor de compliance nesta fase.", normal))
    else:
        rows = [["Tipo", "Fonte", "Match", "Confiança", "Motivo/Nota"]]
        for m in matches[:12]:
            conf = "-"
            if m.get("confidence") is not None:
                try:
                    conf = f"{float(m.get('confidence', 0)) * 100:.0f}%"
                except Exception:
                    conf = str(m.get("confidence"))

            rows.append([
                str(m.get("type", m.get("category", "-"))),
                str(m.get("source", "-")),
                "SIM" if m.get("match") else "NÃO",
                conf,
                str(m.get("reason") or m.get("note") or "-"),
            ])

        mt = Table(rows, colWidths=[20*mm, 35*mm, 15*mm, 20*mm, 90*mm], repeatRows=1)
        mt.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1F44")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ]
            )
        )
        elements.append(mt)

    # ---------- 5) Sumário ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("5) Sumário e Observações", H2))
    elements.append(Paragraph(risk.summary or "-", normal))

    # ---------- 6) Metodologia ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("6) Metodologia e Declaração", H2))
    methodology = (
        "Este relatório resulta de um processo automatizado de triagem e avaliação de risco, com base nas fontes "
        "configuradas (PEP, sanções e watchlists) e nos dados internos de histórico de seguro (quando disponíveis). "
        "O score é indicativo e deve ser interpretado em conjunto com as políticas internas da instituição, validação humana "
        "e diligência reforçada quando aplicável."
    )
    elements.append(Paragraph(methodology, normal))

    # ---------- 7) Verificação ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("7) Verificação do Documento", H2))

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

    # Build com rodapé e paginação
    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)

    buffer.seek(0)
    return buffer.read()
