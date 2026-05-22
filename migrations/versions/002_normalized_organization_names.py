"""Add normalized organization names.

Revision ID: 002
Revises: 001
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    columns = {column["name"] for column in inspect(connection).get_columns("organizations")}
    if "normalized_name" not in columns:
        op.add_column("organizations", sa.Column("normalized_name", sa.Text()))
    op.execute(
        """
        update organizations
        set normalized_name = lower(trim(name))
        where normalized_name is null
        """
    )
    op.execute(
        """
        create unique index if not exists organizations_normalized_name_idx
        on organizations(normalized_name)
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrades are not supported for the SaaS MVP.")
