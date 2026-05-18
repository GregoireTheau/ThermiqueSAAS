from thermal_model import (
    build_report_model,
    compare_scenarios,
    load_dwelling,
    load_reference_catalog,
    load_scenario,
    render_report_html,
    resolve_dwelling_references,
)


def _comparison(before_path, after_path):
    catalog = load_reference_catalog()
    dwelling = load_dwelling("data/examples/house_simple.json", validate=False)
    dwelling = resolve_dwelling_references(dwelling, catalog)
    return compare_scenarios(
        dwelling,
        load_scenario(before_path),
        load_scenario(after_path),
        air_density_kg_m3=1.2,
        air_heat_capacity_j_kgk=1005.0,
    )


def test_report_model_keeps_traceable_headline_metrics():
    comparison = _comparison(
        "data/examples/scenario_heatwave_before.json",
        "data/examples/scenario_heatwave.json",
    )

    report = build_report_model(comparison)

    assert report["report_schema_version"] == "0.1"
    assert report["source"]["dwelling_id"] == comparison["dwelling_id"]
    assert report["experiment"]["duration_hours"] == 24
    assert report["experiment"]["duration_days"] == 1
    assert report["experiment"]["weather_source"] == "synthetic"
    assert report["experiment"]["title"].startswith("Simulation")
    assert report["experiment"]["scope_notice"].startswith("Ces resultats portent")
    assert "Aucune projection annuelle" in report["experiment"]["annual_projection_notice"]
    assert "temperature exterieure varie" in report["experiment"]["context_text"]
    assert "definition" in report["main_gain_driver"]
    assert report["headline"]["electricity"]["before"] == round(
        comparison["before"]["totals"]["electricity_kwh"],
        2,
    )
    assert report["headline"]["electricity"]["after"] == round(
        comparison["after"]["totals"]["electricity_kwh"],
        2,
    )
    assert report["headline"]["electricity"]["delta"] == round(
        comparison["deltas"]["electricity_kwh"],
        2,
    )
    assert report["headline"]["electricity"]["effect"] == "reduction"
    assert report["headline"]["electricity"]["unit"] == "kWh"


def test_report_model_excludes_hourly_traces():
    comparison = _comparison(
        "data/examples/scenario_heatwave_before.json",
        "data/examples/scenario_heatwave.json",
    )

    report = build_report_model(comparison)

    assert "hourly" not in report
    assert "before" not in report
    assert "after" not in report
    assert report["methodology"]["reported_values"].startswith("Calculees depuis")


def test_report_model_marks_increases_without_calling_them_savings():
    comparison = _comparison(
        "data/examples/scenario_heatwave.json",
        "data/examples/scenario_heatwave_before.json",
    )

    report = build_report_model(comparison)

    assert report["headline"]["electricity"]["delta"] < 0
    assert report["headline"]["electricity"]["effect"] == "increase"


def test_render_report_html_contains_report_sections_without_hourly_traces():
    comparison = _comparison(
        "data/examples/scenario_heatwave_before.json",
        "data/examples/scenario_heatwave.json",
    )
    report = build_report_model(comparison)

    html = render_report_html(report)

    assert "<!doctype html>" in html
    assert "Simulation toiture reflechissante - confort ete" in html
    assert "Ce qui a ete compare" in html
    assert "Resultat principal" in html
    assert "Lecture des resultats" in html
    assert "Limites de la simulation" in html
    assert "Aucune projection annuelle" in html
    assert "24 h" in html
    assert "Tableaux techniques - detail par piece" in html
    assert comparison["dwelling_id"] in html
    assert '"hourly"' not in html
