from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.insurance_models import (
    InsurancePayment,
    InsuranceClaim,
    InsurancePolicy,
    InsuranceCancellation,
    InsuranceFraudFlag,
)


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


def _norm(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip()


def _match_query(q, model, *, bi: str | None, passport: str | None, full_name: str | None):
    """
    Estratégia de ligação:
    1) BI (quando existe)
    2) Passaporte (quando existe)
    3) Fallback por nome (like) quando não há BI/passaporte
    """
    if bi:
        # match direto pelo BI
        return q.filter(model.bi == bi)
    if passport:
        return q.filter(model.passport == passport)
    if full_name:
        # fallback (pode dar falsos positivos se nomes comuns)
        return q.filter(model.full_name.ilike(f"%{full_name}%"))
    # sem chaves -> não devolve nada
    return q.filter(False)


def build_insurance_profile(
    db: Session,
    entity_id: str,
    *,
    bi: str | None,
    passport: str | None,
    full_name: str | None,
) -> Dict[str, Any]:
    """
    Constrói o perfil segurável para underwriting a partir de fontes internas (Excel importado).

    Retorna dict:
      payer_score (0..1)
      payment_behavior {...}
      claims_history {...}
      active_policies [...]
      cancellations [...]
      fraud_indicators [...]
    """
    today = datetime.utcnow().date()
    d12 = today - timedelta(days=365)
    d36 = today - timedelta(days=365 * 3)

    # -------------------------
    # Payments
    # -------------------------
    q_pay = db.query(InsurancePayment).filter(InsurancePayment.entity_id == entity_id)
    q_pay = _match_query(q_pay, InsurancePayment, bi=bi, passport=passport, full_name=full_name)
    payments: List[InsurancePayment] = q_pay.all()

    total = len(payments)
    on_time = 0
    delays: List[int] = []
    late_12m = 0
    defaults_36m = 0

    for p in payments:
        due = p.due_date
        paid = p.paid_date
        if due and paid:
            delay = (paid - due).days
            delays.append(delay)
            if delay <= 0:
                on_time += 1
            if due >= d12 and delay > 0:
                late_12m += 1

        # default: vencimento nos últimos 36 meses e não pago
        if due and (not bool(p.is_paid)) and due >= d36:
            defaults_36m += 1

    on_time_ratio = (on_time / total) if total else 0.0
    avg_delay = int(round(sum(delays) / len(delays))) if delays else 0

    # payer_score: 0..1 (simples, determinístico, ajustável depois)
    payer_score = max(0.0, min(1.0, on_time_ratio - (0.05 * late_12m) - (0.15 * defaults_36m)))

    # -------------------------
    # Claims
    # -------------------------
    q_claim = db.query(InsuranceClaim).filter(InsuranceClaim.entity_id == entity_id)
    q_claim = _match_query(q_claim, InsuranceClaim, bi=bi, passport=passport, full_name=full_name)
    claims: List[InsuranceClaim] = q_claim.all()

    claims_12m = 0
    claims_36m = 0
    total_paid_36m = 0
    max_single = 0

    for c in claims:
        cd = c.claim_date
        paid_amt = _safe_int(c.amount_paid, 0)

        if cd and cd >= d12:
            claims_12m += 1
        if cd and cd >= d36:
            claims_36m += 1
            total_paid_36m += paid_amt
            if paid_amt > max_single:
                max_single = paid_amt

    # Classificações simples (ajustáveis por política)
    frequency_risk = "BAIXO"
    if claims_12m >= 2 or claims_36m >= 4:
        frequency_risk = "ALTO"
    elif claims_12m == 1 or claims_36m in (2, 3):
        frequency_risk = "MÉDIO"

    severity_risk = "BAIXO"
    if max_single >= 5_000_000 or total_paid_36m >= 10_000_000:
        severity_risk = "ALTO"
    elif max_single >= 1_000_000 or total_paid_36m >= 3_000_000:
        severity_risk = "MÉDIO"

    # -------------------------
    # Policies
    # -------------------------
    q_pol = db.query(InsurancePolicy).filter(InsurancePolicy.entity_id == entity_id)
    q_pol = _match_query(q_pol, InsurancePolicy, bi=bi, passport=passport, full_name=full_name)
    policies: List[InsurancePolicy] = q_pol.all()

    active_policies: List[Dict[str, Any]] = []
    for p in policies:
        active_policies.append(
            {
                "policy_no": _norm(p.policy_no),
                "type": _norm(p.product_type),
                "status": _norm(p.status),
                "start": p.start_date.isoformat() if p.start_date else "",
                "end": p.end_date.isoformat() if p.end_date else "",
                "premium": _safe_int(p.premium, 0),
                "sum_insured": _safe_int(p.sum_insured, 0),
            }
        )

    # -------------------------
    # Cancellations
    # -------------------------
    q_can = db.query(InsuranceCancellation).filter(InsuranceCancellation.entity_id == entity_id)
    q_can = _match_query(q_can, InsuranceCancellation, bi=bi, passport=passport, full_name=full_name)
    cancellations_db: List[InsuranceCancellation] = q_can.all()

    cancellations: List[Dict[str, Any]] = []
    for x in cancellations_db:
        cancellations.append(
            {
                "policy_no": _norm(x.policy_no),
                "reason": _norm(x.reason),
                "date": x.date.isoformat() if x.date else "",
            }
        )

    # -------------------------
    # Fraud flags
    # -------------------------
    q_fr = db.query(InsuranceFraudFlag).filter(InsuranceFraudFlag.entity_id == entity_id)
    q_fr = _match_query(q_fr, InsuranceFraudFlag, bi=bi, passport=passport, full_name=full_name)
    fraud_db: List[InsuranceFraudFlag] = q_fr.all()

    fraud_indicators: List[Dict[str, Any]] = []
    for f in fraud_db:
        fraud_indicators.append(
            {
                "flag": _norm(f.flag),
                "severity": _norm(f.severity),
                "note": _norm(f.note),
                "date": f.date.isoformat() if f.date else "",
            }
        )

    # Resultado final (snapshot)
    return {
        "payer_score": round(float(payer_score), 2),
        "payment_behavior": {
            "on_time_ratio": round(float(on_time_ratio), 2),
            "late_payments_12m": int(late_12m),
            "defaults_36m": int(defaults_36m),
            "avg_delay_days": int(avg_delay),
            "total_records": int(total),
        },
        "claims_history": {
            "claims_12m": int(claims_12m),
            "claims_36m": int(claims_36m),
            "total_paid_36m": int(total_paid_36m),
            "max_single_claim": int(max_single),
            "frequency_risk": frequency_risk,
            "severity_risk": severity_risk,
            "total_records": int(len(claims)),
        },
        "active_policies": active_policies[:50],
        "cancellations": cancellations[:50],
        "fraud_indicators": fraud_indicators[:50],
        "keys_used": {
            "bi": bi or "",
            "passport": passport or "",
            "full_name": full_name or "",
        },
        "generated_at_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    }
