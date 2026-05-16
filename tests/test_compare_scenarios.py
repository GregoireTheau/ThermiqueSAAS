from thermal_model import (
    compare_scenarios,
    load_dwelling,
    load_reference_catalog,
    load_scenario,
    resolve_dwelling_references,
)


def test_compare_heatwave_before_after_reflective_roof():
    catalog = load_reference_catalog()
    dwelling = load_dwelling("data/examples/house_simple.json", validate=False)
    dwelling = resolve_dwelling_references(dwelling, catalog)
    before = load_scenario("data/examples/scenario_heatwave_before.json")
    after = load_scenario("data/examples/scenario_heatwave.json")

    comparison = compare_scenarios(
        dwelling,
        before,
        after,
        air_density_kg_m3=1.2,
        air_heat_capacity_j_kgk=1005.0,
    )

    assert round(comparison["deltas"]["electricity_kwh"], 2) == 2.54
    assert round(
        comparison["deltas"]["rooms"]["bedroom"]["delta_max_temperature_c"],
        1,
    ) == 4.0
    bedroom_deltas = comparison["deltas"]["rooms"]["bedroom"]
    assert "delta_hot_degree_hours" in bedroom_deltas
    assert "delta_cold_degree_hours" in bedroom_deltas
    assert "delta_solar_gain_kwh" in bedroom_deltas
    assert "delta_transmission_exchange_kwh" in bedroom_deltas
    assert "delta_ventilation_exchange_kwh" in bedroom_deltas
    assert "delta_heating_thermal_kwh" in bedroom_deltas
    assert "delta_cooling_thermal_kwh" in bedroom_deltas
    assert comparison["comparison_schema_version"] == "0.2"
    assert comparison["summary"]["energy_savings"]["electricity_saved_kwh"] == comparison["deltas"]["electricity_kwh"]
    assert comparison["summary"]["main_gain_driver"]["key"] == "solar_gains"
