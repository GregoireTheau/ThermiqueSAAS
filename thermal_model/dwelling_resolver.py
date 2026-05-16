"""Resolve dwelling references against the static reference catalog."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .dwelling_loader import validate_dwelling
from .reference_loader import (
    ReferenceCatalog,
    get_climate_zone_for_department,
    get_cooling_system_reference,
    get_envelope_default_reference,
    get_heating_system_reference,
    get_shutter_reference,
    get_ventilation_reference,
    get_window_reference,
)

Dwelling = dict[str, Any]


def resolve_dwelling_references(
    dwelling: dict[str, Any],
    catalog: ReferenceCatalog,
    validate: bool = True,
) -> Dwelling:
    """Return a copy of dwelling with missing fields filled from references.

    Explicit values in the dwelling always win over reference values.
    """
    resolved = deepcopy(dwelling)

    _resolve_location(resolved, catalog)
    envelope_default = _resolve_defaults(resolved, catalog)
    _resolve_rooms(resolved, catalog, envelope_default)
    _resolve_systems(resolved, catalog)

    if validate:
        validate_dwelling(resolved)

    return resolved


def _resolve_location(dwelling: Dwelling, catalog: ReferenceCatalog) -> None:
    location = dwelling["location"]
    if "climate_zone_id" not in location:
        department_code = location.get("postal_code", "")[:2]
        if department_code:
            location["climate_zone_id"] = get_climate_zone_for_department(
                catalog,
                department_code,
            )


def _resolve_defaults(
    dwelling: Dwelling,
    catalog: ReferenceCatalog,
) -> dict[str, Any] | None:
    defaults = dwelling["defaults"]
    building_period_ref = defaults.get("building_period_ref")
    if not building_period_ref:
        return None

    envelope_default = get_envelope_default_reference(catalog, building_period_ref)
    _set_if_missing(
        defaults,
        "thermal_bridge_factor",
        envelope_default["thermal_bridge_factor"],
    )
    _set_if_missing(
        defaults,
        "equivalent_capacity_j_m2k",
        envelope_default["equivalent_capacity_j_m2k"],
    )
    return envelope_default


def _resolve_rooms(
    dwelling: Dwelling,
    catalog: ReferenceCatalog,
    envelope_default: dict[str, Any] | None,
) -> None:
    defaults = dwelling["defaults"]

    for room in dwelling["rooms"]:
        _set_if_missing(room, "initial_temperature_c", defaults["initial_temperature_c"])
        _set_if_missing(
            room,
            "equivalent_capacity_j_m2k",
            defaults["equivalent_capacity_j_m2k"],
        )
        _set_if_missing(room, "internal_gain_w_m2", defaults["internal_gain_w_m2"])
        _resolve_room_ventilation(room, catalog, defaults)

        for surface in room["surfaces"]:
            _resolve_surface(surface, envelope_default)

        for window in room["windows"]:
            _resolve_window(window, catalog)


def _resolve_room_ventilation(
    room: dict[str, Any],
    catalog: ReferenceCatalog,
    defaults: dict[str, Any],
) -> None:
    ventilation = room.setdefault("ventilation", {})
    ventilation_ref = ventilation.get("ventilation_ref")
    if ventilation_ref:
        reference = get_ventilation_reference(catalog, ventilation_ref)
        _set_if_missing(ventilation, "ach_h", reference["default_ach_h"])

    _set_if_missing(ventilation, "mode", "ach")
    _set_if_missing(ventilation, "ach_h", defaults["ach_h"])


def _resolve_surface(
    surface: dict[str, Any],
    envelope_default: dict[str, Any] | None,
) -> None:
    if not envelope_default:
        return

    u_values = envelope_default.get("u_values", {})
    surface_type = surface["type"]
    if surface_type in u_values:
        _set_if_missing(surface, "u_value_w_m2k", u_values[surface_type])


def _resolve_window(window: dict[str, Any], catalog: ReferenceCatalog) -> None:
    window_ref = window.get("window_ref")
    if window_ref:
        reference = get_window_reference(catalog, window_ref)
        _set_if_missing(window, "u_value_w_m2k", reference["u_value_w_m2k"])
        _set_if_missing(window, "g_value", reference["g_value"])

    shutter_ref = window.get("shutter_ref")
    if shutter_ref:
        reference = get_shutter_reference(catalog, shutter_ref)
        shutter = window.setdefault("shutter", {})
        _set_if_missing(shutter, "type", reference["type"])
        _set_if_missing(
            shutter,
            "solar_factor_closed",
            reference["solar_factor_closed"],
        )
        _set_if_missing(shutter, "solar_factor_open", reference["solar_factor_open"])
        _set_if_missing(shutter, "u_factor_closed", reference["u_factor_closed"])


def _resolve_systems(dwelling: Dwelling, catalog: ReferenceCatalog) -> None:
    systems = dwelling["systems"]
    _resolve_building_ventilation(systems, catalog)

    for system in systems["heating"]:
        system_ref = system.get("system_ref")
        if system_ref:
            reference = get_heating_system_reference(catalog, system_ref)
            _set_if_missing(system, "type", reference["type"])
            _set_if_missing(system, "performance_ref", reference["performance_ref"])

    for system in systems["cooling"]:
        system_ref = system.get("system_ref")
        if system_ref:
            reference = get_cooling_system_reference(catalog, system_ref)
            _set_if_missing(system, "type", reference["type"])
            _set_if_missing(system, "performance_ref", reference["performance_ref"])


def _resolve_building_ventilation(
    systems: dict[str, Any],
    catalog: ReferenceCatalog,
) -> None:
    ventilation = systems["ventilation"]
    ventilation_ref = ventilation.get("ventilation_ref")
    if not ventilation_ref:
        return

    reference = get_ventilation_reference(catalog, ventilation_ref)
    _set_if_missing(ventilation, "type", _ventilation_system_type(reference["id"]))
    _set_if_missing(ventilation, "default_ach_h", reference["default_ach_h"])


def _ventilation_system_type(ventilation_ref: str) -> str:
    if "double_flow" in ventilation_ref:
        return "double_flow"
    if "natural" in ventilation_ref:
        return "natural"
    if "simple_flow" in ventilation_ref:
        return "simple_flow"
    return "other"


def _set_if_missing(data: dict[str, Any], key: str, value: Any) -> None:
    if key not in data:
        data[key] = deepcopy(value)
