from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case, cast, Date

from app.db import get_db
from app.deps import require_perm
from app.models import Risk, User, UserRole
from app.audit import log

router = APIRouter(prefix="/admin", tags=["admin"])


def _score_band_expr():
    # score é string no teu model, então fazemos cast para int com segurança:
    score_int = cast(Risk.score, func.INTEGER)
    return case(
        (score_int >= 80, "ALTO"),
        (score_int >= 60, "MÉDIO"),
        else_="BAIXO",
    )


@router.get("/dashboard")
def admin_dashboard(
    days: int = 30,
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("admin:dashboard")),
):
    # Safety: limita days
    days = max(7, min(days, 120))

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    q = db.query(Risk)

    # SUPER_ADMIN vê tudo. ADMIN (sem entity_id) tipicamente também.
    # Se o teu ADMIN tiver entity_id e queres “admin por entidade”, descomenta:
    # if u.role == UserRole.ADMIN and u.entity_id:
    #     q = q.filter(Risk.entity_id == u.entity_id)

    total = q.count()

    total_7d = q.filter(Risk.created_at >= (now - timedelta(days=7))).count()
    total_30d = q.filter(Risk.created_at >= (now - timedelta(days=30))).count()

    # Por status
    by_status_rows = (
        q.with_entities(Risk.status, func.count(Risk.id))
        .group_by(Risk.status)
        .all()
    )
    by_status = {str(s): int(c) for s, c in by_status_rows}

    # Por banda (ALTO/MÉDIO/BAIXO)
    band_expr = _score_band_expr()
    by_band_rows = (
        q.filter(Risk.score.isnot(None))
        .with_entities(band_expr.label("band"), func.count(Risk.id))
        .group_by("band")
        .all()
    )
    by_band = {str(b): int(c) for b, c in by_band_rows}

    # Série riscos por dia (últimos N dias)
    per_day_rows = (
        q.filter(Risk.created_at >= start)
        .with_entities(cast(Risk.created_at, Date).label("d"), func.count(Risk.id))
        .group_by("d")
        .order_by("d")
        .all()
    )

    # Série score médio por dia
    # cast string->int e faz avg
    score_int = cast(Risk.score, func.INTEGER)
    avg_score_rows = (
        q.filter(Risk.created_at >= start)
        .filter(Risk.score.isnot(None))
        .with_entities(cast(Risk.created_at, Date).label("d"), func.avg(score_int))
        .group_by("d")
        .order_by("d")
        .all()
    )

    per_day_map = {str(d): int(c) for d, c in per_day_rows}
    avg_map = {str(d): float(a or 0) for d, a in avg_score_rows}

    # Preenche dias faltantes (para o gráfico ficar “liso”)
    series = []
    for i in range(days):
        d = (start.date() + timedelta(days=i))
        key = str(d)
        series.append({
            "date": key,
            "risks": per_day_map.get(key, 0),
            "avgScore": round(avg_map.get(key, 0.0), 2),
        })

    # Top entidades (só para SUPER_ADMIN)
    top_entities = []
    if u.role == UserRole.SUPER_ADMIN:
        top_rows = (
            db.query(Risk.entity_id, func.count(Risk.id))
            .group_by(Risk.entity_id)
            .order_by(func.count(Risk.id).desc())
            .limit(10)
            .all()
        )
        top_entities = [{"entity_id": e, "count": int(c)} for e, c in top_rows]

    # Últimos riscos
    last = (
        q.order_by(Risk.created_at.desc())
        .limit(10)
        .all()
    )
    last_items = [
        {
            "id": r.id,
            "entity_id": r.entity_id,
            "name": r.query_name,
            "score": r.score,
            "status": str(r.status),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in last
    ]

    log(db, "DASHBOARD_VIEW", actor=u, entity=None, target_ref="admin/dashboard", meta={"days": days})

    return {
        "kpis": {
            "total": total,
            "last7d": total_7d,
            "last30d": total_30d,
        },
        "byStatus": by_status,
        "byBand": by_band,
        "series": series,
        "topEntities": top_entities,
        "lastRisks": last_items,
    }
