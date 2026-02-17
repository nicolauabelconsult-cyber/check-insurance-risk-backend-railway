"""0002_underwriting_tables

Revision ID: 0002_underwriting_tables
Revises: 0001_initial
Create Date: 2026-02-16

Cria tabelas necessárias para histórico de seguros (underwriting) por product_type:
- insurance_policies
- payments
- claims
- cancellations
- fraud_flags

Notas:
- Alinhado com app/models.py e app/services/underwriting.py
- Postgres: usa JSONB quando disponível (fallback JSON)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

try:
    from sqlalchemy.dialects import postgresql
    JSONB = postgresql.JSONB
except Exception:  # pragma: no cover
    JSONB = sa.JSON


revision = "0002_underwriting_tables"
down_revision = "a1c2d3e4f5g6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # insurance_policies
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
    op.create_index("ix_insurance_policies_entity_id", "insurance_policies", ["entity_id"])
    op.create_index("ix_insurance_policies_subject_full_name", "insurance_policies", ["subject_full_name"])
    op.create_index("ix_insurance_policies_subject_bi", "insurance_policies", ["subject_bi"])
    op.create_index("ix_insurance_policies_subject_passport", "insurance_policies", ["subject_passport"])
    op.create_index("ix_insurance_policies_product_type", "insurance_policies", ["product_type"])
    op.create_index("ix_insurance_policies_policy_number", "insurance_policies", ["policy_number"])

    # payments
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
    op.create_index("ix_payments_entity_id", "payments", ["entity_id"])
    op.create_index("ix_payments_subject_full_name", "payments", ["subject_full_name"])
    op.create_index("ix_payments_subject_bi", "payments", ["subject_bi"])
    op.create_index("ix_payments_subject_passport", "payments", ["subject_passport"])
    op.create_index("ix_payments_product_type", "payments", ["product_type"])
    op.create_index("ix_payments_policy_number", "payments", ["policy_number"])

    # claims
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
    op.create_index("ix_claims_entity_id", "claims", ["entity_id"])
    op.create_index("ix_claims_subject_full_name", "claims", ["subject_full_name"])
    op.create_index("ix_claims_subject_bi", "claims", ["subject_bi"])
    op.create_index("ix_claims_subject_passport", "claims", ["subject_passport"])
    op.create_index("ix_claims_product_type", "claims", ["product_type"])
    op.create_index("ix_claims_policy_number", "claims", ["policy_number"])
    op.create_index("ix_claims_claim_number", "claims", ["claim_number"])

    # cancellations
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
    op.create_index("ix_cancellations_entity_id", "cancellations", ["entity_id"])
    op.create_index("ix_cancellations_subject_full_name", "cancellations", ["subject_full_name"])
    op.create_index("ix_cancellations_subject_bi", "cancellations", ["subject_bi"])
    op.create_index("ix_cancellations_subject_passport", "cancellations", ["subject_passport"])
    op.create_index("ix_cancellations_product_type", "cancellations", ["product_type"])
    op.create_index("ix_cancellations_policy_number", "cancellations", ["policy_number"])

    # fraud_flags
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
    op.create_index("ix_fraud_flags_entity_id", "fraud_flags", ["entity_id"])
    op.create_index("ix_fraud_flags_subject_full_name", "fraud_flags", ["subject_full_name"])
    op.create_index("ix_fraud_flags_subject_bi", "fraud_flags", ["subject_bi"])
    op.create_index("ix_fraud_flags_subject_passport", "fraud_flags", ["subject_passport"])
    op.create_index("ix_fraud_flags_product_type", "fraud_flags", ["product_type"])
    op.create_index("ix_fraud_flags_policy_number", "fraud_flags", ["policy_number"])


def downgrade() -> None:
    op.drop_table("fraud_flags")
    op.drop_table("cancellations")
    op.drop_table("claims")
    op.drop_table("payments")
    op.drop_table("insurance_policies")
