    # ---------------------------------------
    # Compliance (multi-fonte): usa matches do Risk por agora
    # (quando tiveres compliance_hits, podes trocar para query no DB)
    # ---------------------------------------
    compliance_by_category = None
    try:
        from app.pdfs import _normalize_matches_generic  # type: ignore
        compliance_by_category = _normalize_matches_generic(getattr(r, "matches", None) or [])
    except Exception:
        compliance_by_category = None

    # ---------------------------------------
    # Underwriting (por tipo de seguro) - tenta ligar se existirem modelos
    # Se não existir ainda, não falha e o PDF continua profissional.
    # ---------------------------------------
    underwriting_by_product = None
    try:
        from app.services.underwriting_rollup import group_by_product_type

        # Ajusta os nomes das classes quando já estiverem definidos no teu models.py
        from app.models import InsurancePolicy, Payment, Claim, Cancellation, FraudFlag  # type: ignore

        policies = db.query(InsurancePolicy).filter(InsurancePolicy.entity_id == r.entity_id).limit(200).all()
        payments = db.query(Payment).filter(Payment.entity_id == r.entity_id).limit(200).all()
        claims = db.query(Claim).filter(Claim.entity_id == r.entity_id).limit(200).all()
        cancellations = db.query(Cancellation).filter(Cancellation.entity_id == r.entity_id).limit(200).all()
        fraud_flags = db.query(FraudFlag).filter(FraudFlag.entity_id == r.entity_id).limit(200).all()

        underwriting_by_product = group_by_product_type(policies, payments, claims, cancellations, fraud_flags)
    except Exception:
        underwriting_by_product = None

    # ---------------------------------------
    # PDF (Institutional)
    # ---------------------------------------
    try:
        pdf_bytes = build_risk_pdf_institutional(
            risk=r,
            analyst_name=u.name,
            generated_at=datetime.utcnow(),
            integrity_hash=integrity_hash,
            server_signature=server_signature,
            verify_url=verify_url,
            underwriting_by_product=underwriting_by_product,
            compliance_by_category=compliance_by_category,
            report_title="Relatório Institucional de Risco",
            report_version="v1.0",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {type(e).__name__}: {e}")
