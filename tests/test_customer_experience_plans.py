from scripts import create_customer_experience as customer_experience
from thermal_model import (
    build_report_model,
    compare_scenarios,
    load_dwelling,
    load_reference_catalog,
    render_report_html,
    resolve_dwelling_references,
    validate_scenario,
)


def _resolved_dwelling():
    catalog = load_reference_catalog()
    dwelling = load_dwelling("data/examples/house_simple.json", validate=False)
    return resolve_dwelling_references(dwelling, catalog), catalog


def _change(change_id):
    return next(
        change
        for change in customer_experience.CHANGES
        if change["id"] == change_id
    )


def test_reflective_roof_runs_heatwave_and_long_summer():
    dwelling, catalog = _resolved_dwelling()
    customer = {"change": _change("reflective_roof"), "target_scope": "all"}

    experiments = customer_experience.build_experiments(customer, dwelling, catalog)

    assert [experiment["id"] for experiment in experiments] == [
        "house_simple_reflective_roof_summer_heatwave",
        "house_simple_reflective_roof_summer_long",
    ]
    assert [experiment["role"] for experiment in experiments] == ["primary", "secondary"]
    assert len(experiments[0]["before"]["weather"]["hourly"]) == 72
    assert len(experiments[1]["before"]["weather"]["hourly"]) == 1440
    assert experiments[1]["before"]["experiment"]["weather_variant"] == (
        "summer_long_with_heatwave"
    )
    validate_scenario(experiments[0]["before"])
    validate_scenario(experiments[1]["after"])


def test_window_summer_experiment_requires_exposed_windows():
    dwelling, catalog = _resolved_dwelling()

    north_window_customer = {
        "change": _change("better_windows"),
        "target_scope": "bathroom",
    }
    exposed_window_customer = {
        "change": _change("better_windows"),
        "target_scope": "bedroom",
    }

    north_window_experiments = customer_experience.build_experiments(
        north_window_customer,
        dwelling,
        catalog,
    )
    exposed_window_experiments = customer_experience.build_experiments(
        exposed_window_customer,
        dwelling,
        catalog,
    )

    assert [experiment["season"] for experiment in north_window_experiments] == ["winter"]
    assert [experiment["season"] for experiment in exposed_window_experiments] == [
        "winter",
        "summer",
    ]


def test_report_exposes_experiment_role_and_reason():
    dwelling, catalog = _resolved_dwelling()
    customer = {"change": _change("solar_protection"), "target_scope": "living_room"}
    experiment = customer_experience.build_experiments(customer, dwelling, catalog)[0]

    comparison = compare_scenarios(
        dwelling,
        experiment["before"],
        experiment["after"],
        air_density_kg_m3=1.2,
        air_heat_capacity_j_kgk=1005.0,
    )
    report = build_report_model(comparison)
    html = render_report_html(report)

    assert comparison["experiment"]["role"] == "primary"
    assert report["experiment"]["label"] == "Ete canicule"
    assert "Experience principale" in html
    assert "apports solaires" in html
