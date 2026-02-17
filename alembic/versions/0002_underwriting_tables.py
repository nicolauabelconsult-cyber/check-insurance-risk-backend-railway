"""0002_underwriting_tables

Revision ID: 0002_underwriting_tables
Revises: a1c2d3e4f5g6
Create Date: 2026-02-15

NOTA:
- Este migration foi tornado idempotente para ambientes onde as tabelas de underwriting
  já tenham sido criadas anteriormente (ex.: testes/manuais/branches).
- Em Postgres, evita 'DuplicateTable' no deploy (Render/Railway).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

try:
    from sqlalchemy.dialects import postgresql
    JSONB = postgresql.JSONB
except Exception:
    JSONB = sa.JSON

revision = "0002_underwriting_tables"
down_revision = "a1c2d3e4f5g6"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return table_name in insp.get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    try:
        idxs = insp.get_indexes(table_name) or []
    except Exception:
        return False
    return any(i.get("name") == index_name for i in idxs)


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]):
    if _has_table(table_name) and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    # =========================================================
    # insurance_policies
    # =========================================================
    if not _has_table("insurance_policies"):
        op.create_table(
            "insurance_policies",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),

            sa.Column("subject_full_name", sa.String(), nullable=True),
            sa.Column("subject_bi", sa.String(), nullable=True),
            sa.Column("subject_passport", sa.String(), nullable=True),

            sa.Column("product_type", sa.String(), nullable=False),

            sa.Column("policy_number", sa.String(), nullable=True),
            sa.Column("insurer_name", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("start_date", sa.DateTime(), nullable=True),
            sa.Column("end_date", sa.DateTime(), nullable=True),

            sa.Column("currency", sa.String(), nullable=True),
            sa.Column("premium_amount", sa.Integer(), nullable=True),
            sa.Column("sum_insured", sa.Integer(), nullable=True),

            sa.Column("source_name", sa.String(), nullable=True),
            sa.Column("source_ref", sa.String(), nullable=True),
            sa.Column("raw_payload", JSONB, nullable=True),

            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        )

    _create_index_if_missing("ix_insurance_policies_entity_id", "insurance_policies", ["entity_id"])
    _create_index_if_missing("ix_insurance_policies_subject_full_name", "insurance_policies", ["subject_full_name"])
    _create_index_if_missing("ix_insurance_policies_subject_bi", "insurance_policies", ["subject_bi"])
    _create_index_if_missing("ix_insurance_policies_subject_passport", "insurance_policies", ["subject_passport"])
    _create_index_if_missing("ix_insurance_policies_product_type", "insurance_policies", ["product_type"])
    _create_index_if_missing("ix_insurance_policies_policy_number", "insurance_policies", ["policy_number"])

    # =========================================================
    # payments
    # =========================================================
    if not _has_table("payments"):
        op.create_table(
            "payments",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),

            sa.Column("subject_full_name", sa.String(), nullable=True),
            sa.Column("subject_bi", sa.String(), nullable=True),
            sa.Column("subject_passport", sa.String(), nullable=True),

            sa.Column("product_type", sa.String(), nullable=False),
            sa.Column("policy_number", sa.String(), nullable=True),

            sa.Column("amount", sa.Integer(), nullable=True),
            sa.Column("currency", sa.String(), nullable=True),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.Column("due_at", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),

            sa.Column("source_name", sa.String(), nullable=True),
            sa.Column("source_ref", sa.String(), nullable=True),
            sa.Column("raw_payload", JSONB, nullable=True),

            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        )

    _create_index_if_missing("ix_payments_entity_id", "payments", ["entity_id"])
    _create_index_if_missing("ix_payments_subject_full_name", "payments", ["subject_full_name"])
    _create_index_if_missing("ix_payments_subject_bi", "payments", ["subject_bi"])
    _create_index_if_missing("ix_payments_subject_passport", "payments", ["subject_passport"])
    _create_index_if_missing("ix_payments_product_type", "payments", ["product_type"])
    _create_index_if_missing("ix_payments_policy_number", "payments", ["policy_number"])

    # =========================================================
    # claims
    # =========================================================
    if not _has_table("claims"):
        op.create_table(
            "claims",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),

            sa.Column("subject_full_name", sa.String(), nullable=True),
            sa.Column("subject_bi", sa.String(), nullable=True),
            sa.Column("subject_passport", sa.String(), nullable=True),

            sa.Column("product_type", sa.String(), nullable=False),
            sa.Column("policy_number", sa.String(), nullable=True),

            sa.Column("claim_number", sa.String(), nullable=True),
            sa.Column("loss_date", sa.DateTime(), nullable=True),
            sa.Column("reported_at", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("amount_claimed", sa.Integer(), nullable=True),
            sa.Column("amount_paid", sa.Integer(), nullable=True),
            sa.Column("currency", sa.String(), nullable=True),

            sa.Column("source_name", sa.String(), nullable=True),
            sa.Column("source_ref", sa.String(), nullable=True),
            sa.Column("raw_payload", JSONB, nullable=True),

            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        )

    _create_index_if_missing("ix_claims_entity_id", "claims", ["entity_id"])
    _create_index_if_missing("ix_claims_subject_full_name", "claims", ["subject_full_name"])
    _create_index_if_missing("ix_claims_subject_bi", "claims", ["subject_bi"])
    _create_index_if_missing("ix_claims_subject_passport", "claims", ["subject_passport"])
    _create_index_if_missing("ix_claims_product_type", "claims", ["product_type"])
    _create_index_if_missing("ix_claims_policy_number", "claims", ["policy_number"])
    _create_index_if_missing("ix_claims_claim_number", "claims", ["claim_number"])

    # =========================================================
    # cancellations
    # =========================================================
    if not _has_table("cancellations"):
        op.create_table(
            "cancellations",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),

            sa.Column("subject_full_name", sa.String(), nullable=True),
            sa.Column("subject_bi", sa.String(), nullable=True),
            sa.Column("subject_passport", sa.String(), nullable=True),

            sa.Column("product_type", sa.String(), nullable=False),
            sa.Column("policy_number", sa.String(), nullable=True),

            sa.Column("cancelled_at", sa.DateTime(), nullable=True),
            sa.Column("reason", sa.String(), nullable=True),

            sa.Column("source_name", sa.String(), nullable=True),
            sa.Column("source_ref", sa.String(), nullable=True),
            sa.Column("raw_payload", JSONB, nullable=True),

            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        )

    _create_index_if_missing("ix_cancellations_entity_id", "cancellations", ["entity_id"])
    _create_index_if_missing("ix_cancellations_subject_full_name", "cancellations", ["subject_full_name"])
    _create_index_if_missing("ix_cancellations_subject_bi", "cancellations", ["subject_bi"])
    _create_index_if_missing("ix_cancellations_subject_passport", "cancellations", ["subject_passport"])
    _create_index_if_missing("ix_cancellations_product_type", "cancellations", ["product_type"])
    _create_index_if_missing("ix_cancellations_policy_number", "cancellations", ["policy_number"])

    # =========================================================
    # fraud_flags
    # =========================================================
    if not _has_table("fraud_flags"):
        op.create_table(
            "fraud_flags",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),

            sa.Column("subject_full_name", sa.String(), nullable=True),
            sa.Column("subject_bi", sa.String(), nullable=True),
            sa.Column("subject_passport", sa.String(), nullable=True),

            sa.Column("product_type", sa.String(), nullable=False),
            sa.Column("policy_number", sa.String(), nullable=True),

            sa.Column("flag_type", sa.String(), nullable=False),
            sa.Column("severity", sa.String(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),

            sa.Column("source_name", sa.String(), nullable=True),
            sa.Column("source_ref", sa.String(), nullable=True),
            sa.Column("raw_payload", JSONB, nullable=True),

            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        )

    _create_index_if_missing("ix_fraud_flags_entity_id", "fraud_flags", ["entity_id"])
    _create_index_if_missing("ix_fraud_flags_subject_full_name", "fraud_flags", ["subject_full_name"])
    _create_index_if_missing("ix_fraud_flags_subject_bi", "fraud_flags", ["subject_bi"])
    _create_index_if_missing("ix_fraud_flags_subject_passport", "fraud_flags", ["subject_passport"])
    _create_index_if_missing("ix_fraud_flags_product_type", "fraud_flags", ["product_type"])
    _create_index_if_missing("ix_fraud_flags_policy_number", "fraud_flags", ["policy_number"])


def downgrade() -> None:
    # Downgrade seguro (não falha se já foi removido manualmente)
    op.execute("DROP TABLE IF EXISTS fraud_flags CASCADE")
    op.execute("DROP TABLE IF EXISTS cancellations CASCADE")
    op.execute("DROP TABLE IF EXISTS claims CASCADE")
    op.execute("DROP TABLE IF EXISTS payments CASCADE")
    op.execute("DROP TABLE IF EXISTS insurance_policies CASCADE")
