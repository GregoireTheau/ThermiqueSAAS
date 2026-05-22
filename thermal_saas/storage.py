"""SQLite storage for the first persistent ThermalTwin SaaS slice."""

from __future__ import annotations

import json
import os
import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from alembic import command
from alembic.config import Config

from .business_flow import run_profile_experience
from .business_profiles import load_business_profile


DEFAULT_DB_PATH = Path("outputs/thermal_saas.sqlite")
DEFAULT_SESSION_TTL_HOURS = 12


class StorageError(ValueError):
    """Raised when stored SaaS data is missing or inconsistent."""


class AuthError(ValueError):
    """Raised when authentication fails."""


def default_db_path() -> Path:
    """Return the configured SQLite path."""
    return Path(os.environ.get("THERMAL_SAAS_DB_PATH", DEFAULT_DB_PATH))


def init_db(db_path: str | Path | None = None) -> None:
    """Create or migrate the SQLite schema."""
    path = Path(db_path or default_db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    config.attributes["db_path"] = str(path)
    command.upgrade(config, "head")


def register_user_with_organization(
    email: str,
    password: str,
    organization_name: str,
    business_profile_id: str,
    name: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Create or join an organization, then create a user and session."""
    _secret_key()
    if len(password) < 8:
        raise AuthError("Password must contain at least 8 characters.")
    init_db(db_path)
    organization = get_organization_by_name(organization_name, db_path)
    if organization is None:
        organization = create_organization(organization_name, business_profile_id, db_path)
    elif organization["business_profile_id"] != business_profile_id:
        raise AuthError("Organization already exists with a different business profile.")
    email = email.strip().lower()
    user = {
        "id": _new_id("usr"),
        "organization_id": organization["id"],
        "email": email,
        "name": name or email,
        "password_hash": _hash_password(password),
        "created_at": _now(),
    }
    try:
        with _connect(db_path or default_db_path()) as connection:
            connection.execute(
                """
                insert into users
                    (id, organization_id, email, name, password_hash, created_at)
                values
                    (:id, :organization_id, :email, :name, :password_hash, :created_at)
                """,
                user,
            )
    except sqlite3.IntegrityError as exc:
        raise AuthError("A user with this email already exists.") from exc
    return _auth_payload(_user_record_to_api(user), organization, db_path)


def login_user(
    email: str,
    password: str,
    organization_name: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Authenticate a user and create a session token."""
    _secret_key()
    init_db(db_path)
    with _connect(db_path or default_db_path()) as connection:
        row = connection.execute(
            "select * from users where email = ?",
            (email.strip().lower(),),
        ).fetchone()
    if row is None:
        raise AuthError("Invalid email or password.")
    user = dict(row)
    if not _verify_password(password, user["password_hash"]):
        raise AuthError("Invalid email or password.")
    organization = get_organization(user["organization_id"], db_path)
    if organization_name and organization["normalized_name"] != _normalize_organization_name(
        organization_name,
    ):
        raise AuthError("This user does not belong to the selected organization.")
    return _auth_payload(_user_record_to_api(user), organization, db_path)


def get_user_by_token(
    token: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return the authenticated user for a bearer token."""
    init_db(db_path)
    token_hash = _hash_token(token)
    with _connect(db_path or default_db_path()) as connection:
        row = connection.execute(
            """
            select
                users.*,
                organizations.business_profile_id as business_profile_id
            from sessions
            join users on users.id = sessions.user_id
            join organizations on organizations.id = users.organization_id
            where sessions.token_hash = ?
              and sessions.revoked_at is null
              and sessions.expires_at > ?
            """,
            (token_hash, _now()),
        ).fetchone()
    if row is None:
        raise AuthError("Invalid or expired session.")
    return _user_record_to_api(dict(row))


def revoke_session(
    token: str,
    db_path: str | Path | None = None,
) -> None:
    """Revoke a bearer token."""
    init_db(db_path)
    with _connect(db_path or default_db_path()) as connection:
        connection.execute(
            """
            update sessions
            set revoked_at = ?
            where token_hash = ? and revoked_at is null
            """,
            (_now(), _hash_token(token)),
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
        "name": name.strip(),
        "normalized_name": _normalize_organization_name(name),
        "business_profile_id": business_profile_id,
        "created_at": _now(),
    }
    with _connect(db_path or default_db_path()) as connection:
        connection.execute(
            """
            insert into organizations (id, name, normalized_name, business_profile_id, created_at)
            values (:id, :name, :normalized_name, :business_profile_id, :created_at)
            """,
            organization,
        )
    return organization


def get_organization_by_name(
    name: str,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Return an organization by normalized name, if it exists."""
    init_db(db_path)
    with _connect(db_path or default_db_path()) as connection:
        row = connection.execute(
            "select * from organizations where normalized_name = ?",
            (_normalize_organization_name(name),),
        ).fetchone()
    return dict(row) if row else None


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


def list_organizations(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    """List organizations ordered by creation date."""
    init_db(db_path)
    with _connect(db_path or default_db_path()) as connection:
        rows = connection.execute(
            "select * from organizations order by created_at desc",
        ).fetchall()
    return [dict(row) for row in rows]


def list_projects(
    organization_id: str | None = None,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """List projects, optionally scoped to one organization."""
    init_db(db_path)
    if organization_id:
        get_organization(organization_id, db_path)
        query = """
            select
                projects.*,
                organizations.business_profile_id as business_profile_id
            from projects
            join organizations on organizations.id = projects.organization_id
            where projects.organization_id = ?
            order by projects.created_at desc
        """
        params = (organization_id,)
    else:
        query = """
            select
                projects.*,
                organizations.business_profile_id as business_profile_id
            from projects
            join organizations on organizations.id = projects.organization_id
            order by projects.created_at desc
        """
        params = ()
    with _connect(db_path or default_db_path()) as connection:
        rows = connection.execute(query, params).fetchall()
    return [dict(row) for row in rows]


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
    organization = get_organization(project["organization_id"], db_path)
    branding = get_organization_branding(project["organization_id"], db_path)
    result = run_profile_experience(
        project["business_profile_id"],
        answers_record["answers"],
        include_report_html=True,
        report_branding=_report_branding_payload(organization, branding),
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


def get_organization_branding(
    organization_id: str,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Return report branding for an organization, if configured."""
    init_db(db_path)
    get_organization(organization_id, db_path)
    with _connect(db_path or default_db_path()) as connection:
        row = connection.execute(
            "select * from organization_branding where organization_id = ?",
            (organization_id,),
        ).fetchone()
    return dict(row) if row else None


def upsert_organization_branding(
    organization_id: str,
    payload: dict[str, Any],
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Create or update nullable report branding fields for an organization."""
    init_db(db_path)
    get_organization(organization_id, db_path)
    now = _now()
    record = {
        "id": _new_id("brd"),
        "organization_id": organization_id,
        "logo_url": _blank_to_none(payload.get("logo_url")),
        "primary_color": _blank_to_none(payload.get("primary_color")),
        "phone": _blank_to_none(payload.get("phone")),
        "email_contact": _blank_to_none(payload.get("email_contact")),
        "website": _blank_to_none(payload.get("website")),
        "legal_mention": _blank_to_none(payload.get("legal_mention")),
        "created_at": now,
        "updated_at": now,
    }
    with _connect(db_path or default_db_path()) as connection:
        connection.execute(
            """
            insert into organization_branding
                (
                    id, organization_id, logo_url, primary_color, phone,
                    email_contact, website, legal_mention, created_at, updated_at
                )
            values
                (
                    :id, :organization_id, :logo_url, :primary_color, :phone,
                    :email_contact, :website, :legal_mention, :created_at, :updated_at
                )
            on conflict(organization_id) do update set
                logo_url = excluded.logo_url,
                primary_color = excluded.primary_color,
                phone = excluded.phone,
                email_contact = excluded.email_contact,
                website = excluded.website,
                legal_mention = excluded.legal_mention,
                updated_at = excluded.updated_at
            """,
            record,
        )
    branding = get_organization_branding(organization_id, db_path)
    if branding is None:
        raise StorageError("Unable to save organization branding.")
    return branding


def project_belongs_to_organization(
    project_id: str,
    organization_id: str,
    db_path: str | Path | None = None,
) -> bool:
    """Return whether a project belongs to an organization."""
    try:
        project = get_project(project_id, db_path)
    except StorageError:
        return False
    return project["organization_id"] == organization_id


def simulation_belongs_to_organization(
    simulation_run_id: str,
    organization_id: str,
    db_path: str | Path | None = None,
) -> bool:
    """Return whether a simulation run belongs to an organization."""
    try:
        simulation = get_simulation_run(simulation_run_id, db_path)
        project = get_project(simulation["project_id"], db_path)
    except StorageError:
        return False
    return project["organization_id"] == organization_id


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


def _auth_payload(
    user: dict[str, Any],
    organization: dict[str, Any],
    db_path: str | Path | None,
) -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    session = {
        "id": _new_id("ses"),
        "user_id": user["id"],
        "token_hash": _hash_token(token),
        "created_at": _now(),
        "expires_at": _session_expires_at(),
    }
    with _connect(db_path or default_db_path()) as connection:
        connection.execute(
            """
            insert into sessions (id, user_id, token_hash, created_at, expires_at)
            values (:id, :user_id, :token_hash, :created_at, :expires_at)
            """,
            session,
        )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": session["expires_at"],
        "user": user,
        "organization": organization,
    }


def _report_branding_payload(
    organization: dict[str, Any],
    branding: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if branding is None:
        return None
    if not any(
        branding.get(field)
        for field in (
            "logo_url",
            "primary_color",
            "phone",
            "email_contact",
            "website",
            "legal_mention",
        )
    ):
        return None
    return {
        "organization_name": organization["name"],
        "logo_url": branding.get("logo_url"),
        "primary_color": branding.get("primary_color"),
        "phone": branding.get("phone"),
        "email_contact": branding.get("email_contact"),
        "website": branding.get("website"),
        "legal_mention": branding.get("legal_mention"),
    }


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _user_record_to_api(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "organization_id": record["organization_id"],
        "email": record["email"],
        "name": record["name"],
        "business_profile_id": record.get("business_profile_id"),
        "created_at": record["created_at"],
    }


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    algorithm, salt, expected = stored_hash.split("$", 2)
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return hmac.compare_digest(digest.hex(), expected)


def _hash_token(token: str) -> str:
    secret_key = _secret_key()
    return hmac.new(secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()


def _secret_key() -> str:
    secret_key = os.environ.get("THERMAL_SAAS_SECRET_KEY")
    if secret_key:
        return secret_key
    if os.environ.get("THERMAL_SAAS_ENV") == "production":
        raise AuthError("THERMAL_SAAS_SECRET_KEY is required in production.")
    return "thermal-saas-dev-secret-change-me"


def _session_expires_at() -> str:
    try:
        ttl_hours = int(os.environ.get("THERMAL_SAAS_SESSION_TTL_HOURS", DEFAULT_SESSION_TTL_HOURS))
    except ValueError:
        ttl_hours = DEFAULT_SESSION_TTL_HOURS
    return (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()


def _normalize_organization_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
