"""Energy, cost and CO2 helper functions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def energy_from_power(power_w: float, timestep_h: float) -> float:
    """Return energy in kWh from power in W and duration in hours."""
    return power_w * timestep_h / 1000.0


def total_cost(
    energy_kwh_by_energy: Mapping[str, float],
    unit_price_by_energy: Mapping[str, float],
    fixed_cost: float = 0.0,
) -> float:
    """Return total cost from kWh by energy and unit prices."""
    variable_cost = sum(
        energy_kwh * unit_price_by_energy[energy]
        for energy, energy_kwh in energy_kwh_by_energy.items()
    )
    return variable_cost + fixed_cost


def co2_emissions(
    energy_kwh_by_energy: Mapping[str, float],
    emission_factor_by_energy: Mapping[str, float],
) -> float:
    """Return CO2 emissions from kWh by energy and emission factors."""
    return sum(
        energy_kwh * emission_factor_by_energy[energy]
        for energy, energy_kwh in energy_kwh_by_energy.items()
    )


def compare_scenarios(before: float, after: float) -> float:
    """Return before - after for energy, cost or CO2 comparisons."""
    return before - after


def sum_energy_from_powers(
    powers_w: Iterable[float],
    timestep_h: float,
) -> float:
    """Return kWh from a sequence of powers using a constant timestep."""
    return sum(energy_from_power(power_w, timestep_h) for power_w in powers_w)
