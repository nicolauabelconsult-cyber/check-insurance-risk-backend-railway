"""0001_initial

Revision ID: 0001_initial
Revises:
Create Date: 2026-02-11

NOTE:
  Este projecto usa UUID (String) como PKs, alinhado com app/models.py.
  Se já tiveres uma BD antiga (com IDs Integer), o caminho mais limpo é
  recriar a BD (ou dropar tabelas) e correr as migrations novamente.
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- ENTITIES ---
    op.create_table(
        "entities",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    # --- USERS ---
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
        sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    # --- SOURCES ---
    op.create_table(
        "sources",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("collected_from", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    # --- RISKS ---
    op.create_table(
        "risks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("query_name", sa.String(), nullable=True),
        sa.Column("query_bi", sa.String(), nullable=True),
        sa.Column("query_passport", sa.String(), nullable=True),
        sa.Column("query_nationality", sa.String(), nullable=True),
        sa.Column("score", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("matches", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("status", sa.String(), nullable=False, server_default="DRAFT"),
        sa.Column("created_by", sa.String(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    # --- AUDIT LOGS ---
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=True),
        sa.Column("actor_name", sa.String(), nullable=False, server_default="Unknown"),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("entity_name", sa.String(), nullable=True),
        sa.Column("target_ref", sa.String(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("risks")
    op.drop_table("sources")
    op.drop_table("users")
    op.drop_table("entities")
