"""Load ThermalTwin static reference data.

Reference files are small JSON documents under data/reference. This loader
indexes each collection by ID so future model code can resolve references such
as "double_glazing_standard" or "simple_flow" without hardcoding values.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ReferenceItem = dict[str, Any]
ReferenceCatalog = dict[str, dict[str, ReferenceItem]]

DEFAULT_REFERENCE_DIR = Path(__file__).resolve().parents[1] / "data" / "reference"

REFERENCE_COLLECTIONS = {
    "materials": ("materials.json", "materials"),
    "envelope_defaults": ("envelope_defaults.json", "construction_eras"),
    "isolation_levels": ("envelope_defaults.json", "isolation_levels"),
    "windows": ("windows.json", "windows"),
    "shutters": ("windows.json", "shutters"),
    "ventilation": ("ventilation.json", "ventilation_types"),
    "heating_systems": ("heating_systems.json", "systems"),
    "cooling_systems": ("cooling_systems.json", "systems"),
    "climate_zones": ("climate_zones_us.json", "climate_zones"),
    "weather_profiles": ("weather_profiles.json", "profiles"),
}


class ReferenceDataError(ValueError):
    """Raised when reference data is missing or inconsistent."""


def load_reference_catalog(
    reference_dir: str | Path = DEFAULT_REFERENCE_DIR,
) -> ReferenceCatalog:
    """Load and index all reference collections by ID."""
    reference_path = Path(reference_dir)
    catalog: ReferenceCatalog = {}
    loaded_files: dict[str, dict[str, Any]] = {}

    for collection_name, (filename, list_key) in REFERENCE_COLLECTIONS.items():
        data = loaded_files.setdefault(
            filename,
            _load_reference_file(reference_path / filename),
        )
        items = data.get(list_key)
        if not isinstance(items, list):
            raise ReferenceDataError(
                f"{filename}.{list_key} must be a list of reference objects"
            )
        catalog[collection_name] = _index_by_id(items, f"{filename}.{list_key}")

    _add_county_zone_map(catalog, loaded_files["climate_zones_us.json"])
    return catalog


def get_reference(
    catalog: ReferenceCatalog,
    collection_name: str,
    reference_id: str,
) -> ReferenceItem:
    """Return one reference item by collection and ID."""
    if collection_name not in catalog:
        raise ReferenceDataError(f"unknown reference collection: {collection_name}")

    collection = catalog[collection_name]
    if reference_id not in collection:
        raise ReferenceDataError(
            f"unknown reference id '{reference_id}' in {collection_name}"
        )

    return collection[reference_id]


def get_material_reference(
    catalog: ReferenceCatalog,
    material_id: str,
) -> ReferenceItem:
    """Return a material reference."""
    return get_reference(catalog, "materials", material_id)


def get_envelope_default_reference(
    catalog: ReferenceCatalog,
    construction_era_id: str,
) -> ReferenceItem:
    """Return an envelope defaults reference for a US construction era."""
    return get_reference(catalog, "envelope_defaults", construction_era_id)


def get_window_reference(
    catalog: ReferenceCatalog,
    window_id: str,
) -> ReferenceItem:
    """Return a glazing reference."""
    return get_reference(catalog, "windows", window_id)


def get_shutter_reference(
    catalog: ReferenceCatalog,
    shutter_id: str,
) -> ReferenceItem:
    """Return a shutter or solar protection reference."""
    return get_reference(catalog, "shutters", shutter_id)


def get_ventilation_reference(
    catalog: ReferenceCatalog,
    ventilation_id: str,
) -> ReferenceItem:
    """Return a ventilation type reference."""
    return get_reference(catalog, "ventilation", ventilation_id)


def get_heating_system_reference(
    catalog: ReferenceCatalog,
    system_id: str,
) -> ReferenceItem:
    """Return a heating system reference."""
    return get_reference(catalog, "heating_systems", system_id)


def get_cooling_system_reference(
    catalog: ReferenceCatalog,
    system_id: str,
) -> ReferenceItem:
    """Return a cooling system reference."""
    return get_reference(catalog, "cooling_systems", system_id)


def get_climate_zone_reference(
    catalog: ReferenceCatalog,
    climate_zone_id: str,
) -> ReferenceItem:
    """Return a climate zone reference."""
    return get_reference(catalog, "climate_zones", climate_zone_id)


def get_weather_profile_reference(
    catalog: ReferenceCatalog,
    profile_id: str,
) -> ReferenceItem:
    """Return a synthetic weather profile reference."""
    return get_reference(catalog, "weather_profiles", profile_id)


def get_climate_zone_for_county(
    catalog: ReferenceCatalog,
    county_fips: str,
) -> str:
    """Return the 2021 IECC climate zone ID for a US county FIPS code."""
    county_map = catalog.get("county_zone_map", {})
    if county_fips not in county_map:
        raise ReferenceDataError(
            f"unknown 2021 IECC climate zone for county FIPS {county_fips}"
        )
    return county_map[county_fips]["climate_zone_id"]


def _load_reference_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ReferenceDataError(f"missing reference file: {path}")

    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    if data.get("schema_version") != "0.1":
        raise ReferenceDataError(f"{path.name}.schema_version must be '0.1'")

    return data


def _index_by_id(items: list[dict[str, Any]], context: str) -> dict[str, ReferenceItem]:
    indexed: dict[str, ReferenceItem] = {}
    for item in items:
        item_id = item.get("id")
        if not item_id:
            raise ReferenceDataError(f"{context} contains an item without id")
        if item_id in indexed:
            raise ReferenceDataError(f"{context} contains duplicate id {item_id}")
        indexed[item_id] = item
    return indexed


def _add_county_zone_map(
    catalog: ReferenceCatalog,
    climate_data: dict[str, Any],
) -> None:
    county_zone_map = climate_data.get("county_zone_map", {})
    indexed_map: dict[str, ReferenceItem] = {}
    climate_zones = catalog["climate_zones"]

    for county_fips, zone_code in county_zone_map.items():
        climate_zone_id = f"US_IECC_2021_{zone_code}"
        if climate_zone_id not in climate_zones:
            raise ReferenceDataError(
                f"county {county_fips} references unknown zone {climate_zone_id}"
            )
        indexed_map[county_fips] = {
            "id": county_fips,
            "climate_zone_id": climate_zone_id,
        }

    catalog["county_zone_map"] = indexed_map
