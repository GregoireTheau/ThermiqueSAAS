"""Add session expiration.

Revision ID: 004
Revises: 003
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    columns = {column["name"] for column in inspect(connection).get_columns("sessions")}
    if "expires_at" not in columns:
        op.add_column("sessions", sa.Column("expires_at", sa.Text()))
    op.execute(
        """
        update sessions
        set expires_at = strftime('%Y-%m-%dT%H:%M:%SZ', created_at, '+12 hours')
        where expires_at is null
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrades are not supported for the SaaS MVP.")
