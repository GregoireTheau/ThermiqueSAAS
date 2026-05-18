#!/usr/bin/env python3
"""Build a client report model from a comparison JSON file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from thermal_model import build_report_model, render_report_html  # noqa: E402


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file)


def write_json(output_path: str | Path, payload: dict[str, Any]) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def write_text(output_path: str | Path, content: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a client report model from a ThermalTwin comparison JSON.",
    )
    parser.add_argument(
        "comparison_path",
        help="Path to the comparison JSON file.",
    )
    parser.add_argument(
        "--output-json",
        help="Optional output path. Defaults to <comparison>_report.json.",
    )
    parser.add_argument(
        "--output-html",
        help="Optional output path for the standalone HTML report.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    comparison_path = Path(args.comparison_path)
    json_output_path = (
        Path(args.output_json)
        if args.output_json
        else comparison_path.with_name(f"{comparison_path.stem}_report.json")
    )
    report = build_report_model(load_json(comparison_path))
    write_json(json_output_path, report)
    print(f"Report model: {json_output_path}")
    if args.output_html:
        html_output_path = Path(args.output_html)
        write_text(html_output_path, render_report_html(report))
        print(f"HTML report: {html_output_path}")


if __name__ == "__main__":
    main()
