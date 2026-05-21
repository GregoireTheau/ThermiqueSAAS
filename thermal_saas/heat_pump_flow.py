"""Compatibility wrappers for the heat-pump seller SaaS flow."""

from __future__ import annotations

from typing import Any

from .business_flow import (
    BusinessFlowError,
    build_customer,
    get_profile_questionnaire,
    run_profile_experience,
)


DEFAULT_AIR_DENSITY_KG_M3 = 1.2
DEFAULT_AIR_HEAT_CAPACITY_J_KGK = 1005.0


HeatPumpFlowError = BusinessFlowError


def get_heat_pump_questionnaire() -> dict[str, Any]:
    """Return the heat-pump seller questionnaire."""
    return get_profile_questionnaire("heat_pump_seller")


def run_heat_pump_experience(
    answers: dict[str, Any],
    *,
    include_report_html: bool = True,
    air_density_kg_m3: float = DEFAULT_AIR_DENSITY_KG_M3,
    air_heat_capacity_j_kgk: float = DEFAULT_AIR_HEAT_CAPACITY_J_KGK,
) -> dict[str, Any]:
    """Build, simulate, and report the heat-pump seller experience."""
    return run_profile_experience(
        "heat_pump_seller",
        answers,
        include_report_html=include_report_html,
        air_density_kg_m3=air_density_kg_m3,
        air_heat_capacity_j_kgk=air_heat_capacity_j_kgk,
    )


def build_heat_pump_customer(
    answers: dict[str, Any],
    profile: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    """Map API answers to the existing customer-experience input format."""
    return build_customer(answers, profile, catalog)
