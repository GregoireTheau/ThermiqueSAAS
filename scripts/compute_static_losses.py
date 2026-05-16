#!/usr/bin/env python3
"""Compute static heat losses for a dwelling JSON file.

This is a first test script, not the final modelling engine. It calculates
room-level H coefficients and heat loss at one indoor/outdoor temperature pair.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from thermal_model import (  # noqa: E402
    get_rooms_by_id,
    load_dwelling,
    load_reference_catalog,
    resolve_dwelling_references,
)
from utils import (  # noqa: E402
    airflow_from_ach,
    corrected_transmission_coefficient,
    sum_ua,
    ventilation_heat_transfer_coefficient,
)


def compute_room_static_losses(
    dwelling: dict[str, Any],
    room: dict[str, Any],
    indoor_temperature_c: float,
    outdoor_temperature_c: float,
    air_density_kg_m3: float,
    air_heat_capacity_j_kgk: float,
) -> dict[str, float]:
    """Return static loss coefficients and losses for one room."""
    defaults = dwelling["defaults"]
    delta_t_k = indoor_temperature_c - outdoor_temperature_c

    surface_ua_w_k = sum_ua(
        (
            surface["u_value_w_m2k"],
            surface["area_m2"],
        )
        for surface in room["surfaces"]
        if surface["boundary"] in {"exterior", "ground", "unheated_space", "party"}
    )
    window_ua_w_k = sum_ua(
        (
            window["u_value_w_m2k"],
            window["area_m2"],
        )
        for window in room["windows"]
    )
    transmission_ua_w_k = surface_ua_w_k + window_ua_w_k
    bridge_factor = defaults["thermal_bridge_factor"]
    transmission_h_w_k = corrected_transmission_coefficient(
        transmission_ua_w_k,
        bridge_factor,
    )

    ventilation = room.get("ventilation", {})
    ach_h = ventilation.get("ach_h", defaults["ach_h"])
    airflow_m3_s = airflow_from_ach(ach_h, room["volume_m3"])
    ventilation_h_w_k = ventilation_heat_transfer_coefficient(
        airflow_m3_s,
        air_density_kg_m3,
        air_heat_capacity_j_kgk,
    )

    total_h_w_k = transmission_h_w_k + ventilation_h_w_k

    return {
        "surface_ua_w_k": surface_ua_w_k,
        "window_ua_w_k": window_ua_w_k,
        "thermal_bridge_h_w_k": transmission_ua_w_k * bridge_factor,
        "transmission_h_w_k": transmission_h_w_k,
        "ventilation_h_w_k": ventilation_h_w_k,
        "total_h_w_k": total_h_w_k,
        "transmission_loss_w": transmission_h_w_k * delta_t_k,
        "ventilation_loss_w": ventilation_h_w_k * delta_t_k,
        "total_loss_w": total_h_w_k * delta_t_k,
    }


def compute_dwelling_static_losses(
    dwelling: dict[str, Any],
    indoor_temperature_c: float,
    outdoor_temperature_c: float,
    air_density_kg_m3: float,
    air_heat_capacity_j_kgk: float,
) -> dict[str, Any]:
    """Return room and total static losses for a dwelling."""
    rooms_by_id = get_rooms_by_id(dwelling)
    room_results = {
        room_id: compute_room_static_losses(
            dwelling,
            room,
            indoor_temperature_c,
            outdoor_temperature_c,
            air_density_kg_m3,
            air_heat_capacity_j_kgk,
        )
        for room_id, room in rooms_by_id.items()
    }

    totals = {
        key: sum(room_result[key] for room_result in room_results.values())
        for key in (
            "surface_ua_w_k",
            "window_ua_w_k",
            "thermal_bridge_h_w_k",
            "transmission_h_w_k",
            "ventilation_h_w_k",
            "total_h_w_k",
            "transmission_loss_w",
            "ventilation_loss_w",
            "total_loss_w",
        )
    }

    return {
        "rooms": room_results,
        "totals": totals,
    }


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
