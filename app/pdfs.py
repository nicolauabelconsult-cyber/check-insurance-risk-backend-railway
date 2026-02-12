from __future__ import annotations

from datetime import datetime
from io import BytesIO
import hashlib
import os
from typing import Any, Dict, List, Tuple

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
# 1) Semântica de Risco (Banco-ready e extensível)
# =========================================================

def classificar_risco(score: int) -> str:
    # Política institucional (ajustável)
    if score >= 70:
        return "ALTO"
    if score >= 40:
        return "MÉDIO"
    return "BAIXO"


def interpretar_score(score: int) -> str:
    nivel = classificar_risco(score)
    if nivel == "ALTO":
        return "Acima do limiar institucional. Recomenda-se Due Diligence Reforçada (EDD) e validação por responsável sénior de Compliance."
    if nivel == "MÉDIO":
        return "Risco moderado. Recomenda-se validação documental adicional e monitorização contínua, conforme política interna."
    return "Risco baixo. Aplicam-se procedimentos normais de compliance e monitorização."


def recomendacao_operacional(score: int) -> str:
    nivel = classificar_risco(score)
    if nivel == "ALTO":
        return (
            "• Aplicar Due Diligence Reforçada (EDD)\n"
            "• Requer validação por responsável sénior de Compliance\n"
            "• Considerar recusa/mitigação conforme política interna\n"
            "• Intensificar monitorização e revisão de transações"
        )
    if nivel == "MÉDIO":
        return (
            "• Solicitar documentação adicional e validações complementares\n"
            "• Aplicar monitorização reforçada por período definido\n"
            "• Rever correspondências e evidências antes de decisão final"
        )
    return (
        "• Prosseguir sob procedimentos normais\n"
        "• Manter monitorização standard e revisão periódica"
    )


# =========================================================
# 2) Integridade e assinatura (simplificada)
# =========================================================

def make_integrity_hash(risk: Risk) -> str:
    raw = f"{risk.id}|{risk.entity_id}|{risk.score}|{risk.status}|{risk.created_at}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_server_signature(integrity_hash: str) -> str:
    raw = f"{integrity_hash}|{settings.PDF_SECRET_KEY}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_report_number(risk: Risk) -> str:
    """
    Banco-ready sem migração:
    número determinístico baseado em data + parte do UUID.
    (Se quiseres sequência real por entidade, adicionamos tabela e migration.)
    """
    dt = risk.created_at or datetime.utcnow()
    ymd = dt.strftime("%Y%m%d")
    short = str(risk.id).split("-")[0].upper()
    return f"CIR-{ymd}-{short}"


# =========================================================
# 3) Normalização de dados (preparado para motor real)
# =========================================================

def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _risk_factors(risk: Risk) -> Dict[str, int]:
    """
    Preparado para motor real.
    - Se o motor gravar risk.risk_factors (dict), usamos.
    - Se ainda não existir, geramos um breakdown básico a partir dos matches.
    """
    factors = getattr(risk, "risk_factors", None)
    if isinstance(factors, dict) and factors:
        # Garantir ints
        return {str(k): _safe_int(v, 0) for k, v in factors.items()}

    # Fallback inteligente (MVP): estimativa a partir de matches
    matches = risk.matches or []
    score = _safe_int(getattr(risk, "score", 0), 0)

    buckets = {
        "sanctions_score": 0,
        "pep_score": 0,
        "watchlist_score": 0,
        "adverse_media_score": 0,
        "jurisdiction_score": 0,
        "name_similarity_score": 0,
    }

    for m in matches:
        if not isinstance(m, dict):
            continue
        if not m.get("match"):
            continue

        mtype = str(m.get("type") or m.get("risk_type") or "").upper().strip()
        src = str(m.get("source") or "").upper()

        # Heurísticas leves (até o motor real gravar fatores reais)
        if mtype == "SANCTIONS" or "OFAC" in src or "UN" in src:
            buckets["sanctions_score"] += 35
        elif mtype == "PEP":
            buckets["pep_score"] += 20
        elif mtype == "ADVERSE_MEDIA" or mtype == "MEDIA":
            buckets["adverse_media_score"] += 15
        else:
            buckets["watchlist_score"] += 10

        conf = m.get("confidence")
        try:
            c = float(conf) if conf is not None else 0.0
        except Exception:
            c = 0.0

        if c >= 0.80:
            buckets["name_similarity_score"] += 8
        elif c >= 0.60:
            buckets["name_similarity_score"] += 4

    # Ajustar para não ultrapassar muito o score (apenas para visual)
    total = sum(buckets.values())
    if total > 0 and score > 0:
        # Normaliza proporcionalmente para aproximar o score
        scale = score / total
        for k in list(buckets.keys()):
            buckets[k] = int(round(buckets[k] * scale))

    return buckets


def _matches_by_type(risk: Risk) -> Dict[str, List[dict]]:
    """
    Agrupa matches por tipo, pronto para crescimento.
    Tipos esperados: SANCTIONS, PEP, WATCHLIST, ADVERSE_MEDIA.
    """
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


def _drivers(risk: Risk, score_int: int) -> List[str]:
    """
    Fatores determinantes do risco (explicação).
    Motor real pode gravar risk.risk_drivers = list[str].
    """
    drivers = getattr(risk, "risk_drivers", None)
    if isinstance(drivers, list) and drivers:
        return [str(x) for x in drivers][:10]

    grouped = _matches_by_type(risk)
    out: List[str] = []

    # Drivers por categoria
    if any(m.get("match") for m in grouped["SANÇÕES"]):
        out.append("Foram identificadas correspondências positivas em bases de dados de sanções internacionais.")
    if any(m.get("match") for m in grouped["PEP"]):
        out.append("Foram identificados indícios de exposição PEP (Pessoa Politicamente Exposta) ou relacionamento próximo.")
    if any(m.get("match") for m in grouped["MEDIA ADVERSA"]):
        out.append("Foram identificados sinais de media adversa/reputacional associados ao sujeito analisado.")
    if any(m.get("match") for m in grouped["WATCHLISTS"]):
        out.append("Foram identificadas correspondências em listas de observação/monitorização.")

    # Drivers por confiança alta
    for m in (risk.matches or []):
        if not isinstance(m, dict):
            continue
        if not m.get("match"):
            continue
        conf = m.get("confidence")
        try:
            c = float(conf) if conf is not None else 0.0
        except Exception:
            c = 0.0
        if c >= 0.80:
            out.append(
                f"Correspondência com elevada confiança ({c*100:.0f}%) na fonte {str(m.get('source','')).strip()}."
            )

    if not out:
        out.append("Não foram identificados fatores agravantes relevantes na informação disponível para este processo.")

    # Complemento por score
    nivel = classificar_risco(score_int)
    if nivel == "ALTO":
        out.append("A classificação global indica necessidade de Due Diligence reforçada e revisão humana obrigatória.")
    elif nivel == "MÉDIO":
        out.append("A classificação global indica necessidade de validações adicionais antes de decisão final.")

    # Remover duplicados preservando ordem
    seen = set()
    final = []
    for d in out:
        if d in seen:
            continue
        seen.add(d)
        final.append(d)

    return final[:12]


# =========================================================
# 4) Elementos gráficos
# =========================================================

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


# =========================================================
# 5) PDF Banco-ready (Português + motor real ready)
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
        title="Relatório de Avaliação de Risco de Compliance",
        author="Check Insurance Risk",
    )

    styles = getSampleStyleSheet()

    H1 = ParagraphStyle(
        "H1",
        parent=styles["Title"],
        fontSize=15.5,
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

    elements: List[Any] = []

    # ---------- Cabeçalho ----------
    logo = _maybe_logo()
    left = []
    if logo:
        left.append(logo)
    left.append(Paragraph("<b>CHECK INSURANCE RISK</b><br/>KYC • AML • PEP • Due Diligence", small_grey))

    header = Table(
        [[left, Paragraph("<b>Relatório de Avaliação de Risco de Compliance</b>", H1)]],
        colWidths=[70 * mm, 110 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#0A1F44")),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ]
        )
    )
    elements.append(header)
    elements.append(Spacer(1, 8))

    # ---------- Metadados ----------
    report_no = make_report_number(risk)
    score_int = _safe_int(getattr(risk, "score", 0), 0)
    nivel = classificar_risco(score_int)

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

    # ---------- Resumo Executivo ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Resumo Executivo", H2))
    resumo = (
        f"O processo avaliado apresenta classificação de risco <b>{nivel}</b>, "
        f"com score global de <b>{score_int}</b>. "
        f"{interpretar_score(score_int)}"
    )
    elements.append(Paragraph(resumo, normal))

    # ---------- Identificação do sujeito ----------
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

    # ---------- Composição do Score ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Composição do Score (Modelo Ponderado)", H2))
    factors = _risk_factors(risk)
    factor_rows = [["Fator", "Pontuação"]]
    total_calc = 0
    for k, v in factors.items():
        label = k.replace("_", " ").replace("score", "").strip().title()
        factor_rows.append([label, str(v)])
        total_calc += _safe_int(v, 0)

    factor_rows.append(["Total calculado (referência)", str(total_calc)])
    factor_rows.append(["Score final (motor)", str(score_int)])

    elements.append(_table(factor_rows, [120 * mm, 60 * mm], header=True))

    # ---------- Correspondências por tipo ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Resultados de Screening (por Categoria)", H2))

    grouped = _matches_by_type(risk)

    def render_group(title: str, items: List[dict]):
        elements.append(Paragraph(f"<b>{title}</b>", normal))
        if not items:
            elements.append(Paragraph("Sem correspondências relevantes identificadas.", small_grey))
            elements.append(Spacer(1, 4))
            return

        rows = [["Fonte", "Correspondência", "Confiança", "Detalhe"]]
        for m in items[:20]:
            match_txt = "SIM" if m.get("match") else "NÃO"
            conf_txt = ""
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

    # ---------- Fatores determinantes ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Motivos e Fatores Determinantes do Score", H2))
    for d in _drivers(risk, score_int):
        elements.append(Paragraph(f"• {d}", normal))

    # ---------- Recomendação ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Recomendação de Compliance", H2))
    rec = recomendacao_operacional(score_int).replace("\n", "<br/>")
    elements.append(Paragraph(rec, normal))

    # ---------- Metodologia ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Metodologia e Nota Legal", H2))
    metodologia = (
        "A presente avaliação foi gerada por motor automatizado de screening, com base em fontes configuradas "
        "de sanções internacionais, PEP e listas de observação. O score é produzido por modelo ponderado e "
        "configurável, sujeito a revisão institucional e validação humana. Este relatório não constitui "
        "determinação legal, devendo ser interpretado conforme as políticas internas do Banco/Seguradora."
    )
    elements.append(Paragraph(metodologia, normal))

    # ---------- Verificação Digital ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Verificação Digital do Documento", H2))

    qr = _qr_image(verify_url)

    # Quebra controlada do URL
    url_lines = simpleSplit(verify_url, normal.fontName, normal.fontSize, 120 * mm)
    url_lines = url_lines[:3]
    pretty_url = "<br/>".join(url_lines)

    vt = Table(
        [[qr, Paragraph(f"<b>Link de verificação:</b><br/>{pretty_url}", normal)]],
        colWidths=[40 * mm, 140 * mm],
    )
    vt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    elements.append(vt)

    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"<b>Hash de integridade:</b> {integrity_hash}", small_grey))
    elements.append(Paragraph(f"<b>Assinatura do sistema:</b> {server_signature}", small_grey))

    # Build com rodapé + paginação
    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)

    buffer.seek(0)
    return buffer.read()
