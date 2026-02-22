"""bridge legacy revision a1c2d3e4f5g6

Revision ID: a1c2d3e4f5g6
Revises: 0001_initial
Create Date: 2026-02-17

Purpose:
- Some existing deployments have alembic_version='a1c2d3e4f5g6' recorded in the database.
- This file re-introduces that revision so Alembic can resolve the current DB state and continue upgrading.

This migration is intentionally a NO-OP.
Schema changes are handled by subsequent revisions.
"""

from __future__ import annotations

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

revision = "a1c2d3e4f5g6"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # no-op (compatibility bridge)
    pass


def downgrade() -> None:
    # no-op
    pass
