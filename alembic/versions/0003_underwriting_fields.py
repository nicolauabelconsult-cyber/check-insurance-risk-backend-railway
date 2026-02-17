"""0003_underwriting_fields

Revision ID: 0003_underwriting_fields
Revises: 0002_underwriting_tables
Create Date: 2026-02-16

Adiciona campos derivados de underwriting na tabela risks.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

try:
    from sqlalchemy.dialects import postgresql
    JSONB = postgresql.JSONB
except Exception:  # pragma: no cover
    JSONB = sa.JSON


revision = "0003_underwriting_fields"
down_revision = "0002_underwriting_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("risks", sa.Column("uw_score", sa.Integer(), nullable=True))
    op.add_column("risks", sa.Column("uw_decision", sa.String(), nullable=True))
    op.add_column("risks", sa.Column("uw_summary", sa.Text(), nullable=True))
    op.add_column("risks", sa.Column("uw_kpis", JSONB, nullable=True))
    op.add_column("risks", sa.Column("uw_factors", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("risks", "uw_factors")
    op.drop_column("risks", "uw_kpis")
    op.drop_column("risks", "uw_summary")
    op.drop_column("risks", "uw_decision")
    op.drop_column("risks", "uw_score")
