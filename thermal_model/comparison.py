"""Scenario comparison engine for ThermalTwin dwellings."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .dwelling_loader import get_rooms_by_id
from .simulation import apply_scenario_overrides, simulate_1r1c


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
        before_summary = before_results["rooms_summary"][room_id]
        after_summary = after_results["rooms_summary"][room_id]
        room_deltas[room_id] = {
            "room_name": room["name"],
            "before_max_temperature_c": before_summary["max_temperature_c"],
            "after_max_temperature_c": after_summary["max_temperature_c"],
            "delta_max_temperature_c": _delta_room_metric(
                before_summary,
                after_summary,
                "max_temperature_c",
            ),
            "before_final_temperature_c": before_summary["final_temperature_c"],
            "after_final_temperature_c": after_summary["final_temperature_c"],
            "delta_final_temperature_c": _delta_room_metric(
                before_summary,
                after_summary,
                "final_temperature_c",
            ),
            "before_hot_degree_hours": before_summary["hot_degree_hours"],
            "after_hot_degree_hours": after_summary["hot_degree_hours"],
            "delta_hot_degree_hours": _delta_room_metric(
                before_summary,
                after_summary,
                "hot_degree_hours",
            ),
            "before_cold_degree_hours": before_summary["cold_degree_hours"],
            "after_cold_degree_hours": after_summary["cold_degree_hours"],
            "delta_cold_degree_hours": _delta_room_metric(
                before_summary,
                after_summary,
                "cold_degree_hours",
            ),
            "delta_solar_gain_kwh": _delta_room_metric(
                before_summary,
                after_summary,
                "solar_gain_kwh",
            ),
            "delta_transmission_exchange_kwh": _delta_room_metric(
                before_summary,
                after_summary,
                "transmission_exchange_kwh",
            ),
            "delta_ventilation_exchange_kwh": _delta_room_metric(
                before_summary,
                after_summary,
                "ventilation_exchange_kwh",
            ),
            "delta_heating_thermal_kwh": _delta_room_metric(
                before_summary,
                after_summary,
                "heating_thermal_kwh",
            ),
            "delta_cooling_thermal_kwh": _delta_room_metric(
                before_summary,
                after_summary,
                "cooling_thermal_kwh",
            ),
        }

    deltas = {
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
    }

    return {
        "comparison_schema_version": "0.3",
        "dwelling_id": dwelling["dwelling_id"],
        "before_scenario_id": before_scenario["scenario_id"],
        "after_scenario_id": after_scenario["scenario_id"],
        "experiment": _build_experiment_context(before_scenario, after_scenario),
        "summary": _build_summary(before_results, after_results, deltas),
        "before": before_results,
        "after": after_results,
        "deltas": deltas,
    }


def _build_experiment_context(
    before_scenario: dict[str, Any],
    after_scenario: dict[str, Any],
) -> dict[str, Any]:
    before_weather = before_scenario["weather"]["hourly"]
    after_weather = after_scenario["weather"]["hourly"]
    if len(before_weather) != len(after_weather):
        raise ValueError("before and after scenarios must have the same weather duration")
    if before_scenario["timestep_h"] != after_scenario["timestep_h"]:
        raise ValueError("before and after scenarios must have the same timestep")

    duration_hours = len(before_weather) * before_scenario["timestep_h"]
    outdoor_temperatures = [
        hour["outdoor_temperature_c"]
        for hour in before_weather
    ]
    experiment = before_scenario.get("experiment", {})
    return {
        "adaptation_id": experiment.get("adaptation_id", "unknown"),
        "adaptation_label": experiment.get("adaptation_label", ""),
        "role": experiment.get("role", "primary"),
        "label": experiment.get("label", ""),
        "season": experiment.get("season", ""),
        "weather_variant": experiment.get("weather_variant", ""),
        "reason": experiment.get("reason", ""),
        "before_description": before_scenario.get("description", ""),
        "after_description": after_scenario.get("description", ""),
        "duration_hours": duration_hours,
        "duration_days": duration_hours / 24.0,
        "timestep_h": before_scenario["timestep_h"],
        "weather_source": before_scenario["weather"].get("source", "unknown"),
        "weather_summary": {
            "outdoor_temperature_min_c": min(outdoor_temperatures),
            "outdoor_temperature_max_c": max(outdoor_temperatures),
        },
        "setpoints": before_scenario["setpoints"],
        "initial_temperature_mode": "scenario_initial_temperatures",
        "intervention": _summarize_retrofit(after_scenario.get("retrofit", {})),
    }


def _summarize_retrofit(retrofit: dict[str, Any]) -> dict[str, Any]:
    return {
        "surface_overrides": _summarize_overrides(
            retrofit.get("surface_overrides", []),
            "surface_id",
        ),
        "window_overrides": _summarize_overrides(
            retrofit.get("window_overrides", []),
            "window_id",
        ),
        "shutter_overrides": _summarize_overrides(
            retrofit.get("shutter_overrides", []),
            "window_id",
        ),
        "system_overrides": _summarize_overrides(
            retrofit.get("system_overrides", []),
            "system_id",
        ),
        "add_systems": _summarize_overrides(
            retrofit.get("add_systems", []),
            "id",
        ),
    }


def _summarize_overrides(
    overrides: list[dict[str, Any]],
    target_key: str,
) -> dict[str, Any]:
    ignored_keys = {target_key, "category"}
    changed_fields = sorted({
        key
        for override in overrides
        for key in override
        if key not in ignored_keys
    })
    targets = [
        override[target_key]
        for override in overrides
        if target_key in override
    ]
    return {
        "count": len(overrides),
        "targets": targets,
        "changed_fields": changed_fields,
    }


def _build_summary(
    before_results: dict[str, Any],
    after_results: dict[str, Any],
    deltas: dict[str, Any],
) -> dict[str, Any]:
    room_deltas = deltas["rooms"]
    comfort_room = max(
        room_deltas.values(),
        key=lambda room: (
            room["delta_hot_degree_hours"]
            + room["delta_cold_degree_hours"]
            + max(0.0, room["delta_max_temperature_c"]) * 24.0
        ),
    )
    return {
        "headline_metrics": {
            "electricity_saved_kwh": deltas["electricity_kwh"],
            "cost_saved_eur": deltas["electricity_cost_eur"],
            "co2_saved_kg": deltas["electricity_co2_kg"],
            "max_temperature_reduction_c": max(
                room["delta_max_temperature_c"] for room in room_deltas.values()
            ),
            "hot_degree_hours_reduced": sum(
                room["delta_hot_degree_hours"] for room in room_deltas.values()
            ),
            "cold_degree_hours_reduced": sum(
                room["delta_cold_degree_hours"] for room in room_deltas.values()
            ),
        },
        "comfort_gain": {
            "label": _comfort_gain_label(comfort_room),
            "room_name": comfort_room["room_name"],
            "max_temperature_reduction_c": comfort_room["delta_max_temperature_c"],
            "hot_degree_hours_reduced": comfort_room["delta_hot_degree_hours"],
            "cold_degree_hours_reduced": comfort_room["delta_cold_degree_hours"],
        },
        "energy_savings": {
            "label": _energy_savings_label(deltas),
            "electricity_before_kwh": before_results["totals"]["electricity_kwh"],
            "electricity_after_kwh": after_results["totals"]["electricity_kwh"],
            "electricity_saved_kwh": deltas["electricity_kwh"],
            "cost_saved_eur": deltas["electricity_cost_eur"],
            "co2_saved_kg": deltas["electricity_co2_kg"],
        },
        "main_gain_driver": _main_gain_driver(deltas),
        "room_cards": [
            {
                "room_id": room_id,
                "room_name": room["room_name"],
                "max_temperature_reduction_c": room["delta_max_temperature_c"],
                "hot_degree_hours_reduced": room["delta_hot_degree_hours"],
                "cold_degree_hours_reduced": room["delta_cold_degree_hours"],
                "heating_thermal_saved_kwh": room["delta_heating_thermal_kwh"],
                "cooling_thermal_saved_kwh": room["delta_cooling_thermal_kwh"],
            }
            for room_id, room in room_deltas.items()
        ],
    }


def _comfort_gain_label(room_delta: dict[str, Any]) -> str:
    if room_delta["delta_hot_degree_hours"] > 0:
        return (
            f"{room_delta['room_name']}: "
            f"{room_delta['delta_hot_degree_hours']:.0f} degres-heures chauds evites"
        )
    if room_delta["delta_cold_degree_hours"] > 0:
        return (
            f"{room_delta['room_name']}: "
            f"{room_delta['delta_cold_degree_hours']:.0f} degres-heures froids evites"
        )
    if room_delta["delta_max_temperature_c"] > 0:
        return (
            f"{room_delta['room_name']}: "
            f"{room_delta['delta_max_temperature_c']:.1f} C de temperature max en moins"
        )
    return "Confort maintenu"


def _energy_savings_label(deltas: dict[str, Any]) -> str:
    if deltas["electricity_kwh"] > 0:
        return (
            f"{deltas['electricity_kwh']:.2f} kWh, "
            f"{deltas['electricity_cost_eur']:.2f} EUR et "
            f"{deltas['electricity_co2_kg']:.2f} kg CO2 economises"
        )
    if deltas["electricity_kwh"] < 0:
        return f"{abs(deltas['electricity_kwh']):.2f} kWh electriques supplementaires"
    return "Consommation electrique inchangee"


def _main_gain_driver(deltas: dict[str, Any]) -> dict[str, Any]:
    room_totals = {
        "solar_gain_kwh": _sum_room_delta(deltas, "delta_solar_gain_kwh"),
        "transmission_exchange_kwh": _sum_room_delta(
            deltas,
            "delta_transmission_exchange_kwh",
        ),
        "ventilation_exchange_kwh": _sum_room_delta(
            deltas,
            "delta_ventilation_exchange_kwh",
        ),
        "heating_thermal_kwh": _sum_room_delta(deltas, "delta_heating_thermal_kwh"),
        "cooling_thermal_kwh": _sum_room_delta(deltas, "delta_cooling_thermal_kwh"),
    }
    candidates = [
        (
            "system_efficiency",
            "meilleure efficacite des equipements",
            max(deltas["heating_electric_kwh"], deltas["cooling_electric_kwh"]),
            "kWh electriques",
        ),
        (
            "solar_gains",
            "apports solaires reduits",
            room_totals["solar_gain_kwh"],
            "kWh solaires",
        ),
        (
            "transmission",
            "echanges par transmission reduits",
            abs(room_totals["transmission_exchange_kwh"]),
            "kWh",
        ),
        (
            "ventilation",
            "echanges par ventilation reduits",
            abs(room_totals["ventilation_exchange_kwh"]),
            "kWh",
        ),
        (
            "heating_need",
            "besoin de chauffage reduit",
            room_totals["heating_thermal_kwh"],
            "kWh thermiques",
        ),
        (
            "cooling_need",
            "besoin de climatisation reduit",
            room_totals["cooling_thermal_kwh"],
            "kWh thermiques",
        ),
    ]
    key, label, value, unit = max(candidates, key=lambda candidate: candidate[2])
    return {
        "key": key,
        "label": label,
        "value": value,
        "unit": unit,
    }


def _sum_room_delta(deltas: dict[str, Any], key: str) -> float:
    return sum(room[key] for room in deltas["rooms"].values())


def _delta_room_metric(
    before_summary: dict[str, Any],
    after_summary: dict[str, Any],
    key: str,
) -> float:
    return before_summary[key] - after_summary[key]


def _delta_total(
    before_results: dict[str, Any],
    after_results: dict[str, Any],
    key: str,
) -> float:
    return before_results["totals"][key] - after_results["totals"][key]
