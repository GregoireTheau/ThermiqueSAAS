"""Hourly 1R1C simulation engine for ThermalTwin dwellings."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from utils import (
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

from .dwelling_loader import get_rooms_by_id
from .static_losses import compute_room_static_losses


DISCOMFORT_COLD_THRESHOLD_C = 19.0
DISCOMFORT_HOT_THRESHOLD_C = 26.0


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
    default_cooling_setpoint_c = scenario["setpoints"]["cooling_c"]

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
        "heating_final_kwh": 0.0,
        "heating_final_kwh_by_energy": {},
        "cooling_thermal_kwh": 0.0,
        "cooling_electric_kwh": 0.0,
    }

    for weather_point in scenario["weather"]["hourly"]:
        outdoor_temperature_c = weather_point["outdoor_temperature_c"]
        cooling_setpoint_c = _cooling_setpoint_c(
            scenario,
            weather_point["hour"],
            default_cooling_setpoint_c,
        )
        room_results: dict[str, Any] = {}
        coupling_power_by_room = _compute_coupling_powers(dwelling, temperatures)

        for room_id, room in rooms.items():
            current_temperature_c = temperatures[room_id]
            shutter_opening_ratio = _shutter_opening_ratio(scenario, weather_point["hour"])
            natural_ventilation_ach = _natural_ventilation_ach(
                scenario,
                weather_point["hour"],
                current_temperature_c,
                outdoor_temperature_c,
            )
            loss_data = compute_room_static_losses(
                dwelling,
                room,
                current_temperature_c,
                outdoor_temperature_c,
                air_density_kg_m3,
                air_heat_capacity_j_kgk,
                natural_ventilation_ach=natural_ventilation_ach,
                shutter_opening_ratio=shutter_opening_ratio,
            )
            total_h_w_k = loss_data["total_h_w_k"]
            internal_gain_w = room.get(
                "internal_gain_w_m2",
                dwelling["defaults"]["internal_gain_w_m2"],
            ) * room["floor_area_m2"]
            solar_gain_w = _compute_room_solar_gain(
                room,
                weather_point,
                scenario,
            )
            coupling_power_w = coupling_power_by_room.get(room_id, 0.0)
            transmission_power_w = loss_data["transmission_h_w_k"] * (
                outdoor_temperature_c - current_temperature_c
            )
            ventilation_power_w = loss_data["ventilation_h_w_k"] * (
                outdoor_temperature_c - current_temperature_c
            )
            infiltration_power_w = loss_data["infiltration_h_w_k"] * (
                outdoor_temperature_c - current_temperature_c
            )
            mechanical_ventilation_power_w = loss_data[
                "mechanical_ventilation_h_w_k"
            ] * (
                outdoor_temperature_c - current_temperature_c
            )
            natural_ventilation_power_w = loss_data[
                "natural_ventilation_h_w_k"
            ] * (
                outdoor_temperature_c - current_temperature_c
            )
            envelope_power_w = total_h_w_k * (outdoor_temperature_c - current_temperature_c)
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

            heating_power_w, heating_final_power_by_energy = _compute_heating(
                heating_by_room.get(room_id, []),
                heating_setpoint_c,
                free_next_temperature_c,
                capacities[room_id],
                timestep_s,
                outdoor_temperature_c,
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
            _add_energy_by_vector(
                totals["heating_final_kwh_by_energy"],
                heating_final_power_by_energy,
                timestep_h,
            )
            totals["heating_electric_kwh"] = totals["heating_final_kwh_by_energy"].get(
                "electricity",
                0.0,
            )
            totals["heating_final_kwh"] = sum(
                totals["heating_final_kwh_by_energy"].values()
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
                "transmission_power_w": transmission_power_w,
                "ventilation_power_w": ventilation_power_w,
                "infiltration_power_w": infiltration_power_w,
                "mechanical_ventilation_power_w": mechanical_ventilation_power_w,
                "natural_ventilation_power_w": natural_ventilation_power_w,
            }

        hourly_results.append(
            {
                "hour": weather_point["hour"],
                "month": weather_point.get("month"),
                "outdoor_temperature_c": outdoor_temperature_c,
                "rooms": room_results,
            }
        )

    electricity_kwh = totals["heating_electric_kwh"] + totals["cooling_electric_kwh"]
    totals["electricity_kwh"] = electricity_kwh
    final_energy_kwh_by_energy = dict(totals["heating_final_kwh_by_energy"])
    final_energy_kwh_by_energy["electricity"] = (
        final_energy_kwh_by_energy.get("electricity", 0.0)
        + totals["cooling_electric_kwh"]
    )
    totals["final_energy_kwh_by_energy"] = final_energy_kwh_by_energy
    totals["final_energy_kwh"] = sum(final_energy_kwh_by_energy.values())
    totals["energy_cost_eur"] = _energy_cost(final_energy_kwh_by_energy, scenario)
    totals["energy_co2_kg"] = _energy_co2(final_energy_kwh_by_energy, scenario)
    totals["electricity_cost_eur"] = (
        electricity_kwh * _energy_price(scenario, "electricity")
    )
    totals["electricity_co2_kg"] = (
        electricity_kwh * _co2_factor(scenario, "electricity")
    )

    return {
        "hourly": hourly_results,
        "rooms_summary": _summarize_rooms(
            hourly_results,
            rooms,
            timestep_h,
            DISCOMFORT_COLD_THRESHOLD_C,
            DISCOMFORT_HOT_THRESHOLD_C,
        ),
        "totals": totals,
    }


def apply_scenario_overrides(
    dwelling: dict[str, Any],
    scenario: dict[str, Any],
) -> None:
    """Apply simple in-place scenario overrides to dwelling inputs."""
    retrofit = scenario.get("retrofit", {})

    _apply_surface_overrides(
        dwelling,
        retrofit.get("surface_overrides", []),
    )
    _apply_window_overrides(
        dwelling,
        retrofit.get("window_overrides", []),
    )
    _apply_shutter_overrides(
        dwelling,
        retrofit.get("shutter_overrides", []),
    )
    _apply_system_overrides(
        dwelling,
        retrofit.get("system_overrides", []),
    )
    _add_systems(
        dwelling,
        retrofit.get("add_systems", []),
    )


def _apply_surface_overrides(
    dwelling: dict[str, Any],
    overrides: list[dict[str, Any]],
) -> None:
    for override in overrides:
        surface = _find_surface(dwelling, override["surface_id"])
        _apply_override(surface, override, {"surface_id"})


def _apply_window_overrides(
    dwelling: dict[str, Any],
    overrides: list[dict[str, Any]],
) -> None:
    for override in overrides:
        window = _find_window(dwelling, override["window_id"])
        _apply_override(window, override, {"window_id"})


def _apply_shutter_overrides(
    dwelling: dict[str, Any],
    overrides: list[dict[str, Any]],
) -> None:
    for override in overrides:
        window = _find_window(dwelling, override["window_id"])
        shutter = window.setdefault("shutter", {})
        _apply_override(shutter, override, {"window_id"})


def _apply_system_overrides(
    dwelling: dict[str, Any],
    overrides: list[dict[str, Any]],
) -> None:
    for override in overrides:
        system = _find_system(
            dwelling,
            override["category"],
            override["system_id"],
        )
        _apply_override(system, override, {"category", "system_id"})


def _add_systems(
    dwelling: dict[str, Any],
    systems: list[dict[str, Any]],
) -> None:
    for system in systems:
        system_data = deepcopy(system)
        category = system_data.pop("category")
        _validate_system_category(category)
        dwelling["systems"][category].append(system_data)


def _find_surface(dwelling: dict[str, Any], surface_id: str) -> dict[str, Any]:
    for room in dwelling["rooms"]:
        for surface in room["surfaces"]:
            if surface["id"] == surface_id:
                return surface
    raise ValueError(f"surface override target not found: {surface_id}")


def _find_window(dwelling: dict[str, Any], window_id: str) -> dict[str, Any]:
    for room in dwelling["rooms"]:
        for window in room["windows"]:
            if window["id"] == window_id:
                return window
    raise ValueError(f"window override target not found: {window_id}")


def _find_system(
    dwelling: dict[str, Any],
    category: str,
    system_id: str,
) -> dict[str, Any]:
    _validate_system_category(category)
    for system in dwelling["systems"][category]:
        if system["id"] == system_id:
            return system
    raise ValueError(f"{category} system override target not found: {system_id}")


def _validate_system_category(category: str) -> None:
    if category not in {"heating", "cooling"}:
        raise ValueError(f"unsupported system category: {category}")


def _apply_override(
    target: dict[str, Any],
    override: dict[str, Any],
    ignored_keys: set[str],
) -> None:
    for key, value in override.items():
        if key not in ignored_keys:
            target[key] = deepcopy(value)


def _summarize_rooms(
    hourly_results: list[dict[str, Any]],
    rooms: dict[str, dict[str, Any]],
    timestep_h: float,
    heating_setpoint_c: float,
    cooling_setpoint_c: float,
) -> dict[str, dict[str, float | str]]:
    rooms_summary = {}
    for room_id, room in rooms.items():
        room_hours = [hour["rooms"][room_id] for hour in hourly_results]
        temperatures_c = [hour["temperature_c"] for hour in room_hours]
        rooms_summary[room_id] = {
            "room_name": room["name"],
            "min_temperature_c": min(temperatures_c),
            "max_temperature_c": max(temperatures_c),
            "final_temperature_c": temperatures_c[-1],
            "heating_thermal_kwh": _sum_energy(room_hours, "heating_power_w", timestep_h),
            "cooling_thermal_kwh": _sum_energy(room_hours, "cooling_power_w", timestep_h),
            "solar_gain_kwh": _sum_energy(room_hours, "solar_gain_w", timestep_h),
            "internal_gain_kwh": _sum_energy(room_hours, "internal_gain_w", timestep_h),
            "envelope_exchange_kwh": _sum_energy(room_hours, "envelope_power_w", timestep_h),
            "transmission_exchange_kwh": _sum_energy(
                room_hours,
                "transmission_power_w",
                timestep_h,
            ),
            "ventilation_exchange_kwh": _sum_energy(
                room_hours,
                "ventilation_power_w",
                timestep_h,
            ),
            "infiltration_exchange_kwh": _sum_energy(
                room_hours,
                "infiltration_power_w",
                timestep_h,
            ),
            "mechanical_ventilation_exchange_kwh": _sum_energy(
                room_hours,
                "mechanical_ventilation_power_w",
                timestep_h,
            ),
            "natural_ventilation_exchange_kwh": _sum_energy(
                room_hours,
                "natural_ventilation_power_w",
                timestep_h,
            ),
            "coupling_exchange_kwh": _sum_energy(room_hours, "coupling_power_w", timestep_h),
            "cold_degree_hours": sum(
                max(0.0, heating_setpoint_c - temperature_c) * timestep_h
                for temperature_c in temperatures_c
            ),
            "hot_degree_hours": sum(
                max(0.0, temperature_c - cooling_setpoint_c) * timestep_h
                for temperature_c in temperatures_c
            ),
        }
    return rooms_summary


def _sum_energy(
    room_hours: list[dict[str, Any]],
    power_key: str,
    timestep_h: float,
) -> float:
    return sum(energy_from_power(hour[power_key], timestep_h) for hour in room_hours)


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


def _natural_ventilation_ach(
    scenario: dict[str, Any],
    hour: int,
    room_temperature_c: float,
    outdoor_temperature_c: float,
) -> float:
    controls = scenario.get("controls", {}).get("natural_ventilation", {})
    natural_ach = controls.get("default_ach", 0.0)
    if controls.get("smart_night_cooling", False):
        smart_ach = controls.get("smart_ach", 4.0)
        natural_ach = smart_ach if outdoor_temperature_c < room_temperature_c else 0.0

    for entry in controls.get("hourly", []):
        if entry["hour"] == hour:
            return entry["ach"]
    return natural_ach


def _cooling_setpoint_c(
    scenario: dict[str, Any],
    hour: float,
    default_cooling_setpoint_c: float,
) -> float:
    schedule = scenario.get("controls", {}).get("cooling_setpoint_schedule", {})
    if not schedule:
        return default_cooling_setpoint_c
    hour_in_day = int(hour) % 24
    day_start = int(schedule.get("day_start_hour", 7))
    night_start = int(schedule.get("night_start_hour", 22))
    is_day = day_start <= hour_in_day < night_start
    value = schedule.get("day_c" if is_day else "night_c", default_cooling_setpoint_c)
    return float(value)


def _compute_heating(
    systems: list[dict[str, Any]],
    heating_setpoint_c: float,
    free_next_temperature_c: float,
    capacity_j_k: float,
    timestep_s: float,
    outdoor_temperature_c: float,
) -> tuple[float, dict[str, float]]:
    if not systems:
        return 0.0, {}

    required_power_w = heating_power_required(
        heating_setpoint_c,
        free_next_temperature_c,
        capacity_j_k,
        timestep_s,
    )
    max_power_w = sum(system["max_power_w"] for system in systems)
    heating_power_w = limited_heating_power(required_power_w, max_power_w)
    final_power_by_energy: dict[str, float] = {}
    for system in systems:
        system_thermal_power_w = heating_power_w * system["max_power_w"] / max_power_w
        final_power_w = heating_electric_power(
            system_thermal_power_w,
            _heating_performance(system["performance_ref"], outdoor_temperature_c),
        )
        energy_vector = _heating_energy_vector(system)
        final_power_by_energy[energy_vector] = (
            final_power_by_energy.get(energy_vector, 0.0) + final_power_w
        )
    return heating_power_w, final_power_by_energy


def _heating_performance(
    performance_ref: dict[str, Any],
    outdoor_temperature_c: float,
) -> float:
    if performance_ref["mode"] == "temperature_curve":
        points = sorted(
            performance_ref["points"],
            key=lambda point: point["outdoor_temperature_c"],
        )
        if outdoor_temperature_c <= points[0]["outdoor_temperature_c"]:
            return points[0]["cop"]
        if outdoor_temperature_c >= points[-1]["outdoor_temperature_c"]:
            return points[-1]["cop"]
        for lower, upper in zip(points, points[1:]):
            if lower["outdoor_temperature_c"] <= outdoor_temperature_c <= upper[
                "outdoor_temperature_c"
            ]:
                span = upper["outdoor_temperature_c"] - lower["outdoor_temperature_c"]
                ratio = (outdoor_temperature_c - lower["outdoor_temperature_c"]) / span
                return lower["cop"] + ratio * (upper["cop"] - lower["cop"])
    return performance_ref["cop"]


def _heating_energy_vector(system: dict[str, Any]) -> str:
    if "energy_vector" in system:
        return system["energy_vector"]
    system_ref = system.get("system_ref", "")
    if "gas" in system_ref:
        return "gas"
    if "fuel_oil" in system_ref:
        return "fuel_oil"
    if "wood" in system_ref:
        return "wood"
    return "electricity"


def _add_energy_by_vector(
    total_by_energy: dict[str, float],
    power_by_energy: dict[str, float],
    timestep_h: float,
) -> None:
    for energy, power_w in power_by_energy.items():
        total_by_energy[energy] = total_by_energy.get(energy, 0.0) + energy_from_power(
            power_w,
            timestep_h,
        )


def _energy_cost(energy_kwh_by_energy: dict[str, float], scenario: dict[str, Any]) -> float:
    return sum(
        energy_kwh * _energy_price(scenario, energy)
        for energy, energy_kwh in energy_kwh_by_energy.items()
    )


def _energy_co2(energy_kwh_by_energy: dict[str, float], scenario: dict[str, Any]) -> float:
    return sum(
        energy_kwh * _co2_factor(scenario, energy)
        for energy, energy_kwh in energy_kwh_by_energy.items()
    )


def _energy_price(scenario: dict[str, Any], energy: str) -> float:
    defaults = {
        "electricity": 0.25,
        "gas": 0.11,
        "fuel_oil": 0.13,
        "wood": 0.07,
    }
    return scenario["energy_prices"].get(f"{energy}_eur_kwh", defaults[energy])


def _co2_factor(scenario: dict[str, Any], energy: str) -> float:
    defaults = {
        "electricity": 0.06,
        "gas": 0.227,
        "fuel_oil": 0.324,
        "wood": 0.03,
    }
    return scenario["co2_factors"].get(f"{energy}_kg_kwh", defaults[energy])


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
