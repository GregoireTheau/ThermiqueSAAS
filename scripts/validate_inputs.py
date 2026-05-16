#!/usr/bin/env python3
"""Validate ThermalTwin JSON inputs against JSON Schema and domain loaders."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from jsonschema import Draft202012Validator  # noqa: E402

from thermal_model import (  # noqa: E402
    load_dwelling,
    load_scenario,
    validate_dwelling,
    validate_scenario,
)


DEFAULT_DWELLING_SCHEMA = PROJECT_ROOT / "schemas" / "dwelling.schema.json"
DEFAULT_SCENARIO_SCHEMA = PROJECT_ROOT / "schemas" / "scenario.schema.json"


def validate_json_schema(
    data_path: str | Path,
    schema_path: str | Path,
) -> None:
    """Validate a JSON document against a JSON Schema file."""
    data = _load_json(data_path)
    schema = _load_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda error: error.path)
    if errors:
        messages = []
        for error in errors:
            path = ".".join(str(part) for part in error.path) or "<root>"
            messages.append(f"{path}: {error.message}")
        raise ValueError("\n".join(messages))


def validate_dwelling_file(path: str | Path, schema_path: str | Path) -> None:
    """Validate dwelling schema and domain constraints."""
    validate_json_schema(path, schema_path)
    dwelling = load_dwelling(path, validate=False)
    validate_dwelling(dwelling)


def validate_scenario_file(path: str | Path, schema_path: str | Path) -> None:
    """Validate scenario schema and domain constraints."""
    validate_json_schema(path, schema_path)
    scenario = load_scenario(path, validate=False)
    validate_scenario(scenario)


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate ThermalTwin dwelling and scenario JSON files.",
    )
    parser.add_argument(
        "--dwelling",
        default="data/examples/house_simple.json",
        help="Path to dwelling JSON file.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Path to scenario JSON file. Can be repeated.",
    )
    parser.add_argument(
        "--dwelling-schema",
        default=str(DEFAULT_DWELLING_SCHEMA),
        help="Path to dwelling JSON Schema.",
    )
    parser.add_argument(
        "--scenario-schema",
        default=str(DEFAULT_SCENARIO_SCHEMA),
        help="Path to scenario JSON Schema.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    validate_dwelling_file(args.dwelling, args.dwelling_schema)
    print(f"dwelling ok: {args.dwelling}")

    for scenario_path in args.scenario:
        validate_scenario_file(scenario_path, args.scenario_schema)
        print(f"scenario ok: {scenario_path}")


if __name__ == "__main__":
    main()
