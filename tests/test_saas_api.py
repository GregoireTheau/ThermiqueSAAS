from fastapi.testclient import TestClient

from thermal_saas.api import app


def _register(client, profile_id="window_seller"):
    response = client.post(
        "/auth/register",
        json={
            "email": "demo@example.com",
            "password": "password123",
            "name": "Demo User",
            "organization_name": "Demo Org",
            "business_profile_id": profile_id,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    return payload, {"Authorization": f"Bearer {payload['access_token']}"}


def test_business_profiles_api_lists_all_profiles(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    client = TestClient(app)

    response = client.get("/business-profiles")

    assert response.status_code == 200
    profile_ids = {profile["id"] for profile in response.json()["profiles"]}
    assert profile_ids == {
        "heat_pump_seller",
        "reflective_roof_seller",
        "roof_insulation_seller",
        "solar_protection_seller",
        "window_seller",
    }


def test_frontend_app_is_served(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    client = TestClient(app)

    response = client.get("/app")

    assert response.status_code == 200
    assert "ThermalTwin" in response.text
    assert "/static/app.js" in response.text


def test_profile_experience_api_accepts_window_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    client = TestClient(app)

    response = client.post(
        "/business-profiles/window_seller/experiences",
        json={
            "project_name": "Maison API fenetres",
            "city": "Bordeaux",
            "postal_code": "33000",
            "dwelling_type": "house",
            "position_id": "single_storey_house",
            "period_id": "2001_2012_good_insulation",
            "rooms": [
                {
                    "name": "Salon",
                    "type": "living",
                    "floor_area_m2": 30.0,
                    "facades": [
                        {
                            "orientation": "S",
                            "window_area_m2": 4.0,
                            "wall_length_m": 6.0,
                        },
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["business_profile_id"] == "window_seller"
    assert payload["adaptation_id"] == "better_windows"


def test_persistent_project_api_runs_and_exposes_report(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    client = TestClient(app)

    auth_payload, headers = _register(client)
    organization_id = auth_payload["organization"]["id"]
    organizations_response = client.get("/organizations", headers=headers)
    project_response = client.post(
        "/projects",
        headers=headers,
        json={
            "organization_id": organization_id,
            "name": "Maison API persistante",
            "customer_name": "Mme Dupont",
        },
    )
    project_id = project_response.json()["id"]
    projects_response = client.get(
        f"/projects?organization_id={organization_id}",
        headers=headers,
    )

    answers_response = client.post(
        f"/projects/{project_id}/answers",
        headers=headers,
        json={
            "answers": {
                "project_name": "Maison API persistante",
                "city": "Bordeaux",
                "postal_code": "33000",
                "dwelling_type": "house",
                "position_id": "single_storey_house",
                "period_id": "2001_2012_good_insulation",
                "rooms": [
                    {
                        "name": "Salon",
                        "type": "living",
                        "floor_area_m2": 30.0,
                        "facades": [
                            {
                                "orientation": "S",
                                "window_area_m2": 4.0,
                                "wall_length_m": 6.0,
                            },
                        ],
                    },
                ],
            },
        },
    )
    simulation_response = client.post(f"/projects/{project_id}/simulations", headers=headers)
    history_response = client.get(f"/projects/{project_id}/simulations", headers=headers)

    assert organizations_response.status_code == 200
    assert organizations_response.json()["organizations"][0]["id"] == organization_id
    assert projects_response.status_code == 200
    assert projects_response.json()["projects"][0]["id"] == project_id
    assert answers_response.status_code == 200
    assert simulation_response.status_code == 200
    simulation_runs = history_response.json()["simulation_runs"]
    assert [run["season"] for run in simulation_runs] == ["winter", "summer", "annual"]
    assert simulation_runs[-1]["role"] == "annual"

    report_response = client.get(
        f"/simulation-runs/{simulation_runs[0]['id']}/report-html",
        headers=headers,
    )
    annual_report_response = client.get(
        f"/simulation-runs/{simulation_runs[-1]['id']}/report-html",
        headers=headers,
    )
    annual_run_response = client.get(
        f"/simulation-runs/{simulation_runs[-1]['id']}",
        headers=headers,
    )
    assert report_response.status_code == 200
    assert "<!doctype html>" in report_response.text
    assert annual_report_response.status_code == 200
    assert "<!doctype html>" in annual_report_response.text
    assert annual_run_response.json()["result"]["comparison"]["experiment"]["weather_year"] == 2023


def test_project_api_requires_authentication(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    client = TestClient(app)

    response = client.get("/projects")

    assert response.status_code == 401


def test_login_me_and_logout(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    client = TestClient(app)
    _register(client)

    login_response = client.post(
        "/auth/login",
        json={"email": "demo@example.com", "password": "password123"},
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_response = client.get("/auth/me", headers=headers)
    logout_response = client.post("/auth/logout", headers=headers)
    after_logout_response = client.get("/auth/me", headers=headers)

    assert login_response.status_code == 200
    assert me_response.json()["user"]["email"] == "demo@example.com"
    assert logout_response.status_code == 200
    assert after_logout_response.status_code == 401


def test_register_second_user_joins_existing_organization(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    client = TestClient(app)
    first_payload, first_headers = _register(client, profile_id="heat_pump_seller")

    lookup_response = client.get("/organizations/lookup?name=Demo%20Org")
    second_response = client.post(
        "/auth/register",
        json={
            "email": "colleague@example.com",
            "password": "password123",
            "organization_name": "Demo Org",
            "business_profile_id": "heat_pump_seller",
        },
    )
    second_payload = second_response.json()
    second_headers = {"Authorization": f"Bearer {second_payload['access_token']}"}

    project_response = client.post(
        "/projects",
        headers=first_headers,
        json={"name": "Projet partagé", "customer_name": "Client commun"},
    )
    projects_seen_by_second_user = client.get("/projects", headers=second_headers)

    assert lookup_response.status_code == 200
    assert lookup_response.json()["exists"] is True
    assert lookup_response.json()["organization"]["business_profile_id"] == (
        "heat_pump_seller"
    )
    assert second_response.status_code == 200
    assert second_payload["organization"]["id"] == first_payload["organization"]["id"]
    assert project_response.status_code == 200
    assert projects_seen_by_second_user.json()["projects"][0]["name"] == "Projet partagé"


def test_register_accepts_each_business_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    client = TestClient(app)
    profile_ids = [
        "heat_pump_seller",
        "reflective_roof_seller",
        "roof_insulation_seller",
        "solar_protection_seller",
        "window_seller",
    ]

    for profile_id in profile_ids:
        response = client.post(
            "/auth/register",
            json={
                "email": f"{profile_id}@example.com",
                "password": "password123",
                "organization_name": f"Org {profile_id}",
                "business_profile_id": profile_id,
            },
        )

        assert response.status_code == 200
        assert response.json()["organization"]["business_profile_id"] == profile_id
