"""United States ZIP/address geocoding for weather simulations."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
CENSUS_GEOCODING_URL = (
    "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
)
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
US_ZIP_RE = re.compile(r"^\d{5}(?:-\d{4})?$")


class LocationResolutionError(ValueError):
    """Raised when a US ZIP code or address cannot be resolved safely."""


def resolve_us_location(
    postal_code: str,
    address: str | None = None,
    *,
    cache_dir: str | Path = ".cache/locations",
) -> dict[str, Any]:
    """Resolve a US ZIP/address to coordinates and an IANA timezone.

    A full street address is resolved by the US Census geocoder. ZIP-only
    lookups use the Open-Meteo/GeoNames geocoder. There is deliberately no
    default location when either provider cannot produce a US match.
    """
    normalized_zip = _normalize_us_zip(postal_code)
    normalized_address = " ".join(str(address or "").split())
    cache_path = _location_cache_path(normalized_zip, normalized_address, cache_dir)
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    if normalized_address:
        location = _resolve_census_address(normalized_address, normalized_zip)
        location["timezone"] = _timezone_for_coordinates(
            location["latitude"],
            location["longitude"],
        )
    else:
        location = _resolve_zip_with_open_meteo(normalized_zip)

    location.update(
        {
            "country": "US",
            "postal_code": normalized_zip,
            "address": normalized_address,
        },
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(location, indent=2), encoding="utf-8")
    return location


def _normalize_us_zip(postal_code: str) -> str:
    normalized = str(postal_code or "").strip()
    if not US_ZIP_RE.fullmatch(normalized):
        raise LocationResolutionError(
            "ZIP code must contain 5 digits, optionally followed by a 4-digit extension.",
        )
    return normalized


def _resolve_zip_with_open_meteo(postal_code: str) -> dict[str, Any]:
    payload = _request_json(
        OPEN_METEO_GEOCODING_URL,
        {
            "name": postal_code[:5],
            "count": 20,
            "language": "en",
            "countryCode": "US",
        },
    )
    candidates = [
        result
        for result in payload.get("results", [])
        if result.get("country_code") == "US"
        and postal_code[:5] in result.get("postcodes", [])
    ]
    if not candidates:
        raise LocationResolutionError(f"ZIP code {postal_code} could not be resolved in the US.")
    result = candidates[0]
    timezone = result.get("timezone")
    if not timezone:
        timezone = _timezone_for_coordinates(result["latitude"], result["longitude"])
    return {
        "city": result.get("name", ""),
        "state": result.get("admin1", ""),
        "latitude": float(result["latitude"]),
        "longitude": float(result["longitude"]),
        "elevation_m": _optional_float(result.get("elevation")),
        "timezone": timezone,
        "geocoding_provider": "Open-Meteo Geocoding / GeoNames",
        "geocoding_precision": "postal_code",
    }


def _resolve_census_address(address: str, postal_code: str) -> dict[str, Any]:
    payload = _request_json(
        CENSUS_GEOCODING_URL,
        {
            "address": f"{address}, {postal_code}",
            "benchmark": "Public_AR_Current",
            "format": "json",
        },
    )
    matches = payload.get("result", {}).get("addressMatches", [])
    if not matches:
        raise LocationResolutionError(
            f"Address could not be resolved in ZIP code {postal_code}.",
        )
    match = matches[0]
    components = match.get("addressComponents", {})
    matched_zip = str(components.get("zip", ""))
    if matched_zip and matched_zip != postal_code[:5]:
        raise LocationResolutionError(
            f"Address resolved to ZIP code {matched_zip}, not {postal_code[:5]}.",
        )
    coordinates = match.get("coordinates", {})
    return {
        "city": components.get("city", ""),
        "state": components.get("state", ""),
        "latitude": float(coordinates["y"]),
        "longitude": float(coordinates["x"]),
        "elevation_m": None,
        "timezone": "",
        "geocoding_provider": "US Census Geocoder",
        "geocoding_precision": "street_address",
    }


def _timezone_for_coordinates(latitude: float, longitude: float) -> str:
    payload = _request_json(
        OPEN_METEO_FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": "auto",
            "forecast_days": 1,
        },
    )
    timezone = payload.get("timezone")
    if not timezone or "/" not in timezone:
        raise LocationResolutionError("An IANA timezone could not be resolved for this location.")
    return str(timezone)


def _request_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    request_url = f"{url}?{urlencode(params)}"
    try:
        with urlopen(request_url, timeout=20) as response:  # noqa: S310 - fixed HTTPS hosts
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LocationResolutionError("The location service is temporarily unavailable.") from exc


def _location_cache_path(
    postal_code: str,
    address: str,
    cache_dir: str | Path,
) -> Path:
    cache_key = sha256(f"{postal_code}|{address.lower()}".encode()).hexdigest()[:20]
    return Path(cache_dir) / f"us_{postal_code[:5]}_{cache_key}.json"


def _optional_float(value: Any) -> float | None:
    return None if value in (None, "") else float(value)
