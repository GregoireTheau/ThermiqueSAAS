"""FastAPI entrypoint for the first ThermalTwin SaaS slice."""

from __future__ import annotations

from typing import Any

from .business_flow import BusinessFlowError, run_profile_experience
from .business_profiles import (
    build_questionnaire,
    list_business_profiles as load_all_business_profiles,
    load_business_profile,
)
from .storage import (
    StorageError,
    create_organization,
    create_project,
    create_simulation_runs,
    get_latest_project_answers,
    get_project,
    get_simulation_report_html,
    get_simulation_run,
    list_project_simulation_runs,
    save_project_answers,
)
from thermal_model import load_reference_catalog

try:
    from fastapi import FastAPI, HTTPException, Response
except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional runtime deps
    raise RuntimeError(
        "FastAPI is not installed. Install requirements.txt before running the API.",
    ) from exc


app = FastAPI(title="ThermalTwin SaaS API", version="0.1")


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


@app.post("/business-profiles/{profile_id}/experiences")
def create_profile_experience(profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return run_profile_experience(profile_id, payload)
    except BusinessFlowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/organizations")
def create_organization_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return create_organization(
            name=payload["name"],
            business_profile_id=payload["business_profile_id"],
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Missing field: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/projects")
def create_project_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return create_project(
            organization_id=payload["organization_id"],
            name=payload["name"],
            customer_name=payload.get("customer_name"),
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Missing field: {exc.args[0]}") from exc
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}")
def get_project_endpoint(project_id: str) -> dict[str, Any]:
    try:
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
def save_project_answers_endpoint(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        answers = payload.get("answers", payload)
        return save_project_answers(project_id, answers)
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/simulations")
def create_project_simulations_endpoint(project_id: str) -> dict[str, Any]:
    try:
        return create_simulation_runs(project_id)
    except BusinessFlowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/simulations")
def list_project_simulations_endpoint(project_id: str) -> dict[str, Any]:
    try:
        get_project(project_id)
        return {"simulation_runs": list_project_simulation_runs(project_id)}
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/simulation-runs/{simulation_run_id}")
def get_simulation_run_endpoint(simulation_run_id: str) -> dict[str, Any]:
    try:
        return get_simulation_run(simulation_run_id)
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/simulation-runs/{simulation_run_id}/report-html")
def get_simulation_report_html_endpoint(simulation_run_id: str) -> Response:
    try:
        return Response(
            content=get_simulation_report_html(simulation_run_id),
            media_type="text/html",
        )
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
