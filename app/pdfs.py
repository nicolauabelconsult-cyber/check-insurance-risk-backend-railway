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
            str(getattr(risk, "search_id", "") or ""),
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
    s = s.replace("\n", " ").strip()
    return s[:max_len]


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


def _normalize_matches_generic(matches: Any) -> Dict[str, Dict[str, List[dict]]]:
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
    band, review_level = _score_band(score)
    reasons: List[str] = []

    if sanc_hits > 0:
        decision = "SUSPENDER / ESCALAR"
        reasons.append("Foram identificadas correspondências em listas de sanções. Requer validação imediata e escalonamento.")
    elif pep_hits > 0:
        decision = "EDD (Revisão Reforçada)"
        reasons.append("Foram identificadas correspondências PEP. Recomenda-se diligência reforçada e validação documental.")
    elif fraud_flags > 0:
        decision = "Revisão Reforçada"
        reasons.append("Foram identificados indicadores de risco operacional/fraude. Recomenda-se revisão reforçada.")
    else:
        decision = "Revisão Padrão"
        reasons.append("Não foram identificadas correspondências críticas nas fontes configuradas com os dados disponíveis.")

    reasons.append(f"Nível de risco (score): {band}. Nível de revisão sugerido: {review_level}.")
    reasons.append("Resultados dependem da completude dos dados fornecidos e das fontes ativas/configuradas.")
    reasons.append("Correspondências aproximadas devem ser confirmadas por validação humana antes de decisão final.")
    return decision, reasons[:5]


def _institutional_summary(score: Any, pep: int, sanc: int, watch: int, adv: int, has_uw: bool) -> str:
    band, review = _score_band(score)
    s = _score_to_int(score)

    lines: List[str] = []
    lines.append(f"A avaliação classificou o risco global como {band} (score {s}/100), recomendando {review}.")
    if sanc > 0:
        lines.append("Foram identificadas correspondências em sanções, exigindo validação imediata e escalonamento.")
    elif pep > 0:
        lines.append("Foram identificadas correspondências PEP, recomendando diligência reforçada (EDD) e validação documental.")
    else:
        lines.append("Não foram identificadas correspondências críticas em sanções/PEP com base nos dados disponíveis.")
    if watch > 0:
        lines.append("Foram observadas correspondências em watchlists, recomendando verificação contextual.")
    if adv > 0:
        lines.append("Foram observadas referências em adverse media, recomendando avaliação qualitativa do contexto.")
    if not has_uw:
        lines.append("Não existe histórico de seguros (underwriting) disponível à data da análise nas fontes atualmente carregadas.")
    lines.append("A decisão final deve ser tomada de acordo com políticas internas e requisitos regulatórios aplicáveis.")
    return " ".join(lines)


# ============================================================
# PDF Builder (Institutional 1.0 Final)
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
    report_title: str = "Relatório Institucional de Avaliação de Risco",
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
        KeepTogether,
        Image,
    )

    # QR opcional
    try:
        import qrcode  # type: ignore
    except Exception:
        qrcode = None  # type: ignore

    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)

    styles = getSampleStyleSheet()
    BRAND = colors.HexColor("#0B1F3B")
    LIGHT = colors.HexColor("#F6F7F9")

    H0 = ParagraphStyle("H0", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, spaceAfter=6, textColor=BRAND)
    H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=14, spaceAfter=6)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11, spaceAfter=4)
    H3 = ParagraphStyle("H3", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=9, spaceAfter=2)
    BODY = ParagraphStyle("BODY", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=12)
    SMALL = ParagraphStyle("SMALL", parent=styles["BodyText"], fontName="Helvetica", fontSize=8, leading=10, textColor=colors.grey)

    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(18 * mm, 10 * mm, "Confidencial | Check Insurance Risk")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Página {doc.page}")
        canvas.restoreState()

    def tbl(data: List[List[str]], col_widths=None, header_bg=BRAND) -> Table:
        t = Table(data, colWidths=col_widths, hAlign="LEFT")
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), header_bg),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ]
            )
        )
        return t

    def badge(text: str) -> Table:
        t = Table([[Paragraph(f"<b>{_safe(text, 180)}</b>", ParagraphStyle("BADGE", parent=BODY, textColor=colors.white))]])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), BRAND),
                    ("LEFTPADDING", (0, 0), (-1, -1), 9),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return t

    score = getattr(risk, "score", None)
    score_i = _score_to_int(score)
    band, review_level = _score_band(score)

    comp = compliance_by_category or _normalize_matches_generic(getattr(risk, "matches", None) or [])
    pep_count, sanc_count, watch_count, adv_count = _counts_from_compliance(comp)

    uw = underwriting_by_product or {}
    has_uw = bool(uw)

    fraud_flags_count = 0
    try:
        for _pt, pack in (uw or {}).items():
            fraud_flags_count += len((pack or {}).get("fraud_flags", []) or [])
    except Exception:
        fraud_flags_count = 0

    decision, reasons = _decision_policy(score, pep_count, sanc_count, fraud_flags_count)
    exec_summary = _institutional_summary(score, pep_count, sanc_count, watch_count, adv_count, has_uw)

    search_id = getattr(risk, "search_id", None) or getattr(risk, "search_reference", None) or getattr(risk, "reference", None) or getattr(risk, "id", "")
    search_id = str(search_id)

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
    # CAPA EXECUTIVA
    # ============================================================
    story.append(Paragraph("CHECK INSURANCE RISK", H0))
    story.append(Paragraph(report_title, H1))
    story.append(Spacer(1, 6))

    person_rows = [
        ["Campo", "Valor"],
        ["Nome", _safe(getattr(risk, "query_name", ""), 140)],
        ["Nacionalidade", _safe(getattr(risk, "query_nationality", ""), 80)],
        ["BI", _safe(getattr(risk, "query_bi", ""), 80)],
        ["Passaporte", _safe(getattr(risk, "query_passport", ""), 80)],
        ["Data da análise (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S %Z")],
        ["ID da Pesquisa", _safe(search_id, 80)],
    ]
    story.append(tbl(person_rows, col_widths=[55 * mm, 110 * mm]))
    story.append(Spacer(1, 8))

    story.append(badge(f"DECISÃO RECOMENDADA: {decision}"))
    story.append(Spacer(1, 8))

    story.append(
        tbl(
            [
                ["Score", "Nível", "Nível de Revisão", "PEP", "Sanções", "Watchlists", "Adverse Media"],
                [str(score_i) if score else "N/A", band, review_level, str(pep_count), str(sanc_count), str(watch_count), str(adv_count)],
            ],
            col_widths=[16 * mm, 18 * mm, 45 * mm, 16 * mm, 20 * mm, 24 * mm, 25 * mm],
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("Escopo (declaração institucional)", H3))
    story.append(
        Paragraph(
            "Esta avaliação reflete os dados fornecidos na pesquisa e as fontes atualmente configuradas/ativas. "
            "A decisão final deve incluir validação humana e documental conforme políticas internas e requisitos regulatórios.",
            BODY,
        )
    )
    story.append(Spacer(1, 10))
    story.append(Paragraph("Confidencialidade", H3))
    story.append(
        Paragraph(
            "Documento confidencial e destinado exclusivamente às partes autorizadas. Qualquer divulgação depende de autorização prévia.",
            SMALL,
        )
    )

    story.append(PageBreak())

    # ============================================================
    # 1) Sumário Executivo
    # ============================================================
    story.append(Paragraph("1) Sumário Executivo", H1))
    story.append(Paragraph(exec_summary, BODY))
    story.append(Spacer(1, 8))

    rr = [["#", "Razão (Top 5)"]]
    for i, r_ in enumerate(reasons, 1):
        rr.append([str(i), _safe(r_, 260)])
    story.append(tbl(rr, col_widths=[10 * mm, 155 * mm]))

    story.append(PageBreak())

    # ============================================================
    # 2) Compliance
    # ============================================================
    story.append(Paragraph("2) Compliance", H1))
    story.append(
        Paragraph(
            "Esta secção apresenta possíveis correspondências em bases de PEP, listas de sanções e watchlists, organizadas por fonte. "
            "Correspondências devem ser confirmadas por verificação humana.",
            BODY,
        )
    )
    story.append(Spacer(1, 6))

    def _render_category(title: str, by_source: Dict[str, List[dict]]) -> List[Any]:
        block: List[Any] = []
        block.append(Paragraph(title, H2))
        if not by_source:
            block.append(Paragraph("Sem informações a apresentar (sem registos/correspondências disponíveis).", BODY))
            block.append(Spacer(1, 6))
            return block

        rows = [["Fonte", "Qtd. registos", "Top score"]]
        for src, hits in by_source.items():
            top = 0
            for h in hits or []:
                try:
                    top = max(top, int(h.get("match_score", 0) or 0))
                except Exception:
                    pass
            rows.append([_safe(src, 60), str(len(hits or [])), str(top)])
        block.append(tbl(rows, col_widths=[90 * mm, 35 * mm, 40 * mm]))
        block.append(Spacer(1, 6))
        return block

    story.extend(_render_category("2.1 PEP", comp.get("PEP") or {}))
    story.extend(_render_category("2.2 Sanções", comp.get("SANCTIONS") or {}))
    story.extend(_render_category("2.3 Watchlists", comp.get("WATCHLIST") or {}))
    story.extend(_render_category("2.4 Adverse Media", comp.get("ADVERSE_MEDIA") or {}))

    story.append(PageBreak())

    # ============================================================
    # 3) Underwriting / Seguros (sempre)
    # ============================================================
    story.append(Paragraph("3) Underwriting / Histórico de Seguros", H1))
    story.append(
        Paragraph(
            "A análise abaixo apresenta o histórico agregado por tipo de produto de seguro (product_type), com base nos registos atualmente disponíveis.",
            BODY,
        )
    )
    story.append(Spacer(1, 8))

    if not uw:
        story.append(Paragraph("Sem informações de seguros a apresentar (não existem registos disponíveis nas fontes/tabelas atualmente carregadas).", BODY))
        story.append(Spacer(1, 6))
        story.append(Paragraph("A ausência de dados de underwriting limita a avaliação do comportamento histórico associado a produtos de seguro.", SMALL))
    else:
        for product_type in sorted(uw.keys(), key=lambda x: str(x)):
            pack = uw.get(product_type) or {}

            policies = pack.get("policies", []) or []
            payments = pack.get("payments", []) or []
            claims = pack.get("claims", []) or []
            cancellations = pack.get("cancellations", []) or []
            fraud_flags = pack.get("fraud_flags", []) or []

            active_policies = 0
            cancelled_policies = 0
            for p in policies:
                st = str((p or {}).get("status", "")).lower()
                if st in ("active", "ativa", "ativo"):
                    active_policies += 1
                if st in ("cancelled", "canceled", "cancelada", "cancelado"):
                    cancelled_policies += 1

            late_payments = 0
            for p in payments:
                st = (p or {}).get("status", None)
                if st and str(st).lower() in ("late", "atraso", "atrasado"):
                    late_payments += 1

            block: List[Any] = []
            block.append(Paragraph(f"Tipo de Seguro: <b>{_safe(product_type, 60) or 'N/A'}</b>", H2))

            summary_table = [
                ["Indicador", "Valor"],
                ["Número total de apólices", str(len(policies))],
                ["Apólices ativas", str(active_policies)],
                ["Apólices canceladas", str(cancelled_policies)],
                ["Total de pagamentos registados", str(len(payments))],
                ["Pagamentos em atraso", str(late_payments)],
                ["Número de sinistros", str(len(claims))],
                ["Cancelamentos", str(len(cancellations))],
                ["Indicadores de fraude (fraud flags)", str(len(fraud_flags))],
            ]
            block.append(tbl(summary_table, col_widths=[95 * mm, 70 * mm]))
            block.append(Spacer(1, 6))

            if len(fraud_flags) > 0:
                observation = "Foram identificados indicadores de risco operacional associados a este produto, recomendando validação adicional e revisão reforçada."
            elif len(claims) > 0 and late_payments > 0:
                observation = "O histórico demonstra ocorrência de sinistros e registos pontuais de atraso em pagamentos. Recomenda-se análise contextual adicional."
            elif len(policies) > 0:
                observation = "O histórico disponível demonstra comportamento regular, sem indicadores críticos de risco operacional."
            else:
                observation = "Não existem eventos relevantes registados para este produto."

            block.append(Paragraph(f"<b>Observação:</b> {observation}", BODY))
            block.append(Spacer(1, 10))
            story.append(KeepTogether(block))

    story.append(PageBreak())

    # ============================================================
    # 4) Metodologia e Limitações
    # ============================================================
    story.append(Paragraph("4) Metodologia e Limitações", H1))
    story.append(
        Paragraph(
            "A avaliação combina: (i) fontes de compliance (PEP/sanções/watchlists/adverse media), "
            "(ii) indicadores de underwriting quando disponíveis, e (iii) regras de decisão e classificação de risco. "
            "Os resultados são indicativos e devem ser confirmados por validação humana e documental.",
            BODY,
        )
    )
    story.append(Spacer(1, 8))

    limits = [
        "A ausência de correspondências não constitui prova de inexistência de risco.",
        "Fontes externas podem ter atrasos de atualização e diferenças de cobertura.",
        "Correspondências aproximadas devem ser validadas manualmente antes de decisão final.",
        "O relatório não substitui obrigações regulatórias, políticas internas, nem aconselhamento jurídico.",
    ]
    lt = [["#", "Limitação"]]
    for i, t in enumerate(limits, 1):
        lt.append([str(i), _safe(t, 260)])
    story.append(tbl(lt, col_widths=[10 * mm, 155 * mm]))

    story.append(PageBreak())

    # ============================================================
    # 5) Integridade e Verificação
    # ============================================================
    story.append(Paragraph("5) Integridade e Verificação", H1))
    story.append(Paragraph("Este apêndice suporta rastreabilidade e auditoria.", BODY))
    story.append(Spacer(1, 8))

    integrity_rows = [
        ["Campo", "Valor"],
        ["ID da Pesquisa", _safe(search_id, 120)],
        ["Risk ID (interno)", _safe(getattr(risk, "id", ""), 120)],
        ["Hash", _safe(integrity_hash, 240)],
        ["Assinatura do servidor", _safe(server_signature, 240)],
        ["URL de verificação", _safe(verify_url, 260)],
    ]
    story.append(tbl(integrity_rows, col_widths=[55 * mm, 110 * mm]))
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
            story.append(Image(qbuf, width=30 * mm, height=30 * mm))
        except Exception:
            story.append(Paragraph("QR indisponível (erro ao gerar).", SMALL))
    else:
        story.append(Paragraph("QR indisponível (dependência não instalada).", SMALL))

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return buf.getvalue()


def build_risk_pdf_institutional_pt(*args, **kwargs) -> bytes:
    return build_risk_pdf_institutional(*args, **kwargs)
