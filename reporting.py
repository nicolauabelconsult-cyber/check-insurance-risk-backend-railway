# reporting.py
from datetime import datetime
from io import BytesIO

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from openpyxl import Workbook

from models import RiskRecord, User


def generate_risk_pdf(db: Session, record: RiskRecord) -> StreamingResponse:
    """
    AQUI fica a tua implementação actual de PDF com reportlab.
    Se já tens essa parte a funcionar, mantém como estava.
    Não mexo nela agora para não estragar nada.
    """
    # 👉 Usa o código que já tinhas antes para o PDF.
    raise NotImplementedError("Implementa aqui a geração de PDF como já tinhas.")
    # (Se já tens implementado, apaga esta linha e cola o teu código antigo)


def export_risk_excel(db: Session) -> StreamingResponse:
    """
    Exporta todos os registos de risco em formato .xlsx usando openpyxl
    (sem pandas, para evitar problemas de build no Render).
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Análises de Risco"

    # Cabeçalho
    headers = [
        "ID",
        "Data Análise",
        "Nome",
        "NIF",
        "Passaporte",
        "Cartão Residente",
        "País",
        "Score",
        "Nível",
        "Decisão",
        "Analista",
    ]
    ws.append(headers)

    # Dados
    records = (
        db.query(RiskRecord)
        .order_by(RiskRecord.created_at.desc())
        .all()
    )

    for r in records:
        analyst_name = r.analyst.username if isinstance(r.analyst, User) else None
        ws.append(
            [
                r.id,
                r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
                r.full_name,
                r.nif or "",
                r.passport or "",
                r.resident_card or "",
                r.country or "",
                r.score,
                r.level,
                r.decision or "",
                analyst_name or "",
            ]
        )

    # Guardar em memória
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    filename = f"check_insurance_risk_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
