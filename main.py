# main.py – backend Check Insurance Risk

from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from config import settings
from database import Base, engine, get_db
from models import (
    User,
    RiskRecord,
    NormalizedEntity,
    RiskLevel,
    RiskDecision,
)
from risk_engine import (
    analyze_risk_request,
    confirm_match_and_persist,
)
from auth import (
    router as auth_router,
    get_current_active_user,
    get_current_admin,
)
from users import router as users_router
from schemas import (
    RiskCheckRequest,
    RiskCheckResponse,
    ConfirmMatchRequest,
    RiskHistoryResponse,
    RiskHistoryItem,
    RiskDetailResponse,
    ClienteInfo,
    FonteInfo,
    HistoricoClienteItem,
)
from reporting import generate_risk_pdf, export_risk_excel
from info_sources import router as info_sources_router
from dashboard import router as dashboard_router
from seed_admin import seed_default_admin


# -------------------------------------------------------------------
# APP & CORS
# -------------------------------------------------------------------

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------------
# DB INIT & STARTUP
# -------------------------------------------------------------------

# Criar tabelas na base de dados
Base.metadata.create_all(bind=engine)


@app.on_event("startup")
def startup_event() -> None:
    """Criar utilizador admin por defeito (se não existir)."""
    db = next(get_db())
    try:
        seed_default_admin(db)
    finally:
        db.close()


# -------------------------------------------------------------------
# ROUTERS EXTERNOS
# -------------------------------------------------------------------

# Autenticação
app.include_router(auth_router, prefix=settings.API_PREFIX)

# Gestão de utilizadores (admin)
app.include_router(users_router, prefix=settings.API_PREFIX)

# Fontes de informação
app.include_router(info_sources_router, prefix=settings.API_PREFIX)

# Dashboard
app.include_router(dashboard_router, prefix=settings.API_PREFIX)


# -------------------------------------------------------------------
# ENDPOINTS DE RISCO
# -------------------------------------------------------------------

@app.post(f"{settings.API_PREFIX}/risk/check", response_model=RiskCheckResponse)
def risk_check(
    payload: RiskCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RiskCheckResponse:
    """
    Executa análise de risco:
    - usa o motor (analyze_risk_request) para obter score / nível / candidatos
    - grava RiskRecord na BD
    - devolve matches com match_score para o frontend
    """

    # 1) Motor de risco
    engine_result = analyze_risk_request(
        db=db,
        name=payload.full_name,      # <- usa full_name do schema
        nif=payload.nif,
        passport=payload.passport,
        resident_card=payload.resident_card,
        nationality=payload.country,
    )

    score = float(engine_result.get("score") or 0.0)
    level_str = str(engine_result.get("level") or "LOW")
    factors = engine_result.get("factors", []) or []
    candidates = engine_result.get("candidates", []) or []

    # Converter nível string → enum para decidir sugestão
    try:
        level_enum = RiskLevel(level_str)
    except Exception:
        level_enum = RiskLevel.LOW

    if level_enum in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        decision_suggested = RiskDecision.UNDER_INVESTIGATION.value
    else:
        decision_suggested = RiskDecision.APPROVED.value

    # 2) Guardar registo na BD
    record = RiskRecord(
        full_name=payload.full_name,
        nif=payload.nif,
        passport=payload.passport,
        resident_card=payload.resident_card,
        country=payload.country,
        score=int(score),
        level=level_str,
        decision=None,
        decision_notes=None,
        explanation={
            "factors": factors,
            "candidates": candidates,
            "decision_suggested": decision_suggested,
        },
        analyst_id=current_user.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # 3) Resposta para o frontend
    # Pydantic converte automaticamente cada dict → CandidateMatch
    return RiskCheckResponse(
        score=score,
        level=level_str,
        factors=factors,
        candidates=candidates,
    )


@app.post(f"{settings.API_PREFIX}/risk/confirm-match")
def confirm_match(
    payload: ConfirmMatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Confirma o match escolhido pelo analista.
    Apenas associa o RiskRecord a uma NormalizedEntity (confirmed_entity_id).
    """

    record = (
        db.query(RiskRecord)
        .filter(RiskRecord.id == payload.risk_record_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Análise não encontrada.")

    # Actualiza o registo com a entidade escolhida
    confirm_match_and_persist(
        db=db,
        risk_record=record,
        chosen_candidate_id=payload.chosen_candidate_id,
    )

    return {"message": "Match confirmado com sucesso."}


@app.get(f"{settings.API_PREFIX}/risk/history", response_model=RiskHistoryResponse)
def risk_history(
    query: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RiskHistoryResponse:
    """
    Pesquisa histórico por nome / NIF / passaporte / cartão de residente.
    """

    q = f"%{query.upper()}%"
    records = (
        db.query(RiskRecord)
        .filter(
            (RiskRecord.full_name.ilike(q))
            | (RiskRecord.nif.ilike(q))
            | (RiskRecord.passport.ilike(q))
            | (RiskRecord.resident_card.ilike(q))
        )
        .order_by(RiskRecord.created_at.desc())
        .all()
    )

    items: List[RiskHistoryItem] = []
    for r in records:
        items.append(
            RiskHistoryItem(
                analysis_id=r.id,
                data=r.created_at,
                nome=r.full_name,
                score=r.score,
                nivel=r.level,      # string já compatível com schema
                decisao=r.decision, # idem
            )
        )

    return RiskHistoryResponse(
        identifier=query,
        results=items,
        total=len(items),
    )


@app.get(f"{settings.API_PREFIX}/risk/{{risk_id}}", response_model=RiskDetailResponse)
def risk_detail(
    risk_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RiskDetailResponse:
    """
    Detalhe completo de uma análise – alimenta o relatório web.
    """

    r = db.query(RiskRecord).filter(RiskRecord.id == risk_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Análise não encontrada.")

    # Cliente
    cliente = ClienteInfo(
        nome=r.full_name,
        nif=r.nif,
        passaporte=r.passport,
        cartao_residente=r.resident_card,
        nacionalidade=r.country,
        endereco=None,
    )

    # Explicação
    exp = r.explanation or {}
    if isinstance(exp, dict):
        principais_riscos = exp.get("factors", []) or []
    else:
        principais_riscos = []

    # Histórico simplificado
    historico: List[HistoricoClienteItem] = []
    base_q = db.query(RiskRecord).filter(
        (RiskRecord.nif == r.nif) | (RiskRecord.full_name == r.full_name)
    )
    for h in base_q.order_by(RiskRecord.created_at.desc()).all():
        historico.append(
            HistoricoClienteItem(
                data=h.created_at,
                operacao="Análise de risco",
                score=h.score,
                nivel=h.level,
                decisao=h.decision,
            )
        )

    # Fontes simplificadas: se houver entidade confirmada, pega a fonte
    fontes: List[FonteInfo] = []
    if r.confirmed_entity_id:
        entity = (
            db.query(NormalizedEntity)
            .filter(NormalizedEntity.id == r.confirmed_entity_id)
            .first()
        )
        if entity:
            fontes.append(
                FonteInfo(
                    tipo=getattr(entity, "source_type", None),
                    ocorrencias=1,
                    ultima_atualizacao=getattr(entity, "created_at", None),
                )
            )

    return RiskDetailResponse(
        id=r.id,
        data_analise=r.created_at,
        analista=r.analyst.username if r.analyst else None,
        score=r.score,
        nivel=r.level,
        decisao=r.decision,
        cliente=cliente,
        fontes=fontes,
        principais_riscos=principais_riscos,
        historico_cliente=historico,
        relacoes=[],
        recomendacoes=r.decision_notes,
    )


@app.get(f"{settings.API_PREFIX}/risk/{{risk_id}}/report/pdf")
def risk_report_pdf(
    risk_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    """
    Gera o PDF da análise individual.
    """
    r = db.query(RiskRecord).filter(RiskRecord.id == risk_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Análise não encontrada.")
    return generate_risk_pdf(db, r)


@app.get(f"{settings.API_PREFIX}/risk/export/excel")
def risk_export_excel(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> StreamingResponse:
    """
    Exporta todas as análises em Excel.
    """
    return export_risk_excel(db)


# Health-check simples (opcional)
@app.get("/health")
def health_check():
    return {"status": "ok"}
