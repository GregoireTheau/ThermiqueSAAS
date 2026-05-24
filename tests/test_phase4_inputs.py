from thermal_model import (
    compute_room_static_losses,
    load_reference_catalog,
    simulate_1r1c,
    validate_dwelling,
)


def _single_room_dwelling(heating_system):
    return {
        "schema_version": "0.1",
        "dwelling_id": "phase4_input_case",
        "metadata": {
            "name": "Phase 4 input case",
            "description": "Minimal dwelling for input data improvements.",
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
            "initial_temperature_c": 19.0,
            "equivalent_capacity_j_m2k": 160000,
            "thermal_bridge_factor": 0.0,
            "internal_gain_w_m2": 0.0,
            "ach_h": 0.0,
        },
        "rooms": [
            {
                "id": "main_room",
                "name": "Main room",
                "type": "living",
                "floor_area_m2": 30.0,
                "height_m": 2.5,
                "volume_m3": 75.0,
                "initial_temperature_c": 19.0,
                "equivalent_capacity_j_m2k": 160000,
                "internal_gain_w_m2": 0.0,
                "ventilation": {
                    "mode": "ach",
                    "ach_h": 0.0,
                    "infiltration_ach": 0.0,
                    "mechanical_ach": 0.0,
                    "recovery_efficiency": 0.0,
                },
                "surfaces": [
                    {
                        "id": "wall",
                        "type": "external_wall",
                        "boundary": "exterior",
                        "area_m2": 30.0,
                        "u_value_w_m2k": 1.0,
                    }
                ],
                "windows": [
                    {
                        "id": "window",
                        "area_m2": 6.0,
                        "u_value_w_m2k": 2.0,
                        "g_value": 0.5,
                        "azimuth_deg": 180,
                        "tilt_deg": 90,
                        "shutter": {
                            "type": "roller_shutter",
                            "solar_factor_closed": 0.15,
                            "solar_factor_open": 1.0,
                            "u_factor_closed": 0.7,
                        },
                    }
                ],
            }
        ],
        "thermal_links": [],
        "systems": {
            "heating": [heating_system],
            "cooling": [],
            "ventilation": {"type": "none", "default_ach_h": 0.0},
        },
    }


def _winter_scenario(outdoor_temperature_c):
    return {
        "schema_version": "0.1",
        "scenario_id": "phase4_winter",
        "dwelling_id": "phase4_input_case",
        "timestep_h": 1.0,
        "initial_temperatures_c": {"main_room": 19.0},
        "setpoints": {"heating_c": 19.0, "cooling_c": 80.0},
        "controls": {
            "shutters": {"default_opening_ratio": 1.0},
            "natural_ventilation": {"default_ach": 0.0},
        },
        "weather": {
            "source": "synthetic_phase4",
            "hourly": [
                {"hour": hour, "outdoor_temperature_c": outdoor_temperature_c}
                for hour in range(4)
            ],
        },
        "energy_prices": {
            "electricity_eur_kwh": 0.25,
            "gas_eur_kwh": 0.11,
        },
        "co2_factors": {
            "electricity_kg_kwh": 0.06,
            "gas_kg_kwh": 0.227,
        },
    }


def test_phase4_references_include_new_input_options():
    catalog = load_reference_catalog()

    assert "simple_flow_hygro_b" in catalog["ventilation"]
    assert "double_flow_high_efficiency" in catalog["ventilation"]
    assert "roller_shutter_insulating" in catalog["shutters"]
    assert "fixed_south_overhang" in catalog["shutters"]
    assert "isolation_levels" in catalog


def test_closed_shutters_reduce_window_transmission_losses():
    dwelling = _single_room_dwelling(_electric_heater())
    room = dwelling["rooms"][0]

    open_losses = compute_room_static_losses(
        dwelling,
        room,
        indoor_temperature_c=20.0,
        outdoor_temperature_c=0.0,
        air_density_kg_m3=1.2,
        air_heat_capacity_j_kgk=1005.0,
        shutter_opening_ratio=1.0,
    )
    closed_losses = compute_room_static_losses(
        dwelling,
        room,
        indoor_temperature_c=20.0,
        outdoor_temperature_c=0.0,
        air_density_kg_m3=1.2,
        air_heat_capacity_j_kgk=1005.0,
        shutter_opening_ratio=0.0,
    )

    assert closed_losses["window_ua_w_k"] < open_losses["window_ua_w_k"]
    assert closed_losses["total_loss_w"] < open_losses["total_loss_w"]


def test_heating_final_energy_is_split_by_energy_vector():
    dwelling = _single_room_dwelling(_gas_boiler())
    validate_dwelling(dwelling)

    results = simulate_1r1c(dwelling, _winter_scenario(-5.0), 1.2, 1005.0)

    assert results["totals"]["heating_electric_kwh"] == 0.0
    assert results["totals"]["heating_final_kwh_by_energy"]["gas"] > 0.0
    assert results["totals"]["final_energy_kwh_by_energy"]["gas"] > 0.0
    assert results["totals"]["energy_cost_eur"] > 0.0


def test_heat_pump_cop_curve_uses_outdoor_temperature():
    cold_dwelling = _single_room_dwelling(_heat_pump())
    mild_dwelling = _single_room_dwelling(_heat_pump())
    validate_dwelling(cold_dwelling)
    validate_dwelling(mild_dwelling)

    cold_results = simulate_1r1c(cold_dwelling, _winter_scenario(-7.0), 1.2, 1005.0)
    mild_results = simulate_1r1c(mild_dwelling, _winter_scenario(7.0), 1.2, 1005.0)

    cold_cop = (
        cold_results["totals"]["heating_thermal_kwh"]
        / cold_results["totals"]["heating_electric_kwh"]
    )
    mild_cop = (
        mild_results["totals"]["heating_thermal_kwh"]
        / mild_results["totals"]["heating_electric_kwh"]
    )
    assert round(cold_cop, 1) == 2.0
    assert round(mild_cop, 1) == 3.2


def _electric_heater():
    return {
        "id": "electric_heater",
        "type": "electric_radiator",
        "energy_vector": "electricity",
        "served_rooms": ["main_room"],
        "max_power_w": 5000.0,
        "performance_ref": {"mode": "constant", "cop": 1.0},
    }


def _gas_boiler():
    return {
        "id": "gas_boiler",
        "type": "boiler",
        "energy_vector": "gas",
        "served_rooms": ["main_room"],
        "max_power_w": 5000.0,
        "performance_ref": {"mode": "constant", "cop": 0.9},
    }


def _heat_pump():
    return {
        "id": "heat_pump",
        "type": "heat_pump",
        "energy_vector": "electricity",
        "served_rooms": ["main_room"],
        "max_power_w": 5000.0,
        "performance_ref": {
            "mode": "temperature_curve",
            "cop": 3.2,
            "points": [
                {"outdoor_temperature_c": -7.0, "cop": 2.0},
                {"outdoor_temperature_c": 7.0, "cop": 3.2},
            ],
        },
    }
