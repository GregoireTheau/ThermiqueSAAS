from thermal_model import (
    compare_scenarios,
    load_dwelling,
    load_reference_catalog,
    load_scenario,
    resolve_dwelling_references,
)


def _resolved_dwelling():
    catalog = load_reference_catalog()
    dwelling = load_dwelling("data/examples/house_simple.json", validate=False)
    return resolve_dwelling_references(dwelling, catalog)


def _compare(before_path, after_path):
    return compare_scenarios(
        _resolved_dwelling(),
        load_scenario(before_path),
        load_scenario(after_path),
        air_density_kg_m3=1.2,
        air_heat_capacity_j_kgk=1005.0,
    )


def test_commercial_roof_retrofit_heatwave_3d():
    before = load_scenario("data/examples/scenario_commercial_roof_heatwave_3d_before.json")
    after = load_scenario("data/examples/scenario_commercial_roof_heatwave_3d_after.json")

    comparison = _compare(
        "data/examples/scenario_commercial_roof_heatwave_3d_before.json",
        "data/examples/scenario_commercial_roof_heatwave_3d_after.json",
    )

    assert len(before["weather"]["hourly"]) == 72
    assert len(after["weather"]["hourly"]) == 72
    assert round(comparison["deltas"]["electricity_kwh"], 2) == 3.73
    assert round(comparison["deltas"]["rooms"]["bedroom"]["delta_max_temperature_c"], 1) == 1.6
    assert comparison["summary"]["main_gain_driver"]["key"] == "solar_gains"
    assert comparison["summary"]["comfort_gain"]["room_name"] == "Chambre"


def test_commercial_window_shutter_summer_3d():
    comparison = _compare(
        "data/examples/scenario_commercial_window_shutter_summer_before.json",
        "data/examples/scenario_commercial_window_shutter_summer_after.json",
    )

    assert round(comparison["deltas"]["electricity_kwh"], 2) == 9.94
    assert round(comparison["deltas"]["rooms"]["living_room"]["delta_max_temperature_c"], 1) == 3.8
    assert comparison["summary"]["main_gain_driver"]["key"] == "solar_gains"


def test_commercial_heat_pump_winter_7d():
    before = load_scenario("data/examples/scenario_commercial_pac_winter_7d_before.json")
    after = load_scenario("data/examples/scenario_commercial_pac_winter_7d_after.json")

    comparison = _compare(
        "data/examples/scenario_commercial_pac_winter_7d_before.json",
        "data/examples/scenario_commercial_pac_winter_7d_after.json",
    )

    assert len(before["weather"]["hourly"]) == 168
    assert len(after["weather"]["hourly"]) == 168
    assert round(comparison["deltas"]["electricity_kwh"], 2) == 141.09
    assert round(comparison["deltas"]["electricity_cost_eur"], 2) == 35.27
    assert comparison["summary"]["main_gain_driver"]["key"] == "system_efficiency"
