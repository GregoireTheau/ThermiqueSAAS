"""Add organization report branding.

Revision ID: 003
Revises: 002
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists organization_branding (
            id text primary key,
            organization_id text not null unique,
            logo_url text,
            primary_color text,
            phone text,
            email_contact text,
            website text,
            legal_mention text,
            created_at text not null,
            updated_at text not null,
            foreign key (organization_id) references organizations(id) on delete cascade
        )
        """
    )
    op.execute(
        """
        create trigger if not exists organization_branding_updated_at
        after update on organization_branding
        for each row
        when new.updated_at = old.updated_at
        begin
            update organization_branding
            set updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            where id = old.id;
        end
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrades are not supported for the SaaS MVP.")
