from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session


# ============================================================
# Underwriting Loader
# - Aggregates by product_type
# - Pulls from DB tables if they exist in app.models
# - Safe: if a model/table does not exist, it is skipped
# ============================================================

def _as_dict(row: Any) -> dict:
    """
    Convert SQLAlchemy model instance to a clean dict.
    Avoids _sa_instance_state.
    """
    if row is None:
        return {}
    d = dict(getattr(row, "__dict__", {}) or {})
    d.pop("_sa_instance_state", None)
    return d


def _get_product_type(row_dict: dict) -> str:
    """
    Normalize product_type naming across multiple schemas.
    """
    for k in ("product_type", "insurance_type", "product", "branch", "line_of_business"):
        v = row_dict.get(k)
        if v:
            return str(v).strip()
    return "N/A"


def _best_identifier_where(
    model: Any,
    entity_id: str,
    full_name: Optional[str],
    bi: Optional[str],
    passport: Optional[str],
) -> List[Tuple[Any, Any]]:
    """
    Build filter list in priority order:
    1) BI
    2) Passport
    3) Full name (contains / ilike)
    Always includes entity_id if present on model.
    """
    filters = []

    # entity_id
    if hasattr(model, "entity_id") and entity_id:
        filters.append((getattr(model, "entity_id"), entity_id))

    # BI
    if bi:
        for k in ("bi", "id_number", "document_number", "national_id", "customer_bi"):
            if hasattr(model, k):
                filters.append((getattr(model, k), bi))
                return filters  # strongest match

    # Passport
    if passport:
        for k in ("passport", "passport_number", "document_number", "id_number", "customer_passport"):
            if hasattr(model, k):
                filters.append((getattr(model, k), passport))
                return filters  # strong match

    # Name (fallback)
    if full_name:
        # ilike if we can
        for k in ("full_name", "name", "customer_name", "insured_name", "policyholder_name"):
            if hasattr(model, k):
                col = getattr(model, k)
                try:
                    filters.append((col.ilike(f"%{full_name}%"), None))  # special marker
                except Exception:
                    filters.append((col, full_name))
                return filters

    return filters


def _query_model(
    db: Session,
    model: Any,
    entity_id: str,
    full_name: Optional[str],
    bi: Optional[str],
    passport: Optional[str],
    limit: int = 200,
) -> List[dict]:
    """
    Query a given model safely.
    Supports both equals filters and ilike filters.
    """
    q = db.query(model)

    filters = _best_identifier_where(model, entity_id, full_name, bi, passport)
    for f in filters:
        col_or_expr, val = f
        # ilike branch uses (expr, None)
        if val is None and str(col_or_expr).lower().find("like") >= 0:
            q = q.filter(col_or_expr)
        else:
            q = q.filter(col_or_expr == val)

    try:
        rows = q.limit(limit).all()
    except Exception:
        return []

    return [_as_dict(r) for r in (rows or [])]


def load_underwriting_by_product(
    db: Session,
    entity_id: str,
    full_name: Optional[str] = None,
    bi: Optional[str] = None,
    passport: Optional[str] = None,
) -> Dict[str, Dict[str, List[dict]]]:
    """
    Returns:
    {
      "<product_type>": {
         "policies": [...],
         "payments": [...],
         "claims": [...],
         "cancellations": [...],
         "fraud_flags": [...]
      }
    }

    If no data exists, returns {} (PDF will display "Sem informações...").
    """
    # Import models lazily (prevents circular imports / missing models)
    try:
        import app.models as models
    except Exception:
        return {}

    # Candidate model class names (support multiple possible names)
    candidates = {
        "policies": ["InsurancePolicy", "Policy", "InsurancePolicies", "PolicyRecord"],
        "payments": ["Payment", "Payments", "PremiumPayment", "PolicyPayment"],
        "claims": ["Claim", "Claims", "InsuranceClaim", "ClaimRecord"],
        "cancellations": ["Cancellation", "Cancellations", "PolicyCancellation"],
        "fraud_flags": ["FraudFlag", "FraudFlags", "FraudIndicator", "FraudSignal"],
    }

    # Resolve available model classes
    resolved: Dict[str, Any] = {}
    for bucket, names in candidates.items():
        for name in names:
            if hasattr(models, name):
                resolved[bucket] = getattr(models, name)
                break  # first match wins

    if not resolved:
        return {}

    # Pull data
    raw: Dict[str, List[dict]] = {k: [] for k in candidates.keys()}

    for bucket, model in resolved.items():
        raw[bucket] = _query_model(
            db=db,
            model=model,
            entity_id=entity_id,
            full_name=full_name,
            bi=bi,
            passport=passport,
        )

    # Group by product_type
    out: Dict[str, Dict[str, List[dict]]] = {}
    for bucket_name, rows in raw.items():
        for row in rows:
            pt = _get_product_type(row)
            out.setdefault(pt, {"policies": [], "payments": [], "claims": [], "cancellations": [], "fraud_flags": []})
            out[pt][bucket_name].append(row)

    # Cleanup: drop empty product_types
    out = {pt: pack for pt, pack in out.items() if any(len(pack[k]) > 0 for k in pack.keys())}

    return out
