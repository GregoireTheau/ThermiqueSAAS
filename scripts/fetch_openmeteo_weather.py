#!/usr/bin/env python3
"""Fetch Open-Meteo weather for French key cities and export ThermalTwin weather."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from thermal_model import (  # noqa: E402
    FRENCH_KEY_CITIES,
    build_thermal_weather,
    combine_weather_years,
    fetch_open_meteo_year,
    write_parquet,
    write_thermal_weather_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch annual Open-Meteo weather and convert it for ThermalTwin.",
    )
    parser.add_argument(
        "--year",
        dest="years",
        type=int,
        action="append",
        required=True,
        help="Year to fetch. Repeat to fetch several years.",
    )
    parser.add_argument(
        "--city",
        dest="cities",
        action="append",
        choices=["all", *sorted(FRENCH_KEY_CITIES)],
        default=[],
        help="City to fetch. Repeat for several cities, or use all.",
    )
    parser.add_argument(
        "--mode",
        choices=["latest", "mean"],
        default="latest",
        help="latest keeps the most recent fetched year; mean averages all years.",
    )
    parser.add_argument(
        "--model",
        default="era5_seamless",
        help="Open-Meteo model name.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/weather/openmeteo",
        help="Output directory for raw parquet and ThermalTwin weather JSON.",
    )
    parser.add_argument(
        "--cache-dir",
        default=".cache/openmeteo",
        help="HTTP cache directory for Open-Meteo requests.",
    )
    return parser.parse_args()


def selected_cities(args: argparse.Namespace) -> list[str]:
    if not args.cities or "all" in args.cities:
        return sorted(FRENCH_KEY_CITIES)
    return args.cities


def city_slug(city: str) -> str:
    return city.lower().replace(" ", "_")


def main() -> None:
    args = parse_args()
    years = sorted(set(args.years))
    output_dir = Path(args.output_dir)
    raw_dir = output_dir / "raw"
    thermal_dir = output_dir / "thermal"

    for city in selected_cities(args):
        yearly_dataframes = []
        for year in years:
            print(f"Recuperation Open-Meteo: {city} {year}")
            dataframe = fetch_open_meteo_year(
                city,
                year,
                model=args.model,
                cache_dir=args.cache_dir,
            )
            yearly_dataframes.append(dataframe)
            raw_path = raw_dir / f"{city_slug(city)}_{year}.parquet"
            write_parquet(dataframe, raw_path)
            print(f"  parquet brut: {raw_path}")

        annual_dataframe = combine_weather_years(yearly_dataframes, args.mode)
        label = str(years[-1]) if args.mode == "latest" else f"{years[0]}_{years[-1]}_mean"
        source = f"openmeteo_{args.model}_{city_slug(city)}_{label}"
        weather = build_thermal_weather(annual_dataframe, source=source)
        weather_path = thermal_dir / f"{city_slug(city)}_{label}.weather.json"
        write_thermal_weather_json(weather, weather_path)
        print(f"  meteo ThermalTwin: {weather_path}")


if __name__ == "__main__":
    main()
