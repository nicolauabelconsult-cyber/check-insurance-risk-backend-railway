"""add insurance tables

Revision ID: 9b8c1a2f0c44
Revises:
Create Date: 2026-02-13 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "9b8c1a2f0c44"
down_revision = "9b8c1a2f0c44"
branch_labels = None
depends_on = None


def upgrade():
    # -------------------------
    # insurance_payments
    # -------------------------
    op.create_table(
        "insurance_payments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("entity_id", sa.String(), nullable=False),

        sa.Column("bi", sa.String(), nullable=True),
        sa.Column("passport", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=True),

        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.text("false")),

        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_insurance_payments_entity_id", "insurance_payments", ["entity_id"])
    op.create_index("ix_insurance_payments_bi", "insurance_payments", ["bi"])
    op.create_index("ix_insurance_payments_passport", "insurance_payments", ["passport"])
    op.create_index("ix_insurance_payments_full_name", "insurance_payments", ["full_name"])
    op.create_index(
        "ix_payments_entity_bi_pass",
        "insurance_payments",
        ["entity_id", "bi", "passport"],
    )

    # -------------------------
    # insurance_claims
    # -------------------------
    op.create_table(
        "insurance_claims",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("entity_id", sa.String(), nullable=False),

        sa.Column("bi", sa.String(), nullable=True),
        sa.Column("passport", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=True),

        sa.Column("claim_date", sa.Date(), nullable=True),
        sa.Column("claim_type", sa.String(), nullable=True),
        sa.Column("amount_paid", sa.Integer(), nullable=True),
        sa.Column("amount_reserved", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),

        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_insurance_claims_entity_id", "insurance_claims", ["entity_id"])
    op.create_index("ix_insurance_claims_bi", "insurance_claims", ["bi"])
    op.create_index("ix_insurance_claims_passport", "insurance_claims", ["passport"])
    op.create_index("ix_insurance_claims_full_name", "insurance_claims", ["full_name"])
    op.create_index(
        "ix_claims_entity_bi_pass",
        "insurance_claims",
        ["entity_id", "bi", "passport"],
    )

    # -------------------------
    # insurance_policies
    # -------------------------
    op.create_table(
        "insurance_policies",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("entity_id", sa.String(), nullable=False),

        sa.Column("bi", sa.String(), nullable=True),
        sa.Column("passport", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=True),

        sa.Column("policy_no", sa.String(), nullable=False),
        sa.Column("product_type", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),

        sa.Column("premium", sa.Integer(), nullable=True),
        sa.Column("sum_insured", sa.Integer(), nullable=True),

        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_insurance_policies_entity_id", "insurance_policies", ["entity_id"])
    op.create_index("ix_insurance_policies_bi", "insurance_policies", ["bi"])
    op.create_index("ix_insurance_policies_passport", "insurance_policies", ["passport"])
    op.create_index("ix_insurance_policies_full_name", "insurance_policies", ["full_name"])
    op.create_index("ix_insurance_policies_policy_no", "insurance_policies", ["policy_no"])
    op.create_index(
        "ix_policies_entity_bi_pass",
        "insurance_policies",
        ["entity_id", "bi", "passport"],
    )

    # -------------------------
    # insurance_cancellations
    # -------------------------
    op.create_table(
        "insurance_cancellations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("entity_id", sa.String(), nullable=False),

        sa.Column("bi", sa.String(), nullable=True),
        sa.Column("passport", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=True),

        sa.Column("policy_no", sa.String(), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),

        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_insurance_cancellations_entity_id", "insurance_cancellations", ["entity_id"])
    op.create_index("ix_insurance_cancellations_bi", "insurance_cancellations", ["bi"])
    op.create_index("ix_insurance_cancellations_passport", "insurance_cancellations", ["passport"])
    op.create_index("ix_insurance_cancellations_full_name", "insurance_cancellations", ["full_name"])
    op.create_index("ix_insurance_cancellations_policy_no", "insurance_cancellations", ["policy_no"])
    op.create_index(
        "ix_cancel_entity_bi_pass",
        "insurance_cancellations",
        ["entity_id", "bi", "passport"],
    )

    # -------------------------
    # insurance_fraud_flags
    # -------------------------
    op.create_table(
        "insurance_fraud_flags",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("entity_id", sa.String(), nullable=False),

        sa.Column("bi", sa.String(), nullable=True),
        sa.Column("passport", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=True),

        sa.Column("flag", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),

        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_insurance_fraud_flags_entity_id", "insurance_fraud_flags", ["entity_id"])
    op.create_index("ix_insurance_fraud_flags_bi", "insurance_fraud_flags", ["bi"])
    op.create_index("ix_insurance_fraud_flags_passport", "insurance_fraud_flags", ["passport"])
    op.create_index("ix_insurance_fraud_flags_full_name", "insurance_fraud_flags", ["full_name"])
    op.create_index(
        "ix_fraud_entity_bi_pass",
        "insurance_fraud_flags",
        ["entity_id", "bi", "passport"],
    )


def downgrade():
    op.drop_index("ix_fraud_entity_bi_pass", table_name="insurance_fraud_flags")
    op.drop_index("ix_insurance_fraud_flags_full_name", table_name="insurance_fraud_flags")
    op.drop_index("ix_insurance_fraud_flags_passport", table_name="insurance_fraud_flags")
    op.drop_index("ix_insurance_fraud_flags_bi", table_name="insurance_fraud_flags")
    op.drop_index("ix_insurance_fraud_flags_entity_id", table_name="insurance_fraud_flags")
    op.drop_table("insurance_fraud_flags")

    op.drop_index("ix_cancel_entity_bi_pass", table_name="insurance_cancellations")
    op.drop_index("ix_insurance_cancellations_policy_no", table_name="insurance_cancellations")
    op.drop_index("ix_insurance_cancellations_full_name", table_name="insurance_cancellations")
    op.drop_index("ix_insurance_cancellations_passport", table_name="insurance_cancellations")
    op.drop_index("ix_insurance_cancellations_bi", table_name="insurance_cancellations")
    op.drop_index("ix_insurance_cancellations_entity_id", table_name="insurance_cancellations")
    op.drop_table("insurance_cancellations")

    op.drop_index("ix_policies_entity_bi_pass", table_name="insurance_policies")
    op.drop_index("ix_insurance_policies_policy_no", table_name="insurance_policies")
    op.drop_index("ix_insurance_policies_full_name", table_name="insurance_policies")
    op.drop_index("ix_insurance_policies_passport", table_name="insurance_policies")
    op.drop_index("ix_insurance_policies_bi", table_name="insurance_policies")
    op.drop_index("ix_insurance_policies_entity_id", table_name="insurance_policies")
    op.drop_table("insurance_policies")

    op.drop_index("ix_claims_entity_bi_pass", table_name="insurance_claims")
    op.drop_index("ix_insurance_claims_full_name", table_name="insurance_claims")
    op.drop_index("ix_insurance_claims_passport", table_name="insurance_claims")
    op.drop_index("ix_insurance_claims_bi", table_name="insurance_claims")
    op.drop_index("ix_insurance_claims_entity_id", table_name="insurance_claims")
    op.drop_table("insurance_claims")

    op.drop_index("ix_payments_entity_bi_pass", table_name="insurance_payments")
    op.drop_index("ix_insurance_payments_full_name", table_name="insurance_payments")
    op.drop_index("ix_insurance_payments_passport", table_name="insurance_payments")
    op.drop_index("ix_insurance_payments_bi", table_name="insurance_payments")
    op.drop_index("ix_insurance_payments_entity_id", table_name="insurance_payments")
    op.drop_table("insurance_payments")
