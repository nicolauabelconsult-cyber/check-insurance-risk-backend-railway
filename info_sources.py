"""
info_sources.py
Gestão das Fontes de Informação (InfoSource) e importação de bases Excel
sem usar pandas, apenas openpyxl.
"""

from typing import List, Optional
from io import BytesIO

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
)
from sqlalchemy.orm import Session
from openpyxl import load_workbook

from database import get_db
from models import InfoSource, NormalizedEntity, User
from schemas import InfoSourceRead
from auth import get_current_active_user, get_current_admin


router = APIRouter(prefix="/info-sources", tags=["Info Sources"])


@router.get("/", response_model=List[InfoSourceRead])
def list_sources(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_admin)
):
    sources = db.query(InfoSource).order_by(InfoSource.created_at.desc()).all()
    return sources


@router.post("/upload", response_model=InfoSourceRead, status_code=status.HTTP_201_CREATED)
async def upload_source(
    name: str = Form(...),
    type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    if type not in RISK_WEIGHTS:
        raise HTTPException(status_code=400, detail="Tipo de fonte inválido.")

    try:
        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(file.file)
        elif file.filename.lower().endswith((".xls", ".xlsx")):
            df = pd.read_excel(file.file)
        else:
            raise HTTPException(status_code=400, detail="Formato de ficheiro não suportado.")
    except Exception:
        raise HTTPException(status_code=400, detail="Erro ao ler o ficheiro.")

    source = InfoSource(
        name=name,
        type=type,
        created_by_id=current_user.id,
    )
    db.add(source)
    db.flush()  # para ter source.id

    weight = RISK_WEIGHTS[type]

    # Esperado: colunas Nome, NIF, Passaporte, CartaoResidente, Nacionalidade, Cargo
    count = 0
    for _, row in df.iterrows():
        entity = NormalizedEntity(
            source_id=source.id,
            source_type=type,
            source_risk_weight=weight,
            full_name_norm=normalize_text(str(row.get("Nome", ""))),
            nif_norm=normalize_text(str(row.get("NIF", ""))) if row.get("NIF") else None,
            passport_norm=normalize_text(str(row.get("Passaporte", "")))
            if row.get("Passaporte")
            else None,
            resident_card_norm=normalize_text(str(row.get("CartaoResidente", "")))
            if row.get("CartaoResidente")
            else None,
            country_code=str(row.get("Nacionalidade", "")).upper() or None,
            role_or_position=row.get("Cargo") or None,
            extra_data=row.to_dict(),
        )
        db.add(entity)
        count += 1

    source.records_count = count
    db.commit()
    db.refresh(source)
    return source
