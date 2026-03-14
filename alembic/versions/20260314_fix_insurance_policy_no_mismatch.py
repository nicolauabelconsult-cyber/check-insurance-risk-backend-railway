"""fix insurance policy_no mismatch

Revision ID: 20260314_fix_insurance_policy_no_mismatch
Revises: 0004_source_records
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260314_fix_ins"
down_revision = "0004_source_records"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    cols = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in cols


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_name = "insurance_policies"

    has_policy_no = _has_column(inspector, table_name, "policy_no")
    has_policy_number = _has_column(inspector, table_name, "policy_number")

    # 1) garantir que policy_number existe
    if not has_policy_number:
        op.add_column(
            table_name,
            sa.Column("policy_number", sa.String(), nullable=True),
        )

    # 2) se existir policy_no, copiar para policy_number quando necessário
    if has_policy_no:
        op.execute(
            """
            UPDATE insurance_policies
            SET policy_number = COALESCE(policy_number, policy_no)
            WHERE policy_number IS NULL
            """
        )

        # 3) remover NOT NULL de policy_no para não bloquear inserts novos
        op.alter_column(
            table_name,
            "policy_no",
            existing_type=sa.String(),
            nullable=True,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_name = "insurance_policies"

    cols = [c["name"] for c in inspector.get_columns(table_name)]
    if "policy_no" in cols:
        op.alter_column(
            table_name,
            "policy_no",
            existing_type=sa.String(),
            nullable=False,
        )
