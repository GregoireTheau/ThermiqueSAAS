from scripts.run_model_validation import (
    _matches_expectation,
    build_case_answers,
    evaluate_checks,
    expand_runs,
    extract_metrics,
    load_matrix,
)
from thermal_saas.business_flow import run_profile_experience


MATRIX_PATH = "data/validation/us_roof_validation_matrix.json"


def test_validation_matrix_has_unique_canonical_and_sensitivity_runs():
    matrix = load_matrix(MATRIX_PATH)
    runs = expand_runs(matrix)

    assert len(matrix["cases"]) == 10
    assert len(runs) == 33
    assert len({run["run_id"] for run in runs}) == len(runs)


def test_validation_case_uses_product_flow_and_extracts_annual_metrics(tmp_path):
    matrix = load_matrix(MATRIX_PATH)
    run_spec = expand_runs(matrix)[0]
    answers = build_case_answers(
        run_spec["case"],
        weather_type="historical",
        weather_year=2023,
        tmy_name="tmy-2024",
        weather_dir=tmp_path / "weather",
    )

    result = run_profile_experience(
        "roof_insulation_seller",
        answers,
        include_report_html=False,
    )
    annual = next(run for run in result["simulation_runs"] if run["role"] == "annual")
    metrics, monthly = extract_metrics(
        run_spec,
        annual,
        answers,
        result["resolved_dwelling"],
    )

    assert metrics["before_heating_thermal_kwh"] > 0
    assert metrics["after_heating_thermal_kwh"] > 0
    assert metrics["heating_demand_reduced_kwh"] > 0
    assert metrics["before_peak_heating_kw"] <= metrics["before_installed_heating_capacity_kw"]
    assert metrics["before_energy_balance_max_residual_w"] <= 1e-5
    assert metrics["after_energy_balance_max_residual_w"] <= 1e-5
    assert len(monthly) == 24


def test_monotonic_expectations_are_directional_and_tolerant():
    assert _matches_expectation([10.0, 9.0, 9.0], "nonincreasing", 0.0)
    assert _matches_expectation([8.0, 8.01, 9.0], "nondecreasing", 0.002)
    assert _matches_expectation([10.0, 10.005, 9.995], "approximately_constant", 0.001)
    assert not _matches_expectation([10.0, 11.0, 9.0], "nonincreasing", 0.0)


def test_partial_run_skips_incomplete_sensitivity_checks():
    matrix = load_matrix(MATRIX_PATH)
    metric = {
        "run_id": "atlanta_1970_ranch",
        "before_heating_thermal_kwh": 10.0,
        "after_heating_thermal_kwh": 8.0,
        "before_heating_final_kwh": 12.0,
        "after_heating_final_kwh": 9.0,
        "before_energy_cost_usd": 2.0,
        "after_energy_cost_usd": 1.5,
        "before_energy_balance_max_residual_w": 0.0,
        "after_energy_balance_max_residual_w": 0.0,
        "before_peak_heating_kw": 4.0,
        "after_peak_heating_kw": 3.0,
        "before_installed_heating_capacity_kw": 5.0,
        "after_installed_heating_capacity_kw": 5.0,
        "heating_demand_reduced_kwh": 2.0,
    }

    checks = evaluate_checks([metric], matrix)

    assert len(checks) == 4
    assert all(check["status"] == "pass" for check in checks)
