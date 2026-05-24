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


def test_weather_reference_catalog_contains_9_profiles():
    catalog = load_reference_catalog()

    assert len(catalog["weather_profiles"]) == 9


def test_heatwave_base_temperature_increases_from_h1_to_h3():
    catalog = load_reference_catalog()

    h1 = catalog["weather_profiles"]["H1_heatwave_reference"]
    h2 = catalog["weather_profiles"]["H2_heatwave_reference"]
    h3 = catalog["weather_profiles"]["H3_heatwave_reference"]

    assert (
        h3["temperature_profile"]["base_temp_c"]
        > h2["temperature_profile"]["base_temp_c"]
        > h1["temperature_profile"]["base_temp_c"]
    )


def test_winter_base_temperature_increases_from_h1_to_h3():
    catalog = load_reference_catalog()

    h1 = catalog["weather_profiles"]["H1_winter_design"]
    h2 = catalog["weather_profiles"]["H2_winter_design"]
    h3 = catalog["weather_profiles"]["H3_winter_design"]

    assert (
        h1["temperature_profile"]["base_temp_c"]
        < h2["temperature_profile"]["base_temp_c"]
        < h3["temperature_profile"]["base_temp_c"]
    )


def test_weather_profiles_have_daily_temperature_range():
    catalog = load_reference_catalog()

    for profile in catalog["weather_profiles"].values():
        min_temp, max_temp = daily_min_max(profile)
        assert max_temp > min_temp


def test_weather_profiles_have_client_descriptions():
    catalog = load_reference_catalog()

    for profile in catalog["weather_profiles"].values():
        assert profile["client_description_fr"].strip()
