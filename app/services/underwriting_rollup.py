from __future__ import annotations

from collections import defaultdict


def group_by_product_type(policies, payments, claims, cancellations, fraud_flags):
    """
    Retorna:
    {
      "AUTO": {"policies":[...], "payments":[...], "claims":[...], "cancellations":[...], "fraud_flags":[...]},
      "SAUDE": {...}
    }

    Regras:
    - product_type vem preferencialmente de InsurancePolicy
    - tabelas filhas usam policy_id para mapear product_type
    """
    pol_map = {getattr(p, "id", None): p for p in (policies or [])}

    def ptype_from_policy_id(pid):
        p = pol_map.get(pid)
        return getattr(p, "product_type", None) or "N/A"

    out = defaultdict(lambda: {"policies": [], "payments": [], "claims": [], "cancellations": [], "fraud_flags": []})

    for p in policies or []:
        pt = getattr(p, "product_type", None) or "N/A"
        out[pt]["policies"].append(p)

    for x in payments or []:
        out[ptype_from_policy_id(getattr(x, "policy_id", None))]["payments"].append(x)

    for x in claims or []:
        out[ptype_from_policy_id(getattr(x, "policy_id", None))]["claims"].append(x)

    for x in cancellations or []:
        out[ptype_from_policy_id(getattr(x, "policy_id", None))]["cancellations"].append(x)

    for x in fraud_flags or []:
        out[ptype_from_policy_id(getattr(x, "policy_id", None))]["fraud_flags"].append(x)

    return dict(out)
