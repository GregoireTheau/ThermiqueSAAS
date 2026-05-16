from thermal_model import load_dwelling, load_reference_catalog, load_scenario, resolve_dwelling_references
from scripts.simulate_1r1c import apply_scenario_overrides, simulate_1r1c


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

    assert round(results["totals"]["cooling_electric_kwh"], 2) == 11.29
    bedroom_max = max(
        hour["rooms"]["bedroom"]["temperature_c"]
        for hour in results["hourly"]
    )
    assert round(bedroom_max, 1) == 35.5
