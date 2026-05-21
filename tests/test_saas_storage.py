from thermal_saas.storage import (
    create_organization,
    create_project,
    create_simulation_runs,
    get_latest_project_answers,
    get_project,
    get_simulation_report_html,
    get_simulation_run,
    list_project_simulation_runs,
    save_project_answers,
)


def _answers():
    return {
        "project_name": "Projet stocke",
        "city": "Bordeaux",
        "postal_code": "33000",
        "dwelling_type": "house",
        "position_id": "single_storey_house",
        "period_id": "2001_2012_good_insulation",
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


def test_storage_persists_project_answers_and_simulation_runs(tmp_path):
    db_path = tmp_path / "thermal_saas.sqlite"
    organization = create_organization("Fenetre Pro", "window_seller", db_path)
    project = create_project(organization["id"], "Client Dupont", "Mme Dupont", db_path)

    answers = save_project_answers(project["id"], _answers(), db_path)
    latest_answers = get_latest_project_answers(project["id"], db_path)
    simulation_batch = create_simulation_runs(project["id"], db_path)
    simulation_runs = list_project_simulation_runs(project["id"], db_path)

    assert get_project(project["id"], db_path)["business_profile_id"] == "window_seller"
    assert answers["version"] == 1
    assert latest_answers["answers"]["project_name"] == "Projet stocke"
    assert simulation_batch["adaptation_id"] == "better_windows"
    assert [run["season"] for run in simulation_runs] == ["winter", "summer", "annual"]
    assert simulation_runs[-1]["role"] == "annual"

    persisted_run = get_simulation_run(simulation_runs[0]["id"], db_path)
    assert persisted_run["result"]["comparison"]["experiment"]["adaptation_id"] == (
        "better_windows"
    )
    assert "<!doctype html>" in get_simulation_report_html(simulation_runs[0]["id"], db_path)
    persisted_annual_run = get_simulation_run(simulation_runs[-1]["id"], db_path)
    assert persisted_annual_run["result"]["comparison"]["experiment"]["weather_year"] == 2023
    assert "<!doctype html>" in get_simulation_report_html(simulation_runs[-1]["id"], db_path)
