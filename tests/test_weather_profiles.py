import math

from thermal_model import load_reference_catalog


def daily_min_max(profile: dict) -> tuple[float, float]:
    temperature = profile["temperature_profile"]
    base_temp = temperature["base_temp_c"]
    amplitude = temperature["amplitude_c"]
    phase_hour = temperature.get("phase_hour", 8)
    values = [
        base_temp + amplitude * math.sin(2.0 * math.pi * (hour - phase_hour) / 24.0)
        for hour in range(24)
    ]
    return min(values), max(values)


def test_weather_reference_catalog_contains_location_independent_profiles():
    catalog = load_reference_catalog()

    assert set(catalog["weather_profiles"]) == {
        "generic_winter_design",
        "generic_summer_typical",
        "generic_heatwave_reference",
    }


def test_weather_profiles_have_daily_temperature_range():
    catalog = load_reference_catalog()

    for profile in catalog["weather_profiles"].values():
        min_temp, max_temp = daily_min_max(profile)
        assert max_temp > min_temp


def test_weather_profiles_have_client_descriptions():
    catalog = load_reference_catalog()

    for profile in catalog["weather_profiles"].values():
        assert profile["client_description"].strip()
