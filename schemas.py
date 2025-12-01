from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel, EmailStr, ConfigDict


# ============================================================
# 0. HELPER (compatibilidade)
# ============================================================

def normalize_text(value: Optional[str]) -> Optional[str]:
    """
    Função helper simples para manter compatibilidade com versões antigas.
    """
    if not value:
        return None
    return value.strip().upper()


# ============================================================
# 1. AUTENTICAÇÃO
# ============================================================

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


# ============================================================
# 2. UTILIZADOR
# ============================================================

class UserRead(BaseModel):
    id: int
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    # Permite criar directamente a partir do modelo SQLAlchemy
    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 3. FONTES DE INFORMAÇÃO
# ============================================================

class InfoSourceRead(BaseModel):
    """
    Para listar fontes de informação no frontend.
    """
    id: int
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None

    # Campos extra são ignorados para não rebentar
    model_config = ConfigDict(from_attributes=True, extra="ignore")


class FonteInfo(BaseModel):
    """
    Estrutura usada no detalhe da análise (risk_detail)
    para listar as fontes que suportam o alerta.
    """
    id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None

    # Campos mais "funcionais" usados no main.py / reporting
    tipo: Optional[str] = None
    ocorrencias: Optional[int] = None
    ultima_atualizacao: Optional[datetime] = None

    # Outros campos possíveis vindos do modelo InfoSource
    source_type: Optional[str] = None
    country: Optional[str] = None
    url: Optional[str] = None
    total_records: Optional[int] = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")


# ============================================================
# 4. RISCO – REQUEST / CANDIDATOS / RESPONSE
# ============================================================

class RiskCheckRequest(BaseModel):
    """
    Payload principal para o endpoint de análise de risco.
    """
    name: str
    nif: Optional[str] = None
    passport: Optional[str] = None
    resident_card: Optional[str] = None
    nationality: Optional[str] = None


class CandidateMatch(BaseModel):
    """
    Representa um candidato devolvido pelo motor de risco.
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
    Minimal, compatível com o frontend actual.
    """
    score: float
    level: str
    factors: List[str] = []
    candidates: List[CandidateMatch] = []


class MatchResult(BaseModel):
    """
    Mantido por compatibilidade com versões antigas.
    Se não for usado, não faz mal ficar aqui.
    """
    total: int
    candidates: List[CandidateMatch] = []


class ConfirmMatchRequest(BaseModel):
    """
    Payload para o endpoint de confirmação de match.
    """
    risk_record_id: int
    chosen_candidate_id: Optional[int] = None


# ============================================================
# 5. HISTÓRICO DE RISCO
# ============================================================

class RiskHistoryItem(BaseModel):
    """
    Um registo individual de histórico de risco.
    Campos genéricos, para funcionar com várias versões do main.py.
    """
    id: Optional[int] = None
    analysis_id: Optional[int] = None  # em algumas versões
    data: Optional[datetime] = None
    nome: Optional[str] = None
    score: Optional[float] = None
    nivel: Optional[str] = None
    decisao: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class HistoricoClienteItem(BaseModel):
    """
    Item específico usado em risk_detail para histórico do cliente.
    """
    data: Optional[datetime] = None
    operacao: Optional[str] = None
    score: Optional[float] = None
    nivel: Optional[str] = None
    decisao: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class RiskHistoryResponse(BaseModel):
    """
    Resposta para endpoints de histórico.
    Suporta tanto 'history' como 'results'.
    """
    identifier: Optional[str] = None
    history: List[RiskHistoryItem] = []
    results: List[RiskHistoryItem] = []
    total: Optional[int] = None


# ============================================================
# 6. DETALHE DO CLIENTE / ANÁLISE
# ============================================================

class ClienteInfo(BaseModel):
    """
    Informação básica sobre o cliente / segurado.

    Inclui campos em português e inglês para ser tolerante a
    diferentes versões de main.py / reporting.
    """
    # nomes
    name: Optional[str] = None
    nome: Optional[str] = None

    # identificadores
    nif: Optional[str] = None
    passport: Optional[str] = None
    passaporte: Optional[str] = None
    resident_card: Optional[str] = None
    cartao_residente: Optional[str] = None

    # país / nacionalidade
    nationality: Optional[str] = None
    nacionalidade: Optional[str] = None

    other_id: Optional[str] = None
    endereco: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class RiskDetailResponse(BaseModel):
    """
    Detalhe de uma análise de risco específica.

    Compatível com o que o main.py monta em risk_detail:
    - id
    - data_analise
    - analista
    - score
    - nivel
    - decisao
    - cliente (ClienteInfo)
    - fontes (List[FonteInfo])
    - principais_riscos (lista de strings)
    - historico_cliente (List[HistoricoClienteItem])
    - relacoes (lista de strings)
    - recomendacoes (texto)
    """
    id: Optional[int] = None
    data_analise: Optional[datetime] = None
    analista: Optional[str] = None
    score: Optional[float] = None
    nivel: Optional[str] = None
    decisao: Optional[str] = None

    cliente: Optional[ClienteInfo] = None
    fontes: List[FonteInfo] = []
    principais_riscos: List[str] = []
    historico_cliente: List[HistoricoClienteItem] = []
    relacoes: List[str] = []
    recomendacoes: Optional[str] = None

# ============================================================
# 2. UTILIZADOR
# ============================================================

class UserRead(BaseModel):
    id: int
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    # Permite criar directamente a partir do modelo SQLAlchemy
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    """
    Payload para criação de utilizadores via /api/users.
    Compatível com o ecrã de Administração:
      - Nome (full_name)
      - Email
      - Password inicial
      - Perfil (role: ADMIN / ANALYST)
    """
    full_name: str
    email: EmailStr
    username: str
    initial_password: str
    role: str  # "ADMIN" ou "ANALYST"

# ============================================================
# 7. DASHBOARD
# ============================================================

class DashboardStats(BaseModel):
    """
    Estatísticas gerais para o dashboard.
    Campos todos opcionais para não rebentar se algo mudar.
    """
    total_clients: Optional[int] = None
    total_risk_records: Optional[int] = None
    high_risk_count: Optional[int] = None
    medium_risk_count: Optional[int] = None
    low_risk_count: Optional[int] = None
    total_info_sources: Optional[int] = None
    last_analysis_at: Optional[datetime] = None

    # Versão alternativa baseada no get_dashboard_stats() que mostraste
    total_analises_hoje: Optional[int] = None
    casos_high_critical: Optional[int] = None
    tempo_medio_analise_segundos: Optional[float] = None
    ultimas_analises: List[Any] = []
