"""Add normalized organization names.

Revision ID: 002
Revises: 001
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy import text


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
    _deduplicate_organizations(connection)
    op.execute(
        """
        create unique index if not exists organizations_normalized_name_idx
        on organizations(normalized_name)
        """
    )


def _deduplicate_organizations(connection) -> None:
    duplicates = connection.execute(
        text(
            """
            select normalized_name
            from organizations
            where normalized_name is not null
            group by normalized_name
            having count(*) > 1
            """,
        ),
    ).fetchall()
    for duplicate in duplicates:
        rows = connection.execute(
            text(
                """
                select id, business_profile_id
                from organizations
                where normalized_name = :normalized_name
                order by created_at, id
                """,
            ),
            {"normalized_name": duplicate.normalized_name},
        ).fetchall()
        profiles = {row.business_profile_id for row in rows}
        if len(profiles) == 1:
            _merge_organization_duplicates(connection, rows)
        else:
            _suffix_mixed_profile_duplicates(connection, duplicate.normalized_name, rows)


def _merge_organization_duplicates(connection, rows) -> None:
    canonical_id = rows[0].id
    duplicate_ids = [row.id for row in rows[1:]]
    for duplicate_id in duplicate_ids:
        connection.execute(
            text(
                """
                update users
                set organization_id = :canonical_id
                where organization_id = :duplicate_id
                """,
            ),
            {"canonical_id": canonical_id, "duplicate_id": duplicate_id},
        )
        connection.execute(
            text(
                """
                update projects
                set organization_id = :canonical_id
                where organization_id = :duplicate_id
                """,
            ),
            {"canonical_id": canonical_id, "duplicate_id": duplicate_id},
        )
        connection.execute(
            text("delete from organizations where id = :duplicate_id"),
            {"duplicate_id": duplicate_id},
        )


def _suffix_mixed_profile_duplicates(connection, normalized_name: str, rows) -> None:
    for index, row in enumerate(rows[1:], start=2):
        connection.execute(
            text(
                """
                update organizations
                set normalized_name = :normalized_name
                where id = :id
                """,
            ),
            {
                "id": row.id,
                "normalized_name": f"{normalized_name}-{row.business_profile_id}-{index}",
            },
        )


def downgrade() -> None:
    raise NotImplementedError("Downgrades are not supported for the SaaS MVP.")
