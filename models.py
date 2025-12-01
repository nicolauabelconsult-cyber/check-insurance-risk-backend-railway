# info_sources.py
"""
Gestão das Fontes de Informação (InfoSource) e importação de bases Excel
sem usar pandas, apenas openpyxl.

Funcionalidades:
- GET  /api/info-sources/               -> listar fontes
- POST /api/info-sources/upload-excel   -> importar ficheiro Excel e criar NormalizedEntity
- GET  /api/info-sources/{id}/sample    -> amostra de entidades (para debug / frontend)
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

# -------------------------------------------------------------------------
# Helpers internos
# -------------------------------------------------------------------------


def _require_excel(filename: str) -> None:
    """Garante que o ficheiro tem extensão Excel simples (.xlsx)."""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O ficheiro deve ser um Excel .xlsx",
        )


def _get_col_idx(headers: list[str], name: str) -> Optional[int]:
    """
    Procura o índice de uma coluna, ignorando maiúsculas/minúsculas
    e espaços. Por exemplo 'NIF', 'nif', ' Nif ' são equivalentes.
    """
    name_norm = name.strip().lower()
    for idx, h in enumerate(headers):
        if not h:
            continue
        h_norm = str(h).strip().lower()
        if h_norm == name_norm:
            return idx
    return None


def _str_or_none(value) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip()
    return v or None


# -------------------------------------------------------------------------
# 1) Listar fontes
# -------------------------------------------------------------------------


@router.get("/", response_model=List[InfoSourceRead])
def list_info_sources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[InfoSourceRead]:
    """
    Lista todas as fontes de informação registadas.
    """
    sources = db.query(InfoSource).order_by(InfoSource.created_at.desc()).all()
    return sources


# -------------------------------------------------------------------------
# 2) Upload de Excel
# -------------------------------------------------------------------------


@router.post("/upload-excel")
async def upload_info_source_excel(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Importa um ficheiro Excel (.xlsx) e cria:
    - um registo em InfoSource
    - vários registos em NormalizedEntity

    Regras do template:
    - Primeira linha = cabeçalhos.
    - Colunas esperadas (nomes simples, sem acentos):

        name           -> Nome / Nome completo
        nif            -> NIF / Número de contribuinte
        passport       -> Passaporte
        resident_card  -> Cartão de residente
        country        -> País / Nacionalidade (ex.: AO, PT)

    Se alguma coluna não existir, é simplesmente ignorada.
    """

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ficheiro inválido.",
        )

    _require_excel(file.filename)

    # Ler conteúdo em memória
    content = await file.read()
    try:
        wb = load_workbook(BytesIO(content), read_only=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não foi possível ler o ficheiro Excel: {exc}",
        )

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O ficheiro está vazio.",
        )

    # Cabeçalhos
    raw_headers = rows[0]
    headers = [str(h).strip() if h is not None else "" for h in raw_headers]

    idx_name = _get_col_idx(headers, "name")
    idx_nif = _get_col_idx(headers, "nif")
    idx_passport = _get_col_idx(headers, "passport")
    idx_res_card = _get_col_idx(headers, "resident_card")
    idx_country = _get_col_idx(headers, "country")

    if idx_name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A coluna 'name' é obrigatória no Excel.",
        )

    # Criar registo da fonte
    source = InfoSource(
        name=name,
        description=description,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    # Criar entidades normalizadas
    created = 0
    for row in rows[1:]:
        if not row or all(v is None for v in row):
            continue

        full_name = _str_or_none(row[idx_name]) if idx_name is not None else None
        if not full_name:
            continue

        entity = NormalizedEntity(
            name=full_name,
            normalized_name=full_name.strip().upper(),
            nif=_str_or_none(row[idx_nif]) if idx_nif is not None else None,
            passport=_str_or_none(row[idx_passport]) if idx_passport is not None else None,
            resident_card=_str_or_none(row[idx_res_card]) if idx_res_card is not None else None,
            country=_str_or_none(row[idx_country]).upper()
            if idx_country is not None and _str_or_none(row[idx_country])
            else None,
            info_source_id=source.id,
        )
        db.add(entity)
        created += 1

    db.commit()

    return {
        "message": "Ficheiro importado com sucesso.",
        "source_id": source.id,
        "registos_importados": created,
    }


# -------------------------------------------------------------------------
# 3) Amostra de entidades de uma fonte (para debug / frontend)
# -------------------------------------------------------------------------


@router.get("/{source_id}/sample")
def sample_entities(
    source_id: int,
    limit: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Devolve uma pequena amostra de entidades de uma fonte específica.
    Útil para o frontend mostrar os primeiros registos importados.
    """
    source = db.query(InfoSource).filter(InfoSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Fonte não encontrada.")

    entities = (
        db.query(NormalizedEntity)
        .filter(NormalizedEntity.info_source_id == source_id)
        .order_by(NormalizedEntity.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "source": {
            "id": source.id,
            "name": source.name,
            "description": source.description,
            "created_at": source.created_at,
        },
        "sample": [
            {
                "id": e.id,
                "name": e.name,
                "normalized_name": e.normalized_name,
                "nif": e.nif,
                "passport": e.passport,
                "resident_card": e.resident_card,
                "country": e.country,
            }
            for e in entities
        ],
    }
