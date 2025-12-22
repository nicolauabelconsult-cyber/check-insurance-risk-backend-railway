from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException
from sqlalchemy.orm import Session

from ..db.deps import get_db
from ..schemas.sources import InfoSourceRead
from ..core.deps import require_admin
from ..services import sources as svc

router = APIRouter(prefix="/api/info-sources", tags=["info-sources"])

@router.get("", response_model=list[InfoSourceRead])
def list_sources(db: Session = Depends(get_db), _admin = Depends(require_admin)):
    return svc.list_sources(db)

@router.post("/upload-excel", status_code=201)
async def upload_excel(
    db: Session = Depends(get_db),
    _admin = Depends(require_admin),
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str | None = Form(None),
):
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx/.xls) are supported in this phase.")
    content = await file.read()
    path = svc.save_upload(content, file.filename)
    src = svc.ingest_excel(db, name=name.strip(), description=description, file_path=path)
    return {"id": src.id, "name": src.name, "row_count": src.row_count}

@router.get("/{source_id}/sample")
def sample(source_id: int, limit: int = 10, db: Session = Depends(get_db), _admin = Depends(require_admin)):
    src = svc.get_source(db, source_id)
    if not src:
        raise HTTPException(status_code=404, detail="Source not found")
    return svc.sample_from_source(src, limit=limit)
