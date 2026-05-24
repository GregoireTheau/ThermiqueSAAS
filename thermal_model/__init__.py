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
from .physical_validation import collect_model_warnings
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
from .reporting import build_report_model, render_report_html
from .scenario_loader import (
    ScenarioValidationError,
    load_scenario,
    resolve_scenario_weather_reference,
    validate_scenario,
)
from .simulation import apply_scenario_overrides, simulate_1r1c
from .static_losses import compute_dwelling_static_losses, compute_room_static_losses
from .weather import (
    FRENCH_KEY_CITIES,
    build_thermal_weather,
    city_coordinates,
    city_slug,
    combine_weather_years,
    ensure_openmeteo_thermal_weather,
    fetch_open_meteo_year,
    read_parquet,
    resolve_weather_city,
    thermal_weather_ref,
    write_parquet,
    write_thermal_weather_json,
)

__all__ = [
    "apply_scenario_overrides",
    "build_report_model",
    "compare_scenarios",
    "collect_model_warnings",
    "compute_dwelling_static_losses",
    "compute_room_static_losses",
    "DwellingValidationError",
    "FRENCH_KEY_CITIES",
    "ReferenceDataError",
    "ScenarioValidationError",
    "build_thermal_weather",
    "city_coordinates",
    "city_slug",
    "combine_weather_years",
    "ensure_openmeteo_thermal_weather",
    "fetch_open_meteo_year",
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
    "read_parquet",
    "resolve_dwelling_references",
    "resolve_scenario_weather_reference",
    "resolve_weather_city",
    "render_report_html",
    "simulate_1r1c",
    "thermal_weather_ref",
    "validate_scenario",
    "validate_dwelling",
    "write_parquet",
    "write_thermal_weather_json",
]
