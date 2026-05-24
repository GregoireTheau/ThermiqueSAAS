from thermal_saas.business_flow import run_profile_experience


def _base_answers():
    return {
        "project_name": "Regression metier",
        "city": "Bordeaux",
        "postal_code": "33000",
        "dwelling_type": "house",
        "position_id": "single_storey_house",
        "period_id": "1975_1988_basic_insulation",
        "heating_ref": "electric_radiator",
        "window_ref": "double_glazing_old",
        "roof_insulation_id": "poor",
        "roof_color_id": "dark",
        "attic_ventilation_id": "limited",
        "include_annual_experiment": False,
        "rooms": [
            {
                "name": "Salon",
                "type": "living",
                "floor_area_m2": 35.0,
                "has_roof": True,
                "facades": [
                    {
                        "orientation": "S",
                        "window_area_m2": 7.0,
                        "wall_length_m": 7.0,
                        "mask_factor": 0.9,
                    },
                ],
            },
        ],
    }


def _primary_run(result):
    return next(run for run in result["simulation_runs"] if run["role"] == "primary")


def test_heat_pump_commercial_path_reduces_winter_electricity():
    answers = {
        key: value
        for key, value in _base_answers().items()
        if key != "heating_ref"
    } | {
        "current_energy_id": "electricity",
        "heat_emitters_id": "electric_radiators",
    }

    run = _primary_run(
        run_profile_experience(
            "heat_pump_seller",
            answers,
            include_report_html=False,
        ),
    )

    assert run["season"] == "winter"
    assert (
        run["comparison"]["after"]["totals"]["heating_electric_kwh"]
        < run["comparison"]["before"]["totals"]["heating_electric_kwh"]
    )
    assert run["comparison"]["summary"]["main_gain_driver"]["key"] == "system_efficiency"


def test_window_commercial_path_reduces_winter_heating_needs():
    run = _primary_run(
        run_profile_experience(
            "window_seller",
            _base_answers() | {"window_air_leakage_id": "leaky"},
            include_report_html=False,
        ),
    )

    assert run["season"] == "winter"
    assert (
        run["comparison"]["after"]["totals"]["heating_thermal_kwh"]
        < run["comparison"]["before"]["totals"]["heating_thermal_kwh"]
    )


def test_roof_insulation_commercial_path_reduces_winter_heating_needs():
    run = _primary_run(
        run_profile_experience(
            "roof_insulation_seller",
            _base_answers() | {"adaptation_id": "roof_insulation"},
            include_report_html=False,
        ),
    )

    assert run["season"] == "winter"
    assert (
        run["comparison"]["after"]["totals"]["heating_thermal_kwh"]
        < run["comparison"]["before"]["totals"]["heating_thermal_kwh"]
    )


def test_solar_protection_commercial_path_reduces_summer_overheating():
    run = _primary_run(
        run_profile_experience(
            "solar_protection_seller",
            _base_answers() | {"shutter_ref": "none"},
            include_report_html=False,
        ),
    )
    room_id = next(iter(run["comparison"]["before"]["rooms_summary"]))
    room_summary_before = run["comparison"]["before"]["rooms_summary"][room_id]
    room_summary_after = run["comparison"]["after"]["rooms_summary"][room_id]

    assert run["season"] == "summer"
    assert (
        room_summary_after["hot_degree_hours"]
        < room_summary_before["hot_degree_hours"]
    )
    assert (
        room_summary_after["max_temperature_c"]
        < room_summary_before["max_temperature_c"]
    )
