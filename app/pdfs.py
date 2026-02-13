from __future__ import annotations

from datetime import datetime
from io import BytesIO
import hashlib
import os
from typing import Any

import qrcode

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

from app.settings import settings
from app.models import Risk


# -----------------------------
# Helpers (institucional/banco)
# -----------------------------

def score_to_level(score: int) -> str:
    # Ajusta thresholds conforme política
    if score >= 70:
        return "ALTO"
    if score >= 40:
        return "MÉDIO"
    return "BAIXO"


def score_interpretation_pt(score: int) -> str:
    lvl = score_to_level(score)
    if lvl == "ALTO":
        return "Acima do limiar institucional. Recomenda-se diligência reforçada (EDD)."
    if lvl == "MÉDIO":
        return "Risco moderado. Podem ser necessárias verificações adicionais e condições."
    return "Risco baixo. Recomenda-se monitorização padrão conforme política interna."


def make_integrity_hash(risk: Risk) -> str:
    # Determinístico: não usar campos voláteis
    raw = f"{risk.id}|{risk.entity_id}|{risk.score}|{getattr(risk.status, 'value', risk.status)}|{risk.created_at}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_server_signature(integrity_hash: str) -> str:
    # “Assinatura digital simplificada”: hash + segredo servidor
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
    """
    Opcional: coloca logo se existir.
    Define em env: PDF_LOGO_PATH=/opt/render/project/src/app/assets/logo.png
    """
    path = getattr(settings, "PDF_LOGO_PATH", None) or os.getenv("PDF_LOGO_PATH")
    if not path:
        return None
    if not os.path.exists(path):
        return None
    return Image(path, width=22 * mm, height=22 * mm)


def _footer(c: rl_canvas.Canvas, doc):
    c.saveState()
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)

    c.drawString(18 * mm, 12 * mm, "Documento confidencial. Distribuição não autorizada é proibida.")
    c.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Página {doc.page}")

    c.restoreState()


def _fmt_pct(x: Any) -> str:
    if x is None:
        return "-"
    if isinstance(x, (int, float)) and x <= 1:
        return f"{x * 100:.0f}%"
    return str(x)


def _safe_int(x: Any) -> int:
    try:
        return int(x or 0)
    except Exception:
        return 0


# ---------------------------------
# Main: PDF Institucional (PT)
# ---------------------------------

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
        title="Check Insurance Risk - Relatório de Avaliação",
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

    header_table = Table([[header_left, Paragraph("<b>Relatório de Avaliação</b>", H1)]], colWidths=[70 * mm, 110 * mm])
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

    # ---------- Meta ----------
    report_no = make_report_number(risk)
    score_int = _safe_int(getattr(risk, "score", 0))
    risk_level = score_to_level(score_int)

    app_version = getattr(settings, "APP_VERSION", "v1.0")
    app_env = getattr(settings, "APP_ENV", "Production")
    system_version = f"{app_version} ({app_env})"

    meta = [
        ["Nº do Relatório", report_no],
        ["Risk ID", str(risk.id)],
        ["Entity ID", str(risk.entity_id)],
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

    # ---------- Visão Geral ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("1. Visão Geral do Risco (KYC/AML/PEP)", H2))

    overview = [
        ["Nome consultado", risk.query_name or ""],
        ["Nacionalidade", risk.query_nationality or ""],
        ["BI", risk.query_bi or ""],
        ["Passaporte", risk.query_passport or ""],
        ["Estado", getattr(risk.status, "value", str(risk.status))],
        ["Score", str(risk.score)],
        ["Nível de risco", risk_level],
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

    # ---------- Matches ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("2. Resultados de Triagem (Sanções/PEP/Watchlists)", H2))

    matches = risk.matches or []
    if not matches:
        elements.append(Paragraph("Sem correspondências reportadas pelo motor de triagem.", normal))
    else:
        rows = [["Fonte", "Match", "Confiança", "Observação"]]
        for m in matches:
            conf = ""
            if m.get("confidence") is not None:
                try:
                    conf = f"{float(m.get('confidence', 0)) * 100:.0f}%"
                except Exception:
                    conf = str(m.get("confidence"))
            rows.append(
                [
                    str(m.get("source", "")),
                    "SIM" if m.get("match") else "NÃO",
                    conf,
                    str(m.get("note", "")),
                ]
            )
        mt = Table(rows, colWidths=[35 * mm, 18 * mm, 25 * mm, 102 * mm])
        mt.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1F44")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ]
            )
        )
        elements.append(mt)

    # ---------- Sumário ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("3. Sumário da Avaliação (Narrativa)", H2))
    elements.append(Paragraph((risk.summary or "-"), normal))

    # ---------- Underwriting ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("4. Decisão de Subscrição (Seguro)", H2))

    uw_score = getattr(risk, "uw_score", None)
    uw_decision = getattr(risk, "uw_decision", None)
    uw_summary = getattr(risk, "uw_summary", None)
    uw_kpis = getattr(risk, "uw_kpis", None) or {}
    uw_factors = getattr(risk, "uw_factors", None) or []

    if uw_score is None:
        elements.append(
            Paragraph(
                "Sem dados de subscrição disponíveis neste registo (histórico de pagamentos/sinistros/apólices não encontrado).",
                normal,
            )
        )
    else:
        decision_table = Table(
            [
                ["Score Underwriting (0-100)", str(uw_score)],
                ["Recomendação", uw_decision or "-"],
                ["Resumo Executivo", uw_summary or "-"],
            ],
            colWidths=[55 * mm, 125 * mm],
        )
        decision_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(decision_table)

        # KPIs
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("4.1 Indicadores-Chave (KPIs)", H2))

        pagamentos = uw_kpis.get("pagamentos", {})
        sinistros = uw_kpis.get("sinistros", {})
        apolices = uw_kpis.get("apolices", {})
        cancelamentos = uw_kpis.get("cancelamentos", {})
        fraude = uw_kpis.get("fraude", {})

        kpi_rows = [
            ["Pagamentos",
             f"Taxa pagamento: {_fmt_pct(pagamentos.get('taxa_pagamento'))} | "
             f"Em aberto: {pagamentos.get('faturas_em_aberto', '-') } | "
             f"Atraso médio (dias): {pagamentos.get('atraso_medio_dias', '-') }"],
            ["Sinistros",
             f"Total: {sinistros.get('total_sinistros', '-') } | "
             f"Pago: {sinistros.get('valor_pago_total', '-') } | "
             f"Reservado: {sinistros.get('valor_reservado_total', '-') }"],
            ["Apólices",
             f"Ativas: {apolices.get('apolices_ativas', '-') } | "
             f"Soma segurada total: {apolices.get('soma_segurada_total', '-') } | "
             f"Prémio total: {apolices.get('premio_total', '-') }"],
            ["Cancelamentos", f"Total: {cancelamentos.get('total_cancelamentos', '-') }"],
            ["Fraude", f"Flags: {fraude.get('total_flags', '-') } | HIGH: {fraude.get('flags_high', '-') }"],
        ]

        kpi_table = Table(kpi_rows, colWidths=[35 * mm, 145 * mm])
        kpi_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(kpi_table)

        # Fatores
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("4.2 Motivos do Score (Fatores de Decisão)", H2))

        if not uw_factors:
            elements.append(Paragraph("Sem fatores registados.", normal))
        else:
            rows = [["Categoria", "Peso", "Motivo"]]
            for f in uw_factors[:25]:
                rows.append([str(f.get("categoria", "")), str(f.get("peso", "")), str(f.get("motivo", ""))])

            ft = Table(rows, colWidths=[30 * mm, 15 * mm, 135 * mm])
            ft.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1F44")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ]
                )
            )
            elements.append(ft)

    # ---------- Metodologia ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("5. Metodologia e Nota Legal", H2))
    methodology = (
        "Este relatório resulta de um processo automatizado de triagem (KYC/AML/PEP) e de um modelo "
        "de apoio à subscrição (underwriting) com base em dados disponíveis (pagamentos, sinistros, apólices, "
        "cancelamentos e flags). O score é indicativo e não constitui decisão legal. A instituição deve aplicar "
        "políticas internas, revisão humana e diligência reforçada quando aplicável."
    )
    elements.append(Paragraph(methodology, normal))

    # ---------- Verificação ----------
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("6. Verificação do Documento", H2))

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

    # Build com rodapé
    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)

    buffer.seek(0)
    return buffer.read()
