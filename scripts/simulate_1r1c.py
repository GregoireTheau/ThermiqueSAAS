#!/usr/bin/env python3
"""Run an hourly 1R1C simulation for a dwelling and scenario."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from thermal_model import (  # noqa: E402
    apply_scenario_overrides,
    get_rooms_by_id,
    load_dwelling,
    load_reference_catalog,
    load_scenario,
    resolve_dwelling_references,
    simulate_1r1c,
)


def print_simulation_summary(
    dwelling: dict[str, Any],
    scenario: dict[str, Any],
    results: dict[str, Any],
) -> None:
    """Print a compact simulation summary."""
    print(f"Dwelling: {dwelling['dwelling_id']}")
    print(f"Scenario: {scenario['scenario_id']}")
    print(f"Simulated hours: {len(results['hourly'])}")
    print()
    print("Final temperatures")
    last_hour = results["hourly"][-1]
    rooms = get_rooms_by_id(dwelling)
    for room_id, room_result in last_hour["rooms"].items():
        print(f"- {rooms[room_id]['name']}: {room_result['temperature_c']:.1f} C")
    print()
    print("Max temperatures")
    for room_id, room in rooms.items():
        max_temperature_c = max(
            hour["rooms"][room_id]["temperature_c"]
            for hour in results["hourly"]
        )
        print(f"- {room['name']}: {max_temperature_c:.1f} C")
    print()
    print("Energy balance")
    totals = results["totals"]
    print(f"- Thermal heating: {totals['heating_thermal_kwh']:.2f} kWh")
    print(f"- Electric heating: {totals['heating_electric_kwh']:.2f} kWh")
    print(f"- Thermal cooling: {totals['cooling_thermal_kwh']:.2f} kWh")
    print(f"- Electric cooling: {totals['cooling_electric_kwh']:.2f} kWh")
    print(f"- Total electricity: {totals['electricity_kwh']:.2f} kWh")
    print(f"- Electricity cost: ${totals['electricity_cost_usd']:.2f}")


def write_results_json(
    output_path: str | Path,
    dwelling: dict[str, Any],
    scenario: dict[str, Any],
    results: dict[str, Any],
) -> None:
    """Write raw structured simulation results as JSON."""
    payload = {
        "dwelling_id": dwelling["dwelling_id"],
        "scenario_id": scenario["scenario_id"],
        "timestep_h": scenario["timestep_h"],
        "results": results,
    }
    with Path(output_path).open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def write_results_csv(
    output_path: str | Path,
    results: dict[str, Any],
) -> None:
    """Write hourly room-level simulation results as CSV."""
    fieldnames = [
        "hour",
        "room_id",
        "outdoor_temperature_c",
        "temperature_c",
        "free_temperature_c",
        "heating_power_w",
        "cooling_power_w",
        "internal_gain_w",
        "solar_gain_w",
        "coupling_power_w",
        "envelope_power_w",
        "transmission_power_w",
        "ventilation_power_w",
        "infiltration_power_w",
        "mechanical_ventilation_power_w",
        "natural_ventilation_power_w",
    ]
    with Path(output_path).open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for hour_result in results["hourly"]:
            for room_id, room_result in hour_result["rooms"].items():
                writer.writerow(
                    {
                        "hour": hour_result["hour"],
                        "room_id": room_id,
                        "outdoor_temperature_c": hour_result[
                            "outdoor_temperature_c"
                        ],
                        **room_result,
                    }
                )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a first hourly 1R1C simulation.",
    )
    parser.add_argument(
        "dwelling_path",
        nargs="?",
        default="data/examples/house_simple.json",
        help="Path to the dwelling JSON file.",
    )
    parser.add_argument(
        "scenario_path",
        nargs="?",
        default="data/examples/scenario_simple.json",
        help="Path to the scenario JSON file.",
    )
    parser.add_argument(
        "--reference-dir",
        default="data/reference",
        help="Path to the reference data directory.",
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
    parser.add_argument(
        "--output-json",
        help="Optional path to write raw hourly results as JSON.",
    )
    parser.add_argument(
        "--output-csv",
        help="Optional path to write hourly room-level results as CSV.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    catalog = load_reference_catalog(args.reference_dir)
    dwelling = load_dwelling(args.dwelling_path, validate=False)
    dwelling = resolve_dwelling_references(dwelling, catalog)
    scenario = load_scenario(args.scenario_path)

    if scenario["dwelling_id"] != dwelling["dwelling_id"]:
        raise ValueError("scenario.dwelling_id does not match dwelling.dwelling_id")

    apply_scenario_overrides(dwelling, scenario)
    results = simulate_1r1c(
        dwelling,
        scenario,
        args.air_density_kg_m3,
        args.air_heat_capacity_j_kgk,
    )
    print_simulation_summary(dwelling, scenario, results)

    if args.output_json:
        write_results_json(args.output_json, dwelling, scenario, results)
    if args.output_csv:
        write_results_csv(args.output_csv, results)


if __name__ == "__main__":
    main()
