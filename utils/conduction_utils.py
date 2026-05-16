"""Conduction, transmission and thermal bridge helper functions."""

from __future__ import annotations

from collections.abc import Iterable


def thermal_resistance_layer(thickness_m: float, conductivity_w_mk: float) -> float:
    """Return layer thermal resistance R = e / lambda in m2.K/W."""
    return thickness_m / conductivity_w_mk


def thermal_resistance_total(
    layer_resistances_m2k_w: Iterable[float],
    r_si_m2k_w: float = 0.0,
    r_se_m2k_w: float = 0.0,
) -> float:
    """Return total resistance including optional surface resistances."""
    return r_si_m2k_w + sum(layer_resistances_m2k_w) + r_se_m2k_w


def u_value_from_resistance(resistance_m2k_w: float) -> float:
    """Return U = 1 / R in W/m2.K."""
    return 1.0 / resistance_m2k_w


def transmission_heat_flow(
    u_w_m2k: float,
    area_m2: float,
    source_temperature_c: float,
    room_temperature_c: float,
) -> float:
    """Return heat flow into the room: Phi = U * A * (T_source - T_room)."""
    return u_w_m2k * area_m2 * (source_temperature_c - room_temperature_c)


def heat_loss(
    u_w_m2k: float,
    area_m2: float,
    room_temperature_c: float,
    exterior_temperature_c: float,
) -> float:
    """Return displayed heat loss as a positive value when the room loses heat."""
    return u_w_m2k * area_m2 * (room_temperature_c - exterior_temperature_c)


def adjacent_heat_flow(
    u_w_m2k: float,
    area_m2: float,
    adjacent_temperature_c: float,
    room_temperature_c: float,
) -> float:
    """Return heat flow from an adjacent zone into the room."""
    return transmission_heat_flow(
        u_w_m2k,
        area_m2,
        adjacent_temperature_c,
        room_temperature_c,
    )


def reduced_adjacent_heat_flow(
    u_w_m2k: float,
    area_m2: float,
    exterior_temperature_c: float,
    room_temperature_c: float,
    loss_reduction_factor: float,
) -> float:
    """Return reduced heat flow for an unmodelled adjacent space."""
    return loss_reduction_factor * transmission_heat_flow(
        u_w_m2k,
        area_m2,
        exterior_temperature_c,
        room_temperature_c,
    )


def sum_ua(elements: Iterable[tuple[float, float]]) -> float:
    """Return sum(U * A) for an iterable of (U, area) tuples."""
    return sum(u_w_m2k * area_m2 for u_w_m2k, area_m2 in elements)


def corrected_transmission_coefficient(
    ua_sum_w_k: float,
    thermal_bridge_factor: float,
) -> float:
    """Return H corrected by a simple thermal bridge markup."""
    return (1.0 + thermal_bridge_factor) * ua_sum_w_k


def linear_thermal_bridges_coefficient(
    bridges: Iterable[tuple[float, float]],
) -> float:
    """Return sum(psi * length) for an iterable of (psi, length) tuples."""
    return sum(psi_w_mk * length_m for psi_w_mk, length_m in bridges)


def external_loss_coefficient(
    ua_elements: Iterable[tuple[float, float]],
    thermal_bridge_factor: float = 0.0,
    thermal_bridges_w_k: float = 0.0,
) -> float:
    """Return H_ext from U*A elements plus MVP thermal bridge correction."""
    ua_sum_w_k = sum_ua(ua_elements)
    return corrected_transmission_coefficient(
        ua_sum_w_k,
        thermal_bridge_factor,
    ) + thermal_bridges_w_k
