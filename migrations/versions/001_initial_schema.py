"""Initial SaaS schema.

Revision ID: 001
Revises:
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op


revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists organizations (
            id text primary key,
            name text not null,
            business_profile_id text not null,
            created_at text not null
        )
        """
    )
    op.execute(
        """
        create table if not exists projects (
            id text primary key,
            organization_id text not null,
            name text not null,
            customer_name text,
            created_at text not null,
            foreign key (organization_id) references organizations(id)
        )
        """
    )
    op.execute(
        """
        create table if not exists project_answers (
            id text primary key,
            project_id text not null,
            version integer not null,
            business_profile_id text not null,
            answers_json text not null,
            created_at text not null,
            foreign key (project_id) references projects(id)
        )
        """
    )
    op.execute(
        """
        create table if not exists simulation_runs (
            id text primary key,
            project_id text not null,
            answers_id text not null,
            business_profile_id text not null,
            adaptation_id text not null,
            season text not null,
            role text not null,
            status text not null,
            result_json text not null,
            report_html text not null,
            created_at text not null,
            foreign key (project_id) references projects(id),
            foreign key (answers_id) references project_answers(id)
        )
        """
    )
    op.execute(
        """
        create table if not exists users (
            id text primary key,
            organization_id text not null,
            email text not null unique,
            name text not null,
            password_hash text not null,
            created_at text not null,
            foreign key (organization_id) references organizations(id)
        )
        """
    )
    op.execute(
        """
        create table if not exists sessions (
            id text primary key,
            user_id text not null,
            token_hash text not null unique,
            created_at text not null,
            revoked_at text,
            foreign key (user_id) references users(id)
        )
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrades are not supported for the SaaS MVP.")
