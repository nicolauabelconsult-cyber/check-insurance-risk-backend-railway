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

