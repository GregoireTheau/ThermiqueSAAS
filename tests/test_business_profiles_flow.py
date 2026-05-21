from thermal_saas.business_flow import (
    ensure_annual_weather,
    get_profile_questionnaire,
    run_profile_experience,
)
from thermal_saas.business_profiles import list_business_profiles


def _base_answers():
    return {
        "project_name": "Maison multi profil",
        "city": "Bordeaux",
        "postal_code": "33000",
        "dwelling_type": "house",
        "position_id": "single_storey_house",
        "period_id": "2001_2012_good_insulation",
        "heating_ref": "electric_radiator",
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
                        "mask_factor": 0.85,
                    },
                ],
            },
        ],
    }


def test_all_business_profiles_are_listed():
    profile_ids = {profile["id"] for profile in list_business_profiles()}

    assert profile_ids == {
        "heat_pump_seller",
        "reflective_roof_seller",
        "roof_insulation_seller",
        "solar_protection_seller",
        "window_seller",
    }


def test_solar_protection_profile_runs_only_summer_protection_experience():
    questionnaire = get_profile_questionnaire("solar_protection_seller")
    question_ids = _question_ids(questionnaire)

    assert "shutter_ref" in question_ids
    assert "current_energy_id" not in question_ids

    result = run_profile_experience("solar_protection_seller", _base_answers())

    assert result["adaptation_id"] == "solar_protection"
    assert [run["season"] for run in result["simulation_runs"]] == ["summer", "annual"]
    retrofit = result["simulation_runs"][0]["after_scenario"]["retrofit"]
    assert retrofit["shutter_overrides"]
    _assert_annual_run(result["simulation_runs"][-1])


def test_roof_insulation_profile_runs_roof_insulation_experiences():
    answers = _base_answers() | {
        "adaptation_id": "roof_insulation",
        "roof_insulation_id": "poor",
        "roof_color_id": "dark",
        "attic_ventilation_id": "limited",
    }

    result = run_profile_experience("roof_insulation_seller", answers)

    assert result["adaptation_id"] == "roof_insulation"
    assert [run["season"] for run in result["simulation_runs"]] == ["winter", "summer", "annual"]
    for run in result["simulation_runs"]:
        assert run["after_scenario"]["retrofit"]["surface_overrides"]
    _assert_annual_run(result["simulation_runs"][-1])


def test_roof_profile_can_run_reflective_roof_variant():
    answers = _base_answers()

    result = run_profile_experience("reflective_roof_seller", answers)

    assert result["adaptation_id"] == "reflective_roof"
    assert [run["season"] for run in result["simulation_runs"]] == ["summer", "summer", "annual"]
    for run in result["simulation_runs"]:
        overrides = run["after_scenario"]["retrofit"]["surface_overrides"]
        assert overrides[0]["albedo"] == 0.75
    _assert_annual_run(result["simulation_runs"][-1])


def test_window_profile_runs_window_replacement_experiences():
    answers = _base_answers() | {
        "window_ref": "double_glazing_old",
        "window_air_leakage_id": "leaky",
    }

    result = run_profile_experience("window_seller", answers)

    assert result["adaptation_id"] == "better_windows"
    assert [run["season"] for run in result["simulation_runs"]] == ["winter", "summer", "annual"]
    for run in result["simulation_runs"]:
        assert run["after_scenario"]["retrofit"]["window_overrides"]
    _assert_annual_run(result["simulation_runs"][-1])


def test_annual_weather_can_be_created_from_local_2023_raw(tmp_path):
    pd = __import__("pandas")
    weather_dir = tmp_path / "openmeteo"
    raw_dir = weather_dir / "raw"
    raw_dir.mkdir(parents=True)
    dataframe = pd.DataFrame(
        {
            "datetime": pd.date_range(
                "2023-01-01 00:00",
                periods=24,
                freq="h",
                tz="Europe/Paris",
            ),
            "temperature_2m": [10.0] * 24,
            "shortwave_radiation": [120.0] * 24,
            "direct_radiation": [80.0] * 24,
            "diffuse_radiation": [40.0] * 24,
            "city": ["Nantes"] * 24,
        },
    )
    dataframe.to_parquet(raw_dir / "nantes_2023.parquet", index=False)

    weather_path = ensure_annual_weather("Nantes", 2023, weather_dir)

    assert weather_path == weather_dir / "thermal" / "nantes_2023.weather.json"
    assert weather_path.exists()


def _question_ids(questionnaire):
    return {
        question["id"]
        for section in questionnaire["sections"]
        for question in section["questions"]
    }


def _assert_annual_run(run):
    assert run["season"] == "annual"
    assert run["role"] == "annual"
    assert run["before_scenario"]["experiment"]["weather_year"] == 2023
    assert run["before_scenario"]["experiment"]["weather_city"] == "Bordeaux"
    assert run["before_scenario"]["weather"]["weather_ref"] == (
        "data/weather/openmeteo/thermal/bordeaux_2023.weather.json"
    )
    assert len(run["before_scenario"]["weather"]["hourly"]) == 8760
    assert "<!doctype html>" in run["report_html"]
