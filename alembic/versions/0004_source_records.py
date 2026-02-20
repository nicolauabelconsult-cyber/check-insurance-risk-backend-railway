from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_source_records"
down_revision = "0003"  # <-- AJUSTAR
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "source_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("subject_name", sa.String(), nullable=False),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_source_records_entity_id", "source_records", ["entity_id"])
    op.create_index("ix_source_records_category", "source_records", ["category"])
    op.create_index("ix_source_records_subject_name", "source_records", ["subject_name"])

    op.create_index(
        "ix_source_records_entity_cat_subject",
        "source_records",
        ["entity_id", "category", "subject_name"],
    )


def downgrade():
    op.drop_index("ix_source_records_entity_cat_subject", table_name="source_records")
    op.drop_index("ix_source_records_subject_name", table_name="source_records")
    op.drop_index("ix_source_records_category", table_name="source_records")
    op.drop_index("ix_source_records_entity_id", table_name="source_records")
    op.drop_table("source_records")
