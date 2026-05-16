"""1R1C inertia helper functions."""

from __future__ import annotations


def air_thermal_capacity(
    volume_m3: float,
    air_density_kg_m3: float,
    air_heat_capacity_j_kgk: float,
) -> float:
    """Return C_air = rho_air * V * c_p_air in J/K."""
    return air_density_kg_m3 * volume_m3 * air_heat_capacity_j_kgk


def equivalent_capacity_from_floor_area(
    floor_area_m2: float,
    equivalent_capacity_j_m2k: float,
) -> float:
    """Return C_i = c_equiv * S_i in J/K."""
    return floor_area_m2 * equivalent_capacity_j_m2k


def next_temperature_explicit(
    current_temperature_c: float,
    net_power_w: float,
    capacity_j_k: float,
    timestep_s: float,
) -> float:
    """Return T(t + dt) using explicit Euler integration."""
    return current_temperature_c + timestep_s / capacity_j_k * net_power_w
