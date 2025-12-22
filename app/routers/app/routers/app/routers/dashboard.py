from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db.deps import get_db
from ..core.deps import get_current_user
from ..schemas.dashboard import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/stats", response_model=DashboardStats)
def stats(_user = Depends(get_current_user), db: Session = Depends(get_db)):
    return DashboardStats(
        total_clients=None,
        total_analyses=None,
        high_risk=None,
        medium_risk=None,
        low_risk=None,
        critical_risk=None,
    )
