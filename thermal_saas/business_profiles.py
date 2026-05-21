"""Business profile loading for the ThermalTwin SaaS."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_DIR = PROJECT_ROOT / "business_profiles"


class BusinessProfileError(ValueError):
    """Raised when a business profile cannot be loaded or used."""


def load_business_profile(
    profile_id: str,
    profile_dir: str | Path = DEFAULT_PROFILE_DIR,
) -> dict[str, Any]:
    """Load a versioned business profile from disk."""
    profile_path = Path(profile_dir) / f"{profile_id}.json"
    if not profile_path.exists():
        raise BusinessProfileError(f"Unknown business profile: {profile_id}")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if profile.get("id") != profile_id:
        raise BusinessProfileError(f"Business profile id mismatch in {profile_path}")
    return profile


def list_business_profiles(
    profile_dir: str | Path = DEFAULT_PROFILE_DIR,
) -> list[dict[str, Any]]:
    """Load all available business profiles."""
    profiles = []
    for profile_path in sorted(Path(profile_dir).glob("*.json")):
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profiles.append(profile)
    return profiles


def build_questionnaire(
    profile: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    """Return the questionnaire with catalog-backed options resolved."""
    questionnaire = deepcopy(profile["questionnaire"])
    for section in questionnaire["sections"]:
        for question in section["questions"]:
            if question.get("options_ref") == "envelope_defaults":
                question["options"] = [
                    {"id": item["id"], "label": item["name"]}
                    for item in catalog["envelope_defaults"].values()
                ]
    return questionnaire
