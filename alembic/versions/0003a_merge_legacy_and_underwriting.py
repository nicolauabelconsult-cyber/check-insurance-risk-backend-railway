"""Merge legacy bridge (a1c2d3e4f5g6) with underwriting chain (0003_underwriting_fields)

Revision ID: 0003a_merge_legacy_and_underwriting
Revises: 0003_underwriting_fields, a1c2d3e4f5g6
Create Date: 2026-02-20

This is a NO-OP merge migration to ensure single-head upgrade path on production databases that may
have alembic_version set to either:
- 0003_underwriting_fields (new chain)
- a1c2d3e4f5g6 (legacy bridge)
"""

from alembic import op  # noqa: F401


# revision identifiers, used by Alembic.
revision = "0003a_merge_legacy_and_underwriting"
down_revision = ("0003_underwriting_fields", "a1c2d3e4f5g6")
branch_labels = None
depends_on = None


def upgrade():
    # NO-OP (merge only)
    pass


def downgrade():
    # NO-OP (merge only)
    pass
