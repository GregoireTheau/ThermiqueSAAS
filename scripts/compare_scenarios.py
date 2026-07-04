#!/usr/bin/env python3
"""Compare two ThermalTwin scenarios on the same dwelling."""

from __future__ import annotations

import argparse
import json
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
    load_scenario,
    resolve_dwelling_references,
)


def print_comparison(comparison: dict[str, Any]) -> None:
    """Print a compact before/after comparison."""
    before_totals = comparison["before"]["totals"]
    after_totals = comparison["after"]["totals"]
    deltas = comparison["deltas"]
    summary = comparison["summary"]
    experiment = comparison["experiment"]

    print(f"Dwelling: {comparison['dwelling_id']}")
    print(f"Before: {comparison['before_scenario_id']}")
    print(f"After: {comparison['after_scenario_id']}")
    print(
        "Experience: "
        f"{experiment['duration_days']:.1f} days "
        f"({experiment['duration_hours']:.0f} h), "
        f"weather {experiment['weather_source']}, "
        f"{experiment['weather_summary']['outdoor_temperature_min_c']:.1f} C -> "
        f"{experiment['weather_summary']['outdoor_temperature_max_c']:.1f} C ext."
    )
    print("Scope: simulated results over this period, without annual projection.")
    print()
    print("Commercial reading")
    print(f"- Comfort gained: {summary['comfort_gain']['label']}")
    print(f"- Energy saved: {summary['energy_savings']['label']}")
    print(
        "- Main cause: "
        f"{summary['main_gain_driver']['label']} "
        f"({summary['main_gain_driver']['value']:.2f} "
        f"{summary['main_gain_driver']['unit']})"
    )
    print()
    print("Energy / cost / CO2")
    print(
        "Electricity kWh: "
        f"{before_totals['electricity_kwh']:.2f} -> "
        f"{after_totals['electricity_kwh']:.2f} "
        f"(gain {deltas['electricity_kwh']:.2f})"
    )
    print(
        "Cost EUR: "
        f"{before_totals['electricity_cost_eur']:.2f} -> "
        f"{after_totals['electricity_cost_eur']:.2f} "
        f"(gain {deltas['electricity_cost_eur']:.2f})"
    )
    print(
        "CO2 kg: "
        f"{before_totals['electricity_co2_kg']:.2f} -> "
        f"{after_totals['electricity_co2_kg']:.2f} "
        f"(gain {deltas['electricity_co2_kg']:.2f})"
    )
    print()
    print("Comfort by room")
    for room_delta in deltas["rooms"].values():
        print(
            f"- {room_delta['room_name']}: "
            f"{room_delta['before_max_temperature_c']:.1f} C -> "
            f"{room_delta['after_max_temperature_c']:.1f} C "
            f"(reduction {room_delta['delta_max_temperature_c']:.1f} C), "
            f"warm degree-hours avoided "
            f"{room_delta['delta_hot_degree_hours']:.0f}, "
            f"cold degree-hours avoided "
            f"{room_delta['delta_cold_degree_hours']:.0f}"
        )
    print()
    print("Technical deltas by room")
    for room_delta in deltas["rooms"].values():
        print(
            f"- {room_delta['room_name']}: "
            f"solar {room_delta['delta_solar_gain_kwh']:.2f} kWh, "
            f"transmission {room_delta['delta_transmission_exchange_kwh']:.2f} kWh, "
            f"ventilation {room_delta['delta_ventilation_exchange_kwh']:.2f} kWh, "
            f"heating {room_delta['delta_heating_thermal_kwh']:.2f} kWh, "
            f"cooling {room_delta['delta_cooling_thermal_kwh']:.2f} kWh"
        )


def write_comparison_json(
    output_path: str | Path,
    comparison: dict[str, Any],
) -> None:
    """Write the full comparison payload as JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(comparison, file, indent=2, ensure_ascii=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two ThermalTwin scenarios on the same dwelling.",
    )
    parser.add_argument(
        "dwelling_path",
        nargs="?",
        default="data/examples/house_simple.json",
        help="Path to the dwelling JSON file.",
    )
    parser.add_argument(
        "before_scenario_path",
        nargs="?",
        default="data/examples/scenario_heatwave_before.json",
        help="Path to the before scenario JSON file.",
    )
    parser.add_argument(
        "after_scenario_path",
        nargs="?",
        default="data/examples/scenario_heatwave.json",
        help="Path to the after scenario JSON file.",
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
        help="Optional path to write full comparison results as JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    catalog = load_reference_catalog(args.reference_dir)
    dwelling = load_dwelling(args.dwelling_path, validate=False)
    dwelling = resolve_dwelling_references(dwelling, catalog)
    before_scenario = load_scenario(args.before_scenario_path)
    after_scenario = load_scenario(args.after_scenario_path)

    if before_scenario["dwelling_id"] != dwelling["dwelling_id"]:
        raise ValueError("before scenario dwelling_id does not match dwelling")
    if after_scenario["dwelling_id"] != dwelling["dwelling_id"]:
        raise ValueError("after scenario dwelling_id does not match dwelling")

    comparison = compare_scenarios(
        dwelling,
        before_scenario,
        after_scenario,
        args.air_density_kg_m3,
        args.air_heat_capacity_j_kgk,
    )
    print_comparison(comparison)

    if args.output_json:
        write_comparison_json(args.output_json, comparison)


if __name__ == "__main__":
    main()
