from fastapi.testclient import TestClient

from thermal_saas.backup import BackupResult
from thermal_saas.api import AUTH_RATE_LIMITS, _allowed_hosts, _cors_origins, app


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
    assert "/static/app.js?v=20260527-beta-login" in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_legal_page_is_served(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    client = TestClient(app)

    response = client.get("/legal")

    assert response.status_code == 200
    assert "Conditions générales d'utilisation" in response.text
    assert "Politique de confidentialité" in response.text
    assert "Mentions légales" in response.text
    assert "estimations et simulations thermiques" in response.text


def test_health_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "thermal-saas"


def test_profile_experience_api_returns_clear_user_error(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    client = TestClient(app)

    response = client.post(
        "/business-profiles/window_seller/experiences",
        json={
            "project_name": "Erreur claire",
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
                    "height_m": 2.5,
                    "facades": [
                        {
                            "orientation": "S",
                            "window_area_m2": 20.0,
                            "wall_length_m": 3.0,
                        },
                    ],
                },
            ],
        },
    )

    assert response.status_code == 400
    assert "window_area_m2" in response.json()["detail"]
    assert "surface de façade" in response.json()["detail"]


def test_startup_initializes_empty_database(tmp_path, monkeypatch):
    db_path = tmp_path / "thermal_saas.sqlite"
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(db_path))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert db_path.exists()


def test_render_external_hostname_is_allowed(monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_ALLOWED_HOSTS", "thermal-beta.example.com")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "thermal-saas-beta.onrender.com")

    assert _allowed_hosts() == [
        "thermal-beta.example.com",
        "thermal-saas-beta.onrender.com",
    ]


def test_production_allowed_hosts_do_not_include_local_defaults(monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_ENV", "production")
    monkeypatch.delenv("THERMAL_SAAS_ALLOWED_HOSTS", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "thermal-saas-beta.onrender.com")

    assert _allowed_hosts() == ["thermal-saas-beta.onrender.com"]


def test_render_external_url_is_allowed_for_cors(monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_CORS_ORIGINS", "https://thermal-beta.example.com")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://thermal-saas-beta.onrender.com/")

    assert _cors_origins() == [
        "https://thermal-beta.example.com",
        "https://thermal-saas-beta.onrender.com",
    ]


def test_production_cors_does_not_include_local_defaults(monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_ENV", "production")
    monkeypatch.delenv("THERMAL_SAAS_CORS_ORIGINS", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://thermal-saas-beta.onrender.com/")

    assert _cors_origins() == ["https://thermal-saas-beta.onrender.com"]


def test_production_rejects_wildcard_cors(monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_ENV", "production")
    monkeypatch.setenv("THERMAL_SAAS_CORS_ORIGINS", "*")

    try:
        _cors_origins()
    except RuntimeError as exc:
        assert "cannot contain '*'" in str(exc)
    else:
        raise AssertionError("Wildcard CORS should be rejected in production.")


def test_admin_backup_requires_configured_token(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    monkeypatch.delenv("THERMAL_SAAS_ADMIN_TOKEN", raising=False)
    client = TestClient(app)

    response = client.post(
        "/admin/backups",
        headers={"X-Thermal-Admin-Token": "token"},
    )

    assert response.status_code == 503


def test_admin_backup_rejects_invalid_token(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    monkeypatch.setenv("THERMAL_SAAS_ADMIN_TOKEN", "expected-token")
    client = TestClient(app)

    response = client.post(
        "/admin/backups",
        headers={"X-Thermal-Admin-Token": "wrong-token"},
    )

    assert response.status_code == 403


def test_admin_backup_uploads_sqlite_backup(tmp_path, monkeypatch):
    db_path = tmp_path / "thermal_saas.sqlite"
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(db_path))
    monkeypatch.setenv("THERMAL_SAAS_ADMIN_TOKEN", "expected-token")

    def fake_backup(path):
        assert path == db_path
        return BackupResult(
            bucket="beta-backups",
            key="thermal-saas/sqlite/thermal_saas-test.sqlite.gz",
            size_bytes=123,
            database_path=str(path),
            created_at="20260523T120000Z",
        )

    monkeypatch.setattr("thermal_saas.api.backup_sqlite_to_object_storage", fake_backup)
    client = TestClient(app)

    response = client.post(
        "/admin/backups",
        headers={"X-Thermal-Admin-Token": "expected-token"},
    )

    assert response.status_code == 200
    assert response.json()["backup"]["bucket"] == "beta-backups"
    assert response.json()["backup"]["key"].endswith(".sqlite.gz")


def test_admin_beta_user_requires_valid_token(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    monkeypatch.setenv("THERMAL_SAAS_ADMIN_TOKEN", "expected-token")
    client = TestClient(app)

    missing_response = client.post(
        "/admin/beta-users",
        json={
            "email": "client@example.com",
            "password": "password123",
            "organization_name": "Client Org",
        },
    )
    response = client.post(
        "/admin/beta-users",
        headers={"X-Thermal-Admin-Token": "wrong-token"},
        json={
            "email": "client@example.com",
            "password": "password123",
            "organization_name": "Client Org",
        },
    )

    assert missing_response.status_code == 403
    assert response.status_code == 403


def test_admin_beta_user_creates_roof_insulation_user_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    monkeypatch.setenv("THERMAL_SAAS_ADMIN_TOKEN", "expected-token")
    client = TestClient(app)

    response = client.post(
        "/admin/beta-users",
        headers={"X-Thermal-Admin-Token": "expected-token"},
        json={
            "email": "client@example.com",
            "password": "password123",
            "organization_name": "Client Org",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "client@example.com"
    assert payload["organization"]["name"] == "Client Org"
    assert payload["organization"]["business_profile_id"] == "roof_insulation_seller"
    assert "access_token" not in payload


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
    monkeypatch.setattr("thermal_saas.api.render_pdf_from_html", lambda html: b"%PDF-1.4\n")
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
    pdf_report_response = client.get(
        f"/simulation-runs/{simulation_runs[-1]['id']}/report-pdf",
        headers={**headers, "Origin": "http://127.0.0.1:8010"},
    )
    annual_run_response = client.get(
        f"/simulation-runs/{simulation_runs[-1]['id']}",
        headers=headers,
    )
    assert report_response.status_code == 200
    assert "<!doctype html>" in report_response.text
    assert annual_report_response.status_code == 200
    assert "<!doctype html>" in annual_report_response.text
    assert pdf_report_response.status_code == 200
    assert pdf_report_response.content.startswith(b"%PDF")
    assert pdf_report_response.headers["content-type"] == "application/pdf"
    assert "attachment" in pdf_report_response.headers["content-disposition"]
    assert "rapport-mme-dupont-better-windows-annual-annual-" in (
        pdf_report_response.headers["content-disposition"]
    )
    assert "content-disposition" in (
        pdf_report_response.headers["access-control-expose-headers"].lower()
    )
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
    cookie_me_response = client.get("/auth/me")
    logout_response = client.post("/auth/logout", headers=headers)
    after_logout_response = client.get("/auth/me", headers=headers)

    assert login_response.status_code == 200
    assert "httponly" in login_response.headers["set-cookie"].lower()
    assert me_response.json()["user"]["email"] == "demo@example.com"
    assert cookie_me_response.json()["user"]["email"] == "demo@example.com"
    assert logout_response.status_code == 200
    assert "thermal_saas_session=" in logout_response.headers["set-cookie"]
    assert after_logout_response.status_code == 401


def test_auth_rate_limit_blocks_repeated_attempts(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    monkeypatch.setattr("thermal_saas.api.AUTH_RATE_LIMIT_ATTEMPTS", 2)
    AUTH_RATE_LIMITS.clear()
    client = TestClient(app)

    responses = [
        client.post(
            "/auth/login",
            json={"email": "missing@example.com", "password": "wrong-password"},
        )
        for _ in range(3)
    ]

    assert [response.status_code for response in responses] == [401, 401, 429]


def test_session_expires(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    monkeypatch.setenv("THERMAL_SAAS_SESSION_TTL_HOURS", "0")
    client = TestClient(app)

    payload, headers = _register(client)
    response = client.get("/auth/me", headers=headers)

    assert "expires_at" in payload
    assert response.status_code == 401


def test_secret_key_is_required_in_production(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    monkeypatch.setenv("THERMAL_SAAS_ENV", "production")
    monkeypatch.setenv("THERMAL_SAAS_ADMIN_TOKEN", "expected-token")
    monkeypatch.delenv("THERMAL_SAAS_SECRET_KEY", raising=False)
    client = TestClient(app)

    response = client.post(
        "/admin/beta-users",
        headers={"X-Thermal-Admin-Token": "expected-token"},
        json={
            "email": "secure@example.com",
            "password": "password123",
            "organization_name": "Secure Org",
        },
    )

    assert response.status_code == 400
    assert "THERMAL_SAAS_SECRET_KEY" in response.json()["detail"]


def test_secret_key_must_be_long_in_production(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    monkeypatch.setenv("THERMAL_SAAS_ENV", "production")
    monkeypatch.setenv("THERMAL_SAAS_ADMIN_TOKEN", "expected-token")
    monkeypatch.setenv("THERMAL_SAAS_SECRET_KEY", "too-short")
    client = TestClient(app)

    response = client.post(
        "/admin/beta-users",
        headers={"X-Thermal-Admin-Token": "expected-token"},
        json={
            "email": "secure@example.com",
            "password": "password123",
            "organization_name": "Secure Org",
        },
    )

    assert response.status_code == 400
    assert "at least 32 characters" in response.json()["detail"]


def test_public_register_is_disabled_in_production(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    monkeypatch.setenv("THERMAL_SAAS_ENV", "production")
    monkeypatch.setenv("THERMAL_SAAS_SECRET_KEY", "a-production-secret-with-at-least-32-chars")
    client = TestClient(app)

    response = client.post(
        "/auth/register",
        json={
            "email": "secure@example.com",
            "password": "password123",
            "organization_name": "Secure Org",
            "business_profile_id": "window_seller",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Inscription publique désactivée."


def test_large_payload_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        content=b"x" * 1_000_001,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413


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


def test_organization_branding_api_roundtrips_and_validates_color(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_SAAS_DB_PATH", str(tmp_path / "thermal_saas.sqlite"))
    client = TestClient(app)
    _, headers = _register(client)

    empty_response = client.get("/organization-branding", headers=headers)
    save_response = client.put(
        "/organization-branding",
        headers=headers,
        json={
            "primary_color": "#1a5c3a",
            "phone": "0102030405",
            "email_contact": "contact@example.com",
            "website": "https://example.com",
            "legal_mention": "RCS Test",
        },
    )
    invalid_response = client.put(
        "/organization-branding",
        headers=headers,
        json={"primary_color": "green"},
    )

    assert empty_response.status_code == 200
    assert empty_response.json()["branding"] is None
    assert save_response.status_code == 200
    assert save_response.json()["branding"]["primary_color"] == "#1a5c3a"
    assert save_response.json()["branding"]["phone"] == "0102030405"
    assert invalid_response.status_code == 400
