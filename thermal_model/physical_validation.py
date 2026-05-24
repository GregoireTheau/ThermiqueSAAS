"""Physical-domain warnings for model inputs and outputs."""

from __future__ import annotations

from typing import Any

from .static_losses import compute_room_static_losses


MAX_WINDOW_TO_FLOOR_RATIO = 0.6
MAX_TOTAL_VENTILATION_ACH = 3.0
MAX_PLAUSIBLE_ROOM_TEMPERATURE_C = 45.0


def collect_model_warnings(
    dwelling: dict[str, Any],
    scenario: dict[str, Any] | None = None,
    results: dict[str, Any] | None = None,
    *,
    air_density_kg_m3: float = 1.2,
    air_heat_capacity_j_kgk: float = 1005.0,
) -> list[dict[str, Any]]:
    """Return non-blocking warnings for physically suspicious model conditions."""
    warnings = []
    warnings.extend(_window_area_warnings(dwelling))
    warnings.extend(_ventilation_warnings(dwelling))
    if scenario:
        warnings.extend(
            _heating_capacity_warnings(
                dwelling,
                scenario,
                air_density_kg_m3,
                air_heat_capacity_j_kgk,
            ),
        )
    if results:
        warnings.extend(_temperature_output_warnings(results))
    return warnings


def _window_area_warnings(dwelling: dict[str, Any]) -> list[dict[str, Any]]:
    warnings = []
    for room in dwelling["rooms"]:
        window_area_m2 = sum(window["area_m2"] for window in room["windows"])
        ratio = window_area_m2 / room["floor_area_m2"]
        if ratio > MAX_WINDOW_TO_FLOOR_RATIO:
            warnings.append(
                _warning(
                    "window_area_unusually_high",
                    "Window area is unusually high compared with floor area.",
                    room_id=room["id"],
                    value=ratio,
                    threshold=MAX_WINDOW_TO_FLOOR_RATIO,
                ),
            )
    return warnings


def _ventilation_warnings(dwelling: dict[str, Any]) -> list[dict[str, Any]]:
    warnings = []
    for room in dwelling["rooms"]:
        ventilation = room.get("ventilation", {})
        total_ach = ventilation.get("infiltration_ach", 0.0) + ventilation.get(
            "mechanical_ach",
            ventilation.get("ach_h", dwelling["defaults"]["ach_h"]),
        )
        if total_ach > MAX_TOTAL_VENTILATION_ACH:
            warnings.append(
                _warning(
                    "ventilation_ach_unusually_high",
                    "Ventilation air change rate is unusually high for a dwelling.",
                    room_id=room["id"],
                    value=total_ach,
                    threshold=MAX_TOTAL_VENTILATION_ACH,
                ),
            )
    return warnings


def _heating_capacity_warnings(
    dwelling: dict[str, Any],
    scenario: dict[str, Any],
    air_density_kg_m3: float,
    air_heat_capacity_j_kgk: float,
) -> list[dict[str, Any]]:
    heating_setpoint_c = scenario["setpoints"]["heating_c"]
    outdoor_min_c = min(
        point["outdoor_temperature_c"]
        for point in scenario["weather"]["hourly"]
    )
    if outdoor_min_c >= heating_setpoint_c:
        return []

    heating_by_room = _heating_power_by_room(dwelling)
    warnings = []
    for room in dwelling["rooms"]:
        losses = compute_room_static_losses(
            dwelling,
            room,
            heating_setpoint_c,
            outdoor_min_c,
            air_density_kg_m3,
            air_heat_capacity_j_kgk,
        )
        available_power_w = heating_by_room.get(room["id"], 0.0)
        required_power_w = losses["total_loss_w"]
        if available_power_w < required_power_w:
            warnings.append(
                _warning(
                    "heating_power_may_be_insufficient",
                    "Heating power may be insufficient to hold the target temperature.",
                    room_id=room["id"],
                    value=available_power_w,
                    threshold=required_power_w,
                ),
            )
    return warnings


def _temperature_output_warnings(results: dict[str, Any]) -> list[dict[str, Any]]:
    warnings = []
    for room_id, summary in results["rooms_summary"].items():
        max_temperature_c = summary["max_temperature_c"]
        if max_temperature_c > MAX_PLAUSIBLE_ROOM_TEMPERATURE_C:
            warnings.append(
                _warning(
                    "room_temperature_unusually_high",
                    "Simulated room temperature is outside the usual dwelling validity range.",
                    room_id=room_id,
                    value=max_temperature_c,
                    threshold=MAX_PLAUSIBLE_ROOM_TEMPERATURE_C,
                ),
            )
    return warnings


def _heating_power_by_room(dwelling: dict[str, Any]) -> dict[str, float]:
    heating_by_room: dict[str, float] = {}
    for system in dwelling["systems"]["heating"]:
        for room_id in system["served_rooms"]:
            heating_by_room[room_id] = heating_by_room.get(room_id, 0.0) + system[
                "max_power_w"
            ]
    return heating_by_room


def _warning(
    code: str,
    message: str,
    *,
    room_id: str,
    value: float,
    threshold: float,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "warning",
        "room_id": room_id,
        "message": message,
        "value": value,
        "threshold": threshold,
    }
