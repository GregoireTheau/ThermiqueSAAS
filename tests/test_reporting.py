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
from thermal_saas.business_flow import run_profile_experience


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
    assert ".00 °C" not in html
    assert comparison["dwelling_id"] in html


def test_comfort_mode_and_room_status_handle_cold_symmetrically():
    assert get_comfort_mode({"season": "winter", "scenario_type": "heat_pump"}) == "cold"
    assert get_comfort_mode(
        {
            "season": "winter",
            "scenario_type": "heat_pump",
            "total_hot_discomfort_before": 12,
            "total_cold_discomfort_before": 0,
        },
    ) == "hot"
    assert get_comfort_mode(
        {
            "season": "summer",
            "scenario_type": "solar_protection",
            "total_hot_discomfort_before": 0,
            "total_cold_discomfort_before": 8,
        },
    ) == "cold"
    assert get_room_status(
        {"temp_min_before": 15.5, "cold_dh_reduction_pct": 0},
        "cold",
    ) == ("Critique", "status-critical")
    assert get_room_status(
        {"temp_min_before": 18.0, "cold_dh_reduction_pct": 35},
        "cold",
    ) == ("Amélioré", "status-improved")


def test_render_report_html_hides_zero_rows():
    comparison = _comparison(
        "data/examples/scenario_heatwave_before.json",
        "data/examples/scenario_heatwave.json",
    )
    report = build_report_model(comparison)

    html = render_report_html(report)

    assert "Chauffage thermique" not in html
    assert "Heures d&#x27;inconfort cumulées (froid)" not in html


def test_annual_temperature_profile_uses_daily_points_and_month_labels():
    result = run_profile_experience(
        "window_seller",
        {
            "project_name": "Maison annuelle",
            "city": "Bordeaux",
            "postal_code": "33000",
            "dwelling_type": "house",
            "position_id": "single_storey_house",
            "period_id": "2001_2012_good_insulation",
            "window_ref": "double_glazing_old",
            "window_air_leakage_id": "leaky",
            "rooms": [
                {
                    "name": "Salon",
                    "type": "living",
                    "floor_area_m2": 30.0,
                    "has_roof": True,
                    "facades": [
                        {
                            "orientation": "S",
                            "window_area_m2": 4.0,
                            "wall_length_m": 6.0,
                        },
                    ],
                },
            ],
        },
        include_report_html=False,
    )
    annual_report = result["simulation_runs"][-1]["report"]
    profile = annual_report["temperature_profiles"]["rooms"][0]
    room = annual_report["rooms"][0]

    assert result["simulation_runs"][-1]["season"] == "annual"
    assert len(profile["points"]) == 365
    assert "before_min_temperature_c" in profile["points"][0]
    assert profile["summary"]["temp_max_before"] > max(
        point["before_temperature_c"]
        for point in profile["points"]
    )
    assert profile["critical_markers"]
    assert profile["critical_markers"][0]["type"] == "hot"
    assert room["thermal_balance_deltas"]["solar_gain"]["delta"] != 0
    assert room["thermal_balance_deltas"]["transmission_exchange"]["delta"] != 0
    assert profile["x_axis"]["labels"][1] == ("Fév", 744)
    assert profile["x_axis"]["zones"][0] == {
        "label": "Été",
        "start_hour": 3624,
        "end_hour": 5832,
    }

    html = render_report_html(annual_report)

    assert "La zone ombrée représente l&#x27;amplitude min/max journalière." in html
    assert "<polygon" in html
    assert "<title>" in html
