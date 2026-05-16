"""Load and validate ThermalTwin scenario JSON files."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

Scenario = dict[str, Any]


class ScenarioValidationError(ValueError):
    """Raised when a scenario JSON is structurally inconsistent."""


def load_scenario(path: str | Path, validate: bool = True) -> Scenario:
    """Load a scenario JSON file and optionally validate it."""
    with Path(path).open(encoding="utf-8") as file:
        scenario = json.load(file)

    if validate:
        validate_scenario(scenario)

    return scenario


def validate_scenario(scenario: Mapping[str, Any]) -> None:
    """Validate the minimal scenario fields needed by the first simulation."""
    _require_keys(
        scenario,
        (
            "schema_version",
            "scenario_id",
            "dwelling_id",
            "timestep_h",
            "setpoints",
            "weather",
            "energy_prices",
            "co2_factors",
        ),
        "scenario",
    )
    if scenario["schema_version"] != "0.1":
        raise ScenarioValidationError("scenario.schema_version must be '0.1'")
    if scenario["timestep_h"] <= 0:
        raise ScenarioValidationError("scenario.timestep_h must be > 0")

    setpoints = scenario["setpoints"]
    _require_keys(setpoints, ("heating_c", "cooling_c"), "scenario.setpoints")
    if setpoints["heating_c"] > setpoints["cooling_c"]:
        raise ScenarioValidationError("heating_c cannot be greater than cooling_c")

    weather = scenario["weather"]
    _require_keys(weather, ("hourly",), "scenario.weather")
    if not weather["hourly"]:
        raise ScenarioValidationError("scenario.weather.hourly cannot be empty")

    expected_hour = 0
    for point in weather["hourly"]:
        _require_keys(point, ("hour", "outdoor_temperature_c"), "weather hourly point")
        if point["hour"] != expected_hour:
            raise ScenarioValidationError(
                f"weather hour must be sequential from 0, got {point['hour']}"
            )
        expected_hour += 1

    _require_keys(
        scenario["energy_prices"],
        ("electricity_eur_kwh",),
        "scenario.energy_prices",
    )
    _require_keys(
        scenario["co2_factors"],
        ("electricity_kg_kwh",),
        "scenario.co2_factors",
    )


def _require_keys(
    data: Mapping[str, Any],
    required_keys: tuple[str, ...],
    context: str,
) -> None:
    missing = [key for key in required_keys if key not in data]
    if missing:
        raise ScenarioValidationError(
            f"{context} is missing required keys: {', '.join(missing)}"
        )
