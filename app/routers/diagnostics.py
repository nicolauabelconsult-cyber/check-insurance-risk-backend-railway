from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db import get_db
from app.deps import require_perm

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/underwriting")
def underwriting_diagnostics(entity_id: str, db: Session = Depends(get_db), u=Depends(require_perm("risk:read"))):
    # 1) lista tabelas candidatas existentes
    candidates = [
        "insurance_policies",
        "policies",
        "underwriting_policies",
        "payments",
        "claims",
        "cancellations",
        "fraud_flags",
    ]

    tables = {}
    for t in candidates:
        ok = db.execute(
            text("""SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='public' AND table_name=:t
            )"""),
            {"t": t},
        ).scalar()
        if ok:
            cols = db.execute(
                text("""SELECT column_name FROM information_schema.columns
                        WHERE table_schema='public' AND table_name=:t
                        ORDER BY ordinal_position"""),
                {"t": t},
            ).scalars().all()
            tables[t] = cols

    # 2) tenta contar apólices por product_type
    summary = {}
    if "insurance_policies" in tables:
        # tenta descobrir colunas prováveis
        cols = set(tables["insurance_policies"])
        eid_col = "entity_id" if "entity_id" in cols else ("tenant_id" if "tenant_id" in cols else None)
        pt_col = "product_type" if "product_type" in cols else ("branch" if "branch" in cols else None)

        if eid_col and pt_col:
            rows = db.execute(
                text(f"""
                    SELECT COALESCE({pt_col}, 'N/A') AS product_type, COUNT(*) AS n
                    FROM insurance_policies
                    WHERE {eid_col} = :eid
                    GROUP BY COALESCE({pt_col}, 'N/A')
                    ORDER BY n DESC
                """),
                {"eid": entity_id},
            ).mappings().all()
            summary = {"policies_by_product_type": rows, "entity_col": eid_col, "product_type_col": pt_col}
        else:
            summary = {"error": "insurance_policies exists but missing entity_id/tenant_id or product_type/branch columns"}

    return {"entity_id": entity_id, "tables_found": tables, "summary": summary}
