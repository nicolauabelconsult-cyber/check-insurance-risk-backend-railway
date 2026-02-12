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
# Helpers: bank-grade semantics
# -----------------------------

def score_to_level(score: int) -> str:
    # Ajusta thresholds conforme política do banco
    if score >= 70:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


def score_interpretation(score: int) -> str:
    level = score_to_level(score)
    if level == "HIGH":
        return "Above institutional threshold. Enhanced due diligence recommended."
    if level == "MEDIUM":
        return "Moderate risk. Additional checks may be required."
    return "Low risk. Standard monitoring recommended."


def make_integrity_hash(risk: Risk) -> str:
    # Mantém simples e determinístico
    raw = f"{risk.id}|{risk.entity_id}|{risk.score}|{risk.status}|{risk.created_at}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_server_signature(integrity_hash: str) -> str:
    # “Assinatura digital simplificada” (hash + segredo)
    raw = f"{integrity_hash}|{settings.PDF_SECRET_KEY}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_report_number(risk: Risk) -> str:
    """
    Banco-ready sem migração:
    número determinístico baseado em data + parte do UUID.
    (Se quiseres sequência real por entidade, fazemos migration depois.)
    """
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

    # ✅ Platypus Image aceita file-like
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


def _footer(canvas: canvas.Canvas, doc):
    """
    Rodapé institucional com paginação.
    """
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)

    canvas.drawString(
        18 * mm,
        12 * mm,
        "Confidential document. Unauthorized distribution is prohibited."
    )
    canvas.drawRightString(
        A4[0] - 18 * mm,
        12 * mm,
        f"Page {doc.page}"
    )

    canvas.restoreState()


# ---------------------------------
# Main: build institutional PDF v2
# ---------------------------------

def build_risk_pdf_institutional(
    risk: Risk,
    analyst_name: str,
    generated_at: datetime,
    integrity_hash: str,
    server_signature: str,
    verify_url: str,
) -> bytes:
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Check Insurance Risk - Risk Assessment Report",
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
        [[header_left, Paragraph("<b>Risk Assessment Report</b>", H1)]],
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
        ["Report Number", report_no],
        ["Risk ID", str(risk.id)],
        ["Entity ID", str(risk.entity_id)],
        ["Analyst", analyst_name],
        ["Generated at (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S")],
        ["System Version", system_version],
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

    # ---------- Risk Summary ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Risk Overview", H2))

    overview = [
        ["Query Name", risk.query_name or ""],
        ["Nationality", risk.query_nationality or ""],
        ["BI", risk.query_bi or ""],
        ["Passport", risk.query_passport or ""],
        ["Status", getattr(risk.status, "value", str(risk.status))],
        ["Score", str(risk.score)],
        ["Risk Level", risk_level],
        ["Score Interpretation", score_interpretation(score_int)],
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

    # ---------- Matches ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Screening Matches", H2))

    matches = risk.matches or []
    if not matches:
        elements.append(Paragraph("No matches reported by the screening engine.", normal))
    else:
        rows = [["Source", "Match", "Confidence", "Notes"]]
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
                    "YES" if m.get("match") else "NO",
                    conf,
                    str(m.get("note", "")),
                ]
            )
        mt = Table(rows, colWidths=[35 * mm, 18 * mm, 25 * mm, 102 * mm])
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

    # ---------- Narrative Summary ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Assessment Summary", H2))
    elements.append(Paragraph(risk.summary or "-", normal))

    # ---------- Methodology & Disclaimer ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Methodology & Disclaimer", H2))
    methodology = (
        "This report was generated by an automated screening process using configured sanctions, PEP and watchlist sources. "
        "The resulting score is an indicative compliance risk assessment and does not constitute a legal determination. "
        "Institutions should apply internal policies, human review and enhanced due diligence where applicable."
    )
    elements.append(Paragraph(methodology, normal))

    # ---------- Verification ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Document Verification", H2))

    qr = _qr_image(verify_url)

    # Quebra controlada do URL (para não ficar feio no PDF)
    url_lines = simpleSplit(verify_url, normal.fontName, normal.fontSize, 120 * mm)
    url_lines = url_lines[:3]  # no máximo 3 linhas
    pretty_url = "<br/>".join(url_lines)

    ver_table = Table(
        [[qr, Paragraph(f"<b>Verify URL:</b><br/>{pretty_url}", normal)]],
        colWidths=[40 * mm, 140 * mm],
    )
    ver_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    elements.append(ver_table)

    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"<b>Integrity Hash:</b> {integrity_hash}", small_grey))
    elements.append(Paragraph(f"<b>Server Signature:</b> {server_signature}", small_grey))

    # Build com rodapé e paginação
    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)

    buffer.seek(0)
    return buffer.read()
