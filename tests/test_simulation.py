from thermal_model import (
    apply_scenario_overrides,
    load_dwelling,
    load_reference_catalog,
    load_scenario,
    resolve_dwelling_references,
    simulate_1r1c,
)


def _resolved_dwelling():
    catalog = load_reference_catalog()
    dwelling = load_dwelling("data/examples/house_simple.json", validate=False)
    return resolve_dwelling_references(dwelling, catalog)


def test_winter_simulation_energy_totals():
    dwelling = _resolved_dwelling()
    scenario = load_scenario("data/examples/scenario_simple.json")

    results = simulate_1r1c(
        dwelling,
        scenario,
        air_density_kg_m3=1.2,
        air_heat_capacity_j_kgk=1005.0,
    )

    assert round(results["totals"]["heating_thermal_kwh"], 2) == 33.01
    assert round(results["totals"]["heating_electric_kwh"], 2) == 19.86
    assert round(results["totals"]["cooling_electric_kwh"], 2) == 0.0
    assert set(results) == {"hourly", "rooms_summary", "totals"}
    assert set(results["rooms_summary"]) == {"living_room", "bedroom", "bathroom"}

    living_summary = results["rooms_summary"]["living_room"]
    living_temperatures = [
        hour["rooms"]["living_room"]["temperature_c"]
        for hour in results["hourly"]
    ]
    assert living_summary["room_name"] == "Salon cuisine"
    assert living_summary["max_temperature_c"] == max(living_temperatures)
    assert living_summary["final_temperature_c"] == living_temperatures[-1]


def test_heatwave_after_reflective_roof_simulation():
    dwelling = _resolved_dwelling()
    scenario = load_scenario("data/examples/scenario_heatwave.json")
    apply_scenario_overrides(dwelling, scenario)

    results = simulate_1r1c(
        dwelling,
        scenario,
        air_density_kg_m3=1.2,
        air_heat_capacity_j_kgk=1005.0,
    )

    assert round(results["totals"]["cooling_electric_kwh"], 2) == 10.34
    assert round(results["rooms_summary"]["living_room"]["cooling_thermal_kwh"], 2) == 31.02
    assert round(results["rooms_summary"]["bedroom"]["hot_degree_hours"], 1) == 113.2
    assert round(results["rooms_summary"]["bedroom"]["solar_gain_kwh"], 2) == 3.95
    assert round(results["rooms_summary"]["bedroom"]["transmission_exchange_kwh"], 2) == 1.01
    assert round(results["rooms_summary"]["bedroom"]["ventilation_exchange_kwh"], 2) == 0.18
    bedroom_max = max(
        hour["rooms"]["bedroom"]["temperature_c"]
        for hour in results["hourly"]
    )
    assert round(bedroom_max, 1) == 34.2


def test_apply_scenario_overrides_updates_windows_shutters_and_systems():
    dwelling = _resolved_dwelling()
    scenario = {
        "retrofit": {
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
    }

    apply_scenario_overrides(dwelling, scenario)

    bedroom_window = dwelling["rooms"][1]["windows"][0]
    assert bedroom_window["u_value_w_m2k"] == 1.1
    assert bedroom_window["g_value"] == 0.4
    assert bedroom_window["shutter"]["solar_factor_closed"] == 0.08

    living_ac = dwelling["systems"]["cooling"][0]
    assert living_ac["max_power_w"] == 3500
    assert living_ac["performance_ref"]["eer"] == 3.8
    assert dwelling["systems"]["cooling"][1]["id"] == "bedroom_ac"
