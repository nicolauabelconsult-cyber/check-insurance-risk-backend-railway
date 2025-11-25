from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


# ---------- Auth ----------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class TokenData(BaseModel):
    username: str
    role: str


class LoginRequest(BaseModel):
    username: str
    password: str


# ---------- User ----------

class UserBase(BaseModel):
    username: str
    email: EmailStr
    role: str


class UserOut(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Risk & Matching ----------

class RiskCheckRequest(BaseModel):
    full_name: str
    nif: Optional[str] = None
    passport: Optional[str] = None
    resident_card: Optional[str] = None
    country: Optional[str] = None


class RiskMatchOut(BaseModel):
    match_id: int
    nome: str
    fontes: List[str]
    score: int
    nivel: str
    explicacao: List[str]


class RiskCheckResponse(BaseModel):
    analysis_id: int
    score: int
    level: str
    decision_suggested: str
    explanation: List[str]
    matches: List[RiskMatchOut]


class ConfirmMatchRequest(BaseModel):
    analysis_id: int
    match_id: Optional[int] = None
    final_decision: str
    notes: Optional[str] = None


class RiskHistoryItem(BaseModel):
    analysis_id: int
    data: datetime
    nome: str
    score: int
    nivel: str
    decisao: str


class RiskHistoryResponse(BaseModel):
    results: List[RiskHistoryItem]


class RiskDetailClient(BaseModel):
    nome: str
    nif: Optional[str]
    passaporte: Optional[str]
    cartao_residente: Optional[str]
    nacionalidade: Optional[str]
    endereco: Optional[str] = None


class RiskDetailFonte(BaseModel):
    tipo: str
    ocorrencias: int
    ultima_atualizacao: Optional[datetime]


class RiskDetailHistoricoItem(BaseModel):
    data: datetime
    operacao: str
    score: int
    nivel: str
    decisao: str


class RiskDetailResponse(BaseModel):
    id: int
    data_analise: datetime
    analista: Optional[str]
    score: int
    nivel: str
    decisao: str
    cliente: RiskDetailClient
    fontes: List[RiskDetailFonte]
    principais_riscos: List[str]
    historico_cliente: List[RiskDetailHistoricoItem]
    relacoes: List[str]
    recomendacoes: Optional[str]


# ---------- Dashboard ----------

class DashboardStats(BaseModel):
    total_analises_hoje: int
    casos_high_critical: int
    tempo_medio_analise_segundos: float
    ultimas_analises: List[RiskHistoryItem]


# ---------- Info Sources ----------

class InfoSourceOut(BaseModel):
    id: int
    name: str
    source_type: str
    description: Optional[str]
    record_count: int
    last_import_at: Optional[datetime]

    class Config:
        from_attributes = True
