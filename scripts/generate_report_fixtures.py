#!/usr/bin/env python3
"""Generate report outputs from fixed dwellings without interactive input."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import create_customer_experience as customer_experience  # noqa: E402
from thermal_model import (  # noqa: E402
    build_report_model,
    compare_scenarios,
    load_dwelling,
    load_reference_catalog,
    render_report_html,
    resolve_dwelling_references,
    validate_dwelling,
    validate_scenario,
)


DEFAULT_ADAPTATIONS = [
    "reflective_roof",
    "better_windows",
    "solar_protection",
    "heat_pump",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate before/after comparisons and report HTML from a fixed "
            "dwelling fixture."
        ),
    )
    parser.add_argument(
        "--dwelling-path",
        default="data/examples/apartment_two_rooms.json",
        help="Path to the dwelling fixture JSON.",
    )
    parser.add_argument(
        "--reference-dir",
        default="data/reference",
        help="Path to the reference data directory.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/report_fixtures",
        help="Directory where generated fixture outputs are written.",
    )
    parser.add_argument(
        "--adaptation",
        action="append",
        choices=[change["id"] for change in customer_experience.CHANGES],
        help=(
            "Adaptation to generate. Can be passed multiple times. Defaults "
            "to a representative set covering roof, windows, shutters and PAC."
        ),
    )
    parser.add_argument(
        "--target-scope",
        default="all",
        help="Target room id or 'all'. Defaults to all rooms.",
    )
    parser.add_argument(
        "--air-density-kg-m3",
        type=float,
        default=1.2,
        help="Air density used for ventilation losses.",
    )
    parser.add_argument(
        "--air-heat-capacity-j-kgk",
        type=float,
        default=1005.0,
        help="Air heat capacity used for ventilation losses.",
    )
    return parser.parse_args()


def find_change(change_id: str) -> dict[str, Any]:
    return next(
        change
        for change in customer_experience.CHANGES
        if change["id"] == change_id
    )


def write_json(output_path: str | Path, payload: dict[str, Any]) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def write_text(output_path: str | Path, content: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate_report_fixtures(args: argparse.Namespace) -> list[Path]:
    catalog = load_reference_catalog(args.reference_dir)
    dwelling = load_dwelling(args.dwelling_path, validate=False)
    validate_dwelling(dwelling)
    resolved_dwelling = resolve_dwelling_references(dwelling, catalog)
    output_dir = Path(args.output_dir) / dwelling["dwelling_id"]
    output_paths = []

    write_json(output_dir / "dwelling.json", dwelling)
    adaptation_ids = args.adaptation or DEFAULT_ADAPTATIONS
    for adaptation_id in adaptation_ids:
        customer = {
            "change": find_change(adaptation_id),
            "target_scope": args.target_scope,
        }
        experiments = customer_experience.build_experiments(
            customer,
            resolved_dwelling,
            catalog,
        )
        if not experiments:
            print(f"{adaptation_id}: no applicable experiment for target {args.target_scope}")
            continue

        for experiment in experiments:
            before = experiment["before"]
            after = experiment["after"]
            validate_scenario(before)
            validate_scenario(after)

            before_path = output_dir / f"{experiment['id']}_before.json"
            after_path = output_dir / f"{experiment['id']}_after.json"
            comparison_path = output_dir / f"{experiment['id']}_comparison.json"
            report_path = output_dir / f"{experiment['id']}_comparison_report.json"
            html_path = output_dir / f"{experiment['id']}_report.html"
            summary_path = output_dir / f"{experiment['id']}_customer_summary.json"

            comparison = compare_scenarios(
                resolved_dwelling,
                before,
                after,
                args.air_density_kg_m3,
                args.air_heat_capacity_j_kgk,
            )
            report = build_report_model(comparison)
            customer_summary = customer_experience.build_customer_summary(
                experiment["season"],
                comparison,
            )

            write_json(before_path, before)
            write_json(after_path, after)
            write_json(comparison_path, comparison)
            write_json(report_path, report)
            write_text(html_path, render_report_html(report))
            write_json(summary_path, customer_summary)
            output_paths.append(html_path)
            print(f"{experiment['id']}: {html_path}")

    return output_paths


def main() -> None:
    generate_report_fixtures(parse_args())


if __name__ == "__main__":
    main()
