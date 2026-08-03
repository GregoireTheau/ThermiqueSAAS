import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import pytest


def _deterministic_annual_weather():
    """Return a plausible non-leap year without relying on provider data."""
    start = datetime(2001, 1, 1)
    hourly = []
    for hour in range(365 * 24):
        timestamp = start + timedelta(hours=hour)
        day = hour // 24
        hour_in_day = hour % 24
        seasonal = 14.0 + 11.0 * math.sin(2.0 * math.pi * (day - 80) / 365.0)
        daily = 4.0 * math.sin(2.0 * math.pi * (hour_in_day - 9) / 24.0)
        sun = max(0.0, math.sin(math.pi * (hour_in_day - 6) / 12.0))
        summer_factor = 0.65 + 0.35 * math.sin(
            2.0 * math.pi * (day - 80) / 365.0,
        )
        solar = sun * max(0.3, summer_factor)
        hourly.append(
            {
                "hour": hour,
                "month": timestamp.month,
                "outdoor_temperature_c": round(seasonal + daily, 2),
                "solar_irradiance_w_m2": {
                    "north": round(80.0 * solar, 2),
                    "east": round((500.0 if hour_in_day < 12 else 120.0) * solar, 2),
                    "south": round(550.0 * solar, 2),
                    "west": round((500.0 if hour_in_day > 12 else 120.0) * solar, 2),
                    "roof": round(700.0 * solar, 2),
                },
            },
        )
    return hourly


@pytest.fixture(autouse=True)
def _offline_us_services(monkeypatch, tmp_path):
    """Keep the suite deterministic; provider adapters have focused unit tests."""
    location = {
        "country": "US",
        "postal_code": "80202",
        "address": "",
        "city": "Denver",
        "state": "Colorado",
        "county": "Denver",
        "county_fips": "08031",
        "latitude": 39.7392,
        "longitude": -104.9903,
        "elevation_m": 1609.0,
        "timezone": "America/Denver",
        "geocoding_provider": "test fixture",
        "geocoding_precision": "postal_code",
    }

    def fake_resolve(postal_code, address=None, **_kwargs):
        return {
            **location,
            "postal_code": str(postal_code),
            "address": str(address or ""),
        }

    def fake_weather(resolved_location, weather_type, **kwargs):
        from thermal_model.weather import us_weather_ref

        output_path = Path(
            us_weather_ref(
                resolved_location,
                weather_type,
                year=kwargs.get("year"),
                tmy_name=kwargs.get("tmy_name", "tmy-2024"),
                output_dir=kwargs.get("output_dir", tmp_path / "weather"),
            ),
        )
        if output_path.exists():
            return output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        reference = kwargs.get("year") or kwargs.get("tmy_name", "tmy-2024")
        payload = {
            "schema_version": "0.2",
            "source": f"test_{weather_type}_{reference}",
            "metadata": {
                "weather_type": weather_type,
                "provider": "test fixture",
                "dataset": "deterministic hourly weather",
                "model": "test-model",
                "year": kwargs.get("year"),
                "weather_reference": str(reference),
                "latitude": 39.7,
                "longitude": -105.0,
                "timezone": "America/Denver",
                "station": "test-grid",
                "engine_version": "1r1c-mvp-0.1",
                "hourly_sha256": "test-weather-sha256",
            },
            "hourly": _deterministic_annual_weather(),
        }
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        return output_path

    monkeypatch.setenv("THERMAL_WEATHER_DIR", str(tmp_path / "weather"))
    monkeypatch.setattr("thermal_saas.business_flow.resolve_us_location", fake_resolve)
    monkeypatch.setattr("thermal_saas.business_flow.ensure_us_thermal_weather", fake_weather)
