"""add underwriting fields to risk

Revision ID: a1c2d3e4f5g6
Revises: 9b8c1a2f0c44
Create Date: 2026-02-13 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "a1c2d3e4f5g6"
down_revision = "4d2c1f7a8b10"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("risks", sa.Column("uw_score", sa.Integer(), nullable=True))
    op.add_column("risks", sa.Column("uw_decision", sa.String(), nullable=True))
    op.add_column("risks", sa.Column("uw_summary", sa.Text(), nullable=True))
    op.add_column("risks", sa.Column("uw_kpis", sa.JSON(), nullable=True))
    op.add_column("risks", sa.Column("uw_factors", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("risks", "uw_factors")
    op.drop_column("risks", "uw_kpis")
    op.drop_column("risks", "uw_summary")
    op.drop_column("risks", "uw_decision")
    op.drop_column("risks", "uw_score")
