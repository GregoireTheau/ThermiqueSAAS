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

    assert report["report_schema_version"] == "0.5"
    assert report["source"]["dwelling_id"] == comparison["dwelling_id"]
    assert report["experiment"]["duration_hours"] == 24
    assert report["experiment"]["duration_days"] == 1
    assert report["experiment"]["weather_source"] == "synthetic"
    assert report["experiment"]["title"].startswith("Simulation")
    assert "experiment" in report["narrative"]["context"].lower()
    assert "after scenario applies" not in report["narrative"]["tested_change"]
    assert "In the model" not in report["narrative"]["tested_change"]
    assert "temperature" in report["narrative"]["conclusion"]
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
    assert report["headline"]["final_energy"]["unit"] == "kWh_final"
    assert report["headline"]["cost"]["before"] == round(
        comparison["before"]["totals"]["energy_cost_eur"],
        2,
    )
    assert 1 <= len(report["primary_kpis"]) <= 3


def test_report_model_excludes_hourly_traces():
    comparison = _comparison(
        "data/examples/scenario_heatwave_before.json",
        "data/examples/scenario_heatwave.json",
    )

    report = build_report_model(comparison)

    assert "hourly" not in report
    assert "before" not in report
    assert "after" not in report
    assert report["methodology"]["reported_values"].startswith("Calculated from")
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
    assert "Simulation reflective roof - summer comfort" in html
    assert "Executive Summary" in html
    assert "Scenario</div>Thermal simulation during a heatwave episode" in html
    assert "roofing" not in html
    assert "Scenarios" not in html
    assert "Context" in html
    assert "Temperature Charts" in html
    assert "Main Results" in html
    assert "Thermal demand" in html
    assert "Total final energy" in html
    assert "Reading the Results" in html
    assert "Room Details" in html
    assert "Report generated automatically" in html
    assert "Simulation limits" not in html
    assert "24 h" in html
    assert "°C" in html
    assert '<svg class="chart" viewBox="0 0 1040 370"' in html
    assert 'y="12.0" width="746" height="26"' in html
    assert 'y1="70.0"' in html
    assert "€" in html
    assert ".00 °C" not in html
    assert comparison["dwelling_id"] in html


def test_report_context_only_mentions_cooling_setpoints_when_cooling_exists():
    comparison = _comparison(
        "data/examples/scenario_heatwave_before.json",
        "data/examples/scenario_heatwave.json",
    )
    comparison["experiment"]["setpoints"] = {
        "heating_c": 19.0,
        "cooling_c": 27.0,
        "cooling_day_c": 27.0,
        "cooling_night_c": 24.0,
    }

    comparison["experiment"]["has_cooling"] = False
    no_cooling_html = render_report_html(build_report_model(comparison))
    assert "Setpoints" in no_cooling_html
    assert "Heating 19 °C" in no_cooling_html
    assert "cooling 27 °C during the day, 24 °C at night" not in no_cooling_html

    comparison["experiment"]["has_cooling"] = True
    cooling_html = render_report_html(build_report_model(comparison))
    assert "Heating 19 °C, cooling 27 °C during the day, 24 °C at night" in cooling_html


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
    ) == ("Critical", "status-critical")
    assert get_room_status(
        {"temp_min_before": 18.0, "cold_dh_reduction_pct": 35},
        "cold",
    ) == ("Improved", "status-improved")


def test_render_report_html_hides_zero_rows():
    comparison = _comparison(
        "data/examples/scenario_heatwave_before.json",
        "data/examples/scenario_heatwave.json",
    )
    report = build_report_model(comparison)

    html = render_report_html(report)

    assert "Heating demand" not in html
    assert "Cumulative discomfort hours (cold)" not in html


def test_report_kpis_are_adapted_to_business_scenario_type():
    heat_pump_result = run_profile_experience(
        "heat_pump_seller",
        {
            "project_name": "Maison PAC",
            "city": "Bordeaux",
            "postal_code": "33000",
            "dwelling_type": "house",
            "position_id": "single_storey_house",
            "period_id": "1975_1988_basic_insulation",
            "heating_ref": "electric_radiator",
            "current_energy_id": "electricity",
            "heat_emitters_id": "electric_radiators",
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
    heat_pump_report = heat_pump_result["simulation_runs"][0]["report"]

    assert heat_pump_report["experiment"]["scenario_type"] == "heat_pump"
    assert [kpi["label"] for kpi in heat_pump_report["primary_kpis"]] == [
        "Final energy saved",
        "Cost saved",
        "CO₂ avoided",
    ]
    assert "The heat pump provides the same heat demand" in heat_pump_report["narrative"]["conclusion"]


def test_business_report_presentation_is_profile_specific():
    answers = {
        "project_name": "Maison présentation",
        "city": "Bordeaux",
        "postal_code": "33000",
        "dwelling_type": "house",
        "position_id": "single_storey_house",
        "period_id": "1975_1988_basic_insulation",
        "heating_ref": "electric_radiator",
        "current_energy_id": "electricity",
        "heat_emitters_id": "electric_radiators",
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
                        "window_area_m2": 5.0,
                        "wall_length_m": 6.0,
                    },
                ],
            },
        ],
    }

    heat_pump = run_profile_experience(
        "heat_pump_seller",
        answers,
        include_report_html=False,
    )["simulation_runs"][-1]["report"]
    assert [kpi["label"] for kpi in heat_pump["primary_kpis"]] == [
        "Final energy saved",
        "Cost saved",
        "CO₂ avoided",
    ]
    assert "Hot discomfort avoided" not in [
        kpi["label"] for kpi in heat_pump["primary_kpis"]
    ]

    roof = run_profile_experience(
        "roof_insulation_seller",
        answers,
        include_report_html=True,
    )["simulation_runs"][-1]
    assert [kpi["label"] for kpi in roof["report"]["primary_kpis"]] == [
        "Heating demand reduced",
        "Final heating energy",
        "Cost saved",
    ]
    assert "Summer impact" in roof["report_html"]

    reflective_result = run_profile_experience(
        "reflective_roof_seller",
        answers,
        include_report_html=True,
    )
    reflective_long_summer = reflective_result["simulation_runs"][0]["report"]
    long_profile = reflective_long_summer["temperature_profiles"]["rooms"][0]
    assert long_profile["x_axis"]["type"] == "season_months"
    assert long_profile["aggregation"] == "daily_max"
    assert long_profile["points"][0]["before_temperature_c"] == long_profile["points"][0]["before_max_temperature_c"]
    assert "before_average_temperature_c" in long_profile["points"][0]
    assert long_profile["x_axis"]["labels"] == [
        ("Jun", 0),
        ("Jul", 1272),
        ("Sep", 2544),
    ]
    assert ">h0<" not in reflective_result["simulation_runs"][0]["report_html"]
    assert ">Jun<" in reflective_result["simulation_runs"][0]["report_html"]
    assert ">May<" not in reflective_result["simulation_runs"][0]["report_html"]
    assert (
        "Scenario</div>Thermal simulation from June to September before and after "
        "adding a reflective roof coating."
        in reflective_result["simulation_runs"][0]["report_html"]
    )
    assert (
        "<tr><td>Tested change</td><td>Add a reflective roof coating against heat</td></tr>"
        in reflective_result["simulation_runs"][0]["report_html"]
    )
    assert "In the model, this corresponds" not in reflective_result["simulation_runs"][0]["report_html"]
    assert "roofing" not in reflective_result["simulation_runs"][0]["report_html"]
    assert "maximum temperature for each day" in reflective_result["simulation_runs"][0]["report_html"]
    assert "Indoor avg/day" in reflective_result["simulation_runs"][0]["report_html"]
    assert (
        reflective_result["simulation_runs"][1]["report"]["temperature_profiles"]["rooms"][0]["x_axis"]["type"]
        == "hours"
    )
    assert (
        reflective_result["simulation_runs"][1]["report"]["temperature_profiles"]["rooms"][0]["aggregation"]
        == "hourly"
    )
    assert len(reflective_result["simulation_runs"][1]["before_scenario"]["weather"]["hourly"]) == 120

    reflective = reflective_result["simulation_runs"][1]
    assert [kpi["label"] for kpi in reflective["report"]["primary_kpis"]] == [
        "Hot discomfort avoided",
        "Maximum temperature reduced",
    ]
    assert "Final energy saved" not in [
        kpi["label"] for kpi in reflective["report"]["primary_kpis"]
    ]
    assert "real heatwave zoom" in reflective["report_html"]
    assert "simulated temperature hour by hour" in reflective["report_html"]

    windows_result = run_profile_experience(
        "window_seller",
        answers,
        include_report_html=True,
    )
    windows_summer = windows_result["simulation_runs"][1]
    assert (
        "High-performance glazing reduces direct solar gains in summer.<br>"
        "The effect on comfort depends on orientation"
        in windows_summer["report_html"]
    )

    windows = windows_result["simulation_runs"][-1]
    assert [kpi["label"] for kpi in windows["report"]["primary_kpis"]] == [
        "Final energy saved",
        "Cost saved",
        "Hot discomfort avoided",
    ]
    assert "Double effect" in windows["report_html"]
    assert (
        "Final energy = billed energy after system efficiency or COP.<br>"
        "In the table, variation is calculated as after - before"
        in windows["report_html"]
    )


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
    assert profile["x_axis"]["labels"][1] == ("Feb", 744)
    assert profile["x_axis"]["zones"][0] == {
        "label": "Summer",
        "start_hour": 3624,
        "end_hour": 5832,
    }

    html = render_report_html(annual_report)

    assert "Curves show daily average" in html
    assert "<polygon" in html
    assert "<title>" in html
