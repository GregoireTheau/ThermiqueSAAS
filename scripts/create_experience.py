#!/usr/bin/env python3
"""Guided CLI to create and optionally compare a first experience."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from thermal_model import (  # noqa: E402
    compare_scenarios,
    load_dwelling,
    load_reference_catalog,
    resolve_dwelling_references,
)


EXPERIENCE_TYPES = [
    {
        "id": "summer_comfort",
        "label": "Summer comfort / heatwave",
        "season": "summer",
        "initial_temperature_c": 26.0,
        "setpoints": {"heating_c": 18.0, "cooling_c": 26.0},
    },
    {
        "id": "winter_heating",
        "label": "Winter heating / energy savings",
        "season": "winter",
        "initial_temperature_c": 19.0,
        "setpoints": {"heating_c": 19.0, "cooling_c": 28.0},
    },
]

INTERVENTIONS = [
    {
        "id": "reflective_roof",
        "label": "Reflective roof",
        "season": "summer",
    },
    {
        "id": "solar_shutter",
        "label": "High-performance shutter / solar protection",
        "season": "summer",
    },
    {
        "id": "heat_pump",
        "label": "Replace electric heating with heat pump",
        "season": "winter",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create before/after scenarios from guided choices.",
    )
    parser.add_argument(
        "--dwelling-path",
        default="data/examples/house_simple.json",
        help="Path to the dwelling JSON file.",
    )
    parser.add_argument(
        "--reference-dir",
        default="data/reference",
        help="Path to the reference data directory.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/created_experiences",
        help="Directory where scenario and comparison JSON files are written.",
    )
    parser.add_argument(
        "--air-density-kg-m3",
        type=float,
        default=1.2,
        help="Air density used for ventilation losses.",
    )
    parser.add_argument(
        "--air-heat-capacity-j-kgk",
        type=float,
        default=1005.0,
        help="Air heat capacity used for ventilation losses.",
    )
    return parser.parse_args()


def choose_one(title: str, options: list[dict[str, Any]]) -> dict[str, Any]:
    print(title)
    for index, option in enumerate(options, start=1):
        print(f"{index}. {option['label']}")

    while True:
        raw_value = input("> ").strip()
        if raw_value.isdigit():
            index = int(raw_value)
            if 1 <= index <= len(options):
                return options[index - 1]
        print(f"Invalid choice. Enter a number between 1 and {len(options)}.")


def choose_duration_days() -> int:
    print("Weather duration")
    print("1. 3 days")
    print("2. 7 days")

    while True:
        raw_value = input("> ").strip()
        if raw_value == "1":
            return 3
        if raw_value == "2":
            return 7
        print("Invalid choice. Enter 1 or 2.")


def choose_yes_no(label: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    raw_value = input(f"{label} ({suffix}) > ").strip().lower()
    if not raw_value:
        return default
    return raw_value in {"o", "oui", "y", "yes"}


def build_room_options(dwelling: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"id": room["id"], "label": f"{room['name']} ({room['id']})"}
        for room in dwelling["rooms"]
    ]


def build_scenario(
    scenario_id: str,
    dwelling_id: str,
    experience_type: dict[str, Any],
    duration_days: int,
    room_id: str,
    intervention: dict[str, Any] | None,
    dwelling: dict[str, Any],
) -> dict[str, Any]:
    scenario = {
        "schema_version": "0.1",
        "scenario_id": scenario_id,
        "dwelling_id": dwelling_id,
        "description": f"{experience_type['label']} - {room_id}",
        "timestep_h": 1.0,
        "initial_temperatures_c": _initial_temperatures(
            dwelling,
            experience_type["initial_temperature_c"],
        ),
        "setpoints": experience_type["setpoints"],
        "weather": build_weather(experience_type["season"], duration_days),
        "energy_prices": {"electricity_usd_kwh": 0.18},
        "co2_factors": {"electricity_kg_kwh": 0.0},
    }

    if experience_type["season"] == "summer":
        scenario["controls"] = {"shutters": build_daytime_shutter_controls(duration_days)}

    if intervention:
        retrofit = build_retrofit(dwelling, room_id, intervention["id"])
        if retrofit:
            scenario["retrofit"] = retrofit

    return scenario


def _initial_temperatures(
    dwelling: dict[str, Any],
    initial_temperature_c: float,
) -> dict[str, float]:
    return {
        room["id"]: initial_temperature_c
        for room in dwelling["rooms"]
    }


def build_weather(season: str, duration_days: int) -> dict[str, Any]:
    hourly = []
    for hour in range(duration_days * 24):
        hour_in_day = hour % 24
        if season == "summer":
            outdoor_temperature_c = 29.0 + 7.0 * math.sin(
                2.0 * math.pi * (hour_in_day - 8) / 24.0,
            )
            solar_peak = max(0.0, math.sin(math.pi * (hour_in_day - 6) / 13.0))
            east_irradiance = 520.0 if hour_in_day < 13 else 160.0
            west_irradiance = 520.0 if hour_in_day > 12 else 160.0
            hourly.append(
                {
                    "hour": hour,
                    "month": 7,
                    "outdoor_temperature_c": round(outdoor_temperature_c, 2),
                    "solar_irradiance_w_m2": {
                        "north": round(80.0 * solar_peak, 2),
                        "east": round(east_irradiance * solar_peak, 2),
                        "south": round(620.0 * solar_peak, 2),
                        "west": round(west_irradiance * solar_peak, 2),
                        "roof": round(760.0 * solar_peak, 2),
                    },
                },
            )
        else:
            outdoor_temperature_c = 3.0 + 4.0 * math.sin(
                2.0 * math.pi * (hour_in_day - 7) / 24.0,
            )
            hourly.append(
                {
                    "hour": hour,
                    "month": 1,
                    "outdoor_temperature_c": round(outdoor_temperature_c, 2),
                    "solar_irradiance_w_m2": {
                        "north": 0.0,
                        "east": 0.0,
                        "south": 0.0,
                        "west": 0.0,
                        "roof": 0.0,
                    },
                },
            )

    return {"source": f"generated_{season}_{duration_days}d", "hourly": hourly}


def build_daytime_shutter_controls(duration_days: int) -> dict[str, Any]:
    return {
        "default_opening_ratio": 1.0,
        "hourly": [
            {"hour": hour, "opening_ratio": 0.2}
            for hour in range(duration_days * 24)
            if 8 <= hour % 24 <= 19
        ],
    }


def build_retrofit(
    dwelling: dict[str, Any],
    room_id: str,
    intervention_id: str,
) -> dict[str, Any]:
    room = _find_room(dwelling, room_id)

    if intervention_id == "reflective_roof":
        roof_surfaces = [
            surface
            for surface in room["surfaces"]
            if surface["type"] == "roof" and surface["boundary"] == "exterior"
        ]
        return {
            "surface_overrides": [
                {
                    "surface_id": surface["id"],
                    "albedo": 0.75,
                }
                for surface in roof_surfaces
            ],
        }

    if intervention_id == "solar_shutter":
        return {
            "shutter_overrides": [
                {
                    "window_id": window["id"],
                    "type": "external_blind",
                    "solar_factor_closed": 0.05,
                    "solar_factor_open": 1.0,
                    "u_factor_closed": 0.8,
                }
                for window in room["windows"]
            ],
        }

    if intervention_id == "heat_pump":
        return {
            "system_overrides": [
                {
                    "category": "heating",
                    "system_id": system["id"],
                    "system_ref": "air_source_heat_pump_standard",
                    "type": "heat_pump",
                    "energy_vector": "electricity",
                    "performance_ref": {
                        "mode": "temperature_curve",
                        "cop": 3.2,
                        "points": [
                            {"outdoor_temperature_c": -7.0, "cop": 2.0},
                            {"outdoor_temperature_c": 7.0, "cop": 3.2},
                            {"outdoor_temperature_c": 15.0, "cop": 4.0},
                        ],
                    },
                }
                for system in dwelling["systems"]["heating"]
                if room_id in system["served_rooms"]
            ],
        }

    return {}


def _find_room(dwelling: dict[str, Any], room_id: str) -> dict[str, Any]:
    for room in dwelling["rooms"]:
        if room["id"] == room_id:
            return room
    raise ValueError(f"room not found: {room_id}")


def write_json(output_path: str | Path, payload: dict[str, Any]) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def print_comparison_summary(comparison: dict[str, Any]) -> None:
    summary = comparison["summary"]
    experiment = comparison["experiment"]
    print()
    print("Comparison result")
    print(
        "- Experience: "
        f"{experiment['duration_days']:.1f} days "
        f"({experiment['duration_hours']:.0f} h), "
        f"weather {experiment['weather_source']}"
    )
    print("- Scope: simulated results over this period, without annual projection.")
    print(f"- Comfort: {summary['comfort_gain']['label']}")
    print(f"- Energy: {summary['energy_savings']['label']}")
    print(f"- Main cause: {summary['main_gain_driver']['label']}")


def main() -> None:
    args = parse_args()
    catalog = load_reference_catalog(args.reference_dir)
    dwelling = load_dwelling(args.dwelling_path, validate=False)
    dwelling = resolve_dwelling_references(dwelling, catalog)

    print("Create a ThermalTwin experience")
    experience_type = choose_one("Experience type", EXPERIENCE_TYPES)
    room = choose_one("Room concerned", build_room_options(dwelling))
    interventions = [
        intervention
        for intervention in INTERVENTIONS
        if intervention["season"] == experience_type["season"]
    ]
    intervention = choose_one("Intervention", interventions)
    duration_days = choose_duration_days()
    should_export = choose_yes_no("Export before/after JSON files", default=True)
    should_compare = choose_yes_no("Run the comparison directly", default=True)

    experiment_id = (
        f"{experience_type['id']}_{room['id']}_{intervention['id']}_{duration_days}d"
    )
    before = build_scenario(
        f"{experiment_id}_before",
        dwelling["dwelling_id"],
        experience_type,
        duration_days,
        room["id"],
        None,
        dwelling,
    )
    after = build_scenario(
        f"{experiment_id}_after",
        dwelling["dwelling_id"],
        experience_type,
        duration_days,
        room["id"],
        intervention,
        dwelling,
    )

    output_dir = Path(args.output_dir)
    before_path = output_dir / f"{experiment_id}_before.json"
    after_path = output_dir / f"{experiment_id}_after.json"
    comparison_path = output_dir / f"{experiment_id}_comparison.json"

    if should_export:
        write_json(before_path, before)
        write_json(after_path, after)
        print()
        print(f"Before exported: {before_path}")
        print(f"After exported: {after_path}")

    if should_compare:
        comparison = compare_scenarios(
            dwelling,
            before,
            after,
            args.air_density_kg_m3,
            args.air_heat_capacity_j_kgk,
        )
        write_json(comparison_path, comparison)
        print(f"Comparison exported: {comparison_path}")
        print_comparison_summary(comparison)


if __name__ == "__main__":
    main()
