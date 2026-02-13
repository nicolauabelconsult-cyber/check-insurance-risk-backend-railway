from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from app.insurance_models import (
    InsurancePayment,
    InsuranceClaim,
    InsurancePolicy,
    InsuranceCancellation,
    InsuranceFraudFlag,
)


def _person_filter(entity_id: str, bi: str | None, passport: str | None, full_name: str | None):
    # match por BI/Passaporte; fallback por nome (mais fraco)
    clauses = [InsurancePayment.entity_id == entity_id]  # placeholder, não usado diretamente
    return bi, passport, full_name


def _match_q(model, entity_id: str, bi: str | None, passport: str | None, full_name: str | None):
    base = [model.entity_id == entity_id]
    ident = []
    if bi:
        ident.append(model.bi == bi)
    if passport:
        ident.append(model.passport == passport)

    # se não tiver BI/Passaporte, cai no nome (menos confiável)
    if ident:
        return and_(*base, or_(*ident))
    if full_name:
        return and_(*base, model.full_name.ilike(full_name))
    return and_(*base, model.full_name == "__NO_MATCH__")


def compute_underwriting(
    db: Session,
    entity_id: str,
    bi: str | None,
    passport: str | None,
    full_name: str | None,
) -> dict[str, Any]:
    # -----------------------
    # Payments KPIs
    # -----------------------
    pay_q = db.query(InsurancePayment).filter(_match_q(InsurancePayment, entity_id, bi, passport, full_name))
    total_invoices = pay_q.count()
    paid_invoices = pay_q.filter(InsurancePayment.is_paid.is_(True)).count()
    unpaid_invoices = total_invoices - paid_invoices

    paid_ratio = (paid_invoices / total_invoices) if total_invoices > 0 else None

    # atraso médio (dias) quando pago
    avg_delay = None
    if total_invoices > 0:
        avg_delay = (
            db.query(func.avg(func.date_part("day", InsurancePayment.paid_date - InsurancePayment.due_date)))
            .filter(_match_q(InsurancePayment, entity_id, bi, passport, full_name))
            .filter(InsurancePayment.is_paid.is_(True))
            .filter(InsurancePayment.paid_date.isnot(None))
            .filter(InsurancePayment.due_date.isnot(None))
            .scalar()
        )
        if avg_delay is not None:
            avg_delay = float(avg_delay)

    # -----------------------
    # Claims KPIs
    # -----------------------
    cl_q = db.query(InsuranceClaim).filter(_match_q(InsuranceClaim, entity_id, bi, passport, full_name))
    claims_count = cl_q.count()

    total_paid = cl_q.with_entities(func.coalesce(func.sum(InsuranceClaim.amount_paid), 0)).scalar() or 0
    total_reserved = cl_q.with_entities(func.coalesce(func.sum(InsuranceClaim.amount_reserved), 0)).scalar() or 0

    # -----------------------
    # Policies KPIs
    # -----------------------
    pol_q = db.query(InsurancePolicy).filter(_match_q(InsurancePolicy, entity_id, bi, passport, full_name))
    policies_total = pol_q.count()
    policies_active = pol_q.filter(InsurancePolicy.status.ilike("active")).count() if policies_total > 0 else 0

    total_sum_insured = pol_q.with_entities(func.coalesce(func.sum(InsurancePolicy.sum_insured), 0)).scalar() or 0
    total_premium = pol_q.with_entities(func.coalesce(func.sum(InsurancePolicy.premium), 0)).scalar() or 0

    # -----------------------
    # Cancellations KPIs
    # -----------------------
    canc_q = db.query(InsuranceCancellation).filter(_match_q(InsuranceCancellation, entity_id, bi, passport, full_name))
    cancellations_count = canc_q.count()

    # -----------------------
    # Fraud flags KPIs
    # -----------------------
    fr_q = db.query(InsuranceFraudFlag).filter(_match_q(InsuranceFraudFlag, entity_id, bi, passport, full_name))
    fraud_count = fr_q.count()
    high_fraud = fr_q.filter(InsuranceFraudFlag.severity.ilike("high")).count() if fraud_count > 0 else 0

    # -----------------------
    # Scoring heurístico (pronto para motor real)
    # -----------------------
    factors: list[dict[str, Any]] = []
    score = 0

    # Pagamentos
    if paid_ratio is None:
        factors.append({"categoria": "Pagamentos", "peso": 10, "motivo": "Sem histórico de pagamentos disponível."})
        score += 10
    else:
        if paid_ratio < 0.7:
            factors.append({"categoria": "Pagamentos", "peso": 35, "motivo": f"Baixa taxa de pagamento ({paid_ratio:.0%})."})
            score += 35
        elif paid_ratio < 0.9:
            factors.append({"categoria": "Pagamentos", "peso": 20, "motivo": f"Taxa de pagamento moderada ({paid_ratio:.0%})."})
            score += 20
        else:
            factors.append({"categoria": "Pagamentos", "peso": 5, "motivo": f"Boa taxa de pagamento ({paid_ratio:.0%})."})
            score += 5

    if avg_delay is not None and avg_delay > 10:
        factors.append({"categoria": "Pagamentos", "peso": 10, "motivo": f"Atraso médio elevado ({avg_delay:.0f} dias)."})
        score += 10

    if unpaid_invoices > 0:
        factors.append({"categoria": "Pagamentos", "peso": 10, "motivo": f"Faturas em aberto: {unpaid_invoices}."})
        score += 10

    # Sinistros
    if claims_count >= 3:
        factors.append({"categoria": "Sinistros", "peso": 25, "motivo": f"Frequência de sinistros elevada ({claims_count})."})
        score += 25
    elif claims_count == 2:
        factors.append({"categoria": "Sinistros", "peso": 15, "motivo": "Dois sinistros registados."})
        score += 15
    elif claims_count == 1:
        factors.append({"categoria": "Sinistros", "peso": 8, "motivo": "Um sinistro registado."})
        score += 8
    else:
        factors.append({"categoria": "Sinistros", "peso": 3, "motivo": "Sem sinistros registados."})
        score += 3

    if total_paid and total_paid > 0:
        factors.append({"categoria": "Sinistros", "peso": 10, "motivo": f"Valor pago em sinistros: {int(total_paid)}."})
        score += 10

    # Exposição (apólices)
    if policies_active >= 3:
        factors.append({"categoria": "Exposição", "peso": 15, "motivo": f"Múltiplas apólices ativas ({policies_active})."})
        score += 15
    elif policies_active >= 1:
        factors.append({"categoria": "Exposição", "peso": 7, "motivo": f"Apólices ativas ({policies_active})."})
        score += 7
    else:
        factors.append({"categoria": "Exposição", "peso": 5, "motivo": "Sem apólices ativas registadas."})
        score += 5

    if total_sum_insured and total_sum_insured > 0:
        factors.append({"categoria": "Exposição", "peso": 5, "motivo": f"Soma segurada total: {int(total_sum_insured)}."})
        score += 5

    # Cancelamentos
    if cancellations_count >= 2:
        factors.append({"categoria": "Cancelamentos", "peso": 18, "motivo": f"Cancelamentos recorrentes ({cancellations_count})."})
        score += 18
    elif cancellations_count == 1:
        factors.append({"categoria": "Cancelamentos", "peso": 10, "motivo": "Existe 1 cancelamento anterior."})
        score += 10
    else:
        factors.append({"categoria": "Cancelamentos", "peso": 3, "motivo": "Sem cancelamentos registados."})
        score += 3

    # Fraude
    if high_fraud > 0:
        factors.append({"categoria": "Fraude", "peso": 40, "motivo": f"Red flag de fraude (HIGH): {high_fraud} ocorrência(s)."})
        score += 40
    elif fraud_count > 0:
        factors.append({"categoria": "Fraude", "peso": 20, "motivo": f"Red flags de fraude: {fraud_count}."})
        score += 20
    else:
        factors.append({"categoria": "Fraude", "peso": 2, "motivo": "Sem flags de fraude."})
        score += 2

    # Normalização simples: 0..100
    score = max(0, min(100, score))

    # Decisão
    if score >= 70:
        decision = "RECUSAR ou ACEITAR COM CONDIÇÕES (EDD)"
        decision_short = "ALTO RISCO"
    elif score >= 40:
        decision = "ACEITAR COM CONDIÇÕES"
        decision_short = "RISCO MÉDIO"
    else:
        decision = "ACEITAR (condições padrão)"
        decision_short = "BAIXO RISCO"

    kpis = {
        "pagamentos": {
            "total_faturas": total_invoices,
            "faturas_pagas": paid_invoices,
            "faturas_em_aberto": unpaid_invoices,
            "taxa_pagamento": paid_ratio,
            "atraso_medio_dias": avg_delay,
        },
        "sinistros": {
            "total_sinistros": claims_count,
            "valor_pago_total": int(total_paid or 0),
            "valor_reservado_total": int(total_reserved or 0),
        },
        "apolices": {
            "total_apolices": policies_total,
            "apolices_ativas": policies_active,
            "premio_total": int(total_premium or 0),
            "soma_segurada_total": int(total_sum_insured or 0),
        },
        "cancelamentos": {"total_cancelamentos": cancellations_count},
        "fraude": {"total_flags": fraud_count, "flags_high": high_fraud},
    }

    summary = (
        f"Resultado de subscrição: {decision_short}. "
        f"Score underwriting={score}/100 com base em pagamentos, sinistros, exposição, cancelamentos e fraude."
    )

    return {
        "uw_score": score,
        "uw_decision": decision,
        "uw_summary": summary,
        "uw_kpis": kpis,
        "uw_factors": factors,
    }
