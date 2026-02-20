"""Merge underwriting and bridge heads (NO-OP)

Revision ID: 0003a_merge_uw_br
Revises: 0003_underwriting_fields, a1c2d3e4f5g6
Create Date: 2026-02-20

NOTE: This project stores Alembic revision IDs in a varchar(32) column (alembic_version.version_num).
So revision IDs must be 32 chars or fewer.
"""

# revision identifiers, used by Alembic.
revision = "0003a_merge_uw_br"
down_revision = ("0003_underwriting_fields", "a1c2d3e4f5g6")
branch_labels = None
depends_on = None


def upgrade():
    # NO-OP merge
    pass


def downgrade():
    # NO-OP merge
    pass
