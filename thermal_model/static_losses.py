"""Static heat loss calculations for ThermalTwin dwellings."""

from __future__ import annotations

from typing import Any

from utils import (
    airflow_from_ach,
    corrected_transmission_coefficient,
    sum_ua,
    ventilation_heat_transfer_coefficient,
)

from .dwelling_loader import get_rooms_by_id


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
