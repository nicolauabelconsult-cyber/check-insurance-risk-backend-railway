from __future__ import annotations

from datetime import datetime
import hashlib
import hmac
from typing import Any, Optional

from app.settings import settings

# Imports leves aqui.
# Evita importar routers ou "main" neste módulo para não criar ciclos.


def make_integrity_hash(risk: Any) -> str:
    """
    Gera um hash determinístico a partir dos campos principais do Risk.
    Usa SHA256. Não depende de DB nem de routers.
    """
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
    """
    Assinatura simplificada do servidor (HMAC-SHA256) para validação externa.
    Requer PDF_SIGNING_SECRET em settings (ou usa JWT_SECRET como fallback).
    """
    secret = getattr(settings, "PDF_SIGNING_SECRET", None) or getattr(settings, "JWT_SECRET", "")
    if not secret:
        # Falha explícita ajuda a diagnosticar envs mal configurados
        raise RuntimeError("Missing PDF_SIGNING_SECRET/JWT_SECRET in settings")
    sig = hmac.new(secret.encode("utf-8"), integrity_hash.encode("utf-8"), hashlib.sha256).hexdigest()
    return sig


def build_risk_pdf_institutional(
    risk: Any,
    analyst_name: str,
    generated_at: datetime,
    integrity_hash: str,
    server_signature: str,
    verify_url: str,
) -> bytes:
    """
    PDF institucional (PT) "bank-level".
    Mantém dependências encapsuladas: reportlab só é importado dentro da função
    para reduzir risco de crash no boot e evitar ciclos.
    """
    # Import local para reduzir risco no startup
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    # Se tiveres qrcode, tenta usar; se não, segue sem QR.
    try:
        import qrcode  # type: ignore
    except Exception:
        qrcode = None  # type: ignore

    from io import BytesIO

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    # Header
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, height - 20 * mm, "CHECK INSURANCE RISK")
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, height - 27 * mm, "Relatório Institucional de Risco (versão institucional)")

    # Meta
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, height - 37 * mm, f"Gerado em: {generated_at.isoformat()} UTC")
    c.drawString(20 * mm, height - 42 * mm, f"Analista: {analyst_name}")
    c.drawString(20 * mm, height - 47 * mm, f"Risk ID: {getattr(risk, 'id', '')}")
    c.drawString(20 * mm, height - 52 * mm, f"Entidade: {getattr(risk, 'entity_id', '')}")

    # Core summary
    y = height - 65 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, y, "1) Identificação")
    y -= 7 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Nome: {getattr(risk, 'query_name', '')}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Nacionalidade: {getattr(risk, 'query_nationality', '')}")
    y -= 6 * mm
    bi = getattr(risk, "query_bi", None)
    passport = getattr(risk, "query_passport", None)
    if bi:
        c.drawString(20 * mm, y, f"BI: {bi}")
        y -= 6 * mm
    if passport:
        c.drawString(20 * mm, y, f"Passaporte: {passport}")
        y -= 6 * mm

    # Compliance section
    y -= 4 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, y, "2) Compliance")
    y -= 7 * mm
    c.setFont("Helvetica", 10)
    matches = getattr(risk, "matches", None) or []
    c.drawString(20 * mm, y, f"Correspondências: {len(matches)}")
    y -= 6 * mm
    summary = getattr(risk, "summary", "") or ""
    c.drawString(20 * mm, y, f"Resumo: {summary[:110]}")
    y -= 6 * mm

    # Underwriting / scoring
    y -= 4 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, y, "3) Underwriting / Score")
    y -= 7 * mm
    c.setFont("Helvetica", 10)
    score = getattr(risk, "score", "") or ""
    c.drawString(20 * mm, y, f"Score: {score}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Decisão recomendada: Revisão conforme score e evidências.")
    y -= 10 * mm

    # Integrity block
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, "4) Integridade & Verificação")
    y -= 6 * mm
    c.setFont("Helvetica", 8)
    c.drawString(20 * mm, y, f"Hash: {integrity_hash}")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Assinatura do servidor: {server_signature}")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Verificação: {verify_url}")

    # QR (se disponível)
    if qrcode is not None:
        try:
            qr_img = qrcode.make(verify_url)
            qr_buf = BytesIO()
            qr_img.save(qr_buf, format="PNG")
            qr_buf.seek(0)
            c.drawInlineImage(qr_buf, width - 45 * mm, height - 55 * mm, 30 * mm, 30 * mm)
        except Exception:
            pass

    # Footer
    c.setFont("Helvetica", 7)
    c.drawString(20 * mm, 12 * mm, "Confidencial. Uso exclusivo institucional.")
    c.showPage()
    c.save()

    return buf.getvalue()


# Alias opcional para compatibilidade (se algum endpoint ainda chamar _pt)
def build_risk_pdf_institutional_pt(*args, **kwargs) -> bytes:
    return build_risk_pdf_institutional(*args, **kwargs)
