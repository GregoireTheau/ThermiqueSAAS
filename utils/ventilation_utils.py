"""Ventilation, infiltration and ACH helper functions."""

from __future__ import annotations


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return min(max(value, min_value), max_value)


def airflow_from_ach(
    ach_h: float,
    volume_m3: float,
    seconds_per_hour: float = 3600.0,
) -> float:
    """Return volumetric airflow q = ACH * V / 3600 in m3/s."""
    return ach_h * volume_m3 / seconds_per_hour


def ventilation_heat_transfer_coefficient(
    airflow_m3_s: float,
    air_density_kg_m3: float,
    air_heat_capacity_j_kgk: float,
) -> float:
    """Return H_air = rho_air * c_p_air * q_air in W/K."""
    return air_density_kg_m3 * air_heat_capacity_j_kgk * airflow_m3_s


def ventilation_heat_flow(
    h_air_w_k: float,
    exterior_temperature_c: float,
    room_temperature_c: float,
) -> float:
    """Return ventilation heat flow into the room."""
    return h_air_w_k * (exterior_temperature_c - room_temperature_c)


def supply_temperature_with_recovery(
    exterior_temperature_c: float,
    room_temperature_c: float,
    recovery_efficiency: float,
) -> float:
    """Return double-flow ventilation supply temperature."""
    return exterior_temperature_c + recovery_efficiency * (
        room_temperature_c - exterior_temperature_c
    )


def effective_air_coefficient_with_recovery(
    h_air_w_k: float,
    recovery_efficiency: float,
) -> float:
    """Return effective H_air after heat recovery."""
    return h_air_w_k * (1.0 - recovery_efficiency)


def wind_factor(
    wind_speed_m_s: float,
    reference_wind_speed_m_s: float,
    wind_sensitivity: float,
) -> float:
    """Return F_vent = 1 + k_vent * max(0, v_vent - v_ref)."""
    return 1.0 + wind_sensitivity * max(
        0.0,
        wind_speed_m_s - reference_wind_speed_m_s,
    )


def ach_with_wind(
    base_ach_h: float,
    wind_speed_m_s: float,
    reference_wind_speed_m_s: float,
    wind_sensitivity: float,
    min_ach_h: float,
    max_ach_h: float,
) -> float:
    """Return wind-corrected ACH, clamped between min and max values."""
    corrected_ach_h = base_ach_h * wind_factor(
        wind_speed_m_s,
        reference_wind_speed_m_s,
        wind_sensitivity,
    )
    return _clamp(corrected_ach_h, min_ach_h, max_ach_h)
