from __future__ import annotations

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session


def load_underwriting_by_product(
    db: Session,
    entity_id: str,
    full_name: Optional[str] = None,
    bi: Optional[str] = None,
    passport: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Agrega underwriting por product_type.
    - Se tabelas/modelos não existirem, devolve {} (não quebra PDF).
    - Quando existirem dados, devolve:
      {
        "AUTOMOVEL": {
          "policies": [...],
          "payments": [...],
          "claims": [...],
          "cancellations": [...],
          "fraud_flags": [...]
        },
        ...
      }
    """
    out: Dict[str, Dict[str, Any]] = {}

    # Importa modelos apenas se existirem (evita ImportError)
    try:
        from app import models  # type: ignore
    except Exception:
        return out

    Policy = getattr(models, "InsurancePolicy", None)
    Payment = getattr(models, "Payment", None)
    Claim = getattr(models, "Claim", None)
    Cancellation = getattr(models, "Cancellation", None)
    FraudFlag = getattr(models, "FraudFlag", None)

    if Policy is None:
        return out

    # Base query policies por entity_id
    q_pol = db.query(Policy).filter(getattr(Policy, "entity_id") == entity_id)

    # Opcional: filtrar por identificadores se campos existirem
    # (tolerante: só aplica se a coluna existir)
    def _maybe_filter(q, model, col, value):
        if value is None:
            return q
        if hasattr(model, col):
            return q.filter(getattr(model, col) == value)
        return q

    q_pol = _maybe_filter(q_pol, Policy, "holder_name", full_name)
    q_pol = _maybe_filter(q_pol, Policy, "holder_bi", bi)
    q_pol = _maybe_filter(q_pol, Policy, "holder_passport", passport)

    policies = q_pol.limit(500).all()

    # Helper: garantir pack por product_type
    def pack(pt: str):
        k = (pt or "N/A").strip() or "N/A"
        out.setdefault(k, {"policies": [], "payments": [], "claims": [], "cancellations": [], "fraud_flags": []})
        return out[k]

    # Policies
    for p in policies:
        pt = getattr(p, "product_type", None) or getattr(p, "insurance_type", None) or "N/A"
        d = {
            "policy_no": getattr(p, "policy_no", None),
            "status": getattr(p, "status", None),
            "start_date": getattr(p, "start_date", None),
            "end_date": getattr(p, "end_date", None),
            "premium": getattr(p, "premium", None),
        }
        pack(str(pt))["policies"].append(d)

    # Se não tiver outros modelos, termina aqui
    if Payment is None and Claim is None and Cancellation is None and FraudFlag is None:
        return out

    # Tenta ligar por policy_id, se existir
    policy_ids = [getattr(p, "id", None) for p in policies if getattr(p, "id", None)]
    if not policy_ids:
        return out

    if Payment is not None:
        rows = db.query(Payment).filter(getattr(Payment, "policy_id").in_(policy_ids)).limit(2000).all()
        for x in rows:
            pt = getattr(x, "product_type", None) or getattr(x, "insurance_type", None)
            if not pt:
                # tenta descobrir product_type via policy_id (fallback simples)
                pt = "N/A"
            d = {"amount": getattr(x, "amount", None), "status": getattr(x, "status", None), "paid_at": getattr(x, "paid_at", None)}
            pack(str(pt))["payments"].append(d)

    if Claim is not None:
        rows = db.query(Claim).filter(getattr(Claim, "policy_id").in_(policy_ids)).limit(2000).all()
        for x in rows:
            pt = getattr(x, "product_type", None) or getattr(x, "insurance_type", None) or "N/A"
            d = {"amount": getattr(x, "amount", None), "occurred_at": getattr(x, "occurred_at", None), "status": getattr(x, "status", None)}
            pack(str(pt))["claims"].append(d)

    if Cancellation is not None:
        rows = db.query(Cancellation).filter(getattr(Cancellation, "policy_id").in_(policy_ids)).limit(2000).all()
        for x in rows:
            pt = getattr(x, "product_type", None) or getattr(x, "insurance_type", None) or "N/A"
            d = {"reason": getattr(x, "reason", None), "cancelled_at": getattr(x, "cancelled_at", None)}
            pack(str(pt))["cancellations"].append(d)

    if FraudFlag is not None:
        rows = db.query(FraudFlag).filter(getattr(FraudFlag, "policy_id").in_(policy_ids)).limit(2000).all()
        for x in rows:
            pt = getattr(x, "product_type", None) or getattr(x, "insurance_type", None) or "N/A"
            d = {"code": getattr(x, "code", None), "severity": getattr(x, "severity", None), "notes": getattr(x, "notes", None)}
            pack(str(pt))["fraud_flags"].append(d)

    return out
