"""Open-Meteo ingestion and ThermalTwin weather conversion helpers."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any
import unicodedata


FRENCH_KEY_CITIES: dict[str, tuple[float, float]] = {
    "Paris": (48.8566, 2.3522),
    "Lyon": (45.7640, 4.8357),
    "Marseille": (43.2965, 5.3698),
    "Bordeaux": (44.8378, -0.5792),
    "Lille": (50.6292, 3.0573),
    "Nantes": (47.2184, -1.5536),
    "Toulouse": (43.6047, 1.4442),
    "Strasbourg": (48.5734, 7.7521),
    "Grenoble": (45.1885, 5.7245),
    "Rennes": (48.1173, -1.6778),
    "Nice": (43.7102, 7.2620),
    "Montpellier": (43.6110, 3.8767),
    "Toulon": (43.1242, 5.9280),
    "Ajaccio": (41.9192, 8.7386),
    "Bastia": (42.6973, 9.4509),
    "Brest": (48.3904, -4.4861),
    "Dijon": (47.3220, 5.0415),
    "Clermont-Ferrand": (45.7772, 3.0870),
    "Limoges": (45.8336, 1.2611),
    "Tours": (47.3941, 0.6848),
    "Orléans": (47.9029, 1.9093),
    "Caen": (49.1829, -0.3707),
    "Rouen": (49.4431, 1.0993),
    "Nancy": (48.6921, 6.1844),
    "Metz": (49.1193, 6.1757),
    "Perpignan": (42.6887, 2.8948),
    "Pau": (43.2951, -0.3708),
    "Bayonne": (43.4929, -1.4748),
    "Biarritz": (43.4832, -1.5586),
}

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

OPEN_METEO_HOURLY_VARIABLES = [
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "dew_point_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "direct_normal_irradiance",
]

DEPARTMENT_WEATHER_CITY = {
    "01": "Lyon",
    "02": "Paris",
    "03": "Lyon",
    "04": "Marseille",
    "05": "Grenoble",
    "06": "Nice",
    "07": "Lyon",
    "08": "Strasbourg",
    "09": "Toulouse",
    "10": "Paris",
    "11": "Montpellier",
    "12": "Toulouse",
    "13": "Marseille",
    "14": "Caen",
    "15": "Lyon",
    "16": "Bordeaux",
    "17": "Bordeaux",
    "18": "Orléans",
    "19": "Limoges",
    "2A": "Ajaccio",
    "2B": "Bastia",
    "21": "Dijon",
    "22": "Rennes",
    "23": "Bordeaux",
    "24": "Bordeaux",
    "25": "Dijon",
    "26": "Grenoble",
    "27": "Rouen",
    "28": "Orléans",
    "29": "Brest",
    "30": "Montpellier",
    "31": "Toulouse",
    "32": "Toulouse",
    "33": "Bordeaux",
    "34": "Montpellier",
    "35": "Rennes",
    "36": "Tours",
    "37": "Tours",
    "38": "Grenoble",
    "39": "Dijon",
    "40": "Bordeaux",
    "41": "Nantes",
    "42": "Lyon",
    "43": "Lyon",
    "44": "Nantes",
    "45": "Orléans",
    "46": "Toulouse",
    "47": "Bordeaux",
    "48": "Montpellier",
    "49": "Nantes",
    "50": "Caen",
    "51": "Metz",
    "52": "Nancy",
    "53": "Nantes",
    "54": "Nancy",
    "55": "Nancy",
    "56": "Rennes",
    "57": "Metz",
    "58": "Dijon",
    "59": "Lille",
    "60": "Paris",
    "61": "Caen",
    "62": "Lille",
    "63": "Clermont-Ferrand",
    "64": "Pau",
    "65": "Pau",
    "66": "Perpignan",
    "67": "Strasbourg",
    "68": "Strasbourg",
    "69": "Lyon",
    "70": "Dijon",
    "71": "Dijon",
    "72": "Tours",
    "73": "Grenoble",
    "74": "Grenoble",
    "75": "Paris",
    "76": "Rouen",
    "77": "Paris",
    "78": "Paris",
    "79": "Tours",
    "80": "Lille",
    "81": "Toulouse",
    "82": "Toulouse",
    "83": "Toulon",
    "84": "Marseille",
    "85": "Nantes",
    "86": "Nantes",
    "87": "Limoges",
    "88": "Nancy",
    "89": "Dijon",
    "90": "Strasbourg",
    "91": "Paris",
    "92": "Paris",
    "93": "Paris",
    "94": "Paris",
    "95": "Paris",
}

CLIMATE_ZONE_WEATHER_CITY = {
    "FR_H1a": "Lille",
    "FR_H1b": "Strasbourg",
    "FR_H1c": "Lyon",
    "FR_H2a": "Rennes",
    "FR_H2b": "Nantes",
    "FR_H2c": "Bordeaux",
    "FR_H2d": "Toulouse",
    "FR_H3": "Marseille",
}


def city_coordinates(city: str) -> tuple[float, float]:
    """Return coordinates for a supported French key city."""
    try:
        return FRENCH_KEY_CITIES[city]
    except KeyError as exc:
        supported = ", ".join(sorted(FRENCH_KEY_CITIES))
        raise ValueError(f"unknown city '{city}'. Supported cities: {supported}") from exc


def city_slug(city: str) -> str:
    """Return the filename slug used for generated weather assets."""
    return _normalize_city(city).replace(" ", "_")


def resolve_weather_city(
    city: str | None,
    postal_code: str | None = None,
    climate_zone_id: str | None = None,
) -> dict[str, str]:
    """Map a user city/postal code/zone to the closest supported weather city."""
    normalized_city = _normalize_city(city or "")
    supported_by_normalized = {
        _normalize_city(supported_city): supported_city
        for supported_city in FRENCH_KEY_CITIES
    }
    if normalized_city in supported_by_normalized:
        resolved_city = supported_by_normalized[normalized_city]
        return {
            "requested_city": city or resolved_city,
            "weather_city": resolved_city,
            "match_mode": "exact_city",
        }

    department_code = _department_code(postal_code or "")
    if department_code in DEPARTMENT_WEATHER_CITY:
        return {
            "requested_city": city or "",
            "weather_city": DEPARTMENT_WEATHER_CITY[department_code],
            "match_mode": "department",
        }

    if climate_zone_id in CLIMATE_ZONE_WEATHER_CITY:
        return {
            "requested_city": city or "",
            "weather_city": CLIMATE_ZONE_WEATHER_CITY[climate_zone_id],
            "match_mode": "climate_zone",
        }

    return {
        "requested_city": city or "",
        "weather_city": "Paris",
        "match_mode": "default",
    }


def thermal_weather_ref(
    city: str,
    year: int,
    *,
    output_dir: str | Path = "data/weather/openmeteo",
) -> str:
    """Return the standard ThermalTwin weather JSON path for one city/year."""
    return str(Path(output_dir) / "thermal" / f"{city_slug(city)}_{year}.weather.json")


def ensure_openmeteo_thermal_weather(
    city: str,
    year: int,
    *,
    output_dir: str | Path = "data/weather/openmeteo",
    model: str = "era5_seamless",
    cache_dir: str | Path = ".cache/openmeteo",
) -> Path:
    """Create the standard Parquet and ThermalTwin weather files when missing."""
    weather_path = Path(thermal_weather_ref(city, year, output_dir=output_dir))
    if weather_path.exists():
        return weather_path

    dataframe = fetch_open_meteo_year(
        city,
        year,
        model=model,
        cache_dir=cache_dir,
    )
    raw_path = Path(output_dir) / "raw" / f"{city_slug(city)}_{year}.parquet"
    write_parquet(dataframe, raw_path)
    annual_dataframe = combine_weather_years([dataframe], "latest")
    weather = build_thermal_weather(
        annual_dataframe,
        source=f"openmeteo_{model}_{city_slug(city)}_{year}",
    )
    write_thermal_weather_json(weather, weather_path)
    return weather_path


def fetch_open_meteo_year(
    city: str,
    year: int,
    *,
    model: str = "era5_seamless",
    timezone: str = "Europe/Paris",
    cache_dir: str | Path = ".cache/openmeteo",
) -> Any:
    """Fetch one city/year from Open-Meteo and return a pandas DataFrame."""
    pd, openmeteo_requests, requests_cache, retry = _weather_dependencies()
    latitude, longitude = city_coordinates(city)
    cache_session = requests_cache.CachedSession(str(cache_dir), expire_after=-1)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    client = openmeteo_requests.Client(session=retry_session)
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "hourly": OPEN_METEO_HOURLY_VARIABLES,
        "timezone": timezone,
        "models": model,
    }

    responses = client.weather_api(OPEN_METEO_ARCHIVE_URL, params=params)
    response = responses[0]
    hourly = response.Hourly()
    datetimes = pd.date_range(
        start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
        end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=hourly.Interval()),
        inclusive="left",
    ).tz_convert(timezone)

    data = {"datetime": datetimes}
    for index, variable in enumerate(OPEN_METEO_HOURLY_VARIABLES):
        data[variable] = hourly.Variables(index).ValuesAsNumpy()
    data["city"] = city
    data["latitude"] = latitude
    data["longitude"] = longitude
    data["source_model"] = model
    return pd.DataFrame(data)


def write_parquet(dataframe: Any, output_path: str | Path) -> Path:
    """Write weather rows as Parquet and return the path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_parquet(path, index=False)
    return path


def read_parquet(path: str | Path) -> Any:
    """Read a Parquet weather file."""
    pd, *_ = _weather_dependencies(require_openmeteo=False)
    return pd.read_parquet(path)


def combine_weather_years(dataframes: list[Any], mode: str) -> Any:
    """Return one annual DataFrame from one or several year DataFrames."""
    if not dataframes:
        raise ValueError("at least one weather DataFrame is required")
    if mode == "latest":
        return _non_leap_year(dataframes[-1]).reset_index(drop=True)
    if mode != "mean":
        raise ValueError("mode must be 'latest' or 'mean'")

    pd, *_ = _weather_dependencies(require_openmeteo=False)
    prepared = []
    for dataframe in dataframes:
        annual = _non_leap_year(dataframe).copy()
        annual["month"] = annual["datetime"].dt.month
        annual["day"] = annual["datetime"].dt.day
        annual["hour_of_day"] = annual["datetime"].dt.hour
        prepared.append(annual)

    merged = pd.concat(prepared, ignore_index=True)
    numeric_columns = [
        column
        for column in OPEN_METEO_HOURLY_VARIABLES
        if column in merged.columns
    ]
    averaged = (
        merged.groupby(["month", "day", "hour_of_day"], as_index=False)[numeric_columns]
        .mean()
        .sort_values(["month", "day", "hour_of_day"])
        .reset_index(drop=True)
    )
    city = str(merged["city"].iloc[0]) if "city" in merged else ""
    averaged["city"] = city
    averaged["datetime"] = pd.date_range(
        "2001-01-01 00:00",
        periods=len(averaged),
        freq="h",
        tz=merged["datetime"].dt.tz,
    )
    return averaged


def build_thermal_weather(
    dataframe: Any,
    *,
    source: str,
    solar_mode: str = "mvp_orientation",
) -> dict[str, Any]:
    """Convert an Open-Meteo DataFrame to the scenario weather object."""
    if solar_mode != "mvp_orientation":
        raise ValueError("only solar_mode='mvp_orientation' is supported")

    hourly = []
    for hour, row in enumerate(dataframe.sort_values("datetime").to_dict("records")):
        hourly.append(
            {
                "hour": hour,
                "month": int(row["datetime"].month),
                "outdoor_temperature_c": round(float(row["temperature_2m"]), 2),
                "solar_irradiance_w_m2": _orientation_irradiance(row),
            }
        )
    return {
        "source": source,
        "hourly": hourly,
    }


def write_thermal_weather_json(weather: dict[str, Any], output_path: str | Path) -> Path:
    """Write a ThermalTwin weather object as JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(weather, file, indent=2)
    return path


def _orientation_irradiance(row: dict[str, Any]) -> dict[str, float]:
    shortwave = _non_negative(row.get("shortwave_radiation", 0.0))
    direct = _non_negative(row.get("direct_radiation", 0.0))
    diffuse = _non_negative(row.get("diffuse_radiation", 0.0))
    hour = row["datetime"].hour
    east_weight = _solar_window_weight(hour, 5, 12)
    south_weight = _solar_window_weight(hour, 8, 16)
    west_weight = _solar_window_weight(hour, 12, 19)
    return {
        "north": round(diffuse * 0.35, 2),
        "east": round(diffuse * 0.5 + direct * east_weight, 2),
        "south": round(diffuse * 0.6 + direct * south_weight, 2),
        "west": round(diffuse * 0.5 + direct * west_weight, 2),
        "roof": round(shortwave, 2),
    }


def _solar_window_weight(hour: int, start_hour: int, end_hour: int) -> float:
    if hour < start_hour or hour > end_hour:
        return 0.0
    span = end_hour - start_hour
    return max(0.0, math.sin(math.pi * (hour - start_hour) / span))


def _non_negative(value: Any) -> float:
    if value is None:
        return 0.0
    number = float(value)
    if math.isnan(number):
        return 0.0
    return max(0.0, number)


def _non_leap_year(dataframe: Any) -> Any:
    datetimes = dataframe["datetime"]
    return dataframe.loc[~((datetimes.dt.month == 2) & (datetimes.dt.day == 29))]


def _normalize_city(city: str) -> str:
    ascii_city = unicodedata.normalize("NFKD", city).encode("ascii", "ignore").decode()
    return " ".join(ascii_city.lower().replace("-", " ").split())


def _department_code(postal_code: str) -> str:
    cleaned = postal_code.strip().upper()
    if cleaned.startswith(("2A", "2B")):
        return cleaned[:2]
    digits = "".join(character for character in cleaned if character.isdigit())
    return digits[:2]


def _weather_dependencies(require_openmeteo: bool = True) -> tuple[Any, Any, Any, Any]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Install pandas and pyarrow to use weather ingestion") from exc

    if not require_openmeteo:
        return pd, None, None, None

    try:
        import openmeteo_requests
        import requests_cache
        from retry_requests import retry
    except ImportError as exc:
        raise RuntimeError(
            "Install openmeteo-requests requests-cache retry-requests pandas pyarrow "
            "to fetch Open-Meteo weather"
        ) from exc

    return pd, openmeteo_requests, requests_cache, retry
