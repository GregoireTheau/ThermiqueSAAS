import json
from copy import deepcopy
from pathlib import Path

import pytest

from thermal_model import (
    resolve_scenario_weather_reference,
    simulate_1r1c,
    validate_dwelling,
    validate_scenario,
)


REFERENCE_CASES_DIR = Path("data/reference_cases")
REFERENCE_CASES_PATH = REFERENCE_CASES_DIR / "reference_cases.json"


def _load_reference_cases():
    with REFERENCE_CASES_PATH.open(encoding="utf-8") as file:
        return json.load(file)["cases"]


def _build_dwelling(case):
    area_m2 = case["area_m2"]
    height_m = case["height_m"]
    ventilation_ach = (
        case["ventilation"]["infiltration_ach"]
        + case["ventilation"]["mechanical_ach"]
    )

    heating_systems = []
    if case["systems"]["heating"]:
        heating = case["systems"]["heating"]
        heating_systems.append(
            {
                "id": "heating_system",
                "type": heating["type"],
                "served_rooms": ["main_room"],
                "max_power_w": heating["max_power_w"],
                "performance_ref": {
                    "mode": "constant",
                    "cop": heating["cop"],
                },
            }
        )

    cooling_systems = []
    if case["systems"]["cooling"]:
        cooling = case["systems"]["cooling"]
        cooling_systems.append(
            {
                "id": "cooling_system",
                "type": cooling["type"],
                "served_rooms": ["main_room"],
                "max_power_w": cooling["max_power_w"],
                "performance_ref": {
                    "mode": "constant",
                    "eer": cooling["eer"],
                },
            }
        )

    return {
        "schema_version": "0.1",
        "dwelling_id": case["case_id"],
        "metadata": {
            "name": case["label"],
            "description": case["physical_comment"],
            "created_by": "reference_cases",
        },
        "location": {
            "country": "FR",
            "postal_code": "33000",
            "city": "Reference",
            "climate_zone_id": "US_IECC_2021_3A",
            "ground_albedo": 0.2,
        },
        "defaults": {
            "initial_temperature_c": case["initial_temperature_c"],
            "equivalent_capacity_j_m2k": case["equivalent_capacity_j_m2k"],
            "thermal_bridge_factor": case["thermal_bridge_factor"],
            "internal_gain_w_m2": case["internal_gain_w_m2"],
            "ach_h": ventilation_ach,
        },
        "rooms": [
            {
                "id": "main_room",
                "name": case["label"],
                "type": "living",
                "floor_area_m2": area_m2,
                "height_m": height_m,
                "volume_m3": area_m2 * height_m,
                "initial_temperature_c": case["initial_temperature_c"],
                "equivalent_capacity_j_m2k": case["equivalent_capacity_j_m2k"],
                "internal_gain_w_m2": case["internal_gain_w_m2"],
                "ventilation": {
                    "mode": "ach",
                    "ach_h": ventilation_ach,
                    "infiltration_ach": case["ventilation"]["infiltration_ach"],
                    "mechanical_ach": case["ventilation"]["mechanical_ach"],
                    "recovery_efficiency": case["ventilation"]["recovery_efficiency"],
                },
                "surfaces": deepcopy(case["surfaces"]),
                "windows": deepcopy(case["windows"]),
            }
        ],
        "thermal_links": [],
        "systems": {
            "heating": heating_systems,
            "cooling": cooling_systems,
            "ventilation": {
                "type": "other",
                "default_ach_h": ventilation_ach,
                "infiltration_ach": case["ventilation"]["infiltration_ach"],
                "mechanical_ach": case["ventilation"]["mechanical_ach"],
                "recovery_efficiency": case["ventilation"]["recovery_efficiency"],
            },
        },
    }


def _build_scenario(case):
    scenario_data = case["scenario"]
    natural_ventilation = {
        "default_ach": scenario_data["natural_ventilation_default_ach"],
    }
    if scenario_data.get("smart_night_cooling"):
        natural_ventilation["smart_night_cooling"] = True
        natural_ventilation["smart_ach"] = scenario_data["smart_ach"]

    scenario = {
        "schema_version": "0.1",
        "scenario_id": f"{case['case_id']}_scenario",
        "dwelling_id": case["case_id"],
        "description": case["physical_comment"],
        "timestep_h": 1.0,
        "initial_temperatures_c": {"main_room": case["initial_temperature_c"]},
        "climate_zone_id": scenario_data.get(
            "climate_zone_id",
            "US_IECC_2021_3A",
        ),
        "setpoints": {
            "heating_c": scenario_data["heating_c"],
            "cooling_c": scenario_data["cooling_c"],
        },
        "controls": {
            "shutters": {
                "default_opening_ratio": scenario_data["shutter_opening_ratio"],
            },
            "natural_ventilation": natural_ventilation,
        },
        "weather": {"weather_ref": scenario_data["weather_ref"]},
        "energy_prices": {"electricity_eur_kwh": 0.25},
        "co2_factors": {"electricity_kg_kwh": 0.06},
    }
    if "shutter_hourly" in scenario_data:
        scenario["controls"]["shutters"]["hourly"] = [
            {"hour": hour, "opening_ratio": entry["opening_ratio"]}
            for entry in scenario_data["shutter_hourly"]
            for hour in range(entry["start_hour"], entry["end_hour"] + 1)
        ]
    resolve_scenario_weather_reference(scenario, REFERENCE_CASES_DIR)
    return scenario


def _metric_value(results, metric_name):
    if metric_name in results["totals"]:
        return results["totals"][metric_name]
    return results["rooms_summary"]["main_room"][metric_name]


def test_reference_case_manifest_is_complete():
    cases = _load_reference_cases()

    assert 10 <= len(cases) <= 20
    assert len({case["case_id"] for case in cases}) == len(cases)
    for case in cases:
        assert case["physical_comment"]
        assert case["expected_metrics"]


@pytest.mark.parametrize(
    "case",
    _load_reference_cases(),
    ids=lambda case: case["case_id"],
)
def test_reference_case_outputs_stay_within_expected_ranges(case):
    dwelling = _build_dwelling(case)
    scenario = _build_scenario(case)
    validate_dwelling(dwelling)
    validate_scenario(scenario)

    results = simulate_1r1c(
        dwelling,
        scenario,
        air_density_kg_m3=1.2,
        air_heat_capacity_j_kgk=1005.0,
    )

    for metric_name, expected_range in case["expected_metrics"].items():
        value = _metric_value(results, metric_name)
        assert expected_range["min"] <= value <= expected_range["max"], metric_name


def test_reference_cases_keep_expected_physical_ordering():
    results_by_case = {}
    for case in _load_reference_cases():
        dwelling = _build_dwelling(case)
        scenario = _build_scenario(case)
        results_by_case[case["case_id"]] = simulate_1r1c(
            dwelling,
            scenario,
            air_density_kg_m3=1.2,
            air_heat_capacity_j_kgk=1005.0,
        )

    assert (
        results_by_case["modern_high_efficiency_house_winter"]["totals"][
            "heating_electric_kwh"
        ]
        < results_by_case["seventies_house_winter"]["totals"]["heating_electric_kwh"]
    )
    assert (
        results_by_case["heatwave_with_closed_shutters"]["rooms_summary"]["main_room"][
            "hot_degree_hours"
        ]
        < results_by_case["large_south_bay_heatwave"]["rooms_summary"]["main_room"][
            "hot_degree_hours"
        ]
    )
    assert (
        results_by_case["weak_ventilation_winter"]["totals"]["heating_electric_kwh"]
        < results_by_case["strong_ventilation_winter"]["totals"]["heating_electric_kwh"]
    )
    assert (
        results_by_case["heavy_inertia_heatwave"]["rooms_summary"]["main_room"][
            "max_temperature_c"
        ]
        < results_by_case["light_inertia_heatwave"]["rooms_summary"]["main_room"][
            "max_temperature_c"
        ]
    )


def test_heatwave_reference_cases_define_protected_and_unprotected_variants():
    heatwave_cases = [
        case
        for case in _load_reference_cases()
        if case["scenario"]["weather_ref"] == "weather_heatwave_24h.json"
    ]

    assert heatwave_cases
    for case in heatwave_cases:
        assert set(case["scenario_variants"]) == {
            "canicule_sans_protection",
            "canicule_occupant_raisonnable",
        }
        for window in case["windows"]:
            assert window["shutter"]["solar_factor_closed"] == 0.15
            assert window["shutter"]["solar_factor_open"] == 1.0


def test_reasonable_occupant_heatwave_variant_reduces_temperature_at_20h():
    for case in _load_reference_cases():
        if case["scenario"]["weather_ref"] != "weather_heatwave_24h.json":
            continue

        unprotected_case = deepcopy(case)
        unprotected_case["scenario"].update(
            case["scenario_variants"]["canicule_sans_protection"]
        )
        protected_case = deepcopy(case)
        protected_case["scenario"].update(
            case["scenario_variants"]["canicule_occupant_raisonnable"]
        )
        dwelling = _build_dwelling(case)
        unprotected_results = simulate_1r1c(
            dwelling,
            _build_scenario(unprotected_case),
            air_density_kg_m3=1.2,
            air_heat_capacity_j_kgk=1005.0,
        )
        protected_results = simulate_1r1c(
            dwelling,
            _build_scenario(protected_case),
            air_density_kg_m3=1.2,
            air_heat_capacity_j_kgk=1005.0,
        )

        assert (
            protected_results["hourly"][20]["rooms"]["main_room"]["temperature_c"]
            < unprotected_results["hourly"][20]["rooms"]["main_room"]["temperature_c"]
        )
