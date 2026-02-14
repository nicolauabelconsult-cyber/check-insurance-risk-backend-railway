from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
from typing import Any, Dict, List, Optional, Tuple

from app.settings import settings


# ============================================================
# Integrity
# ============================================================
def make_integrity_hash(risk: Any) -> str:
    payload = "|".join(
        [
            str(getattr(risk, "id", "") or ""),
            str(getattr(risk, "entity_id", "") or ""),
            str(getattr(risk, "query_name", "") or ""),
            str(getattr(risk, "query_bi", "") or ""),
            str(getattr(risk, "query_passport", "") or ""),
            str(getattr(risk, "query_nationality", "") or ""),
            str(getattr(risk, "score", "") or ""),
            str(getattr(risk, "status", "") or ""),
            str(getattr(risk, "created_at", "") or ""),
        ]
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def make_server_signature(integrity_hash: str) -> str:
    secret = getattr(settings, "PDF_SIGNING_SECRET", None) or getattr(settings, "JWT_SECRET", "")
    if not secret:
        raise RuntimeError("Missing PDF_SIGNING_SECRET/JWT_SECRET in settings")
    return hmac.new(secret.encode("utf-8"), integrity_hash.encode("utf-8"), hashlib.sha256).hexdigest()


# ============================================================
# Helpers
# ============================================================
def _safe(v: Any, max_len: int = 240) -> str:
    s = "" if v is None else str(v)
    return s.replace("\n", " ").strip()[:max_len]


def _score_to_int(score: Any) -> int:
    try:
        return int(score)
    except Exception:
        return 0


def _score_band(score: Any) -> Tuple[str, str]:
    s = _score_to_int(score)
    if s >= 80:
        return ("ALTO", "EDD (Enhanced Due Diligence)")
    if s >= 60:
        return ("MÉDIO", "Revisão Reforçada")
    return ("BAIXO", "Revisão Padrão")


# ============================================================
# PDF Builder
# ============================================================
def build_risk_pdf_institutional(
    risk: Any,
    analyst_name: str,
    generated_at: datetime,
    integrity_hash: str,
    server_signature: str,
    verify_url: str,
    underwriting_by_product: Optional[Dict[str, Any]] = None,
    compliance_by_category: Optional[Dict[str, Any]] = None,
    report_title: str = "Relatório Institucional de Risco",
    report_version: str = "v2.0",
) -> bytes:

    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        PageBreak,
    )

    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)

    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=15)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11)
    BODY = ParagraphStyle("BODY", parent=styles["BodyText"], fontSize=9)

    BRAND = colors.HexColor("#0B1F3B")

    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(20 * mm, 10 * mm, "Confidencial | Check Insurance Risk")
        canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Página {doc.page}")
        canvas.restoreState()

    def tbl(data, widths=None):
        t = Table(data, colWidths=widths)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), BRAND),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ]
            )
        )
        return t

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    story: List[Any] = []

    # ============================================================
    # CAPA
    # ============================================================
    story.append(Paragraph("CHECK INSURANCE RISK", H1))
    story.append(Spacer(1, 6))
    story.append(Paragraph(report_title, H2))
    story.append(Spacer(1, 12))

    meta = [
        ["Campo", "Valor"],
        ["Risk ID", _safe(getattr(risk, "id", ""))],
        ["Entidade", _safe(getattr(risk, "entity_id", ""))],
        ["Analista", _safe(analyst_name)],
        ["Data (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S")],
        ["Versão", report_version],
    ]
    story.append(tbl(meta, [50 * mm, 90 * mm]))
    story.append(PageBreak())

    # ============================================================
    # IDENTIFICAÇÃO
    # ============================================================
    story.append(Paragraph("1) Identificação", H1))
    story.append(Spacer(1, 6))

    ident = [
        ["Campo", "Valor"],
        ["Nome", _safe(getattr(risk, "query_name", ""))],
        ["Nacionalidade", _safe(getattr(risk, "query_nationality", ""))],
        ["BI", _safe(getattr(risk, "query_bi", ""))],
        ["Passaporte", _safe(getattr(risk, "query_passport", ""))],
        ["Score", str(_score_to_int(getattr(risk, "score", 0)))],
    ]
    story.append(tbl(ident, [50 * mm, 90 * mm]))
    story.append(PageBreak())

    # ============================================================
    # UNDERWRITING / SEGUROS (SEMPRE)
    # ============================================================
    story.append(Paragraph("2) Underwriting / Seguros", H1))
    story.append(Spacer(1, 6))

    uw = underwriting_by_product or {}

    if not uw:
        story.append(
            Paragraph(
                "Sem dados de seguros a apresentar para a entidade analisada, "
                "com base nos registos atualmente disponíveis.",
                BODY,
            )
        )
        story.append(Spacer(1, 12))
    else:
        for product_type in sorted(uw.keys()):
            pack = uw.get(product_type) or {}

            story.append(Paragraph(f"Tipo de Seguro: {product_type}", H2))
            story.append(Spacer(1, 4))

            summary = [
                ["Apólices", "Pagamentos", "Sinistros", "Cancelamentos", "Fraud Flags"],
                [
                    str(len(pack.get("policies", []) or [])),
                    str(len(pack.get("payments", []) or [])),
                    str(len(pack.get("claims", []) or [])),
                    str(len(pack.get("cancellations", []) or [])),
                    str(len(pack.get("fraud_flags", []) or [])),
                ],
            ]

            story.append(tbl(summary))
            story.append(Spacer(1, 12))

    # ============================================================
    # INTEGRIDADE
    # ============================================================
    story.append(PageBreak())
    story.append(Paragraph("3) Integridade do Documento", H1))
    story.append(Spacer(1, 6))

    integrity = [
        ["Campo", "Valor"],
        ["Hash", _safe(integrity_hash)],
        ["Assinatura do Servidor", _safe(server_signature)],
        ["URL de Verificação", _safe(verify_url)],
    ]

    story.append(tbl(integrity, [50 * mm, 90 * mm]))

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)

    return buf.getvalue()


def build_risk_pdf_institutional_pt(*args, **kwargs) -> bytes:
    return build_risk_pdf_institutional(*args, **kwargs)
