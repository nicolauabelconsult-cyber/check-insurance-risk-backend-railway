from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

# -----------------------------
# Config institucional (ajustável)
# -----------------------------

DEFAULT_WEIGHTS = {
    "compliance": 0.70,
    "insurance": 0.30,
}

HARD_STOPS = {
    "sanctions_positive": ("RECUSAR", "Correspondência positiva em sanções internacionais (hard-stop)."),
    "fraud_severe": ("RECUSAR", "Indicador de fraude severa (hard-stop)."),
}

ESCALATE_TRIGGERS = {
    "pep_positive": ("ESCALAR", "Sujeito identificado como PEP: exige EDD e validação sénior."),
    "adverse_media_positive": ("ESCALAR", "Media adversa relevante: exige revisão reputacional."),
}


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


# =========================================================
# 1) INSURANCE SCORE (0-100) a partir do insurance_profile
# =========================================================

def insurance_score_from_profile(profile: Dict[str, Any] | None) -> Tuple[int, List[str]]:
    """
    Retorna:
      - insurance_score (0..100)
      - drivers (motivos)
    """
    if not isinstance(profile, dict) or not profile:
        return 0, ["Sem dados de histórico segurável (pagamentos/sinistros/apólices/fraude)."]

    drivers: List[str] = []
    score = 100  # começamos no melhor e penalizamos

    pb = profile.get("payment_behavior") or {}
    ch = profile.get("claims_history") or {}
    active_policies = profile.get("active_policies") or []
    canc = profile.get("cancellations") or []
    fraud = profile.get("fraud_indicators") or []

    # --- Pagamentos ---
    on_time_ratio = _safe_float(pb.get("on_time_ratio"), 0.0)
    late_12m = _safe_int(pb.get("late_payments_12m"), 0)
    defaults_36m = _safe_int(pb.get("defaults_36m"), 0)
    avg_delay = _safe_int(pb.get("avg_delay_days"), 0)

    if on_time_ratio < 0.70:
        score -= 20
        drivers.append("Baixa taxa de pagamentos em dia (<70%).")
    elif on_time_ratio < 0.85:
        score -= 10
        drivers.append("Taxa de pagamentos em dia moderada (70%-85%).")

    if late_12m >= 3:
        score -= 15
        drivers.append("Múltiplos atrasos de pagamento nos últimos 12 meses (>=3).")
    elif late_12m == 2:
        score -= 8
        drivers.append("Atrasos de pagamento nos últimos 12 meses (2).")

    if defaults_36m >= 1:
        score -= 30
        drivers.append("Incumprimento(s) registado(s) nos últimos 36 meses (default).")

    if avg_delay >= 15:
        score -= 10
        drivers.append("Média de atraso elevada (>=15 dias).")
    elif avg_delay >= 7:
        score -= 5
        drivers.append("Média de atraso moderada (7-14 dias).")

    # --- Sinistros ---
    claims_12m = _safe_int(ch.get("claims_12m"), 0)
    claims_36m = _safe_int(ch.get("claims_36m"), 0)
    total_paid_36m = _safe_int(ch.get("total_paid_36m"), 0)
    max_single = _safe_int(ch.get("max_single_claim"), 0)
    freq_risk = str(ch.get("frequency_risk") or "").upper()
    sev_risk = str(ch.get("severity_risk") or "").upper()

    if claims_12m >= 2:
        score -= 15
        drivers.append("Frequência elevada de sinistros nos últimos 12 meses (>=2).")
    elif claims_12m == 1:
        score -= 6
        drivers.append("Registo de sinistro nos últimos 12 meses (1).")

    if claims_36m >= 4:
        score -= 10
        drivers.append("Histórico de sinistros elevado nos últimos 36 meses (>=4).")

    if max_single >= 5_000_000:
        score -= 15
        drivers.append("Severidade elevada: maior sinistro >= 5.000.000 AOA.")
    elif max_single >= 1_000_000:
        score -= 8
        drivers.append("Severidade moderada: maior sinistro >= 1.000.000 AOA.")

    if total_paid_36m >= 10_000_000:
        score -= 12
        drivers.append("Total pago em sinistros elevado (36 meses >= 10.000.000 AOA).")
    elif total_paid_36m >= 3_000_000:
        score -= 6
        drivers.append("Total pago em sinistros moderado (36 meses >= 3.000.000 AOA).")

    if freq_risk == "ALTO":
        score -= 10
        drivers.append("Classificação interna: risco de frequência ALTO.")
    elif freq_risk == "MÉDIO":
        score -= 5
        drivers.append("Classificação interna: risco de frequência MÉDIO.")

    if sev_risk == "ALTO":
        score -= 10
        drivers.append("Classificação interna: risco de severidade ALTO.")
    elif sev_risk == "MÉDIO":
        score -= 5
        drivers.append("Classificação interna: risco de severidade MÉDIO.")

    # --- Cancelamentos ---
    if len(canc) >= 1:
        score -= 8
        drivers.append("Existem registos de cancelamento/rescisão de apólices.")

    # --- Fraude ---
    # Se existir severidade ALTO -> hard-stop (tratado no final_decision)
    if any(str(f.get("severity", "")).upper() == "MÉDIO" for f in fraud):
        score -= 12
        drivers.append("Existem indicadores de fraude com severidade MÉDIO.")

    # --- Apólices ativas ---
    # Não penaliza por existir, mas pode indicar exposição agregada
    if len(active_policies) >= 4:
        score -= 3
        drivers.append("Elevada quantidade de apólices ativas (exposição agregada).")

    # clamp 0..100
    score = max(0, min(100, score))

    if not drivers:
        drivers = ["Histórico segurável favorável ou sem sinais relevantes de agravamento."]

    return score, drivers


# =========================================================
# 2) FINAL SCORE + DECISÃO (hard-stops e gatilhos)
# =========================================================

@dataclass
class FinalDecision:
    compliance_score: int
    insurance_score: int
    final_score: int
    decision: str
    rationale: str
    premium_hint: str
    underwriting_actions: List[str]
    underwriting_conditions: List[str]
    decision_drivers: List[str]


def final_decision(
    *,
    compliance_score: int,
    grouped_matches: Dict[str, List[dict]] | None,
    insurance_profile: Dict[str, Any] | None,
    weights: Dict[str, float] | None = None,
) -> FinalDecision:
    """
    Usa:
      - compliance_score (0..100)
      - grouped_matches: dict com SANÇÕES/PEP/MEDIA ADVERSA/WATCHLISTS/...
      - insurance_profile: dict construído a partir dos Excels
    Produz:
      - final_score e decisão underwriting + ações/condições
    """
    weights = weights or DEFAULT_WEIGHTS

    ins_score, ins_drivers = insurance_score_from_profile(insurance_profile)

    grouped = grouped_matches or {}
    sanctions_positive = any(m.get("match") for m in grouped.get("SANÇÕES", []))
    pep_positive = any(m.get("match") for m in grouped.get("PEP", []))
    adverse_positive = any(m.get("match") for m in grouped.get("MEDIA ADVERSA", []))

    fraud = (insurance_profile or {}).get("fraud_indicators") or []
    fraud_severe = any(str(f.get("severity", "")).upper() == "ALTO" for f in fraud)

    # Hard-stops
    if sanctions_positive:
        return FinalDecision(
            compliance_score=compliance_score,
            insurance_score=ins_score,
            final_score=0,
            decision=HARD_STOPS["sanctions_positive"][0],
            rationale=HARD_STOPS["sanctions_positive"][1],
            premium_hint="Não aplicável (recusa).",
            underwriting_actions=[
                "Bloquear emissão imediata.",
                "Submeter ao Compliance e registar ocorrência (sanções).",
            ],
            underwriting_conditions=[],
            decision_drivers=["SANÇÕES: correspondência positiva."],
        )

    if fraud_severe:
        return FinalDecision(
            compliance_score=compliance_score,
            insurance_score=ins_score,
            final_score=0,
            decision=HARD_STOPS["fraud_severe"][0],
            rationale=HARD_STOPS["fraud_severe"][1],
            premium_hint="Não aplicável (recusa).",
            underwriting_actions=[
                "Bloquear emissão imediata.",
                "Acionar equipa antifraude e validação documental reforçada.",
            ],
            underwriting_conditions=[],
            decision_drivers=["FRAUDE: severidade ALTO."],
        )

    # Weighted final score
    final_score = int(round(
        (compliance_score * float(weights.get("compliance", 0.7))) +
        (ins_score * float(weights.get("insurance", 0.3)))
    ))
    final_score = max(0, min(100, final_score))

    # Base decision thresholds (ajustáveis)
    decision = "ACEITAR"
    rationale = "Perfil global favorável sob condições padrão."
    conditions: List[str] = ["Condições padrão do produto."]
    actions: List[str] = ["Manter monitorização standard e revisão periódica, conforme política."]
    premium_hint = "Sem agravamento recomendado (referência)."

    decision_drivers = []
    # Escalate triggers
    if pep_positive:
        decision = "ESCALAR"
        decision_drivers.append("PEP: gatilho de EDD.")
    if adverse_positive and decision != "ESCALAR":
        decision = "ESCALAR"
        decision_drivers.append("MEDIA ADVERSA: revisão reputacional.")

    # Score-driven
    if final_score >= 75:
        if decision != "ESCALAR":
            decision = "ACEITAR COM CONDIÇÕES"
        rationale = "Score global elevado: recomenda-se mitigação e validação antes de emissão."
        conditions = [
            "Aumentar franquia e/ou ajustar limites conforme produto.",
            "Cláusulas específicas de exclusão, conforme política interna.",
        ]
        actions = [
            "Validação documental adicional e revisão por responsável sénior.",
            "Monitorização reforçada e revisão periódica do risco.",
        ]
        premium_hint = "Sugere-se agravamento do prémio (ex.: +10% a +25%), conforme grelha interna."
    elif final_score >= 55:
        if decision == "ACEITAR":
            decision = "ACEITAR COM CONDIÇÕES"
        rationale = "Score global moderado: emitir com condições e mitigadores."
        conditions = [
            "Ajustar franquia ao perfil.",
            "Definir limites de cobertura e condições de pagamento conforme política.",
        ]
        actions = [
            "Solicitar documentação adicional e validação de informações críticas.",
            "Monitorização reforçada por período definido.",
        ]
        premium_hint = "Sugere-se ajuste moderado do prémio (ex.: +5% a +15%) se histórico justificar."
    else:
        # final_score baixo
        decision = "ESCALAR"
        rationale = "Score global baixo: recomenda-se revisão do comité antes de decisão final."
        conditions = [
            "Rever limites de cobertura e reforçar franquia.",
            "Considerar exclusões adicionais conforme produto.",
        ]
        actions = [
            "Recolher evidências adicionais e validação cruzada de dados.",
            "Revisão por Underwriting + Compliance.",
        ]
        premium_hint = "Sugere-se agravamento significativo e mitigadores fortes, sujeito a aprovação."

    # Inject insurance drivers to decision_drivers (curto)
    decision_drivers.extend(ins_drivers[:5])

    return FinalDecision(
        compliance_score=compliance_score,
        insurance_score=ins_score,
        final_score=final_score,
        decision=decision,
        rationale=rationale,
        premium_hint=premium_hint,
        underwriting_actions=actions,
        underwriting_conditions=conditions,
        decision_drivers=decision_drivers,
    )
