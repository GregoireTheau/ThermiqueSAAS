#!/usr/bin/env python3
"""Run a beta deployment smoke test against the public SaaS HTTP API."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


DEFAULT_ANSWERS = {
    "project_name": "Smoke test beta",
    "city": "Bordeaux",
    "postal_code": "33000",
    "dwelling_type": "house",
    "position_id": "single_storey_house",
    "construction_era_id": "us_2000_2009",
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
}


class SmokeClient:
    def __init__(self, base_url: str, timeout: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self.token: str | None = None

    def get(
        self,
        path: str,
        expected_status: int | tuple[int, ...] = 200,
    ) -> tuple[dict | None, bytes, dict]:
        return self.request("GET", path, expected_status=expected_status)

    def post(
        self,
        path: str,
        payload: dict | None = None,
        expected_status: int | tuple[int, ...] = 200,
        headers: dict[str, str] | None = None,
    ) -> tuple[dict | None, bytes, dict]:
        return self.request("POST", path, payload, expected_status, headers)

    def request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        expected_status: int | tuple[int, ...] = 200,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[dict | None, bytes, dict]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if extra_headers:
            headers.update(extra_headers)
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                content = response.read()
                status = response.status
                response_headers = dict(response.headers)
        except HTTPError as exc:
            content = exc.read()
            status = exc.code
            response_headers = dict(exc.headers)
        except URLError as exc:
            raise SystemExit(f"Request failed for {method} {path}: {exc}") from exc

        expected_statuses = (
            expected_status if isinstance(expected_status, tuple) else (expected_status,)
        )
        if status not in expected_statuses:
            detail = content.decode("utf-8", errors="replace")[:1000]
            raise SystemExit(
                f"{method} {path} returned {status}, expected {expected_statuses}: {detail}",
            )

        parsed = None
        content_type = response_headers.get("Content-Type", "")
        if "application/json" in content_type and content:
            parsed = json.loads(content)
        return parsed, content, response_headers


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        required=True,
        help="Public deployment URL, e.g. https://your-thermaltwin-deployment.example.com",
    )
    parser.add_argument(
        "--email",
        default=None,
        help="User email to create or reuse for the smoke test",
    )
    parser.add_argument(
        "--password",
        default="SmokeTest123!",
        help="Password for the smoke test user",
    )
    parser.add_argument(
        "--organization",
        default=None,
        help="Organization to create or reuse",
    )
    parser.add_argument("--profile", default="window_seller", help="Business profile id")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout in seconds")
    parser.add_argument(
        "--skip-pdf",
        action="store_true",
        help="Skip server-side PDF rendering check",
    )
    parser.add_argument(
        "--admin-token",
        default=None,
        help="Optional admin token; when provided, also checks /admin/backups",
    )
    args = parser.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    email = args.email or f"smoke+{stamp}@example.com"
    organization = args.organization or f"Smoke Org {stamp}"
    client = SmokeClient(args.base_url, args.timeout)

    health, _, _ = client.get("/health")
    assert health and health["status"] == "ok"
    _, app_html, _ = client.get("/app")
    assert b"ThermalTwin" in app_html

    auth_payload, _, _ = client.post(
        "/auth/register",
        {
            "email": email,
            "password": args.password,
            "organization_name": organization,
            "business_profile_id": args.profile,
            "name": "Smoke Test",
        },
        expected_status=(200, 400),
    )
    assert auth_payload
    if "access_token" not in auth_payload:
        auth_payload, _, _ = client.post(
            "/auth/login",
            {
                "email": email,
                "password": args.password,
                "organization_name": organization,
            },
        )
        assert auth_payload
    client.token = auth_payload["access_token"]

    me, _, _ = client.get("/auth/me")
    assert me and me["user"]["email"] == email

    query = urlencode({"name": organization})
    lookup, _, _ = client.get(f"/organizations/lookup?{query}")
    assert lookup and lookup["exists"] is True

    project, _, _ = client.post(
        "/projects",
        {
            "name": f"Smoke Project {stamp}",
            "customer_name": "Client Smoke",
        },
    )
    assert project

    client.post(f"/projects/{project['id']}/answers", {"answers": DEFAULT_ANSWERS})
    simulation_payload, _, _ = client.post(f"/projects/{project['id']}/simulations")
    simulation_runs = simulation_payload["simulation_runs"]
    assert len(simulation_runs) == 3

    annual_run = simulation_runs[-1]
    _, html, _ = client.get(f"/simulation-runs/{annual_run['id']}/report-html")
    assert b"<!doctype html>" in html.lower()

    if not args.skip_pdf:
        _, pdf, headers = client.get(f"/simulation-runs/{annual_run['id']}/report-pdf")
        assert pdf.startswith(b"%PDF")
        assert "application/pdf" in headers.get("Content-Type", "")

    backup_checked = False
    if args.admin_token:
        backup_payload, _, _ = client.post(
            "/admin/backups",
            headers={"X-Thermal-Admin-Token": args.admin_token},
        )
        assert backup_payload and backup_payload["status"] == "ok"
        backup_checked = True

    print(
        json.dumps(
            {
                "status": "ok",
                "base_url": args.base_url.rstrip("/"),
                "email": email,
                "organization": organization,
                "project_id": project["id"],
                "simulation_run_ids": [run["id"] for run in simulation_runs],
                "pdf_checked": not args.skip_pdf,
                "backup_checked": backup_checked,
            },
            indent=2,
        ),
    )


if __name__ == "__main__":
    main()
