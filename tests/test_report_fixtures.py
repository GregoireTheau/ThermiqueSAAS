from argparse import Namespace

from scripts.generate_report_fixtures import generate_report_fixtures


def test_generate_report_fixtures_outputs_multiple_html_reports(tmp_path):
    output_paths = generate_report_fixtures(
        Namespace(
            dwelling_path="data/examples/apartment_two_rooms.json",
            reference_dir="data/reference",
            output_dir=tmp_path,
            adaptation=["reflective_roof", "heat_pump"],
            target_scope="all",
            air_density_kg_m3=1.2,
            air_heat_capacity_j_kgk=1005.0,
            include_annual=False,
            annual_weather_year=2023,
            annual_weather_city=None,
            annual_weather_dir="data/weather/openmeteo",
            openmeteo_model="era5_seamless",
            openmeteo_cache_dir=".cache/openmeteo",
        ),
    )

    assert len(output_paths) == 3
    assert all(path.exists() for path in output_paths)
    assert (tmp_path / "apartment_two_rooms" / "dwelling.json").exists()
    assert any("summer_heatwave_report.html" in path.name for path in output_paths)
    assert any("winter_cold_report.html" in path.name for path in output_paths)
