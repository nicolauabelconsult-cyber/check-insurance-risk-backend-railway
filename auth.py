# main.py
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query
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
from auth import (
    router as auth_router,
    get_current_active_user,
    get_current_admin,
)
from schemas import (
    RiskCheckRequest,
    RiskCheckResponse,
    CandidateMatch,
    ConfirmMatchRequest,
    RiskHistoryResponse,
    RiskHistoryItem,
    RiskDetailResponse,
)
from risk_engine import (
    analyze_risk_request,
    calculate_match_score,
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

# Criar tabelas na base de dados
Base.metadata.create_all(bind=engine)


@app.on_event("startup")
def startup_event() -> None:
    """
    Evento de arranque:
    - cria o utilizador admin por defeito, se ainda não existir.
    """
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

    - Usa risk_engine.analyze_risk_request para obter score, nível, factores e candidatos.
    - Calcula match_score por candidato.
    - Grava um RiskRecord na base de dados.
    - Devolve RiskCheckResponse (score, level, factors, candidates).
    """

    # 1) Chamar o motor de risco
    result = analyze_risk_request(
        db=db,
        name=payload.name,
        nif=payload.nif,
        passport=payload.passport,
        resident_card=payload.resident_card,
        nationality=payload.nationality,
    )

    raw_score = result.get("score") or 0.0
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 0.0

    level_value = result.get("level")
    if isinstance(level_value, RiskLevel):
        level_str = level_value.value
    else:
        level_str = str(level_value or RiskLevel.LOW.value)

    factors = result.get("factors") or []
    raw_candidates = result.get("candidates") or []

    # 2) Calcular match_score por candidato
    search_params = {
        "name": payload.name,
        "nif": payload.nif,
        "passport": payload.passport,
        "resident_card": payload.resident_card,
        "nationality": payload.nationality,
    }

    candidates: List[CandidateMatch] = []
    for c in raw_candidates:
        # Garantir que temos um dict com os campos esperados
        if isinstance(c, dict):
            cand_dict = dict(c)
        else:
            cand_dict = {
                "id": getattr(c, "id", None),
                "name": getattr(c, "name", None),
                "normalized_name": getattr(c, "normalized_name", None),
                "nif": getattr(c, "nif", None),
                "passport": getattr(c, "passport", None),
                "resident_card": getattr(c, "resident_card", None),
                "country": getattr(c, "country", None),
                "info_source_id": getattr(c, "info_source_id", None),
            }

        match_score = calculate_match_score(candidate=cand_dict, search=search_params)
        cand_dict["match_score"] = match_score

        candidates.append(CandidateMatch(**cand_dict))

    # 3) Gravar registo de risco
    record = RiskRecord(
        full_name=payload.name,
        nif=payload.nif,
        passport=payload.passport,
        resident_card=payload.resident_card,
        country=payload.nationality,
        score=int(score),
        level=level_str,
        decision=None,
        explanation={"factors": factors},
        analyst_id=current_user.id,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    # 4) Resposta para o frontend
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
    Confirma o candidato escolhido para um determinado RiskRecord.

    - risk_record_id: ID do registo de risco
    - chosen_candidate_id: ID da NormalizedEntity seleccionada
    """
    record = (
        db.query(RiskRecord)
        .filter(RiskRecord.id == payload.risk_record_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Registo de risco não encontrado.")

    if payload.chosen_candidate_id is not None:
        entity = (
            db.query(NormalizedEntity)
            .filter(NormalizedEntity.id == payload.chosen_candidate_id)
            .first()
        )
        if not entity:
            raise HTTPException(status_code=404, detail="Entidade seleccionada não existe.")
        record.confirmed_entity_id = entity.id

    db.add(record)
    db.commit()
    db.refresh(record)

    return {"success": True, "message": "Match confirmado com sucesso."}


@app.get(f"{settings.API_PREFIX}/risk/history", response_model=RiskHistoryResponse)
def risk_history(
    identifier: str = Query(..., description="NIF, passaporte, cartão de residente ou nome"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RiskHistoryResponse:
    """
    Devolve o histórico de análises para um identificador:
    - NIF, passaporte, cartão de residente ou nome.
    """

    q = f"%{identifier.upper()}%"

    records = (
        db.query(RiskRecord)
        .filter(
            (RiskRecord.nif.ilike(q))
            | (RiskRecord.passport.ilike(q))
            | (RiskRecord.resident_card.ilike(q))
            | (RiskRecord.full_name.ilike(q))
        )
        .order_by(RiskRecord.created_at.desc())
        .all()
    )

    history_items: List[RiskHistoryItem] = []
    for r in records:
        history_items.append(
            RiskHistoryItem(
                id=r.id,
                name=r.full_name,
                nif=r.nif,
                passport=r.passport,
                resident_card=r.resident_card,
                risk_level=r.level,
                risk_score=r.score,
                created_at=r.created_at,
            )
        )

    return RiskHistoryResponse(
        identifier=identifier,
        history=history_items,
        total=len(history_items),
    )


@app.get(f"{settings.API_PREFIX}/risk/{{risk_id}}", response_model=RiskDetailResponse)
def risk_detail(
    risk_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RiskDetailResponse:
    """
    Detalhe de uma análise de risco específica.
    Alimenta o ecrã de detalhe / relatório web.
    """
    r: Optional[RiskRecord] = (
        db.query(RiskRecord).filter(RiskRecord.id == risk_id).first()
    )
    if not r:
        raise HTTPException(status_code=404, detail="Análise não encontrada.")

    # Reconstruir pedido original (aproximado) a partir do RiskRecord
    request_obj = RiskCheckRequest(
        name=r.full_name,
        nif=r.nif,
        passport=r.passport,
        resident_card=r.resident_card,
        nationality=r.country,
    )

    # Factores
    factors: List[str] = []
    if isinstance(r.explanation, dict) and "factors" in r.explanation:
        raw_factors = r.explanation.get("factors") or []
        factors = [str(f) for f in raw_factors]
    elif isinstance(r.explanation, list):
        factors = [str(f) for f in r.explanation]

    # Histórico para o mesmo NIF/passaporte/cartão (ou nome)
    identifier = r.nif or r.passport or r.resident_card or r.full_name
    history_records: List[RiskRecord] = []
    if identifier:
        history_records = (
            db.query(RiskRecord)
            .filter(
                (RiskRecord.nif == identifier)
                | (RiskRecord.passport == identifier)
                | (RiskRecord.resident_card == identifier)
                | (RiskRecord.full_name == identifier)
            )
            .order_by(RiskRecord.created_at.desc())
            .all()
        )

    history_items: List[RiskHistoryItem] = []
    for h in history_records:
        history_items.append(
            RiskHistoryItem(
                id=h.id,
                name=h.full_name,
                nif=h.nif,
                passport=h.passport,
                resident_card=h.resident_card,
                risk_level=h.level,
                risk_score=h.score,
                created_at=h.created_at,
            )
        )

    return RiskDetailResponse(
        id=r.id,
        request=request_obj,
        score=r.score,
        level=r.level,
        factors=factors,
        candidates=[],          # neste momento não estamos a persistir matches por análise
        history=history_items,
    )


@app.get(f"{settings.API_PREFIX}/risk/{{risk_id}}/report/pdf")
def risk_report_pdf(
    risk_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    """
    Gera o PDF da análise individual.
    Depende de reporting.generate_risk_pdf estar implementado.
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
    Apenas utilizadores ADMIN podem aceder.
    """
    return export_risk_excel(db)
