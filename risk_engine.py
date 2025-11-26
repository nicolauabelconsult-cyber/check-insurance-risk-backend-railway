# risk_engine.py
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from models import RiskRecord, NormalizedEntity, RiskLevel, RiskDecision

# 👉 Substitui estes nomes pelos que aparecem no teu "from risk_engine import (...)"
#    Podes deixar as implementações simples por agora – o objectivo é só o backend arrancar.


def analyze_risk_request(*args, **kwargs) -> Dict[str, Any]:
    """
    Função placeholder: faz uma análise de risco muito simples.
    Depois podemos trocar por lógica real.
    """
    return {
        "score": 10,
        "level": RiskLevel.LOW,
        "factors": [],
        "matches": [],
    }


def confirm_match_and_persist(*args, **kwargs) -> RiskRecord:
    """
    Placeholder: supõe que já houve a análise e devolve um RiskRecord fictício.
    """
    # Aqui poderíamos receber o DB e gravar, mas por agora devolvemos algo mínimo ou None.
    # Na prática, o main.py pode não precisar do retorno.
    raise NotImplementedError("confirm_match_and_persist ainda não foi implementado.")


def get_history_for_identifier(*args, **kwargs) -> List[RiskRecord]:
    """
    Placeholder: devolve lista vazia de histórico, até ligarmos à BD de verdade.
    """
    return []
