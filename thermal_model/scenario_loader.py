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
    """Load a scenario JSON file, resolve external weather, and optionally validate it."""
    scenario_path = Path(path)
    with scenario_path.open(encoding="utf-8") as file:
        scenario = json.load(file)

    resolve_scenario_weather_reference(scenario, scenario_path.parent)

    if validate:
        validate_scenario(scenario)

    return scenario


def resolve_scenario_weather_reference(
    scenario: Scenario,
    base_dir: str | Path = ".",
) -> Scenario:
    """Resolve scenario.weather.weather_ref in place when present."""
    weather = scenario.get("weather", {})
    weather_ref = weather.get("weather_ref")
    if not weather_ref or "hourly" in weather:
        return scenario

    weather_path = Path(weather_ref)
    if not weather_path.is_absolute():
        weather_path = Path(base_dir) / weather_path
        if not weather_path.exists():
            weather_path = Path(weather_ref)
    with weather_path.open(encoding="utf-8") as file:
        referenced_weather = json.load(file)

    if "hourly" not in referenced_weather:
        raise ScenarioValidationError(
            f"weather reference must contain hourly data: {weather_path}"
        )

    weather["hourly"] = referenced_weather["hourly"]
    weather["source"] = weather.get(
        "source",
        referenced_weather.get("source", str(weather_ref)),
    )
    if "metadata" in referenced_weather:
        weather["metadata"] = referenced_weather["metadata"]
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
    _validate_temperature_setpoint(setpoints["heating_c"], "scenario.setpoints.heating_c")
    _validate_temperature_setpoint(setpoints["cooling_c"], "scenario.setpoints.cooling_c")
    if setpoints["heating_c"] > setpoints["cooling_c"]:
        raise ScenarioValidationError(
            "scenario.setpoints.heating_c cannot be greater than scenario.setpoints.cooling_c"
        )

    controls = scenario.get("controls", {})
    natural_ventilation = controls.get("natural_ventilation", {})
    for key in ("default_ach", "smart_ach"):
        if key in natural_ventilation and natural_ventilation[key] < 0:
            raise ScenarioValidationError(
                f"scenario.controls.natural_ventilation.{key} must be >= 0"
            )
    for entry in natural_ventilation.get("hourly", []):
        _require_keys(entry, ("hour", "ach"), "natural ventilation hourly control")
        if entry["hour"] < 0:
            raise ScenarioValidationError("natural ventilation hour must be >= 0")
        if entry["ach"] < 0:
            raise ScenarioValidationError("natural ventilation ach must be >= 0")

    weather = scenario["weather"]
    if "hourly" not in weather:
        if "weather_ref" in weather:
            raise ScenarioValidationError(
                "scenario.weather.weather_ref must be resolved before validation"
            )
        _require_keys(weather, ("hourly",), "scenario.weather")
    if not weather["hourly"]:
        raise ScenarioValidationError("scenario.weather.hourly cannot be empty")

    expected_hour = 0.0
    for point in weather["hourly"]:
        _require_keys(point, ("hour", "outdoor_temperature_c"), "weather hourly point")
        if "month" in point and not 1 <= point["month"] <= 12:
            raise ScenarioValidationError("weather hourly point month must be between 1 and 12")
        if abs(float(point["hour"]) - expected_hour) > 1e-9:
            raise ScenarioValidationError(
                f"weather hour must follow scenario.timestep_h from 0, got {point['hour']}"
            )
        expected_hour += float(scenario["timestep_h"])

    _require_keys(
        scenario["energy_prices"],
        ("electricity_usd_kwh",),
        "scenario.energy_prices",
    )
    _require_keys(
        scenario["co2_factors"],
        ("electricity_kg_kwh",),
        "scenario.co2_factors",
    )


def validate_scenario_against_dwelling(
    scenario: Mapping[str, Any],
    dwelling: Mapping[str, Any],
) -> None:
    """Validate scenario references that need the dwelling object graph."""
    room_ids = {room["id"] for room in dwelling["rooms"]}
    surface_ids = {
        surface["id"]
        for room in dwelling["rooms"]
        for surface in room.get("surfaces", [])
    }
    window_ids = {
        window["id"]
        for room in dwelling["rooms"]
        for window in room.get("windows", [])
    }
    system_ids = {
        category: {system["id"] for system in dwelling["systems"].get(category, [])}
        for category in ("heating", "cooling")
    }

    for room_id in scenario.get("initial_temperatures_c", {}):
        if room_id not in room_ids:
            raise ScenarioValidationError(
                f"scenario.initial_temperatures_c references unknown room '{room_id}'"
            )

    retrofit = scenario.get("retrofit", {})
    for override in retrofit.get("surface_overrides", []):
        surface_id = override.get("surface_id")
        if surface_id not in surface_ids:
            raise ScenarioValidationError(
                f"scenario.retrofit.surface_overrides references unknown surface '{surface_id}'"
            )
    for override in retrofit.get("window_overrides", []):
        window_id = override.get("window_id")
        if window_id not in window_ids:
            raise ScenarioValidationError(
                f"scenario.retrofit.window_overrides references unknown window '{window_id}'"
            )
    for override in retrofit.get("shutter_overrides", []):
        window_id = override.get("window_id")
        if window_id not in window_ids:
            raise ScenarioValidationError(
                f"scenario.retrofit.shutter_overrides references unknown window '{window_id}'"
            )
    for override in retrofit.get("system_overrides", []):
        category = override.get("category")
        system_id = override.get("system_id")
        if category not in system_ids:
            raise ScenarioValidationError(
                f"scenario.retrofit.system_overrides has unsupported category '{category}'"
            )
        if system_id not in system_ids[category]:
            raise ScenarioValidationError(
                f"scenario.retrofit.system_overrides references unknown {category} system '{system_id}'"
            )
    for system in retrofit.get("add_systems", []):
        category = system.get("category")
        if category not in system_ids:
            raise ScenarioValidationError(
                f"scenario.retrofit.add_systems has unsupported category '{category}'"
            )
        for room_id in system.get("served_rooms", []):
            if room_id not in room_ids:
                raise ScenarioValidationError(
                    f"scenario.retrofit.add_systems system '{system.get('id')}' references unknown room '{room_id}'"
                )


def _validate_temperature_setpoint(value: float, context: str) -> None:
    if value == 0 or value >= 60:
        return
    if value < 10 or value > 35:
        raise ScenarioValidationError(f"{context} must be between 10 and 35 °C")


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
