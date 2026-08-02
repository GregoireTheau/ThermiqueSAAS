"""Open-Meteo ingestion and ThermalTwin weather conversion helpers."""

from __future__ import annotations

import json
import math
import csv
import io
import os
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from pathlib import Path
from typing import Any
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


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
NLR_NSRDB_TMY_URL = (
    "https://developer.nlr.gov/api/nsrdb/v2/solar/"
    "nsrdb-GOES-tmy-v4-0-0-download.csv"
)
NLR_NSRDB_POLAR_TMY_URL = (
    "https://developer.nlr.gov/api/nsrdb/v2/solar/"
    "nsrdb-polar-tmy-v4-0-0-download.csv"
)
DEFAULT_NSRDB_TMY_NAME = "tmy-2024"
US_WEATHER_GRID_DEGREES = Decimal("0.1")

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

WEATHER_DATA_SCHEMA_VERSION = "0.2"
THERMAL_ENGINE_VERSION = "1r1c-mvp-0.1"

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
) -> dict[str, str]:
    """Map legacy French input to a supported city without climate-zone fallback."""
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

    raise ValueError(
        "A supported city or postal-code mapping is required; climate zones do not select weather.",
    )


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


def us_weather_ref(
    location: dict[str, Any],
    weather_type: str,
    *,
    year: int | None = None,
    tmy_name: str = DEFAULT_NSRDB_TMY_NAME,
    output_dir: str | Path = "data/weather/us",
) -> str:
    """Return the immutable weather path for a canonical US weather cell."""
    latitude, longitude = _weather_grid_coordinates(location)
    timezone_slug = _timezone_slug(location.get("timezone"))
    suffix = str(year) if weather_type == "historical" else tmy_name
    filename = (
        f"{latitude:.1f}_{longitude:.1f}_{timezone_slug}_"
        f"{weather_type}_{suffix}.weather.json"
    )
    return str(Path(output_dir) / "thermal" / filename)


def ensure_us_thermal_weather(
    location: dict[str, Any],
    weather_type: str,
    *,
    year: int | None = None,
    tmy_name: str = DEFAULT_NSRDB_TMY_NAME,
    output_dir: str | Path = "data/weather/us",
    openmeteo_model: str = "era5_seamless",
    cache_dir: str | Path = ".cache/openmeteo",
) -> Path:
    """Download and cache historical Open-Meteo or NSRDB TMY weather."""
    if weather_type not in {"historical", "typical"}:
        raise ValueError("weather_type must be 'historical' or 'typical'")
    if weather_type == "historical" and year is None:
        raise ValueError("year is required for historical weather")

    weather_path = Path(
        us_weather_ref(
            location,
            weather_type,
            year=year,
            tmy_name=tmy_name,
            output_dir=output_dir,
        ),
    )
    if weather_path.exists():
        return weather_path

    grid_latitude, grid_longitude = _weather_grid_coordinates(location)
    weather_location = {
        **location,
        "latitude": grid_latitude,
        "longitude": grid_longitude,
    }

    if weather_type == "historical":
        dataframe = fetch_open_meteo_coordinates(
            grid_latitude,
            grid_longitude,
            int(year),
            model=openmeteo_model,
            timezone_name=str(location["timezone"]),
            cache_dir=cache_dir,
        )
        raw_path = Path(output_dir) / "raw" / weather_path.name.replace(
            ".weather.json",
            ".parquet",
        )
        write_parquet(dataframe, raw_path)
        metadata = _weather_metadata(
            weather_location,
            weather_type="historical",
            provider="Open-Meteo",
            dataset="Historical weather archive",
            model=openmeteo_model,
            year=int(year),
            station=f"Open-Meteo grid {grid_latitude:.1f}, {grid_longitude:.1f}",
        )
        source = f"openmeteo_{openmeteo_model}_{year}"
    else:
        dataframe, nsrdb_metadata, raw_csv = fetch_nsrdb_tmy(
            weather_location,
            tmy_name=tmy_name,
        )
        raw_path = Path(output_dir) / "raw" / weather_path.name.replace(
            ".weather.json",
            ".csv",
        )
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw_csv, encoding="utf-8")
        metadata = _weather_metadata(
            weather_location,
            weather_type="typical",
            provider="NLR NSRDB",
            dataset="GOES Typical Meteorological Year PSM v4",
            model=str(nsrdb_metadata.get("Version", "PSM v4")),
            year=None,
            station=str(
                nsrdb_metadata.get("Location ID")
                or nsrdb_metadata.get("Site ID")
                or f"NSRDB grid {grid_latitude:.1f}, {grid_longitude:.1f}"
            ),
            weather_reference=tmy_name,
            source_latitude=_metadata_float(nsrdb_metadata, "Latitude"),
            source_longitude=_metadata_float(nsrdb_metadata, "Longitude"),
        )
        source = f"nsrdb_goes_tmy_v4_{tmy_name}"

    annual_dataframe = combine_weather_years([dataframe], "latest")
    weather = build_thermal_weather(
        annual_dataframe,
        source=source,
        metadata=metadata,
    )
    write_thermal_weather_json(weather, weather_path)
    return weather_path


def fetch_open_meteo_coordinates(
    latitude: float,
    longitude: float,
    year: int,
    *,
    model: str = "era5_seamless",
    timezone_name: str,
    cache_dir: str | Path = ".cache/openmeteo",
) -> Any:
    """Fetch one historical year for exact coordinates."""
    return _fetch_open_meteo(
        latitude,
        longitude,
        year,
        model=model,
        timezone_name=timezone_name,
        cache_dir=cache_dir,
        location_label=f"{latitude:.4f},{longitude:.4f}",
    )


def fetch_nsrdb_tmy(
    location: dict[str, Any],
    *,
    tmy_name: str = DEFAULT_NSRDB_TMY_NAME,
) -> tuple[Any, dict[str, str], str]:
    """Download one pinned NSRDB TMY CSV and convert it to the weather frame shape."""
    api_key = os.environ.get("THERMAL_NSRDB_API_KEY", "").strip()
    email = os.environ.get("THERMAL_NSRDB_EMAIL", "").strip()
    if not api_key or not email:
        raise RuntimeError(
            "Typical weather requires THERMAL_NSRDB_API_KEY and THERMAL_NSRDB_EMAIL.",
        )
    latitude = float(location["latitude"])
    longitude = float(location["longitude"])
    endpoint = NLR_NSRDB_POLAR_TMY_URL if latitude >= 60.0 else NLR_NSRDB_TMY_URL
    params = {
        "api_key": api_key,
        "wkt": f"POINT({longitude} {latitude})",
        "attributes": "air_temperature,ghi,dhi,dni",
        "names": tmy_name,
        "utc": "false",
        "leap_day": "false",
        "interval": 60,
        "full_name": os.environ.get("THERMAL_NSRDB_FULL_NAME", "ThermalTwin"),
        "email": email,
        "affiliation": os.environ.get("THERMAL_NSRDB_AFFILIATION", "ThermalTwin"),
        "mailing_list": "false",
        "reason": "Building thermal simulation",
    }
    try:
        with urlopen(f"{endpoint}?{urlencode(params)}", timeout=60) as response:  # noqa: S310
            raw_csv = response.read().decode("utf-8-sig")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError("NSRDB typical weather is temporarily unavailable.") from exc
    return _parse_nsrdb_csv(raw_csv, location), _parse_nsrdb_metadata(raw_csv), raw_csv


def fetch_open_meteo_year(
    city: str,
    year: int,
    *,
    model: str = "era5_seamless",
    timezone: str = "Europe/Paris",
    cache_dir: str | Path = ".cache/openmeteo",
) -> Any:
    """Fetch one city/year from Open-Meteo and return a pandas DataFrame."""
    latitude, longitude = city_coordinates(city)
    return _fetch_open_meteo(
        latitude,
        longitude,
        year,
        model=model,
        timezone_name=timezone,
        cache_dir=cache_dir,
        location_label=city,
    )


def _fetch_open_meteo(
    latitude: float,
    longitude: float,
    year: int,
    *,
    model: str,
    timezone_name: str,
    cache_dir: str | Path,
    location_label: str,
) -> Any:
    pd, openmeteo_requests, requests_cache, retry = _weather_dependencies()
    cache_session = requests_cache.CachedSession(str(cache_dir), expire_after=-1)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    client = openmeteo_requests.Client(session=retry_session)
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "hourly": OPEN_METEO_HOURLY_VARIABLES,
        "timezone": timezone_name,
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
    ).tz_convert(timezone_name)

    data = {"datetime": datetimes}
    for index, variable in enumerate(OPEN_METEO_HOURLY_VARIABLES):
        data[variable] = hourly.Variables(index).ValuesAsNumpy()
    data["city"] = location_label
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
    metadata: dict[str, Any] | None = None,
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
    weather = {
        "schema_version": WEATHER_DATA_SCHEMA_VERSION,
        "source": source,
        "hourly": hourly,
    }
    if metadata:
        weather["metadata"] = {
            **metadata,
            "hourly_sha256": sha256(
                json.dumps(hourly, separators=(",", ":"), sort_keys=True).encode(),
            ).hexdigest(),
        }
    return weather


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


def _parse_nsrdb_metadata(raw_csv: str) -> dict[str, str]:
    rows = list(csv.reader(io.StringIO(raw_csv)))
    if len(rows) < 3:
        raise RuntimeError("NSRDB returned an incomplete CSV file.")
    return dict(zip(rows[0], rows[1]))


def _parse_nsrdb_csv(raw_csv: str, location: dict[str, Any]) -> Any:
    pd, *_ = _weather_dependencies(require_openmeteo=False)
    metadata = _parse_nsrdb_metadata(raw_csv)
    dataframe = pd.read_csv(io.StringIO(raw_csv), skiprows=2)
    required = {"Year", "Month", "Day", "Hour", "Minute", "GHI", "DHI"}
    missing = sorted(required - set(dataframe.columns))
    if missing:
        raise RuntimeError(f"NSRDB CSV is missing columns: {', '.join(missing)}")
    temperature_column = next(
        (column for column in ("Temperature", "Air Temperature") if column in dataframe),
        None,
    )
    if not temperature_column:
        raise RuntimeError("NSRDB CSV is missing air temperature.")
    dataframe["datetime"] = pd.to_datetime(
        {
            "year": [2001] * len(dataframe),
            "month": dataframe["Month"],
            "day": dataframe["Day"],
            "hour": dataframe["Hour"],
            "minute": dataframe["Minute"],
        },
        errors="raise",
    )
    dataframe["temperature_2m"] = dataframe[temperature_column]
    dataframe["shortwave_radiation"] = dataframe["GHI"]
    dataframe["diffuse_radiation"] = dataframe["DHI"]
    dataframe["direct_radiation"] = (
        dataframe["GHI"] - dataframe["DHI"]
    ).clip(lower=0.0)
    dataframe["direct_normal_irradiance"] = dataframe.get("DNI", 0.0)
    dataframe["city"] = location.get("city", "")
    dataframe["latitude"] = _metadata_float(metadata, "Latitude") or location["latitude"]
    dataframe["longitude"] = _metadata_float(metadata, "Longitude") or location["longitude"]
    dataframe["source_model"] = metadata.get("Version", "PSM v4")
    return dataframe


def _weather_metadata(
    location: dict[str, Any],
    *,
    weather_type: str,
    provider: str,
    dataset: str,
    model: str,
    year: int | None,
    station: str,
    weather_reference: str | None = None,
    source_latitude: float | None = None,
    source_longitude: float | None = None,
) -> dict[str, Any]:
    latitude, longitude = _weather_grid_coordinates(location)
    return {
        "weather_type": weather_type,
        "provider": provider,
        "dataset": dataset,
        "model": model,
        "year": year,
        "weather_reference": weather_reference or str(year),
        "latitude": latitude,
        "longitude": longitude,
        "source_latitude": round(source_latitude, 4) if source_latitude is not None else latitude,
        "source_longitude": round(source_longitude, 4) if source_longitude is not None else longitude,
        "timezone": location["timezone"],
        "station": station,
        "engine_version": THERMAL_ENGINE_VERSION,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def _weather_grid_coordinates(location: dict[str, Any]) -> tuple[float, float]:
    return (
        float(
            Decimal(str(location["latitude"])).quantize(
                US_WEATHER_GRID_DEGREES,
                rounding=ROUND_HALF_UP,
            ),
        ),
        float(
            Decimal(str(location["longitude"])).quantize(
                US_WEATHER_GRID_DEGREES,
                rounding=ROUND_HALF_UP,
            ),
        ),
    )


def _timezone_slug(value: Any) -> str:
    timezone_name = str(value or "timezone-unknown").strip().lower()
    normalized = timezone_name.replace("/", "-").replace("_", "-")
    return "-".join(part for part in normalized.split() if part)


def _metadata_float(metadata: dict[str, str], key: str) -> float | None:
    value = metadata.get(key)
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


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
