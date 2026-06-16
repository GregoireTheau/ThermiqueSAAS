import pandas as pd

from thermal_model.weather import (
    build_thermal_weather,
    city_coordinates,
    combine_weather_years,
    resolve_weather_city,
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
