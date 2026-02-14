"""add branch and product_type to insurance_policies

Revision ID: 4d2c1f7a8b10
Revises: 9b8c1a2f0c44
Create Date: 2026-02-13 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "4d2c1f7a8b10"

# ✅ MUDA ISTO para o teu HEAD real se for diferente
down_revision = "9b8c1a2f0c44"

branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nota: no teu primeiro script já existe "product_type".
    # Então aqui vamos adicionar "branch" e (opcionalmente) "insurance_type" se quiseres separar.
    #
    # Se quiseres manter apenas "product_type" como tipo, remove insurance_type.

    # 1) branch (ex: Auto, Vida, Saúde, Viagem, Patrimonial, etc.)
    op.add_column(
        "insurance_policies",
        sa.Column("branch", sa.String(length=50), nullable=True),
    )
    op.create_index(
        "ix_insurance_policies_branch",
        "insurance_policies",
        ["branch"],
    )

    # 2) Se QUISERES separar “ramo” e “tipo”, usa insurance_type.
    #    Se não quiseres, apaga este bloco.
    op.add_column(
        "insurance_policies",
        sa.Column("insurance_type", sa.String(length=50), nullable=True),
    )
    op.create_index(
        "ix_insurance_policies_insurance_type",
        "insurance_policies",
        ["insurance_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_insurance_policies_insurance_type", table_name="insurance_policies")
    op.drop_column("insurance_policies", "insurance_type")

    op.drop_index("ix_insurance_policies_branch", table_name="insurance_policies")
    op.drop_column("insurance_policies", "branch")
