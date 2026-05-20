from thermal_model import (
    build_report_model,
    compare_scenarios,
    load_dwelling,
    load_reference_catalog,
    load_scenario,
    render_report_html,
    resolve_dwelling_references,
)
from thermal_model.reporting import get_comfort_mode, get_room_status


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

    assert report["report_schema_version"] == "0.3"
    assert report["source"]["dwelling_id"] == comparison["dwelling_id"]
    assert report["experiment"]["duration_hours"] == 24
    assert report["experiment"]["duration_days"] == 1
    assert report["experiment"]["weather_source"] == "synthetic"
    assert report["experiment"]["title"].startswith("Simulation")
    assert "expérience" in report["narrative"]["context"].lower()
    assert "scénario après applique" in report["narrative"]["tested_change"]
    assert "température" in report["narrative"]["conclusion"]
    assert report["temperature_profiles"]["thresholds"]["primary"] == "hot"
    assert report["comfort_mode"] == "hot"
    assert report["experiment"]["scenario_type"] == "unknown"
    assert report["temperature_profiles"]["rooms"][0]["points"][0]["hour"] == 0
    assert "before_temperature_c" in report["temperature_profiles"]["rooms"][0]["points"][0]
    assert "temp_min_before" in report["temperature_profiles"]["rooms"][0]["summary"]
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
    assert "temperature_profiles" in report


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
    assert "Simulation toiture réfléchissante - confort été" in html
    assert "Synthèse exécutive" in html
    assert "Scénario</div>Simulation thermique pendant un épisode de canicule" in html
    assert "Scénarios" not in html
    assert "Contexte" in html
    assert "Graphiques de température" in html
    assert "Résultats principaux" in html
    assert "Lecture des résultats" in html
    assert "Détail par pièce" in html
    assert "Rapport généré automatiquement" in html
    assert "Limites de la simulation" not in html
    assert "24 h" in html
    assert "°C" in html
    assert "€" in html
    assert ".0 °C" not in html
    assert comparison["dwelling_id"] in html


def test_comfort_mode_and_room_status_handle_cold_symmetrically():
    assert get_comfort_mode({"season": "winter", "scenario_type": "heat_pump"}) == "cold"
    assert get_comfort_mode({"season": "", "scenario_type": "windows"}) == "mixed"
    assert get_room_status(
        {"temp_min_before": 15.5, "cold_dh_reduction_pct": 0},
        "cold",
    ) == ("Critique", "status-critical")
    assert get_room_status(
        {"temp_min_before": 18.0, "cold_dh_reduction_pct": 35},
        "cold",
    ) == ("Amélioré", "status-improved")
