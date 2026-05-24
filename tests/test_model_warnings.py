from copy import deepcopy

from thermal_model import collect_model_warnings, simulate_1r1c


def _dwelling(
    *,
    window_area_m2=4.0,
    infiltration_ach=0.2,
    mechanical_ach=0.2,
    heating_power_w=2000.0,
):
    return {
        "schema_version": "0.1",
        "dwelling_id": "warning_case",
        "metadata": {
            "name": "Warning case",
            "description": "Synthetic warning case.",
            "created_by": "tests",
        },
        "location": {
            "country": "FR",
            "postal_code": "33000",
            "city": "Reference",
            "climate_zone_id": "FR_H2c",
            "ground_albedo": 0.2,
        },
        "defaults": {
            "initial_temperature_c": 20.0,
            "equivalent_capacity_j_m2k": 160000,
            "thermal_bridge_factor": 0.1,
            "internal_gain_w_m2": 0.0,
            "ach_h": infiltration_ach + mechanical_ach,
        },
        "rooms": [
            {
                "id": "main_room",
                "name": "Main room",
                "type": "living",
                "floor_area_m2": 20.0,
                "height_m": 2.5,
                "volume_m3": 50.0,
                "initial_temperature_c": 20.0,
                "equivalent_capacity_j_m2k": 160000,
                "internal_gain_w_m2": 0.0,
                "ventilation": {
                    "mode": "ach",
                    "ach_h": infiltration_ach + mechanical_ach,
                    "infiltration_ach": infiltration_ach,
                    "mechanical_ach": mechanical_ach,
                    "recovery_efficiency": 0.0,
                },
                "surfaces": [
                    {
                        "id": "south_wall",
                        "type": "external_wall",
                        "boundary": "exterior",
                        "area_m2": 20.0,
                        "u_value_w_m2k": 1.8,
                        "azimuth_deg": 180,
                        "tilt_deg": 90,
                        "albedo": 0.35,
                        "solar_to_room_factor": 0.08,
                        "mask_factor": 1.0,
                    },
                    {
                        "id": "roof",
                        "type": "roof",
                        "boundary": "exterior",
                        "area_m2": 20.0,
                        "u_value_w_m2k": 1.5,
                        "azimuth_deg": 180,
                        "tilt_deg": 25,
                        "albedo": 0.2,
                        "solar_to_room_factor": 0.08,
                        "mask_factor": 1.0,
                    },
                ],
                "windows": [
                    {
                        "id": "south_window",
                        "area_m2": window_area_m2,
                        "u_value_w_m2k": 1.6,
                        "g_value": 0.55,
                        "azimuth_deg": 180,
                        "tilt_deg": 90,
                        "mask_factor": 1.0,
                    }
                ],
            }
        ],
        "thermal_links": [],
        "systems": {
            "heating": [
                {
                    "id": "heating_system",
                    "type": "electric_radiator",
                    "served_rooms": ["main_room"],
                    "max_power_w": heating_power_w,
                    "performance_ref": {"mode": "constant", "cop": 1.0},
                }
            ],
            "cooling": [],
            "ventilation": {
                "type": "other",
                "default_ach_h": infiltration_ach + mechanical_ach,
                "infiltration_ach": infiltration_ach,
                "mechanical_ach": mechanical_ach,
                "recovery_efficiency": 0.0,
            },
        },
    }


def _scenario(*, temperatures, heating_c=19.0, solar_south=0.0, solar_roof=0.0):
    return {
        "schema_version": "0.1",
        "scenario_id": "warning_scenario",
        "dwelling_id": "warning_case",
        "timestep_h": 1.0,
        "initial_temperatures_c": {"main_room": 26.0},
        "setpoints": {"heating_c": heating_c, "cooling_c": 80.0},
        "controls": {
            "shutters": {"default_opening_ratio": 1.0},
            "natural_ventilation": {"default_ach": 0.0},
        },
        "weather": {
            "source": "synthetic_warning",
            "hourly": [
                {
                    "hour": hour,
                    "outdoor_temperature_c": temperature,
                    "solar_irradiance_w_m2": {
                        "north": 0.0,
                        "east": 0.0,
                        "south": solar_south,
                        "west": 0.0,
                        "roof": solar_roof,
                    },
                }
                for hour, temperature in enumerate(temperatures)
            ],
        },
        "energy_prices": {"electricity_eur_kwh": 0.25},
        "co2_factors": {"electricity_kg_kwh": 0.06},
    }


def test_model_warnings_detect_unrealistic_window_area():
    warnings = collect_model_warnings(_dwelling(window_area_m2=16.0))

    assert _warning_codes(warnings) == {"window_area_unusually_high"}


def test_model_warnings_detect_extreme_ventilation_rate():
    warnings = collect_model_warnings(_dwelling(infiltration_ach=3.2, mechanical_ach=0.4))

    assert "ventilation_ach_unusually_high" in _warning_codes(warnings)


def test_model_warnings_detect_undersized_heating_against_winter_weather():
    warnings = collect_model_warnings(
        _dwelling(heating_power_w=200.0),
        _scenario(temperatures=[-8.0] * 6, heating_c=19.0),
    )

    assert "heating_power_may_be_insufficient" in _warning_codes(warnings)


def test_model_warnings_detect_unusually_high_simulated_temperature():
    dwelling = _dwelling(window_area_m2=16.0, heating_power_w=2000.0)
    scenario = _scenario(
        temperatures=[38.0] * 10,
        heating_c=0.0,
        solar_south=900.0,
        solar_roof=900.0,
    )
    no_heating_dwelling = deepcopy(dwelling)
    no_heating_dwelling["systems"]["heating"] = []
    results = simulate_1r1c(
        no_heating_dwelling,
        scenario,
        air_density_kg_m3=1.2,
        air_heat_capacity_j_kgk=1005.0,
    )

    warnings = collect_model_warnings(no_heating_dwelling, scenario, results)

    assert "room_temperature_unusually_high" in _warning_codes(warnings)


def test_business_flow_exposes_model_warnings_without_blocking_runs():
    from thermal_saas.business_flow import run_profile_experience

    result = run_profile_experience(
        "solar_protection_seller",
        {
            "project_name": "Warnings exposed",
            "city": "Bordeaux",
            "postal_code": "33000",
            "dwelling_type": "house",
            "position_id": "single_storey_house",
            "period_id": "1975_1988_basic_insulation",
            "include_annual_experiment": False,
            "rooms": [
                {
                    "name": "Salon",
                    "type": "living",
                    "floor_area_m2": 20.0,
                    "has_roof": True,
                    "facades": [
                        {
                            "orientation": "S",
                            "window_area_m2": 16.0,
                            "wall_length_m": 7.0,
                            "mask_factor": 1.0,
                        },
                    ],
                }
            ],
        },
        include_report_html=False,
    )

    run = result["simulation_runs"][0]
    assert "model_warnings" in run
    assert "window_area_unusually_high" in _warning_codes(
        run["model_warnings"]["before"],
    )


def _warning_codes(warnings):
    return {warning["code"] for warning in warnings}
