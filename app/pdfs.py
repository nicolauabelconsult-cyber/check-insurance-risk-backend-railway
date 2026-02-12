from __future__ import annotations

import hashlib
from datetime import datetime
from io import BytesIO

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, Spacer, Table, SimpleDocTemplate

from app.models import Risk
from app.settings import settings


def make_integrity_hash(risk: Risk) -> str:
    """Deterministic hash for public verification.

    Keep it stable across PDF re-generations.
    """
    created = risk.created_at.isoformat() if getattr(risk, "created_at", None) else ""
    raw = f"{risk.id}|{risk.entity_id}|{risk.score}|{created}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_server_signature(integrity_hash: str) -> str:
    """Simplified server signature (HMAC-like) used to prove the PDF was issued by the server."""
    raw = f"{integrity_hash}|{settings.PDF_SECRET_KEY}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _qr_image(verify_url: str) -> Image:
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(verify_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)

    # ✅ Platypus Image aceita file-like (BytesIO), não ImageReader
    return Image(bio, width=40 * mm, height=40 * mm)


def build_risk_pdf_institutional(
    *,
    risk: Risk,
    analyst_name: str,
    generated_at: datetime,
    integrity_hash: str,
    server_signature: str,
    verify_url: str,
) -> bytes:
    """Generate an institutional PDF for a risk assessment."""

    buf = BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Check Insurance Risk - Risk Assessment Report",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CIRTitle",
        parent=styles["Title"],
        textColor=colors.HexColor("#0A1F44"),
        spaceAfter=6,
    )
    h2 = ParagraphStyle(
        "CIRH2",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#0A1F44"),
        spaceBefore=6,
        spaceAfter=10,
    )
    label = ParagraphStyle(
        "CIRLabel",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
    )
    small = ParagraphStyle(
        "CIRSmall",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.grey,
        leading=10,
    )

    elements = []

    # Header
    elements.append(Paragraph("CHECK INSURANCE RISK", title_style))
    elements.append(Paragraph("Risk Assessment Report", h2))

    elements.append(Paragraph(f"<b>Risk ID:</b> {risk.id}", label))
    elements.append(Paragraph(f"<b>Entity ID:</b> {risk.entity_id}", label))
    elements.append(Paragraph(f"<b>Analyst:</b> {analyst_name}", label))
    elements.append(Paragraph(f"<b>Generated at (UTC):</b> {generated_at.strftime('%Y-%m-%d %H:%M:%S')}", label))
    elements.append(Spacer(1, 10))

    # Core table
    data = [
        ["Metric", "Value"],
        ["Query Name", risk.query_name or ""],
        ["Nationality", risk.query_nationality or ""],
        ["BI", risk.query_bi or ""],
        ["Passport", risk.query_passport or ""],
        ["Score", risk.score or ""],
        ["Status", risk.status.value if hasattr(risk.status, "value") else str(risk.status)],
    ]

    table = Table(data, colWidths=[55 * mm, 110 * mm])
    table.setStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1F44")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ]
    )
    elements.append(table)
    elements.append(Spacer(1, 10))

    # Summary
    if risk.summary:
        elements.append(Paragraph("Summary", h2))
        elements.append(Paragraph(risk.summary, label))
        elements.append(Spacer(1, 10))

    # Verification block (QR + hashes)
    elements.append(Paragraph("Verification", h2))
    qr_img = _qr_image(verify_url)

    ver_table = Table(
        [
            [
                qr_img,
                Paragraph(
                    f"<b>Verify URL:</b> {verify_url}<br/><br/>"
                    f"<b>Integrity Hash:</b> {integrity_hash}<br/><br/>"
                    f"<b>Server Signature:</b> {server_signature}",
                    label,
                ),
            ]
        ],
        colWidths=[45 * mm, 120 * mm],
    )
    ver_table.setStyle(
        [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.lightgrey),
            ("INNERPADDING", (0, 0), (-1, -1), 6),
        ]
    )
    elements.append(ver_table)
    elements.append(Spacer(1, 10))

    # Footer
    elements.append(Paragraph("Confidential document. Unauthorized distribution is prohibited.", small))

    doc.build(elements)
    return buf.getvalue()
