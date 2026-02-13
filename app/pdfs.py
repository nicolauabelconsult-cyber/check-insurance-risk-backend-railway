from __future__ import annotations

from datetime import datetime
from io import BytesIO
import hashlib
import os
from typing import Any, Dict, List

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


# =========================================================
# Helpers
# =========================================================

def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def classificar_risco(score: int) -> str:
    if score >= 70:
        return "ALTO"
    if score >= 40:
        return "MÉDIO"
    return "BAIXO"


def interpretar_score(score: int) -> str:
    nivel = classificar_risco(score)
    if nivel == "ALTO":
        return "Acima do limiar institucional. Recomenda-se Due Diligence Reforçada (EDD) e validação sénior."
    if nivel == "MÉDIO":
        return "Risco moderado. Recomenda-se validações adicionais e monitorização reforçada."
    return "Risco baixo. Procedimentos padrão e monitorização normal."


def recomendacao_operacional(score: int) -> str:
    nivel = classificar_risco(score)
    if nivel == "ALTO":
        return (
            "• Aplicar Due Diligence Reforçada (EDD)\n"
            "• Requer validação sénior (Compliance)\n"
            "• Considerar mitigação/recusa conforme política\n"
            "• Intensificar monitorização"
        )
    if nivel == "MÉDIO":
        return (
            "• Solicitar documentação adicional\n"
            "• Validar correspondências antes de decisão final\n"
            "• Monitorização reforçada por período definido"
        )
    return "• Prosseguir sob procedimentos padrão\n• Monitorização standard"


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


def _maybe_logo() -> Image | None:
    path = getattr(settings, "PDF_LOGO_PATH", None) or os.getenv("PDF_LOGO_PATH")
    if not path or not os.path.exists(path):
        return None
    return Image(path, width=22 * mm, height=22 * mm)


def _footer(c: canvas.Canvas, doc):
    c.saveState()
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)
    c.drawString(18 * mm, 12 * mm, "Documento confidencial. A distribuição não autorizada é proibida.")
    c.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Página {doc.page}")
    c.restoreState()


def _table(data: List[List[str]], col_widths: List[float], header: bool = True) -> Table:
    t = Table(data, colWidths=col_widths)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1F44")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
        ]
    t.setStyle(TableStyle(style))
    return t


def _render_bullets(items: List[str]) -> str:
    return "<br/>".join([f"• {x}" for x in items]) if items else "—"


# =========================================================
# Matches agrupados (exportável para risks.py)
# =========================================================

def matches_by_type(risk: Risk) -> Dict[str, List[dict]]:
    grouped: Dict[str, List[dict]] = {
        "SANÇÕES": [],
        "PEP": [],
        "WATCHLISTS": [],
        "MEDIA ADVERSA": [],
        "OUTROS": [],
    }

    for m in (risk.matches or []):
        if not isinstance(m, dict):
            continue

        t = str(m.get("type") or m.get("risk_type") or "").upper().strip()
        src = str(m.get("source") or "").upper()

        if t == "SANCTIONS" or "OFAC" in src or "UN" in src:
            grouped["SANÇÕES"].append(m)
        elif t == "PEP":
            grouped["PEP"].append(m)
        elif t in {"ADVERSE_MEDIA", "MEDIA"}:
            grouped["MEDIA ADVERSA"].append(m)
        elif t == "WATCHLIST":
            grouped["WATCHLISTS"].append(m)
        else:
            grouped["OUTROS"].append(m)

    return grouped


# =========================================================
# PDF Principal
# =========================================================

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
        title="Relatório de Avaliação de Risco (Compliance + Subscrição)",
        author="Check Insurance Risk",
    )

    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=styles["Title"], fontSize=15.5, textColor=colors.HexColor("#0A1F44"))
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11, textColor=colors.HexColor("#0A1F44"), spaceBefore=10, spaceAfter=6)
    normal = ParagraphStyle("N", parent=styles["Normal"], fontSize=9, leading=12)
    small_grey = ParagraphStyle("SG", parent=styles["Normal"], fontSize=7.8, textColor=colors.grey, leading=10)

    elements: List[Any] = []

    # Cabeçalho
    logo = _maybe_logo()
    left = []
    if logo:
        left.append(logo)
    left.append(Paragraph("<b>CHECK INSURANCE RISK</b><br/>KYC • AML • PEP • Due Diligence", small_grey))

    header = Table([[left, Paragraph("<b>Relatório Institucional (Banco/Seguradora)</b>", H1)]], colWidths=[70 * mm, 110 * mm])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#0A1F44")), ("BOTTOMPADDING", (0, 0), (-1, 0), 8)]))
    elements.append(header)
    elements.append(Spacer(1, 8))

    report_no = make_report_number(risk)
    compliance_score = _safe_int(getattr(risk, "score", 0), 0)
    nivel = classificar_risco(compliance_score)

    app_version = getattr(settings, "APP_VERSION", "v1.0")
    app_env = getattr(settings, "APP_ENV", "Produção")
    system_version = f"{app_version} ({app_env})"

    meta = [
        ["Número do Relatório", report_no],
        ["ID do Processo", str(risk.id)],
        ["Entidade", str(risk.entity_id)],
        ["Analista", analyst_name],
        ["Data de Emissão (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S")],
        ["Versão do Sistema", system_version],
    ]
    elements.append(_table([["Campo", "Valor"]] + meta, [50 * mm, 130 * mm]))

    # Resumo Executivo
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Resumo Executivo (Compliance)", H2))
    elements.append(Paragraph(f"Classificação de risco <b>{nivel}</b>, com score de compliance <b>{compliance_score}</b>. {interpretar_score(compliance_score)}", normal))

    # Identificação
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Identificação do Sujeito Avaliado", H2))
    subj = [
        ["Nome consultado", risk.query_name or ""],
        ["Nacionalidade", risk.query_nationality or ""],
        ["BI", risk.query_bi or ""],
        ["Passaporte", risk.query_passport or ""],
        ["Estado do processo", getattr(risk.status, "value", str(risk.status))],
    ]
    elements.append(_table([["Campo", "Valor"]] + subj, [50 * mm, 130 * mm]))

    # Screening por categoria
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Resultados de Screening (por Categoria)", H2))
    grouped = matches_by_type(risk)

    def render_group(title: str, items: List[dict]):
        elements.append(Paragraph(f"<b>{title}</b>", normal))
        if not items:
            elements.append(Paragraph("Sem correspondências relevantes identificadas.", small_grey))
            elements.append(Spacer(1, 4))
            return
        rows = [["Fonte", "Correspondência", "Confiança", "Detalhe"]]
        for m in items[:20]:
            match_txt = "SIM" if m.get("match") else "NÃO"
            conf = m.get("confidence")
            try:
                conf_txt = f"{float(conf) * 100:.0f}%" if conf is not None else ""
            except Exception:
                conf_txt = str(conf) if conf is not None else ""
            detail_bits = []
            for key in ("program", "category", "role", "position", "country", "note"):
                if m.get(key):
                    detail_bits.append(f"{key}: {m.get(key)}")
            detail = " | ".join(detail_bits) if detail_bits else (m.get("note") or "")
            rows.append([str(m.get("source", "")), match_txt, conf_txt, str(detail)])
        elements.append(_table(rows, [45 * mm, 25 * mm, 25 * mm, 85 * mm], header=True))
        elements.append(Spacer(1, 6))

    render_group("SANÇÕES", grouped["SANÇÕES"])
    render_group("PEP (Pessoa Politicamente Exposta)", grouped["PEP"])
    render_group("WATCHLISTS / LISTAS DE OBSERVAÇÃO", grouped["WATCHLISTS"])
    render_group("MEDIA ADVERSA (Risco Reputacional)", grouped["MEDIA ADVERSA"])
    if grouped["OUTROS"]:
        render_group("OUTROS", grouped["OUTROS"])

    # Sumário narrativo
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Sumário da Avaliação (Compliance)", H2))
    elements.append(Paragraph(risk.summary or "—", normal))

    # Recomendação Compliance
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Recomendação de Compliance", H2))
    elements.append(Paragraph(recomendacao_operacional(compliance_score).replace("\n", "<br/>"), normal))

    # ================================
    # Perfil Segurador (Excel)
    # ================================
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Perfil Segurador e Histórico (Fontes Excel)", H2))

    insurance = getattr(risk, "insurance_profile", None)
    if isinstance(insurance, dict) and insurance:
        pb = insurance.get("payment_behavior") or {}
        ch = insurance.get("claims_history") or {}
        active = insurance.get("active_policies") or []
        canc = insurance.get("cancellations") or []
        fraud = insurance.get("fraud_indicators") or []

        payer_score = _safe_float(insurance.get("payer_score"), 0.0)

        pay_table = [
            ["Indicador", "Valor"],
            ["Índice de Pagador (0-1)", f"{payer_score:.2f}"],
            ["Pagamentos em dia (ratio)", f"{_safe_float(pb.get('on_time_ratio'), 0.0):.2f}"],
            ["Atrasos (12 meses)", str(_safe_int(pb.get("late_payments_12m"), 0))],
            ["Incumprimentos (36 meses)", str(_safe_int(pb.get("defaults_36m"), 0))],
            ["Média de atraso (dias)", str(_safe_int(pb.get("avg_delay_days"), 0))],
        ]
        elements.append(_table(pay_table, [80 * mm, 100 * mm], header=True))

        elements.append(Spacer(1, 6))
        claims_table = [
            ["Indicador", "Valor"],
            ["Sinistros (12 meses)", str(_safe_int(ch.get("claims_12m"), 0))],
            ["Sinistros (36 meses)", str(_safe_int(ch.get("claims_36m"), 0))],
            ["Total pago (36 meses)", str(_safe_int(ch.get("total_paid_36m"), 0))],
            ["Maior sinistro", str(_safe_int(ch.get("max_single_claim"), 0))],
            ["Risco de frequência", str(ch.get("frequency_risk") or "—")],
            ["Risco de severidade", str(ch.get("severity_risk") or "—")],
        ]
        elements.append(_table(claims_table, [80 * mm, 100 * mm], header=True))

        # Apólices ativas
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("<b>Apólices ativas</b>", normal))
        if active:
            rows = [["Nº Apólice", "Tipo", "Estado", "Início", "Fim", "Prémio", "Capital"]]
            for p in active[:15]:
                rows.append([
                    str(p.get("policy_no", "")),
                    str(p.get("type", "")),
                    str(p.get("status", "")),
                    str(p.get("start", "")),
                    str(p.get("end", "")),
                    str(p.get("premium", "")),
                    str(p.get("sum_insured", "")),
                ])
            elements.append(_table(rows, [25*mm, 25*mm, 18*mm, 20*mm, 20*mm, 25*mm, 27*mm], header=True))
        else:
            elements.append(Paragraph("Sem dados de apólices ativas disponíveis.", small_grey))

        # Cancelamentos
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("<b>Cancelamentos/Rescisões</b>", normal))
        if canc:
            rows = [["Nº Apólice", "Motivo", "Data"]]
            for x in canc[:15]:
                rows.append([str(x.get("policy_no", "")), str(x.get("reason", "")), str(x.get("date", ""))])
            elements.append(_table(rows, [40*mm, 110*mm, 30*mm], header=True))
        else:
            elements.append(Paragraph("Sem registos de cancelamentos disponíveis.", small_grey))

        # Fraude
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("<b>Indicadores de Fraude</b>", normal))
        if fraud:
            rows = [["Flag", "Severidade", "Nota", "Data"]]
            for f in fraud[:15]:
                rows.append([
                    str(f.get("flag", "")),
                    str(f.get("severity", "")),
                    str(f.get("note", "")),
                    str(f.get("date", "")),
                ])
            elements.append(_table(rows, [45*mm, 25*mm, 85*mm, 25*mm], header=True))
        else:
            elements.append(Paragraph("Sem indicadores de fraude reportados.", small_grey))
    else:
        elements.append(Paragraph("Sem dados de histórico segurável para este sujeito (pagamentos/sinistros/apólices/fraude).", small_grey))

    # ================================
    # Decisão Final (FinalDecision)
    # ================================
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Decisão Final de Subscrição (Banco/Seguradora)", H2))

    fd = getattr(risk, "final_decision", None)
    if isinstance(fd, dict) and fd:
        decisao = str(fd.get("decision", "—"))
        racional = str(fd.get("rationale", "—"))
        premium_hint = str(fd.get("premium_hint", "—"))
        comp_score = str(fd.get("compliance_score", "—"))
        ins_score = str(fd.get("insurance_score", "—"))
        final_score = str(fd.get("final_score", "—"))
        conditions = fd.get("underwriting_conditions", []) or []
        actions = fd.get("underwriting_actions", []) or []
        drivers = fd.get("decision_drivers", []) or []
    else:
        decisao = "—"
        racional = "Sem decisão final calculada."
        premium_hint = "—"
        comp_score = str(compliance_score)
        ins_score = "—"
        final_score = "—"
        conditions = []
        actions = []
        drivers = []

    score_table = [
        ["Métrica", "Valor"],
        ["Compliance Score", comp_score],
        ["Insurance Score (histórico segurável)", ins_score],
        ["Score Final (ponderado)", final_score],
    ]
    elements.append(_table(score_table, [90 * mm, 90 * mm], header=True))

    elements.append(Spacer(1, 6))

    uw_table = [
        ["Campo", "Valor"],
        ["Decisão final", decisao],
        ["Racional", racional],
        ["Sugestão de ajuste de prémio", premium_hint],
        ["Condições sugeridas", _render_bullets([str(x) for x in conditions])],
        ["Ações obrigatórias antes de emitir", _render_bullets([str(x) for x in actions])],
    ]
    uw = Table(uw_table, colWidths=[55 * mm, 125 * mm])
    uw.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1F44")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("FONTSIZE", (0, 0), (-1, -1), 8.7),
            ]
        )
    )
    elements.append(uw)

    if drivers:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("Principais motivos para a decisão", H2))
        for d in drivers[:10]:
            elements.append(Paragraph(f"• {d}", normal))

    # Metodologia e Nota Legal
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Metodologia e Nota Legal", H2))
    metodologia = (
        "A presente avaliação combina screening de compliance (KYC/AML/PEP/Sanções/Watchlists/Media) "
        "com perfil segurador (pagamentos, sinistros, apólices, cancelamentos e indicadores de fraude), "
        "quando disponível via fontes internas (Excel). O resultado é um apoio à decisão e não constitui "
        "determinação legal. Deve ser interpretado conforme a política interna do Banco/Seguradora."
    )
    elements.append(Paragraph(metodologia, normal))

    # Verificação Digital
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Verificação Digital do Documento", H2))

    qr = _qr_image(verify_url)
    url_lines = simpleSplit(verify_url, normal.fontName, normal.fontSize, 120 * mm)
    url_lines = url_lines[:3]
    pretty_url = "<br/>".join(url_lines)

    vt = Table([[qr, Paragraph(f"<b>Link de verificação:</b><br/>{pretty_url}", normal)]], colWidths=[40 * mm, 140 * mm])
    vt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    elements.append(vt)

    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"<b>Hash de integridade:</b> {integrity_hash}", small_grey))
    elements.append(Paragraph(f"<b>Assinatura do sistema:</b> {server_signature}", small_grey))

    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)

    buffer.seek(0)
    return buffer.read()
