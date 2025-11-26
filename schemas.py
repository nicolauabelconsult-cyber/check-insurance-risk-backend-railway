from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, ConfigDict

def normalize_text(value: Optional[str]) -> Optional[str]:
    """
    Mantém compatibilidade com versões antigas do backend.
    Actualmente faz o mesmo que _norm().
    """
    if not value:
        return None
    return value.strip().upper()

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

class InfoSourceRead(BaseModel):
    """
    Schema para devolver informação sobre as Fontes de Informação (InfoSource)
    no frontend.
    """
    id: int
    name: str
    description: Optional[str] = None
    source_type: Optional[str] = None
    file_path: Optional[str] = None
    original_filename: Optional[str] = None
    is_active: Optional[bool] = None
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

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, ConfigDict
# (garante que estas imports já lá estão)

class ClienteInfo(BaseModel):
    """
    Informação básica sobre o cliente / assegurado.
    Campos todos opcionais para ser tolerante a diferentes usos no main.py.
    """
    name: Optional[str] = None
    nif: Optional[str] = None
    passport: Optional[str] = None
    resident_card: Optional[str] = None
    nationality: Optional[str] = None
    other_id: Optional[str] = None  # caso uses algum outro identificador

    # Ignora campos extra que possam vir do código ou do frontend
    model_config = ConfigDict(extra="ignore")

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, ConfigDict

# -------------------------------------------------------
# AUTENTICAÇÃO
# -------------------------------------------------------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


# -------------------------------------------------------
# UTILIZADOR
# -------------------------------------------------------

class UserRead(BaseModel):
    id: int
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------
# RISCO – REQUEST / CANDIDATOS / RESPONSE
# -------------------------------------------------------

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
    """
    score: float
    level: str
    factors: List[str] = []
    candidates: List[CandidateMatch] = []


# -------------------------------------------------------
# HISTÓRICO DE RISCO
# -------------------------------------------------------

class RiskHistoryItem(BaseModel):
    """
    Um item do histórico de análises de risco de um cliente.
    Ajusta os campos conforme a tua tabela RiskRecord.
    """
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    score: Optional[float] = None
    level: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(extra="ignore")

class HistoricoClienteItem(RiskHistoryItem):
    """
    Alias em português para compatibilidade com o main.py.
    Estrutura idêntica a RiskHistoryItem.
    """
    pass

class RiskHistoryResponse(BaseModel):
    """
    Resposta para endpoint que devolve histórico de um identificador.
    """
    identifier: str
    history: List[RiskHistoryItem] = []


# -------------------------------------------------------
# DETALHE DO CLIENTE / ANÁLISE
# -------------------------------------------------------

class ClienteInfo(BaseModel):
    """
    Informação básica sobre o cliente / segurado.
    """
    name: Optional[str] = None
    nif: Optional[str] = None
    passport: Optional[str] = None
    resident_card: Optional[str] = None
    nationality: Optional[str] = None
    other_id: Optional[str] = None

    model_config = ConfigDict(extra="ignore")

class RiskDetailResponse(BaseModel):
    """
    Detalhe completo de uma análise de risco.
    Compatível com o main.py para ver detalhe de um RiskRecord.
    """
    id: Optional[int] = None
    cliente: Optional[ClienteInfo] = None
    request: Optional[RiskCheckRequest] = None
    score: Optional[float] = None
    level: Optional[str] = None
    factors: List[str] = []
    candidates: List[CandidateMatch] = []
    history: List[RiskHistoryItem] = []

class RiskDetailResponse(BaseModel):
    """
    Detalhe de uma análise de risco específica.

    Compatível com a estrutura típica:
    - id: id do registo de risco
    - cliente: informação do cliente (ClienteInfo)
    - score: score de risco
    - level: nível de risco
    - factors: lista de factores
    - candidates: candidatos considerados
    - history: histórico associado
    """
    id: Optional[int] = None
    cliente: Optional[ClienteInfo] = None
    request: Optional[RiskCheckRequest] = None
    score: Optional[float] = None
    level: Optional[str] = None
    factors: List[str] = []
    candidates: List[CandidateMatch] = []
    history: List[RiskHistoryItem] = []

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

class FonteInfo(BaseModel):
    """
    Informação sobre a fonte de dados (InfoSource).
    Ajusta os nomes dos campos conforme a tua tabela/models.InfoSource.
    """
    id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    source_type: Optional[str] = None  # ex.: 'INTERNA', 'PEP', 'SANCTIONS'
    country: Optional[str] = None
    url: Optional[str] = None
    last_updated: Optional[datetime] = None
    total_records: Optional[int] = None

    # Permite criar a partir de modelos SQLAlchemy e ignora campos extra
    model_config = ConfigDict(from_attributes=True, extra="ignore")
