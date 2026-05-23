from thermal_model import (
    compute_room_static_losses,
    compute_dwelling_static_losses,
    load_dwelling,
    load_reference_catalog,
    resolve_dwelling_references,
)


def test_compute_static_losses_house_simple_total():
    catalog = load_reference_catalog()
    dwelling = load_dwelling("data/examples/house_simple.json", validate=False)
    dwelling = resolve_dwelling_references(dwelling, catalog)

    results = compute_dwelling_static_losses(
        dwelling,
        indoor_temperature_c=20.0,
        outdoor_temperature_c=0.0,
        air_density_kg_m3=1.2,
        air_heat_capacity_j_kgk=1005.0,
    )

    assert round(results["totals"]["total_h_w_k"], 1) == 103.7
    assert round(results["totals"]["total_loss_w"]) == 2075


def test_room_static_losses_split_ventilation_and_recovery():
    room = {
        "volume_m3": 100.0,
        "surfaces": [],
        "windows": [],
        "ventilation": {
            "mode": "ach",
            "ach_h": 0.5,
            "infiltration_ach": 0.15,
            "mechanical_ach": 0.35,
            "recovery_efficiency": 0.75,
        },
    }
    dwelling = {"defaults": {"thermal_bridge_factor": 0.0, "ach_h": 0.5}}

    losses = compute_room_static_losses(
        dwelling,
        room,
        indoor_temperature_c=20.0,
        outdoor_temperature_c=0.0,
        air_density_kg_m3=1.2,
        air_heat_capacity_j_kgk=1005.0,
        natural_ventilation_ach=3.0,
    )

    assert round(losses["infiltration_h_w_k"], 2) == 5.03
    assert round(losses["mechanical_ventilation_h_w_k"], 2) == 2.93
    assert round(losses["natural_ventilation_h_w_k"], 2) == 100.5
    assert round(losses["ventilation_h_w_k"], 2) == 108.46


def test_room_static_losses_applies_boundary_temperature_reduction_factors():
    room = {
        "volume_m3": 1.0,
        "surfaces": [
            {"id": "exterior", "boundary": "exterior", "area_m2": 10.0, "u_value_w_m2k": 1.0},
            {"id": "party", "boundary": "party", "area_m2": 10.0, "u_value_w_m2k": 1.0},
            {"id": "unheated", "boundary": "unheated_space", "area_m2": 10.0, "u_value_w_m2k": 1.0},
            {"id": "ground", "boundary": "ground", "area_m2": 10.0, "u_value_w_m2k": 1.0},
            {"id": "room", "boundary": "room", "area_m2": 10.0, "u_value_w_m2k": 1.0},
        ],
        "windows": [],
        "ventilation": {"mode": "ach", "ach_h": 0.0},
    }
    dwelling = {"defaults": {"thermal_bridge_factor": 0.0, "ach_h": 0.0}}

    losses = compute_room_static_losses(
        dwelling,
        room,
        indoor_temperature_c=20.0,
        outdoor_temperature_c=0.0,
        air_density_kg_m3=1.2,
        air_heat_capacity_j_kgk=1005.0,
    )

    assert losses["surface_ua_w_k"] == 28.0
    assert losses["transmission_h_w_k"] == 28.0
