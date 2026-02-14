from __future__ import annotations

from datetime import datetime
from io import BytesIO
import hashlib
import os

import qrcode

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

from app.settings import settings
from app.models import Risk


# -----------------------------
# Helpers: semântica institucional
# -----------------------------

def score_to_level(score: int) -> str:
    # Ajusta thresholds conforme política do banco/seguradora
    if score >= 70:
        return "ALTO"
    if score >= 40:
        return "MÉDIO"
    return "BAIXO"


def score_interpretation_pt(score: int) -> str:
    nivel = score_to_level(score)
    if nivel == "ALTO":
        return "Acima do limiar institucional. Recomenda-se diligência reforçada (EDD) e validação humana."
    if nivel == "MÉDIO":
        return "Risco moderado. Podem ser necessários controlos adicionais e validação documental."
    return "Baixo risco. Monitorização padrão recomendada."


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
    if not path:
        return None
    if not os.path.exists(path):
        return None
    return Image(path, width=22 * mm, height=22 * mm)


def _footer(c: canvas.Canvas, doc):
    c.saveState()
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)

    c.drawString(18 * mm, 12 * mm, "Documento confidencial. Distribuição não autorizada é proibida.")
    c.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Página {doc.page}")

    c.restoreState()


# -----------------------------
# Extração “bank-ready” do conteúdo
# -----------------------------

def _extract_score_int(risk: Risk) -> int:
    try:
        return int(str(risk.score))
    except Exception:
        return 0


def _motivos_score_pt(risk: Risk) -> list[dict]:
    """
    Preparado para motor real:
    - Hoje tenta inferir motivos com base em matches.
    - Amanhã o motor pode preencher risk.matches com 'reason_codes', 'categories', etc.
    Retorna lista de itens: {categoria, motivo, impacto}
    """
    motivos: list[dict] = []

    matches = risk.matches or []
    for m in matches:
        src = str(m.get("source", "")).strip() or "Fonte"
        match = bool(m.get("match", False))
        conf = m.get("confidence", None)
        note = str(m.get("note", "")).strip()

        if not match:
            continue

        cat = "Conformidade"
        # Heurística simples: se a fonte contém “PEP”, categoriza como PEP
        if "pep" in src.lower():
            cat = "PEP (Pessoa Politicamente Exposta)"
        if "san" in src.lower():
            cat = "Sanções"
        if "watch" in src.lower() or "lista" in src.lower():
            cat = "Watchlist"

        impacto = "Elevado" if (isinstance(conf, (int, float)) and conf >= 0.8) else "Moderado"
        motivo_txt = note or f"Correspondência positiva em {src}."

        motivos.append(
            {
                "categoria": cat,
                "motivo": motivo_txt,
                "impacto": impacto,
                "confianca": f"{float(conf) * 100:.0f}%" if isinstance(conf, (int, float)) else "",
                "fonte": src,
            }
        )

    if not motivos:
        motivos.append(
            {
                "categoria": "Sem alertas relevantes",
                "motivo": "Não foram identificadas correspondências positivas nas fontes activas no momento.",
                "impacto": "N/A",
                "confianca": "",
                "fonte": "",
            }
        )

    return motivos


def _secao_decisao_apolice_placeholder(risk: Risk) -> dict:
    """
    Preparado para Underwriting (Excel → DB → KPIs).
    Hoje é placeholder, mas com campos estáveis para o futuro.
    """
    score = _extract_score_int(risk)
    nivel = score_to_level(score)

    if nivel == "ALTO":
        decisao = "NÃO APROVAR AUTOMATICAMENTE"
        recomendacao = (
            "Encaminhar para revisão manual (Compliance + Underwriting). "
            "Solicitar documentação adicional e aplicar diligência reforçada."
        )
        condicoes = ["Revisão manual obrigatória", "EDD", "Validação de beneficiário efectivo (se aplicável)"]
    elif nivel == "MÉDIO":
        decisao = "APROVAR COM CONDIÇÕES"
        recomendacao = (
            "Aprovar sob condições: validação documental, confirmação de identidade e monitorização reforçada."
        )
        condicoes = ["Validação documental", "Monitorização reforçada por período definido"]
    else:
        decisao = "APROVAR"
        recomendacao = "Aprovação recomendada com monitorização padrão."
        condicoes = ["Monitorização padrão"]

    return {
        "decisao": decisao,
        "recomendacao": recomendacao,
        "condicoes": condicoes,
        "nota_futuro": "Quando o serviço de Underwriting estiver activo, esta secção incluirá histórico de sinistros, pagamentos e apólices activas.",
    }


# -----------------------------
# PDF principal (PT)
# -----------------------------

def build_risk_pdf_institutional_pt(
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
        title="Check Insurance Risk - Relatório de Risco",
        author="Check Insurance Risk",
    )

    styles = getSampleStyleSheet()

    H1 = ParagraphStyle(
        "H1",
        parent=styles["Title"],
        fontSize=16,
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
    normal = ParagraphStyle("N", parent=styles["Normal"], fontSize=9, leading=12)
    small_grey = ParagraphStyle("SG", parent=styles["Normal"], fontSize=7.8, textColor=colors.grey, leading=10)

    elements = []

    # ---------- Header ----------
    logo = _maybe_logo()
    header_left = []
    if logo:
        header_left.append(logo)
    header_left.append(Paragraph("<b>CHECK INSURANCE RISK</b><br/>KYC • AML • PEP • Due Diligence", small_grey))

    header_table = Table(
        [[header_left, Paragraph("<b>Relatório Institucional de Risco</b>", H1)]],
        colWidths=[70 * mm, 110 * mm],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#0A1F44")),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 8))

    # ---------- Metadados ----------
    report_no = make_report_number(risk)
    score_int = _extract_score_int(risk)
    nivel = score_to_level(score_int)

    app_version = getattr(settings, "APP_VERSION", "v1.0")
    app_env = getattr(settings, "APP_ENV", "Production")
    system_version = f"{app_version} ({app_env})"

    meta = [
        ["Nº do Relatório", report_no],
        ["ID do Risco", str(risk.id)],
        ["Entidade", str(risk.entity_id)],
        ["Analista", analyst_name],
        ["Gerado em (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S")],
        ["Versão do Sistema", system_version],
    ]
    meta_table = Table(meta, colWidths=[45 * mm, 135 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(meta_table)

    # ---------- Resumo ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("1. Identificação e Resumo", H2))

    overview = [
        ["Nome pesquisado", risk.query_name or ""],
        ["Nacionalidade", risk.query_nationality or ""],
        ["BI", risk.query_bi or ""],
        ["Passaporte", risk.query_passport or ""],
        ["Estado", getattr(risk.status, "value", str(risk.status))],
        ["Score", str(risk.score)],
        ["Nível de Risco", nivel],
        ["Interpretação", score_interpretation_pt(score_int)],
    ]
    ov_table = Table(overview, colWidths=[45 * mm, 135 * mm])
    ov_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(ov_table)

    # ---------- Motivos do Score ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("2. Motivos do Score (explicabilidade)", H2))

    motivos = _motivos_score_pt(risk)
    rows = [["Categoria", "Motivo", "Impacto", "Confiança", "Fonte"]]
    for item in motivos:
        rows.append(
            [
                item.get("categoria", ""),
                item.get("motivo", ""),
                item.get("impacto", ""),
                item.get("confianca", ""),
                item.get("fonte", ""),
            ]
        )

    mt = Table(rows, colWidths=[38 * mm, 72 * mm, 20 * mm, 18 * mm, 32 * mm])
    mt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1F44")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("FONTSIZE", (0, 0), (-1, -1), 8.2),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(mt)

    # ---------- Correspondências ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("3. Correspondências Detalhadas (matches)", H2))

    matches = risk.matches or []
    if not matches:
        elements.append(Paragraph("Não foram reportadas correspondências pelo motor de triagem.", normal))
    else:
        rows2 = [["Fonte", "Match", "Confiança", "Notas"]]
        for m in matches:
            conf = ""
            if m.get("confidence") is not None:
                try:
                    conf = f"{float(m.get('confidence', 0)) * 100:.0f}%"
                except Exception:
                    conf = str(m.get("confidence"))
            rows2.append(
                [
                    str(m.get("source", "")),
                    "SIM" if m.get("match") else "NÃO",
                    conf,
                    str(m.get("note", "")),
                ]
            )
        tab = Table(rows2, colWidths=[40 * mm, 15 * mm, 22 * mm, 103 * mm])
        tab.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1F44")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        elements.append(tab)

    # ---------- Sumário narrativo ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("4. Sumário da Avaliação", H2))
    elements.append(Paragraph(risk.summary or "-", normal))

    # ---------- Decisão para Apólice (placeholder underwriting) ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("5. Apoio à Decisão de Apólice (Underwriting)", H2))

    uw = _secao_decisao_apolice_placeholder(risk)
    elements.append(Paragraph(f"<b>Decisão sugerida:</b> {uw['decisao']}", normal))
    elements.append(Paragraph(f"<b>Recomendação:</b> {uw['recomendacao']}", normal))
    elements.append(Spacer(1, 4))
    conds = "<br/>".join([f"• {c}" for c in uw["condicoes"]])
    elements.append(Paragraph(f"<b>Condições:</b><br/>{conds}", normal))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(f"<i>{uw['nota_futuro']}</i>", small_grey))

    # ---------- Metodologia ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("6. Metodologia e Nota Legal", H2))
    methodology = (
        "Este relatório é gerado por processo automatizado de triagem e análise com base nas fontes activas "
        "(PEP/Sanções/Watchlists) e regras internas. O score é indicativo e não constitui decisão legal. "
        "A instituição deve aplicar políticas internas, revisão humana e diligência reforçada quando aplicável."
    )
    elements.append(Paragraph(methodology, normal))

    # ---------- Verificação ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("7. Verificação Pública do Documento", H2))

    qr = _qr_image(verify_url)
    url_lines = simpleSplit(verify_url, normal.fontName, normal.fontSize, 120 * mm)
    url_lines = url_lines[:3]
    pretty_url = "<br/>".join(url_lines)

    ver_table = Table([[qr, Paragraph(f"<b>URL de verificação:</b><br/>{pretty_url}", normal)]], colWidths=[40 * mm, 140 * mm])
    ver_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    elements.append(ver_table)

    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"<b>Hash de Integridade:</b> {integrity_hash}", small_grey))
    elements.append(Paragraph(f"<b>Assinatura do Servidor:</b> {server_signature}", small_grey))

    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)

    buffer.seek(0)
    return buffer.read()
