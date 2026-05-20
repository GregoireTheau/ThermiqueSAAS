import pandas as pd

from thermal_model.weather import (
    build_thermal_weather,
    city_coordinates,
    combine_weather_years,
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
