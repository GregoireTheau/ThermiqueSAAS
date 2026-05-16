#!/usr/bin/env python3
"""Compare two ThermalTwin scenarios on the same dwelling."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.simulate_1r1c import (  # noqa: E402
    apply_scenario_overrides,
    simulate_1r1c,
)
from thermal_model import (  # noqa: E402
    get_rooms_by_id,
    load_dwelling,
    load_reference_catalog,
    load_scenario,
    resolve_dwelling_references,
)


def compare_scenarios(
    dwelling: dict[str, Any],
    before_scenario: dict[str, Any],
    after_scenario: dict[str, Any],
    air_density_kg_m3: float,
    air_heat_capacity_j_kgk: float,
) -> dict[str, Any]:
    """Run two scenario simulations and return comparison metrics."""
    before_dwelling = deepcopy(dwelling)
    after_dwelling = deepcopy(dwelling)
    apply_scenario_overrides(before_dwelling, before_scenario)
    apply_scenario_overrides(after_dwelling, after_scenario)

    before_results = simulate_1r1c(
        before_dwelling,
        before_scenario,
        air_density_kg_m3,
        air_heat_capacity_j_kgk,
    )
    after_results = simulate_1r1c(
        after_dwelling,
        after_scenario,
        air_density_kg_m3,
        air_heat_capacity_j_kgk,
    )

    rooms = get_rooms_by_id(dwelling)
    room_deltas = {}
    for room_id, room in rooms.items():
        before_max_c = _max_room_temperature(before_results, room_id)
        after_max_c = _max_room_temperature(after_results, room_id)
        before_final_c = _final_room_temperature(before_results, room_id)
        after_final_c = _final_room_temperature(after_results, room_id)
        room_deltas[room_id] = {
            "room_name": room["name"],
            "before_max_temperature_c": before_max_c,
            "after_max_temperature_c": after_max_c,
            "delta_max_temperature_c": before_max_c - after_max_c,
            "before_final_temperature_c": before_final_c,
            "after_final_temperature_c": after_final_c,
            "delta_final_temperature_c": before_final_c - after_final_c,
        }

    return {
        "dwelling_id": dwelling["dwelling_id"],
        "before_scenario_id": before_scenario["scenario_id"],
        "after_scenario_id": after_scenario["scenario_id"],
        "before": before_results,
        "after": after_results,
        "deltas": {
            "heating_thermal_kwh": _delta_total(
                before_results,
                after_results,
                "heating_thermal_kwh",
            ),
            "heating_electric_kwh": _delta_total(
                before_results,
                after_results,
                "heating_electric_kwh",
            ),
            "cooling_thermal_kwh": _delta_total(
                before_results,
                after_results,
                "cooling_thermal_kwh",
            ),
            "cooling_electric_kwh": _delta_total(
                before_results,
                after_results,
                "cooling_electric_kwh",
            ),
            "electricity_kwh": _delta_total(before_results, after_results, "electricity_kwh"),
            "electricity_cost_eur": _delta_total(
                before_results,
                after_results,
                "electricity_cost_eur",
            ),
            "electricity_co2_kg": _delta_total(
                before_results,
                after_results,
                "electricity_co2_kg",
            ),
            "rooms": room_deltas,
        },
    }


def print_comparison(comparison: dict[str, Any]) -> None:
    """Print a compact before/after comparison."""
    before_totals = comparison["before"]["totals"]
    after_totals = comparison["after"]["totals"]
    deltas = comparison["deltas"]

    print(f"Logement: {comparison['dwelling_id']}")
    print(f"Avant: {comparison['before_scenario_id']}")
    print(f"Apres: {comparison['after_scenario_id']}")
    print()
    print("Energie / cout / CO2")
    print(
        "Electricite kWh: "
        f"{before_totals['electricity_kwh']:.2f} -> "
        f"{after_totals['electricity_kwh']:.2f} "
        f"(gain {deltas['electricity_kwh']:.2f})"
    )
    print(
        "Cout EUR: "
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
    print("Temperature max par piece")
    for room_delta in deltas["rooms"].values():
        print(
            f"- {room_delta['room_name']}: "
            f"{room_delta['before_max_temperature_c']:.1f} C -> "
            f"{room_delta['after_max_temperature_c']:.1f} C "
            f"(baisse {room_delta['delta_max_temperature_c']:.1f} C)"
        )


def write_comparison_json(
    output_path: str | Path,
    comparison: dict[str, Any],
) -> None:
    """Write the full comparison payload as JSON."""
    with Path(output_path).open("w", encoding="utf-8") as file:
        json.dump(comparison, file, indent=2)


def _delta_total(
    before_results: dict[str, Any],
    after_results: dict[str, Any],
    key: str,
) -> float:
    return before_results["totals"][key] - after_results["totals"][key]


def _max_room_temperature(results: dict[str, Any], room_id: str) -> float:
    return max(hour["rooms"][room_id]["temperature_c"] for hour in results["hourly"])


def _final_room_temperature(results: dict[str, Any], room_id: str) -> float:
    return results["hourly"][-1]["rooms"][room_id]["temperature_c"]


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
