"""Load and validate ThermalTwin dwelling JSON files.

This module deliberately avoids external dependencies. JSON Schema validates
shape; this loader handles practical cross-checks the modelling engine needs.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

Dwelling = dict[str, Any]
Room = dict[str, Any]
Surface = dict[str, Any]
Window = dict[str, Any]
ThermalLink = dict[str, Any]


class DwellingValidationError(ValueError):
    """Raised when a dwelling JSON is structurally inconsistent."""


def load_dwelling(path: str | Path, validate: bool = True) -> Dwelling:
    """Load a dwelling JSON file and optionally validate it."""
    with Path(path).open(encoding="utf-8") as file:
        dwelling = json.load(file)

    if validate:
        validate_dwelling(dwelling)

    return dwelling


def validate_dwelling(dwelling: Mapping[str, Any]) -> None:
    """Validate the cross-field constraints needed before modelling."""
    _require_keys(
        dwelling,
        (
            "schema_version",
            "dwelling_id",
            "metadata",
            "location",
            "defaults",
            "rooms",
            "thermal_links",
            "systems",
        ),
        "dwelling",
    )

    if dwelling["schema_version"] != "0.1":
        raise DwellingValidationError("dwelling.schema_version must be '0.1'")

    rooms = dwelling["rooms"]
    if not isinstance(rooms, list) or not rooms:
        raise DwellingValidationError("dwelling.rooms must be a non-empty list")

    room_ids = _validate_rooms(rooms)
    _validate_thermal_links(dwelling["thermal_links"], room_ids)
    _validate_systems(dwelling["systems"], room_ids)


def get_rooms_by_id(dwelling: Mapping[str, Any]) -> dict[str, Room]:
    """Return rooms indexed by room ID."""
    return {room["id"]: room for room in dwelling["rooms"]}


def iter_external_surfaces(dwelling: Mapping[str, Any]) -> Iterator[tuple[Room, Surface]]:
    """Yield exterior, ground, party and unheated-space surfaces with their room."""
    external_boundaries = {"exterior", "ground", "unheated_space", "party"}
    for room in dwelling["rooms"]:
        for surface in room.get("surfaces", []):
            if surface.get("boundary") in external_boundaries:
                yield room, surface


def iter_windows(dwelling: Mapping[str, Any]) -> Iterator[tuple[Room, Window]]:
    """Yield windows with their room."""
    for room in dwelling["rooms"]:
        for window in room.get("windows", []):
            yield room, window


def iter_thermal_links(dwelling: Mapping[str, Any]) -> Iterator[ThermalLink]:
    """Yield thermal links between rooms."""
    yield from dwelling.get("thermal_links", [])


def _validate_rooms(rooms: list[Mapping[str, Any]]) -> set[str]:
    room_ids: list[str] = []
    object_ids: list[str] = []

    for room in rooms:
        _require_keys(
            room,
            (
                "id",
                "name",
                "type",
                "floor_area_m2",
                "height_m",
                "volume_m3",
                "surfaces",
                "windows",
            ),
            "room",
        )
        _validate_positive(room["floor_area_m2"], f"room {room['id']}.floor_area_m2")
        _validate_positive(room["height_m"], f"room {room['id']}.height_m")
        _validate_positive(room["volume_m3"], f"room {room['id']}.volume_m3")

        if "equivalent_capacity_j_m2k" in room:
            _validate_positive(
                room["equivalent_capacity_j_m2k"],
                f"room {room['id']}.equivalent_capacity_j_m2k",
            )
        if "internal_gain_w_m2" in room:
            _validate_non_negative(
                room["internal_gain_w_m2"],
                f"room {room['id']}.internal_gain_w_m2",
            )
        if "ventilation" in room:
            _validate_room_ventilation(room["ventilation"], room["id"])

        room_ids.append(room["id"])
        object_ids.append(room["id"])

        for surface in room["surfaces"]:
            _validate_surface(surface, room["id"])
            object_ids.append(surface["id"])

        for window in room["windows"]:
            _validate_window(window, room["id"])
            object_ids.append(window["id"])

    _validate_unique(room_ids, "room ids")
    _validate_unique(object_ids, "room, surface and window ids")
    return set(room_ids)


def _validate_room_ventilation(ventilation: Mapping[str, Any], room_id: str) -> None:
    _require_keys(ventilation, ("mode", "ach_h"), f"room {room_id}.ventilation")
    if ventilation["mode"] != "ach":
        raise DwellingValidationError(
            f"room {room_id}.ventilation.mode must be 'ach'"
        )
    _validate_non_negative(ventilation["ach_h"], f"room {room_id}.ventilation.ach_h")


def _validate_surface(surface: Mapping[str, Any], room_id: str) -> None:
    _require_keys(
        surface,
        ("id", "type", "boundary", "area_m2", "u_value_w_m2k"),
        f"surface in room {room_id}",
    )
    _validate_positive(surface["area_m2"], f"surface {surface['id']}.area_m2")
    _validate_positive(
        surface["u_value_w_m2k"],
        f"surface {surface['id']}.u_value_w_m2k",
    )

    if "azimuth_deg" in surface:
        _validate_between(surface["azimuth_deg"], 0, 360, f"surface {surface['id']}.azimuth_deg")
    if "tilt_deg" in surface:
        _validate_between(surface["tilt_deg"], 0, 180, f"surface {surface['id']}.tilt_deg")
    for key in ("albedo", "solar_to_room_factor", "mask_factor"):
        if key in surface:
            _validate_factor(surface[key], f"surface {surface['id']}.{key}")


def _validate_window(window: Mapping[str, Any], room_id: str) -> None:
    _require_keys(
        window,
        ("id", "area_m2", "u_value_w_m2k", "g_value", "azimuth_deg", "tilt_deg"),
        f"window in room {room_id}",
    )
    _validate_positive(window["area_m2"], f"window {window['id']}.area_m2")
    _validate_positive(
        window["u_value_w_m2k"],
        f"window {window['id']}.u_value_w_m2k",
    )
    _validate_factor(window["g_value"], f"window {window['id']}.g_value")
    _validate_between(window["azimuth_deg"], 0, 360, f"window {window['id']}.azimuth_deg")
    _validate_between(window["tilt_deg"], 0, 180, f"window {window['id']}.tilt_deg")

    if "mask_factor" in window:
        _validate_factor(window["mask_factor"], f"window {window['id']}.mask_factor")
    if "shutter" in window:
        _validate_shutter(window["shutter"], window["id"])


def _validate_shutter(shutter: Mapping[str, Any], window_id: str) -> None:
    _require_keys(
        shutter,
        ("type", "solar_factor_closed", "solar_factor_open", "u_factor_closed"),
        f"window {window_id}.shutter",
    )
    for key in ("solar_factor_closed", "solar_factor_open", "u_factor_closed"):
        _validate_factor(shutter[key], f"window {window_id}.shutter.{key}")


def _validate_thermal_links(
    links: list[Mapping[str, Any]],
    room_ids: set[str],
) -> None:
    link_ids: list[str] = []
    for link in links:
        _require_keys(
            link,
            (
                "id",
                "room_a",
                "room_b",
                "type",
                "area_m2",
                "u_value_w_m2k",
                "opening_factor",
            ),
            "thermal_link",
        )
        link_ids.append(link["id"])
        if link["room_a"] not in room_ids:
            raise DwellingValidationError(
                f"thermal link {link['id']} references unknown room_a {link['room_a']}"
            )
        if link["room_b"] not in room_ids:
            raise DwellingValidationError(
                f"thermal link {link['id']} references unknown room_b {link['room_b']}"
            )
        if link["room_a"] == link["room_b"]:
            raise DwellingValidationError(
                f"thermal link {link['id']} cannot link a room to itself"
            )
        _validate_positive(link["area_m2"], f"thermal link {link['id']}.area_m2")
        _validate_positive(
            link["u_value_w_m2k"],
            f"thermal link {link['id']}.u_value_w_m2k",
        )
        _validate_non_negative(
            link["opening_factor"],
            f"thermal link {link['id']}.opening_factor",
        )

    _validate_unique(link_ids, "thermal link ids")


def _validate_systems(systems: Mapping[str, Any], room_ids: set[str]) -> None:
    _require_keys(systems, ("heating", "cooling", "ventilation"), "systems")
    system_ids: list[str] = []

    for system_type in ("heating", "cooling"):
        for system in systems[system_type]:
            _require_keys(
                system,
                ("id", "type", "served_rooms", "max_power_w", "performance_ref"),
                f"{system_type} system",
            )
            system_ids.append(system["id"])
            _validate_positive(
                system["max_power_w"],
                f"{system_type} system {system['id']}.max_power_w",
            )
            _validate_served_rooms(system["served_rooms"], room_ids, system["id"])
            _validate_performance_ref(
                system["performance_ref"],
                system_type,
                system["id"],
            )

    _validate_unique(system_ids, "system ids")

    ventilation = systems["ventilation"]
    _require_keys(ventilation, ("type", "default_ach_h"), "systems.ventilation")
    _validate_non_negative(
        ventilation["default_ach_h"],
        "systems.ventilation.default_ach_h",
    )


def _validate_served_rooms(
    served_rooms: list[str],
    room_ids: set[str],
    system_id: str,
) -> None:
    if not served_rooms:
        raise DwellingValidationError(f"system {system_id}.served_rooms cannot be empty")
    _validate_unique(served_rooms, f"system {system_id}.served_rooms")
    for room_id in served_rooms:
        if room_id not in room_ids:
            raise DwellingValidationError(
                f"system {system_id} references unknown room {room_id}"
            )


def _validate_performance_ref(
    performance_ref: Mapping[str, Any],
    system_type: str,
    system_id: str,
) -> None:
    _require_keys(performance_ref, ("mode",), f"system {system_id}.performance_ref")
    if performance_ref["mode"] != "constant":
        raise DwellingValidationError(
            f"system {system_id}.performance_ref.mode must be 'constant'"
        )

    performance_key = "cop" if system_type == "heating" else "eer"
    _require_keys(
        performance_ref,
        (performance_key,),
        f"system {system_id}.performance_ref",
    )
    _validate_positive(
        performance_ref[performance_key],
        f"system {system_id}.performance_ref.{performance_key}",
    )


def _require_keys(
    data: Mapping[str, Any],
    required_keys: tuple[str, ...],
    context: str,
) -> None:
    missing = [key for key in required_keys if key not in data]
    if missing:
        raise DwellingValidationError(
            f"{context} is missing required keys: {', '.join(missing)}"
        )


def _validate_unique(values: list[str], context: str) -> None:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise DwellingValidationError(
            f"duplicate {context}: {', '.join(duplicates)}"
        )


def _validate_positive(value: float, context: str) -> None:
    if value <= 0:
        raise DwellingValidationError(f"{context} must be > 0")


def _validate_non_negative(value: float, context: str) -> None:
    if value < 0:
        raise DwellingValidationError(f"{context} must be >= 0")


def _validate_factor(value: float, context: str) -> None:
    _validate_between(value, 0, 1, context)


def _validate_between(
    value: float,
    min_value: float,
    max_value: float,
    context: str,
) -> None:
    if value < min_value or value > max_value:
        raise DwellingValidationError(
            f"{context} must be between {min_value} and {max_value}"
        )
