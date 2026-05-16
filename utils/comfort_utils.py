"""Simplified comfort helper functions."""

from __future__ import annotations

from collections.abc import Iterable


def operative_temperature(
    air_temperature_c: float,
    mean_surface_temperature_c: float,
) -> float:
    """Return simplified operative temperature."""
    return (air_temperature_c + mean_surface_temperature_c) / 2.0


def warm_degree_hours(
    temperatures_c: Iterable[float],
    warm_threshold_c: float,
    timestep_h: float,
) -> float:
    """Return warm discomfort degree-hours."""
    return sum(
        max(0.0, temperature_c - warm_threshold_c) * timestep_h
        for temperature_c in temperatures_c
    )


def cold_degree_hours(
    temperatures_c: Iterable[float],
    cold_threshold_c: float,
    timestep_h: float,
) -> float:
    """Return cold discomfort degree-hours."""
    return sum(
        max(0.0, cold_threshold_c - temperature_c) * timestep_h
        for temperature_c in temperatures_c
    )
