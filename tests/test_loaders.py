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
