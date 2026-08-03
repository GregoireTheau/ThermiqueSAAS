from copy import deepcopy

from thermal_model import (
    compute_room_static_losses,
    simulate_1r1c,
    validate_dwelling,
    validate_scenario,
)


AIR_DENSITY_KG_M3 = 1.2
AIR_HEAT_CAPACITY_J_KGK = 1005.0


def _base_dwelling(
    *,
    wall_u_value=0.8,
    roof_u_value=0.4,
    window_area_m2=4.0,
    window_shutter=None,
    infiltration_ach=0.2,
    mechanical_ach=0.2,
    equivalent_capacity_j_m2k=160000,
    heating_power_w=0.0,
):
    heating_systems = []
    if heating_power_w > 0:
        heating_systems.append(
            {
                "id": "heating_system",
                "type": "electric_resistance",
                "served_rooms": ["main_room"],
                "max_power_w": heating_power_w,
                "performance_ref": {"mode": "constant", "cop": 1.0},
            }
        )

    window = {
        "id": "south_window",
        "area_m2": window_area_m2,
        "u_value_w_m2k": 1.6,
        "g_value": 0.55,
        "azimuth_deg": 180,
        "tilt_deg": 90,
        "mask_factor": 1.0,
    }
    if window_shutter:
        window["shutter"] = deepcopy(window_shutter)

    return {
        "schema_version": "0.1",
        "dwelling_id": "thermal_invariant_dwelling",
        "metadata": {
            "name": "Thermal invariant dwelling",
            "description": "Minimal single-room dwelling for model property tests.",
            "created_by": "tests",
        },
        "location": {
            "country": "FR",
            "postal_code": "33000",
            "city": "Reference",
            "climate_zone_id": "US_IECC_2021_3A",
            "ground_albedo": 0.2,
        },
        "defaults": {
            "initial_temperature_c": 20.0,
            "equivalent_capacity_j_m2k": equivalent_capacity_j_m2k,
            "thermal_bridge_factor": 0.1,
            "internal_gain_w_m2": 0.0,
            "ach_h": infiltration_ach + mechanical_ach,
        },
        "rooms": [
            {
                "id": "main_room",
                "name": "Main room",
                "type": "living",
                "floor_area_m2": 40.0,
                "height_m": 2.5,
                "volume_m3": 100.0,
                "initial_temperature_c": 20.0,
                "equivalent_capacity_j_m2k": equivalent_capacity_j_m2k,
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
                        "area_m2": 25.0,
                        "u_value_w_m2k": wall_u_value,
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
                        "area_m2": 40.0,
                        "u_value_w_m2k": roof_u_value,
                        "azimuth_deg": 180,
                        "tilt_deg": 25,
                        "albedo": 0.3,
                        "solar_to_room_factor": 0.02,
                        "mask_factor": 1.0,
                    },
                ],
                "windows": [window],
            }
        ],
        "thermal_links": [],
        "systems": {
            "heating": heating_systems,
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


def _scenario(
    *,
    temperatures,
    solar_south=0.0,
    solar_roof=0.0,
    heating_c=0.0,
    cooling_c=80.0,
    initial_temperature_c=20.0,
    shutter_opening_ratio=1.0,
):
    scenario = {
        "schema_version": "0.1",
        "scenario_id": "thermal_invariant_scenario",
        "dwelling_id": "thermal_invariant_dwelling",
        "timestep_h": 1.0,
        "initial_temperatures_c": {"main_room": initial_temperature_c},
        "setpoints": {"heating_c": heating_c, "cooling_c": cooling_c},
        "controls": {
            "shutters": {"default_opening_ratio": shutter_opening_ratio},
            "natural_ventilation": {"default_ach": 0.0},
        },
        "weather": {
            "source": "synthetic_invariant",
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
        "energy_prices": {"electricity_usd_kwh": 0.18},
        "co2_factors": {"electricity_kg_kwh": 0.0},
    }
    validate_scenario(scenario)
    return scenario


def _simulate(dwelling, scenario):
    validate_dwelling(dwelling)
    return simulate_1r1c(
        dwelling,
        scenario,
        air_density_kg_m3=AIR_DENSITY_KG_M3,
        air_heat_capacity_j_kgk=AIR_HEAT_CAPACITY_J_KGK,
    )


def test_increasing_insulation_reduces_static_heat_losses():
    baseline = _base_dwelling(wall_u_value=1.2, roof_u_value=0.9)
    insulated = _base_dwelling(wall_u_value=0.3, roof_u_value=0.15)

    baseline_losses = compute_room_static_losses(
        baseline,
        baseline["rooms"][0],
        indoor_temperature_c=20.0,
        outdoor_temperature_c=0.0,
        air_density_kg_m3=AIR_DENSITY_KG_M3,
        air_heat_capacity_j_kgk=AIR_HEAT_CAPACITY_J_KGK,
    )
    insulated_losses = compute_room_static_losses(
        insulated,
        insulated["rooms"][0],
        indoor_temperature_c=20.0,
        outdoor_temperature_c=0.0,
        air_density_kg_m3=AIR_DENSITY_KG_M3,
        air_heat_capacity_j_kgk=AIR_HEAT_CAPACITY_J_KGK,
    )

    assert (
        insulated_losses["transmission_loss_w"]
        < baseline_losses["transmission_loss_w"]
    )
    assert insulated_losses["total_loss_w"] < baseline_losses["total_loss_w"]


def test_increasing_south_glazing_area_increases_solar_gains():
    small_window = _base_dwelling(window_area_m2=2.0)
    large_window = _base_dwelling(window_area_m2=8.0)
    scenario = _scenario(
        temperatures=[20.0] * 6,
        solar_south=600.0,
        solar_roof=0.0,
        initial_temperature_c=20.0,
    )

    small_results = _simulate(small_window, scenario)
    large_results = _simulate(large_window, scenario)

    assert (
        large_results["rooms_summary"]["main_room"]["solar_gain_kwh"]
        > small_results["rooms_summary"]["main_room"]["solar_gain_kwh"]
    )


def test_closed_shutters_reduce_summer_overheating():
    shutter = {
        "type": "roller_shutter",
        "solar_factor_closed": 0.15,
        "solar_factor_open": 1.0,
        "u_factor_closed": 0.8,
    }
    dwelling = _base_dwelling(window_area_m2=10.0, window_shutter=shutter)
    open_shutters = _scenario(
        temperatures=[27.0, 30.0, 34.0, 38.0, 39.0, 36.0, 32.0, 29.0],
        solar_south=750.0,
        solar_roof=800.0,
        initial_temperature_c=26.0,
        shutter_opening_ratio=1.0,
    )
    closed_shutters = _scenario(
        temperatures=[27.0, 30.0, 34.0, 38.0, 39.0, 36.0, 32.0, 29.0],
        solar_south=750.0,
        solar_roof=800.0,
        initial_temperature_c=26.0,
        shutter_opening_ratio=0.0,
    )

    open_results = _simulate(dwelling, open_shutters)
    closed_results = _simulate(dwelling, closed_shutters)

    assert (
        closed_results["rooms_summary"]["main_room"]["hot_degree_hours"]
        < open_results["rooms_summary"]["main_room"]["hot_degree_hours"]
    )
    assert (
        closed_results["rooms_summary"]["main_room"]["max_temperature_c"]
        < open_results["rooms_summary"]["main_room"]["max_temperature_c"]
    )


def test_increasing_inertia_dampens_temperature_peaks():
    light_inertia = _base_dwelling(equivalent_capacity_j_m2k=80000)
    heavy_inertia = _base_dwelling(equivalent_capacity_j_m2k=300000)
    scenario = _scenario(
        temperatures=[28.0, 31.0, 35.0, 39.0, 40.0, 38.0, 34.0, 30.0],
        solar_south=700.0,
        solar_roof=700.0,
        initial_temperature_c=26.0,
    )

    light_results = _simulate(light_inertia, scenario)
    heavy_results = _simulate(heavy_inertia, scenario)

    assert (
        heavy_results["rooms_summary"]["main_room"]["max_temperature_c"]
        < light_results["rooms_summary"]["main_room"]["max_temperature_c"]
    )


def test_increasing_ventilation_increases_winter_heat_losses():
    low_ventilation = _base_dwelling(infiltration_ach=0.1, mechanical_ach=0.1)
    high_ventilation = _base_dwelling(infiltration_ach=0.9, mechanical_ach=0.3)

    low_losses = compute_room_static_losses(
        low_ventilation,
        low_ventilation["rooms"][0],
        indoor_temperature_c=20.0,
        outdoor_temperature_c=0.0,
        air_density_kg_m3=AIR_DENSITY_KG_M3,
        air_heat_capacity_j_kgk=AIR_HEAT_CAPACITY_J_KGK,
    )
    high_losses = compute_room_static_losses(
        high_ventilation,
        high_ventilation["rooms"][0],
        indoor_temperature_c=20.0,
        outdoor_temperature_c=0.0,
        air_density_kg_m3=AIR_DENSITY_KG_M3,
        air_heat_capacity_j_kgk=AIR_HEAT_CAPACITY_J_KGK,
    )

    assert high_losses["ventilation_loss_w"] > low_losses["ventilation_loss_w"]
    assert high_losses["total_loss_w"] > low_losses["total_loss_w"]


def test_undersized_heating_power_does_not_reach_target_temperature():
    undersized = _base_dwelling(
        wall_u_value=1.8,
        roof_u_value=1.5,
        infiltration_ach=0.8,
        mechanical_ach=0.0,
        heating_power_w=300.0,
    )
    scenario = _scenario(
        temperatures=[-5.0] * 12,
        heating_c=19.0,
        cooling_c=80.0,
        initial_temperature_c=19.0,
    )

    results = _simulate(undersized, scenario)

    assert results["rooms_summary"]["main_room"]["final_temperature_c"] < 19.0
    assert results["rooms_summary"]["main_room"]["cold_degree_hours"] > 0.0


def test_warmer_weather_reduces_heating_needs():
    dwelling = _base_dwelling(heating_power_w=6000.0)
    cold_weather = _scenario(
        temperatures=[-5.0, -4.0, -3.0, -2.0, -3.0, -4.0],
        heating_c=19.0,
        cooling_c=80.0,
        initial_temperature_c=19.0,
    )
    mild_weather = _scenario(
        temperatures=[8.0, 9.0, 10.0, 11.0, 10.0, 9.0],
        heating_c=19.0,
        cooling_c=80.0,
        initial_temperature_c=19.0,
    )

    cold_results = _simulate(dwelling, cold_weather)
    mild_results = _simulate(dwelling, mild_weather)

    assert (
        mild_results["totals"]["heating_thermal_kwh"]
        < cold_results["totals"]["heating_thermal_kwh"]
    )
    assert (
        mild_results["totals"]["heating_electric_kwh"]
        < cold_results["totals"]["heating_electric_kwh"]
    )


def test_climate_zone_and_month_do_not_modify_local_weather_solar_gains():
    dwelling = _base_dwelling()
    scenario_without_month = _scenario(
        temperatures=[30.0] * 24,
        solar_south=600.0,
        heating_c=0.0,
        cooling_c=80.0,
    )
    scenario_without_month["climate_zone_id"] = "US_IECC_2021_3A"
    scenario_with_month = deepcopy(scenario_without_month)
    for point in scenario_with_month["weather"]["hourly"]:
        point["month"] = 7
    scenario_without_zone = deepcopy(scenario_with_month)
    del scenario_without_zone["climate_zone_id"]

    without_month_results = simulate_1r1c(
        dwelling,
        scenario_without_month,
        air_density_kg_m3=AIR_DENSITY_KG_M3,
        air_heat_capacity_j_kgk=AIR_HEAT_CAPACITY_J_KGK,
    )
    with_month_results = simulate_1r1c(
        dwelling,
        scenario_with_month,
        air_density_kg_m3=AIR_DENSITY_KG_M3,
        air_heat_capacity_j_kgk=AIR_HEAT_CAPACITY_J_KGK,
    )
    without_zone_results = simulate_1r1c(
        dwelling,
        scenario_without_zone,
        air_density_kg_m3=AIR_DENSITY_KG_M3,
        air_heat_capacity_j_kgk=AIR_HEAT_CAPACITY_J_KGK,
    )

    solar_gains = {
        results["rooms_summary"]["main_room"]["solar_gain_kwh"]
        for results in (without_month_results, with_month_results, without_zone_results)
    }
    assert len(solar_gains) == 1
