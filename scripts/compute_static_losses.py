#!/usr/bin/env python3
"""Compute static heat losses for a dwelling JSON file."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from thermal_model import (  # noqa: E402
    compute_dwelling_static_losses,
    get_rooms_by_id,
    load_dwelling,
    load_reference_catalog,
    resolve_dwelling_references,
)


def print_static_losses(
    dwelling: dict[str, Any],
    results: dict[str, Any],
    indoor_temperature_c: float,
    outdoor_temperature_c: float,
) -> None:
    """Print a compact text report."""
    print(f"Logement: {dwelling['dwelling_id']}")
    print(
        "Hypothese: "
        f"T_int={indoor_temperature_c:.1f} C, "
        f"T_ext={outdoor_temperature_c:.1f} C"
    )
    print()
    print("Pertes statiques par piece")
    print(
        "piece | H transmission W/K | H ventilation W/K | "
        "H total W/K | perte totale W"
    )
    print("-" * 78)

    rooms_by_id = get_rooms_by_id(dwelling)
    for room_id, room_result in results["rooms"].items():
        room_name = rooms_by_id[room_id]["name"]
        print(
            f"{room_name} | "
            f"{room_result['transmission_h_w_k']:.1f} | "
            f"{room_result['ventilation_h_w_k']:.1f} | "
            f"{room_result['total_h_w_k']:.1f} | "
            f"{room_result['total_loss_w']:.0f}"
        )

    totals = results["totals"]
    print("-" * 78)
    print(
        "TOTAL | "
        f"{totals['transmission_h_w_k']:.1f} | "
        f"{totals['ventilation_h_w_k']:.1f} | "
        f"{totals['total_h_w_k']:.1f} | "
        f"{totals['total_loss_w']:.0f}"
    )
    print()
    print("Detail logement")
    print(f"- UA parois: {totals['surface_ua_w_k']:.1f} W/K")
    print(f"- UA vitrages: {totals['window_ua_w_k']:.1f} W/K")
    print(f"- Majoration ponts thermiques: {totals['thermal_bridge_h_w_k']:.1f} W/K")
    print(f"- Pertes transmission: {totals['transmission_loss_w']:.0f} W")
    print(f"- Pertes ventilation: {totals['ventilation_loss_w']:.0f} W")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute static heat losses for a ThermalTwin dwelling JSON.",
    )
    parser.add_argument(
        "dwelling_path",
        nargs="?",
        default="data/examples/house_simple.json",
        help="Path to the dwelling JSON file.",
    )
    parser.add_argument(
        "--reference-dir",
        default="data/reference",
        help="Path to the reference data directory.",
    )
    parser.add_argument(
        "--indoor-temperature-c",
        type=float,
        default=20.0,
        help="Indoor reference temperature in deg C.",
    )
    parser.add_argument(
        "--outdoor-temperature-c",
        type=float,
        default=0.0,
        help="Outdoor reference temperature in deg C.",
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


def main() -> None:
    args = parse_args()
    dwelling = load_dwelling(args.dwelling_path, validate=False)
    reference_catalog = load_reference_catalog(args.reference_dir)
    dwelling = resolve_dwelling_references(dwelling, reference_catalog)
    results = compute_dwelling_static_losses(
        dwelling,
        args.indoor_temperature_c,
        args.outdoor_temperature_c,
        args.air_density_kg_m3,
        args.air_heat_capacity_j_kgk,
    )
    print_static_losses(
        dwelling,
        results,
        args.indoor_temperature_c,
        args.outdoor_temperature_c,
    )


if __name__ == "__main__":
    main()
