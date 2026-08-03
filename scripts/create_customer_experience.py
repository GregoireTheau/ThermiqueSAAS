#!/usr/bin/env python3
"""Create a customer-specific dwelling and run relevant before/after experiments."""

from __future__ import annotations

import argparse
import json
import math
import re
from copy import deepcopy
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from thermal_model import (  # noqa: E402
    build_report_model,
    compare_scenarios,
    ensure_openmeteo_thermal_weather,
    get_climate_zone_for_county,
    get_weather_profile_reference,
    load_reference_catalog,
    render_report_html,
    resolve_scenario_weather_reference,
    resolve_dwelling_references,
    resolve_us_location,
    resolve_weather_city,
    thermal_weather_ref,
    us_weather_ref,
    validate_dwelling,
    validate_scenario,
)
ORIENTATIONS = {
    "N": ("north", 0, "North"),
    "NE": ("northeast", 45, "North-East"),
    "E": ("east", 90, "East"),
    "SE": ("southeast", 135, "South-East"),
    "S": ("south", 180, "South"),
    "SW": ("southwest", 225, "South-West"),
    "W": ("west", 270, "West"),
    "NW": ("northwest", 315, "North-West"),
}

ROOM_TYPES = [
    {"id": "living", "label": "Living room"},
    {"id": "bedroom", "label": "Bedroom"},
    {"id": "kitchen", "label": "Kitchen"},
    {"id": "bathroom", "label": "Bathroom"},
    {"id": "office", "label": "Office"},
    {"id": "corridor", "label": "Hallway / entrance"},
    {"id": "staircase", "label": "Staircase"},
    {"id": "other", "label": "Other"},
]

DWELLING_TYPES = [
    {"id": "house", "label": "House"},
    {"id": "apartment", "label": "Apartment"},
]

DWELLING_POSITIONS = [
    {"id": "single_storey_house", "label": "Single-storey house"},
    {"id": "multi_storey_house", "label": "Multi-storey house"},
    {"id": "apartment_ground_floor", "label": "Ground-floor apartment"},
    {"id": "apartment_middle_floor", "label": "Middle-floor apartment"},
    {"id": "apartment_top_floor", "label": "Top-floor apartment"},
    {"id": "apartment_ground_top_floor", "label": "Ground-floor apartment directly under the roof"},
]

ADJACENCY_LEVELS = [
    {"id": "detached", "label": "Detached home, most facades facing outside"},
    {"id": "one_side", "label": "Adjoining or heated neighbor on one side"},
    {"id": "two_sides", "label": "Adjoining or heated neighbors on two sides"},
    {"id": "surrounded", "label": "Strongly surrounded by heated homes"},
]

WALL_INSULATION_LEVELS = [
    {"id": "poor", "label": "No, or probably not insulated", "u_factor": 1.25},
    {"id": "standard", "label": "I don't know / typical for the home's age", "u_factor": 1.0},
    {"id": "renovated", "label": "Yes, insulation added or renovated", "u_factor": 0.75},
]

ROOF_INSULATION_LEVELS = [
    {"id": "unknown", "label": "I don't know", "u_factor": 1.0},
    {"id": "not_concerned", "label": "No directly affected roof", "u_factor": 1.0},
    {"id": "poor", "label": "Roof or attic with weak insulation", "u_factor": 1.35},
    {"id": "standard", "label": "Standard roof insulation", "u_factor": 1.0},
    {"id": "renovated", "label": "Well-insulated or renovated roof", "u_factor": 0.65},
]

ROOF_ASSEMBLIES = [
    {
        "id": "vented_attic_ceiling",
        "label": "Vented attic — insulation at attic floor / ceiling",
        "thermal_boundary": "attic_floor",
        "roof_configuration_id": "attic",
    },
    {
        "id": "unvented_conditioned_attic_roof_deck",
        "label": "Unvented conditioned attic — insulation at roof deck",
        "thermal_boundary": "roof_deck",
        "roof_configuration_id": "sloped_ceiling",
    },
    {
        "id": "cathedral_ceiling_roof_deck",
        "label": "Cathedral ceiling — insulation at roof deck",
        "thermal_boundary": "roof_deck",
        "roof_configuration_id": "sloped_ceiling",
    },
    {
        "id": "compact_flat_roof",
        "label": "Compact or flat roof assembly",
        "thermal_boundary": "roof_deck",
        "roof_configuration_id": "flat_roof",
    },
]

FRAMING_TYPES = [
    {"id": "wood_frame", "label": "Wood framing / trusses"},
    {"id": "steel_frame", "label": "Steel framing"},
    {"id": "masonry_concrete", "label": "Masonry or concrete"},
    {"id": "unknown", "label": "Unknown"},
]

HVAC_DUCT_LOCATIONS = [
    {"id": "no_ducts", "label": "No HVAC ducts", "distribution_efficiency": 1.0},
    {"id": "conditioned_space", "label": "Ducts inside conditioned space", "distribution_efficiency": 1.0},
    {"id": "conditioned_attic", "label": "Ducts in conditioned attic", "distribution_efficiency": 1.0},
    {"id": "unconditioned_basement", "label": "Ducts in unconditioned basement", "distribution_efficiency": 0.92},
    {"id": "mixed_unknown", "label": "Mixed or unknown location", "distribution_efficiency": 0.90},
    {"id": "vented_attic", "label": "Ducts in vented attic", "distribution_efficiency": 0.85},
    {"id": "unconditioned_crawlspace", "label": "Ducts in unconditioned crawlspace", "distribution_efficiency": 0.85},
    {"id": "garage", "label": "Ducts in garage", "distribution_efficiency": 0.85},
]

R_VALUE_IP_TO_M2K_W = 0.1761101838

FLOOR_INSULATION_LEVELS = [
    {"id": "unknown", "label": "I don't know", "u_factor": 1.0},
    {"id": "not_concerned", "label": "No directly affected ground floor", "u_factor": 1.0},
    {"id": "poor", "label": "Weak ground-floor insulation", "u_factor": 1.25},
    {"id": "standard", "label": "Standard ground-floor insulation", "u_factor": 1.0},
    {"id": "renovated", "label": "Insulated/renovated ground floor", "u_factor": 0.75},
]

AIRTIGHTNESS_LEVELS = [
    {"id": "leaky", "label": "Yes, noticeable drafts around windows, doors, or outlets", "ach_factor": 1.2},
    {"id": "standard", "label": "I don't know / nothing specific", "ach_factor": 1.0},
    {"id": "good", "label": "No, fairly airtight home", "ach_factor": 0.85},
]

EXTERIOR_CONTACTS = [
    {"id": "exterior", "label": "Yes, one or more facades face outside"},
    {"id": "interior", "label": "No, interior room"},
    {"id": "unheated_space", "label": "No, against an unheated garage/cellar/attic"},
    {"id": "party", "label": "No, against a neighbor or party wall"},
]

THERMAL_LAYOUTS = [
    {"id": "open_living", "label": "Rooms mostly open onto the living area"},
    {"id": "corridor", "label": "Rooms mostly open onto a hallway / entrance"},
    {"id": "manual", "label": "Enter the main doors or openings one by one"},
]

WINDOW_SIZES = [
    {"id": "none", "label": "No window", "factor": 0.0},
    {"id": "small", "label": "Small: one standard window", "factor": 0.08},
    {"id": "medium", "label": "Medium: two windows or one French door", "factor": 0.14},
    {"id": "large", "label": "Large: bay window or large glazed area", "factor": 0.22},
    {"id": "custom", "label": "Enter an approximate area in m2"},
]

WINDOW_LEVELS = [
    {"id": "single_glazing_old", "label": "Single glazing"},
    {"id": "double_glazing_old", "label": "Old double glazing"},
    {"id": "double_glazing_standard", "label": "Recent standard double glazing"},
    {"id": "double_glazing_low_e", "label": "High-performance double glazing"},
]

SHUTTER_LEVELS = [
    {"id": "none", "label": "No shutter/protection"},
    {"id": "roller_shutter_standard", "label": "Roller or hinged shutters"},
    {"id": "external_blind", "label": "External blinds"},
    {"id": "interior_blind", "label": "Interior blinds"},
]

SOLAR_MASK_LEVELS = [
    {"id": "none", "label": "No shading, direct sun", "mask_factor": 1.0},
    {"id": "light", "label": "Light shading: sparse tree, railing, small overhang", "mask_factor": 0.85},
    {"id": "medium", "label": "Medium shading: balcony, dense tree, nearby opposite building", "mask_factor": 0.65},
    {"id": "strong", "label": "Strong shading: loggia, very close building, frequent shade", "mask_factor": 0.4},
]

SHUTTER_USAGE_LEVELS = [
    {"id": "day_closed", "label": "In summer, closed during the day when it is hot"},
    {"id": "partial", "label": "In summer, partly closed or depending on occupancy"},
    {"id": "rare", "label": "Rarely closed during the day"},
]

HEATING_SYSTEMS = [
    {"id": "natural_gas_furnace_standard", "label": "Natural gas forced-air furnace"},
    {"id": "propane_furnace_standard", "label": "Propane forced-air furnace"},
    {"id": "air_source_heat_pump_standard", "label": "Central air-source heat pump"},
    {"id": "electric_resistance", "label": "Electric resistance heat"},
]

VENTILATION_SYSTEMS = [
    {"id": "natural_leaky_old", "label": "Natural ventilation in an older home"},
    {"id": "natural_average", "label": "Average natural ventilation"},
    {"id": "simple_flow", "label": "Single-flow mechanical ventilation"},
    {"id": "double_flow_standard", "label": "Dual-flow mechanical ventilation"},
    {"id": "airtight_recent", "label": "Recent airtight home"},
]

CHANGES = [
    {
        "id": "roof_insulation",
        "label": "Improve roof / attic insulation",
        "experiments": ["winter_cold_primary", "summer_heatwave_secondary"],
    },
    {
        "id": "reflective_roof",
        "label": "Add a reflective roof coating against heat",
        "experiments": ["summer_openmeteo_period_primary", "summer_openmeteo_heatwave_zoom"],
    },
    {
        "id": "better_windows",
        "label": "Replace windows with high-performance double glazing",
        "experiments": ["winter_cold_primary", "summer_heatwave_if_exposed"],
    },
    {
        "id": "solar_protection",
        "label": "Add shutters or solar protection",
        "experiments": ["summer_heatwave_primary"],
    },
    {
        "id": "heat_pump",
        "label": "Replace the current heating system with a heat pump",
        "experiments": ["winter_cold_primary"],
    },
]

EXPERIMENT_SPECS = {
    "winter_cold_primary": {
        "id": "winter_cold",
        "season": "winter",
        "weather_variant": "winter_cold",
        "simulation_type": "stress",
        "weather_mode": "synthetic",
        "duration_days": 7,
        "role": "primary",
        "label": "Cold winter",
        "reason": "Main experiment to measure heat losses and heating demand.",
    },
    "summer_heatwave_primary": {
        "id": "summer_heatwave",
        "season": "summer",
        "weather_variant": "summer_heatwave",
        "simulation_type": "stress",
        "weather_mode": "synthetic",
        "duration_days": 3,
        "role": "primary",
        "label": "Summer heatwave",
        "reason": "Main experiment to measure summer comfort and solar gains.",
    },
    "summer_heatwave_secondary": {
        "id": "summer_heatwave",
        "season": "summer",
        "weather_variant": "summer_heatwave",
        "simulation_type": "stress",
        "weather_mode": "synthetic",
        "duration_days": 3,
        "role": "secondary",
        "label": "Summer heatwave",
        "reason": "Secondary experiment to check the effect on overheating.",
    },
    "summer_heatwave_if_exposed": {
        "id": "summer_heatwave",
        "season": "summer",
        "weather_variant": "summer_heatwave",
        "simulation_type": "stress",
        "weather_mode": "synthetic",
        "duration_days": 3,
        "role": "secondary",
        "condition": "exposed_windows",
        "label": "Summer heatwave",
        "reason": "Secondary experiment run when exposed glazing can influence solar gains.",
    },
    "summer_long_secondary": {
        "id": "summer_long",
        "season": "summer",
        "weather_variant": "summer_long_with_heatwave",
        "simulation_type": "seasonal",
        "weather_mode": "synthetic",
        "duration_days": 60,
        "role": "secondary",
        "label": "Long summer with heatwave",
        "reason": "Secondary experiment over two typical summer months with an integrated heatwave episode.",
    },
    "summer_openmeteo_period_primary": {
        "id": "summer_real_period",
        "season": "summer",
        "weather_variant": "openmeteo_june_september",
        "simulation_type": "seasonal",
        "weather_mode": "us_historical_summer_period",
        "duration_days": 107,
        "role": "primary",
        "label": "Early June to mid-September",
        "reason": "Main real-weather experiment to measure summer comfort over the exposed period.",
    },
    "summer_openmeteo_heatwave_zoom": {
        "id": "summer_real_heatwave_zoom",
        "season": "summer",
        "weather_variant": "openmeteo_warmest_5_days",
        "simulation_type": "stress",
        "weather_mode": "us_historical_heatwave_zoom",
        "duration_days": 5,
        "role": "secondary",
        "label": "Real heatwave zoom",
        "reason": "Zoom on the 5 hottest consecutive days between early June and mid-September.",
    },
    "annual_us_typical": {
        "id": "annual",
        "season": "annual",
        "weather_variant": "nsrdb_tmy",
        "simulation_type": "annual",
        "weather_mode": "us_typical",
        "duration_days": 365,
        "role": "annual",
        "label": "Typical weather year",
        "reason": "Primary annual estimate using a pinned US typical meteorological year.",
    },
    "annual_us_historical": {
        "id": "annual",
        "season": "annual",
        "weather_variant": "openmeteo_historical",
        "simulation_type": "annual",
        "weather_mode": "us_historical",
        "duration_days": 365,
        "role": "annual",
        "label": "Historical weather year",
        "reason": "Contextual annual comparison using one explicitly selected historical year.",
    },
}

ROOF_TYPES = [
    {"id": "attic", "label": "Attic above the home"},
    {"id": "sloped_ceiling", "label": "Sloped roof above the home"},
    {"id": "flat_roof", "label": "Flat roof above the home"},
]

ROOF_COLORS = [
    {"id": "dark", "label": "Dark", "albedo": 0.18},
    {"id": "medium", "label": "Medium", "albedo": 0.25},
    {"id": "light", "label": "Light", "albedo": 0.4},
    {"id": "unknown", "label": "I don't know", "albedo": 0.25},
]

ATTIC_VENTILATION_LEVELS = [
    {"id": "attic", "label": "Attic above the home", "solar_to_room_factor": 0.0225},
    {"id": "sloped_ceiling", "label": "Sloped roof above the home", "solar_to_room_factor": 0.05},
    {"id": "flat_roof", "label": "Flat roof above the home", "solar_to_room_factor": 0.07},
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a customer dwelling and run the relevant experiments.",
    )
    parser.add_argument(
        "--reference-dir",
        default="data/reference",
        help="Path to the reference data directory.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/customer_experiences",
        help="Directory where generated JSON files are written.",
    )
    parser.add_argument(
        "--air-density-kg-m3",
        type=float,
        default=1.2,
        help="Air density used for ventilation losses.",
    )
    parser.add_argument(
        "--air-heat-capacity-j-kgk",
        type=float,
        default=1005.0,
        help="Air heat capacity used for ventilation losses.",
    )
    parser.add_argument(
        "--annual-weather-year",
        type=int,
        default=2023,
        help="Open-Meteo year used for annual simulations.",
    )
    parser.add_argument(
        "--annual-weather-dir",
        default="data/weather/openmeteo",
        help="Directory containing/generated Open-Meteo weather assets.",
    )
    parser.add_argument(
        "--openmeteo-model",
        default="era5_seamless",
        help="Open-Meteo model used when annual weather must be fetched.",
    )
    parser.add_argument(
        "--openmeteo-cache-dir",
        default=".cache/openmeteo",
        help="HTTP cache directory for Open-Meteo annual weather fetches.",
    )
    return parser.parse_args()


def choose_one(title: str, options: list[dict[str, Any]]) -> dict[str, Any]:
    print()
    print(title)
    for index, option in enumerate(options, start=1):
        print(f"{index}. {option['label']}")

    while True:
        value = input("> ").strip()
        if value.isdigit() and 1 <= int(value) <= len(options):
            return options[int(value) - 1]
        print(f"Invalid choice. Enter a number between 1 and {len(options)}.")


def ask_text(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{label}{suffix} > ").strip()
        if value:
            return value
        if default is not None:
            return default
        print("Value required.")


def ask_float(label: str, default: float | None = None, minimum: float = 0.0) -> float:
    suffix = f" [{default:g}]" if default is not None else ""
    while True:
        raw_value = input(f"{label}{suffix} > ").strip()
        if not raw_value and default is not None:
            return default
        try:
            value = float(raw_value.replace(",", "."))
        except ValueError:
            print("Enter a number.")
            continue
        if value >= minimum:
            return value
        print(f"The value must be greater than or equal to {minimum:g}.")


def ask_int(label: str, default: int | None = None, minimum: int = 1) -> int:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw_value = input(f"{label}{suffix} > ").strip()
        if not raw_value and default is not None:
            return default
        if raw_value.isdigit() and int(raw_value) >= minimum:
            return int(raw_value)
        print(f"Enter an integer greater than or equal to {minimum}.")


def ask_yes_no(label: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    value = input(f"{label} ({suffix}) > ").strip().lower()
    if not value:
        return default
    return value in {"o", "oui", "y", "yes"}


def choose_orientation(title: str) -> str:
    options = [
        {"id": code, "label": orientation[2]}
        for code, orientation in ORIENTATIONS.items()
    ]
    return choose_one(title, options)["id"]


def choose_window_area(room_type: str, area_m2: float, orientation_code: str) -> float:
    size = choose_one("Glazing area on this facade", WINDOW_SIZES)
    if size["id"] == "custom":
        return ask_float("Approximate glazing area in m2", minimum=0.0)
    if size["id"] == "none":
        return 0.0

    default_area = default_window_area(room_type, area_m2, orientation_code)
    return round(max(default_area, area_m2 * size["factor"]), 1)


def slugify(value: str, default: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return slug or default


def get_catalog_item(catalog: dict[str, Any], collection: str, item_id: str) -> dict[str, Any]:
    return catalog[collection][item_id]


def collect_customer_input(catalog: dict[str, Any]) -> dict[str, Any]:
    print("Create a ThermalTwin customer experience")
    print("We start with the change to test, then describe the dwelling needed for this simulation.")
    print("Weather scenarios will be selected automatically.")
    print()

    project_name = ask_text("Dwelling/project name", "my_dwelling")
    postal_code = ask_text("US ZIP code", "80202")
    location = resolve_us_location(postal_code)
    city = location["city"]
    climate_zone_id = get_climate_zone_for_county(catalog, location["county_fips"])
    climate_zone = catalog["climate_zones"][climate_zone_id]
    location.update(
        {
            "climate_zone_id": climate_zone_id,
            "climate_zone_code": climate_zone["code"],
            "climate_zone_standard": "2021 IECC / ASHRAE 169-2013",
        },
    )

    dwelling_type = choose_one("Dwelling type", DWELLING_TYPES)
    position = choose_dwelling_position(dwelling_type["id"])
    adjacency = choose_one("Is the dwelling attached or surrounded by heated neighbors?", ADJACENCY_LEVELS)
    change = choose_one("Change to test", CHANGES)
    change_details = collect_change_details(change["id"])

    period = choose_one(
        "When was the dwelling built?",
        envelope_period_options(catalog),
    )
    wall_insulation = choose_one("Are exterior walls insulated?", WALL_INSULATION_LEVELS)
    roof_insulation = collect_roof_insulation(dwelling_type["id"], position["id"])
    roof_assembly = choose_one("Attic and roof assembly", ROOF_ASSEMBLIES)
    framing = choose_one("Roof framing type", FRAMING_TYPES)
    existing_roof_r_value = ask_float("Existing insulation R-value (US)", default=19.0, minimum=1.0)
    proposed_roof_r_value = ask_float("Proposed insulation R-value (US)", default=49.0, minimum=1.0)
    hvac_ducts = choose_one("HVAC duct presence and location", HVAC_DUCT_LOCATIONS)
    floor_insulation = collect_floor_insulation(dwelling_type["id"], position["id"])
    airtightness = choose_one("Do you feel drafts?", AIRTIGHTNESS_LEVELS)
    ventilation = choose_one("Main ventilation", VENTILATION_SYSTEMS)
    window_level = choose_one("Main glazing type", WINDOW_LEVELS)
    shutter_level = choose_one("Current solar protection", SHUTTER_LEVELS)
    heating = choose_one("Main heating", HEATING_SYSTEMS)
    has_cooling = ask_yes_no("Does the dwelling already have active air conditioning", False)
    setpoints = collect_setpoints()
    shutter_usage = collect_shutter_usage(shutter_level["id"])

    room_count = ask_int("Number of rooms to model", default=3, minimum=1)
    rooms = []
    for index in range(room_count):
        rooms.append(collect_room(index + 1, dwelling_type["id"], position["id"], change["id"]))
    ensure_unique_room_ids(rooms)
    thermal_layout = collect_thermal_layout(rooms)

    target_scope = choose_one(
        "Area affected by the change",
        [{"id": "all", "label": "Whole dwelling"}]
        + [{"id": room["id"], "label": room["name"]} for room in rooms],
    )

    return {
        "project_name": project_name,
        "dwelling_type": dwelling_type["id"],
        "position": position,
        "adjacency": adjacency,
        "city": city,
        "postal_code": postal_code,
        "location": location,
        "climate_zone_id": climate_zone_id,
        "construction_era_id": period["id"],
        "wall_insulation": wall_insulation,
        "roof_insulation": roof_insulation,
        "building_characteristics": {
            "construction_era": {"id": period["id"], "label": period["label"]},
            "roof_assembly": roof_assembly,
            "framing": framing,
            "existing_roof_r_value": existing_roof_r_value,
            "proposed_roof_r_value": proposed_roof_r_value,
            "hvac_ducts": {**hvac_ducts, "present": hvac_ducts["id"] != "no_ducts"},
        },
        "floor_insulation": floor_insulation,
        "airtightness": airtightness,
        "ventilation_id": ventilation["id"],
        "window_ref": window_level["id"],
        "shutter_ref": shutter_level["id"],
        "shutter_usage": shutter_usage,
        "heating_ref": heating["id"],
        "has_cooling": has_cooling,
        "setpoints": setpoints,
        "rooms": rooms,
        "thermal_layout": thermal_layout,
        "change": change,
        "change_details": change_details,
        "target_scope": target_scope["id"],
    }


def choose_dwelling_position(dwelling_type: str) -> dict[str, Any]:
    if dwelling_type == "house":
        options = [
            option
            for option in DWELLING_POSITIONS
            if option["id"] in {"single_storey_house", "multi_storey_house"}
        ]
    else:
        options = [
            option
            for option in DWELLING_POSITIONS
            if option["id"].startswith("apartment_")
        ]
    return choose_one("Dwelling position", options)


def collect_change_details(change_id: str) -> dict[str, Any]:
    if change_id in {"reflective_roof", "roof_insulation"}:
        return {
            "roof_type": choose_one("Roof type concerned", ROOF_TYPES),
            "roof_color": choose_one("Current dominant roof color", ROOF_COLORS),
            "attic_ventilation": choose_one("Roof configuration above the dwelling", ATTIC_VENTILATION_LEVELS),
        }
    if change_id in {"better_windows", "solar_protection"}:
        return {
            "window_air_leakage": choose_one(
                "Do you feel air leakage around the windows?",
                AIRTIGHTNESS_LEVELS,
            ),
        }
    return {}


def collect_setpoints() -> dict[str, float]:
    print()
    print("Usual setpoints")
    heating_c = ask_float("Target winter heating temperature in C", default=19.0, minimum=5.0)
    cooling_c = ask_float("Target summer cooling temperature in C", default=26.0, minimum=heating_c)
    return {"heating_c": heating_c, "cooling_c": cooling_c}


def collect_shutter_usage(shutter_ref: str) -> dict[str, Any]:
    if shutter_ref == "none":
        return {"id": "none", "label": "No current solar protection"}
    return choose_one("In summer, how are shutters/blinds used?", SHUTTER_USAGE_LEVELS)


def collect_roof_insulation(dwelling_type: str, dwelling_position: str) -> dict[str, Any]:
    if not dwelling_has_roof_contact(dwelling_type, dwelling_position):
        return option_by_id(ROOF_INSULATION_LEVELS, "not_concerned")
    return choose_one("Is the roof or attic insulated?", ROOF_INSULATION_LEVELS)


def collect_floor_insulation(dwelling_type: str, dwelling_position: str) -> dict[str, Any]:
    if not dwelling_has_floor_contact(dwelling_type, dwelling_position):
        return option_by_id(FLOOR_INSULATION_LEVELS, "not_concerned")
    return choose_one("Is the ground floor insulated?", FLOOR_INSULATION_LEVELS)


def option_by_id(options: list[dict[str, Any]], option_id: str) -> dict[str, Any]:
    return next(option for option in options if option["id"] == option_id)


def envelope_period_options(catalog: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"id": period["id"], "label": period["name"]}
        for period in catalog["envelope_defaults"].values()
    ]


def collect_room(
    index: int,
    dwelling_type: str,
    dwelling_position: str,
    change_id: str,
) -> dict[str, Any]:
    print()
    print(f"Room {index}")
    name = ask_text("Room name", f"Room {index}")
    room_type = choose_one("Room type", ROOM_TYPES)
    area_m2 = ask_float("Room area in m2", minimum=1.0)
    height_m = ask_float("Ceiling height in m", default=2.5, minimum=1.5)
    exterior_contact = choose_one("Does this room have an exterior wall?", EXTERIOR_CONTACTS)
    facades = []
    if exterior_contact["id"] == "exterior":
        facade_count = ask_int("Number of exterior facades", default=1, minimum=1)
        facade_count = min(facade_count, 4)
        used_orientations = set()
        for facade_index in range(facade_count):
            while True:
                orientation = choose_orientation(f"Facade {facade_index + 1} orientation")
                if orientation not in used_orientations:
                    used_orientations.add(orientation)
                    break
                print("This orientation has already been entered for the room.")
            window_area = choose_window_area(room_type["id"], area_m2, orientation)
            wall_length_m = ask_float(
                "Approximate length of this facade in m",
                default=round(math.sqrt(area_m2), 1),
                minimum=0.5,
            )
            mask = collect_solar_mask(window_area, change_id)
            window_ref = None
            if change_id in {"better_windows", "solar_protection"} and window_area > 0:
                window_ref = choose_one("Glazing type on this facade", WINDOW_LEVELS)["id"]
            facades.append(
                {
                    "orientation": orientation,
                    "window_area_m2": window_area,
                    "wall_length_m": wall_length_m,
                    "mask_factor": mask["mask_factor"],
                    "window_ref": window_ref,
                },
            )

    has_roof = default_has_roof(dwelling_type, dwelling_position)
    has_ground_floor = default_has_ground_floor(dwelling_type, dwelling_position)
    if should_ask_room_roof(dwelling_type, dwelling_position):
        label = (
            "Is this room directly under the roof or attic"
            if dwelling_type == "house"
            else "Is this room directly under the roof"
        )
        has_roof = ask_yes_no(label, has_roof)
    if should_ask_room_ground_floor(dwelling_type, dwelling_position):
        label = (
            "Is this room in contact with the ground"
            if dwelling_type == "house"
            else "Is this room above an unheated space or the ground"
        )
        has_ground_floor = ask_yes_no(label, has_ground_floor)

    return {
        "id": slugify(name, f"room_{index}"),
        "name": name,
        "type": room_type["id"],
        "floor_area_m2": area_m2,
        "height_m": height_m,
        "exterior_contact": exterior_contact["id"],
        "facades": facades,
        "has_roof": has_roof,
        "has_ground_floor": has_ground_floor,
    }


def should_ask_room_roof(dwelling_type: str, dwelling_position: str) -> bool:
    if dwelling_type == "house":
        return dwelling_position == "multi_storey_house"
    return False


def should_ask_room_ground_floor(dwelling_type: str, dwelling_position: str) -> bool:
    if dwelling_type == "house":
        return dwelling_position == "multi_storey_house"
    return False


def collect_solar_mask(window_area_m2: float, change_id: str) -> dict[str, Any]:
    if window_area_m2 <= 0:
        return SOLAR_MASK_LEVELS[0]
    if change_id not in {"reflective_roof", "better_windows", "solar_protection"}:
        return SOLAR_MASK_LEVELS[0]
    return choose_one("Solar shading in front of this window", SOLAR_MASK_LEVELS)


def default_has_roof(dwelling_type: str, dwelling_position: str) -> bool:
    return dwelling_has_roof_contact(dwelling_type, dwelling_position)


def default_has_ground_floor(dwelling_type: str, dwelling_position: str) -> bool:
    return dwelling_has_floor_contact(dwelling_type, dwelling_position)


def dwelling_has_roof_contact(dwelling_type: str, dwelling_position: str) -> bool:
    if dwelling_type == "house":
        return True
    return dwelling_position in {"apartment_top_floor", "apartment_ground_top_floor"}


def dwelling_has_floor_contact(dwelling_type: str, dwelling_position: str) -> bool:
    if dwelling_type == "house":
        return dwelling_position == "single_storey_house"
    return dwelling_position in {"apartment_ground_floor", "apartment_ground_top_floor"}


def collect_thermal_layout(rooms: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rooms) < 2:
        return {"type": "single_room", "connections": []}

    layout = choose_one("How do the rooms connect to each other?", THERMAL_LAYOUTS)
    if layout["id"] != "manual":
        return {"type": layout["id"], "connections": []}

    print()
    print("Main doors or openings")
    print("Answer yes if the two rooms are connected by a door or an opening often left open.")
    connections = []
    for index, first_room in enumerate(rooms):
        for second_room in rooms[index + 1:]:
            if ask_yes_no(
                f"Door or opening often left open between {first_room['name']} and {second_room['name']}",
                False,
            ):
                connections.append(
                    {
                        "room_a": first_room["id"],
                        "room_b": second_room["id"],
                    },
                )
    return {"type": "manual", "connections": connections}


def ensure_unique_room_ids(rooms: list[dict[str, Any]]) -> None:
    seen: dict[str, int] = {}
    for index, room in enumerate(rooms, start=1):
        base_id = room["id"] or f"room_{index}"
        count = seen.get(base_id, 0) + 1
        seen[base_id] = count
        if count > 1:
            room["id"] = f"{base_id}_{count}"


def default_window_area(room_type: str, area_m2: float, orientation: str) -> float:
    if room_type == "bathroom":
        return 0.6
    if room_type in {"corridor", "staircase"}:
        return 0.0
    if room_type == "living":
        factor = 0.18 if orientation in {"S", "SE", "SW", "W"} else 0.1
        return round(max(1.5, area_m2 * factor), 1)
    if room_type == "bedroom":
        return round(max(1.2, area_m2 * 0.12), 1)
    return round(max(0.8, area_m2 * 0.1), 1)


def build_dwelling(customer: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    period = get_catalog_item(catalog, "envelope_defaults", customer["construction_era_id"])
    building_characteristics = customer.get(
        "building_characteristics",
        default_building_characteristics(customer["construction_era_id"], period),
    )
    ventilation = get_catalog_item(catalog, "ventilation", customer["ventilation_id"])
    ach_factor = customer["airtightness"]["ach_factor"]
    ventilation_split = ventilation_components(
        customer["ventilation_id"],
        ventilation,
        ach_factor,
    )
    dwelling_id = slugify(customer["project_name"], "customer_dwelling")

    rooms = [
        build_room(room, customer, catalog, period, ventilation_split)
        for room in customer["rooms"]
    ]
    total_area_m2 = sum(room["floor_area_m2"] for room in rooms)
    room_ids = [room["id"] for room in rooms]

    return {
        "schema_version": "0.1",
        "dwelling_id": dwelling_id,
        "metadata": {
            "name": customer["project_name"],
            "description": build_dwelling_description(customer),
            "created_by": "create_customer_experience.py",
        },
        "location": {
            **customer.get(
                "location",
                {
                    "country": customer.get("country", "US"),
                    "postal_code": customer["postal_code"],
                    "city": customer["city"],
                },
            ),
            "climate_zone_id": customer["climate_zone_id"],
            "ground_albedo": 0.2,
        },
        "building_characteristics": building_characteristics,
        "defaults": {
            "initial_temperature_c": 20.0,
            "construction_era_ref": customer["construction_era_id"],
            "equivalent_capacity_j_m2k": period["equivalent_capacity_j_m2k"],
            "thermal_bridge_factor": period["thermal_bridge_factor"],
            "internal_gain_w_m2": 4.0,
            "ach_h": ventilation_split["legacy_ach_h"],
            "infiltration_ach": ventilation_split["infiltration_ach"],
            "mechanical_ach": ventilation_split["mechanical_ach"],
            "recovery_efficiency": ventilation_split["recovery_efficiency"],
        },
        "rooms": rooms,
        "thermal_links": build_thermal_links(rooms, customer["thermal_layout"]),
        "systems": {
            "heating": [
                build_heating_system(
                    customer["heating_ref"],
                    room_ids,
                    total_area_m2,
                    catalog,
                    duct_efficiency_for_heating(
                        customer["heating_ref"],
                        building_characteristics["hvac_ducts"]["distribution_efficiency"],
                    ),
                ),
            ],
            "cooling": build_cooling_systems(
                customer["has_cooling"],
                rooms,
                total_area_m2,
                building_characteristics["hvac_ducts"]["distribution_efficiency"],
            ),
            "ventilation": {
                "ventilation_ref": customer["ventilation_id"],
                "type": ventilation_type(customer["ventilation_id"]),
                "default_ach_h": ventilation_split["legacy_ach_h"],
                "infiltration_ach": ventilation_split["infiltration_ach"],
                "mechanical_ach": ventilation_split["mechanical_ach"],
                "recovery_efficiency": ventilation_split["recovery_efficiency"],
            },
        },
    }


def build_dwelling_description(customer: dict[str, Any]) -> str:
    position = customer.get("position", {}).get("label")
    adjacency = customer.get("adjacency", {}).get("label")
    details = [
        value
        for value in (position, adjacency)
        if value
    ]
    if not details:
        return "Dwelling created from the ThermalTwin customer CLI."
    return "Dwelling created from the ThermalTwin customer CLI. " + " / ".join(details)


def default_building_characteristics(
    construction_era_id: str,
    period: dict[str, Any],
) -> dict[str, Any]:
    existing_r_value = 1.0 / (
        float(period["u_values"]["roof"]) * R_VALUE_IP_TO_M2K_W
    )
    return {
        "construction_era": {"id": construction_era_id, "label": period["name"]},
        "roof_assembly": deepcopy(ROOF_ASSEMBLIES[0]),
        "framing": deepcopy(FRAMING_TYPES[-1]),
        "existing_roof_r_value": round(existing_r_value, 2),
        "proposed_roof_r_value": 49.0,
        "hvac_ducts": {**HVAC_DUCT_LOCATIONS[0], "present": False},
    }


def build_room(
    room_input: dict[str, Any],
    customer: dict[str, Any],
    catalog: dict[str, Any],
    period: dict[str, Any],
    ventilation_split: dict[str, float],
) -> dict[str, Any]:
    room_id = room_input["id"]
    area_m2 = room_input["floor_area_m2"]
    height_m = room_input["height_m"]
    volume_m3 = area_m2 * height_m
    windows = build_windows(room_input, customer, catalog)

    return {
        "id": room_id,
        "name": room_input["name"],
        "type": room_input["type"],
        "floor_area_m2": area_m2,
        "height_m": height_m,
        "has_cooling": room_input.get("has_cooling"),
        "volume_m3": round(volume_m3, 2),
        "initial_temperature_c": 20.0,
        "equivalent_capacity_j_m2k": period["equivalent_capacity_j_m2k"],
        "internal_gain_w_m2": internal_gain_for_room(room_input["type"]),
        "ventilation": {
            "mode": "ach",
            "ach_h": ventilation_split["legacy_ach_h"],
            "infiltration_ach": ventilation_split["infiltration_ach"],
            "mechanical_ach": ventilation_split["mechanical_ach"],
            "recovery_efficiency": ventilation_split["recovery_efficiency"],
            "ventilation_ref": customer["ventilation_id"],
        },
        "surfaces": build_surfaces(room_input, windows, customer, period),
        "windows": windows,
    }


def build_surfaces(
    room_input: dict[str, Any],
    windows: list[dict[str, Any]],
    customer: dict[str, Any],
    period: dict[str, Any],
) -> list[dict[str, Any]]:
    room_id = room_input["id"]
    area_m2 = room_input["floor_area_m2"]
    height_m = room_input["height_m"]
    side_width_m = math.sqrt(area_m2)
    window_area_by_orientation = {
        orientation: sum(
            window["area_m2"]
            for window in windows
            if orientation_key(window["azimuth_deg"]) == orientation
        )
        for orientation in ("north", "east", "south", "west")
    }

    surfaces = []
    for facade in room_input["facades"]:
        orientation_key_name, azimuth_deg, _label = ORIENTATIONS[facade["orientation"]]
        solar_orientation = orientation_key(azimuth_deg)
        wall_length_m = facade.get("wall_length_m", side_width_m)
        gross_wall_area = wall_length_m * height_m
        net_wall_area = max(1.0, gross_wall_area - window_area_by_orientation[solar_orientation])
        surfaces.append(
            {
                "id": f"{room_id}_{orientation_key_name}_wall",
                "type": "external_wall",
                "boundary": "exterior",
                "area_m2": round(net_wall_area, 2),
                "u_value_w_m2k": rounded_u(
                    period,
                    "external_wall",
                    customer["wall_insulation"]["u_factor"],
                ),
                "azimuth_deg": azimuth_deg,
                "tilt_deg": 90,
                "albedo": 0.35,
                "solar_to_room_factor": 0.08,
                "mask_factor": facade.get("mask_factor", 1.0),
            },
        )

    if room_input["exterior_contact"] in {"unheated_space", "party"}:
        surfaces.append(
            {
                "id": f"{room_id}_{room_input['exterior_contact']}_wall",
                "type": "party_wall",
                "boundary": room_input["exterior_contact"],
                "area_m2": round(side_width_m * height_m, 2),
                "u_value_w_m2k": rounded_u(
                    period,
                    "external_wall",
                    customer["wall_insulation"]["u_factor"],
                ),
            },
        )

    if room_input["has_roof"]:
        roof_color = customer.get("change_details", {}).get("roof_color", {})
        attic_ventilation = customer.get("change_details", {}).get("attic_ventilation", {})
        surfaces.append(
            {
                "id": f"{room_id}_roof",
                "type": "roof",
                "boundary": "exterior",
                "area_m2": round(area_m2, 2),
                "u_value_w_m2k": roof_u_value(customer, period),
                "azimuth_deg": 180,
                "tilt_deg": 25,
                "albedo": roof_color.get("albedo", 0.25),
                "solar_to_room_factor": attic_ventilation.get("solar_to_room_factor", 0.0225),
                "mask_factor": 1.0,
            },
        )

    if room_input["has_ground_floor"]:
        surfaces.append(
            {
                "id": f"{room_id}_floor",
                "type": "floor",
                "boundary": "ground",
                "area_m2": round(area_m2, 2),
                "u_value_w_m2k": rounded_u(
                    period,
                    "floor",
                    customer["floor_insulation"]["u_factor"],
                ),
            },
        )

    return surfaces


def build_windows(
    room_input: dict[str, Any],
    customer: dict[str, Any],
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    shutter_ref = get_catalog_item(catalog, "shutters", customer["shutter_ref"])
    windows = []
    for index, facade in enumerate(room_input["facades"], start=1):
        if facade["window_area_m2"] <= 0:
            continue
        orientation_name, azimuth_deg, _label = ORIENTATIONS[facade["orientation"]]
        window_ref_id = facade.get("window_ref") or customer["window_ref"]
        window_ref = get_catalog_item(catalog, "windows", window_ref_id)
        window_data = {
            "id": f"{room_input['id']}_{orientation_name}_window_{index}",
            "window_ref": window_ref_id,
            "area_m2": round(facade["window_area_m2"], 2),
            "u_value_w_m2k": window_ref["u_value_w_m2k"],
            "g_value": window_ref["g_value"],
            "azimuth_deg": azimuth_deg,
            "tilt_deg": 90,
            "mask_factor": facade.get("mask_factor", 1.0),
            "shutter_ref": customer["shutter_ref"],
        }
        if customer["shutter_ref"] != "none":
            window_data["shutter"] = {
                "type": shutter_ref["type"],
                "solar_factor_closed": shutter_ref["solar_factor_closed"],
                "solar_factor_open": shutter_ref["solar_factor_open"],
                "u_factor_closed": shutter_ref["u_factor_closed"],
            }
        windows.append(window_data)
    return windows


def internal_gain_for_room(room_type: str) -> float:
    if room_type in {"living", "kitchen"}:
        return 5.0
    if room_type in {"bedroom", "office"}:
        return 3.0
    if room_type == "staircase":
        return 1.0
    return 2.0


def rounded_u(period: dict[str, Any], surface_type: str, u_factor: float) -> float:
    return round(period["u_values"][surface_type] * u_factor, 3)


def roof_u_from_r_value(r_value_ip: float) -> float:
    """Convert an effective US R-value to W/m².K for the 1R1C envelope."""
    return round(1.0 / (float(r_value_ip) * R_VALUE_IP_TO_M2K_W), 3)


def roof_u_value(customer: dict[str, Any], period: dict[str, Any]) -> float:
    characteristics = customer.get("building_characteristics", {})
    r_value = characteristics.get("existing_roof_r_value")
    if r_value is not None:
        return roof_u_from_r_value(r_value)
    return rounded_u(period, "roof", customer["roof_insulation"]["u_factor"])


def ventilation_components(
    ventilation_id: str,
    ventilation: dict[str, Any],
    ach_factor: float,
) -> dict[str, float]:
    default_ach = ventilation["default_ach_h"]
    base_infiltration_ach = 0.15 * ach_factor
    if "natural" in ventilation_id:
        infiltration_ach = default_ach * ach_factor
        mechanical_ach = 0.0
    else:
        infiltration_ach = base_infiltration_ach
        mechanical_ach = max(0.0, default_ach - 0.15)
    return {
        "legacy_ach_h": round(default_ach * ach_factor, 2),
        "infiltration_ach": round(infiltration_ach, 2),
        "mechanical_ach": round(mechanical_ach, 2),
        "recovery_efficiency": ventilation.get("recovery_efficiency", 0.0),
    }


def orientation_key(azimuth_deg: float) -> str:
    if azimuth_deg < 45 or azimuth_deg >= 315:
        return "north"
    if azimuth_deg < 135:
        return "east"
    if azimuth_deg < 225:
        return "south"
    return "west"


def build_thermal_links(
    rooms: list[dict[str, Any]],
    thermal_layout: dict[str, Any],
) -> list[dict[str, Any]]:
    if len(rooms) < 2:
        return []

    rooms_by_id = {room["id"]: room for room in rooms}
    if thermal_layout["type"] == "manual":
        connections = thermal_layout["connections"]
    elif thermal_layout["type"] == "corridor":
        hub = next(
            (room for room in rooms if room["type"] == "corridor"),
            next((room for room in rooms if room["type"] == "living"), rooms[0]),
        )
        connections = [
            {"room_a": hub["id"], "room_b": room["id"]}
            for room in rooms
            if room["id"] != hub["id"]
        ]
    else:
        hub = next((room for room in rooms if room["type"] == "living"), rooms[0])
        connections = [
            {"room_a": hub["id"], "room_b": room["id"]}
            for room in rooms
            if room["id"] != hub["id"]
        ]

    links = []
    seen_pairs = set()
    for connection in connections:
        room_a_id = connection["room_a"]
        room_b_id = connection["room_b"]
        if room_a_id == room_b_id:
            continue
        pair_key = tuple(sorted((room_a_id, room_b_id)))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        room_b = rooms_by_id[room_b_id]
        default_area_m2 = min(10.0, max(4.0, math.sqrt(room_b["floor_area_m2"]) * room_b["height_m"]))
        area_m2 = connection.get("area_m2", default_area_m2)
        links.append(
            {
                "id": f"{room_a_id}_{room_b_id}_link",
                "room_a": room_a_id,
                "room_b": room_b_id,
                "type": "internal_wall",
                "area_m2": round(area_m2, 2),
                "u_value_w_m2k": connection.get("u_value_w_m2k", 1.8),
                "opening_factor": connection.get("opening_factor", 0.8),
            },
        )
    return links


def build_heating_system(
    heating_ref: str,
    room_ids: list[str],
    total_area_m2: float,
    catalog: dict[str, Any],
    distribution_efficiency: float = 1.0,
) -> dict[str, Any]:
    reference = get_catalog_item(catalog, "heating_systems", heating_ref)
    return {
        "id": "main_heating",
        "system_ref": heating_ref,
        "type": reference["type"],
        "served_rooms": room_ids,
        "max_power_w": round(max(1500.0, total_area_m2 * 95.0), 0),
        "performance_ref": deepcopy(reference["performance_ref"]),
        "distribution_efficiency": distribution_efficiency,
    }


def duct_efficiency_for_heating(
    heating_ref: str,
    duct_distribution_efficiency: float,
) -> float:
    return duct_distribution_efficiency


def build_cooling_systems(
    has_cooling: bool,
    rooms: list[dict[str, Any]],
    total_area_m2: float,
    distribution_efficiency: float = 1.0,
) -> list[dict[str, Any]]:
    if not has_cooling:
        return []
    room_level_answers = [room for room in rooms if room.get("has_cooling") is not None]
    if room_level_answers:
        served_rooms = [room["id"] for room in rooms if room.get("has_cooling") is True]
    else:
        served_rooms = [
            room["id"]
            for room in rooms
            if room["type"] in {"living", "bedroom", "office"}
        ] or [room["id"] for room in rooms]
    if not served_rooms:
        return []
    return [
        {
            "id": "main_cooling",
            "system_ref": "air_conditioner_standard",
            "type": "air_conditioner",
            "served_rooms": served_rooms,
            "max_power_w": round(max(1200.0, total_area_m2 * 70.0), 0),
            "performance_ref": {"mode": "constant", "eer": 3.0},
            "distribution_efficiency": distribution_efficiency,
        },
    ]


def ventilation_type(ventilation_id: str) -> str:
    if "double_flow" in ventilation_id:
        return "double_flow"
    if "natural" in ventilation_id:
        return "natural"
    if "simple_flow" in ventilation_id:
        return "simple_flow"
    return "other"


def selected_room_ids(customer: dict[str, Any], dwelling: dict[str, Any]) -> list[str]:
    if customer["target_scope"] == "all":
        return [room["id"] for room in dwelling["rooms"]]
    return [customer["target_scope"]]


def ensure_applicable_target(customer: dict[str, Any], dwelling: dict[str, Any]) -> bool:
    room_ids = selected_room_ids(customer, dwelling)
    if change_applies(dwelling, customer["change"]["id"], room_ids):
        return True

    print()
    print("The selected change does not apply to the selected area.")
    print(change_inapplicable_reason(dwelling, customer["change"]["id"], room_ids))
    options = applicable_target_options(customer, dwelling)
    if not options:
        return False

    if not ask_yes_no("Choose another compatible area", True):
        return False

    target = choose_one("Compatible area", options)
    customer["target_scope"] = target["id"]
    return True


def applicable_target_options(
    customer: dict[str, Any],
    dwelling: dict[str, Any],
) -> list[dict[str, str]]:
    change_id = customer["change"]["id"]
    options = []
    all_room_ids = [room["id"] for room in dwelling["rooms"]]
    if change_applies(dwelling, change_id, all_room_ids):
        options.append({"id": "all", "label": "Whole dwelling"})
    for room in dwelling["rooms"]:
        if change_applies(dwelling, change_id, [room["id"]]):
            options.append({"id": room["id"], "label": room["name"]})
    return options


def change_inapplicable_reason(
    dwelling: dict[str, Any],
    change_id: str,
    room_ids: list[str],
) -> str:
    if change_id in {"roof_insulation", "reflective_roof"}:
        return "No roof was described in the target area."
    if change_id in {"better_windows", "solar_protection"}:
        return "No window was described in the target area."
    if change_id == "heat_pump":
        return "No heating system serves the target area."
    return "The target area does not contain any compatible element."


def build_experiments(
    customer: dict[str, Any],
    dwelling: dict[str, Any],
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    change = customer["change"]
    room_ids = selected_room_ids(customer, dwelling)
    if not change_applies(dwelling, change["id"], room_ids):
        return []

    experiments = []
    for experiment_spec in selected_experiment_specs(
        change,
        dwelling,
        room_ids,
        customer.get("include_annual_experiment", True),
        customer.get("annual_weather_type", "typical"),
    ):
        base_id = f"{dwelling['dwelling_id']}_{change['id']}_{experiment_spec['id']}"
        before = build_scenario(
            base_id,
            dwelling,
            experiment_spec,
            change,
            False,
            room_ids,
            catalog,
            customer.get("setpoints"),
            customer.get("shutter_usage"),
            customer.get("annual_weather_year", 2023),
            customer.get("annual_tmy_name", "tmy-2024"),
            customer.get("annual_weather_dir", "data/weather/us"),
            customer.get("energy_prices"),
        )
        after = build_scenario(
            base_id,
            dwelling,
            experiment_spec,
            change,
            True,
            room_ids,
            catalog,
            customer.get("setpoints"),
            customer.get("shutter_usage"),
            customer.get("annual_weather_year", 2023),
            customer.get("annual_tmy_name", "tmy-2024"),
            customer.get("annual_weather_dir", "data/weather/us"),
            customer.get("energy_prices"),
        )
        experiments.append(
            {
                "id": base_id,
                "season": experiment_spec["season"],
                "role": experiment_spec["role"],
                "before": before,
                "after": after,
            },
        )
    return experiments


def selected_experiment_specs(
    change: dict[str, Any],
    dwelling: dict[str, Any],
    room_ids: list[str],
    include_annual_experiment: bool = True,
    annual_weather_type: str = "typical",
) -> list[dict[str, Any]]:
    specs = []
    for experiment_id in change["experiments"]:
        spec = EXPERIMENT_SPECS[experiment_id]
        if spec.get("condition") == "exposed_windows" and not has_exposed_windows(
            dwelling,
            room_ids,
        ):
            continue
        specs.append(spec)
    if include_annual_experiment and change["id"] != "reflective_roof":
        annual_spec_id = (
            "annual_us_historical"
            if annual_weather_type == "historical"
            else "annual_us_typical"
        )
        specs.append(EXPERIMENT_SPECS[annual_spec_id])
    return specs


def has_exposed_windows(dwelling: dict[str, Any], room_ids: list[str]) -> bool:
    rooms = [room for room in dwelling["rooms"] if room["id"] in room_ids]
    return any(
        orientation_key(window["azimuth_deg"]) in {"east", "south", "west"}
        for room in rooms
        for window in room["windows"]
    )


def change_applies(
    dwelling: dict[str, Any],
    change_id: str,
    room_ids: list[str],
) -> bool:
    rooms = [room for room in dwelling["rooms"] if room["id"] in room_ids]
    if change_id in {"roof_insulation", "reflective_roof"}:
        return any(
            surface["type"] == "roof"
            for room in rooms
            for surface in room["surfaces"]
        )
    if change_id in {"better_windows", "solar_protection"}:
        return any(room["windows"] for room in rooms)
    if change_id == "heat_pump":
        return any(
            any(room_id in system["served_rooms"] for room_id in room_ids)
            for system in dwelling["systems"]["heating"]
        )
    return False


def build_scenario(
    base_id: str,
    dwelling: dict[str, Any],
    experiment_spec: dict[str, Any],
    change: dict[str, Any],
    apply_change: bool,
    room_ids: list[str],
    catalog: dict[str, Any],
    setpoints: dict[str, float] | None = None,
    shutter_usage: dict[str, Any] | None = None,
    annual_weather_year: int = 2023,
    annual_tmy_name: str = "tmy-2024",
    annual_weather_dir: str | Path = "data/weather/us",
    energy_prices: dict[str, float] | None = None,
) -> dict[str, Any]:
    season = experiment_spec["season"]
    scenario_setpoints = setpoints or default_setpoints_for_experiment(experiment_spec)
    weather_city = {}
    scenario = {
        "schema_version": "0.1",
        "scenario_id": f"{base_id}_{'after' if apply_change else 'before'}",
        "dwelling_id": dwelling["dwelling_id"],
        "description": f"{experiment_spec['label']} {'after' if apply_change else 'before'}",
        "experiment": {
            "adaptation_id": change["id"],
            "adaptation_label": change["label"],
            "role": experiment_spec["role"],
            "label": experiment_spec["label"],
            "season": season,
            "weather_variant": experiment_spec["weather_variant"],
            "simulation_type": experiment_spec["simulation_type"],
            "weather_mode": experiment_spec["weather_mode"],
            "reason": experiment_spec["reason"],
        },
        "timestep_h": 1.0,
        "initial_temperatures_c": {
            room["id"]: initial_temperature_for_experiment(experiment_spec)
            for room in dwelling["rooms"]
        },
        "climate_zone_id": dwelling["location"]["climate_zone_id"],
        "setpoints": scenario_setpoints,
        "weather": build_scenario_weather(
            experiment_spec,
            dwelling,
            catalog,
            weather_city,
            annual_weather_year,
            annual_tmy_name,
            annual_weather_dir,
        ),
        "energy_prices": energy_prices or {
            "electricity_usd_kwh": 0.18,
            "natural_gas_usd_therm": 1.50,
            "propane_usd_gallon": 2.50,
        },
        "co2_factors": {"electricity_kg_kwh": 0.0},
    }
    if experiment_spec["weather_mode"].startswith("us_"):
        weather_type = "typical" if experiment_spec["weather_mode"] == "us_typical" else "historical"
        scenario["experiment"].update(
            {
                "requested_city": dwelling["location"].get("city", ""),
                "weather_city": dwelling["location"].get("city", ""),
                "weather_match_mode": dwelling["location"].get("geocoding_precision", ""),
                "weather_reference": (
                    annual_tmy_name if weather_type == "typical" else str(annual_weather_year)
                ),
            },
        )
        if weather_type == "historical":
            scenario["experiment"]["weather_year"] = annual_weather_year
    if season in {"summer", "annual"}:
        scenario["controls"] = {
            "shutters": build_summer_shutter_controls(
                experiment_spec["duration_days"],
                shutter_usage,
            ),
        }
        if {
            "cooling_day_c",
            "cooling_night_c",
        }.issubset(scenario_setpoints):
            scenario["controls"]["cooling_setpoint_schedule"] = {
                "day_c": scenario_setpoints["cooling_day_c"],
                "night_c": scenario_setpoints["cooling_night_c"],
                "day_start_hour": 7,
                "night_start_hour": 22,
            }
        if season == "summer":
            scenario["controls"]["natural_ventilation"] = build_summer_natural_ventilation_controls()
    if apply_change:
        retrofit = build_retrofit(dwelling, change["id"], room_ids, catalog)
        if retrofit:
            scenario["retrofit"] = retrofit
    return scenario


def default_setpoints_for_experiment(experiment_spec: dict[str, Any]) -> dict[str, float]:
    if experiment_spec["season"] == "summer":
        return {"heating_c": 18.0, "cooling_c": 26.0}
    if experiment_spec["season"] == "annual":
        return {"heating_c": 19.0, "cooling_c": 26.0}
    return {"heating_c": 19.0, "cooling_c": 28.0}


def initial_temperature_for_experiment(experiment_spec: dict[str, Any]) -> float:
    if experiment_spec["season"] == "summer":
        return 26.0
    if experiment_spec["season"] == "annual":
        return 20.0
    return 19.0


def build_scenario_weather(
    experiment_spec: dict[str, Any],
    dwelling: dict[str, Any],
    catalog: dict[str, Any],
    weather_city: dict[str, str],
    annual_weather_year: int,
    annual_tmy_name: str,
    annual_weather_dir: str | Path,
) -> dict[str, Any]:
    if experiment_spec["weather_mode"].startswith("us_"):
        weather_type = (
            "typical"
            if experiment_spec["weather_mode"] == "us_typical"
            else "historical"
        )
        location = dwelling["location"]
        return {
            "source": (
                f"nsrdb_goes_tmy_v4_{annual_tmy_name}"
                if weather_type == "typical"
                else f"openmeteo_era5_seamless_{annual_weather_year}"
            ),
            "weather_ref": us_weather_ref(
                location,
                weather_type,
                year=annual_weather_year,
                tmy_name=annual_tmy_name,
                output_dir=annual_weather_dir,
            ),
            "_request": {
                "location": location,
                "weather_type": weather_type,
                "year": annual_weather_year if weather_type == "historical" else None,
                "tmy_name": annual_tmy_name,
                "weather_dir": str(annual_weather_dir),
            },
        }
    if experiment_spec["weather_mode"].startswith("openmeteo_"):
        city = weather_city["weather_city"]
        return {
            "source": f"openmeteo_{city}_{annual_weather_year}",
            "weather_ref": thermal_weather_ref(
                city,
                annual_weather_year,
                output_dir=annual_weather_dir,
            ),
        }
    return build_weather(experiment_spec, catalog)


def build_weather(
    experiment_spec: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    weather_variant = experiment_spec["weather_variant"]
    duration_days = experiment_spec["duration_days"]
    default_profile = weather_profile_for_variant(weather_variant)

    hourly = []
    for hour in range(duration_days * 24):
        day = hour // 24
        hour_in_day = hour % 24
        if weather_variant == "summer_long_with_heatwave" and 27 <= day <= 29:
            profile_id = weather_profile_for_variant("summer_heatwave")
        else:
            profile_id = default_profile
        weather_profile = get_weather_profile_reference(catalog, profile_id)
        temperature_profile = weather_profile["temperature_profile"]
        base_temp = temperature_profile["base_temp_c"]
        amplitude = temperature_profile["amplitude_c"]
        phase_hour = temperature_profile.get("phase_hour", 8)
        outdoor_temperature_c = base_temp + amplitude * math.sin(
            2.0 * math.pi * (hour_in_day - phase_hour) / 24.0,
        )
        weather_point = {
            "hour": hour,
            "month": month_for_weather_profile(weather_profile),
            "outdoor_temperature_c": round(outdoor_temperature_c, 2),
            "solar_irradiance_w_m2": solar_profile(weather_profile, hour_in_day),
        }
        hourly.append(weather_point)
    return {"source": f"generated_{default_profile}", "hourly": hourly}


def weather_profile_for_variant(weather_variant: str) -> str:
    if weather_variant == "summer_heatwave":
        return "generic_heatwave_reference"
    elif weather_variant == "summer_long_with_heatwave":
        return "generic_summer_typical"
    return "generic_winter_design"


def month_for_weather_profile(weather_profile: dict[str, Any]) -> int:
    if weather_profile["profile_type"] == "winter_design":
        return 1
    return 7


def solar_profile(weather_profile: dict[str, Any], hour_in_day: int) -> dict[str, float]:
    profile = weather_profile["solar_profile"]
    if profile["mode"] == "winter_reference":
        peak = max(0.0, math.sin(math.pi * (hour_in_day - 8) / 8.0))
        return {
            "north": round(profile["north_peak_w_m2"] * peak, 2),
            "east": round(
                (
                    profile["east_morning_peak_w_m2"]
                    if hour_in_day < 13
                    else profile["east_afternoon_peak_w_m2"]
                )
                * peak,
                2,
            ),
            "south": round(profile["south_peak_w_m2"] * peak, 2),
            "west": round(
                (
                    profile["west_afternoon_peak_w_m2"]
                    if hour_in_day > 12
                    else profile["west_morning_peak_w_m2"]
                )
                * peak,
                2,
            ),
            "roof": round(profile["roof_peak_w_m2"] * peak, 2),
        }

    peak = max(0.0, math.sin(math.pi * (hour_in_day - 6) / 13.0))
    return {
        "north": round(profile["north_peak_w_m2"] * peak, 2),
        "east": round(
            (
                profile["east_morning_peak_w_m2"]
                if hour_in_day < 13
                else profile["east_afternoon_peak_w_m2"]
            )
            * peak,
            2,
        ),
        "south": round(profile["south_peak_w_m2"] * peak, 2),
        "west": round(
            (
                profile["west_afternoon_peak_w_m2"]
                if hour_in_day > 12
                else profile["west_morning_peak_w_m2"]
            )
            * peak,
            2,
        ),
        "roof": round(profile["roof_peak_w_m2"] * peak, 2),
    }


def build_summer_shutter_controls(
    duration_days: int,
    shutter_usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    usage_id = (shutter_usage or {}).get("id", "partial")
    if usage_id == "none":
        return {"default_opening_ratio": 1.0, "hourly": []}
    if usage_id == "day_closed":
        daytime_opening_ratio = 0.1
    elif usage_id == "rare":
        daytime_opening_ratio = 0.75
    else:
        daytime_opening_ratio = 0.25

    return {
        "default_opening_ratio": 1.0,
        "hourly": [
            {"hour": hour, "opening_ratio": daytime_opening_ratio}
            for hour in range(duration_days * 24)
            if 8 <= hour % 24 <= 19
        ],
    }


def build_summer_natural_ventilation_controls() -> dict[str, Any]:
    return {
        "default_ach": 0.0,
        "smart_night_cooling": True,
        "smart_ach": 4.0,
    }


def build_retrofit(
    dwelling: dict[str, Any],
    change_id: str,
    room_ids: list[str],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    rooms = [room for room in dwelling["rooms"] if room["id"] in room_ids]
    if change_id == "roof_insulation":
        target_r_value = dwelling.get("building_characteristics", {}).get(
            "proposed_roof_r_value",
            49.0,
        )
        return clean_retrofit({
            "surface_overrides": [
                {
                    "surface_id": surface["id"],
                    "u_value_w_m2k": roof_u_from_r_value(target_r_value),
                }
                for room in rooms
                for surface in room["surfaces"]
                if surface["type"] == "roof"
            ],
        })
    if change_id == "reflective_roof":
        return clean_retrofit({
            "surface_overrides": [
                {
                    "surface_id": surface["id"],
                    "albedo": 0.75,
                }
                for room in rooms
                for surface in room["surfaces"]
                if surface["type"] == "roof"
            ],
        })
    if change_id == "better_windows":
        window_ref = get_catalog_item(catalog, "windows", "double_glazing_low_e")
        return clean_retrofit({
            "window_overrides": [
                {
                    "window_id": window["id"],
                    "window_ref": "double_glazing_low_e",
                    "u_value_w_m2k": window_ref["u_value_w_m2k"],
                    "g_value": window_ref["g_value"],
                }
                for room in rooms
                for window in room["windows"]
            ],
        })
    if change_id == "solar_protection":
        shutter_ref = get_catalog_item(catalog, "shutters", "roller_shutter_standard")
        return clean_retrofit({
            "shutter_overrides": [
                {
                    "window_id": window["id"],
                    "type": shutter_ref["type"],
                    "solar_factor_closed": 0.08,
                    "solar_factor_open": shutter_ref["solar_factor_open"],
                    "u_factor_closed": shutter_ref["u_factor_closed"],
                }
                for room in rooms
                for window in room["windows"]
            ],
        })
    if change_id == "heat_pump":
        reference = get_catalog_item(catalog, "heating_systems", "air_source_heat_pump_standard")
        return clean_retrofit({
            "system_overrides": [
                {
                    "category": "heating",
                    "system_id": system["id"],
                    "system_ref": "air_source_heat_pump_standard",
                    "type": reference["type"],
                    "energy_vector": reference["energy_vector"],
                    "performance_ref": reference["performance_ref"],
                }
                for system in dwelling["systems"]["heating"]
                if any(room_id in system["served_rooms"] for room_id in room_ids)
            ],
        })
    return {}


def clean_retrofit(retrofit: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        key: value
        for key, value in retrofit.items()
        if value
    }


def write_json(output_path: str | Path, payload: dict[str, Any]) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def write_text(output_path: str | Path, content: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_customer_experience(args: argparse.Namespace) -> None:
    catalog = load_reference_catalog(args.reference_dir)
    customer = collect_customer_input(catalog)
    customer["annual_weather_year"] = args.annual_weather_year
    customer["annual_weather_dir"] = args.annual_weather_dir
    dwelling = build_dwelling(customer, catalog)
    validate_dwelling(dwelling)
    resolved_dwelling = resolve_dwelling_references(dwelling, catalog)
    target_is_applicable = ensure_applicable_target(customer, resolved_dwelling)
    experiments = build_experiments(customer, resolved_dwelling, catalog)

    output_dir = Path(args.output_dir) / dwelling["dwelling_id"]
    write_json(output_dir / "dwelling.json", dwelling)
    print()
    print(f"Dwelling exported: {output_dir / 'dwelling.json'}")

    if not target_is_applicable or not experiments:
        print("No experience launched: the selected change does not apply to the entered elements.")
        return

    for experiment in experiments:
        prepare_experiment_weather(experiment, args)
        before = experiment["before"]
        after = experiment["after"]
        validate_scenario(before)
        validate_scenario(after)
        before_path = output_dir / f"{experiment['id']}_before.json"
        after_path = output_dir / f"{experiment['id']}_after.json"
        comparison_path = output_dir / f"{experiment['id']}_comparison.json"
        report_path = output_dir / f"{experiment['id']}_comparison_report.json"
        html_path = output_dir / f"{experiment['id']}_report.html"
        summary_path = output_dir / f"{experiment['id']}_customer_summary.json"
        write_json(before_path, before)
        write_json(after_path, after)

        comparison = compare_scenarios(
            resolved_dwelling,
            before,
            after,
            args.air_density_kg_m3,
            args.air_heat_capacity_j_kgk,
        )
        write_json(comparison_path, comparison)
        report = build_report_model(comparison)
        write_json(report_path, report)
        write_text(html_path, render_report_html(report))
        customer_summary = build_customer_summary(experiment["season"], comparison)
        write_json(summary_path, customer_summary)
        print(f"Before scenario: {before_path}")
        print(f"After scenario: {after_path}")
        print(f"Comparison: {comparison_path}")
        print(f"JSON report: {report_path}")
        print(f"HTML report: {html_path}")
        print(f"Customer summary: {summary_path}")
        print_customer_summary(customer_summary)


def prepare_experiment_weather(experiment: dict[str, Any], args: argparse.Namespace) -> None:
    """Ensure external annual weather exists and resolve it before simulation."""
    if experiment["role"] != "annual":
        return

    weather_city = experiment["before"]["experiment"]["weather_city"]
    weather_year = experiment["before"]["experiment"]["weather_year"]
    weather_path = ensure_openmeteo_thermal_weather(
        weather_city,
        weather_year,
        output_dir=args.annual_weather_dir,
        model=args.openmeteo_model,
        cache_dir=args.openmeteo_cache_dir,
    )
    print(f"Annual Open-Meteo weather: {weather_city} {weather_year} -> {weather_path}")

    for scenario_key in ("before", "after"):
        resolve_scenario_weather_reference(experiment[scenario_key], Path.cwd())


def build_customer_summary(season: str, comparison: dict[str, Any]) -> dict[str, Any]:
    key_room_id, room = most_improved_room(comparison)
    energy = comparison["summary"]["energy_savings"]
    driver = comparison["summary"]["main_gain_driver"]
    experiment = comparison["experiment"]
    return {
        "season": season,
        "dwelling_id": comparison["dwelling_id"],
        "before_scenario_id": comparison["before_scenario_id"],
        "after_scenario_id": comparison["after_scenario_id"],
        "experiment": {
            "adaptation_id": experiment.get("adaptation_id", "unknown"),
            "adaptation_label": experiment.get("adaptation_label", ""),
            "role": experiment.get("role", "primary"),
            "label": experiment.get("label", ""),
            "weather_variant": experiment.get("weather_variant", ""),
            "simulation_type": experiment.get("simulation_type", ""),
            "weather_mode": experiment.get("weather_mode", ""),
            "requested_city": experiment.get("requested_city", ""),
            "weather_city": experiment.get("weather_city", ""),
            "weather_match_mode": experiment.get("weather_match_mode", ""),
            "weather_year": experiment.get("weather_year"),
            "reason": experiment.get("reason", ""),
            "duration_hours": round(experiment["duration_hours"], 2),
            "duration_days": round(experiment["duration_days"], 2),
            "scope_notice": (
                "These results cover only a simulation of "
                f"{experiment['duration_days']:.2f} days."
            ),
            "annual_projection_notice": (
                "This experience is an annual simulation."
                if experiment.get("simulation_type") == "annual"
                else "No annual projection is calculated in this report."
            ),
            "weather_source": experiment["weather_source"],
            "outdoor_temperature_min_c": round(
                experiment["weather_summary"]["outdoor_temperature_min_c"],
                1,
            ),
            "outdoor_temperature_max_c": round(
                experiment["weather_summary"]["outdoor_temperature_max_c"],
                1,
            ),
            "heating_setpoint_c": experiment["setpoints"]["heating_c"],
            "cooling_setpoint_c": experiment["setpoints"]["cooling_c"],
            "before_description": experiment["before_description"],
            "after_description": experiment["after_description"],
        },
        "headline": {
            "electricity_saved_kwh": round(energy["electricity_saved_kwh"], 2),
            "cost_saved_usd": round(energy["cost_saved_usd"], 2),
            "main_gain_driver": driver["label"],
        },
        "comfort": {
            "room_id": key_room_id,
            "room_name": room["room_name"],
            "max_temperature_before_c": round(room["before_max_temperature_c"], 1),
            "max_temperature_after_c": round(room["after_max_temperature_c"], 1),
            "max_temperature_reduction_c": round(room["delta_max_temperature_c"], 1),
            "hot_discomfort_before_c_h": round(room["before_hot_degree_hours"], 0),
            "hot_discomfort_after_c_h": round(room["after_hot_degree_hours"], 0),
            "hot_discomfort_reduced_c_h": round(room["delta_hot_degree_hours"], 0),
            "cold_discomfort_before_c_h": round(room["before_cold_degree_hours"], 0),
            "cold_discomfort_after_c_h": round(room["after_cold_degree_hours"], 0),
            "cold_discomfort_reduced_c_h": round(room["delta_cold_degree_hours"], 0),
            "explanation": discomfort_explanation(room),
        },
    }


def most_improved_room(comparison: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    rooms = comparison["deltas"]["rooms"]
    return max(
        rooms.items(),
        key=lambda item: (
            item[1]["delta_hot_degree_hours"]
            + item[1]["delta_cold_degree_hours"]
            + max(0.0, item[1]["delta_max_temperature_c"]) * 24.0
        ),
    )


def discomfort_explanation(room: dict[str, Any]) -> str:
    if room["delta_hot_degree_hours"] > 0:
        return (
            "Cumulative warm discomfort corresponds to hours spent above "
            "the comfort setpoint, weighted by the temperature gap."
        )
    if room["delta_cold_degree_hours"] > 0:
        return (
            "Cumulative cold discomfort corresponds to hours spent below the "
            "heating setpoint, weighted by the temperature gap."
        )
    if room["delta_max_temperature_c"] > 0:
        return "The maximum temperature decreases, without a significant gain on cumulative discomfort."
    return "Simulated comfort remains broadly stable."


def print_customer_summary(summary: dict[str, Any]) -> None:
    comfort = summary["comfort"]
    experiment = summary["experiment"]
    headline = summary["headline"]
    print(f"{summary['season'].title()} reading:")
    role_labels = {
        "primary": "primary",
        "secondary": "secondary",
        "annual": "annual",
    }
    role_label = role_labels.get(experiment["role"], "simulation")
    print(
        "- Experience: "
        f"{role_label}, {experiment['label'] or summary['season']}, "
        f"{experiment['duration_days']:.1f} days "
        f"({experiment['duration_hours']:.0f} h), "
        f"weather {experiment['weather_source']}, "
        f"{experiment['outdoor_temperature_min_c']:.1f} C -> "
        f"{experiment['outdoor_temperature_max_c']:.1f} C ext."
    )
    if experiment.get("simulation_type") == "annual":
        print("- Scope: simulated results over a complete weather year.")
    else:
        print("- Scope: simulated results over this period, without annual projection.")
    if headline["electricity_saved_kwh"] > 0:
        print(
            "- Energy: "
            f"{headline['electricity_saved_kwh']:.2f} kWh, "
            f"${headline['cost_saved_usd']:.2f} saved"
        )
    elif headline["electricity_saved_kwh"] < 0:
        print(
            "- Energy: "
            f"{abs(headline['electricity_saved_kwh']):.2f} additional kWh"
        )
    else:
        print("- Energy: consumption unchanged in this simulation")
    print(
        "- Most impacted room: "
        f"{comfort['room_name']} "
        f"({comfort['max_temperature_before_c']:.1f} C -> "
        f"{comfort['max_temperature_after_c']:.1f} C max temperature)"
    )
    if comfort["hot_discomfort_reduced_c_h"] > 0:
        print(
            "- Summer comfort: warm discomfort reduced by "
            f"{comfort['hot_discomfort_reduced_c_h']:.0f} C.h "
            f"({comfort['hot_discomfort_before_c_h']:.0f} -> "
            f"{comfort['hot_discomfort_after_c_h']:.0f} C.h)"
        )
    elif comfort["cold_discomfort_reduced_c_h"] > 0:
        print(
            "- Winter comfort: cold discomfort reduced by "
            f"{comfort['cold_discomfort_reduced_c_h']:.0f} C.h "
            f"({comfort['cold_discomfort_before_c_h']:.0f} -> "
            f"{comfort['cold_discomfort_after_c_h']:.0f} C.h)"
        )
    else:
        print("- Comfort: stable in this simulation")
    print(f"- Main explanation: {headline['main_gain_driver']}")


def main() -> None:
    run_customer_experience(parse_args())


if __name__ == "__main__":
    main()
