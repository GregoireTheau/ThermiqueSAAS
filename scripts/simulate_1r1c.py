#!/usr/bin/env python3
"""Run a first hourly 1R1C simulation for a dwelling and scenario.

This is intentionally MVP-sized: transmission, ventilation, internal gains,
simple solar gains, inter-room coupling, heating and cooling.
"""

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

from scripts.compute_static_losses import compute_room_static_losses  # noqa: E402
from thermal_model import (  # noqa: E402
    get_rooms_by_id,
    load_dwelling,
    load_reference_catalog,
    load_scenario,
    resolve_dwelling_references,
)
from utils import (  # noqa: E402
    albedo_to_absorptivity,
    cooling_electric_power,
    cooling_power_required,
    energy_from_power,
    equivalent_capacity_from_floor_area,
    heating_electric_power,
    heating_power_required,
    limited_cooling_power,
    limited_heating_power,
    next_temperature_explicit,
    opaque_solar_power_to_room,
    shutter_factor,
    solar_gain_window,
)


def simulate_1r1c(
    dwelling: dict[str, Any],
    scenario: dict[str, Any],
    air_density_kg_m3: float,
    air_heat_capacity_j_kgk: float,
) -> dict[str, Any]:
    """Simulate room air temperatures over the scenario weather series."""
    timestep_h = scenario["timestep_h"]
    timestep_s = timestep_h * 3600.0
    heating_setpoint_c = scenario["setpoints"]["heating_c"]
    cooling_setpoint_c = scenario["setpoints"]["cooling_c"]

    rooms = get_rooms_by_id(dwelling)
    scenario_initial_temperatures = scenario.get("initial_temperatures_c", {})
    temperatures = {
        room_id: scenario_initial_temperatures.get(
            room_id,
            room.get(
                "initial_temperature_c",
                dwelling["defaults"]["initial_temperature_c"],
            ),
        )
        for room_id, room in rooms.items()
    }
    capacities = {
        room_id: equivalent_capacity_from_floor_area(
            room["floor_area_m2"],
            room.get(
                "equivalent_capacity_j_m2k",
                dwelling["defaults"]["equivalent_capacity_j_m2k"],
            ),
        )
        for room_id, room in rooms.items()
    }
    heating_by_room = _index_systems_by_room(dwelling["systems"]["heating"])
    cooling_by_room = _index_systems_by_room(dwelling["systems"]["cooling"])

    hourly_results: list[dict[str, Any]] = []
    totals = {
        "heating_thermal_kwh": 0.0,
        "heating_electric_kwh": 0.0,
        "cooling_thermal_kwh": 0.0,
        "cooling_electric_kwh": 0.0,
    }

    for weather_point in scenario["weather"]["hourly"]:
        outdoor_temperature_c = weather_point["outdoor_temperature_c"]
        room_results: dict[str, Any] = {}
        coupling_power_by_room = _compute_coupling_powers(dwelling, temperatures)

        for room_id, room in rooms.items():
            current_temperature_c = temperatures[room_id]
            loss_data = compute_room_static_losses(
                dwelling,
                room,
                current_temperature_c,
                outdoor_temperature_c,
                air_density_kg_m3,
                air_heat_capacity_j_kgk,
            )
            total_h_w_k = loss_data["total_h_w_k"]
            internal_gain_w = room.get(
                "internal_gain_w_m2",
                dwelling["defaults"]["internal_gain_w_m2"],
            ) * room["floor_area_m2"]
            solar_gain_w = _compute_room_solar_gain(room, weather_point, scenario)
            coupling_power_w = coupling_power_by_room.get(room_id, 0.0)
            envelope_power_w = total_h_w_k * (
                outdoor_temperature_c - current_temperature_c
            )
            free_net_power_w = (
                envelope_power_w
                + internal_gain_w
                + solar_gain_w
                + coupling_power_w
            )
            free_next_temperature_c = next_temperature_explicit(
                current_temperature_c,
                free_net_power_w,
                capacities[room_id],
                timestep_s,
            )

            heating_power_w, heating_electric_w = _compute_heating(
                heating_by_room.get(room_id, []),
                heating_setpoint_c,
                free_next_temperature_c,
                capacities[room_id],
                timestep_s,
            )
            cooling_power_w, cooling_electric_w = _compute_cooling(
                cooling_by_room.get(room_id, []),
                free_next_temperature_c,
                cooling_setpoint_c,
                capacities[room_id],
                timestep_s,
            )
            final_net_power_w = free_net_power_w + heating_power_w - cooling_power_w
            next_temperature_c = next_temperature_explicit(
                current_temperature_c,
                final_net_power_w,
                capacities[room_id],
                timestep_s,
            )

            temperatures[room_id] = next_temperature_c
            totals["heating_thermal_kwh"] += energy_from_power(
                heating_power_w,
                timestep_h,
            )
            totals["heating_electric_kwh"] += energy_from_power(
                heating_electric_w,
                timestep_h,
            )
            totals["cooling_thermal_kwh"] += energy_from_power(
                cooling_power_w,
                timestep_h,
            )
            totals["cooling_electric_kwh"] += energy_from_power(
                cooling_electric_w,
                timestep_h,
            )
            room_results[room_id] = {
                "temperature_c": next_temperature_c,
                "free_temperature_c": free_next_temperature_c,
                "heating_power_w": heating_power_w,
                "cooling_power_w": cooling_power_w,
                "internal_gain_w": internal_gain_w,
                "solar_gain_w": solar_gain_w,
                "coupling_power_w": coupling_power_w,
                "envelope_power_w": envelope_power_w,
            }

        hourly_results.append(
            {
                "hour": weather_point["hour"],
                "outdoor_temperature_c": outdoor_temperature_c,
                "rooms": room_results,
            }
        )

    electricity_kwh = totals["heating_electric_kwh"] + totals["cooling_electric_kwh"]
    totals["electricity_kwh"] = electricity_kwh
    totals["electricity_cost_eur"] = (
        electricity_kwh * scenario["energy_prices"]["electricity_eur_kwh"]
    )
    totals["electricity_co2_kg"] = (
        electricity_kwh * scenario["co2_factors"]["electricity_kg_kwh"]
    )

    return {
        "hourly": hourly_results,
        "totals": totals,
    }


def _index_systems_by_room(systems: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    systems_by_room: dict[str, list[dict[str, Any]]] = {}
    for system in systems:
        for room_id in system["served_rooms"]:
            systems_by_room.setdefault(room_id, []).append(system)
    return systems_by_room


def _compute_coupling_powers(
    dwelling: dict[str, Any],
    temperatures: dict[str, float],
) -> dict[str, float]:
    coupling_power_by_room = {room["id"]: 0.0 for room in dwelling["rooms"]}
    for link in dwelling["thermal_links"]:
        room_a = link["room_a"]
        room_b = link["room_b"]
        h_link_w_k = (
            link["opening_factor"]
            * link["u_value_w_m2k"]
            * link["area_m2"]
        )
        power_b_to_a_w = h_link_w_k * (temperatures[room_b] - temperatures[room_a])
        coupling_power_by_room[room_a] += power_b_to_a_w
        coupling_power_by_room[room_b] -= power_b_to_a_w
    return coupling_power_by_room


def _compute_room_solar_gain(
    room: dict[str, Any],
    weather_point: dict[str, Any],
    scenario: dict[str, Any],
) -> float:
    irradiance_by_orientation = weather_point.get("solar_irradiance_w_m2", {})
    if not irradiance_by_orientation:
        return 0.0

    shutter_opening_ratio = _shutter_opening_ratio(scenario, weather_point["hour"])
    solar_gain_w = 0.0

    for window in room["windows"]:
        orientation = _surface_orientation_key(window)
        irradiance_w_m2 = irradiance_by_orientation.get(orientation, 0.0)
        shutter_reduction_factor = 1.0
        if "shutter" in window:
            shutter_reduction_factor = shutter_factor(
                window["shutter"]["solar_factor_closed"],
                window["shutter"]["solar_factor_open"],
                shutter_opening_ratio,
            )
        solar_gain_w += solar_gain_window(
            window["area_m2"],
            irradiance_w_m2,
            window["g_value"],
            shutter_reduction_factor,
            window.get("mask_factor", 1.0),
        )

    for surface in room["surfaces"]:
        if surface["boundary"] != "exterior":
            continue
        if "albedo" not in surface or "solar_to_room_factor" not in surface:
            continue
        orientation = _surface_orientation_key(surface)
        irradiance_w_m2 = irradiance_by_orientation.get(orientation, 0.0)
        solar_gain_w += opaque_solar_power_to_room(
            surface["area_m2"],
            irradiance_w_m2,
            albedo_to_absorptivity(surface["albedo"]),
            surface["solar_to_room_factor"],
            surface.get("mask_factor", 1.0),
        )

    return solar_gain_w


def _surface_orientation_key(surface: dict[str, Any]) -> str:
    if surface.get("type") == "roof" or surface.get("tilt_deg", 90) < 60:
        return "roof"

    azimuth_deg = surface.get("azimuth_deg", 180) % 360
    if azimuth_deg < 45 or azimuth_deg >= 315:
        return "north"
    if azimuth_deg < 135:
        return "east"
    if azimuth_deg < 225:
        return "south"
    return "west"


def _shutter_opening_ratio(scenario: dict[str, Any], hour: int) -> float:
    shutters = scenario.get("controls", {}).get("shutters", {})
    default_opening_ratio = shutters.get("default_opening_ratio", 1.0)
    hourly = shutters.get("hourly", [])
    for entry in hourly:
        if entry["hour"] == hour:
            return entry["opening_ratio"]
    return default_opening_ratio


def _compute_heating(
    systems: list[dict[str, Any]],
    heating_setpoint_c: float,
    free_next_temperature_c: float,
    capacity_j_k: float,
    timestep_s: float,
) -> tuple[float, float]:
    if not systems:
        return 0.0, 0.0

    required_power_w = heating_power_required(
        heating_setpoint_c,
        free_next_temperature_c,
        capacity_j_k,
        timestep_s,
    )
    max_power_w = sum(system["max_power_w"] for system in systems)
    heating_power_w = limited_heating_power(required_power_w, max_power_w)
    electric_power_w = sum(
        heating_electric_power(
            heating_power_w * system["max_power_w"] / max_power_w,
            system["performance_ref"]["cop"],
        )
        for system in systems
    )
    return heating_power_w, electric_power_w


def _compute_cooling(
    systems: list[dict[str, Any]],
    free_next_temperature_c: float,
    cooling_setpoint_c: float,
    capacity_j_k: float,
    timestep_s: float,
) -> tuple[float, float]:
    if not systems:
        return 0.0, 0.0

    required_power_w = cooling_power_required(
        free_next_temperature_c,
        cooling_setpoint_c,
        capacity_j_k,
        timestep_s,
    )
    max_power_w = sum(system["max_power_w"] for system in systems)
    cooling_power_w = limited_cooling_power(required_power_w, max_power_w)
    electric_power_w = sum(
        cooling_electric_power(
            cooling_power_w * system["max_power_w"] / max_power_w,
            system["performance_ref"]["eer"],
        )
        for system in systems
    )
    return cooling_power_w, electric_power_w


def print_simulation_summary(
    dwelling: dict[str, Any],
    scenario: dict[str, Any],
    results: dict[str, Any],
) -> None:
    """Print a compact simulation summary."""
    print(f"Logement: {dwelling['dwelling_id']}")
    print(f"Scenario: {scenario['scenario_id']}")
    print(f"Heures simulees: {len(results['hourly'])}")
    print()
    print("Temperatures finales")
    last_hour = results["hourly"][-1]
    rooms = get_rooms_by_id(dwelling)
    for room_id, room_result in last_hour["rooms"].items():
        print(f"- {rooms[room_id]['name']}: {room_result['temperature_c']:.1f} C")
    print()
    print("Temperatures max")
    for room_id, room in rooms.items():
        max_temperature_c = max(
            hour["rooms"][room_id]["temperature_c"]
            for hour in results["hourly"]
        )
        print(f"- {room['name']}: {max_temperature_c:.1f} C")
    print()
    print("Bilan energie")
    totals = results["totals"]
    print(f"- Chauffage thermique: {totals['heating_thermal_kwh']:.2f} kWh")
    print(f"- Chauffage electrique: {totals['heating_electric_kwh']:.2f} kWh")
    print(f"- Clim thermique: {totals['cooling_thermal_kwh']:.2f} kWh")
    print(f"- Clim electrique: {totals['cooling_electric_kwh']:.2f} kWh")
    print(f"- Electricite totale: {totals['electricity_kwh']:.2f} kWh")
    print(f"- Cout electricite: {totals['electricity_cost_eur']:.2f} EUR")
    print(f"- CO2 electricite: {totals['electricity_co2_kg']:.2f} kg")


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


def apply_scenario_overrides(
    dwelling: dict[str, Any],
    scenario: dict[str, Any],
) -> None:
    """Apply simple in-place scenario overrides to dwelling inputs."""
    surface_overrides = {
        override["surface_id"]: override
        for override in scenario.get("retrofit", {}).get("surface_overrides", [])
    }
    if not surface_overrides:
        return

    for room in dwelling["rooms"]:
        for surface in room["surfaces"]:
            override = surface_overrides.get(surface["id"])
            if override:
                for key, value in override.items():
                    if key != "surface_id":
                        surface[key] = value


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
