import json
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts import create_customer_experience as customer_experience
from thermal_model import (
    build_report_model,
    compare_scenarios,
    load_dwelling,
    load_reference_catalog,
    render_report_html,
    resolve_dwelling_references,
    validate_scenario,
)


def _resolved_dwelling():
    catalog = load_reference_catalog()
    dwelling = load_dwelling("data/examples/house_simple.json", validate=False)
    return resolve_dwelling_references(dwelling, catalog), catalog


def _change(change_id):
    return next(
        change
        for change in customer_experience.CHANGES
        if change["id"] == change_id
    )


def test_reflective_roof_runs_heatwave_and_long_summer():
    dwelling, catalog = _resolved_dwelling()
    customer = {"change": _change("reflective_roof"), "target_scope": "all"}

    experiments = customer_experience.build_experiments(customer, dwelling, catalog)

    assert [experiment["id"] for experiment in experiments] == [
        "house_simple_reflective_roof_summer_heatwave",
        "house_simple_reflective_roof_summer_long",
        "house_simple_reflective_roof_annual",
    ]
    assert [experiment["role"] for experiment in experiments] == [
        "primary",
        "secondary",
        "annual",
    ]
    assert len(experiments[0]["before"]["weather"]["hourly"]) == 72
    assert len(experiments[1]["before"]["weather"]["hourly"]) == 1440
    assert experiments[1]["before"]["experiment"]["weather_variant"] == (
        "summer_long_with_heatwave"
    )
    assert experiments[2]["before"]["experiment"]["simulation_type"] == "annual"
    assert experiments[2]["before"]["experiment"]["weather_city"] == "Bordeaux"
    assert experiments[2]["before"]["weather"]["weather_ref"] == (
        "data/weather/openmeteo/thermal/bordeaux_2023.weather.json"
    )
    schema = json.loads(Path("schemas/scenario.schema.json").read_text())
    assert list(Draft202012Validator(schema).iter_errors(experiments[2]["before"])) == []
    validate_scenario(experiments[0]["before"])
    validate_scenario(experiments[1]["after"])


def test_window_summer_experiment_requires_exposed_windows():
    dwelling, catalog = _resolved_dwelling()

    north_window_customer = {
        "change": _change("better_windows"),
        "target_scope": "bathroom",
    }
    exposed_window_customer = {
        "change": _change("better_windows"),
        "target_scope": "bedroom",
    }

    north_window_experiments = customer_experience.build_experiments(
        north_window_customer,
        dwelling,
        catalog,
    )
    exposed_window_experiments = customer_experience.build_experiments(
        exposed_window_customer,
        dwelling,
        catalog,
    )

    assert [experiment["season"] for experiment in north_window_experiments] == [
        "winter",
        "annual",
    ]
    assert [experiment["season"] for experiment in exposed_window_experiments] == [
        "winter",
        "summer",
        "annual",
    ]


def test_report_exposes_experiment_role_and_reason():
    dwelling, catalog = _resolved_dwelling()
    customer = {"change": _change("solar_protection"), "target_scope": "living_room"}
    experiment = customer_experience.build_experiments(customer, dwelling, catalog)[0]

    comparison = compare_scenarios(
        dwelling,
        experiment["before"],
        experiment["after"],
        air_density_kg_m3=1.2,
        air_heat_capacity_j_kgk=1005.0,
    )
    report = build_report_model(comparison)
    html = render_report_html(report)

    assert comparison["experiment"]["role"] == "primary"
    assert report["experiment"]["label"] == "Ete canicule"
    assert "Experience principale" in html
    assert "apports solaires" in html


def test_customer_facade_dimensions_masks_and_roof_details_feed_dwelling():
    catalog = load_reference_catalog()
    customer = {
        "project_name": "test logement",
        "postal_code": "33000",
        "city": "Bordeaux",
        "climate_zone_id": "FR_H2c",
        "period_id": "2001_2012_good_insulation",
        "wall_insulation": {"u_factor": 1.0},
        "roof_insulation": {"u_factor": 1.0},
        "floor_insulation": {"u_factor": 1.0},
        "airtightness": {"ach_factor": 1.0},
        "ventilation_id": "simple_flow",
        "window_ref": "double_glazing_standard",
        "shutter_ref": "roller_shutter_standard",
        "heating_ref": "electric_radiator",
        "has_cooling": False,
        "thermal_layout": {"type": "single_room", "connections": []},
        "change_details": {
            "roof_color": {"albedo": 0.4},
            "attic_ventilation": {"solar_to_room_factor": 0.05},
        },
        "rooms": [
            {
                "id": "living",
                "name": "Salon",
                "type": "living",
                "floor_area_m2": 20.0,
                "height_m": 2.5,
                "exterior_contact": "exterior",
                "facades": [
                    {
                        "orientation": "S",
                        "window_area_m2": 3.0,
                        "wall_length_m": 6.0,
                        "mask_factor": 0.65,
                        "window_ref": "double_glazing_old",
                    },
                ],
                "has_roof": True,
                "has_ground_floor": False,
            },
        ],
    }

    dwelling = customer_experience.build_dwelling(customer, catalog)
    room = dwelling["rooms"][0]
    wall = next(surface for surface in room["surfaces"] if surface["type"] == "external_wall")
    roof = next(surface for surface in room["surfaces"] if surface["type"] == "roof")
    window = room["windows"][0]

    assert wall["area_m2"] == 12.0
    assert wall["mask_factor"] == 0.65
    assert window["window_ref"] == "double_glazing_old"
    assert window["mask_factor"] == 0.65
    assert roof["albedo"] == 0.4
    assert roof["solar_to_room_factor"] == 0.05


def test_customer_setpoints_and_shutter_usage_feed_summer_scenario():
    dwelling, catalog = _resolved_dwelling()
    customer = {
        "change": _change("solar_protection"),
        "target_scope": "living_room",
        "setpoints": {"heating_c": 20.0, "cooling_c": 27.0},
        "shutter_usage": {"id": "rare"},
    }

    experiment = customer_experience.build_experiments(customer, dwelling, catalog)[0]
    before = experiment["before"]

    assert before["setpoints"] == {"heating_c": 20.0, "cooling_c": 27.0}
    assert before["controls"]["shutters"]["hourly"][0] == {
        "hour": 8,
        "opening_ratio": 0.75,
    }


def test_middle_floor_apartment_does_not_need_room_roof_or_floor_questions():
    assert customer_experience.default_has_roof("apartment", "apartment_middle_floor") is False
    assert customer_experience.default_has_ground_floor("apartment", "apartment_middle_floor") is False
    assert customer_experience.should_ask_room_roof("apartment", "apartment_middle_floor") is False
    assert customer_experience.should_ask_room_ground_floor(
        "apartment",
        "apartment_middle_floor",
    ) is False


def test_ambiguous_positions_keep_room_roof_or_floor_questions():
    assert customer_experience.should_ask_room_roof("house", "multi_storey_house") is True
    assert customer_experience.should_ask_room_ground_floor("house", "multi_storey_house") is True
    assert customer_experience.should_ask_room_roof("apartment", "apartment_top_floor") is False
    assert customer_experience.should_ask_room_ground_floor(
        "apartment",
        "apartment_ground_floor",
    ) is False


def test_apartment_position_controls_roof_and_floor_contact():
    assert customer_experience.dwelling_has_roof_contact(
        "apartment",
        "apartment_middle_floor",
    ) is False
    assert customer_experience.dwelling_has_floor_contact(
        "apartment",
        "apartment_middle_floor",
    ) is False
    assert customer_experience.dwelling_has_roof_contact(
        "apartment",
        "apartment_ground_floor",
    ) is False
    assert customer_experience.dwelling_has_floor_contact(
        "apartment",
        "apartment_ground_floor",
    ) is True
    assert customer_experience.dwelling_has_roof_contact(
        "apartment",
        "apartment_ground_top_floor",
    ) is True
    assert customer_experience.dwelling_has_floor_contact(
        "apartment",
        "apartment_ground_top_floor",
    ) is True


def test_non_contact_roof_and_floor_insulation_are_not_concerned():
    roof = customer_experience.collect_roof_insulation("apartment", "apartment_middle_floor")
    floor = customer_experience.collect_floor_insulation("apartment", "apartment_top_floor")

    assert roof["id"] == "not_concerned"
    assert floor["id"] == "not_concerned"
