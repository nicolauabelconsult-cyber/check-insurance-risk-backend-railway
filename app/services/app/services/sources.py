import os
import uuid
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..db.models import InfoSource
from ..core.config import settings

def list_sources(db: Session):
    return db.scalars(select(InfoSource).order_by(InfoSource.id.desc())).all()

def get_source(db: Session, source_id: int):
    return db.get(InfoSource, source_id)

def save_upload(file_bytes: bytes, filename: str) -> str:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    safe = filename.replace("/", "_").replace("\\", "_")
    path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}_{safe}")
    with open(path, "wb") as f:
        f.write(file_bytes)
    return path

def ingest_excel(db: Session, name: str, description: str | None, file_path: str):
    row_count = None
    try:
        df = pd.read_excel(file_path)
        row_count = int(df.shape[0])
    except Exception:
        row_count = None

    src = InfoSource(name=name, description=description, file_path=file_path, row_count=row_count)
    db.add(src)
    db.commit()
    db.refresh(src)
    return src

def sample_from_source(src: InfoSource, limit: int = 10):
    df = pd.read_excel(src.file_path)
    if limit and limit > 0:
        df = df.head(limit)
    return df.where(pd.notnull(df), None).to_dict(orient="records")
