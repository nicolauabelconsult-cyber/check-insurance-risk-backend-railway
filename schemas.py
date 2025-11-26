from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, ConfigDict



# -------------------------
# MODELOS DE AUTENTICAÇÃO
# -------------------------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


# -------------------------
# MODELOS DE UTILIZADOR
# -------------------------

class UserRead(BaseModel):
    id: int
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    # Permite criar o schema directamente a partir do modelo SQLAlchemy
    model_config = ConfigDict(from_attributes=True)

class RiskCheckRequest(BaseModel):
    """
    Payload principal para o endpoint de análise de risco.

    Estes campos alinham com o que o main.py e o risk_engine usam:
    - name, nif, passport, resident_card, nationality
    """
    name: str
    nif: Optional[str] = None
    passport: Optional[str] = None
    resident_card: Optional[str] = None
    nationality: Optional[str] = None

class CandidateMatch(BaseModel):
    """
    Representa um candidato devolvido pelo motor de risco.
    Campos alinhados com o risk_engine.find_candidates / aggregate_matches.
    """
    id: Optional[int] = None
    name: Optional[str] = None
    normalized_name: Optional[str] = None
    nif: Optional[str] = None
    passport: Optional[str] = None
    resident_card: Optional[str] = None
    country: Optional[str] = None
    info_source_id: Optional[int] = None
    match_score: Optional[float] = None

class RiskCheckResponse(BaseModel):
    """
    Resposta padrão do endpoint de análise de risco.

    Compatível com o que o risk_engine.analyze_risk_request devolve:
    - score: float (0–100)
    - level: string (ex.: "LOW", "MEDIUM", "HIGH")
    - factors: lista de motivos / factores de risco
    - candidates: lista de candidatos potenciais
    """
    score: float
    level: str
    factors: List[str] = []
    candidates: List[CandidateMatch] = []

class MatchResult(BaseModel):
    """
    Resultado do endpoint de multi-match / pesquisa de candidatos.

    Usamos:
    - total: número total de candidatos encontrados
    - candidates: lista de candidatos (CandidateMatch)
    """
    total: int
    candidates: List[CandidateMatch] = []

class ConfirmMatchRequest(BaseModel):
    """
    Payload para o endpoint de confirmação de match.

    - risk_record_id: ID do registo de risco que queremos actualizar
    - chosen_candidate_id: ID do candidato escolhido pelo analista
    """
    risk_record_id: int
    chosen_candidate_id: Optional[int] = None

class MatchResult(BaseModel):
    total: int
    candidates: List[CandidateMatch] = []


class ConfirmMatchRequest(BaseModel):
    risk_record_id: int
    chosen_candidate_id: Optional[int] = None

class RiskHistoryItem(BaseModel):
    """
    Um registo individual de histórico de risco.
    Campos alinhados, de forma genérica, com o modelo RiskRecord.
    Todos opcionais para evitar erros de validação.
    """
    id: Optional[int] = None
    name: Optional[str] = None
    nif: Optional[str] = None
    passport: Optional[str] = None
    resident_card: Optional[str] = None
    risk_level: Optional[str] = None
    risk_score: Optional[float] = None
    created_at: Optional[datetime] = None

    # Permite criar directamente a partir do modelo SQLAlchemy, se usado
    model_config = ConfigDict(from_attributes=True)


class RiskHistoryResponse(BaseModel):
    """
    Resposta do endpoint de histórico de risco.

    Deixamos tudo opcional / com default para ser compatível
    com praticamente qualquer dict que o main.py devolva.
    """
    identifier: Optional[str] = None
    history: List[RiskHistoryItem] = []
    total: Optional[int] = None

class RiskDetailResponse(BaseModel):
    """
    Detalhe de uma análise de risco específica.

    Campos todos opcionais / com default, para ser compatível
    com quase qualquer forma de retorno do main.py.
    """
    id: Optional[int] = None              # id do RiskRecord, se existir
    request: Optional[RiskCheckRequest] = None  # dados de entrada da análise
    score: Optional[float] = None         # score calculado (0–100)
    level: Optional[str] = None           # nível de risco ("LOW", "MEDIUM", "HIGH", etc.)
    factors: List[str] = []               # lista de factores/motivos
    candidates: List[CandidateMatch] = [] # candidatos considerados
    history: List[RiskHistoryItem] = []   # histórico associado (se usado)
