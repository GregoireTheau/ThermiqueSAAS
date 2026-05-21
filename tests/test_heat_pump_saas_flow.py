from thermal_saas.heat_pump_flow import get_heat_pump_questionnaire, run_heat_pump_experience


def _answers():
    return {
        "project_name": "Maison PAC test",
        "city": "Bordeaux",
        "postal_code": "33000",
        "dwelling_type": "house",
        "position_id": "single_storey_house",
        "period_id": "2001_2012_good_insulation",
        "current_energy_id": "electricity",
        "heating_ref": "electric_radiator",
        "heat_emitters_id": "electric_radiators",
        "heating_setpoint_c": 19.0,
        "rooms": [
            {
                "name": "Salon",
                "type": "living",
                "floor_area_m2": 30.0,
                "facades": [
                    {
                        "orientation": "S",
                        "window_area_m2": 4.0,
                        "wall_length_m": 6.0,
                    },
                ],
            },
        ],
    }


def test_heat_pump_questionnaire_only_exposes_heat_pump_adaptation():
    questionnaire = get_heat_pump_questionnaire()

    question_ids = [
        question["id"]
        for section in questionnaire["sections"]
        for question in section["questions"]
    ]

    assert "current_energy_id" in question_ids
    assert "heat_emitters_id" in question_ids
    assert "rooms" in question_ids


def test_heat_pump_flow_runs_winter_experience_and_returns_report_html():
    result = run_heat_pump_experience(_answers())

    assert result["business_profile_id"] == "heat_pump_seller"
    assert result["adaptation_id"] == "heat_pump"
    assert result["dwelling"]["dwelling_id"] == "maison_pac_test"
    assert [run["season"] for run in result["simulation_runs"]] == ["winter", "annual"]

    run = result["simulation_runs"][0]
    assert run["before_scenario"]["experiment"]["adaptation_id"] == "heat_pump"
    assert run["after_scenario"]["retrofit"]["system_overrides"]
    assert run["comparison"]["experiment"]["adaptation_id"] == "heat_pump"
    assert "<!doctype html>" in run["report_html"]

    annual_run = result["simulation_runs"][1]
    assert annual_run["role"] == "annual"
    assert annual_run["before_scenario"]["experiment"]["weather_year"] == 2023
    assert annual_run["before_scenario"]["weather"]["weather_ref"] == (
        "data/weather/openmeteo/thermal/bordeaux_2023.weather.json"
    )
    assert "<!doctype html>" in annual_run["report_html"]
