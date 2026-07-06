#!/usr/bin/env python3
"""Create a beta user through the production admin API."""

from __future__ import annotations

import argparse
import os

import requests


DEFAULT_PROFILE = "roof_insulation_seller"
DEFAULT_URL = "https://your-thermaltwin-deployment.example.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a ThermalTwin beta customer account.")
    parser.add_argument("--email", required=True, help="User login email.")
    parser.add_argument("--password", required=True, help="Temporary password to send to the customer.")
    parser.add_argument("--org", required=True, help="Customer organization name.")
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="Business profile id.")
    parser.add_argument("--url", default=DEFAULT_URL, help="ThermalTwin API base URL.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    admin_token = os.environ.get("THERMAL_SAAS_ADMIN_TOKEN", "").strip()
    if not admin_token:
        print("Error: THERMAL_SAAS_ADMIN_TOKEN must be set in the environment.")
        return 1

    endpoint = args.url.rstrip("/") + "/admin/beta-users"
    response = requests.post(
        endpoint,
        headers={"X-Thermal-Admin-Token": admin_token},
        json={
            "email": args.email,
            "password": args.password,
            "organization_name": args.org,
            "business_profile_id": args.profile,
        },
        timeout=20,
    )
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except requests.JSONDecodeError:
            detail = response.text
        print(f"Beta account creation error ({response.status_code}): {detail}")
        return 1

    payload = response.json()
    user = payload["user"]
    organization = payload["organization"]
    print("Beta account created")
    print(f"Email: {user['email']}")
    print(f"Organization: {organization['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
