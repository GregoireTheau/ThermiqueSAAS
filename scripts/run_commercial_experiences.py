#!/usr/bin/env python3
"""Run all current commercial before/after experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from thermal_model import (  # noqa: E402
    compare_scenarios,
    load_dwelling,
    load_reference_catalog,
    load_scenario,
    resolve_dwelling_references,
)


EXPERIMENTS = [
    {
        "name": "commercial_roof_heatwave_3d",
        "before": "data/examples/scenario_commercial_roof_heatwave_3d_before.json",
        "after": "data/examples/scenario_commercial_roof_heatwave_3d_after.json",
    },
    {
        "name": "commercial_window_shutter_summer",
        "before": "data/examples/scenario_commercial_window_shutter_summer_before.json",
        "after": "data/examples/scenario_commercial_window_shutter_summer_after.json",
    },
    {
        "name": "commercial_pac_winter_7d",
        "before": "data/examples/scenario_commercial_pac_winter_7d_before.json",
        "after": "data/examples/scenario_commercial_pac_winter_7d_after.json",
    },
]


def write_comparison_json(output_path: str | Path, comparison: dict[str, Any]) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(comparison, file, indent=2, ensure_ascii=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run all current commercial before/after experiments.",
    )
    parser.add_argument(
        "--dwelling-path",
        default="data/examples/house_simple.json",
        help="Path to the dwelling JSON file.",
    )
    parser.add_argument(
        "--reference-dir",
        default="data/reference",
        help="Path to the reference data directory.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/commercial_experiences",
        help="Directory where comparison JSON files are written.",
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


def main() -> None:
    args = parse_args()
    catalog = load_reference_catalog(args.reference_dir)
    dwelling = load_dwelling(args.dwelling_path, validate=False)
    dwelling = resolve_dwelling_references(dwelling, catalog)
    output_dir = Path(args.output_dir)

    for experiment in EXPERIMENTS:
        before_scenario = load_scenario(experiment["before"])
        after_scenario = load_scenario(experiment["after"])

        if before_scenario["dwelling_id"] != dwelling["dwelling_id"]:
            raise ValueError(f"{experiment['before']} dwelling_id does not match dwelling")
        if after_scenario["dwelling_id"] != dwelling["dwelling_id"]:
            raise ValueError(f"{experiment['after']} dwelling_id does not match dwelling")

        comparison = compare_scenarios(
            dwelling,
            before_scenario,
            after_scenario,
            args.air_density_kg_m3,
            args.air_heat_capacity_j_kgk,
        )
        output_path = output_dir / f"{experiment['name']}.json"
        write_comparison_json(output_path, comparison)
        print(f"{experiment['name']}: {output_path}")


if __name__ == "__main__":
    main()
