"""Solar, glazing, shutters and albedo helper functions."""

from __future__ import annotations

from collections.abc import Iterable
from math import cos, radians


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return min(max(value, min_value), max_value)


def sky_ground_view_factors(surface_tilt_deg: float) -> tuple[float, float]:
    """Return simplified sky and ground view factors for a tilted plane."""
    tilt_rad = radians(surface_tilt_deg)
    sky_factor = (1.0 + cos(tilt_rad)) / 2.0
    ground_factor = (1.0 - cos(tilt_rad)) / 2.0
    return sky_factor, ground_factor


def direct_irradiance_on_plane(
    dni_w_m2: float,
    cosine_incidence: float,
) -> float:
    """Return direct irradiance on a plane."""
    return dni_w_m2 * max(0.0, cosine_incidence)


def diffuse_irradiance_on_plane(
    dhi_w_m2: float,
    sky_view_factor: float,
) -> float:
    """Return diffuse sky irradiance on a plane."""
    return dhi_w_m2 * sky_view_factor


def ground_reflected_irradiance_on_plane(
    ghi_w_m2: float,
    ground_albedo: float,
    ground_view_factor: float,
) -> float:
    """Return ground-reflected irradiance on a plane."""
    return ghi_w_m2 * ground_albedo * ground_view_factor


def irradiance_on_plane(
    dni_w_m2: float,
    dhi_w_m2: float,
    ghi_w_m2: float,
    cosine_incidence: float,
    surface_tilt_deg: float,
    ground_albedo: float,
) -> float:
    """Return total plane irradiance from direct, diffuse and ground terms."""
    sky_factor, ground_factor = sky_ground_view_factors(surface_tilt_deg)
    return (
        direct_irradiance_on_plane(dni_w_m2, cosine_incidence)
        + diffuse_irradiance_on_plane(dhi_w_m2, sky_factor)
        + ground_reflected_irradiance_on_plane(
            ghi_w_m2,
            ground_albedo,
            ground_factor,
        )
    )


def mask_irradiance(irradiance_w_m2: float, mask_factor: float) -> float:
    """Return irradiance after a simple mask factor between 0 and 1."""
    return irradiance_w_m2 * _clamp(mask_factor, 0.0, 1.0)


def solar_gain_window(
    area_m2: float,
    irradiance_w_m2: float,
    g_value: float,
    shutter_reduction_factor: float = 1.0,
    mask_factor: float = 1.0,
) -> float:
    """Return solar gain through a window in W."""
    return (
        area_m2
        * irradiance_w_m2
        * _clamp(mask_factor, 0.0, 1.0)
        * g_value
        * shutter_reduction_factor
    )


def solar_gain_for_windows(
    windows: Iterable[tuple[float, float, float, float, float]],
) -> float:
    """Return sum of window gains.

    Each tuple is (area_m2, irradiance_w_m2, g_value, shutter_factor, mask_factor).
    """
    return sum(solar_gain_window(*window) for window in windows)


def shutter_factor(
    closed_factor: float,
    open_factor: float,
    opening_ratio: float,
) -> float:
    """Return linear shutter factor from closed to open state."""
    opening = _clamp(opening_ratio, 0.0, 1.0)
    return closed_factor + opening * (open_factor - closed_factor)


def window_u_with_shutter(
    u_window_w_m2k: float,
    shutter_u_factor: float,
) -> float:
    """Return effective window U-value when shutter insulation is applied."""
    return shutter_u_factor * u_window_w_m2k


def albedo_to_absorptivity(albedo: float) -> float:
    """Return alpha = 1 - rho for an opaque surface."""
    return 1.0 - albedo


def absorbed_opaque_solar_power(
    area_m2: float,
    irradiance_w_m2: float,
    absorptivity: float,
    mask_factor: float = 1.0,
) -> float:
    """Return absorbed solar power on an opaque surface."""
    return (
        area_m2
        * irradiance_w_m2
        * _clamp(mask_factor, 0.0, 1.0)
        * absorptivity
    )


def opaque_solar_power_to_room(
    area_m2: float,
    irradiance_w_m2: float,
    absorptivity: float,
    room_transfer_factor: float,
    mask_factor: float = 1.0,
) -> float:
    """Return opaque solar power estimated to reach the room."""
    return room_transfer_factor * absorbed_opaque_solar_power(
        area_m2,
        irradiance_w_m2,
        absorptivity,
        mask_factor,
    )


def solar_delta_absorbed_power(
    area_m2: float,
    irradiance_w_m2: float,
    absorptivity_before: float,
    absorptivity_after: float,
    mask_factor: float = 1.0,
) -> float:
    """Return reduction in absorbed solar power after albedo improvement."""
    return (
        (absorptivity_before - absorptivity_after)
        * irradiance_w_m2
        * _clamp(mask_factor, 0.0, 1.0)
        * area_m2
    )


def solar_delta_room_power_from_albedo(
    area_m2: float,
    irradiance_w_m2: float,
    absorptivity_before: float,
    absorptivity_after: float,
    room_transfer_factor: float,
    mask_factor: float = 1.0,
) -> float:
    """Return estimated room heat gain reduction after albedo improvement."""
    return room_transfer_factor * solar_delta_absorbed_power(
        area_m2,
        irradiance_w_m2,
        absorptivity_before,
        absorptivity_after,
        mask_factor,
    )
