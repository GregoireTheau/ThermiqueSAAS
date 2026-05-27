from thermal_saas.business_flow import (
    BusinessFlowError,
    build_customer,
    ensure_annual_weather,
    get_profile_questionnaire,
    run_profile_experience,
)
from thermal_saas.business_profiles import list_business_profiles, load_business_profile
from thermal_model import load_reference_catalog
from scripts import create_customer_experience as customer_experience


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


def test_all_business_profiles_ask_ventilation_and_airtightness():
    for profile in list_business_profiles():
        question_ids = _question_ids(get_profile_questionnaire(profile["id"]))

        assert "ventilation_id" in question_ids
        assert "airtightness_id" in question_ids


def test_roof_profiles_ask_roof_configuration_above_dwelling():
    expected_options = [
        ("attic", "Combles au-dessus du logement"),
        ("sloped_ceiling", "Toits rampants au-dessus du logement"),
        ("flat_roof", "Toit terrasse au-dessus du logement"),
    ]
    for profile_id in {"reflective_roof_seller", "roof_insulation_seller"}:
        question = _question_by_id(get_profile_questionnaire(profile_id), "attic_ventilation_id")

        assert question["label"] == "Configuration de toiture au-dessus du logement"
        assert [(option["id"], option["label"]) for option in question["options"]] == expected_options


def test_solar_protection_profile_runs_only_summer_protection_experience():
    questionnaire = get_profile_questionnaire("solar_protection_seller")
    question_ids = _question_ids(questionnaire)

    assert "has_cooling" in question_ids
    assert "shutter_ref" in question_ids
    assert "current_energy_id" not in question_ids

    result = run_profile_experience("solar_protection_seller", _base_answers())

    assert result["adaptation_id"] == "solar_protection"
    assert [run["season"] for run in result["simulation_runs"]] == ["summer", "annual"]
    retrofit = result["simulation_runs"][0]["after_scenario"]["retrofit"]
    assert retrofit["shutter_overrides"]
    _assert_annual_run(result["simulation_runs"][-1])


def test_has_cooling_answer_builds_cooling_system_only_when_enabled():
    catalog = load_reference_catalog()
    profile = load_business_profile("solar_protection_seller")

    customer_without_cooling = build_customer(_base_answers() | {"has_cooling": "false"}, profile, catalog)
    dwelling_without_cooling = customer_experience.build_dwelling(customer_without_cooling, catalog)
    assert dwelling_without_cooling["systems"]["cooling"] == []

    customer_with_cooling = build_customer(_base_answers() | {"has_cooling": "true"}, profile, catalog)
    dwelling_with_cooling = customer_experience.build_dwelling(customer_with_cooling, catalog)
    assert dwelling_with_cooling["systems"]["cooling"][0]["type"] == "air_conditioner"


def test_room_level_cooling_limits_served_rooms_and_day_night_setpoints():
    catalog = load_reference_catalog()
    profile = load_business_profile("reflective_roof_seller")
    answers = _base_answers() | {
        "has_cooling": "true",
        "cooling_setpoint_day_c": 27,
        "cooling_setpoint_night_c": 24,
        "include_annual_experiment": False,
        "rooms": [
            {
                "name": "Salon",
                "type": "living",
                "floor_area_m2": 30.0,
                "has_roof": True,
                "has_cooling": True,
                "facades": [{"orientation": "S", "window_area_m2": 4.0, "wall_length_m": 6.0}],
            },
            {
                "name": "Chambre",
                "type": "bedroom",
                "floor_area_m2": 12.0,
                "has_roof": True,
                "has_cooling": False,
                "facades": [{"orientation": "E", "window_area_m2": 1.5, "wall_length_m": 3.5}],
            },
        ],
    }

    customer = build_customer(answers, profile, catalog)
    dwelling = customer_experience.build_dwelling(customer, catalog)
    result = run_profile_experience("reflective_roof_seller", answers, include_report_html=False)
    summer = next(run for run in result["simulation_runs"] if run["season"] == "summer")

    assert dwelling["systems"]["cooling"][0]["served_rooms"] == ["salon"]
    assert customer["setpoints"]["cooling_c"] == 27
    assert summer["before_scenario"]["controls"]["cooling_setpoint_schedule"] == {
        "day_c": 27.0,
        "night_c": 24.0,
        "day_start_hour": 7,
        "night_start_hour": 22,
    }


def test_heat_pump_profile_uses_existing_heating_before_retrofit():
    catalog = load_reference_catalog()
    profile = load_business_profile("heat_pump_seller")
    answers = {
        key: value
        for key, value in _base_answers().items()
        if key != "heating_ref"
    } | {
        "airtightness_id": "standard",
        "ventilation_id": "simple_flow",
        "current_energy_id": "electricity",
        "heat_emitters_id": "electric_radiators",
    }

    customer = build_customer(answers, profile, catalog)
    dwelling = customer_experience.build_dwelling(customer, catalog)
    heating = dwelling["systems"]["heating"][0]

    assert heating["system_ref"] == "electric_radiator"
    assert heating["performance_ref"]["cop"] == 1.0

    result = run_profile_experience("heat_pump_seller", answers)
    retrofit = result["simulation_runs"][0]["after_scenario"]["retrofit"]["system_overrides"][0]

    assert retrofit["system_ref"] == "air_air_heat_pump_standard"
    assert retrofit["performance_ref"]["cop"] >= 2.5


def test_heat_pump_profile_maps_existing_energy_to_initial_heating():
    catalog = load_reference_catalog()
    profile = load_business_profile("heat_pump_seller")
    base_answers = {
        key: value
        for key, value in _base_answers().items()
        if key != "heating_ref"
    } | {
        "airtightness_id": "standard",
        "ventilation_id": "simple_flow",
        "heat_emitters_id": "water_radiators",
    }

    expected_refs = {
        "gas": "gas_boiler_standard",
        "fuel_oil": "fuel_oil_boiler_standard",
        "wood": "wood_stove_standard",
    }
    for energy_id, expected_ref in expected_refs.items():
        customer = build_customer(base_answers | {"current_energy_id": energy_id}, profile, catalog)

        assert customer["heating_ref"] == expected_ref


def test_roof_insulation_profile_runs_roof_insulation_experiences():
    answers = _base_answers() | {
        "adaptation_id": "roof_insulation",
        "roof_insulation_id": "poor",
        "roof_color_id": "dark",
        "attic_ventilation_id": "flat_roof",
    }

    result = run_profile_experience("roof_insulation_seller", answers)

    assert result["adaptation_id"] == "roof_insulation"
    roof = next(surface for surface in result["dwelling"]["rooms"][0]["surfaces"] if surface["type"] == "roof")
    assert roof["solar_to_room_factor"] == 0.07
    assert [run["season"] for run in result["simulation_runs"]] == ["winter", "summer", "annual"]
    for run in result["simulation_runs"]:
        assert run["after_scenario"]["retrofit"]["surface_overrides"]
    _assert_annual_run(result["simulation_runs"][-1])


def test_roof_profile_can_run_reflective_roof_variant():
    answers = _base_answers()

    result = run_profile_experience("reflective_roof_seller", answers)

    assert result["adaptation_id"] == "reflective_roof"
    assert [run["season"] for run in result["simulation_runs"]] == ["summer", "summer"]
    assert [run["role"] for run in result["simulation_runs"]] == ["primary", "secondary"]
    assert len(result["simulation_runs"][0]["before_scenario"]["weather"]["hourly"]) == 124 * 24
    assert len(result["simulation_runs"][1]["before_scenario"]["weather"]["hourly"]) == 5 * 24
    for run in result["simulation_runs"]:
        overrides = run["after_scenario"]["retrofit"]["surface_overrides"]
        assert overrides[0]["albedo"] == 0.75


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


def test_business_flow_rejects_window_larger_than_facade():
    answers = _base_answers()
    answers["rooms"][0]["facades"][0] = {
        "orientation": "S",
        "window_area_m2": 20.0,
        "wall_length_m": 3.0,
    }

    try:
        run_profile_experience("window_seller", answers)
    except BusinessFlowError as exc:
        assert "window_area_m2" in str(exc)
        assert "surface de façade" in str(exc)
    else:
        raise AssertionError("run_profile_experience accepted a window larger than facade")


def test_business_flow_rejects_empty_exterior_facades_and_invalid_orientation():
    answers = _base_answers()
    answers["rooms"][0]["facades"] = []

    try:
        run_profile_experience("window_seller", answers)
    except BusinessFlowError as exc:
        assert "facades" in str(exc)
    else:
        raise AssertionError("run_profile_experience accepted an exterior room without facade")

    answers = _base_answers()
    answers["rooms"][0]["facades"][0]["orientation"] = "BAD"

    try:
        run_profile_experience("window_seller", answers)
    except BusinessFlowError as exc:
        assert "orientation" in str(exc)
    else:
        raise AssertionError("run_profile_experience accepted an invalid orientation")


def test_business_flow_rejects_absurd_height_setpoints_and_incompatible_adaptation():
    answers = _base_answers()
    answers["rooms"][0]["height_m"] = 0.5

    try:
        run_profile_experience("window_seller", answers)
    except BusinessFlowError as exc:
        assert "height_m" in str(exc)
    else:
        raise AssertionError("run_profile_experience accepted absurd room height")

    try:
        run_profile_experience(
            "window_seller",
            _base_answers() | {"heating_setpoint_c": 19.0, "cooling_setpoint_c": 15.0},
        )
    except BusinessFlowError as exc:
        assert "chauffage" in str(exc)
        assert "climatisation" in str(exc)
    else:
        raise AssertionError("run_profile_experience accepted inverted setpoints")

    try:
        run_profile_experience(
            "window_seller",
            _base_answers() | {"adaptation_id": "heat_pump"},
        )
    except BusinessFlowError as exc:
        assert "compatible" in str(exc)
        assert "window_seller" in str(exc)
    else:
        raise AssertionError("run_profile_experience accepted incompatible adaptation")


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


def _question_by_id(questionnaire, question_id):
    for section in questionnaire["sections"]:
        for question in section["questions"]:
            if question["id"] == question_id:
                return question
    raise AssertionError(f"Question {question_id} not found")


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
