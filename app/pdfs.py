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
def _safe(v: Any, max_len: int = 220) -> str:
    s = "" if v is None else str(v)
    s = s.replace("\n", " ").strip()
    return s[:max_len]


def _score_to_int(score: Any) -> int:
    try:
        return int(score)
    except Exception:
        return 0


def _score_band(score: Any) -> Tuple[str, str]:
    """
    Returns (band, default_review_level).
    """
    s = _score_to_int(score)
    if s >= 80:
        return ("ALTO", "EDD (Enhanced Due Diligence)")
    if s >= 60:
        return ("MÉDIO", "Revisão Reforçada")
    return ("BAIXO", "Revisão Padrão")


def _normalize_matches_generic(matches: Any) -> Dict[str, Dict[str, List[dict]]]:
    """
    Normaliza risk.matches para:
    {
      "PEP": {"INTERNAL":[...], "OFAC":[...]},
      "SANCTIONS": {"UN":[...]},
      "WATCHLIST": {...},
      "ADVERSE_MEDIA": {...}
    }

    Aceita variações:
    - category/type/list_type
    - source/source_system/provider/sources[0]
    """
    out: Dict[str, Dict[str, List[dict]]] = {"PEP": {}, "SANCTIONS": {}, "WATCHLIST": {}, "ADVERSE_MEDIA": {}}

    if not matches:
        return out
    if isinstance(matches, dict):
        matches = [matches]
    if not isinstance(matches, list):
        return out

    for m in matches:
        if not isinstance(m, dict):
            m = {"value": m}

        cat = (m.get("category") or m.get("type") or m.get("list_type") or "WATCHLIST")
        cat = str(cat).upper().strip()
        if cat not in out:
            cat = "WATCHLIST"

        src = (
            m.get("source")
            or m.get("source_system")
            or m.get("provider")
            or (m.get("sources")[0] if isinstance(m.get("sources"), list) and m.get("sources") else None)
            or "DESCONHECIDO"
        )
        out[cat].setdefault(str(src), []).append(m)

    return out


def _counts_from_compliance(comp: Dict[str, Dict[str, List[dict]]]) -> Tuple[int, int, int, int]:
    pep = sum(len(v or []) for v in (comp.get("PEP") or {}).values())
    sanc = sum(len(v or []) for v in (comp.get("SANCTIONS") or {}).values())
    watch = sum(len(v or []) for v in (comp.get("WATCHLIST") or {}).values())
    adv = sum(len(v or []) for v in (comp.get("ADVERSE_MEDIA") or {}).values())
    return pep, sanc, watch, adv


def _decision_policy(score: Any, pep_hits: int, sanc_hits: int, fraud_flags: int) -> Tuple[str, List[str]]:
    """
    Decisão recomendada com linguagem institucional.
    """
    band, _review = _score_band(score)
    reasons: List[str] = []

    if sanc_hits > 0:
        decision = "SUSPENDER / ESCALAR"
        reasons.append("Identificadas correspondências em listas de sanções. Requer validação imediata e escalonamento.")
    elif pep_hits > 0:
        decision = "EDD (Revisão Reforçada)"
        reasons.append("Identificadas correspondências PEP. Recomenda-se diligência reforçada e validação documental.")
    elif fraud_flags > 0:
        decision = "Revisão Reforçada"
        reasons.append("Identificados indicadores operacionais/risco (fraud flags). Recomenda-se revisão reforçada.")
    else:
        decision = "Revisão Padrão"
        reasons.append("Com os dados disponíveis, não foram identificadas correspondências críticas.")

    # razões padrão institucionais
    reasons.append(f"Nível de risco (score): {band}.")
    reasons.append("Resultados dependem da completude dos dados fornecidos e das fontes ativas/configuradas.")
    reasons.append("Correspondências aproximadas devem ser confirmadas por validação humana antes de decisão final.")
    return decision, reasons[:5]


# ============================================================
# PDF Builder (Institutional / Bank-level)
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
    report_version: str = "v1.0",
) -> bytes:
    """
    Padrão institucional:
    - Capa + Sumário Executivo (decisão, score, razões)
    - Identificação e Escopo
    - Compliance (por categoria e por fonte, com detalhes)
    - Underwriting (por tipo de seguro / product_type)
    - Metodologia e Limitações
    - Integridade e Verificação (hash, assinatura, URL, QR)
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
        Image,
    )

    # QR opcional
    try:
        import qrcode  # type: ignore
    except Exception:
        qrcode = None  # type: ignore

    # UTC stamp
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)

    # Styles
    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=16, spaceAfter=10)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, spaceAfter=6)
    H3 = ParagraphStyle("H3", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=10, spaceAfter=4)
    BODY = ParagraphStyle("BODY", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=12)
    SMALL = ParagraphStyle("SMALL", parent=styles["BodyText"], fontName="Helvetica", fontSize=8, leading=10, textColor=colors.grey)

    BRAND = colors.HexColor("#0B1F3B")
    LIGHT = colors.HexColor("#F6F7F9")

    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(18 * mm, 10 * mm, "Confidencial | Check Insurance Risk")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Página {doc.page}")
        canvas.restoreState()

    def tbl(data: List[List[str]], col_widths=None) -> Table:
        t = Table(data, colWidths=col_widths, hAlign="LEFT")
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), BRAND),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ]
            )
        )
        return t

    def tag(text: str) -> Table:
        t = Table([[Paragraph(f"<b>{_safe(text, 140)}</b>", ParagraphStyle("TAG", parent=BODY, textColor=colors.white))]])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), BRAND),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return t

    # Data blocks
    score = getattr(risk, "score", None)
    score_i = _score_to_int(score)
    band, review_level = _score_band(score)

    comp = compliance_by_category or _normalize_matches_generic(getattr(risk, "matches", None) or [])
    pep_count, sanc_count, watch_count, adv_count = _counts_from_compliance(comp)

    uw = underwriting_by_product or {}
    fraud_flags_count = 0
    try:
        for _pt, pack in (uw or {}).items():
            fraud_flags_count += len((pack or {}).get("fraud_flags", []) or [])
    except Exception:
        fraud_flags_count = 0

    decision, reasons = _decision_policy(score, pep_count, sanc_count, fraud_flags_count)

    # Build doc
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=report_title,
        author="Check Insurance Risk",
    )

    story: List[Any] = []

    # ============================================================
    # CAPA + SUMÁRIO EXECUTIVO
    # ============================================================
    story.append(Paragraph("CHECK INSURANCE RISK", H1))
    story.append(Paragraph(report_title, H2))
    story.append(Spacer(1, 6))
    story.append(tag(f"DECISÃO RECOMENDADA: {decision}"))
    story.append(Spacer(1, 8))

    meta = [
        ["Campo", "Valor"],
        ["Data/Hora (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S %Z")],
        ["Versão", report_version],
        ["Analista", _safe(analyst_name, 80)],
        ["Tenant / Entidade", _safe(getattr(risk, "entity_id", ""), 80)],
        ["Referência (Risk ID)", _safe(getattr(risk, "id", ""), 80)],
    ]
    story.append(tbl(meta, col_widths=[55 * mm, 110 * mm]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Declaração de confidencialidade", H3))
    story.append(
        Paragraph(
            "Este documento é confidencial e destinado exclusivamente às partes autorizadas. "
            "A distribuição, reprodução ou divulgação depende de autorização prévia.",
            BODY,
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("Sumário executivo", H2))
    story.append(
        tbl(
            [
                ["Score", "Nível", "Nível de Revisão", "PEP", "Sanções", "Watchlists"],
                [str(score_i) if score else "N/A", band, review_level, str(pep_count), str(sanc_count), str(watch_count)],
            ],
            col_widths=[18 * mm, 22 * mm, 50 * mm, 20 * mm, 25 * mm, 30 * mm],
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>Razões principais (Top 5)</b>", BODY))
    rr = [["#", "Razão"]]
    for i, r in enumerate(reasons, 1):
        rr.append([str(i), _safe(r, 240)])
    story.append(tbl(rr, col_widths=[10 * mm, 155 * mm]))

    summary = _safe(getattr(risk, "summary", ""), 420)
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>Resumo:</b> {summary if summary else 'Sem resumo registado.'}", BODY))

    story.append(PageBreak())

    # ============================================================
    # 1) IDENTIFICAÇÃO & ESCOPO
    # ============================================================
    story.append(Paragraph("1) Identificação e Escopo", H1))

    ident = [
        ["Campo", "Valor"],
        ["Nome", _safe(getattr(risk, "query_name", ""), 140)],
        ["Nacionalidade", _safe(getattr(risk, "query_nationality", ""), 80)],
        ["BI", _safe(getattr(risk, "query_bi", ""), 80)],
        ["Passaporte", _safe(getattr(risk, "query_passport", ""), 80)],
        ["Estado do registo", _safe(getattr(risk, "status", ""), 40)],
    ]
    story.append(tbl(ident, col_widths=[55 * mm, 110 * mm]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Escopo da avaliação", H3))
    story.append(
        Paragraph(
            "A avaliação reflete os dados fornecidos no momento da consulta e a disponibilidade das fontes "
            "configuradas. Os resultados devem ser interpretados em conjunto com validação documental e "
            "políticas internas de conformidade e underwriting.",
            BODY,
        )
    )
    story.append(PageBreak())

    # ============================================================
    # 2) COMPLIANCE (por categoria e fonte)
    # ============================================================
    story.append(Paragraph("2) Compliance", H1))
    story.append(
        Paragraph(
            "Esta secção apresenta possíveis correspondências em bases de PEP, listas de sanções e watchlists, "
            "organizadas por fonte. Correspondências devem ser confirmadas por verificação humana.",
            BODY,
        )
    )
    story.append(Spacer(1, 8))

    def render_category(title: str, by_source: Dict[str, List[dict]]):
        story.append(Paragraph(title, H2))
        if not by_source:
            story.append(Paragraph("Sem correspondências registadas para esta categoria.", BODY))
            story.append(Spacer(1, 6))
            return

        # Resumo por fonte
        rows = [["Fonte", "Qtd. registos", "Top score"]]
        for src, hits in (by_source or {}).items():
            top = 0
            for h in hits or []:
                try:
                    top = max(top, int(h.get("match_score", 0) or 0))
                except Exception:
                    pass
            rows.append([_safe(src, 60), str(len(hits or [])), str(top)])
        story.append(tbl(rows, col_widths=[90 * mm, 35 * mm, 40 * mm]))
        story.append(Spacer(1, 6))

        # Detalhes (Top 5 por fonte)
        for src, hits in (by_source or {}).items():
            story.append(Paragraph(f"Fonte: <b>{_safe(src, 80)}</b>", H3))
            hs = sorted((hits or []), key=lambda x: int(x.get("match_score", 0) or 0), reverse=True)[:5]
            d = [["Nome", "Score", "País/Nac.", "DOB", "Cargo/Função/Nota", "Ref/Doc"]]
            for h in hs:
                d.append(
                    [
                        _safe(h.get("full_name") or h.get("name") or h.get("value"), 40),
                        _safe(h.get("match_score") or h.get("score"), 6),
                        _safe(h.get("nationality") or h.get("country"), 14),
                        _safe(h.get("dob") or h.get("date_of_birth"), 10),
                        _safe(h.get("role") or h.get("position") or h.get("notes") or h.get("summary"), 36),
                        _safe(h.get("id_number") or h.get("source_ref") or h.get("reference"), 18),
                    ]
                )
            story.append(tbl(d))
            story.append(Spacer(1, 8))

    render_category("2.1 PEP", comp.get("PEP") or {})
    render_category("2.2 Sanções", comp.get("SANCTIONS") or {})
    render_category("2.3 Watchlists", comp.get("WATCHLIST") or {})
    if (comp.get("ADVERSE_MEDIA") or {}):
        render_category("2.4 Adverse Media", comp.get("ADVERSE_MEDIA") or {})

    story.append(PageBreak())

    # ============================================================
    # 3) UNDERWRITING (por product_type)
    # ============================================================
    story.append(Paragraph("3) Underwriting", H1))
    story.append(Paragraph("Histórico por tipo de seguro (product_type).", BODY))
    story.append(Spacer(1, 8))

    if not uw:
        story.append(
            Paragraph(
                "Sem dados de underwriting agregados neste relatório (policies/claims/payments/cancellations/fraud flags).",
                BODY,
            )
        )
        story.append(Spacer(1, 6))
    else:
        for product_type in sorted(uw.keys(), key=lambda x: str(x)):
            pack = uw.get(product_type) or {}
            block: List[Any] = []
            block.append(Paragraph(f"Tipo de seguro: <b>{_safe(product_type, 40) or 'N/A'}</b>", H2))
            block.append(
                tbl(
                    [
                        ["Apólices", "Pagamentos", "Sinistros", "Cancelamentos", "Fraud flags"],
                        [
                            str(len(pack.get("policies", []) or [])),
                            str(len(pack.get("payments", []) or [])),
                            str(len(pack.get("claims", []) or [])),
                            str(len(pack.get("cancellations", []) or [])),
                            str(len(pack.get("fraud_flags", []) or [])),
                        ],
                    ],
                    col_widths=[33 * mm] * 5,
                )
            )
            block.append(Spacer(1, 4))
            block.append(Paragraph("Nota: amostra (Top 10) por categoria para manter concisão.", SMALL))
            story.append(KeepTogether(block))
            story.append(Spacer(1, 8))

    story.append(PageBreak())

    # ============================================================
    # 4) METODOLOGIA & LIMITAÇÕES
    # ============================================================
    story.append(Paragraph("4) Metodologia e Limitações", H1))

    story.append(Paragraph("Metodologia (alto nível)", H2))
    story.append(
        Paragraph(
            "A avaliação combina: (i) correspondência em fontes de compliance (PEP/sanções/watchlists), "
            "(ii) indicadores operacionais (underwriting) quando disponíveis, e (iii) regras de decisão configuráveis. "
            "Os resultados são indicativos e devem ser confirmados por validação humana e documental.",
            BODY,
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("Limitações", H2))
    limits = [
        "A ausência de correspondências não constitui prova de inexistência de risco.",
        "Fontes externas podem ter atrasos de atualização e diferenças de cobertura.",
        "Correspondências aproximadas (fuzzy) devem ser validadas manualmente antes de decisão final.",
        "O relatório não substitui obrigações regulatórias, políticas internas, nem aconselhamento jurídico.",
    ]
    lt = [["#", "Ponto"]]
    for i, t in enumerate(limits, 1):
        lt.append([str(i), _safe(t, 240)])
    story.append(tbl(lt, col_widths=[10 * mm, 155 * mm]))

    story.append(PageBreak())

    # ============================================================
    # 5) INTEGRIDADE & VERIFICAÇÃO
    # ============================================================
    story.append(Paragraph("5) Integridade e Verificação", H1))
    story.append(Paragraph(f"<b>Hash:</b> {_safe(integrity_hash, 200)}", BODY))
    story.append(Paragraph(f"<b>Assinatura do servidor:</b> {_safe(server_signature, 200)}", BODY))
    story.append(Paragraph(f"<b>URL de verificação:</b> {_safe(verify_url, 260)}", BODY))
    story.append(Spacer(1, 10))

    if qrcode is not None:
        try:
            from io import BytesIO as _BIO

            qr_img = qrcode.make(verify_url)
            qbuf = _BIO()
            qr_img.save(qbuf, format="PNG")
            qbuf.seek(0)
            story.append(Paragraph("QR Code de verificação:", BODY))
            story.append(Spacer(1, 4))
            story.append(Image(qbuf, width=28 * mm, height=28 * mm))
        except Exception:
            story.append(Paragraph("QR indisponível (erro ao gerar).", SMALL))
    else:
        story.append(Paragraph("QR indisponível (dependência não instalada).", SMALL))

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return buf.getvalue()


# Compatibilidade (se algum canto ainda chamar _pt)
def build_risk_pdf_institutional_pt(*args, **kwargs) -> bytes:
    return build_risk_pdf_institutional(*args, **kwargs)
