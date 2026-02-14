"""add branch and product_type to insurance_policies

Revision ID: 4d2c1f7a8b10
Revises: 9b8c1a2f0c44
Create Date: 2026-02-14 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "4d2c1f7a8b10"
down_revision = "9b8c1a2f0c44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("insurance_policies", sa.Column("branch", sa.String(), nullable=True))
    op.add_column("insurance_policies", sa.Column("product_type", sa.String(), nullable=True))

    op.create_index("ix_insurance_policies_branch", "insurance_policies", ["branch"])
    op.create_index("ix_insurance_policies_product_type", "insurance_policies", ["product_type"])


def downgrade() -> None:
    op.drop_index("ix_insurance_policies_product_type", table_name="insurance_policies")
    op.drop_index("ix_insurance_policies_branch", table_name="insurance_policies")

    op.drop_column("insurance_policies", "product_type")
    op.drop_column("insurance_policies", "branch")
