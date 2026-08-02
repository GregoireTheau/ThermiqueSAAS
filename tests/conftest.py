import json
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _offline_us_services(monkeypatch, tmp_path):
    """Keep the suite deterministic; provider adapters have focused unit tests."""
    location = {
        "country": "US",
        "postal_code": "80202",
        "address": "",
        "city": "Denver",
        "state": "Colorado",
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
        fixture_path = (
            Path(__file__).resolve().parents[1]
            / "data/weather/openmeteo/thermal/bordeaux_2023.weather.json"
        )
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
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
            "hourly": fixture["hourly"],
        }
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        return output_path

    monkeypatch.setenv("THERMAL_WEATHER_DIR", str(tmp_path / "weather"))
    monkeypatch.setattr("thermal_saas.business_flow.resolve_us_location", fake_resolve)
    monkeypatch.setattr("thermal_saas.business_flow.ensure_us_thermal_weather", fake_weather)
