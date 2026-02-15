from __future__ import annotations

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.models import Risk


def _normalize_to_product_dict(uw_kpis: Any, uw_factors: Any) -> Dict[str, Any]:
    """
    Aceita vários formatos e devolve SEMPRE:
    {
      "<product_type>": {
        "policies": [...],
        "payments": [...],
        "claims": [...],
        "cancellations": [...],
        "fraud_flags": [...],
        "kpis": {...},
        "factors": {...},
        "summary": "...",
        "score": 0,
        "decision": "..."
      }
    }

    Se não existir product_type (porque o teu Risk guarda só KPIs gerais),
    colocamos tudo em "GERAL".
    """
    out: Dict[str, Any] = {}

    # Se já vier no formato por produto, aceitamos
    if isinstance(uw_kpis, dict):
        # Se tiver cara de por-produto: chaves "AUTO", "SAUDE", etc com dict interno
        # Ex: {"AUTO": {"payments":[], ...}, "SAUDE": {...}}
        looks_like_by_product = False
        for v in uw_kpis.values():
            if isinstance(v, dict):
                if any(k in v for k in ("policies", "payments", "claims", "cancellations", "fraud_flags", "kpis")):
                    looks_like_by_product = True
                    break

        if looks_like_by_product:
            for pt, pack in uw_kpis.items():
                if not isinstance(pack, dict):
                    pack = {"kpis": {"value": pack}}
                out[str(pt)] = {
                    "policies": pack.get("policies", []) or [],
                    "payments": pack.get("payments", []) or [],
                    "claims": pack.get("claims", []) or [],
                    "cancellations": pack.get("cancellations", []) or [],
                    "fraud_flags": pack.get("fraud_flags", []) or [],
                    "kpis": pack.get("kpis", {}) if isinstance(pack.get("kpis", {}), dict) else {"value": pack.get("kpis")},
                    "factors": pack.get("factors", {}) if isinstance(pack.get("factors", {}), dict) else {"value": pack.get("factors")},
                }
            # factors gerais podem entrar por fora
            if isinstance(uw_factors, dict) and uw_factors:
                out.setdefault("GERAL", {"policies": [], "payments": [], "claims": [], "cancellations": [], "fraud_flags": [], "kpis": {}, "factors": {}})
                out["GERAL"]["factors"] = uw_factors
            return out

    # Caso padrão (o teu hoje): KPIs e factors gerais
    out["GERAL"] = {
        "policies": [],
        "payments": [],
        "claims": [],
        "cancellations": [],
        "fraud_flags": [],
        "kpis": uw_kpis if isinstance(uw_kpis, dict) else ({} if uw_kpis is None else {"value": uw_kpis}),
        "factors": uw_factors if isinstance(uw_factors, dict) else ({} if uw_factors is None else {"value": uw_factors}),
    }
    return out


def load_underwriting_by_product(
    db: Session,
    entity_id: str,
    full_name: Optional[str] = None,
    bi: Optional[str] = None,
    passport: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Como ainda não tens tabelas underwriting, buscamos o underwriting NO PRÓPRIO Risk
    (uw_kpis/uw_factors/uw_summary/uw_score/uw_decision).

    Estratégia:
    - Primeiro tenta encontrar o Risk mais recente daquela entidade que combine BI/passport/name.
    - Se não encontrar, devolve {} (PDF mostrará "Sem informações...").
    """
    q = db.query(Risk).filter(Risk.entity_id == entity_id)

    # prioridade: BI > passport > nome
    if bi:
        q = q.filter(Risk.query_bi == bi)
    elif passport:
        q = q.filter(Risk.query_passport == passport)
    elif full_name:
        q = q.filter(Risk.query_name.ilike(f"%{full_name}%"))

    r = q.order_by(Risk.created_at.desc()).first()
    if not r:
        return {}

    by_product = _normalize_to_product_dict(r.uw_kpis, r.uw_factors)

    # Enriquecer com os campos superiores
    for _pt, pack in by_product.items():
        if isinstance(pack, dict):
            pack["summary"] = r.uw_summary
            pack["score"] = r.uw_score
            pack["decision"] = r.uw_decision

    # Se não houver nada mesmo (kpis/factors vazios e listas vazias), devolve {}
    has_any = False
    for pack in by_product.values():
        if not isinstance(pack, dict):
            continue
        if pack.get("policies") or pack.get("payments") or pack.get("claims") or pack.get("cancellations") or pack.get("fraud_flags"):
            has_any = True
            break
        if (pack.get("kpis") and isinstance(pack.get("kpis"), dict) and len(pack["kpis"]) > 0) or (
            pack.get("factors") and isinstance(pack.get("factors"), dict) and len(pack["factors"]) > 0
        ):
            has_any = True
            break
        if pack.get("summary") or pack.get("score") or pack.get("decision"):
            has_any = True
            break

    return by_product if has_any else {}
