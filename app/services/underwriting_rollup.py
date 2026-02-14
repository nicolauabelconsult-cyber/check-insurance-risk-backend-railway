from collections import defaultdict

def group_by_product_type(policies, payments, claims, cancellations, fraud_flags):
    pol_map = {p.id: p for p in policies}

    def _ptype_from_policy_id(pid):
        p = pol_map.get(pid)
        return getattr(p, "product_type", None) or "N/A"

    out = defaultdict(lambda: {"policies": [], "payments": [], "claims": [], "cancellations": [], "fraud_flags": []})

    for p in policies:
        pt = getattr(p, "product_type", None) or "N/A"
        out[pt]["policies"].append(p)

    for x in payments:
        out[_ptype_from_policy_id(getattr(x, "policy_id", None))]["payments"].append(x)

    for x in claims:
        out[_ptype_from_policy_id(getattr(x, "policy_id", None))]["claims"].append(x)

    for x in cancellations:
        out[_ptype_from_policy_id(getattr(x, "policy_id", None))]["cancellations"].append(x)

    for x in fraud_flags:
        out[_ptype_from_policy_id(getattr(x, "policy_id", None))]["fraud_flags"].append(x)

    return dict(out)
