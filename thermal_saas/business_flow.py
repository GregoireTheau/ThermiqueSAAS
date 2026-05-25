"""Generic business-profile flow for the ThermalTwin SaaS."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts import create_customer_experience as customer_experience
from thermal_model import (
    build_report_model,
    build_thermal_weather,
    city_slug,
    collect_model_warnings,
    combine_weather_years,
    compare_scenarios,
    ensure_openmeteo_thermal_weather,
    load_reference_catalog,
    read_parquet,
    render_report_html,
    resolve_dwelling_references,
    resolve_scenario_weather_reference,
    thermal_weather_ref,
    validate_dwelling,
    validate_scenario,
    write_thermal_weather_json,
)

from .business_profiles import build_questionnaire, load_business_profile


DEFAULT_AIR_DENSITY_KG_M3 = 1.2
DEFAULT_AIR_HEAT_CAPACITY_J_KGK = 1005.0


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
            "city",
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
            f"Le changement '{adaptation_id}' n'est pas compatible avec le profil métier '{profile['id']}'.",
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
    climate_zone_id = answers.get("climate_zone_id") or customer_experience.infer_climate_zone(
        catalog,
        postal_code,
    )
    if not climate_zone_id:
        raise BusinessFlowError("climate_zone_id is required when postal_code cannot be mapped.")

    heating_setpoint_c = float(answers.get("heating_setpoint_c", 19.0))
    cooling_setpoint_c = float(answers.get("cooling_setpoint_c", 26.0))
    _validate_setpoint(heating_setpoint_c, "heating_setpoint_c")
    _validate_setpoint(cooling_setpoint_c, "cooling_setpoint_c")
    if cooling_setpoint_c < heating_setpoint_c:
        raise BusinessFlowError(
            "La consigne de chauffage ne peut pas être supérieure à la consigne de climatisation.",
        )

    return {
        "project_name": answers["project_name"],
        "dwelling_type": dwelling_type,
        "position": position,
        "adjacency": _option_by_id(
            customer_experience.ADJACENCY_LEVELS,
            answers.get("adjacency_id", "detached"),
        ),
        "city": answers["city"],
        "postal_code": postal_code,
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
        "setpoints": {"heating_c": heating_setpoint_c, "cooling_c": cooling_setpoint_c},
        "rooms": rooms,
        "thermal_layout": _thermal_layout(rooms, answers.get("thermal_layout")),
        "change": change,
        "change_details": _change_details(adaptation_id, answers),
        "target_scope": answers.get("target_scope", "all"),
        "include_annual_experiment": _answer_bool(
            answers.get("include_annual_experiment"),
            bool(profile.get("include_annual_experiment", True)),
        ),
        "annual_weather_year": int(answers.get("annual_weather_year", 2023)),
        "annual_weather_dir": answers.get("annual_weather_dir", "data/weather/openmeteo"),
    }


def prepare_experiment_weather(experiment: dict[str, Any]) -> None:
    """Ensure annual weather exists locally and resolve weather_ref scenarios."""
    if experiment["role"] != "annual":
        return

    weather_city = experiment["before"]["experiment"]["weather_city"]
    weather_year = experiment["before"]["experiment"]["weather_year"]
    weather_dir = _weather_dir_from_scenario(experiment["before"])
    try:
        ensure_annual_weather(weather_city, weather_year, weather_dir)
    except Exception as exc:
        raise BusinessFlowError(
            f"Météo annuelle {weather_year} indisponible pour {weather_city}.",
        ) from exc

    for scenario_key in ("before", "after"):
        resolve_scenario_weather_reference(experiment[scenario_key], Path.cwd())


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
        return {
            "roof_type": _option_by_id(
                customer_experience.ROOF_TYPES,
                answers.get("roof_type_id", "lost_attic"),
            ),
            "roof_color": _option_by_id(
                customer_experience.ROOF_COLORS,
                answers.get("roof_color_id", "medium"),
            ),
            "attic_ventilation": _option_by_id(
                customer_experience.ATTIC_VENTILATION_LEVELS,
                answers.get("attic_ventilation_id", "limited"),
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
        raise BusinessFlowError(f"rooms[{index}].floor_area_m2 doit être > 0.")
    if height_m < 1.8 or height_m > 5.0:
        raise BusinessFlowError(f"rooms[{index}].height_m doit être entre 1.8 m et 5.0 m.")

    room_id = room.get("id") or customer_experience.slugify(room["name"], f"room_{index}")
    exterior_contact = room.get("exterior_contact", "exterior")
    if exterior_contact not in {"exterior", "interior", "unheated_space", "party"}:
        raise BusinessFlowError(f"rooms[{index}].exterior_contact est invalide.")
    if exterior_contact == "exterior" and "facades" in room and not room["facades"]:
        raise BusinessFlowError(
            f"rooms[{index}].facades doit contenir au moins une façade extérieure."
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
            f"rooms[{room_index}].facades[{facade_index}].orientation est invalide."
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
            f"rooms[{room_index}].facades[{facade_index}].window_area_m2 doit être >= 0."
        )
    if wall_length_m <= 0:
        raise BusinessFlowError(
            f"rooms[{room_index}].facades[{facade_index}].wall_length_m doit être > 0."
        )
    if mask_factor < 0 or mask_factor > 1:
        raise BusinessFlowError(
            f"rooms[{room_index}].facades[{facade_index}].mask_factor doit être entre 0 et 1."
        )
    gross_facade_area = wall_length_m * room_height_m
    if window_area > gross_facade_area:
        raise BusinessFlowError(
            f"rooms[{room_index}].facades[{facade_index}].window_area_m2 ne peut pas dépasser la surface de façade ({gross_facade_area:.2f} m²)."
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
            return {"id": "none", "label": "Pas de protection solaire actuelle"}
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
        raise BusinessFlowError(f"{field_name} doit être entre 10 °C et 35 °C.")


def _float_field(value: Any, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise BusinessFlowError(f"{field_name} doit être un nombre.") from exc


def _require_fields(payload: dict[str, Any], field_names: list[str]) -> None:
    missing = [field for field in field_names if field not in payload]
    if missing:
        raise BusinessFlowError(f"Missing required field(s): {', '.join(missing)}")
