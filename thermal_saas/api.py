"""FastAPI entrypoint for the first ThermalTwin SaaS slice."""

from __future__ import annotations

from typing import Any
from pathlib import Path
import re

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
    from fastapi import Depends, FastAPI, Header, HTTPException, Response
    from fastapi.responses import FileResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional runtime deps
    raise RuntimeError(
        "FastAPI is not installed. Install requirements.txt before running the API.",
    ) from exc


app = FastAPI(title="ThermalTwin SaaS API", version="0.1")
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


@app.get("/")
def redirect_to_app() -> RedirectResponse:
    return RedirectResponse(url="/app")


@app.get("/app")
def get_app() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    token = authorization.removeprefix("Bearer ").strip()
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
def register_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return register_user_with_organization(
            email=payload["email"],
            password=payload["password"],
            organization_name=payload["organization_name"],
            business_profile_id=payload["business_profile_id"],
            name=payload.get("name"),
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Missing field: {exc.args[0]}") from exc
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/auth/login")
def login_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return login_user(
            payload["email"],
            payload["password"],
            organization_name=payload.get("organization_name"),
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Missing field: {exc.args[0]}") from exc
    except AuthError as exc:
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
    authorization: str | None = Header(default=None),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    token = authorization.removeprefix("Bearer ").strip()
    revoke_session(token)
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
    payload: dict[str, Any],
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if user["organization_id"]:
        raise HTTPException(status_code=403, detail="Use /auth/register to create an organization.")
    try:
        return create_organization(
            name=payload["name"],
            business_profile_id=payload["business_profile_id"],
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
    payload: dict[str, Any],
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    _validate_branding_payload(payload)
    return {
        "branding": upsert_organization_branding(
            user["organization_id"],
            payload,
        ),
    }


@app.post("/projects")
def create_project_endpoint(
    payload: dict[str, Any],
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    try:
        organization_id = payload.get("organization_id", user["organization_id"])
        if organization_id != user["organization_id"]:
            raise HTTPException(status_code=403, detail="Cannot create project for this organization.")
        return create_project(
            organization_id=organization_id,
            name=payload["name"],
            customer_name=payload.get("customer_name"),
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
    payload: dict[str, Any],
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    try:
        require_project_access(project_id, user)
        answers = payload.get("answers", payload)
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
        pdf_content = render_pdf_from_html(get_simulation_report_html(simulation_run_id))
        filename = f"thermal-report-{simulation_run_id}.pdf"
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PdfExportError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
