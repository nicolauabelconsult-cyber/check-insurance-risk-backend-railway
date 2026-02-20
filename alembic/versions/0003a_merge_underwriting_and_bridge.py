"""Merge underwriting and bridge heads (NO-OP)

Revision ID: 0003a_merge_underwriting_and_bridge
Revises: 0003_underwriting_fields, a1c2d3e4f5g6
Create Date: 2026-02-20

This is a NO-OP merge migration to ensure a single-head upgrade path on production databases.
"""

revision = "0003a_merge_underwriting_and_bridge"
down_revision = ("0003_underwriting_fields", "a1c2d3e4f5g6")
branch_labels = None
depends_on = None


def upgrade():
    # NO-OP merge
    pass


def downgrade():
    # NO-OP merge
    pass
