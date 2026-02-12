from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
from datetime import datetime
import hashlib
import qrcode

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

from core.deps import get_db, get_current_user
from core.permissions import require_perm
from models import Risk
from audit.service import log_action
from core.config import settings  # deve conter PDF_SECRET_KEY e BASE_URL

router = APIRouter()


@router.get("/risks/{risk_id}/pdf")
def generate_risk_pdf(
    risk_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    require_perm(current_user, "risk:read")

    risk = (
        db.query(Risk)
        .filter(
            Risk.id == risk_id,
            Risk.entity_id == current_user.entity_id,
        )
        .first()
    )

    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=60,
        bottomMargin=60,
    )

    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Title"],
        textColor=colors.HexColor("#0A1F44"),
    )

    normal_style = styles["Normal"]

    # Header
    elements.append(Paragraph("CHECK INSURANCE RISK", title_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Risk Assessment Report", styles["Heading2"]))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph(f"<b>Risk ID:</b> {risk.id}", normal_style))
    elements.append(Paragraph(f"<b>Entity:</b> {risk.entity_id}", normal_style))
    elements.append(Paragraph(f"<b>Analyst:</b> {current_user.name}", normal_style))
    elements.append(
        Paragraph(
            f"<b>Date:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}",
            normal_style,
        )
    )
    elements.append(Spacer(1, 20))

    # Score Table
    data = [
        ["Metric", "Value"],
        ["Score", str(risk.score)],
        ["Risk Level", risk.level],
        ["Status", risk.status],
    ]

    table = Table(data, colWidths=[70 * mm, 50 * mm])
    table.setStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1F44")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]
    )

    elements.append(table)
    elements.append(Spacer(1, 20))

    # Integrity Hash
    raw_data = f"{risk.id}{risk.score}{risk.level}{risk.created_at}"
    integrity_hash = hashlib.sha256(raw_data.encode()).hexdigest()

    elements.append(Paragraph("<b>Digital Integrity Hash:</b>", normal_style))
    elements.append(Paragraph(integrity_hash, normal_style))
    elements.append(Spacer(1, 20))

    # QR Code
    verify_url = f"{settings.BASE_URL}/verify/{risk.id}/{integrity_hash}"
    qr = qrcode.make(verify_url)
    qr_buffer = BytesIO()
    qr.save(qr_buffer)
    qr_buffer.seek(0)

    elements.append(Paragraph("<b>Verification QR Code:</b>", normal_style))
    elements.append(Spacer(1, 6))
    elements.append(Image(qr_buffer, width=40 * mm, height=40 * mm))
    elements.append(Spacer(1, 20))

    # Server Digital Signature
    server_signature = hashlib.sha256(
        f"{integrity_hash}{settings.PDF_SECRET_KEY}".encode()
    ).hexdigest()

    elements.append(Paragraph("<b>System Digital Signature:</b>", normal_style))
    elements.append(Paragraph(server_signature, normal_style))
    elements.append(Spacer(1, 40))

    # Footer
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.grey,
    )

    elements.append(
        Paragraph(
            "Confidential document. Unauthorized distribution is prohibited.",
            footer_style,
        )
    )

    doc.build(elements)
    buffer.seek(0)

    # Audit log
    log_action(
        db=db,
        actor_id=current_user.id,
        entity_id=current_user.entity_id,
        action="RISK_PDF_DOWNLOAD",
        target_id=risk.id,
        meta={"score": risk.score},
    )

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=risk_{risk.id}.pdf"
        },
    )
