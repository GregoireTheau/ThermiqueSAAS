"""Thermal model data loading helpers."""

from .comparison import compare_scenarios
from .dwelling_loader import (
    DwellingValidationError,
    get_rooms_by_id,
    iter_external_surfaces,
    iter_thermal_links,
    iter_windows,
    load_dwelling,
    validate_dwelling,
)
from .dwelling_resolver import resolve_dwelling_references
from .reference_loader import (
    ReferenceDataError,
    get_climate_zone_for_department,
    get_climate_zone_reference,
    get_cooling_system_reference,
    get_envelope_default_reference,
    get_heating_system_reference,
    get_material_reference,
    get_reference,
    get_shutter_reference,
    get_ventilation_reference,
    get_window_reference,
    load_reference_catalog,
)
from .scenario_loader import (
    ScenarioValidationError,
    load_scenario,
    validate_scenario,
)
from .simulation import apply_scenario_overrides, simulate_1r1c
from .static_losses import compute_dwelling_static_losses, compute_room_static_losses

__all__ = [
    "apply_scenario_overrides",
    "compare_scenarios",
    "compute_dwelling_static_losses",
    "compute_room_static_losses",
    "DwellingValidationError",
    "ReferenceDataError",
    "ScenarioValidationError",
    "get_climate_zone_for_department",
    "get_climate_zone_reference",
    "get_cooling_system_reference",
    "get_envelope_default_reference",
    "get_heating_system_reference",
    "get_material_reference",
    "get_reference",
    "get_rooms_by_id",
    "get_shutter_reference",
    "get_ventilation_reference",
    "get_window_reference",
    "iter_external_surfaces",
    "iter_thermal_links",
    "iter_windows",
    "load_dwelling",
    "load_reference_catalog",
    "load_scenario",
    "resolve_dwelling_references",
    "simulate_1r1c",
    "validate_scenario",
    "validate_dwelling",
]
