import pytest

import thermal_model.location as location_module
from thermal_model.location import LocationResolutionError, resolve_us_location


def test_zip_resolution_returns_us_coordinates_timezone_and_uses_cache(tmp_path, monkeypatch):
    calls = []

    def fake_request(url, params):
        calls.append((url, params))
        return {
            "results": [
                {
                    "name": "Denver",
                    "country_code": "US",
                    "admin1": "Colorado",
                    "postcodes": ["80202"],
                    "latitude": 39.7525,
                    "longitude": -104.9995,
                    "elevation": 1598.0,
                    "timezone": "America/Denver",
                },
            ],
        }

    monkeypatch.setattr(location_module, "_request_json", fake_request)

    first = resolve_us_location("80202", cache_dir=tmp_path)
    second = resolve_us_location("80202", cache_dir=tmp_path)

    assert first == second
    assert first["city"] == "Denver"
    assert first["timezone"] == "America/Denver"
    assert first["geocoding_precision"] == "postal_code"
    assert len(calls) == 1


def test_optional_address_uses_census_coordinates_and_coordinate_timezone(tmp_path, monkeypatch):
    def fake_request(url, params):
        if "census" in url:
            return {
                "result": {
                    "addressMatches": [
                        {
                            "coordinates": {"x": -104.991, "y": 39.740},
                            "addressComponents": {
                                "zip": "80202",
                                "city": "DENVER",
                                "state": "CO",
                            },
                        },
                    ],
                },
            }
        return {"timezone": "America/Denver"}

    monkeypatch.setattr(location_module, "_request_json", fake_request)

    location = resolve_us_location(
        "80202",
        "1701 Wynkoop St",
        cache_dir=tmp_path,
    )

    assert location["latitude"] == 39.740
    assert location["longitude"] == -104.991
    assert location["timezone"] == "America/Denver"
    assert location["geocoding_provider"] == "US Census Geocoder"
    assert location["geocoding_precision"] == "street_address"


def test_invalid_or_unresolved_zip_has_no_default_location(tmp_path, monkeypatch):
    with pytest.raises(LocationResolutionError, match="5 digits"):
        resolve_us_location("Bordeaux", cache_dir=tmp_path)

    monkeypatch.setattr(location_module, "_request_json", lambda *_args, **_kwargs: {})
    with pytest.raises(LocationResolutionError, match="could not be resolved"):
        resolve_us_location("00000", cache_dir=tmp_path)
