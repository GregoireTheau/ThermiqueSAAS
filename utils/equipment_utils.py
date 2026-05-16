"""Heating and cooling helper functions."""

from __future__ import annotations


def heating_power_required(
    setpoint_temperature_c: float,
    free_next_temperature_c: float,
    capacity_j_k: float,
    timestep_s: float,
) -> float:
    """Return heating power required to reach setpoint at next step."""
    return max(
        0.0,
        (setpoint_temperature_c - free_next_temperature_c)
        * capacity_j_k
        / timestep_s,
    )


def limited_heating_power(
    required_heating_power_w: float,
    max_heating_power_w: float,
) -> float:
    """Return applied heating power capped by equipment capacity."""
    return min(max(0.0, required_heating_power_w), max_heating_power_w)


def heating_electric_power(
    heating_power_w: float,
    performance: float,
) -> float:
    """Return electric or final power consumed for heating."""
    return heating_power_w / performance


def cooling_power_required(
    free_next_temperature_c: float,
    setpoint_temperature_c: float,
    capacity_j_k: float,
    timestep_s: float,
) -> float:
    """Return cooling power required to reach setpoint at next step."""
    return max(
        0.0,
        (free_next_temperature_c - setpoint_temperature_c)
        * capacity_j_k
        / timestep_s,
    )


def limited_cooling_power(
    required_cooling_power_w: float,
    max_cooling_power_w: float,
) -> float:
    """Return applied cooling power capped by equipment capacity."""
    return min(max(0.0, required_cooling_power_w), max_cooling_power_w)


def cooling_electric_power(
    cooling_power_w: float,
    eer: float,
) -> float:
    """Return electric power consumed for sensible cooling."""
    return cooling_power_w / eer
