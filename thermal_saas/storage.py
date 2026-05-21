"""SQLite storage for the first persistent ThermalTwin SaaS slice."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .business_flow import run_profile_experience
from .business_profiles import load_business_profile


DEFAULT_DB_PATH = Path("outputs/thermal_saas.sqlite")


class StorageError(ValueError):
    """Raised when stored SaaS data is missing or inconsistent."""


def default_db_path() -> Path:
    """Return the configured SQLite path."""
    return Path(os.environ.get("THERMAL_SAAS_DB_PATH", DEFAULT_DB_PATH))


def init_db(db_path: str | Path | None = None) -> None:
    """Create the SQLite schema if needed."""
    path = Path(db_path or default_db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as connection:
        connection.executescript(
            """
            create table if not exists organizations (
                id text primary key,
                name text not null,
                business_profile_id text not null,
                created_at text not null
            );

            create table if not exists projects (
                id text primary key,
                organization_id text not null,
                name text not null,
                customer_name text,
                created_at text not null,
                foreign key (organization_id) references organizations(id)
            );

            create table if not exists project_answers (
                id text primary key,
                project_id text not null,
                version integer not null,
                business_profile_id text not null,
                answers_json text not null,
                created_at text not null,
                foreign key (project_id) references projects(id)
            );

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
            );
            """
        )


def create_organization(
    name: str,
    business_profile_id: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Create an organization tied to one business profile."""
    load_business_profile(business_profile_id)
    init_db(db_path)
    organization = {
        "id": _new_id("org"),
        "name": name,
        "business_profile_id": business_profile_id,
        "created_at": _now(),
    }
    with _connect(db_path or default_db_path()) as connection:
        connection.execute(
            """
            insert into organizations (id, name, business_profile_id, created_at)
            values (:id, :name, :business_profile_id, :created_at)
            """,
            organization,
        )
    return organization


def create_project(
    organization_id: str,
    name: str,
    customer_name: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Create a customer project for an organization."""
    init_db(db_path)
    organization = get_organization(organization_id, db_path)
    project = {
        "id": _new_id("prj"),
        "organization_id": organization["id"],
        "business_profile_id": organization["business_profile_id"],
        "name": name,
        "customer_name": customer_name,
        "created_at": _now(),
    }
    with _connect(db_path or default_db_path()) as connection:
        connection.execute(
            """
            insert into projects (id, organization_id, name, customer_name, created_at)
            values (:id, :organization_id, :name, :customer_name, :created_at)
            """,
            project,
        )
    return project


def get_organization(
    organization_id: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return an organization by id."""
    init_db(db_path)
    with _connect(db_path or default_db_path()) as connection:
        row = connection.execute(
            "select * from organizations where id = ?",
            (organization_id,),
        ).fetchone()
    if row is None:
        raise StorageError(f"Unknown organization: {organization_id}")
    return dict(row)


def get_project(
    project_id: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return a project with organization profile context."""
    init_db(db_path)
    with _connect(db_path or default_db_path()) as connection:
        row = connection.execute(
            """
            select
                projects.*,
                organizations.business_profile_id as business_profile_id
            from projects
            join organizations on organizations.id = projects.organization_id
            where projects.id = ?
            """,
            (project_id,),
        ).fetchone()
    if row is None:
        raise StorageError(f"Unknown project: {project_id}")
    return dict(row)


def save_project_answers(
    project_id: str,
    answers: dict[str, Any],
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Store a new immutable answers version for a project."""
    project = get_project(project_id, db_path)
    with _connect(db_path or default_db_path()) as connection:
        version = (
            connection.execute(
                "select coalesce(max(version), 0) + 1 from project_answers where project_id = ?",
                (project_id,),
            ).fetchone()[0]
        )
        record = {
            "id": _new_id("ans"),
            "project_id": project_id,
            "version": version,
            "business_profile_id": project["business_profile_id"],
            "answers_json": json.dumps(answers, ensure_ascii=False),
            "created_at": _now(),
        }
        connection.execute(
            """
            insert into project_answers
                (id, project_id, version, business_profile_id, answers_json, created_at)
            values
                (:id, :project_id, :version, :business_profile_id, :answers_json, :created_at)
            """,
            record,
        )
    return _answers_record_to_api(record)


def get_latest_project_answers(
    project_id: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return the latest answers version for a project."""
    init_db(db_path)
    with _connect(db_path or default_db_path()) as connection:
        row = connection.execute(
            """
            select * from project_answers
            where project_id = ?
            order by version desc
            limit 1
            """,
            (project_id,),
        ).fetchone()
    if row is None:
        raise StorageError(f"No answers saved for project: {project_id}")
    return _answers_record_to_api(dict(row))


def create_simulation_runs(
    project_id: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run the latest project answers and persist each generated simulation."""
    project = get_project(project_id, db_path)
    answers_record = get_latest_project_answers(project_id, db_path)
    result = run_profile_experience(
        project["business_profile_id"],
        answers_record["answers"],
        include_report_html=True,
    )

    created_runs = []
    with _connect(db_path or default_db_path()) as connection:
        for simulation in result["simulation_runs"]:
            report_html = simulation.pop("report_html")
            record = {
                "id": _new_id("sim"),
                "project_id": project_id,
                "answers_id": answers_record["id"],
                "business_profile_id": project["business_profile_id"],
                "adaptation_id": result["adaptation_id"],
                "season": simulation["season"],
                "role": simulation["role"],
                "status": "completed",
                "result_json": json.dumps(simulation, ensure_ascii=False),
                "report_html": report_html,
                "created_at": _now(),
            }
            connection.execute(
                """
                insert into simulation_runs
                    (
                        id, project_id, answers_id, business_profile_id, adaptation_id,
                        season, role, status, result_json, report_html, created_at
                    )
                values
                    (
                        :id, :project_id, :answers_id, :business_profile_id, :adaptation_id,
                        :season, :role, :status, :result_json, :report_html, :created_at
                    )
                """,
                record,
            )
            created_runs.append(_simulation_record_to_summary(record))

    return {
        "project_id": project_id,
        "answers_id": answers_record["id"],
        "business_profile_id": project["business_profile_id"],
        "adaptation_id": result["adaptation_id"],
        "simulation_runs": created_runs,
    }


def list_project_simulation_runs(
    project_id: str,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """List persisted simulation runs for a project."""
    init_db(db_path)
    with _connect(db_path or default_db_path()) as connection:
        rows = connection.execute(
            """
            select * from simulation_runs
            where project_id = ?
            order by created_at asc
            """,
            (project_id,),
        ).fetchall()
    return [_simulation_record_to_summary(dict(row)) for row in rows]


def get_simulation_run(
    simulation_run_id: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return a persisted simulation run with its JSON result."""
    init_db(db_path)
    with _connect(db_path or default_db_path()) as connection:
        row = connection.execute(
            "select * from simulation_runs where id = ?",
            (simulation_run_id,),
        ).fetchone()
    if row is None:
        raise StorageError(f"Unknown simulation run: {simulation_run_id}")
    record = dict(row)
    return _simulation_record_to_api(record)


def get_simulation_report_html(
    simulation_run_id: str,
    db_path: str | Path | None = None,
) -> str:
    """Return the stored HTML report for a simulation run."""
    return get_simulation_run(simulation_run_id, db_path)["report_html"]


def _connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("pragma foreign_keys = on")
    return connection


def _answers_record_to_api(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "project_id": record["project_id"],
        "version": record["version"],
        "business_profile_id": record["business_profile_id"],
        "answers": json.loads(record["answers_json"]),
        "created_at": record["created_at"],
    }


def _simulation_record_to_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "project_id": record["project_id"],
        "answers_id": record["answers_id"],
        "business_profile_id": record["business_profile_id"],
        "adaptation_id": record["adaptation_id"],
        "season": record["season"],
        "role": record["role"],
        "status": record["status"],
        "created_at": record["created_at"],
    }


def _simulation_record_to_api(record: dict[str, Any]) -> dict[str, Any]:
    payload = _simulation_record_to_summary(record)
    payload["result"] = json.loads(record["result_json"])
    payload["report_html"] = record["report_html"]
    return payload


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
