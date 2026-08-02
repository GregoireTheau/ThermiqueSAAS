"""Generic business-profile flow for the ThermalTwin SaaS."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import os
from pathlib import Path
from typing import Any

from scripts import create_customer_experience as customer_experience
from thermal_model import (
    DEFAULT_NSRDB_TMY_NAME,
    build_report_model,
    build_thermal_weather,
    city_slug,
    collect_model_warnings,
    combine_weather_years,
    compare_scenarios,
    ensure_openmeteo_thermal_weather,
    ensure_us_thermal_weather,
    get_climate_zone_for_county,
    load_reference_catalog,
    read_parquet,
    render_report_html,
    resolve_dwelling_references,
    resolve_scenario_weather_reference,
    resolve_us_location,
    thermal_weather_ref,
    us_weather_ref,
    validate_dwelling,
    validate_scenario,
    write_thermal_weather_json,
)

from .business_profiles import build_questionnaire, load_business_profile


DEFAULT_AIR_DENSITY_KG_M3 = 1.2
DEFAULT_AIR_HEAT_CAPACITY_J_KGK = 1005.0
JUNE_1_START_HOUR = 151 * 24
SEPTEMBER_16_START_HOUR = 258 * 24
HEATWAVE_ZOOM_DAYS = 5


class BusinessFlowError(ValueError):
    """Raised when business-flow answers are incomplete or invalid."""


def _answer_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "oui", "on"}
    return bool(value)


def get_profile_questionnaire(profile_id: str) -> dict[str, Any]:
    """Return a profile questionnaire with catalog-backed options resolved."""
    catalog = load_reference_catalog()
    profile = load_business_profile(profile_id)
    return build_questionnaire(profile, catalog)


def run_profile_experience(
    profile_id: str,
    answers: dict[str, Any],
    *,
    include_report_html: bool = True,
    report_branding: dict[str, Any] | None = None,
    air_density_kg_m3: float = DEFAULT_AIR_DENSITY_KG_M3,
    air_heat_capacity_j_kgk: float = DEFAULT_AIR_HEAT_CAPACITY_J_KGK,
) -> dict[str, Any]:
    """Build, simulate, and report an experience for a business profile."""
    catalog = load_reference_catalog()
    profile = load_business_profile(profile_id)
    customer = build_customer(answers, profile, catalog)
    dwelling = customer_experience.build_dwelling(customer, catalog)
    validate_dwelling(dwelling)
    resolved_dwelling = resolve_dwelling_references(dwelling, catalog)
    experiments = customer_experience.build_experiments(customer, resolved_dwelling, catalog)
    if not experiments:
        raise BusinessFlowError(
            f"The {customer['change']['id']} adaptation does not apply to this dwelling.",
        )

    simulation_runs = []
    for experiment in experiments:
        for scenario_key in ("before", "after"):
            experiment[scenario_key].setdefault("experiment", {})[
                "business_profile_id"
            ] = profile["id"]
        prepare_experiment_weather(experiment)
        before = experiment["before"]
        after = experiment["after"]
        validate_scenario(before)
        validate_scenario(after)
        comparison = compare_scenarios(
            resolved_dwelling,
            before,
            after,
            air_density_kg_m3,
            air_heat_capacity_j_kgk,
        )
        report = build_report_model(comparison)
        run = {
            "id": experiment["id"],
            "season": experiment["season"],
            "role": experiment["role"],
            "before_scenario": before,
            "after_scenario": after,
            "comparison": comparison,
            "model_warnings": {
                "before": collect_model_warnings(
                    resolved_dwelling,
                    before,
                    comparison["before"],
                    air_density_kg_m3=air_density_kg_m3,
                    air_heat_capacity_j_kgk=air_heat_capacity_j_kgk,
                ),
                "after": collect_model_warnings(
                    resolved_dwelling,
                    after,
                    comparison["after"],
                    air_density_kg_m3=air_density_kg_m3,
                    air_heat_capacity_j_kgk=air_heat_capacity_j_kgk,
                ),
            },
            "report": report,
        }
        if include_report_html:
            run["report_html"] = render_report_html(report, branding=report_branding)
        simulation_runs.append(run)

    return {
        "business_profile_id": profile["id"],
        "adaptation_id": customer["change"]["id"],
        "dwelling": dwelling,
        "resolved_dwelling": resolved_dwelling,
        "simulation_runs": simulation_runs,
    }


def build_customer(
    answers: dict[str, Any],
    profile: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    """Map API answers to the existing customer-experience input format."""
    _require_fields(
        answers,
        [
            "project_name",
            "postal_code",
            "dwelling_type",
            "position_id",
            "period_id",
            "rooms",
        ],
    )
    adaptation_id = answers.get("adaptation_id", profile["default_adaptation"])
    if adaptation_id not in profile["allowed_adaptations"]:
        raise BusinessFlowError(
            f"The change '{adaptation_id}' is not compatible with business profile '{profile['id']}'.",
        )

    change = _change_by_id(adaptation_id)
    dwelling_type = answers["dwelling_type"]
    position = _option_by_id(customer_experience.DWELLING_POSITIONS, answers["position_id"])
    if not answers["rooms"]:
        raise BusinessFlowError("At least one room is required.")
    rooms = [
        _normalize_room(room, index, dwelling_type, position["id"])
        for index, room in enumerate(answers["rooms"], start=1)
    ]
    customer_experience.ensure_unique_room_ids(rooms)

    postal_code = str(answers["postal_code"])
    try:
        location = resolve_us_location(
            postal_code,
            answers.get("address"),
            cache_dir=os.environ.get("THERMAL_LOCATION_CACHE_DIR", ".cache/locations"),
        )
    except ValueError as exc:
        raise BusinessFlowError(str(exc)) from exc
    try:
        climate_zone_id = get_climate_zone_for_county(
            catalog,
            location["county_fips"],
        )
    except ValueError as exc:
        raise BusinessFlowError(str(exc)) from exc
    climate_zone = catalog["climate_zones"][climate_zone_id]
    location.update(
        {
            "climate_zone_id": climate_zone_id,
            "climate_zone_code": climate_zone["code"],
            "climate_zone_standard": "2021 IECC / ASHRAE 169-2013",
        },
    )
    annual_weather_type = str(answers.get("annual_weather_type", "typical"))
    if annual_weather_type not in {"typical", "historical"}:
        raise BusinessFlowError("annual_weather_type must be 'typical' or 'historical'.")
    annual_weather_year = int(answers.get("annual_weather_year", 2023))
    needs_historical_year = (
        annual_weather_type == "historical"
        or profile["id"] == "reflective_roof_seller"
    )
    if (
        needs_historical_year
        and (annual_weather_year < 1940 or annual_weather_year >= date.today().year)
    ):
        raise BusinessFlowError(
            "Historical weather year must be a complete year from 1940 onward.",
        )

    heating_setpoint_c = float(answers.get("heating_setpoint_c", 19.0))
    cooling_setpoint_day_c = float(
        answers.get("cooling_setpoint_day_c", answers.get("cooling_setpoint_c", 26.0)),
    )
    cooling_setpoint_night_c = float(
        answers.get("cooling_setpoint_night_c", cooling_setpoint_day_c),
    )
    cooling_setpoint_c = cooling_setpoint_day_c
    _validate_setpoint(heating_setpoint_c, "heating_setpoint_c")
    _validate_setpoint(cooling_setpoint_day_c, "cooling_setpoint_day_c")
    _validate_setpoint(cooling_setpoint_night_c, "cooling_setpoint_night_c")
    if min(cooling_setpoint_day_c, cooling_setpoint_night_c) < heating_setpoint_c:
        raise BusinessFlowError(
            "The heating setpoint cannot be higher than the cooling setpoint.",
        )

    return {
        "project_name": answers["project_name"],
        "dwelling_type": dwelling_type,
        "position": position,
        "adjacency": _option_by_id(
            customer_experience.ADJACENCY_LEVELS,
            answers.get("adjacency_id", "detached"),
        ),
        "city": location["city"],
        "postal_code": postal_code,
        "address": str(answers.get("address") or "").strip(),
        "location": location,
        "climate_zone_id": climate_zone_id,
        "period_id": answers["period_id"],
        "wall_insulation": _option_by_id(
            customer_experience.WALL_INSULATION_LEVELS,
            answers.get("wall_insulation_id", "standard"),
        ),
        "roof_insulation": _roof_insulation(answers, dwelling_type, position["id"]),
        "floor_insulation": _floor_insulation(answers, dwelling_type, position["id"]),
        "airtightness": _option_by_id(
            customer_experience.AIRTIGHTNESS_LEVELS,
            answers.get("airtightness_id", "standard"),
        ),
        "ventilation_id": answers.get("ventilation_id", "simple_flow"),
        "window_ref": answers.get("window_ref", "double_glazing_standard"),
        "shutter_ref": answers.get("shutter_ref", "roller_shutter_standard"),
        "shutter_usage": _shutter_usage(answers, adaptation_id),
        "heating_ref": _initial_heating_ref(profile["id"], answers),
        "has_cooling": _answer_bool(answers.get("has_cooling"), False),
        "setpoints": {
            "heating_c": heating_setpoint_c,
            "cooling_c": cooling_setpoint_c,
            "cooling_day_c": cooling_setpoint_day_c,
            "cooling_night_c": cooling_setpoint_night_c,
        },
        "rooms": rooms,
        "thermal_layout": _thermal_layout(rooms, answers.get("thermal_layout")),
        "change": change,
        "change_details": _change_details(adaptation_id, answers),
        "energy_prices": _energy_prices(answers),
        "target_scope": answers.get("target_scope", "all"),
        "include_annual_experiment": _answer_bool(
            answers.get("include_annual_experiment"),
            bool(profile.get("include_annual_experiment", True)),
        ),
        "annual_weather_type": annual_weather_type,
        "annual_weather_year": annual_weather_year,
        "annual_tmy_name": str(answers.get("annual_tmy_name", DEFAULT_NSRDB_TMY_NAME)),
        "annual_weather_dir": answers.get(
            "annual_weather_dir",
            os.environ.get("THERMAL_WEATHER_DIR", "data/weather/us"),
        ),
    }


def prepare_experiment_weather(experiment: dict[str, Any]) -> None:
    """Ensure Open-Meteo weather exists locally and resolve/filter weather_ref scenarios."""
    weather_mode = experiment["before"].get("experiment", {}).get("weather_mode", "")
    if weather_mode.startswith("us_"):
        request = experiment["before"]["weather"].pop("_request")
        for scenario_key in ("before", "after"):
            experiment[scenario_key]["weather"].pop("_request", None)
        try:
            ensure_us_thermal_weather(
                request["location"],
                request["weather_type"],
                year=request.get("year"),
                tmy_name=request["tmy_name"],
                output_dir=request["weather_dir"],
            )
        except Exception as exc:
            reference = request.get("year") or request["tmy_name"]
            raise BusinessFlowError(
                f"{request['weather_type'].title()} weather {reference} is unavailable "
                f"for ZIP code {request['location']['postal_code']}.",
            ) from exc
        for scenario_key in ("before", "after"):
            resolve_scenario_weather_reference(experiment[scenario_key], Path.cwd())
        if weather_mode == "us_historical_summer_period":
            for scenario_key in ("before", "after"):
                _filter_openmeteo_summer_period(experiment[scenario_key])
        elif weather_mode == "us_historical_heatwave_zoom":
            for scenario_key in ("before", "after"):
                _filter_openmeteo_heatwave_zoom(experiment[scenario_key])
        return
    if not weather_mode.startswith("openmeteo_"):
        return

    weather_city = experiment["before"]["experiment"]["weather_city"]
    weather_year = experiment["before"]["experiment"]["weather_year"]
    weather_dir = _weather_dir_from_scenario(experiment["before"])
    try:
        ensure_annual_weather(weather_city, weather_year, weather_dir)
    except Exception as exc:
        raise BusinessFlowError(
            f"Annual weather {weather_year} is unavailable for {weather_city}.",
        ) from exc

    for scenario_key in ("before", "after"):
        resolve_scenario_weather_reference(experiment[scenario_key], Path.cwd())

    if weather_mode == "openmeteo_summer_period":
        for scenario_key in ("before", "after"):
            _filter_openmeteo_summer_period(experiment[scenario_key])
    elif weather_mode == "openmeteo_heatwave_zoom":
        for scenario_key in ("before", "after"):
            _filter_openmeteo_heatwave_zoom(experiment[scenario_key])


def _filter_openmeteo_summer_period(scenario: dict[str, Any]) -> None:
    hourly = scenario["weather"]["hourly"]
    selected = hourly[JUNE_1_START_HOUR:SEPTEMBER_16_START_HOUR]
    scenario["weather"]["hourly"] = _renumber_weather_hours(selected)
    scenario["weather"]["source"] = f"{scenario['weather']['source']}_jun1_sep15"


def _filter_openmeteo_heatwave_zoom(scenario: dict[str, Any]) -> None:
    seasonal = scenario["weather"]["hourly"][JUNE_1_START_HOUR:SEPTEMBER_16_START_HOUR]
    window_start = _warmest_consecutive_days_start(seasonal, HEATWAVE_ZOOM_DAYS)
    selected = seasonal[window_start:window_start + HEATWAVE_ZOOM_DAYS * 24]
    scenario["weather"]["hourly"] = _renumber_weather_hours(selected)
    scenario["weather"]["source"] = f"{scenario['weather']['source']}_warmest_5_days"


def _warmest_consecutive_days_start(
    hourly: list[dict[str, Any]],
    days: int,
) -> int:
    hours_per_window = days * 24
    if len(hourly) <= hours_per_window:
        return 0
    daily_means = [
        sum(point["outdoor_temperature_c"] for point in hourly[index:index + 24]) / 24.0
        for index in range(0, len(hourly) - 23, 24)
    ]
    best_day = max(
        range(0, len(daily_means) - days + 1),
        key=lambda day: sum(daily_means[day:day + days]) / days,
    )
    return best_day * 24


def _renumber_weather_hours(hourly: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {**point, "hour": index}
        for index, point in enumerate(hourly)
    ]


def ensure_annual_weather(
    city: str,
    year: int,
    weather_dir: str | Path = "data/weather/openmeteo",
) -> Path:
    """Return a 2023 annual weather asset, creating it from local raw data if needed."""
    weather_path = Path(thermal_weather_ref(city, year, output_dir=weather_dir))
    if weather_path.exists():
        return weather_path

    raw_path = Path(weather_dir) / "raw" / f"{city_slug(city)}_{year}.parquet"
    if raw_path.exists():
        dataframe = read_parquet(raw_path)
        annual_dataframe = combine_weather_years([dataframe], "latest")
        weather = build_thermal_weather(
            annual_dataframe,
            source=f"openmeteo_local_{city_slug(city)}_{year}",
        )
        return write_thermal_weather_json(weather, weather_path)

    return ensure_openmeteo_thermal_weather(city, year, output_dir=weather_dir)


def _weather_dir_from_scenario(scenario: dict[str, Any]) -> str:
    weather_ref = scenario.get("weather", {}).get("weather_ref", "")
    if not weather_ref:
        return "data/weather/openmeteo"
    path = Path(weather_ref)
    if path.name.endswith(".weather.json") and path.parent.name == "thermal":
        return str(path.parent.parent)
    return "data/weather/openmeteo"


def _change_details(adaptation_id: str, answers: dict[str, Any]) -> dict[str, Any]:
    if adaptation_id in {"reflective_roof", "roof_insulation"}:
        roof_configuration_id = _roof_configuration_id(answers)
        return {
            "roof_type": _option_by_id(
                customer_experience.ROOF_TYPES,
                roof_configuration_id,
            ),
            "roof_color": _option_by_id(
                customer_experience.ROOF_COLORS,
                answers.get("roof_color_id", "medium"),
            ),
            "attic_ventilation": _option_by_id(
                customer_experience.ATTIC_VENTILATION_LEVELS,
                roof_configuration_id,
            ),
        }
    if adaptation_id in {"better_windows", "solar_protection"}:
        return {
            "window_air_leakage": _option_by_id(
                customer_experience.AIRTIGHTNESS_LEVELS,
                answers.get("window_air_leakage_id", "standard"),
            ),
        }
    if adaptation_id == "heat_pump":
        _require_fields(answers, ["current_energy_id", "heat_emitters_id"])
        return {
            "current_energy": _option_by_id(
                customer_experience.HEAT_PUMP_CURRENT_ENERGIES,
                answers["current_energy_id"],
            ),
            "heat_emitters": _option_by_id(
                customer_experience.HEAT_EMITTERS,
                answers["heat_emitters_id"],
            ),
        }
    return {}


def _roof_configuration_id(answers: dict[str, Any]) -> str:
    value = answers.get("attic_ventilation_id") or answers.get("roof_type_id") or "attic"
    legacy_mapping = {
        "lost_attic": "attic",
        "ventilated": "attic",
        "limited": "attic",
        "not_ventilated": "attic",
    }
    return legacy_mapping.get(value, value)


def _initial_heating_ref(profile_id: str, answers: dict[str, Any]) -> str:
    if profile_id != "heat_pump_seller":
        return answers.get("heating_ref", "electric_radiator")

    _require_fields(answers, ["current_energy_id", "heat_emitters_id"])
    current_energy_id = answers["current_energy_id"]
    heat_emitters_id = answers["heat_emitters_id"]
    if current_energy_id == "gas":
        return "gas_boiler_standard"
    if current_energy_id == "fuel_oil":
        return "fuel_oil_boiler_standard"
    if current_energy_id == "wood":
        return "wood_stove_standard"
    if current_energy_id == "electricity" and heat_emitters_id == "air_units":
        return "air_air_heat_pump_standard"
    return "electric_radiator"


def _energy_prices(answers: dict[str, Any]) -> dict[str, float]:
    heating_ref = answers.get("heating_ref", "electric_radiator")
    energy = _heating_energy_vector(heating_ref)
    default_prices = {
        "electricity": 0.25,
        "gas": 0.11,
        "fuel_oil": 0.13,
        "wood": 0.07,
    }
    price = answers.get("heating_energy_price_eur_kwh")
    if price in (None, ""):
        price = default_prices[energy]
    price = float(price)
    if price <= 0:
        raise BusinessFlowError("The heating energy price must be strictly positive.")
    prices = {"electricity_eur_kwh": default_prices["electricity"]}
    prices[f"{energy}_eur_kwh"] = price
    return prices


def _heating_energy_vector(heating_ref: str) -> str:
    if heating_ref.startswith("gas_"):
        return "gas"
    if heating_ref.startswith("fuel_oil_"):
        return "fuel_oil"
    if heating_ref.startswith("wood_"):
        return "wood"
    return "electricity"


def _normalize_room(
    room: dict[str, Any],
    index: int,
    dwelling_type: str,
    dwelling_position: str,
) -> dict[str, Any]:
    _require_fields(room, ["name", "type", "floor_area_m2"])
    floor_area_m2 = _float_field(room["floor_area_m2"], f"rooms[{index}].floor_area_m2")
    height_m = _float_field(room.get("height_m", 2.5), f"rooms[{index}].height_m")
    if floor_area_m2 <= 0:
        raise BusinessFlowError(f"rooms[{index}].floor_area_m2 must be > 0.")
    if height_m < 1.8 or height_m > 5.0:
        raise BusinessFlowError(f"rooms[{index}].height_m must be between 1.8 m and 5.0 m.")

    room_id = room.get("id") or customer_experience.slugify(room["name"], f"room_{index}")
    exterior_contact = room.get("exterior_contact", "exterior")
    if exterior_contact not in {"exterior", "interior", "unheated_space", "party"}:
        raise BusinessFlowError(f"rooms[{index}].exterior_contact is invalid.")
    if exterior_contact == "exterior" and "facades" in room and not room["facades"]:
        raise BusinessFlowError(
            f"rooms[{index}].facades must contain at least one exterior facade."
        )
    facades = [
        _normalize_facade(facade, room["type"], floor_area_m2, height_m, index, facade_index)
        for facade_index, facade in enumerate(room.get("facades", []), start=1)
    ]
    if exterior_contact == "exterior" and not facades:
        facades = [
            _normalize_facade(
                {
                    "orientation": room.get("main_orientation", "S"),
                    "window_area_m2": room.get("window_area_m2", 0.0),
                },
                room["type"],
                floor_area_m2,
                height_m,
                index,
                1,
            ),
        ]

    return {
        "id": room_id,
        "name": room["name"],
        "type": room["type"],
        "floor_area_m2": floor_area_m2,
        "height_m": height_m,
        "exterior_contact": exterior_contact,
        "facades": facades,
        "has_roof": bool(
            room.get(
                "has_roof",
                customer_experience.default_has_roof(dwelling_type, dwelling_position),
            ),
        ),
        "has_ground_floor": bool(
            room.get(
                "has_ground_floor",
                customer_experience.default_has_ground_floor(
                    dwelling_type,
                    dwelling_position,
                ),
            ),
        ),
        "has_cooling": _answer_bool(room["has_cooling"], False)
        if "has_cooling" in room
        else None,
    }


def _normalize_facade(
    facade: dict[str, Any],
    room_type: str,
    room_area_m2: float,
    room_height_m: float,
    room_index: int,
    facade_index: int,
) -> dict[str, Any]:
    orientation = facade.get("orientation", "S")
    if orientation not in customer_experience.ORIENTATIONS:
        raise BusinessFlowError(
            f"rooms[{room_index}].facades[{facade_index}].orientation is invalid."
        )
    window_area = facade.get("window_area_m2")
    if window_area is None:
        window_area = customer_experience.default_window_area(
            room_type,
            room_area_m2,
            orientation,
        )
    window_area = _float_field(
        window_area,
        f"rooms[{room_index}].facades[{facade_index}].window_area_m2",
    )
    wall_length_m = _float_field(
        facade.get("wall_length_m", room_area_m2**0.5),
        f"rooms[{room_index}].facades[{facade_index}].wall_length_m",
    )
    mask_factor = _float_field(
        facade.get("mask_factor", 1.0),
        f"rooms[{room_index}].facades[{facade_index}].mask_factor",
    )
    if window_area < 0:
        raise BusinessFlowError(
            f"rooms[{room_index}].facades[{facade_index}].window_area_m2 must be >= 0."
        )
    if wall_length_m <= 0:
        raise BusinessFlowError(
            f"rooms[{room_index}].facades[{facade_index}].wall_length_m must be > 0."
        )
    if mask_factor < 0 or mask_factor > 1:
        raise BusinessFlowError(
            f"rooms[{room_index}].facades[{facade_index}].mask_factor must be between 0 and 1."
        )
    gross_facade_area = wall_length_m * room_height_m
    if window_area > gross_facade_area:
        raise BusinessFlowError(
            f"rooms[{room_index}].facades[{facade_index}].window_area_m2 cannot exceed the facade area ({gross_facade_area:.2f} m²)."
        )
    return {
        "orientation": orientation,
        "window_area_m2": window_area,
        "wall_length_m": wall_length_m,
        "mask_factor": mask_factor,
        "window_ref": facade.get("window_ref"),
    }


def _thermal_layout(
    rooms: list[dict[str, Any]],
    explicit_layout: dict[str, Any] | None,
) -> dict[str, Any]:
    if explicit_layout:
        return deepcopy(explicit_layout)
    if len(rooms) < 2:
        return {"type": "single_room", "connections": []}
    return {"type": "open_living", "connections": []}


def _shutter_usage(answers: dict[str, Any], adaptation_id: str) -> dict[str, Any]:
    shutter_usage_id = answers.get("shutter_usage_id")
    if not shutter_usage_id:
        if (
            adaptation_id != "solar_protection"
            and answers.get("shutter_ref", "roller_shutter_standard") == "none"
        ):
            return {"id": "none", "label": "No current solar protection"}
        return _option_by_id(customer_experience.SHUTTER_USAGE_LEVELS, "partial")
    return _option_by_id(customer_experience.SHUTTER_USAGE_LEVELS, shutter_usage_id)


def _roof_insulation(
    answers: dict[str, Any],
    dwelling_type: str,
    dwelling_position: str,
) -> dict[str, Any]:
    default_id = (
        "standard"
        if customer_experience.dwelling_has_roof_contact(dwelling_type, dwelling_position)
        else "not_concerned"
    )
    return _option_by_id(
        customer_experience.ROOF_INSULATION_LEVELS,
        answers.get("roof_insulation_id", default_id),
    )


def _floor_insulation(
    answers: dict[str, Any],
    dwelling_type: str,
    dwelling_position: str,
) -> dict[str, Any]:
    default_id = (
        "standard"
        if customer_experience.dwelling_has_floor_contact(dwelling_type, dwelling_position)
        else "not_concerned"
    )
    return _option_by_id(
        customer_experience.FLOOR_INSULATION_LEVELS,
        answers.get("floor_insulation_id", default_id),
    )


def _change_by_id(change_id: str) -> dict[str, Any]:
    return _option_by_id(customer_experience.CHANGES, change_id)


def _option_by_id(options: list[dict[str, Any]], option_id: str) -> dict[str, Any]:
    try:
        return next(option for option in options if option["id"] == option_id)
    except StopIteration as exc:
        raise BusinessFlowError(f"Unknown option id: {option_id}") from exc


def _validate_setpoint(value: float, field_name: str) -> None:
    if value < 10 or value > 35:
        raise BusinessFlowError(f"{field_name} must be between 10 °C and 35 °C.")


def _float_field(value: Any, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise BusinessFlowError(f"{field_name} must be a number.") from exc


def _require_fields(payload: dict[str, Any], field_names: list[str]) -> None:
    missing = [field for field in field_names if field not in payload]
    if missing:
        raise BusinessFlowError(f"Missing required field(s): {', '.join(missing)}")
