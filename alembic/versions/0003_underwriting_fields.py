"""0003_underwriting_fields

Revision ID: 0003_underwriting_fields
Revises: 0002_underwriting_tables
Create Date: 2026-02-16

Adiciona campos derivados de underwriting na tabela risks.
- Idempotente: não falha se colunas já existirem (ambientes com migrações anteriores/parciais).
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


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        cols = insp.get_columns(table_name)
    except Exception:
        return False
    return any(c.get("name") == column_name for c in cols)


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    if not _column_exists(table, column.name):
        op.add_column(table, column)


def _drop_column_if_exists(table: str, column_name: str) -> None:
    if _column_exists(table, column_name):
        op.drop_column(table, column_name)


def upgrade() -> None:
    _add_column_if_missing("risks", sa.Column("uw_score", sa.Integer(), nullable=True))
    _add_column_if_missing("risks", sa.Column("uw_decision", sa.String(), nullable=True))
    _add_column_if_missing("risks", sa.Column("uw_summary", sa.Text(), nullable=True))
    _add_column_if_missing("risks", sa.Column("uw_kpis", JSONB, nullable=True))
    _add_column_if_missing("risks", sa.Column("uw_factors", JSONB, nullable=True))


def downgrade() -> None:
    _drop_column_if_exists("risks", "uw_factors")
    _drop_column_if_exists("risks", "uw_kpis")
    _drop_column_if_exists("risks", "uw_summary")
    _drop_column_if_exists("risks", "uw_decision")
    _drop_column_if_exists("risks", "uw_score")
