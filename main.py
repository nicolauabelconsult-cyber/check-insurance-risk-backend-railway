# main.py
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from config import settings
from database import Base, engine, get_db
from risk_engine import (
    analyze_risk_request,
    confirm_match_and_persist,
    get_history_for_identifier,
)
from auth import (
    router as auth_router,
    get_current_active_user,
    get_current_admin,
)
from risk_engine import (
    find_candidates,
    calculate_match_score,
    aggregate_matches,
    base_level_from_score,
)
from schemas import (
    RiskCheckRequest,
    RiskCheckResponse,
    MatchResult,
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

# Routers externos
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(info_sources_router, prefix=settings.API_PREFIX)
app.include_router(dashboard_router, prefix=settings.API_PREFIX)

# Criar tabelas
Base.metadata.create_all(bind=engine)


@app.on_event("startup")
def startup_event() -> None:
    """Criar utilizador admin por defeito."""
    db = next(get_db())
    try:
        seed_default_admin(db)
    finally:
        db.close()


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
    - pesquisa em entidades normalizadas
    - calcula score e nível
    - grava RiskRecord
    - devolve matches possíveis
    """

    # 1. Procurar candidatos em todas as fontes
    candidates: List[NormalizedEntity] = find_candidates(
        db,
        full_name=payload.full_name,
        nif=payload.nif,
        passport=payload.passport,
        resident_card=payload.resident_card,
    )

    entities_with_scores = []
    explanation_global: List[str] = []

    if candidates:
        for entity in candidates:
            score, factors = calculate_match_score(
                country=payload.country,
                entity=entity,
                input_full_name=payload.full_name,
                input_nif=payload.nif,
                input_passport=payload.passport,
                input_resident_card=payload.resident_card,
            )
            entities_with_scores.append((entity, score, factors))
    else:
        # Sem matches, score baixo
        explanation_global.append(
            "Nenhuma correspondência encontrada em bases PEP/Fraude/Sinistros/Sanções."
        )

    # 2. Agregar matches
    matches_objects: List[MatchResult] = []
    if entities_with_scores:
        aggregated = aggregate_matches(entities_with_scores)
        for item in aggregated:
            matches_objects.append(
                MatchResult(
                    match_id=item["match_id"],
                    nome=item["entity"].full_name_norm or "",
                    fontes=[item["entity"].source_type],
                    score=item["score"],
                    nivel=item["nivel"],
                    explicacao=item["factors"],
                )
            )
        # Score global = máximo dos matches
        score_global = max(m.score for m in matches_objects)
        explanation_global = ["Matches encontrados em bases de alto risco."]
    else:
        score_global = 10

    level_global = base_level_from_score(score_global)
    if level_global in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
        decision_suggested = RiskDecision.UNDER_INVESTIGATION
    else:
        decision_suggested = RiskDecision.APPROVED

    # 3. Gravar registo de risco
    record = RiskRecord(
        full_name=payload.full_name,
        nif=payload.nif,
        passport=payload.passport,
        resident_card=payload.resident_card,
        country=payload.country,
        score=score_global,
        level=level_global.value,
        decision=None,
        explanation=explanation_global,
        analyst_id=current_user.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return RiskCheckResponse(
        analysis_id=record.id,
        score=score_global,
        level=level_global,
        decision_suggested=decision_suggested,
        explanation=explanation_global,
        matches=matches_objects,
    )


@app.post(f"{settings.API_PREFIX}/risk/confirm-match")
def confirm_match(
    payload: ConfirmMatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Confirmar qual o match é o correcto e registar decisão final do analista.
    (Por enquanto, o match_id não está ligado a uma entidade específica — simplificado.)
    """
    record = db.query(RiskRecord).filter(RiskRecord.id == payload.analysis_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Análise não encontrada.")

    # TODO: mapear correctamente match_id -> NormalizedEntity.
    entity = db.query(NormalizedEntity).first()

    record.decision = payload.final_decision.value
    record.decision_notes = payload.notes
    if entity:
        record.confirmed_entity_id = entity.id

    db.commit()
    return {"message": "Match confirmado e decisão registada."}


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
                nivel=RiskLevel(r.level),
                decisao=RiskDecision(r.decision) if r.decision else None,  # type: ignore
            )
        )

    return RiskHistoryResponse(results=items)


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

    cliente = ClienteInfo(
        nome=r.full_name,
        nif=r.nif,
        passaporte=r.passport,
        cartao_residente=r.resident_card,
        nacionalidade=r.country,
        endereco=None,
    )

    fontes: List[FonteInfo] = []
    principais_riscos = r.explanation or []
    historico: List[HistoricoClienteItem] = []
    relacoes: List[str] = []

    # Histórico simplificado: todas as análises com mesmo NIF ou nome
    base_q = db.query(RiskRecord).filter(
        (RiskRecord.nif == r.nif) | (RiskRecord.full_name == r.full_name)
    )
    for h in base_q.order_by(RiskRecord.created_at.desc()).all():
        historico.append(
            HistoricoClienteItem(
                data=h.created_at,
                operacao="Análise de risco",
                score=h.score,
                nivel=RiskLevel(h.level),
                decisao=RiskDecision(h.decision) if h.decision else None,  # type: ignore
            )
        )

    # Fontes simplificadas: se houver entidade confirmada, usa a sua fonte
    if r.confirmed_entity_id:
        entity = db.query(NormalizedEntity).filter(
            NormalizedEntity.id == r.confirmed_entity_id
        ).first()
        if entity:
            fontes.append(
                FonteInfo(
                    tipo=entity.source_type,
                    ocorrencias=1,
                    ultima_atualizacao=entity.created_at,
                )
            )

    return RiskDetailResponse(
        id=r.id,
        data_analise=r.created_at,
        analista=r.analyst.username if r.analyst else None,
        score=r.score,
        nivel=RiskLevel(r.level),
        decisao=RiskDecision(r.decision) if r.decision else None,  # type: ignore
        cliente=cliente,
        fontes=fontes,
        principais_riscos=principais_riscos,
        historico_cliente=historico,
        relacoes=relacoes,
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
