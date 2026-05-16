import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

from thermal_model import (
    get_climate_zone_for_department,
    get_window_reference,
    load_dwelling,
    load_reference_catalog,
    load_scenario,
    resolve_dwelling_references,
)


def test_load_dwelling_house_simple():
    dwelling = load_dwelling("data/examples/house_simple.json")

    assert dwelling["dwelling_id"] == "house_simple"
    assert len(dwelling["rooms"]) == 3
    assert len(dwelling["thermal_links"]) == 2


def test_reference_catalog_loads_expected_refs():
    catalog = load_reference_catalog()

    assert get_window_reference(catalog, "double_glazing_standard")["u_value_w_m2k"] == 1.6
    assert get_climate_zone_for_department(catalog, "33") == "FR_H2c"


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
