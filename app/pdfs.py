from __future__ import annotations

from datetime import datetime
import hashlib
import hmac
from typing import Any, Dict, List, Optional, Tuple

from app.settings import settings


# -------------------------
# Integrity
# -------------------------
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


# -------------------------
# Helpers
# -------------------------
def _score_to_band(score: str | int | None) -> Tuple[str, str]:
    """
    Returns (band, recommendation)
    """
    try:
        s = int(score) if score is not None else 0
    except Exception:
        s = 0

    if s >= 80:
        return ("ALTO", "EDD (Enhanced Due Diligence) recomendada antes de qualquer decisão.")
    if s >= 60:
        return ("MÉDIO", "Revisão reforçada e validação documental adicional recomendadas.")
    return ("BAIXO", "Revisão padrão recomendada; monitorização conforme política interna.")


def _safe(v: Any, max_len: int = 140) -> str:
    s = "" if v is None else str(v)
    s = s.replace("\n", " ").strip()
    return s[:max_len]


def _group_matches_by_source(matches: Any) -> Dict[str, List[dict]]:
    """
    Normaliza matches (list/dict/None) para {source: [match,...]}
    Aceita formatos variados: {"source": "..."} / {"sources":[...]} / {"provider": "..."}
    """
    out: Dict[str, List[dict]] = {}
    if not matches:
        return out

    if isinstance(matches, dict):
        matches = [matches]
    if not isinstance(matches, list):
        return out

    for m in matches:
        if not isinstance(m, dict):
            m = {"value": m}

        src = (
            m.get("source")
            or m.get("source_system")
            or m.get("provider")
            or (m.get("sources")[0] if isinstance(m.get("sources"), list) and m.get("sources") else None)
            or "DESCONHECIDO"
        )
        out.setdefault(str(src), []).append(m)
    return out


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
    PDF institucional banco-level (PT):
    - Capa + Sumário Executivo
    - Identificação
    - Compliance (por fonte)
    - Underwriting (por tipo de seguro, se underwriting_by_product for fornecido)
    - Integridade & verificação
    """
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
        KeepTogether,
    )

    # QR opcional
    try:
        import qrcode  # type: ignore
    except Exception:
        qrcode = None  # type: ignore

    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=16, spaceAfter=10)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, spaceAfter=6)
    H3 = ParagraphStyle("H3", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=10, spaceAfter=4)
    BODY = ParagraphStyle("BODY", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=12)
    SMALL = ParagraphStyle("SMALL", parent=styles["BodyText"], fontName="Helvetica", fontSize=8, leading=10, textColor=colors.grey)
    TAG = ParagraphStyle("TAG", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=9, textColor=colors.white)

    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(18 * mm, 10 * mm, "Confidencial | Check Insurance Risk")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Página {doc.page}")
        canvas.restoreState()

    def box_tag(text: str, bg=colors.HexColor("#0B1F3B")):
        t = Table([[Paragraph(text, TAG)]], colWidths=[55 * mm])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), bg),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        return t

    def styled_table(data: List[List[str]], col_widths=None):
        t = Table(data, colWidths=col_widths, hAlign="LEFT")
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
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F7F9")]),
                ]
            )
        )
        return t

    # --- doc setup ---
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

    story: List[Any] = []

    # -------------------------
    # CAPA / EXEC SUMMARY
    # -------------------------
    score = getattr(risk, "score", None)
    band, recommendation = _score_to_band(score)
    score_str = _safe(score, 8) or "N/A"

    story.append(Paragraph("CHECK INSURANCE RISK", H1))
    story.append(Paragraph("Relatório Institucional de Risco", H2))
    story.append(box_tag(f"NÍVEL DE RISCO: {band}"))

    story.append(Spacer(1, 8))

    meta = [
        ["Campo", "Valor"],
        ["Data/Hora (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S")],
        ["Analista", _safe(analyst_name, 80)],
        ["Entidade (Tenant)", _safe(getattr(risk, "entity_id", ""))],
        ["ID do Relatório (Risk)", _safe(getattr(risk, "id", ""))],
        ["Versão", "Institutional PDF v1"],
    ]
    story.append(styled_table(meta, col_widths=[50 * mm, 115 * mm]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Sumário Executivo", H2))
    story.append(
        styled_table(
            [
                ["Score", "Nível", "Recomendação"],
                [score_str, band, recommendation],
            ],
            col_widths=[25 * mm, 25 * mm, 115 * mm],
        )
    )
    story.append(Spacer(1, 6))

    summary = _safe(getattr(risk, "summary", ""), 420)
    if summary:
        story.append(Paragraph(f"<b>Resumo:</b> {summary}", BODY))
    else:
        story.append(Paragraph("<b>Resumo:</b> Sem resumo registado.", BODY))

    story.append(Spacer(1, 6))
    story.append(Paragraph("⚠️ Nota: Este relatório apoia a decisão, mas não substitui validação humana e documental.", SMALL))

    story.append(PageBreak())

    # -------------------------
    # IDENTIFICAÇÃO
    # -------------------------
    story.append(Paragraph("1) Identificação do Avaliado", H1))
    ident = [
        ["Campo", "Valor"],
        ["Nome", _safe(getattr(risk, "query_name", ""), 120)],
        ["Nacionalidade", _safe(getattr(risk, "query_nationality", ""), 80)],
        ["BI", _safe(getattr(risk, "query_bi", ""), 80)],
        ["Passaporte", _safe(getattr(risk, "query_passport", ""), 80)],
        ["Estado", _safe(getattr(risk, "status", ""), 40)],
    ]
    story.append(styled_table(ident, col_widths=[50 * mm, 115 * mm]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("2) Compliance", H1))
    story.append(Paragraph("PEP / Sanções / Watchlists (por fonte e detalhes)", BODY))
    story.append(Spacer(1, 6))

    # -------------------------
    # COMPLIANCE DETAILS
    # -------------------------
    # Preferir compliance_by_category (se já estiveres a passar); senão usa risk.matches
    if compliance_by_category:
        # Estrutura esperada: { "PEP": {"OFAC":[...], "INTERNAL":[...]}, "SANCTIONS": {...}, ... }
        for cat, by_source in compliance_by_category.items():
            story.append(Paragraph(f"{_safe(cat, 50)}", H2))
            if not by_source:
                story.append(Paragraph("Sem correspondências registadas.", BODY))
                story.append(Spacer(1, 6))
                continue

            # resumo por fonte
            rows = [["Fonte", "Qtd. Hits", "Top Score"]]
            for src, hits in (by_source or {}).items():
                top = max([int(h.get("match_score", 0) or 0) for h in (hits or [])] or [0])
                rows.append([_safe(src, 40), str(len(hits or [])), str(top)])
            story.append(styled_table(rows, col_widths=[80 * mm, 30 * mm, 30 * mm]))
            story.append(Spacer(1, 6))

            # detalhes (top 5 por fonte)
            for src, hits in (by_source or {}).items():
                hits_sorted = sorted((hits or []), key=lambda x: int(x.get("match_score", 0) or 0), reverse=True)[:5]
                detail = [["Nome", "Match", "Nacionalidade", "DOB", "Ref/Doc"]]
                for h in hits_sorted:
                    detail.append(
                        [
                            _safe(h.get("full_name") or h.get("name"), 45),
                            _safe(h.get("match_score"), 6),
                            _safe(h.get("nationality"), 18),
                            _safe(h.get("dob"), 10),
                            _safe(h.get("id_number") or h.get("source_ref"), 22),
                        ]
                    )
                story.append(Paragraph(f"Fonte: <b>{_safe(src, 50)}</b>", H3))
                story.append(styled_table(detail))
                story.append(Spacer(1, 8))

            story.append(Spacer(1, 6))
    else:
        matches = getattr(risk, "matches", None) or []
        grouped = _group_matches_by_source(matches)

        if not grouped:
            story.append(Paragraph("Sem correspondências registadas (PEP/Sanções/Watchlists).", BODY))
        else:
            # Resumo por fonte
            rows = [["Fonte", "Qtd. Itens"]]
            for src, items in grouped.items():
                rows.append([_safe(src, 50), str(len(items))])
            story.append(styled_table(rows, col_widths=[110 * mm, 55 * mm]))
            story.append(Spacer(1, 8))

            # Detalhes por fonte (top 8)
            for src, items in grouped.items():
                story.append(Paragraph(f"Fonte: <b>{_safe(src, 60)}</b>", H3))
                data = [["Nome/Referência", "Match", "Detalhe"]]
                for m in (items or [])[:8]:
                    nm = _safe(m.get("full_name") or m.get("name") or m.get("value"), 40)
                    ms = _safe(m.get("match_score") or m.get("score") or "", 6)
                    det = _safe(m.get("role") or m.get("position") or m.get("notes") or "", 55)
                    data.append([nm, ms, det])
                story.append(styled_table(data))
                story.append(Spacer(1, 8))

    story.append(PageBreak())

    # -------------------------
    # UNDERWRITING (por tipo de seguro)
    # -------------------------
    story.append(Paragraph("3) Underwriting", H1))
    story.append(Paragraph("Histórico por tipo de seguro (product_type)", BODY))
    story.append(Spacer(1, 6))

    uw = underwriting_by_product or {}
    if not uw:
        story.append(
            Paragraph(
                "Sem dados de underwriting agregados neste relatório. "
                "Quando o histórico estiver ligado (policies/claims/payments), esta secção passa a vir por tipo de seguro.",
                BODY,
            )
        )
    else:
        for product_type, pack in uw.items():
            product_type = str(product_type or "N/A")
            story.append(KeepTogether([Paragraph(f"Tipo: <b>{_safe(product_type, 40)}</b>", H2)]))

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
            story.append(styled_table(counts, col_widths=[33 * mm] * 5))
            story.append(Spacer(1, 6))

            # Nota: não despejar tudo no PDF. Top 10 por tipo.
            story.append(Paragraph("Observação: exibimos apenas amostra (Top 10) por tipo de seguro.", SMALL))
            story.append(Spacer(1, 6))

    story.append(PageBreak())

    # -------------------------
    # INTEGRIDADE & VERIFICAÇÃO
    # -------------------------
    story.append(Paragraph("4) Integridade & Verificação", H1))
    story.append(Paragraph(f"<b>Hash:</b> {_safe(integrity_hash, 200)}", BODY))
    story.append(Paragraph(f"<b>Assinatura do servidor:</b> {_safe(server_signature, 200)}", BODY))
    story.append(Paragraph(f"<b>URL de verificação:</b> {_safe(verify_url, 220)}", BODY))
    story.append(Spacer(1, 8))

    # QR se existir
    if qrcode is not None:
        try:
            from reportlab.platypus import Image  # local import
            from io import BytesIO as _BIO

            qr_img = qrcode.make(verify_url)
            qbuf = _BIO()
            qr_img.save(qbuf, format="PNG")
            qbuf.seek(0)
            story.append(Paragraph("QR de verificação:", BODY))
            story.append(Spacer(1, 4))
            story.append(Image(qbuf, width=28 * mm, height=28 * mm))
        except Exception:
            story.append(Paragraph("QR indisponível (dependência não instalada ou erro ao gerar).", SMALL))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Confidencial. Uso exclusivo institucional. Sujeito a políticas internas e legislação aplicável.", SMALL))

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return buf.getvalue()


# Alias para compatibilidade (se algum canto ainda chamar _pt)
def build_risk_pdf_institutional_pt(*args, **kwargs) -> bytes:
    return build_risk_pdf_institutional(*args, **kwargs)
