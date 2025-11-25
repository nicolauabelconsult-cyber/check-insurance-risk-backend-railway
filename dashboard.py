# app/dashboard.py
from datetime import datetime, date

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .auth import get_current_active_user
from .database import get_db
from .models import RiskRecord, RiskLevel, User
from .schemas import DashboardStats, RiskHistoryItem

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    today = date.today()
    total_hoje = (
        db.query(func.count(RiskRecord.id))
        .filter(func.date(RiskRecord.created_at) == today)
        .scalar()
        or 0
    )

    casos_altos = (
        db.query(func.count(RiskRecord.id))
        .filter(RiskRecord.level.in_([RiskLevel.HIGH.value, RiskLevel.CRITICAL.value]))
        .scalar()
        or 0
    )

    tempo_medio = 0.0  # se houver timestamps de fim de análise podemos calcular melhor

    ultimas = (
        db.query(RiskRecord)
        .order_by(RiskRecord.created_at.desc())
        .limit(10)
        .all()
    )

    ultimas_items: list[RiskHistoryItem] = []
    for r in ultimas:
        ultimas_items.append(
            RiskHistoryItem(
                analysis_id=r.id,
                data=r.created_at,
                nome=r.full_name,
                score=r.score,
                nivel=RiskLevel(r.level),
                decisao=RiskDecision(r.decision) if r.decision else None,  # type: ignore
            )
        )

    return DashboardStats(
        total_analises_hoje=total_hoje,
        casos_high_critical=casos_altos,
        tempo_medio_analise_segundos=tempo_medio,
        ultimas_analises=ultimas_items,
    )
