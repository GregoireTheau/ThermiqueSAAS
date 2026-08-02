import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

from thermal_model import (
    DwellingValidationError,
    ScenarioValidationError,
    get_climate_zone_for_county,
    get_window_reference,
    load_dwelling,
    load_reference_catalog,
    load_scenario,
    resolve_dwelling_references,
    validate_scenario,
    validate_scenario_against_dwelling,
    validate_dwelling,
)


def test_load_dwelling_house_simple():
    dwelling = load_dwelling("data/examples/house_simple.json")

    assert dwelling["dwelling_id"] == "house_simple"
    assert len(dwelling["rooms"]) == 3
    assert len(dwelling["thermal_links"]) == 2


def test_reference_catalog_loads_expected_refs():
    catalog = load_reference_catalog()

    assert get_window_reference(catalog, "double_glazing_standard")["u_value_w_m2k"] == 1.6
    assert get_climate_zone_for_county(catalog, "13121") == "US_IECC_2021_3A"
    assert get_climate_zone_for_county(catalog, "08031") == "US_IECC_2021_5B"


def test_reference_catalog_contains_official_us_county_mapping():
    catalog = load_reference_catalog()

    assert len(catalog["county_zone_map"]) == 3141
    assert catalog["climate_zones"]["US_IECC_2021_3A"]["code"] == "3A"


def test_resolve_dwelling_references_keeps_explicit_values():
    dwelling = load_dwelling("data/examples/house_simple.json", validate=False)
    catalog = load_reference_catalog()

    resolved = resolve_dwelling_references(dwelling, catalog)

    living_window = resolved["rooms"][0]["windows"][0]
    assert living_window["window_ref"] == "double_glazing_standard"
    assert living_window["u_value_w_m2k"] == 1.6
    assert living_window["g_value"] == 0.55
    assert living_window["shutter"]["solar_factor_closed"] == 0.15


def test_load_scenario_heatwave_before():
    scenario = load_scenario("data/examples/scenario_heatwave_before.json")

    assert scenario["scenario_id"] == "scenario_heatwave_before_roof"
    assert len(scenario["weather"]["hourly"]) == 24


def test_load_scenario_resolves_relative_weather_ref(tmp_path):
    weather_dir = tmp_path / "weather"
    weather_dir.mkdir()
    weather_path = weather_dir / "bordeaux_2023.weather.json"
    weather_path.write_text(
        json.dumps(
            {
                "source": "openmeteo_test",
                "hourly": [
                    {
                        "hour": 0,
                        "outdoor_temperature_c": 7.0,
                        "solar_irradiance_w_m2": {
                            "north": 0.0,
                            "east": 0.0,
                            "south": 0.0,
                            "west": 0.0,
                            "roof": 0.0,
                        },
                    },
                    {
                        "hour": 1,
                        "outdoor_temperature_c": 6.5,
                    },
                ],
            },
        ),
        encoding="utf-8",
    )
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "scenario_id": "weather_ref_scenario",
                "dwelling_id": "house_simple",
                "timestep_h": 1.0,
                "setpoints": {
                    "heating_c": 19.0,
                    "cooling_c": 26.0,
                },
                "weather": {
                    "weather_ref": "weather/bordeaux_2023.weather.json",
                },
                "energy_prices": {
                    "electricity_eur_kwh": 0.25,
                },
                "co2_factors": {
                    "electricity_kg_kwh": 0.06,
                },
            },
        ),
        encoding="utf-8",
    )

    scenario = load_scenario(scenario_path)

    assert scenario["weather"]["source"] == "openmeteo_test"
    assert scenario["weather"]["hourly"][0]["outdoor_temperature_c"] == 7.0
    assert len(scenario["weather"]["hourly"]) == 2


def test_validate_scenario_requires_resolved_weather_ref():
    scenario = deepcopy(load_scenario("data/examples/scenario_simple.json"))
    scenario["weather"] = {"weather_ref": "weather/bordeaux_2023.weather.json"}

    try:
        validate_scenario(scenario)
    except ScenarioValidationError as exc:
        assert "must be resolved" in str(exc)
    else:
        raise AssertionError("validate_scenario accepted an unresolved weather_ref")


def test_validate_scenario_rejects_absurd_setpoints_and_timestep_mismatch():
    scenario = deepcopy(load_scenario("data/examples/scenario_simple.json"))
    scenario["setpoints"] = {"heating_c": 19.0, "cooling_c": 15.0}

    try:
        validate_scenario(scenario)
    except ScenarioValidationError as exc:
        assert "heating_c" in str(exc)
        assert "cooling_c" in str(exc)
    else:
        raise AssertionError("validate_scenario accepted inverted setpoints")

    scenario = deepcopy(load_scenario("data/examples/scenario_simple.json"))
    scenario["timestep_h"] = 0.5

    try:
        validate_scenario(scenario)
    except ScenarioValidationError as exc:
        assert "timestep_h" in str(exc)
    else:
        raise AssertionError("validate_scenario accepted mismatched timestep")


def test_validate_scenario_against_dwelling_rejects_unknown_retrofit_targets():
    dwelling = load_dwelling("data/examples/house_simple.json")
    scenario = deepcopy(load_scenario("data/examples/scenario_simple.json"))
    scenario["retrofit"] = {
        "surface_overrides": [
            {"surface_id": "missing_wall", "u_value_w_m2k": 0.2},
        ],
    }

    try:
        validate_scenario_against_dwelling(scenario, dwelling)
    except ScenarioValidationError as exc:
        assert "surface_overrides" in str(exc)
        assert "missing_wall" in str(exc)
    else:
        raise AssertionError("validate_scenario_against_dwelling accepted unknown surface")


def test_validate_scenario_against_dwelling_rejects_added_system_unknown_room():
    dwelling = load_dwelling("data/examples/house_simple.json")
    scenario = deepcopy(load_scenario("data/examples/scenario_simple.json"))
    scenario["retrofit"] = {
        "add_systems": [
            {
                "category": "heating",
                "id": "extra_heater",
                "type": "electric_radiator",
                "served_rooms": ["missing_room"],
                "max_power_w": 1200,
                "performance_ref": {"mode": "constant", "cop": 1.0},
            },
        ],
    }

    try:
        validate_scenario_against_dwelling(scenario, dwelling)
    except ScenarioValidationError as exc:
        assert "served_rooms" in str(exc) or "missing_room" in str(exc)
    else:
        raise AssertionError("validate_scenario_against_dwelling accepted unknown room")


def test_scenario_schema_accepts_retrofit_equipment_overrides():
    schema = json.loads(Path("schemas/scenario.schema.json").read_text())
    scenario = deepcopy(load_scenario("data/examples/scenario_heatwave_before.json"))
    scenario["retrofit"] = {
        "window_overrides": [
            {
                "window_id": "bedroom_east_window",
                "u_value_w_m2k": 1.1,
                "g_value": 0.4,
            }
        ],
        "shutter_overrides": [
            {
                "window_id": "bedroom_east_window",
                "type": "roller_shutter",
                "solar_factor_closed": 0.08,
                "solar_factor_open": 1.0,
                "u_factor_closed": 0.7,
            }
        ],
        "system_overrides": [
            {
                "category": "cooling",
                "system_id": "living_ac",
                "max_power_w": 3500,
                "performance_ref": {
                    "mode": "constant",
                    "eer": 3.8,
                },
            }
        ],
        "add_systems": [
            {
                "category": "cooling",
                "id": "bedroom_ac",
                "type": "air_conditioner",
                "served_rooms": ["bedroom"],
                "max_power_w": 1200,
                "performance_ref": {
                    "mode": "constant",
                    "eer": 3.2,
                },
            }
        ],
    }

    errors = list(Draft202012Validator(schema).iter_errors(scenario))

    assert errors == []


def test_scenario_schema_accepts_weather_ref():
    schema = json.loads(Path("schemas/scenario.schema.json").read_text())
    scenario = deepcopy(load_scenario("data/examples/scenario_simple.json"))
    scenario["weather"] = {
        "weather_ref": "data/weather/openmeteo/thermal/bordeaux_2023.weather.json",
    }

    errors = list(Draft202012Validator(schema).iter_errors(scenario))

    assert errors == []


def test_scenario_schema_accepts_natural_ventilation_controls():
    schema = json.loads(Path("schemas/scenario.schema.json").read_text())
    scenario = deepcopy(load_scenario("data/examples/scenario_simple.json"))
    scenario["controls"] = {
        "natural_ventilation": {
            "default_ach": 0.0,
            "smart_night_cooling": True,
            "smart_ach": 4.0,
            "hourly": [
                {"hour": 22, "ach": 3.0},
            ],
        },
    }

    errors = list(Draft202012Validator(schema).iter_errors(scenario))

    assert errors == []


def test_dwelling_schema_accepts_split_ventilation_fields():
    schema = json.loads(Path("schemas/dwelling.schema.json").read_text())
    dwelling = deepcopy(load_dwelling("data/examples/house_simple.json"))
    dwelling["defaults"]["infiltration_ach"] = 0.15
    dwelling["defaults"]["mechanical_ach"] = 0.35
    dwelling["defaults"]["recovery_efficiency"] = 0.75
    dwelling["systems"]["ventilation"]["infiltration_ach"] = 0.15
    dwelling["systems"]["ventilation"]["mechanical_ach"] = 0.35
    dwelling["systems"]["ventilation"]["recovery_efficiency"] = 0.75
    dwelling["rooms"][0]["ventilation"]["infiltration_ach"] = 0.15
    dwelling["rooms"][0]["ventilation"]["mechanical_ach"] = 0.35
    dwelling["rooms"][0]["ventilation"]["recovery_efficiency"] = 0.75

    errors = list(Draft202012Validator(schema).iter_errors(dwelling))

    assert errors == []


def test_validate_dwelling_rejects_duplicate_reversed_thermal_links():
    dwelling = load_dwelling("data/examples/house_simple.json", validate=False)
    dwelling["thermal_links"].append(
        {
            **dwelling["thermal_links"][0],
            "id": "reversed_duplicate_link",
            "room_a": dwelling["thermal_links"][0]["room_b"],
            "room_b": dwelling["thermal_links"][0]["room_a"],
        },
    )

    try:
        validate_dwelling(dwelling)
    except DwellingValidationError as exc:
        assert "thermal link room pairs" in str(exc)
    else:
        raise AssertionError("validate_dwelling accepted duplicate reversed thermal links")


def test_validate_dwelling_rejects_absurd_room_height_and_low_cop():
    dwelling = load_dwelling("data/examples/house_simple.json", validate=False)
    dwelling["rooms"][0]["height_m"] = 15.0

    try:
        validate_dwelling(dwelling)
    except DwellingValidationError as exc:
        assert "height_m" in str(exc)
    else:
        raise AssertionError("validate_dwelling accepted absurd room height")

    dwelling = load_dwelling("data/examples/house_simple.json", validate=False)
    dwelling["systems"]["heating"][0]["type"] = "heat_pump"
    dwelling["systems"]["heating"][0]["performance_ref"]["cop"] = 0.8

    try:
        validate_dwelling(dwelling)
    except DwellingValidationError as exc:
        assert "cop" in str(exc)
        assert ">= 1" in str(exc)
    else:
        raise AssertionError("validate_dwelling accepted COP below 1")
