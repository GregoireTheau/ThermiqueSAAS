"""FastAPI entrypoint for the first ThermalTwin SaaS slice."""

from __future__ import annotations

from typing import Any
from datetime import datetime
import logging
import os
from pathlib import Path
import re
import time
import unicodedata

from .business_flow import BusinessFlowError, run_profile_experience
from .business_profiles import (
    build_questionnaire,
    list_business_profiles as load_all_business_profiles,
    load_business_profile,
)
from .storage import (
    AuthError,
    StorageError,
    create_organization,
    create_project,
    create_simulation_runs,
    get_latest_project_answers,
    get_organization_by_name,
    get_organization_branding,
    get_project,
    get_simulation_report_html,
    get_simulation_run,
    get_user_by_token,
    list_organizations as load_organizations,
    list_projects as load_projects,
    list_project_simulation_runs,
    login_user,
    project_belongs_to_organization,
    register_user_with_organization,
    revoke_session,
    save_project_answers,
    simulation_belongs_to_organization,
    upsert_organization_branding,
)
from thermal_model import load_reference_catalog
from .pdf_export import PdfExportError, render_pdf_from_html

try:
    from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    from fastapi.responses import FileResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field
except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional runtime deps
    raise RuntimeError(
        "FastAPI is not installed. Install requirements.txt before running the API.",
    ) from exc


app = FastAPI(title="ThermalTwin SaaS API", version="0.1")
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        host.strip()
        for host in os.environ.get(
            "THERMAL_SAAS_ALLOWED_HOSTS",
            "127.0.0.1,localhost,testserver",
        ).split(",")
        if host.strip()
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get(
            "THERMAL_SAAS_CORS_ORIGINS",
            "http://127.0.0.1:8000,http://127.0.0.1:8010",
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
FILENAME_UNSAFE_RE = re.compile(r"[^a-z0-9]+")
MAX_REQUEST_BYTES = int(os.environ.get("THERMAL_SAAS_MAX_REQUEST_BYTES", "1000000"))
AUTH_COOKIE_NAME = "thermal_saas_session"
AUTH_RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("THERMAL_SAAS_AUTH_RATE_LIMIT_WINDOW_SECONDS", "300"))
AUTH_RATE_LIMIT_ATTEMPTS = int(os.environ.get("THERMAL_SAAS_AUTH_RATE_LIMIT_ATTEMPTS", "10"))
AUTH_RATE_LIMITS: dict[str, list[float]] = {}
logger = logging.getLogger(__name__)


class RegisterPayload(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=200)
    organization_name: str = Field(min_length=1, max_length=120)
    business_profile_id: str = Field(min_length=1, max_length=80)
    name: str | None = Field(default=None, max_length=120)


class LoginPayload(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)
    organization_name: str | None = Field(default=None, max_length=120)


class OrganizationPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    business_profile_id: str = Field(min_length=1, max_length=80)


class ProjectPayload(BaseModel):
    organization_id: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    customer_name: str | None = Field(default=None, max_length=160)


class AnswersPayload(BaseModel):
    answers: dict[str, Any] | None = None


class BrandingPayload(BaseModel):
    logo_url: str | None = None
    primary_color: str | None = Field(default=None, max_length=7)
    phone: str | None = Field(default=None, max_length=30)
    email_contact: str | None = Field(default=None, max_length=120)
    website: str | None = Field(default=None, max_length=200)
    legal_mention: str | None = Field(default=None, max_length=1000)


@app.middleware("http")
async def reject_large_payloads(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_REQUEST_BYTES:
        return Response(
            content='{"detail":"Request payload too large."}',
            status_code=413,
            media_type="application/json",
        )
    return await call_next(request)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()",
    )
    if os.environ.get("THERMAL_SAAS_ENV") == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.get("/")
def redirect_to_app() -> RedirectResponse:
    return RedirectResponse(url="/app")


@app.get("/app")
def get_app() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


def current_user(
    authorization: str | None = Header(default=None),
    session_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
) -> dict[str, Any]:
    token = _auth_token(authorization, session_cookie)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        return get_user_by_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_project_access(project_id: str, user: dict[str, Any]) -> None:
    if not project_belongs_to_organization(project_id, user["organization_id"]):
        raise HTTPException(status_code=404, detail="Unknown project.")


def require_simulation_access(simulation_run_id: str, user: dict[str, Any]) -> None:
    if not simulation_belongs_to_organization(simulation_run_id, user["organization_id"]):
        raise HTTPException(status_code=404, detail="Unknown simulation run.")


@app.get("/business-profiles")
def list_business_profiles() -> dict[str, Any]:
    return {
        "profiles": [
            {
                "id": profile["id"],
                "label": profile["label"],
                "description": profile["description"],
                "allowed_adaptations": profile["allowed_adaptations"],
            }
            for profile in load_all_business_profiles()
        ],
    }


@app.get("/business-profiles/{profile_id}/questionnaire")
def get_questionnaire(profile_id: str) -> dict[str, Any]:
    try:
        profile = load_business_profile(profile_id)
        return build_questionnaire(profile, load_reference_catalog())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/auth/register")
def register_endpoint(payload: RegisterPayload, request: Request, response: Response) -> dict[str, Any]:
    data = _payload_dict(payload)
    _check_auth_rate_limit(request, data["email"])
    try:
        auth_payload = register_user_with_organization(
            email=data["email"],
            password=data["password"],
            organization_name=data["organization_name"],
            business_profile_id=data["business_profile_id"],
            name=data.get("name"),
        )
        _set_auth_cookie(response, auth_payload)
        _log_auth_event("register_success", request, data["email"])
        return auth_payload
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Missing field: {exc.args[0]}") from exc
    except AuthError as exc:
        _log_auth_event("register_failed", request, data["email"])
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/auth/login")
def login_endpoint(payload: LoginPayload, request: Request, response: Response) -> dict[str, Any]:
    data = _payload_dict(payload)
    _check_auth_rate_limit(request, data["email"])
    try:
        auth_payload = login_user(
            data["email"],
            data["password"],
            organization_name=data.get("organization_name"),
        )
        _set_auth_cookie(response, auth_payload)
        _log_auth_event("login_success", request, data["email"])
        return auth_payload
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Missing field: {exc.args[0]}") from exc
    except AuthError as exc:
        _log_auth_event("login_failed", request, data["email"])
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/organizations/lookup")
def lookup_organization_endpoint(name: str) -> dict[str, Any]:
    organization = get_organization_by_name(name)
    if not organization:
        return {"exists": False, "organization": None}
    profile = load_business_profile(organization["business_profile_id"])
    return {
        "exists": True,
        "organization": {
            "id": organization["id"],
            "name": organization["name"],
            "business_profile_id": organization["business_profile_id"],
            "business_profile_label": profile["label"],
        },
    }


@app.get("/auth/me")
def me_endpoint(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {"user": user}


@app.post("/auth/logout")
def logout_endpoint(
    response: Response,
    authorization: str | None = Header(default=None),
    session_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    token = _auth_token(authorization, session_cookie)
    if token:
        revoke_session(token)
    _clear_auth_cookie(response)
    return {"status": "logged_out", "user_id": user["id"]}


@app.post("/business-profiles/{profile_id}/experiences")
def create_profile_experience(profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return run_profile_experience(profile_id, payload)
    except BusinessFlowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/organizations")
def create_organization_endpoint(
    payload: OrganizationPayload,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    data = _payload_dict(payload)
    if user["organization_id"]:
        raise HTTPException(status_code=403, detail="Use /auth/register to create an organization.")
    try:
        return create_organization(
            name=data["name"],
            business_profile_id=data["business_profile_id"],
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Missing field: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/organizations")
def list_organizations_endpoint(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    organizations = [
        organization
        for organization in load_organizations()
        if organization["id"] == user["organization_id"]
    ]
    return {"organizations": organizations}


@app.get("/organization-branding")
def get_organization_branding_endpoint(
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    branding = get_organization_branding(user["organization_id"])
    return {"branding": branding}


@app.put("/organization-branding")
def upsert_organization_branding_endpoint(
    payload: BrandingPayload,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    data = _payload_dict(payload)
    _validate_branding_payload(data)
    return {
        "branding": upsert_organization_branding(
            user["organization_id"],
            data,
        ),
    }


@app.post("/projects")
def create_project_endpoint(
    payload: ProjectPayload,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    data = _payload_dict(payload)
    try:
        organization_id = data.get("organization_id") or user["organization_id"]
        if organization_id != user["organization_id"]:
            raise HTTPException(status_code=403, detail="Cannot create project for this organization.")
        return create_project(
            organization_id=organization_id,
            name=data["name"],
            customer_name=data.get("customer_name"),
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Missing field: {exc.args[0]}") from exc
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects")
def list_projects_endpoint(
    organization_id: str | None = None,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    try:
        scoped_organization_id = organization_id or user["organization_id"]
        if scoped_organization_id != user["organization_id"]:
            raise HTTPException(status_code=403, detail="Cannot list projects for this organization.")
        return {"projects": load_projects(scoped_organization_id)}
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}")
def get_project_endpoint(
    project_id: str,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    try:
        require_project_access(project_id, user)
        project = get_project(project_id)
        latest_answers = None
        try:
            latest_answers = get_latest_project_answers(project_id)
        except StorageError:
            pass
        return {
            "project": project,
            "latest_answers": latest_answers,
            "simulation_runs": list_project_simulation_runs(project_id),
        }
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/answers")
def save_project_answers_endpoint(
    project_id: str,
    payload: AnswersPayload,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    try:
        require_project_access(project_id, user)
        answers = payload.answers or {}
        return save_project_answers(project_id, answers)
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/simulations")
def create_project_simulations_endpoint(
    project_id: str,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    try:
        require_project_access(project_id, user)
        return create_simulation_runs(project_id)
    except BusinessFlowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/simulations")
def list_project_simulations_endpoint(
    project_id: str,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    try:
        require_project_access(project_id, user)
        get_project(project_id)
        return {"simulation_runs": list_project_simulation_runs(project_id)}
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/simulation-runs/{simulation_run_id}")
def get_simulation_run_endpoint(
    simulation_run_id: str,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    try:
        require_simulation_access(simulation_run_id, user)
        return get_simulation_run(simulation_run_id)
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/simulation-runs/{simulation_run_id}/report-html")
def get_simulation_report_html_endpoint(
    simulation_run_id: str,
    user: dict[str, Any] = Depends(current_user),
) -> Response:
    try:
        require_simulation_access(simulation_run_id, user)
        return Response(
            content=get_simulation_report_html(simulation_run_id),
            media_type="text/html",
        )
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/simulation-runs/{simulation_run_id}/report-pdf")
def get_simulation_report_pdf_endpoint(
    simulation_run_id: str,
    user: dict[str, Any] = Depends(current_user),
) -> Response:
    try:
        require_simulation_access(simulation_run_id, user)
        simulation_run = get_simulation_run(simulation_run_id)
        pdf_content = render_pdf_from_html(simulation_run["report_html"])
        filename = _report_pdf_filename(simulation_run)
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PdfExportError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _report_pdf_filename(simulation_run: dict[str, Any]) -> str:
    project = get_project(simulation_run["project_id"])
    customer_or_project = project.get("customer_name") or project["name"]
    created_day = _format_filename_date(simulation_run["created_at"])
    parts = [
        "rapport",
        customer_or_project,
        simulation_run["adaptation_id"],
        simulation_run["season"],
        simulation_run["role"],
        created_day,
    ]
    return f"{'-'.join(_slugify_filename_part(part) for part in parts if part)}.pdf"


def _format_filename_date(value: str) -> str:
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return value[:10]


def _slugify_filename_part(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = FILENAME_UNSAFE_RE.sub("-", ascii_value).strip("-")
    return slug or "rapport"


def _payload_dict(payload: BaseModel) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return payload.dict()


def _auth_token(authorization: str | None, session_cookie: str | None) -> str | None:
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    return session_cookie


def _set_auth_cookie(response: Response, auth_payload: dict[str, Any]) -> None:
    response.set_cookie(
        AUTH_COOKIE_NAME,
        auth_payload["access_token"],
        httponly=True,
        secure=os.environ.get("THERMAL_SAAS_ENV") == "production",
        samesite="lax",
        max_age=_cookie_max_age_seconds(auth_payload.get("expires_at")),
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        AUTH_COOKIE_NAME,
        httponly=True,
        secure=os.environ.get("THERMAL_SAAS_ENV") == "production",
        samesite="lax",
    )


def _cookie_max_age_seconds(expires_at: str | None) -> int | None:
    if not expires_at:
        return None
    try:
        expires = datetime.fromisoformat(expires_at)
    except ValueError:
        return None
    return max(0, int((expires - datetime.now(expires.tzinfo)).total_seconds()))


def _check_auth_rate_limit(request: Request, email: str) -> None:
    now = time.monotonic()
    key = f"{_client_ip(request)}:{email.strip().lower()}"
    attempts = [
        attempt
        for attempt in AUTH_RATE_LIMITS.get(key, [])
        if now - attempt < AUTH_RATE_LIMIT_WINDOW_SECONDS
    ]
    if len(attempts) >= AUTH_RATE_LIMIT_ATTEMPTS:
        _log_auth_event("auth_rate_limited", request, email)
        raise HTTPException(status_code=429, detail="Too many authentication attempts.")
    attempts.append(now)
    AUTH_RATE_LIMITS[key] = attempts


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _log_auth_event(event: str, request: Request, email: str) -> None:
    logger.info(
        "auth_event=%s ip=%s email=%s",
        event,
        _client_ip(request),
        email.strip().lower(),
    )


def _validate_branding_payload(payload: dict[str, Any]) -> None:
    primary_color = payload.get("primary_color")
    if primary_color and not HEX_COLOR_RE.match(primary_color):
        raise HTTPException(status_code=400, detail="primary_color must be a hex color.")
    logo_url = payload.get("logo_url")
    if logo_url:
        if not isinstance(logo_url, str) or not logo_url.startswith("data:image/"):
            raise HTTPException(status_code=400, detail="logo_url must be an image data URL.")
        if len(logo_url) > 500_000:
            raise HTTPException(status_code=400, detail="logo_url is too large.")
    for field_name, max_length in {
        "phone": 30,
        "email_contact": 120,
        "website": 200,
        "legal_mention": 1000,
    }.items():
        value = payload.get(field_name)
        if value and len(str(value)) > max_length:
            raise HTTPException(status_code=400, detail=f"{field_name} is too long.")
