from __future__ import annotations

from datetime import datetime
import hashlib
import hmac
from typing import Any, Dict, List, Optional

from app.settings import settings


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


def build_risk_pdf_institutional(
    risk: Any,
    analyst_name: str,
    generated_at: datetime,
    integrity_hash: str,
    server_signature: str,
    verify_url: str,
    underwriting_by_product: Optional[Dict[str, Any]] = None,
    compliance_by_category: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    PDF banco-level:
    - Capa + Sumário Executivo
    - Compliance (por categoria e por fonte)
    - Underwriting (por tipo de seguro / product_type)
    - Integridade (hash/assinatura/QR/link)
    """
    from io import BytesIO

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    )

    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=16, spaceAfter=8)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, spaceAfter=6)
    BODY = ParagraphStyle("BODY", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=12)
    SMALL = ParagraphStyle("SMALL", parent=styles["BodyText"], fontName="Helvetica", fontSize=8, leading=10, textColor=colors.grey)

    def _table(data: List[List[str]], col_widths=None):
        t = Table(data, colWidths=col_widths)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B1F3B")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        return t

    def _score_label(score_str: str) -> str:
        try:
            s = int(score_str)
        except Exception:
            return "N/A"
        if s >= 80:
            return "ALTO"
        if s >= 60:
            return "MÉDIO"
        return "BAIXO"

    def _header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(18 * mm, 10 * mm, "Confidencial | Check Insurance Risk")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Página {doc.page}")
        canvas.restoreState()

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Relatório Institucional de Risco",
        author="Check Insurance Risk",
    )

    story = []

    # --- CAPA ---
    story.append(Paragraph("CHECK INSURANCE RISK", H1))
    story.append(Paragraph("Relatório Institucional de Risco", H2))
    story.append(Spacer(1, 6))

    meta = [
        ["Campo", "Valor"],
        ["Data/Hora (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S")],
        ["Analista", analyst_name],
        ["Entidade (Tenant)", str(getattr(risk, "entity_id", ""))],
        ["Risk ID", str(getattr(risk, "id", ""))],
        ["Nome", str(getattr(risk, "query_name", ""))],
        ["Nacionalidade", str(getattr(risk, "query_nationality", ""))],
        ["BI", str(getattr(risk, "query_bi", "") or "")],
        ["Passaporte", str(getattr(risk, "query_passport", "") or "")],
    ]
    story.append(_table(meta, col_widths=[45 * mm, 120 * mm]))
    story.append(Spacer(1, 10))

    score = str(getattr(risk, "score", "") or "")
    risk_level = _score_label(score)
    summary = str(getattr(risk, "summary", "") or "")

    story.append(Paragraph("Sumário Executivo", H2))
    story.append(
        _table(
            [
                ["Score", "Nível", "Decisão Recomendada"],
                [score or "N/A", risk_level, "Revisão reforçada se houver hits; caso contrário revisão padrão."],
            ],
            col_widths=[30 * mm, 30 * mm, 105 * mm],
        )
    )
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>Resumo:</b> {summary}", BODY))
    story.append(PageBreak())

    # --- COMPLIANCE ---
    story.append(Paragraph("Compliance", H1))
    story.append(Paragraph("PEP / Sanções / Watchlists (por fonte)", BODY))
    story.append(Spacer(1, 6))

    comp = compliance_by_category or {"PEP": {}, "SANCTIONS": {}, "WATCHLIST": {}}

    for cat in ["PEP", "SANCTIONS", "WATCHLIST"]:
        story.append(Paragraph(f"{cat}", H2))
        by_source = comp.get(cat) or {}
        if not by_source:
            story.append(Paragraph("Sem correspondências registadas.", BODY))
            story.append(Spacer(1, 6))
            continue

        # resumo por fonte
        summary_rows = [["Fonte", "Qtd. Hits", "Top Score"]]
        for src, hits in by_source.items():
            top = max([h.get("match_score", 0) for h in hits] or [0])
            summary_rows.append([src, str(len(hits)), str(top)])
        story.append(_table(summary_rows, col_widths=[60 * mm, 30 * mm, 30 * mm]))
        story.append(Spacer(1, 6))

        # detalhes (top 5 por fonte)
        for src, hits in by_source.items():
            story.append(Paragraph(f"Fonte: <b>{src}</b>", BODY))
            hits_sorted = sorted(hits, key=lambda x: x.get("match_score", 0), reverse=True)[:5]
            detail = [["Nome", "Match", "Nacionalidade", "DOB", "Doc/Ref"]]
            for h in hits_sorted:
                detail.append(
                    [
                        str(h.get("full_name", ""))[:45],
                        str(h.get("match_score", "")),
                        str(h.get("nationality", "") or ""),
                        str(h.get("dob", "") or ""),
                        str(h.get("id_number", "") or h.get("source_ref", "") or "")[:25],
                    ]
                )
            story.append(_table(detail, col_widths=[70 * mm, 15 * mm, 30 * mm, 20 * mm, 30 * mm]))
            story.append(Spacer(1, 8))

    story.append(PageBreak())

    # --- UNDERWRITING ---
    story.append(Paragraph("Underwriting", H1))
    story.append(Paragraph("Histórico por tipo de seguro (product_type)", BODY))
    story.append(Spacer(1, 6))

    uw = underwriting_by_product or {}
    if not uw:
        story.append(Paragraph("Sem dados de underwriting disponíveis.", BODY))
    else:
        for product_type, pack in uw.items():
            story.append(Paragraph(f"Tipo: <b>{product_type}</b>", H2))

            # counts
            counts = [
                ["Apólices", "Pagamentos", "Sinistros", "Cancelamentos", "Fraud Flags"],
                [
                    str(len(pack.get("policies", []) or [])),
                    str(len(pack.get("payments", []) or [])),
                    str(len(pack.get("claims", []) or [])),
                    str(len(pack.get("cancellations", []) or [])),
                    str(len(pack.get("fraud_flags", []) or [])),
                ],
            ]
            story.append(_table(counts, col_widths=[33 * mm] * 5))
            story.append(Spacer(1, 6))

            # mini tabelas (top 10)
            def _mini(title, rows, cols):
                story.append(Paragraph(title, BODY))
                if not rows:
                    story.append(Paragraph("Sem registos.", SMALL))
                    story.append(Spacer(1, 4))
                    return
                data = [cols]
                for r in rows[:10]:
                    data.append([str(getattr(r, c, "") or "")[:40] for c in cols])
                story.append(_table(data))
                story.append(Spacer(1, 6))

            _mini("Apólices (top 10)", pack.get("policies", []) or [], ["id", "product_type", "status"])
            _mini("Pagamentos (top 10)", pack.get("payments", []) or [], ["id", "amount", "paid_at"])
            _mini("Sinistros (top 10)", pack.get("claims", []) or [], ["id", "amount", "occurred_at"])
            _mini("Cancelamentos (top 10)", pack.get("cancellations", []) or [], ["id", "reason", "cancelled_at"])
            _mini("Fraud Flags (top 10)", pack.get("fraud_flags", []) or [], ["id", "flag", "created_at"])

    story.append(PageBreak())

    # --- INTEGRIDADE ---
    story.append(Paragraph("Integridade & Verificação", H1))
    story.append(Paragraph(f"<b>Hash:</b> {integrity_hash}", BODY))
    story.append(Paragraph(f"<b>Assinatura do servidor:</b> {server_signature}", BODY))
    story.append(Paragraph(f"<b>URL de verificação:</b> {verify_url}", BODY))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Este relatório é confidencial. A validação deve ser feita através do link/QR.", SMALL))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


def build_risk_pdf_institutional_pt(*args, **kwargs) -> bytes:
    return build_risk_pdf_institutional(*args, **kwargs)
