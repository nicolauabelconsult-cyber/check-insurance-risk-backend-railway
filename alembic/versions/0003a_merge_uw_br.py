"""Merge heads: underwriting + bridge (NO-OP)

Revision ID: 0003m_uw_bridge
Revises: 0003_underwriting_fields, a1c2d3e4f5g6
"""

revision = "0003m_uw_bridge"
down_revision = ("0003_underwriting_fields", "a1c2d3e4f5g6")
branch_labels = None
depends_on = None


def upgrade():
    # NO-OP merge
    pass


def downgrade():
    # NO-OP merge
    pass
