from fastapi.testclient import TestClient

from thermal_saas.api import app


def test_business_profiles_api_lists_all_profiles(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    client = TestClient(app)

    response = client.get("/business-profiles")

    assert response.status_code == 200
    profile_ids = {profile["id"] for profile in response.json()["profiles"]}
    assert profile_ids == {
        "heat_pump_seller",
        "roof_insulation_seller",
        "solar_protection_seller",
        "window_seller",
    }


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

    organization_response = client.post(
        "/organizations",
        json={"name": "Fenetre Pro", "business_profile_id": "window_seller"},
    )
    organization_id = organization_response.json()["id"]
    project_response = client.post(
        "/projects",
        json={
            "organization_id": organization_id,
            "name": "Maison API persistante",
            "customer_name": "Mme Dupont",
        },
    )
    project_id = project_response.json()["id"]

    answers_response = client.post(
        f"/projects/{project_id}/answers",
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
    simulation_response = client.post(f"/projects/{project_id}/simulations")
    history_response = client.get(f"/projects/{project_id}/simulations")

    assert answers_response.status_code == 200
    assert simulation_response.status_code == 200
    simulation_runs = history_response.json()["simulation_runs"]
    assert [run["season"] for run in simulation_runs] == ["winter", "summer"]

    report_response = client.get(f"/simulation-runs/{simulation_runs[0]['id']}/report-html")
    assert report_response.status_code == 200
    assert "<!doctype html>" in report_response.text
