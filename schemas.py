from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, ConfigDict


# =========================================================
# AUTENTICAÇÃO
# =========================================================

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


# =========================================================
# UTILIZADOR
# =========================================================

class UserRead(BaseModel):
    id: int
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# INFO SOURCE (Fontes de Informação)
# =========================================================

class InfoSourceRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    source_type: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# DADOS DO CLIENTE
# =========================================================

class ClienteInfo(BaseModel):
    """Informação do cliente analisado."""
    name: Optional[str] = None
    nif: Optional[str] = None
    passport: Optional[str] = None
    resident_card: Optional[str] = None
    nationality: Optional[str] = None
    other_id: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


# =========================================================
# REQUEST – Análise de Risco
# =========================================================

class RiskCheckRequest(BaseModel):
    name: str
    nif: Optional[str] = None
    passport: Optional[str] = None
    resident_card: Optional[str] = None
    nationality: Optional[str] = None


# =========================================================
# CANDIDATOS / MATCHES
# =========================================================

class CandidateMatch(BaseModel):
    id: Optional[int] = None

    name: Optional[str] = None
    normalized_name: Optional[str] = None

    nif: Optional[str] = None
    passport: Optional[str] = None
    resident_card: Optional[str] = None
    country: Optional[str] = None

    info_source_id: Optional[int] = None
    match_score: Optional[float] = None

    model_config = ConfigDict(extra="ignore")


class MatchResult(BaseModel):
    total: int
    candidates: List[CandidateMatch] = []


class ConfirmMatchRequest(BaseModel):
    risk_record_id: int
    chosen_candidate_id: Optional[int] = None


# =========================================================
# RESPOSTA PRINCIPAL – Análise de Risco
# =========================================================

class RiskCheckResponse(BaseModel):
    score: float
    level: str
    factors: List[str] = []
    candidates: List[CandidateMatch] = []


# =========================================================
# HISTÓRICO
# =========================================================

class RiskHistoryItem(BaseModel):
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    score: Optional[float] = None
    level: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class RiskHistoryResponse(BaseModel):
    identifier: Optional[str] = None
    history: List[RiskHistoryItem] = []
    total: Optional[int] = None


# =========================================================
# DETALHE DA ANÁLISE
# =========================================================

class RiskDetailResponse(BaseModel):
    """
    Estrutura final para alimentar:
    - Relatório PDF
    - Relatório Web
    - Modal de detalhe no frontend
    """
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    cliente: Optional[ClienteInfo] = None
    request: Optional[RiskCheckRequest] = None

    score: Optional[float] = None
    level: Optional[str] = None
    factors: List[str] = []

    candidates: List[CandidateMatch] = []
    history: List[RiskHistoryItem] = []

    fontes: Optional[List[InfoSourceRead]] = None
    relacoes: Optional[List[str]] = None
    recomendacoes: Optional[str] = None

    model_config = ConfigDict(extra="ignore")
