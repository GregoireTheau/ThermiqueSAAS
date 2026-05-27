#!/usr/bin/env python3
"""Create a private beta user for the reflective-roof SaaS."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from thermal_saas.storage import (  # noqa: E402
    AuthError,
    default_db_path,
    register_user_with_organization,
)


BETA_PROFILE_ID = "reflective_roof_seller"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a ThermalTwin beta account locked to reflective roof.",
    )
    parser.add_argument("--email", required=True, help="User login email.")
    parser.add_argument(
        "--password",
        required=True,
        help="Temporary password to send to the customer. Minimum 8 characters.",
    )
    parser.add_argument(
        "--organization",
        required=True,
        help="Customer company or organization name.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Optional contact name shown internally. Defaults to the email.",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help=(
            "Optional SQLite path. Defaults to THERMAL_SAAS_DB_PATH. "
            "For local beta dev, falls back to outputs/thermal_saas_phase8.sqlite when present."
        ),
    )
    return parser.parse_args()


def resolve_db_path(explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path)
    if os.environ.get("THERMAL_SAAS_DB_PATH"):
        return default_db_path()
    local_beta_path = PROJECT_ROOT / "outputs" / "thermal_saas_phase8.sqlite"
    if local_beta_path.exists():
        return local_beta_path
    return default_db_path()


def main() -> int:
    args = parse_args()
    db_path = resolve_db_path(args.db_path)
    try:
        payload = register_user_with_organization(
            email=args.email,
            password=args.password,
            organization_name=args.organization,
            business_profile_id=BETA_PROFILE_ID,
            name=args.name,
            db_path=db_path,
        )
    except AuthError as exc:
        print(f"Erreur création compte beta: {exc}", file=sys.stderr)
        return 1

    user = payload["user"]
    organization = payload["organization"]
    print("Compte beta créé")
    print(f"Base SQLite: {db_path}")
    print(f"Organisation: {organization['name']}")
    print(f"Profil: {organization['business_profile_id']}")
    print()
    print("Identifiants à envoyer au client:")
    print(f"Email: {user['email']}")
    print(f"Mot de passe temporaire: {args.password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
