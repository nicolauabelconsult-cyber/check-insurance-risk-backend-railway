from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
from typing import Any, Dict, List, Optional, Tuple

from app.settings import settings


# ============================================================
# Integridade
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
        raise RuntimeError("Falta PDF_SIGNING_SECRET/JWT_SECRET nas definições")
    return hmac.new(secret.encode("utf-8"), integrity_hash.encode("utf-8"), hashlib.sha256).hexdigest()


# ============================================================
# Utilitários
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
        return ("ALTO", "Diligência Reforçada")
    if s >= 60:
        return ("MÉDIO", "Revisão Reforçada")
    return ("BAIXO", "Revisão Padrão")


def _normalize_matches_generic(matches: Any) -> Dict[str, Dict[str, List[dict]]]:
    out: Dict[str, Dict[str, List[dict]]] = {
        "PEP": {},
        "SANCTIONS": {},
        "WATCHLIST": {},
        "ADVERSE_MEDIA": {},
    }
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
        decision = "SUSPENDER E ESCALAR"
        reasons.append("Foram identificadas correspondências em listas de sanções. Exige-se validação imediata e escalonamento.")
    elif pep_hits > 0:
        decision = "DILIGÊNCIA REFORÇADA"
        reasons.append("Foram identificadas correspondências PEP. Recomenda-se diligência reforçada e validação documental.")
    elif fraud_flags > 0:
        decision = "REVISÃO REFORÇADA"
        reasons.append("Foram identificados indicadores de risco operacional ou de fraude. Recomenda-se revisão reforçada.")
    else:
        decision = "REVISÃO PADRÃO"
        reasons.append("Não foram identificadas correspondências críticas nas fontes configuradas, com base nos dados disponíveis.")

    reasons.append(f"Nível de risco apurado: {band}. Nível de revisão sugerido: {review_level}.")
    reasons.append("Os resultados dependem da completude dos dados fornecidos e das fontes activas e configuradas.")
    reasons.append("As correspondências aproximadas devem ser confirmadas por validação humana antes de qualquer decisão final.")
    return decision, reasons[:5]


def _institutional_summary(score: Any, pep: int, sanc: int, watch: int, adv: int, has_uw: bool) -> str:
    band, review = _score_band(score)
    s = _score_to_int(score)

    lines: List[str] = []
    lines.append(f"A avaliação classificou o risco global como {band} (pontuação {s}/100), recomendando {review}.")
    if sanc > 0:
        lines.append("Foram identificadas correspondências em listas de sanções, exigindo validação imediata e escalonamento.")
    elif pep > 0:
        lines.append("Foram identificadas correspondências PEP, recomendando diligência reforçada e validação documental.")
    else:
        lines.append("Não foram identificadas correspondências críticas em listas de sanções ou PEP, com base nos dados disponíveis.")
    if watch > 0:
        lines.append("Foram observadas correspondências em listas de observação, recomendando verificação contextual.")
    if adv > 0:
        lines.append("Foram identificadas referências negativas em meios abertos, recomendando avaliação qualitativa do contexto.")
    if not has_uw:
        lines.append("Não existe histórico segurador disponível, à data da análise, nas fontes actualmente carregadas.")
    lines.append("A decisão final deve ser tomada em conformidade com as políticas internas da instituição e com os requisitos regulatórios aplicáveis.")
    return " ".join(lines)


def _translate_category_name(cat: str) -> str:
    mapping = {
        "PEP": "PEP",
        "SANCTIONS": "Sanções",
        "WATCHLIST": "Listas de observação",
        "ADVERSE_MEDIA": "Meios adversos",
    }
    return mapping.get(str(cat).upper().strip(), _safe(cat, 50))


def _translate_payment_status(v: Any) -> str:
    s = str(v or "").strip().lower()
    mapping = {
        "paid": "Pago",
        "pending": "Pendente",
        "overdue": "Em atraso",
        "late": "Em atraso",
        "unpaid": "Não pago",
        "cancelled": "Cancelado",
        "canceled": "Cancelado",
        "processing": "Em processamento",
        "failed": "Falhado",
        "atraso": "Em atraso",
        "atrasado": "Em atraso",
        "pago": "Pago",
        "pendente": "Pendente",
        "não pago": "Não pago",
    }
    return mapping.get(s, _safe(v, 30) or "N/D")


def _translate_policy_status(v: Any) -> str:
    s = str(v or "").strip().lower()
    mapping = {
        "active": "Activa",
        "ativa": "Activa",
        "ativo": "Activo",
        "inactive": "Inactiva",
        "cancelled": "Cancelada",
        "canceled": "Cancelada",
        "expired": "Expirada",
        "lapsed": "Caducada",
        "suspended": "Suspensa",
        "pending": "Pendente",
        "cancelada": "Cancelada",
        "expirada": "Expirada",
        "suspensa": "Suspensa",
        "pendente": "Pendente",
    }
    return mapping.get(s, _safe(v, 30) or "N/D")


def _translate_claim_status(v: Any) -> str:
    s = str(v or "").strip().lower()
    mapping = {
        "open": "Aberto",
        "closed": "Encerrado",
        "rejected": "Recusado",
        "approved": "Aprovado",
        "paid": "Pago",
        "pending": "Pendente",
        "under_review": "Em análise",
        "in_review": "Em análise",
        "aberto": "Aberto",
        "encerrado": "Encerrado",
        "recusado": "Recusado",
        "aprovado": "Aprovado",
        "pago": "Pago",
        "pendente": "Pendente",
    }
    return mapping.get(s, _safe(v, 30) or "N/D")


# ============================================================
# Construtor do PDF
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
    report_reference: Optional[str] = None,
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

    try:
        import qrcode  # type: ignore
    except Exception:
        qrcode = None  # type: ignore

    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)

    styles = getSampleStyleSheet()

    # Paleta institucional
    BRAND = colors.HexColor("#0F2747")
    BRAND_DARK = colors.HexColor("#09192E")
    LIGHT = colors.HexColor("#F6F8FB")
    SOFT = colors.HexColor("#E9EEF5")
    BORDER = colors.HexColor("#D7DEE8")
    TEXT = colors.HexColor("#1B1F24")
    MUTED = colors.HexColor("#667085")
    WHITE = colors.white

    # =========================
    # Estilos
    # =========================
    H0 = ParagraphStyle(
        "H0",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16.5,
        leading=19,
        textColor=BRAND_DARK,
        alignment=1,
        spaceAfter=4,
    )

    H1 = ParagraphStyle(
        "H1",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=12.5,
        textColor=TEXT,
        alignment=1,
        spaceAfter=3,
    )

    H2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=11.5,
        textColor=TEXT,
        alignment=0,
        spaceAfter=2,
    )

    H3 = ParagraphStyle(
        "H3",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=8.2,
        leading=9.8,
        textColor=TEXT,
        alignment=0,
        spaceAfter=1,
    )

    BODY = ParagraphStyle(
        "BODY",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10,
        textColor=TEXT,
        alignment=0,
        spaceAfter=0,
    )

    BODY_CENTER = ParagraphStyle(
        "BODY_CENTER",
        parent=BODY,
        alignment=1,
    )

    SMALL = ParagraphStyle(
        "SMALL",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.1,
        leading=8.4,
        textColor=MUTED,
        alignment=0,
    )

    SMALL_CENTER = ParagraphStyle(
        "SMALL_CENTER",
        parent=SMALL,
        alignment=1,
    )

    LABEL = ParagraphStyle(
        "LABEL",
        parent=BODY,
        fontName="Helvetica-Bold",
        textColor=BRAND_DARK,
    )

    # =========================
    # Auxiliares internos
    # =========================
    def header_footer(canvas, doc):
        canvas.saveState()

        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.4)
        canvas.line(18 * mm, A4[1] - 12 * mm, A4[0] - 18 * mm, A4[1] - 12 * mm)
        canvas.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)

        canvas.setFont("Helvetica-Bold", 7.8)
        canvas.setFillColor(BRAND_DARK)
        canvas.drawString(20 * mm, 9 * mm, "CHECK INSURANCE RISK")

        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(62 * mm, 9 * mm, "Documento confidencial")
        canvas.drawRightString(A4[0] - 20 * mm, 9 * mm, f"Página {doc.page}")

        canvas.restoreState()

    def tbl(data: List[List[Any]], col_widths=None, header_bg=BRAND, font_size=7.8, center=False) -> Table:
        t = Table(data, colWidths=col_widths, hAlign="CENTER" if center else "LEFT")
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), header_bg),
                    ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), font_size),
                    ("TOPPADDING", (0, 0), (-1, 0), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
                    ("GRID", (0, 0), (-1, -1), 0.25, BORDER),
                    ("FONTSIZE", (0, 1), (-1, -1), font_size),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("TEXTCOLOR", (0, 1), (-1, -1), TEXT),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4.5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4.5),
                    ("TOPPADDING", (0, 1), (-1, -1), 3.2),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 3.2),
                ]
            )
        )
        return t

    def mini_tbl(data: List[List[Any]], col_widths=None) -> Table:
        return tbl(data, col_widths=col_widths, header_bg=BRAND, font_size=7.4, center=True)

    def info_box(title: str, text: str) -> Table:
        t = Table(
            [
                [Paragraph(f"<b>{_safe(title, 100)}</b>", BODY)],
                [Paragraph(_safe(text, 1200), BODY)],
            ],
            colWidths=[170 * mm],
            hAlign="CENTER",
        )
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), SOFT),
                    ("BOX", (0, 0), (-1, -1), 0.35, BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.20, BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return t

    def decision_box(text: str) -> Table:
        t = Table(
            [[Paragraph(f"<b>{_safe(text, 220)}</b>", BODY_CENTER)]],
            colWidths=[170 * mm],
            hAlign="CENTER",
        )
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), BRAND_DARK),
                    ("TEXTCOLOR", (0, 0), (-1, -1), WHITE),
                    ("BOX", (0, 0), (-1, -1), 0.4, BRAND_DARK),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return t

    def two_col_info(left_title: str, left_html: str, right_title: str, right_html: str) -> Table:
        box = Table(
            [
                [
                    Paragraph(f"<b>{_safe(left_title, 80)}</b>", BODY_CENTER),
                    Paragraph(f"<b>{_safe(right_title, 80)}</b>", BODY_CENTER),
                ],
                [
                    Paragraph(left_html, BODY),
                    Paragraph(right_html, BODY),
                ],
            ],
            colWidths=[85 * mm, 85 * mm],
            hAlign="CENTER",
        )
        box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), SOFT),
                    ("BOX", (0, 0), (-1, -1), 0.35, BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.20, BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return box

    def _pick(d: dict, *keys: str, default: str = "N/D") -> str:
        for k in keys:
            v = d.get(k)
            if v is None:
                continue
            s = str(v).strip()
            if s:
                return s
        return default

    def _pick_int(d: dict, *keys: str, default: int = 0) -> int:
        for k in keys:
            v = d.get(k)
            try:
                if v is None:
                    continue
                return int(v)
            except Exception:
                continue
        return default

    def _fmt_date(v: Any) -> str:
        if v is None:
            return "N/D"
        s = str(v).replace("T", " ")
        return s[:10] if len(s) >= 10 else s

    def _fmt_money(v: Any, currency: str | None = None) -> str:
        try:
            fv = float(v)
            txt = f"{fv:,.2f}".replace(",", "X").replace(".", ",").replace("X", " ")
        except Exception:
            txt = _safe(v, 40) if v is not None else "N/D"
        return f"{txt} {currency}".strip() if currency else txt

    def _render_source_evidence(src: str, hits: List[dict], max_rows: int = 10) -> List[Any]:
        block: List[Any] = []
        block.append(Paragraph(f"Fonte: <b>{_safe(src, 80)}</b>", H3))

        rows = [["#", "Nome ou entidade", "Pontuação", "Referência", "Observação"]]
        for i, h in enumerate((hits or [])[:max_rows], 1):
            if not isinstance(h, dict):
                h = {"value": h}
            name = _pick(h, "matched_name", "name", "full_name", "entity_name", "value")
            score = _pick_int(h, "match_score", "score", "similarity", default=0)
            refid = _pick(h, "list_id", "uid", "external_id", "id", "source_ref", "reference")
            note = _pick(h, "reason", "note", "description", "details", "summary")
            rows.append([str(i), _safe(name, 60), str(score), _safe(refid, 40), _safe(note, 100)])

        block.append(mini_tbl(rows, col_widths=[8 * mm, 55 * mm, 18 * mm, 25 * mm, 64 * mm]))
        block.append(Spacer(1, 3))
        return block

    def _render_underwriting_product(product_type: str, pack: dict) -> List[Any]:
        block: List[Any] = []

        policies = pack.get("policies", []) or []
        payments = pack.get("payments", []) or []
        claims = pack.get("claims", []) or []
        cancellations = pack.get("cancellations", []) or []
        fraud_flags = pack.get("fraud_flags", []) or []

        active_policies = sum(
            1 for p in policies
            if str((p or {}).get("status", "")).lower() in ("active", "ativa", "ativo", "activa", "activo")
        )
        cancelled_policies = sum(
            1 for p in policies
            if str((p or {}).get("status", "")).lower() in ("cancelled", "canceled", "cancelada", "cancelado")
        )
        late_payments = sum(
            1 for p in payments
            if str((p or {}).get("status", "")).lower() in ("late", "atraso", "atrasado", "overdue", "em atraso")
        )
        total_claims_paid = sum(float((c or {}).get("amount_paid") or 0) for c in claims)

        block.append(Paragraph(f"Produto segurador: <b>{_safe(product_type, 60) or 'N/D'}</b>", H2))

        summary_table = [
            ["Indicador", "Valor", "Indicador", "Valor"],
            ["Apólices", str(len(policies)), "Apólices activas", str(active_policies)],
            ["Apólices canceladas", str(cancelled_policies), "Pagamentos", str(len(payments))],
            ["Pagamentos em atraso", str(late_payments), "Sinistros", str(len(claims))],
            ["Cancelamentos", str(len(cancellations)), "Sinalizações de fraude", str(len(fraud_flags))],
        ]
        block.append(tbl(summary_table, col_widths=[48 * mm, 37 * mm, 48 * mm, 37 * mm], center=True))
        block.append(Spacer(1, 3))

        if policies:
            block.append(Paragraph("Apólices", H3))
            rows = [["Apólice", "Seguradora", "Estado", "Início", "Fim", "Prémio"]]
            for p in policies[:12]:
                rows.append([
                    _safe(p.get("policy_number"), 30),
                    _safe(p.get("insurer_name"), 35),
                    _translate_policy_status(p.get("status")),
                    _fmt_date(p.get("start_date")),
                    _fmt_date(p.get("end_date")),
                    _fmt_money(p.get("premium_amount"), p.get("currency")),
                ])
            block.append(mini_tbl(rows, col_widths=[26 * mm, 42 * mm, 24 * mm, 24 * mm, 24 * mm, 30 * mm]))
            block.append(Spacer(1, 2))

        if payments:
            block.append(Paragraph("Pagamentos", H3))
            rows = [["Vencimento", "Pagamento", "Valor", "Estado", "Apólice"]]
            for p in payments[:12]:
                rows.append([
                    _fmt_date(p.get("due_at")),
                    _fmt_date(p.get("paid_at")),
                    _fmt_money(p.get("amount"), p.get("currency")),
                    _translate_payment_status(p.get("status")),
                    _safe(p.get("policy_number"), 25),
                ])
            block.append(mini_tbl(rows, col_widths=[28 * mm, 28 * mm, 36 * mm, 28 * mm, 45 * mm]))
            block.append(Spacer(1, 2))

        if claims:
            block.append(Paragraph("Sinistros", H3))
            rows = [["Sinistro", "Data", "Estado", "Valor reclamado", "Valor pago"]]
            for c in claims[:12]:
                rows.append([
                    _safe(c.get("claim_number"), 25),
                    _fmt_date(c.get("loss_date")),
                    _translate_claim_status(c.get("status")),
                    _fmt_money(c.get("amount_claimed"), c.get("currency")),
                    _fmt_money(c.get("amount_paid"), c.get("currency")),
                ])
            block.append(mini_tbl(rows, col_widths=[28 * mm, 26 * mm, 28 * mm, 42 * mm, 42 * mm]))
            block.append(Spacer(1, 2))

        if cancellations:
            block.append(Paragraph("Cancelamentos", H3))
            rows = [["Data", "Motivo"]]
            for c in cancellations[:12]:
                rows.append([
                    _fmt_date(c.get("cancelled_at")),
                    _safe(c.get("reason"), 120),
                ])
            block.append(mini_tbl(rows, col_widths=[28 * mm, 142 * mm]))
            block.append(Spacer(1, 2))

        if fraud_flags:
            block.append(Paragraph("Fraude ou sinalizações", H3))
            rows = [["Severidade ou tipo", "Detalhe"]]
            for f in fraud_flags[:12]:
                rows.append([
                    _safe(f.get("severity") or f.get("flag_type"), 30),
                    _safe(f.get("description"), 120),
                ])
            block.append(mini_tbl(rows, col_widths=[35 * mm, 135 * mm]))
            block.append(Spacer(1, 2))

        if not claims and not cancellations and not fraud_flags:
            block.append(
                info_box(
                    "Eventos adicionais",
                    "Não foram identificados sinistros, cancelamentos ou sinalizações de fraude associados a este produto.",
                )
            )
            block.append(Spacer(1, 2))

        if len(fraud_flags) > 0:
            observation = "Foram identificados indicadores de risco operacional associados a este produto, recomendando validação adicional e revisão reforçada."
        elif len(claims) > 0 and late_payments > 0:
            observation = "O histórico demonstra ocorrência de sinistros e atrasos em pagamentos. Recomenda-se análise contextual adicional."
        elif len(claims) > 0:
            observation = f"O histórico regista {len(claims)} sinistro(s), com total pago estimado de {_fmt_money(total_claims_paid)}."
        elif len(policies) > 0:
            observation = "O histórico disponível demonstra comportamento regular, sem indicadores críticos de risco operacional."
        else:
            observation = "Não existem eventos relevantes registados para este produto."

        block.append(info_box("Leitura de risco", observation))
        return block

    # =========================
    # Preparação de dados
    # =========================
    score = getattr(risk, "score", None)
    score_i = _score_to_int(score)
    band, review_level = _score_band(score)

    comp = compliance_by_category or _normalize_matches_generic(getattr(risk, "matches", None) or [])
    pep_count, sanc_count, watch_count, adv_count = _counts_from_compliance(comp)

    uw = underwriting_by_product or {}
    has_uw = bool(uw)

    fraud_flags_count = 0
    for _pt, pack in (uw or {}).items():
        fraud_flags_count += len((pack or {}).get("fraud_flags", []) or [])

    decision, reasons = _decision_policy(score, pep_count, sanc_count, fraud_flags_count)
    exec_summary = _institutional_summary(score, pep_count, sanc_count, watch_count, adv_count, has_uw)

    report_reference = report_reference or (
        f"CIR-RISK-{generated_at.strftime('%Y%m%d')}-{str(getattr(risk, 'id', '')).replace('-', '').upper()[:6]}"
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=17 * mm,
        bottomMargin=17 * mm,
        title=report_title,
        author="Check Insurance Risk",
    )

    story: List[Any] = []

    # =========================
    # Página 1 - Síntese executiva
    # =========================
    story.append(Paragraph("CHECK INSURANCE RISK", H0))
    story.append(Paragraph("Relatório Institucional de Inteligência de Risco", H1))
    story.append(Spacer(1, 5))

    left_html = (
        f"<b>Nome:</b> {_safe(getattr(risk, 'query_name', ''), 120) or 'N/D'}<br/>"
        f"<b>Nacionalidade:</b> {_safe(getattr(risk, 'query_nationality', ''), 60) or 'N/D'}<br/>"
        f"<b>Bilhete de Identidade:</b> {_safe(getattr(risk, 'query_bi', ''), 60) or 'N/D'}<br/>"
        f"<b>Passaporte:</b> {_safe(getattr(risk, 'query_passport', ''), 60) or 'N/D'}"
    )

    right_html = (
        f"<b>Referência do relatório:</b> {_safe(report_reference, 80)}<br/>"
        f"<b>Data e hora:</b> {generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}<br/>"
        f"<b>Pontuação:</b> {score_i if score is not None else 'N/D'}<br/>"
        f"<b>Classificação:</b> {band}<br/>"
        f"<b>Nível de revisão:</b> {review_level}<br/>"
        f"<b>Analista:</b> {_safe(analyst_name, 80) or 'Sistema'}"
    )

    story.append(two_col_info("Sujeito analisado", left_html, "Dados da análise", right_html))
    story.append(Spacer(1, 5))

    story.append(decision_box(f"DECISÃO RECOMENDADA: {decision}"))
    story.append(Spacer(1, 5))

    kpi_table = [
        ["PEP", "Sanções", "Listas de observação", "Meios adversos", "Histórico segurador", "Fraude"],
        [str(pep_count), str(sanc_count), str(watch_count), str(adv_count), "SIM" if has_uw else "NÃO", str(fraud_flags_count)],
    ]
    story.append(tbl(kpi_table, col_widths=[20 * mm, 24 * mm, 38 * mm, 31 * mm, 33 * mm, 24 * mm], center=True))
    story.append(Spacer(1, 5))

    story.append(Paragraph("Sumário executivo", H1))
    story.append(Paragraph(exec_summary, BODY_CENTER))
    story.append(Spacer(1, 4))

    rr = [["#", "Fundamentação da decisão"]]
    for i, r_ in enumerate(reasons[:5], 1):
        rr.append([str(i), _safe(r_, 260)])
    story.append(tbl(rr, col_widths=[12 * mm, 158 * mm], center=True))
    story.append(Spacer(1, 4))

    story.append(
        info_box(
            "Âmbito da avaliação",
            "A presente avaliação reflecte os dados fornecidos na pesquisa e as fontes actualmente configuradas e activas. A decisão final deve incluir validação humana e documental, nos termos das políticas internas e das exigências regulatórias aplicáveis.",
        )
    )
    story.append(Spacer(1, 3))
    story.append(
        info_box(
            "Confidencialidade",
            "Documento confidencial, destinado exclusivamente a partes autorizadas. A sua divulgação, reprodução ou circulação depende de autorização prévia e expressa.",
        )
    )
    story.append(PageBreak())

    # =========================
    # Página 2 - Compliance
    # =========================
    story.append(Paragraph("Revisão de compliance", H0))
    story.append(Spacer(1, 3))
    story.append(
        Paragraph(
            "A presente secção apresenta potenciais correspondências em fontes de compliance, organizadas por categoria e por fonte. Todas as correspondências devem ser confirmadas por validação humana antes de qualquer deliberação final.",
            BODY_CENTER,
        )
    )
    story.append(Spacer(1, 4))

    def _render_category(title: str, by_source: Dict[str, List[dict]]) -> None:
        story.append(Paragraph(title, H2))
        rows = [["Fonte", "N.º de registos", "Pontuação máxima"]]
        for src, hits in by_source.items():
            top = 0
            for h in hits or []:
                try:
                    top = max(top, int((h or {}).get("match_score", 0) or 0))
                except Exception:
                    pass
            rows.append([_safe(src, 60), str(len(hits or [])), str(top)])
        story.append(tbl(rows, col_widths=[95 * mm, 35 * mm, 40 * mm], center=True))
        story.append(Spacer(1, 3))
        for src, hits in by_source.items():
            story.append(KeepTogether(_render_source_evidence(str(src), hits or [], max_rows=10)))

    if comp.get("PEP"):
        _render_category("PEP", comp.get("PEP") or {})

    others = {
        "Sanções": comp.get("SANCTIONS") or {},
        "Listas de observação": comp.get("WATCHLIST") or {},
        "Meios adversos": comp.get("ADVERSE_MEDIA") or {},
    }

    non_empty = {k: v for k, v in others.items() if v}
    empty = [k for k, v in others.items() if not v]

    for title, val in non_empty.items():
        _render_category(title, val)

    if empty:
        story.append(
            info_box(
                "Outras categorias de compliance",
                "Não foram identificadas correspondências relevantes nas seguintes categorias: " + ", ".join(empty) + ".",
            )
        )
        story.append(Spacer(1, 3))

    # =========================
    # Página 3+ - Histórico segurador
    # =========================
    story.append(PageBreak())
    story.append(Paragraph("Histórico segurador e inteligência de risco", H0))
    story.append(Spacer(1, 3))
    story.append(
        Paragraph(
            "A análise abaixo apresenta o histórico agregado por tipo de produto de seguro, com base nos registos actualmente disponíveis.",
            BODY_CENTER,
        )
    )
    story.append(Spacer(1, 4))

    if not uw:
        story.append(
            info_box(
                "Resultado",
                "Não existem registos de histórico segurador disponíveis nas fontes actualmente carregadas.",
            )
        )
    else:
        for product_type in sorted(uw.keys(), key=lambda x: str(x)):
            story.append(KeepTogether(_render_underwriting_product(product_type, uw.get(product_type) or {})))
            story.append(Spacer(1, 4))

    # =========================
    # Página final - Apêndice técnico
    # =========================
    story.append(PageBreak())
    story.append(Paragraph("Apêndice técnico", H0))
    story.append(Spacer(1, 3))

    methodology_text = (
        "A presente avaliação combina fontes de compliance, histórico segurador quando disponível e regras institucionais de decisão. "
        "Os resultados têm natureza indicativa e devem ser confirmados por validação humana, documental e operacional."
    )
    story.append(info_box("Metodologia", methodology_text))
    story.append(Spacer(1, 4))

    technical_rows = [
        ["Elemento", "Valor"],
        ["Referência do relatório", _safe(report_reference, 90)],
        ["Hash de integridade", _safe(integrity_hash, 90)],
        ["Assinatura do servidor", _safe(server_signature, 90)],
        ["Ligação de verificação", _safe(verify_url, 120)],
    ]
    story.append(tbl(technical_rows, col_widths=[48 * mm, 122 * mm], center=True))
    story.append(Spacer(1, 5))

    story.append(
        info_box(
            "Autenticidade e verificação",
            "A validação digital do documento encontra-se disponível através do código QR de verificação. "
            "A autenticidade do relatório deve ser confirmada com base na referência, no hash de integridade e na assinatura do servidor.",
        )
    )
    story.append(Spacer(1, 5))

    if qrcode is not None:
        try:
            from io import BytesIO as _BIO

            qr_img = qrcode.make(verify_url)
            qbuf = _BIO()
            qr_img.save(qbuf, format="PNG")
            qbuf.seek(0)

            story.append(Paragraph("Código QR de verificação", H2))
            story.append(Spacer(1, 2))

            qr_table = Table(
                [[Image(qbuf, width=26 * mm, height=26 * mm)]],
                colWidths=[170 * mm],
                hAlign="CENTER",
            )
            qr_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
            story.append(qr_table)
        except Exception:
            story.append(Paragraph("Código QR indisponível por erro de geração.", SMALL_CENTER))
    else:
        story.append(Paragraph("Código QR indisponível por ausência da dependência necessária.", SMALL_CENTER))

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return buf.getvalue()


def build_risk_pdf_institutional_pt(*args, **kwargs) -> bytes:
    return build_risk_pdf_institutional(*args, **kwargs)
