"""underwriting tables

Revision ID: uw_0001
Revises: <COLOCA_AQUI_O_TEU_HEAD_ATUAL>
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa

try:
    from sqlalchemy.dialects import postgresql
    JSONB = postgresql.JSONB
except Exception:
    JSONB = sa.JSON

revision = "uw_0001"
down_revision = "<COLOCA_AQUI_O_TEU_HEAD_ATUAL>"
branch_labels = None
depends_on = None


def upgrade():
    # =========================================================
    # insurance_policies
    # =========================================================
    op.create_table(
        "insurance_policies",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id"), nullable=False, index=True),

        # subject identifiers (multi-fonte / multi-pesquisa)
        sa.Column("subject_full_name", sa.String(), nullable=True, index=True),
        sa.Column("subject_bi", sa.String(), nullable=True, index=True),
        sa.Column("subject_passport", sa.String(), nullable=True, index=True),

        # product segmentation
        sa.Column("product_type", sa.String(), nullable=False, index=True),

        # policy details
        sa.Column("policy_number", sa.String(), nullable=True, index=True),
        sa.Column("insurer_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),  # ACTIVE / CANCELLED / EXPIRED / etc
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),

        # values
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("premium_amount", sa.Integer(), nullable=True),
        sa.Column("sum_insured", sa.Integer(), nullable=True),

        # provenance (multi-fonte)
        sa.Column("source_name", sa.String(), nullable=True),
        sa.Column("source_ref", sa.String(), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),

        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # =========================================================
    # payments
    # =========================================================
    op.create_table(
        "payments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id"), nullable=False, index=True),

        sa.Column("subject_full_name", sa.String(), nullable=True, index=True),
        sa.Column("subject_bi", sa.String(), nullable=True, index=True),
        sa.Column("subject_passport", sa.String(), nullable=True, index=True),

        sa.Column("product_type", sa.String(), nullable=False, index=True),
        sa.Column("policy_number", sa.String(), nullable=True, index=True),

        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),  # PAID / LATE / FAILED

        sa.Column("source_name", sa.String(), nullable=True),
        sa.Column("source_ref", sa.String(), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),

        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # =========================================================
    # claims
    # =========================================================
    op.create_table(
        "claims",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id"), nullable=False, index=True),

        sa.Column("subject_full_name", sa.String(), nullable=True, index=True),
        sa.Column("subject_bi", sa.String(), nullable=True, index=True),
        sa.Column("subject_passport", sa.String(), nullable=True, index=True),

        sa.Column("product_type", sa.String(), nullable=False, index=True),
        sa.Column("policy_number", sa.String(), nullable=True, index=True),

        sa.Column("claim_number", sa.String(), nullable=True, index=True),
        sa.Column("loss_date", sa.DateTime(), nullable=True),
        sa.Column("reported_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),  # OPEN / CLOSED / REJECTED
        sa.Column("amount_claimed", sa.Integer(), nullable=True),
        sa.Column("amount_paid", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),

        sa.Column("source_name", sa.String(), nullable=True),
        sa.Column("source_ref", sa.String(), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),

        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # =========================================================
    # cancellations
    # =========================================================
    op.create_table(
        "cancellations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id"), nullable=False, index=True),

        sa.Column("subject_full_name", sa.String(), nullable=True, index=True),
        sa.Column("subject_bi", sa.String(), nullable=True, index=True),
        sa.Column("subject_passport", sa.String(), nullable=True, index=True),

        sa.Column("product_type", sa.String(), nullable=False, index=True),
        sa.Column("policy_number", sa.String(), nullable=True, index=True),

        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),

        sa.Column("source_name", sa.String(), nullable=True),
        sa.Column("source_ref", sa.String(), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),

        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # =========================================================
    # fraud_flags
    # =========================================================
    op.create_table(
        "fraud_flags",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id"), nullable=False, index=True),

        sa.Column("subject_full_name", sa.String(), nullable=True, index=True),
        sa.Column("subject_bi", sa.String(), nullable=True, index=True),
        sa.Column("subject_passport", sa.String(), nullable=True, index=True),

        sa.Column("product_type", sa.String(), nullable=False, index=True),
        sa.Column("policy_number", sa.String(), nullable=True, index=True),

        sa.Column("flag_type", sa.String(), nullable=False),   # e.g. "MULTIPLE_CLAIMS", "DOC_MISMATCH"
        sa.Column("severity", sa.String(), nullable=True),     # LOW/MEDIUM/HIGH
        sa.Column("description", sa.Text(), nullable=True),

        sa.Column("source_name", sa.String(), nullable=True),
        sa.Column("source_ref", sa.String(), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),

        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade():
    op.drop_table("fraud_flags")
    op.drop_table("cancellations")
    op.drop_table("claims")
    op.drop_table("payments")
    op.drop_table("insurance_policies")
