import json

import pandas as pd

from thermal_model.weather import (
    _parse_nsrdb_csv,
    build_thermal_weather,
    city_coordinates,
    combine_weather_years,
    ensure_us_thermal_weather,
    resolve_weather_city,
    us_weather_ref,
)


def _weather_frame(year, temperatures):
    return pd.DataFrame(
        {
            "datetime": pd.date_range(
                f"{year}-01-01 00:00",
                periods=len(temperatures),
                freq="h",
                tz="Europe/Paris",
            ),
            "temperature_2m": temperatures,
            "apparent_temperature": temperatures,
            "relative_humidity_2m": [70.0] * len(temperatures),
            "dew_point_2m": [3.0] * len(temperatures),
            "wind_speed_10m": [8.0] * len(temperatures),
            "wind_direction_10m": [180.0] * len(temperatures),
            "shortwave_radiation": [0.0, 100.0, 400.0, 0.0][: len(temperatures)],
            "direct_radiation": [0.0, 60.0, 260.0, 0.0][: len(temperatures)],
            "diffuse_radiation": [0.0, 40.0, 140.0, 0.0][: len(temperatures)],
            "direct_normal_irradiance": [0.0, 80.0, 320.0, 0.0][: len(temperatures)],
            "city": ["Paris"] * len(temperatures),
        },
    )


def test_city_coordinates_accept_supported_city():
    assert city_coordinates("Bordeaux") == (44.8378, -0.5792)
    assert city_coordinates("Toulon") == (43.1242, 5.9280)
    assert city_coordinates("Biarritz") == (43.4832, -1.5586)


def test_resolve_weather_city_uses_exact_department_then_climate_zone():
    assert resolve_weather_city("Bordeaux", "33000", "FR_H2c") == {
        "requested_city": "Bordeaux",
        "weather_city": "Bordeaux",
        "match_mode": "exact_city",
    }
    assert resolve_weather_city("Toulon", "83000", "FR_H3") == {
        "requested_city": "Toulon",
        "weather_city": "Toulon",
        "match_mode": "exact_city",
    }
    assert resolve_weather_city("Ville inconnue", "83000", "FR_H3")["weather_city"] == "Toulon"
    assert resolve_weather_city("Ville inconnue", "29000", "FR_H2a")["weather_city"] == "Brest"
    assert resolve_weather_city("Ville inconnue", "2A000", "FR_H3")["weather_city"] == "Ajaccio"
    assert resolve_weather_city("Angers", "49000", "FR_H2b")["weather_city"] == "Nantes"
    assert resolve_weather_city("Ville inconnue", "", "FR_H2b")["weather_city"] == "Nantes"


def test_resolve_weather_city_maps_all_metropolitan_departments():
    department_codes = [
        *(f"{department:02d}" for department in range(1, 20)),
        "2A",
        "2B",
        *(str(department) for department in range(21, 96)),
    ]

    unresolved = [
        department
        for department in department_codes
        if resolve_weather_city(
            "Ville inconnue",
            f"{department}000",
            None,
        )["match_mode"] != "department"
    ]

    assert unresolved == []


def test_build_thermal_weather_matches_scenario_weather_shape():
    dataframe = _weather_frame(2023, [4.0, 5.0, 6.0, 7.0])

    weather = build_thermal_weather(dataframe, source="test_openmeteo")

    assert weather["source"] == "test_openmeteo"
    assert len(weather["hourly"]) == 4
    assert weather["hourly"][0]["hour"] == 0
    assert weather["hourly"][2]["outdoor_temperature_c"] == 6.0
    assert set(weather["hourly"][2]["solar_irradiance_w_m2"]) == {
        "north",
        "east",
        "south",
        "west",
        "roof",
    }
    assert weather["hourly"][2]["solar_irradiance_w_m2"]["roof"] == 400.0


def test_combine_weather_years_latest_uses_last_year():
    first = _weather_frame(2022, [1.0, 2.0])
    second = _weather_frame(2023, [5.0, 6.0])

    combined = combine_weather_years([first, second], "latest")

    assert combined["temperature_2m"].tolist() == [5.0, 6.0]


def test_combine_weather_years_mean_averages_same_month_day_hour():
    first = _weather_frame(2022, [1.0, 3.0])
    second = _weather_frame(2023, [5.0, 7.0])

    combined = combine_weather_years([first, second], "mean")

    assert combined["temperature_2m"].tolist() == [3.0, 5.0]
    assert combined["datetime"].dt.month.tolist() == [1, 1]
    assert combined["datetime"].dt.hour.tolist() == [0, 1]


def test_us_weather_ref_is_keyed_by_rounded_coordinates_mode_and_reference(tmp_path):
    location = {
        "latitude": 39.7392,
        "longitude": -104.9903,
        "timezone": "America/Denver",
    }

    historical = us_weather_ref(
        location,
        "historical",
        year=2023,
        output_dir=tmp_path,
    )
    typical = us_weather_ref(
        location,
        "typical",
        tmy_name="tmy-2024",
        output_dir=tmp_path,
    )

    assert historical.endswith(
        "39.7_-105.0_america-denver_historical_2023.weather.json",
    )
    assert typical.endswith(
        "39.7_-105.0_america-denver_typical_tmy-2024.weather.json",
    )


def test_neighboring_zip_locations_share_one_weather_cell(tmp_path):
    atlanta = {
        "latitude": 33.7490,
        "longitude": -84.3880,
        "timezone": "America/New_York",
    }
    neighboring_zip = {
        "latitude": 33.7420,
        "longitude": -84.4210,
        "timezone": "America/New_York",
    }

    atlanta_ref = us_weather_ref(
        atlanta,
        "historical",
        year=2023,
        output_dir=tmp_path,
    )
    neighbor_ref = us_weather_ref(
        neighboring_zip,
        "historical",
        year=2023,
        output_dir=tmp_path,
    )

    assert atlanta_ref == neighbor_ref
    assert "33.7_-84.4_america-new-york" in atlanta_ref

    other_timezone_ref = us_weather_ref(
        neighboring_zip | {"timezone": "America/Chicago"},
        "historical",
        year=2023,
        output_dir=tmp_path,
    )
    assert other_timezone_ref != atlanta_ref


def test_weather_download_uses_shared_cell_coordinates(monkeypatch, tmp_path):
    requested = {}

    def fake_fetch(latitude, longitude, year, **kwargs):
        requested.update(
            latitude=latitude,
            longitude=longitude,
            year=year,
            timezone=kwargs["timezone_name"],
        )
        return _weather_frame(2023, [10.0, 11.0])

    monkeypatch.setattr("thermal_model.weather.fetch_open_meteo_coordinates", fake_fetch)
    location = {
        "postal_code": "30303",
        "city": "Atlanta",
        "latitude": 33.7490,
        "longitude": -84.3880,
        "timezone": "America/New_York",
    }

    weather_path = ensure_us_thermal_weather(
        location,
        "historical",
        year=2023,
        output_dir=tmp_path,
    )
    payload = json.loads(weather_path.read_text(encoding="utf-8"))

    assert requested == {
        "latitude": 33.7,
        "longitude": -84.4,
        "year": 2023,
        "timezone": "America/New_York",
    }
    assert payload["metadata"]["latitude"] == 33.7
    assert payload["metadata"]["longitude"] == -84.4
    assert payload["metadata"]["station"] == "Open-Meteo grid 33.7, -84.4"


def test_nsrdb_csv_parser_normalizes_tmy_calendar_and_weather_columns():
    raw_csv = "\n".join(
        [
            "Source,Location ID,Latitude,Longitude,Version",
            "NSRDB,123,39.74,-104.99,4.0.0",
            "Year,Month,Day,Hour,Minute,Temperature,GHI,DHI,DNI",
            "2011,1,1,0,0,-2.0,0,0,0",
            "2018,1,1,1,0,-1.0,100,40,80",
        ],
    )
    location = {"city": "Denver", "latitude": 39.7392, "longitude": -104.9903}

    dataframe = _parse_nsrdb_csv(raw_csv, location)

    assert dataframe["datetime"].dt.year.tolist() == [2001, 2001]
    assert dataframe["temperature_2m"].tolist() == [-2.0, -1.0]
    assert dataframe["shortwave_radiation"].tolist() == [0, 100]
    assert dataframe["direct_radiation"].tolist() == [0, 60]
