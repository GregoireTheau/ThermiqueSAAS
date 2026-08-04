#!/usr/bin/env python3
"""Run a reproducible US roof-insulation validation matrix."""

from __future__ import annotations

import argparse
import csv
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from html import escape
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from thermal_model import THERMAL_ENGINE_VERSION, apply_scenario_overrides  # noqa: E402
from thermal_saas.business_flow import run_profile_experience  # noqa: E402


FT2_TO_M2 = 0.09290304
FT_TO_M = 0.3048


def load_matrix(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def expand_runs(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    """Return canonical cases plus one-at-a-time sensitivity variants."""
    cases = {case["case_id"]: case for case in matrix["cases"]}
    runs = [
        {
            "run_id": case_id,
            "archetype_id": case_id,
            "case": deepcopy(case),
            "parameter_id": "",
            "parameter_value": "",
        }
        for case_id, case in cases.items()
    ]
    for sensitivity in matrix.get("sensitivities", []):
        archetype_id = sensitivity["archetype_id"]
        base_case = cases[archetype_id]
        base_value = base_case[sensitivity["field"]]
        for value in sensitivity["values"]:
            if value == base_value:
                continue
            variant = deepcopy(base_case)
            variant[sensitivity["field"]] = value
            runs.append(
                {
                    "run_id": (
                        f"{archetype_id}__{sensitivity['parameter_id']}__"
                        f"{_slug(value)}"
                    ),
                    "archetype_id": archetype_id,
                    "case": variant,
                    "parameter_id": sensitivity["parameter_id"],
                    "parameter_value": value,
                },
            )
    return runs


def build_case_answers(
    case: dict[str, Any],
    *,
    weather_type: str,
    weather_year: int,
    tmy_name: str,
    weather_dir: str | Path,
) -> dict[str, Any]:
    """Map a concise validation archetype to the production questionnaire."""
    return {
        "project_name": f"Validation {case['case_id']}",
        "postal_code": case["postal_code"],
        "dwelling_type": case["dwelling_type"],
        "position_id": case["position_id"],
        "adjacency_id": case.get("adjacency_id", "detached"),
        "construction_era_id": case["construction_era_id"],
        "wall_insulation_id": case["wall_insulation_id"],
        "roof_assembly_id": case["roof_assembly_id"],
        "existing_roof_r_value": case["existing_roof_r_value"],
        "proposed_roof_r_value": case["proposed_roof_r_value"],
        "framing_type_id": case["framing_type_id"],
        "hvac_duct_location_id": case["hvac_duct_location_id"],
        "roof_color_id": case.get("roof_color_id", "medium"),
        "airtightness_id": case["airtightness_id"],
        "ventilation_id": case["ventilation_id"],
        "window_ref": case["window_ref"],
        "shutter_ref": case.get("shutter_ref", "none"),
        "heating_ref": case["heating_ref"],
        "has_cooling": case.get("has_cooling", False),
        "heating_setpoint_f": case.get("heating_setpoint_f", 68.0),
        "cooling_setpoint_day_f": case.get("cooling_setpoint_day_f", 78.0),
        "cooling_setpoint_night_f": case.get("cooling_setpoint_night_f", 78.0),
        "electricity_price_usd_kwh": case.get("electricity_price_usd_kwh", 0.18),
        "natural_gas_price_usd_therm": case.get("natural_gas_price_usd_therm", 1.50),
        "propane_price_usd_gallon": case.get("propane_price_usd_gallon", 2.50),
        "annual_weather_type": weather_type,
        "annual_weather_year": weather_year,
        "annual_tmy_name": tmy_name,
        "annual_weather_dir": str(weather_dir),
        "include_annual_experiment": True,
        "rooms": _build_rooms(case),
    }


def _build_rooms(case: dict[str, Any]) -> list[dict[str, Any]]:
    area_m2 = float(case["floor_area_ft2"]) * FT2_TO_M2
    height_m = float(case.get("ceiling_height_ft", 8.0)) * FT_TO_M
    layout = case.get("room_layout", "two_zone")
    room_specs = (
        [("Main zone", "living", 1.0, ["S", "W", "N", "E"])]
        if layout == "single_zone"
        else [
            ("Living zone", "living", 0.62, ["S", "W"]),
            ("Sleeping zone", "bedroom", 0.38, ["N", "E"]),
        ]
    )
    side_m = math.sqrt(area_m2)
    glazing_ratio = float(case.get("window_to_floor_ratio", 0.14))
    rooms = []
    for name, room_type, share, orientations in room_specs:
        room_area_m2 = area_m2 * share
        total_window_m2 = room_area_m2 * glazing_ratio
        facades = [
            {
                "orientation": orientation,
                "wall_length_m": side_m * share,
                "window_area_m2": total_window_m2 / len(orientations),
                "mask_factor": float(case.get("solar_mask_factor", 0.85)),
            }
            for orientation in orientations
        ]
        rooms.append(
            {
                "name": name,
                "type": room_type,
                "floor_area_m2": round(room_area_m2, 3),
                "height_m": round(height_m, 3),
                "facades": facades,
                "has_roof": True,
                "has_ground_floor": case["position_id"] == "single_storey_house",
                "has_cooling": bool(case.get("has_cooling", False)),
            },
        )
    return rooms


def extract_metrics(
    run_spec: dict[str, Any],
    annual_run: dict[str, Any],
    answers: dict[str, Any],
    resolved_dwelling: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    comparison = annual_run["comparison"]
    before_scenario = annual_run["before_scenario"]
    after_scenario = annual_run["after_scenario"]
    before_dwelling = deepcopy(resolved_dwelling)
    after_dwelling = deepcopy(resolved_dwelling)
    apply_scenario_overrides(before_dwelling, before_scenario)
    apply_scenario_overrides(after_dwelling, after_scenario)

    before = _scenario_metrics(comparison["before"], before_scenario, before_dwelling)
    after = _scenario_metrics(comparison["after"], after_scenario, after_dwelling)
    case = run_spec["case"]
    trace = comparison["experiment"]["weather_trace"]
    row: dict[str, Any] = {
        "run_id": run_spec["run_id"],
        "archetype_id": run_spec["archetype_id"],
        "case_label": case["label"],
        "parameter_id": run_spec["parameter_id"],
        "parameter_value": run_spec["parameter_value"],
        "postal_code": case["postal_code"],
        "city": comparison.get("location", {}).get("city", ""),
        "state": comparison.get("location", {}).get("state", ""),
        "climate_zone": comparison.get("location", {}).get("climate_zone_code", ""),
        "floor_area_ft2": case["floor_area_ft2"],
        "construction_era_id": case["construction_era_id"],
        "dwelling_type": case["dwelling_type"],
        "position_id": case["position_id"],
        "roof_assembly_id": case["roof_assembly_id"],
        "existing_roof_r_value": case["existing_roof_r_value"],
        "proposed_roof_r_value": case["proposed_roof_r_value"],
        "airtightness_id": case["airtightness_id"],
        "ventilation_id": case["ventilation_id"],
        "heating_ref": case["heating_ref"],
        "hvac_duct_location_id": case["hvac_duct_location_id"],
        "weather_type": trace.get("weather_type", ""),
        "weather_reference": trace.get("weather_reference", ""),
        "weather_model": trace.get("model", ""),
        "weather_timezone": trace.get("timezone", ""),
        "weather_hash": trace.get("hourly_sha256", ""),
        "electricity_price_usd_kwh": answers["electricity_price_usd_kwh"],
        "natural_gas_price_usd_therm": answers["natural_gas_price_usd_therm"],
        "propane_price_usd_gallon": answers["propane_price_usd_gallon"],
    }
    for key, value in before.items():
        row[f"before_{key}"] = value
    for key, value in after.items():
        row[f"after_{key}"] = value
    row.update(
        {
            "heating_demand_reduced_kwh": _rounded(
                before["heating_thermal_kwh"] - after["heating_thermal_kwh"],
            ),
            "heating_demand_reduced_pct": _percent_reduction(
                before["heating_thermal_kwh"],
                after["heating_thermal_kwh"],
            ),
            "final_heating_energy_reduced_kwh": _rounded(
                before["heating_final_kwh"] - after["heating_final_kwh"],
            ),
            "cost_saved_usd": _rounded(
                before["energy_cost_usd"] - after["energy_cost_usd"],
            ),
        },
    )
    quality_flags = []
    if before["heating_thermal_kwh"] < 100.0:
        quality_flags.append("low_heating_demand_percentage_unstable")
    if before["unmet_heating_degree_hours"] > 10.0:
        quality_flags.append("before_heating_capacity_limited")
    if after["unmet_heating_degree_hours"] > 10.0:
        quality_flags.append("after_heating_capacity_limited")
    row["quality_flags"] = ";".join(quality_flags)
    monthly = _monthly_rows(run_spec["run_id"], comparison)
    return row, monthly


def _scenario_metrics(
    results: dict[str, Any],
    scenario: dict[str, Any],
    dwelling: dict[str, Any],
) -> dict[str, float]:
    totals = results["totals"]
    room_summaries = list(results["rooms_summary"].values())
    heating_powers_kw = [
        sum(room["heating_power_w"] for room in hour["rooms"].values()) / 1000.0
        for hour in results["hourly"]
    ]
    installed_heating_capacity_kw = sum(
        system["max_power_w"] for system in dwelling["systems"]["heating"]
    ) / 1000.0
    setpoint_c = float(scenario["setpoints"]["heating_c"])
    unmet_degree_hours = sum(
        max(0.0, setpoint_c - room["temperature_c"]) * scenario["timestep_h"]
        for hour in results["hourly"]
        for room in hour["rooms"].values()
    )
    return {
        "heating_thermal_kwh": _rounded(totals["heating_thermal_kwh"]),
        "heating_final_kwh": _rounded(totals["heating_final_kwh"]),
        "cooling_thermal_kwh": _rounded(totals["cooling_thermal_kwh"]),
        "cooling_electric_kwh": _rounded(totals["cooling_electric_kwh"]),
        "final_energy_kwh": _rounded(totals["final_energy_kwh"]),
        "energy_cost_usd": _rounded(totals["energy_cost_usd"]),
        "peak_heating_kw": _rounded(max(heating_powers_kw, default=0.0)),
        "p95_heating_kw": _rounded(_percentile(heating_powers_kw, 0.95)),
        "installed_heating_capacity_kw": _rounded(installed_heating_capacity_kw),
        "heating_capacity_utilization_pct": _percent_of(
            max(heating_powers_kw, default=0.0),
            installed_heating_capacity_kw,
        ),
        "unmet_heating_degree_hours": _rounded(unmet_degree_hours),
        "min_indoor_temperature_c": _rounded(
            min(room["min_temperature_c"] for room in room_summaries),
        ),
        "max_indoor_temperature_c": _rounded(
            max(room["max_temperature_c"] for room in room_summaries),
        ),
        "transmission_exchange_kwh": _rounded(
            sum(room["transmission_exchange_kwh"] for room in room_summaries),
        ),
        "infiltration_exchange_kwh": _rounded(
            sum(room["infiltration_exchange_kwh"] for room in room_summaries),
        ),
        "solar_gain_kwh": _rounded(
            sum(room["solar_gain_kwh"] for room in room_summaries),
        ),
        "heating_load_slope_kw_k": _rounded(
            _heating_load_slope(results["hourly"], setpoint_c),
        ),
        "energy_balance_max_residual_w": _rounded(
            _energy_balance_max_residual(results, scenario, dwelling),
            digits=8,
        ),
    }


def _energy_balance_max_residual(
    results: dict[str, Any],
    scenario: dict[str, Any],
    dwelling: dict[str, Any],
) -> float:
    rooms = {room["id"]: room for room in dwelling["rooms"]}
    previous = {
        room_id: scenario.get("initial_temperatures_c", {}).get(
            room_id,
            room.get("initial_temperature_c", dwelling["defaults"]["initial_temperature_c"]),
        )
        for room_id, room in rooms.items()
    }
    timestep_s = float(scenario["timestep_h"]) * 3600.0
    maximum = 0.0
    for hour in results["hourly"]:
        for room_id, values in hour["rooms"].items():
            room = rooms[room_id]
            capacity = (
                room["floor_area_m2"]
                * room.get(
                    "equivalent_capacity_j_m2k",
                    dwelling["defaults"]["equivalent_capacity_j_m2k"],
                )
            )
            represented_power = capacity * (
                values["temperature_c"] - previous[room_id]
            ) / timestep_s
            modeled_power = (
                values["envelope_power_w"]
                + values["internal_gain_w"]
                + values["solar_gain_w"]
                + values["coupling_power_w"]
                + values["heating_power_w"]
                - values["cooling_power_w"]
            )
            maximum = max(maximum, abs(represented_power - modeled_power))
            previous[room_id] = values["temperature_c"]
    return maximum


def _heating_load_slope(hourly: list[dict[str, Any]], setpoint_c: float) -> float:
    points = []
    for hour in hourly:
        heating_kw = sum(
            room["heating_power_w"] for room in hour["rooms"].values()
        ) / 1000.0
        delta_t = max(0.0, setpoint_c - hour["outdoor_temperature_c"])
        if delta_t > 0 and heating_kw > 0:
            points.append((delta_t, heating_kw))
    if len(points) < 2:
        return 0.0
    mean_x = sum(x for x, _ in points) / len(points)
    mean_y = sum(y for _, y in points) / len(points)
    denominator = sum((x - mean_x) ** 2 for x, _ in points)
    if denominator == 0:
        return 0.0
    return sum((x - mean_x) * (y - mean_y) for x, y in points) / denominator


def _monthly_rows(run_id: str, comparison: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for scenario_name in ("before", "after"):
        grouped: dict[int, list[dict[str, Any]]] = {}
        for hour in comparison[scenario_name]["hourly"]:
            grouped.setdefault(int(hour.get("month") or 0), []).append(hour)
        for month, hours in sorted(grouped.items()):
            heating_powers = [
                sum(room["heating_power_w"] for room in hour["rooms"].values())
                for hour in hours
            ]
            rows.append(
                {
                    "run_id": run_id,
                    "scenario": scenario_name,
                    "month": month,
                    "hours": len(hours),
                    "mean_outdoor_temperature_c": _rounded(
                        sum(hour["outdoor_temperature_c"] for hour in hours) / len(hours),
                    ),
                    "heating_thermal_kwh": _rounded(
                        sum(heating_powers) * comparison["experiment"]["timestep_h"] / 1000.0,
                    ),
                    "peak_heating_kw": _rounded(max(heating_powers, default=0.0) / 1000.0),
                },
            )
    return rows


def build_sensitivity_rows(
    metrics: list[dict[str, Any]],
    matrix: dict[str, Any],
) -> list[dict[str, Any]]:
    by_run = {row["run_id"]: row for row in metrics}
    rows = []
    for sensitivity in matrix.get("sensitivities", []):
        archetype_id = sensitivity["archetype_id"]
        reference = by_run[archetype_id]
        base_value = next(
            case[sensitivity["field"]]
            for case in matrix["cases"]
            if case["case_id"] == archetype_id
        )
        values = [base_value, *[value for value in sensitivity["values"] if value != base_value]]
        for value in values:
            run_id = (
                archetype_id
                if value == base_value
                else f"{archetype_id}__{sensitivity['parameter_id']}__{_slug(value)}"
            )
            current = by_run.get(run_id)
            if current is None:
                continue
            row: dict[str, Any] = {
                "archetype_id": archetype_id,
                "parameter_id": sensitivity["parameter_id"],
                "parameter_value": value,
                "reference_value": base_value,
            }
            for metric in (
                "before_heating_thermal_kwh",
                "before_heating_final_kwh",
                "heating_demand_reduced_pct",
                "cost_saved_usd",
                "before_peak_heating_kw",
                "before_unmet_heating_degree_hours",
            ):
                row[metric] = current[metric]
                row[f"{metric}_change_pct"] = _relative_change(
                    reference[metric],
                    current[metric],
                )
            rows.append(row)
    return rows


def evaluate_checks(
    metrics: list[dict[str, Any]],
    matrix: dict[str, Any],
) -> list[dict[str, Any]]:
    checks = []
    for row in metrics:
        nonnegative = all(
            float(row[field]) >= -1e-6
            for field in (
                "before_heating_thermal_kwh",
                "after_heating_thermal_kwh",
                "before_heating_final_kwh",
                "after_heating_final_kwh",
                "before_energy_cost_usd",
                "after_energy_cost_usd",
            )
        )
        checks.append(_check(f"{row['run_id']}:nonnegative_energy", nonnegative))
        residual = max(
            row["before_energy_balance_max_residual_w"],
            row["after_energy_balance_max_residual_w"],
        )
        checks.append(
            _check(
                f"{row['run_id']}:energy_balance",
                residual <= 1e-5,
                f"max residual {residual:.8g} W",
            ),
        )
        checks.append(
            _check(
                f"{row['run_id']}:roof_insulation_not_worse",
                row["heating_demand_reduced_kwh"] >= -0.01,
                f"saved {row['heating_demand_reduced_kwh']:.3f} thermal kWh",
            ),
        )
        capacity_ok = all(
            row[f"{scenario}_peak_heating_kw"]
            <= row[f"{scenario}_installed_heating_capacity_kw"] + 1e-6
            for scenario in ("before", "after")
        )
        checks.append(
            _check(
                f"{row['run_id']}:central_heating_capacity_conserved",
                capacity_ok,
                (
                    f"before {row['before_peak_heating_kw']:.3f}/"
                    f"{row['before_installed_heating_capacity_kw']:.3f} kW; "
                    f"after {row['after_peak_heating_kw']:.3f}/"
                    f"{row['after_installed_heating_capacity_kw']:.3f} kW"
                ),
            ),
        )

    by_run = {row["run_id"]: row for row in metrics}
    cases = {case["case_id"]: case for case in matrix["cases"]}
    for sensitivity in matrix.get("sensitivities", []):
        expectation = sensitivity.get("expectation")
        if not expectation:
            continue
        archetype_id = sensitivity["archetype_id"]
        base_value = cases[archetype_id][sensitivity["field"]]
        values = sensitivity.get("ordered_values", sensitivity["values"])
        if base_value not in values:
            values = [*values, base_value]
        ordered = []
        for value in values:
            run_id = (
                archetype_id
                if value == base_value
                else f"{archetype_id}__{sensitivity['parameter_id']}__{_slug(value)}"
            )
            if run_id in by_run:
                ordered.append((value, float(by_run[run_id][sensitivity["metric"]])))
        if len(ordered) < 2:
            continue
        passed = _matches_expectation(
            [value for _, value in ordered],
            expectation,
            float(sensitivity.get("tolerance_ratio", 0.001)),
        )
        checks.append(
            _check(
                f"sensitivity:{sensitivity['parameter_id']}:{expectation}",
                passed,
                ", ".join(f"{value}={metric:.3f}" for value, metric in ordered),
            ),
        )
    return checks


def _matches_expectation(values: list[float], expectation: str, tolerance_ratio: float) -> bool:
    if len(values) < 2:
        return False
    scale = max(1.0, *(abs(value) for value in values))
    tolerance = scale * tolerance_ratio
    if expectation == "nonincreasing":
        return all(next_value <= value + tolerance for value, next_value in zip(values, values[1:]))
    if expectation == "nondecreasing":
        return all(next_value + tolerance >= value for value, next_value in zip(values, values[1:]))
    if expectation == "approximately_constant":
        return max(values) - min(values) <= tolerance
    raise ValueError(f"Unknown expectation: {expectation}")


def _check(check_id: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {"check_id": check_id, "status": "pass" if passed else "fail", "detail": detail}


def write_outputs(
    output_dir: str | Path,
    matrix_path: str | Path,
    matrix: dict[str, Any],
    metrics: list[dict[str, Any]],
    monthly: list[dict[str, Any]],
    sensitivities: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    errors: list[dict[str, str]],
    weather_type: str,
    weather_year: int,
    tmy_name: str,
) -> None:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    _write_csv(path / "metrics.csv", metrics)
    _write_csv(path / "monthly.csv", monthly)
    _write_csv(path / "sensitivities.csv", sensitivities)
    (path / "checks.json").write_text(
        json.dumps({"checks": checks, "errors": errors}, indent=2),
        encoding="utf-8",
    )
    matrix_bytes = Path(matrix_path).read_bytes()
    summary = {
        "schema_version": "0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine_version": THERMAL_ENGINE_VERSION,
        "matrix": str(matrix_path),
        "matrix_sha256": hashlib.sha256(matrix_bytes).hexdigest(),
        "weather_type": weather_type,
        "weather_year": weather_year if weather_type == "historical" else None,
        "tmy_name": tmy_name if weather_type == "typical" else None,
        "tariff_basis": matrix["tariff_basis"],
        "case_count": len(metrics),
        "check_count": len(checks),
        "failed_check_count": sum(check["status"] == "fail" for check in checks),
        "error_count": len(errors),
        "metrics": metrics,
        "sensitivities": sensitivities,
    }
    (path / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (path / "summary.html").write_text(
        _render_html(summary, checks, errors),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _render_html(
    summary: dict[str, Any],
    checks: list[dict[str, Any]],
    errors: list[dict[str, str]],
) -> str:
    failed = [check for check in checks if check["status"] == "fail"]
    metric_rows = "".join(
        "<tr>"
        f"<td>{escape(row['run_id'])}</td>"
        f"<td>{escape(row['city'])}, {escape(row['state'])}</td>"
        f"<td>{row['before_heating_thermal_kwh']:.0f}</td>"
        f"<td>{row['after_heating_thermal_kwh']:.0f}</td>"
        f"<td>{row['heating_demand_reduced_pct']:.1f}%</td>"
        f"<td>${row['cost_saved_usd']:.0f}</td>"
        f"<td>{row['before_peak_heating_kw']:.1f}</td>"
        f"<td>{row['before_unmet_heating_degree_hours']:.1f}</td>"
        f"<td>{escape(row['quality_flags'] or 'none')}</td>"
        "</tr>"
        for row in summary["metrics"]
        if not row["parameter_id"]
    )
    sensitivity_rows = "".join(
        "<tr>"
        f"<td>{escape(str(row['parameter_id']))}</td>"
        f"<td>{escape(str(row['parameter_value']))}</td>"
        f"<td>{row['before_heating_thermal_kwh_change_pct']:.1f}%</td>"
        f"<td>{row['heating_demand_reduced_pct']:.1f}%</td>"
        f"<td>{row['cost_saved_usd']:.0f}</td>"
        "</tr>"
        for row in summary["sensitivities"]
    )
    issue_rows = "".join(
        f"<li><strong>{escape(item.get('check_id', item.get('run_id', 'error')))}</strong>: "
        f"{escape(item.get('detail', item.get('error', '')))}</li>"
        for item in [*failed, *errors]
    ) or "<li>None</li>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>ThermalTwin model validation</title>
<style>
body{{font:15px system-ui,sans-serif;max-width:1400px;margin:32px auto;padding:0 20px;color:#17202a}}
table{{border-collapse:collapse;width:100%;margin:12px 0 28px}}th,td{{border:1px solid #d8dee4;padding:7px;text-align:right}}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){{text-align:left}}th{{background:#f3f5f7}}
.cards{{display:flex;gap:16px;flex-wrap:wrap}}.card{{background:#f3f5f7;border-radius:8px;padding:12px 18px}}
.warning{{color:#9b2c2c}}</style></head><body>
<h1>ThermalTwin model validation baseline</h1>
<p>Engine <code>{escape(summary['engine_version'])}</code> — generated {escape(summary['generated_at'])} —
weather {escape(summary['weather_type'])}. Indicative validation benchmark, not a rating or audit.</p>
<div class="cards"><div class="card"><strong>{summary['case_count']}</strong><br>runs</div>
<div class="card"><strong>{summary['check_count'] - summary['failed_check_count']}/{summary['check_count']}</strong><br>checks passed</div>
<div class="card"><strong>{summary['error_count']}</strong><br>execution errors</div></div>
<h2>Canonical cases</h2><table><thead><tr><th>Case</th><th>Location</th><th>Heat before kWh</th><th>Heat after kWh</th><th>Demand reduced</th><th>Cost saved</th><th>Peak kW</th><th>Unmet degree-hours</th><th>Quality flags</th></tr></thead><tbody>{metric_rows}</tbody></table>
<h2>One-at-a-time sensitivities</h2><table><thead><tr><th>Parameter</th><th>Value</th><th>Heating-demand change</th><th>Roof saving</th><th>Cost saved</th></tr></thead><tbody>{sensitivity_rows}</tbody></table>
<h2 class="warning">Failed checks and errors</h2><ul>{issue_rows}</ul>
<p>See <code>metrics.csv</code>, <code>monthly.csv</code>, <code>sensitivities.csv</code>, and <code>checks.json</code> for machine-readable results.</p>
</body></html>"""


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[math.ceil(percentile * len(ordered)) - 1]


def _percent_reduction(before: float, after: float) -> float:
    if abs(before) < 1e-12:
        return 0.0
    return _rounded((before - after) / before * 100.0)


def _percent_of(value: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return _rounded(value / total * 100.0)


def _relative_change(reference: float, value: float) -> float:
    if abs(reference) < 1e-12:
        return 0.0 if abs(value) < 1e-12 else 100.0
    return _rounded((value - reference) / abs(reference) * 100.0)


def _rounded(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--matrix",
        default="data/validation/us_roof_validation_matrix.json",
    )
    parser.add_argument("--output-dir", default="outputs/model_validation/current")
    parser.add_argument("--weather-type", choices=("historical", "typical"), default="historical")
    parser.add_argument("--weather-year", type=int, default=2023)
    parser.add_argument("--tmy-name", default="tmy-2024")
    parser.add_argument("--weather-dir", default="data/weather/us-validation")
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix = load_matrix(args.matrix)
    runs = expand_runs(matrix)
    if args.case_ids:
        selected = set(args.case_ids)
        runs = [run for run in runs if run["run_id"] in selected or run["archetype_id"] in selected]
    if args.limit is not None:
        runs = runs[: args.limit]

    metrics: list[dict[str, Any]] = []
    monthly: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for index, run_spec in enumerate(runs, start=1):
        print(f"[{index}/{len(runs)}] {run_spec['run_id']}", flush=True)
        answers = build_case_answers(
            run_spec["case"],
            weather_type=args.weather_type,
            weather_year=args.weather_year,
            tmy_name=args.tmy_name,
            weather_dir=args.weather_dir,
        )
        try:
            result = run_profile_experience(
                "roof_insulation_seller",
                answers,
                include_report_html=False,
            )
            annual = next(
                run for run in result["simulation_runs"] if run["role"] == "annual"
            )
            row, month_rows = extract_metrics(
                run_spec,
                annual,
                answers,
                result["resolved_dwelling"],
            )
            metrics.append(row)
            monthly.extend(month_rows)
        except Exception as exc:  # continue to expose the whole matrix
            errors.append({"run_id": run_spec["run_id"], "error": str(exc)})
            print(f"  ERROR: {exc}", file=sys.stderr, flush=True)

    sensitivities = build_sensitivity_rows(metrics, matrix) if metrics else []
    checks = evaluate_checks(metrics, matrix) if metrics else []
    write_outputs(
        args.output_dir,
        args.matrix,
        matrix,
        metrics,
        monthly,
        sensitivities,
        checks,
        errors,
        args.weather_type,
        args.weather_year,
        args.tmy_name,
    )
    print(
        f"Wrote {len(metrics)} runs to {args.output_dir}; "
        f"{sum(check['status'] == 'fail' for check in checks)} failed checks, "
        f"{len(errors)} execution errors.",
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
