# app/routers/dashboard.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func, case, cast, Float
from sqlalchemy.orm import Session

from app.deps import get_db, require_perm
from app.models import User, UserRole, Risk, Entity, AuditLog, Source


def _iter_period_risks(db: Session, user: User, entity_id: Optional[str], start: datetime, limit: int = 5000):
    """Itera risks no período para métricas que dependem de JSON (matches)."""
    q = db.query(Risk).filter(Risk.created_at >= start)
    q = _apply_entity_scope_risk(q, user, entity_id)
    return q.order_by(Risk.created_at.desc()).limit(limit).all()


def _risk_has_category(r: Risk, cat: str) -> bool:
    cat_u = (cat or "").upper().strip()
    try:
        for m in (r.matches or []):
            if str(m.get("category", "")).upper().strip() == cat_u:
                return True
    except Exception:
        return False
    return False

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Aceitamos períodos usados pelo frontend executivo.
# NOTA: usamos validação manual para evitar 422 inesperado quando o frontend muda.
ALLOWED_PERIODS = {"7d", "30d", "90d", "180d", "6m", "12m"}
ALLOWED_GRANULARITY = {"day", "week"}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_period(period: str) -> Tuple[str, datetime]:
    now = _now_utc()
    p = (period or "30d").strip().lower()
    if p not in ALLOWED_PERIODS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid period '{period}'. Allowed: {sorted(ALLOWED_PERIODS)}",
        )

    if p == "7d":
        return p, now - timedelta(days=7)
    if p == "30d":
        return p, now - timedelta(days=30)
    if p == "90d":
        return p, now - timedelta(days=90)
    if p in ("180d", "6m"):
        return p, now - timedelta(days=180)
    return p, now - timedelta(days=365)  # 12m ~ 365d


def _score_num():
    """
    Cast seguro do score (VARCHAR) para número.
    - Se for numérico: converte para Float
    - Se não for numérico: NULL (avg ignora NULL)
    """
    is_numeric = Risk.score.op("~")(r"^\s*\d+(\.\d+)?\s*$")  # regex postgres
    return case(
        (is_numeric, cast(func.trim(Risk.score), Float)),
        else_=None,
    )


def _bucket_case_exec(score_num_col):
    """Buckets institucionais (matriz formal):
    - CRITICAL: >= 75
    - HIGH:     50-74
    - MEDIUM:   25-49
    - LOW:      0-24
    Score inválido -> NULL -> coalesce para 0 -> LOW
    """
    s = func.coalesce(score_num_col, 0.0)
    return case(
        (s >= 75, "CRITICAL"),
        (s >= 50, "HIGH"),
        (s >= 25, "MEDIUM"),
        else_="LOW",
    )


def _bucket_case_legacy(score_num_col):
    """Compatibilidade com a primeira versão do dashboard."""
    s = func.coalesce(score_num_col, 0.0)
    return case(
        (s >= 80, "High"),
        (s >= 50, "Medium"),
        else_="Low",
    )


def _apply_entity_scope_risk(q, user: User, entity_id: Optional[str]):
    """
    Escopo (Produção V1):
    - SUPER_ADMIN: vê tudo (ou filtra por entity_id se enviado)
    - ADMIN e CLIENT_*: vê apenas a sua entity_id
    """
    if user.role == UserRole.SUPER_ADMIN:
        if entity_id:
            return q.filter(Risk.entity_id == entity_id)
        return q

    if not getattr(user, "entity_id", None):
        raise HTTPException(status_code=403, detail="Entity scope missing for this user")
    return q.filter(Risk.entity_id == user.entity_id)


def _apply_entity_scope_audit(q, user: User, entity_id: Optional[str]):
    if user.role == UserRole.SUPER_ADMIN:
        if entity_id:
            return q.filter(AuditLog.entity_id == entity_id)
        return q

    if not getattr(user, "entity_id", None):
        raise HTTPException(status_code=403, detail="Entity scope missing for this user")
    return q.filter(AuditLog.entity_id == user.entity_id)


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("dashboard:read")),
    period: str = Query("30d"),
    entity_id: Optional[str] = Query(None),
    audit_limit: int = Query(200, ge=10, le=500),
) -> Dict[str, Any]:
    period_norm, start = _parse_period(period)

    # -----------------------------
    # KPIs base
    # -----------------------------
    # Entidades
    if u.role != UserRole.SUPER_ADMIN:
        entities_count = 1 if getattr(u, "entity_id", None) else 0
    else:
        entities_count = db.query(func.count(Entity.id)).scalar() or 0
        if entity_id:
            entities_count = 1

    # Utilizadores
    users_q = db.query(func.count(User.id))
    if u.role != UserRole.SUPER_ADMIN:
        users_q = users_q.filter(User.entity_id == u.entity_id)
    else:
        if entity_id:
            users_q = users_q.filter(User.entity_id == entity_id)
    users_count = users_q.scalar() or 0

    # Fontes
    sources_q = db.query(func.count(Source.id))
    if u.role == UserRole.SUPER_ADMIN:
        if entity_id:
            sources_q = sources_q.filter(Source.entity_id == entity_id)
    else:
        sources_q = sources_q.filter(Source.entity_id == u.entity_id)
    sources_count = sources_q.scalar() or 0

    # Total de risks (vida inteira)
    risks_total_q = db.query(func.count(Risk.id))
    risks_total_q = _apply_entity_scope_risk(risks_total_q, u, entity_id)
    risks_total = risks_total_q.scalar() or 0

    # Risks no período (para KPIs)
    risks_period_q = db.query(Risk.id).filter(Risk.created_at >= start)
    risks_period_q = _apply_entity_scope_risk(risks_period_q, u, entity_id)
    analyses_count = risks_period_q.count()

    # Score médio no período (CAST seguro)
    score_num = _score_num()
    avg_score_q = db.query(func.avg(score_num)).filter(Risk.created_at >= start)
    avg_score_q = _apply_entity_scope_risk(avg_score_q, u, entity_id)
    avg_score_val = avg_score_q.scalar()
    avg_score_val = float(avg_score_val) if avg_score_val is not None else 0.0

    # Distribuição High/Medium/Low no período
    bucket_exec = _bucket_case_exec(score_num)
    bucket_legacy = _bucket_case_legacy(score_num)
    dist_exec_q = db.query(bucket_exec.label("bucket"), func.count(Risk.id).label("count")).filter(
        Risk.created_at >= start
    )
    dist_exec_q = _apply_entity_scope_risk(dist_exec_q, u, entity_id)
    dist_exec_rows = dist_exec_q.group_by("bucket").all()

    distribution_exec = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for r in dist_exec_rows:
        distribution_exec[str(r.bucket)] = int(r.count)

    dist_legacy_q = db.query(bucket_legacy.label("bucket"), func.count(Risk.id).label("count")).filter(
        Risk.created_at >= start
    )
    dist_legacy_q = _apply_entity_scope_risk(dist_legacy_q, u, entity_id)
    dist_legacy_rows = dist_legacy_q.group_by("bucket").all()
    distribution_legacy = {"High": 0, "Medium": 0, "Low": 0}
    for r in dist_legacy_rows:
        distribution_legacy[str(r.bucket)] = int(r.count)

    # -----------------------------
    # Últimas análises (tabela)
    # -----------------------------
    # Risk NÃO tem "name". Campo correto: query_name.
    last_q = db.query(
        Risk.id,
        Risk.query_name,
        Risk.score,
        Risk.status,
        Risk.entity_id,
        Risk.created_at,
    ).filter(Risk.created_at >= start)

    last_q = _apply_entity_scope_risk(last_q, u, entity_id)
    last_rows = last_q.order_by(Risk.created_at.desc()).limit(10).all()

    last_analyses = [
        {
            "id": str(r.id),
            "name": r.query_name,  # devolvemos como "name" para o frontend
            "score": r.score,
            "status": str(r.status) if r.status is not None else None,
            "entity_id": str(r.entity_id) if r.entity_id else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in last_rows
    ]

    # -----------------------------
    # Top auditoria por ação (período)
    # -----------------------------
    # Cliente não vê auditoria. ADMIN vê apenas a sua entidade. SUPER_ADMIN pode ver global/filtrado.
    audit_top_actions: List[Dict[str, Any]] = []
    if u.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        audit_q = db.query(
            AuditLog.action.label("action"),
            func.count(AuditLog.id).label("count"),
        ).filter(AuditLog.created_at >= start)

        # ADMIN é scoped (como cliente)
        if u.role == UserRole.ADMIN and u.entity_id:
            audit_q = audit_q.filter(AuditLog.entity_id == u.entity_id)
        else:
            audit_q = _apply_entity_scope_audit(audit_q, u, entity_id)

        audit_top = (
            audit_q.group_by(AuditLog.action)
            .order_by(func.count(AuditLog.id).desc())
            .limit(7)
            .all()
        )
        audit_top_actions = [{"action": str(a.action), "count": int(a.count)} for a in audit_top]

    # -----------------------------
    # Métricas baseadas em evidências (JSON matches)
    # -----------------------------
    pep_risks = sanc_risks = 0
    sampled = _iter_period_risks(db, u, entity_id, start, limit=2000)
    if analyses_count > 0 and sampled:
        for r in sampled:
            if _risk_has_category(r, "PEP"):
                pep_risks += 1
            if _risk_has_category(r, "SANCTIONS"):
                sanc_risks += 1

    denom = max(len(sampled), 1) if analyses_count > 0 else 1
    pep_rate = pep_risks / denom if analyses_count > 0 else 0.0
    sanctions_rate = sanc_risks / denom if analyses_count > 0 else 0.0

    return {
        "period": period_norm,
        "entity_id": entity_id,
        "kpis": {
            "entities": int(entities_count),
            "users": int(users_count),
            "sources": int(sources_count),
            "risks_total": int(risks_total),
            "analyses": int(analyses_count),
            "avg_score": round(avg_score_val, 2),
            "distribution": distribution_exec,
            "distribution_legacy": distribution_legacy,
        },
        # Campos executivos prontos (sem quebrar o frontend antigo)
        "kpis_exec": {
            "total_analyses": int(analyses_count),
            "critical": int(distribution_exec["CRITICAL"]),
            "high": int(distribution_exec["HIGH"]),
            "medium": int(distribution_exec["MEDIUM"]),
            "low": int(distribution_exec["LOW"]),
            "high_or_critical": int(distribution_exec["CRITICAL"] + distribution_exec["HIGH"]),
            "avg_score": round(avg_score_val, 2),
            "pep_rate": round(pep_rate, 4),
            "sanctions_rate": round(sanctions_rate, 4),
            "sampled": int(len(sampled)),
        },
        "last_analyses": last_analyses,
        "audit_top_actions": audit_top_actions,
    }


@router.get("/distribution")
def dashboard_distribution(
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("dashboard:read")),
    period: str = Query("30d"),
    entity_id: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    period_norm, start = _parse_period(period)

    score_num = _score_num()
    bucket_exec = _bucket_case_exec(score_num)

    q = db.query(bucket_exec.label("bucket"), func.count(Risk.id).label("count")).filter(
        Risk.created_at >= start
    )
    q = _apply_entity_scope_risk(q, u, entity_id)
    rows = q.group_by("bucket").all()

    base = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for r in rows:
        base[str(r.bucket)] = int(r.count)

    return [
        {"bucket": "CRITICAL", "count": base["CRITICAL"], "period": period_norm},
        {"bucket": "HIGH", "count": base["HIGH"], "period": period_norm},
        {"bucket": "MEDIUM", "count": base["MEDIUM"], "period": period_norm},
        {"bucket": "LOW", "count": base["LOW"], "period": period_norm},
    ]


@router.get("/trends")
def dashboard_trends(
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("dashboard:read")),
    period: str = Query("30d"),
    entity_id: Optional[str] = Query(None),
    granularity: str = Query("day"),
) -> List[Dict[str, Any]]:
    period_norm, start = _parse_period(period)

    g = (granularity or "day").strip().lower()
    if g not in ALLOWED_GRANULARITY:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid granularity '{granularity}'. Allowed: {sorted(ALLOWED_GRANULARITY)}",
        )

    trunc_unit = "day" if g == "day" else "week"
    date_key = func.date_trunc(trunc_unit, Risk.created_at).label("date")

    score_num = _score_num()

    bucket_exec = _bucket_case_exec(score_num)
    is_high_or_critical = case(
        (bucket_exec.in_(["HIGH", "CRITICAL"]), 1),
        else_=0,
    )

    q = db.query(
        date_key,
        func.avg(score_num).label("avg_score"),
        func.count(Risk.id).label("count"),
        func.sum(is_high_or_critical).label("high_or_critical"),
    ).filter(Risk.created_at >= start)

    q = _apply_entity_scope_risk(q, u, entity_id)
    q = q.group_by(date_key).order_by(date_key.asc())
    rows = q.all()

    return [
        {
            "date": (r.date.isoformat() if hasattr(r.date, "isoformat") else str(r.date)),
            "avg_score": round(float(r.avg_score or 0.0), 2),
            "count": int(r.count or 0),
            "high_or_critical": int(getattr(r, "high_or_critical", 0) or 0),
            "period": period_norm,
        }
        for r in rows
    ]


@router.get("/drivers")
def dashboard_drivers(
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("dashboard:read")),
    period: str = Query("30d"),
    entity_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=3, le=50),
) -> Dict[str, Any]:
    """Drivers executivos (o que mais empurra risco):
    - contagem de evidências por categoria
    - top fontes por volume de evidências
    """
    period_norm, start = _parse_period(period)

    risks = _iter_period_risks(db, u, entity_id, start, limit=5000)
    cat_counts: Dict[str, int] = {"PEP": 0, "SANCTIONS": 0, "WATCHLIST": 0, "ADVERSE_MEDIA": 0}
    source_counts: Dict[str, int] = {}
    for r in risks:
        for m in (r.matches or []):
            cat = str(m.get("category", "")).upper().strip() or "WATCHLIST"
            if cat in cat_counts:
                cat_counts[cat] += 1
            src = str(m.get("source", "")).strip()
            if src:
                source_counts[src] = source_counts.get(src, 0) + 1

    top_sources = sorted(source_counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]

    return {
        "period": period_norm,
        "entity_id": entity_id,
        "evidence_by_category": cat_counts,
        "top_sources": [{"source": k, "count": v} for k, v in top_sources],
        "sampled_risks": len(risks),
    }


@router.get("/by-sector")
def dashboard_by_sector(
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("dashboard:read")),
    period: str = Query("30d"),
) -> List[Dict[str, Any]]:
    """Somente SUPER_ADMIN: agrega por tipo de entidade (BANK/INSURANCE/OTHER)."""
    if u.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only SUPER_ADMIN can view by-sector")

    period_norm, start = _parse_period(period)

    # join Risk -> Entity para obter o tipo
    score_num = _score_num()
    bucket_exec = _bucket_case_exec(score_num)

    q = (
        db.query(
            Entity.type.label("sector"),
            func.count(Risk.id).label("analyses"),
            func.avg(score_num).label("avg_score"),
            func.sum(case((bucket_exec == "CRITICAL", 1), else_=0)).label("critical"),
            func.sum(case((bucket_exec == "HIGH", 1), else_=0)).label("high"),
        )
        .join(Entity, Entity.id == Risk.entity_id)
        .filter(Risk.created_at >= start)
        .group_by(Entity.type)
        .order_by(func.count(Risk.id).desc())
    )

    rows = q.all()
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "period": period_norm,
                "sector": str(r.sector),
                "analyses": int(r.analyses or 0),
                "avg_score": round(float(r.avg_score or 0.0), 2),
                "high_or_critical": int((r.critical or 0) + (r.high or 0)),
            }
        )
    return out


@router.get("/id-quality")
def dashboard_id_quality(
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("dashboard:read")),
    period: str = Query("30d"),
    entity_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Qualidade de identificação: quantos riscos têm BI ou Passaporte informado."""
    period_norm, start = _parse_period(period)

    q = db.query(
        func.count(Risk.id).label("total"),
        func.sum(case((Risk.query_bi.isnot(None), 1), else_=0)).label("with_bi"),
        func.sum(case((Risk.query_passport.isnot(None), 1), else_=0)).label("with_passport"),
    ).filter(Risk.created_at >= start)
    q = _apply_entity_scope_risk(q, u, entity_id)
    row = q.first()

    total = int(row.total or 0) if row else 0
    with_bi = int(row.with_bi or 0) if row else 0
    with_passport = int(row.with_passport or 0) if row else 0
    with_any = with_bi + with_passport
    coverage = (with_any / total) if total > 0 else 0.0

    return {
        "period": period_norm,
        "entity_id": entity_id,
        "total": total,
        "with_bi": with_bi,
        "with_passport": with_passport,
        "coverage": round(coverage, 4),
    }


@router.get("/underwriting")
def dashboard_underwriting(
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("dashboard:read")),
    period: str = Query("30d"),
    entity_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Resumo executivo de underwriting (versão 1).

    Nota: a plataforma tem tabelas insurance_policies/payments.
    Se estiver vazio, devolvemos zeros (o dashboard não quebra).
    """
    from app.models import InsurancePolicy, Payment

    period_norm, start = _parse_period(period)

    pol_q = db.query(
        func.count(InsurancePolicy.id).label("policies"),
        func.sum(case((InsurancePolicy.status == "CANCELLED", 1), else_=0)).label("cancelled"),
        func.sum(case((InsurancePolicy.status == "ACTIVE", 1), else_=0)).label("active"),
    ).filter(InsurancePolicy.created_at >= start)

    pay_q = db.query(
        func.count(Payment.id).label("payments"),
        func.sum(case((Payment.status == "LATE", 1), else_=0)).label("late"),
        func.sum(case((Payment.status == "FAILED", 1), else_=0)).label("failed"),
        func.sum(case((Payment.status == "PAID", 1), else_=0)).label("paid"),
    ).filter(Payment.created_at >= start)

    # scope
    if u.role != UserRole.SUPER_ADMIN:
        pol_q = pol_q.filter(InsurancePolicy.entity_id == u.entity_id)
        pay_q = pay_q.filter(Payment.entity_id == u.entity_id)
    else:
        if entity_id:
            pol_q = pol_q.filter(InsurancePolicy.entity_id == entity_id)
            pay_q = pay_q.filter(Payment.entity_id == entity_id)

    pol = pol_q.first()
    pay = pay_q.first()

    policies = int(pol.policies or 0) if pol else 0
    cancelled = int(pol.cancelled or 0) if pol else 0
    active = int(pol.active or 0) if pol else 0

    payments = int(pay.payments or 0) if pay else 0
    late = int(pay.late or 0) if pay else 0
    failed = int(pay.failed or 0) if pay else 0
    paid = int(pay.paid or 0) if pay else 0

    late_rate = (late / payments) if payments > 0 else 0.0
    failed_rate = (failed / payments) if payments > 0 else 0.0
    cancel_rate = (cancelled / policies) if policies > 0 else 0.0

    return {
        "period": period_norm,
        "entity_id": entity_id,
        "policies": {"total": policies, "active": active, "cancelled": cancelled, "cancel_rate": round(cancel_rate, 4)},
        "payments": {"total": payments, "paid": paid, "late": late, "failed": failed, "late_rate": round(late_rate, 4), "failed_rate": round(failed_rate, 4)},
    }
