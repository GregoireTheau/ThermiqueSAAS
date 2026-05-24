#!/usr/bin/env python3
"""Create a customer-specific dwelling and run relevant before/after experiments."""

from __future__ import annotations

import argparse
import json
import math
import re
from copy import deepcopy
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from thermal_model import (  # noqa: E402
    build_report_model,
    compare_scenarios,
    ensure_openmeteo_thermal_weather,
    get_weather_profile_reference,
    load_reference_catalog,
    render_report_html,
    resolve_scenario_weather_reference,
    resolve_dwelling_references,
    resolve_weather_city,
    thermal_weather_ref,
    validate_dwelling,
    validate_scenario,
)
from thermal_model.reference_loader import ReferenceDataError  # noqa: E402


ORIENTATIONS = {
    "N": ("north", 0, "Nord"),
    "NE": ("northeast", 45, "Nord-Est"),
    "E": ("east", 90, "Est"),
    "SE": ("southeast", 135, "Sud-Est"),
    "S": ("south", 180, "Sud"),
    "SW": ("southwest", 225, "Sud-Ouest"),
    "W": ("west", 270, "Ouest"),
    "NW": ("northwest", 315, "Nord-Ouest"),
}

ROOM_TYPES = [
    {"id": "living", "label": "Salon / sejour"},
    {"id": "bedroom", "label": "Chambre"},
    {"id": "kitchen", "label": "Cuisine"},
    {"id": "bathroom", "label": "Salle de bain"},
    {"id": "office", "label": "Bureau"},
    {"id": "corridor", "label": "Couloir / entree"},
    {"id": "other", "label": "Autre"},
]

DWELLING_TYPES = [
    {"id": "house", "label": "Maison"},
    {"id": "apartment", "label": "Appartement"},
]

DWELLING_POSITIONS = [
    {"id": "single_storey_house", "label": "Maison de plain-pied"},
    {"id": "multi_storey_house", "label": "Maison avec etage"},
    {"id": "apartment_ground_floor", "label": "Appartement en rez-de-chaussee"},
    {"id": "apartment_middle_floor", "label": "Appartement en etage intermediaire"},
    {"id": "apartment_top_floor", "label": "Appartement au dernier etage"},
    {"id": "apartment_ground_top_floor", "label": "Appartement en rez-de-chaussee directement sous toiture"},
]

ADJACENCY_LEVELS = [
    {"id": "detached", "label": "Logement isole, facades surtout dehors"},
    {"id": "one_side", "label": "Mitoyen ou voisin chauffe sur un cote"},
    {"id": "two_sides", "label": "Mitoyen ou voisin chauffe sur deux cotes"},
    {"id": "surrounded", "label": "Tres entoure par des logements chauffes"},
]

WALL_INSULATION_LEVELS = [
    {"id": "poor", "label": "Non, ou probablement pas isoles", "u_factor": 1.25},
    {"id": "standard", "label": "Je ne sais pas / standard pour l'age du logement", "u_factor": 1.0},
    {"id": "renovated", "label": "Oui, isolation ajoutee ou renovee", "u_factor": 0.75},
]

ROOF_INSULATION_LEVELS = [
    {"id": "unknown", "label": "Je ne sais pas", "u_factor": 1.0},
    {"id": "not_concerned", "label": "Pas de toiture directement concernee", "u_factor": 1.0},
    {"id": "poor", "label": "Toiture ou combles peu isoles", "u_factor": 1.35},
    {"id": "standard", "label": "Isolation toiture standard", "u_factor": 1.0},
    {"id": "renovated", "label": "Toiture bien isolee ou renovee", "u_factor": 0.65},
]

FLOOR_INSULATION_LEVELS = [
    {"id": "unknown", "label": "Je ne sais pas", "u_factor": 1.0},
    {"id": "not_concerned", "label": "Pas de plancher bas directement concerne", "u_factor": 1.0},
    {"id": "poor", "label": "Plancher bas peu isole", "u_factor": 1.25},
    {"id": "standard", "label": "Plancher bas standard", "u_factor": 1.0},
    {"id": "renovated", "label": "Plancher bas isole/renove", "u_factor": 0.75},
]

AIRTIGHTNESS_LEVELS = [
    {"id": "leaky", "label": "Oui, courants d'air sensibles aux fenetres, portes ou prises", "ach_factor": 1.2},
    {"id": "standard", "label": "Je ne sais pas / rien de particulier", "ach_factor": 1.0},
    {"id": "good", "label": "Non, logement plutot etanche", "ach_factor": 0.85},
]

EXTERIOR_CONTACTS = [
    {"id": "exterior", "label": "Oui, une ou plusieurs facades donnent dehors"},
    {"id": "interior", "label": "Non, piece interieure"},
    {"id": "unheated_space", "label": "Non, contre garage/cave/combles non chauffes"},
    {"id": "party", "label": "Non, contre voisin ou mitoyen"},
]

THERMAL_LAYOUTS = [
    {"id": "open_living", "label": "Les pieces donnent surtout sur le sejour"},
    {"id": "corridor", "label": "Les pieces donnent surtout sur un couloir / une entree"},
    {"id": "manual", "label": "Indiquer les portes ou ouvertures principales une par une"},
]

WINDOW_SIZES = [
    {"id": "none", "label": "Aucune fenetre", "factor": 0.0},
    {"id": "small", "label": "Petite: une fenetre standard", "factor": 0.08},
    {"id": "medium", "label": "Moyenne: deux fenetres ou une porte-fenetre", "factor": 0.14},
    {"id": "large", "label": "Grande: baie vitree ou grande surface vitree", "factor": 0.22},
    {"id": "custom", "label": "Entrer une surface approximative en m2"},
]

WINDOW_LEVELS = [
    {"id": "single_glazing_old", "label": "Simple vitrage"},
    {"id": "double_glazing_old", "label": "Double vitrage ancien"},
    {"id": "double_glazing_standard", "label": "Double vitrage recent standard"},
    {"id": "double_glazing_low_e", "label": "Double vitrage performant"},
]

SHUTTER_LEVELS = [
    {"id": "none", "label": "Pas de volet/protection"},
    {"id": "roller_shutter_standard", "label": "Volets roulants ou battants"},
    {"id": "external_blind", "label": "Stores exterieurs"},
    {"id": "interior_blind", "label": "Stores interieurs"},
]

SOLAR_MASK_LEVELS = [
    {"id": "none", "label": "Aucun masque, soleil direct", "mask_factor": 1.0},
    {"id": "light", "label": "Masque leger: arbre clair, garde-corps, petit debord", "mask_factor": 0.85},
    {"id": "medium", "label": "Masque moyen: balcon, arbre dense, vis-a-vis proche", "mask_factor": 0.65},
    {"id": "strong", "label": "Masque fort: loggia, immeuble tres proche, ombre frequente", "mask_factor": 0.4},
]

SHUTTER_USAGE_LEVELS = [
    {"id": "day_closed", "label": "En ete, fermes en journee quand il fait chaud"},
    {"id": "partial", "label": "En ete, partiellement fermes ou selon presence"},
    {"id": "rare", "label": "Rarement fermes en journee"},
]

HEATING_SYSTEMS = [
    {"id": "electric_radiator", "label": "Radiateurs electriques"},
    {"id": "air_air_heat_pump_standard", "label": "PAC air-air"},
    {"id": "air_water_heat_pump_standard", "label": "PAC air-eau"},
]

HEAT_PUMP_CURRENT_ENERGIES = [
    {"id": "electricity", "label": "Electricite"},
    {"id": "gas", "label": "Gaz"},
    {"id": "fuel_oil", "label": "Fioul"},
    {"id": "wood", "label": "Bois"},
    {"id": "unknown", "label": "Je ne sais pas"},
]

HEAT_EMITTERS = [
    {"id": "electric_radiators", "label": "Radiateurs electriques"},
    {"id": "water_radiators", "label": "Radiateurs a eau"},
    {"id": "underfloor", "label": "Plancher chauffant"},
    {"id": "air_units", "label": "Unites murales / soufflage d'air"},
    {"id": "mixed", "label": "Mixte ou incertain"},
]

VENTILATION_SYSTEMS = [
    {"id": "natural_leaky_old", "label": "Ventilation naturelle logement ancien"},
    {"id": "natural_average", "label": "Ventilation naturelle moyenne"},
    {"id": "simple_flow", "label": "VMC simple flux"},
    {"id": "double_flow_standard", "label": "VMC double flux"},
    {"id": "airtight_recent", "label": "Logement recent etanche"},
]

CHANGES = [
    {
        "id": "roof_insulation",
        "label": "Ameliorer l'isolation de la toiture / des combles",
        "experiments": ["winter_cold_primary", "summer_heatwave_secondary"],
    },
    {
        "id": "reflective_roof",
        "label": "Ajouter un revetement reflechissant sur la toiture contre la chaleur",
        "experiments": ["summer_heatwave_primary", "summer_long_secondary"],
    },
    {
        "id": "better_windows",
        "label": "Remplacer les fenetres par du double vitrage performant",
        "experiments": ["winter_cold_primary", "summer_heatwave_if_exposed"],
    },
    {
        "id": "solar_protection",
        "label": "Ajouter des volets ou protections solaires",
        "experiments": ["summer_heatwave_primary"],
    },
    {
        "id": "heat_pump",
        "label": "Remplacer le chauffage actuel par une PAC",
        "experiments": ["winter_cold_primary"],
    },
]

EXPERIMENT_SPECS = {
    "winter_cold_primary": {
        "id": "winter_cold",
        "season": "winter",
        "weather_variant": "winter_cold",
        "simulation_type": "stress",
        "weather_mode": "synthetic",
        "duration_days": 7,
        "role": "primary",
        "label": "Hiver froid",
        "reason": "Experience principale pour mesurer les pertes et les besoins de chauffage.",
    },
    "summer_heatwave_primary": {
        "id": "summer_heatwave",
        "season": "summer",
        "weather_variant": "summer_heatwave",
        "simulation_type": "stress",
        "weather_mode": "synthetic",
        "duration_days": 3,
        "role": "primary",
        "label": "Ete canicule",
        "reason": "Experience principale pour mesurer le confort d'ete et les apports solaires.",
    },
    "summer_heatwave_secondary": {
        "id": "summer_heatwave",
        "season": "summer",
        "weather_variant": "summer_heatwave",
        "simulation_type": "stress",
        "weather_mode": "synthetic",
        "duration_days": 3,
        "role": "secondary",
        "label": "Ete canicule",
        "reason": "Experience secondaire pour verifier l'effet sur la surchauffe.",
    },
    "summer_heatwave_if_exposed": {
        "id": "summer_heatwave",
        "season": "summer",
        "weather_variant": "summer_heatwave",
        "simulation_type": "stress",
        "weather_mode": "synthetic",
        "duration_days": 3,
        "role": "secondary",
        "condition": "exposed_windows",
        "label": "Ete canicule",
        "reason": "Experience secondaire lancée si des vitrages exposes peuvent influencer les apports solaires.",
    },
    "summer_long_secondary": {
        "id": "summer_long",
        "season": "summer",
        "weather_variant": "summer_long_with_heatwave",
        "simulation_type": "seasonal",
        "weather_mode": "synthetic",
        "duration_days": 60,
        "role": "secondary",
        "label": "Ete long avec canicule",
        "reason": "Experience secondaire sur deux mois d'ete type avec un episode de canicule integre.",
    },
    "annual_openmeteo": {
        "id": "annual",
        "season": "annual",
        "weather_variant": "openmeteo_annual",
        "simulation_type": "annual",
        "weather_mode": "openmeteo_annual",
        "duration_days": 365,
        "role": "annual",
        "label": "Annee complete",
        "reason": "Experience annuelle pour estimer les besoins et gains sur une meteo representative.",
    },
}

CLIMATE_ZONES = [
    {"id": "FR_H1a", "label": "Nord / Est froid"},
    {"id": "FR_H2b", "label": "Ouest / climat tempere"},
    {"id": "FR_H2c", "label": "Sud-Ouest / tempere chaud"},
    {"id": "FR_H3", "label": "Mediterranee / climat chaud"},
]

ROOF_TYPES = [
    {"id": "lost_attic", "label": "Combles perdus"},
    {"id": "sloped_ceiling", "label": "Rampants / pieces sous pente"},
    {"id": "flat_roof", "label": "Toit terrasse"},
    {"id": "unknown", "label": "Je ne sais pas"},
]

ROOF_COLORS = [
    {"id": "dark", "label": "Foncee", "albedo": 0.18},
    {"id": "medium", "label": "Moyenne", "albedo": 0.25},
    {"id": "light", "label": "Claire", "albedo": 0.4},
    {"id": "unknown", "label": "Je ne sais pas", "albedo": 0.25},
]

ATTIC_VENTILATION_LEVELS = [
    {"id": "ventilated", "label": "Combles ou sous-toiture bien ventiles", "solar_to_room_factor": 0.015},
    {"id": "limited", "label": "Ventilation limitee ou inconnue", "solar_to_room_factor": 0.02},
    {"id": "not_ventilated", "label": "Peu ou pas ventiles", "solar_to_room_factor": 0.03},
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a customer dwelling and run the relevant experiments.",
    )
    parser.add_argument(
        "--reference-dir",
        default="data/reference",
        help="Path to the reference data directory.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/customer_experiences",
        help="Directory where generated JSON files are written.",
    )
    parser.add_argument(
        "--air-density-kg-m3",
        type=float,
        default=1.2,
        help="Air density used for ventilation losses.",
    )
    parser.add_argument(
        "--air-heat-capacity-j-kgk",
        type=float,
        default=1005.0,
        help="Air heat capacity used for ventilation losses.",
    )
    parser.add_argument(
        "--annual-weather-year",
        type=int,
        default=2023,
        help="Open-Meteo year used for annual simulations.",
    )
    parser.add_argument(
        "--annual-weather-dir",
        default="data/weather/openmeteo",
        help="Directory containing/generated Open-Meteo weather assets.",
    )
    parser.add_argument(
        "--openmeteo-model",
        default="era5_seamless",
        help="Open-Meteo model used when annual weather must be fetched.",
    )
    parser.add_argument(
        "--openmeteo-cache-dir",
        default=".cache/openmeteo",
        help="HTTP cache directory for Open-Meteo annual weather fetches.",
    )
    return parser.parse_args()


def choose_one(title: str, options: list[dict[str, Any]]) -> dict[str, Any]:
    print()
    print(title)
    for index, option in enumerate(options, start=1):
        print(f"{index}. {option['label']}")

    while True:
        value = input("> ").strip()
        if value.isdigit() and 1 <= int(value) <= len(options):
            return options[int(value) - 1]
        print(f"Choix invalide. Entrez un nombre entre 1 et {len(options)}.")


def ask_text(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{label}{suffix} > ").strip()
        if value:
            return value
        if default is not None:
            return default
        print("Valeur requise.")


def ask_float(label: str, default: float | None = None, minimum: float = 0.0) -> float:
    suffix = f" [{default:g}]" if default is not None else ""
    while True:
        raw_value = input(f"{label}{suffix} > ").strip()
        if not raw_value and default is not None:
            return default
        try:
            value = float(raw_value.replace(",", "."))
        except ValueError:
            print("Entrez un nombre.")
            continue
        if value >= minimum:
            return value
        print(f"La valeur doit etre superieure ou egale a {minimum:g}.")


def ask_int(label: str, default: int | None = None, minimum: int = 1) -> int:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw_value = input(f"{label}{suffix} > ").strip()
        if not raw_value and default is not None:
            return default
        if raw_value.isdigit() and int(raw_value) >= minimum:
            return int(raw_value)
        print(f"Entrez un entier superieur ou egal a {minimum}.")


def ask_yes_no(label: str, default: bool) -> bool:
    suffix = "O/n" if default else "o/N"
    value = input(f"{label} ({suffix}) > ").strip().lower()
    if not value:
        return default
    return value in {"o", "oui", "y", "yes"}


def choose_orientation(title: str) -> str:
    options = [
        {"id": code, "label": orientation[2]}
        for code, orientation in ORIENTATIONS.items()
    ]
    return choose_one(title, options)["id"]


def choose_window_area(room_type: str, area_m2: float, orientation_code: str) -> float:
    size = choose_one("Surface vitree sur cette facade", WINDOW_SIZES)
    if size["id"] == "custom":
        return ask_float("Surface vitree approximative en m2", minimum=0.0)
    if size["id"] == "none":
        return 0.0

    default_area = default_window_area(room_type, area_m2, orientation_code)
    return round(max(default_area, area_m2 * size["factor"]), 1)


def slugify(value: str, default: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return slug or default


def get_catalog_item(catalog: dict[str, Any], collection: str, item_id: str) -> dict[str, Any]:
    return catalog[collection][item_id]


def collect_customer_input(catalog: dict[str, Any]) -> dict[str, Any]:
    print("Creation d'une experience client ThermalTwin")
    print("On commence par le changement a etudier, puis on decrit le logement utile a cette simulation.")
    print("Les scenarios meteo seront choisis automatiquement.")
    print()

    project_name = ask_text("Nom du logement/projet", "mon_logement")
    city = ask_text("Ville", "Bordeaux")
    postal_code = ask_text("Code postal", "33000")
    climate_zone_id = infer_climate_zone(catalog, postal_code)
    if not climate_zone_id:
        climate_zone_id = choose_one("Zone climatique approximative", CLIMATE_ZONES)["id"]

    dwelling_type = choose_one("Type de logement", DWELLING_TYPES)
    position = choose_dwelling_position(dwelling_type["id"])
    adjacency = choose_one("Le logement est-il mitoyen ou entoure par des voisins chauffes ?", ADJACENCY_LEVELS)
    change = choose_one("Changement a etudier", CHANGES)
    change_details = collect_change_details(change["id"])

    period = choose_one(
        "Quand le logement a-t-il ete construit ou fortement renove ?",
        envelope_period_options(catalog),
    )
    wall_insulation = choose_one("Les murs donnant dehors sont-ils isoles ?", WALL_INSULATION_LEVELS)
    roof_insulation = collect_roof_insulation(dwelling_type["id"], position["id"])
    floor_insulation = collect_floor_insulation(dwelling_type["id"], position["id"])
    airtightness = choose_one("Ressentez-vous des courants d'air ?", AIRTIGHTNESS_LEVELS)
    ventilation = choose_one("Ventilation principale", VENTILATION_SYSTEMS)
    window_level = choose_one("Type de vitrage principal", WINDOW_LEVELS)
    shutter_level = choose_one("Protections solaires actuelles", SHUTTER_LEVELS)
    heating = choose_one("Chauffage principal", HEATING_SYSTEMS)
    has_cooling = ask_yes_no("Le logement a-t-il deja une climatisation active", False)
    setpoints = collect_setpoints()
    shutter_usage = collect_shutter_usage(shutter_level["id"])

    room_count = ask_int("Nombre de pieces a modeliser", default=3, minimum=1)
    rooms = []
    for index in range(room_count):
        rooms.append(collect_room(index + 1, dwelling_type["id"], position["id"], change["id"]))
    ensure_unique_room_ids(rooms)
    thermal_layout = collect_thermal_layout(rooms)

    target_scope = choose_one(
        "Zone concernee par le changement",
        [{"id": "all", "label": "Tout le logement"}]
        + [{"id": room["id"], "label": room["name"]} for room in rooms],
    )

    return {
        "project_name": project_name,
        "dwelling_type": dwelling_type["id"],
        "position": position,
        "adjacency": adjacency,
        "city": city,
        "postal_code": postal_code,
        "climate_zone_id": climate_zone_id,
        "period_id": period["id"],
        "wall_insulation": wall_insulation,
        "roof_insulation": roof_insulation,
        "floor_insulation": floor_insulation,
        "airtightness": airtightness,
        "ventilation_id": ventilation["id"],
        "window_ref": window_level["id"],
        "shutter_ref": shutter_level["id"],
        "shutter_usage": shutter_usage,
        "heating_ref": heating["id"],
        "has_cooling": has_cooling,
        "setpoints": setpoints,
        "rooms": rooms,
        "thermal_layout": thermal_layout,
        "change": change,
        "change_details": change_details,
        "target_scope": target_scope["id"],
    }


def choose_dwelling_position(dwelling_type: str) -> dict[str, Any]:
    if dwelling_type == "house":
        options = [
            option
            for option in DWELLING_POSITIONS
            if option["id"] in {"single_storey_house", "multi_storey_house"}
        ]
    else:
        options = [
            option
            for option in DWELLING_POSITIONS
            if option["id"].startswith("apartment_")
        ]
    return choose_one("Position du logement", options)


def collect_change_details(change_id: str) -> dict[str, Any]:
    if change_id in {"reflective_roof", "roof_insulation"}:
        return {
            "roof_type": choose_one("Type de toiture concernee", ROOF_TYPES),
            "roof_color": choose_one("Couleur dominante actuelle de la toiture", ROOF_COLORS),
            "attic_ventilation": choose_one("Ventilation des combles ou de la sous-toiture", ATTIC_VENTILATION_LEVELS),
        }
    if change_id in {"better_windows", "solar_protection"}:
        return {
            "window_air_leakage": choose_one(
                "Ressentez-vous des infiltrations d'air autour des fenetres ?",
                AIRTIGHTNESS_LEVELS,
            ),
        }
    if change_id == "heat_pump":
        return {
            "current_energy": choose_one("Energie actuelle du chauffage", HEAT_PUMP_CURRENT_ENERGIES),
            "heat_emitters": choose_one("Emetteurs de chauffage actuels", HEAT_EMITTERS),
        }
    return {}


def collect_setpoints() -> dict[str, float]:
    print()
    print("Consignes habituelles")
    heating_c = ask_float("Temperature de chauffage visee en hiver en C", default=19.0, minimum=5.0)
    cooling_c = ask_float("Temperature de rafraichissement visee en ete en C", default=26.0, minimum=heating_c)
    return {"heating_c": heating_c, "cooling_c": cooling_c}


def collect_shutter_usage(shutter_ref: str) -> dict[str, Any]:
    if shutter_ref == "none":
        return {"id": "none", "label": "Pas de protection solaire actuelle"}
    return choose_one("En ete, comment les volets/stores sont-ils utilises ?", SHUTTER_USAGE_LEVELS)


def collect_roof_insulation(dwelling_type: str, dwelling_position: str) -> dict[str, Any]:
    if not dwelling_has_roof_contact(dwelling_type, dwelling_position):
        return option_by_id(ROOF_INSULATION_LEVELS, "not_concerned")
    return choose_one("La toiture ou les combles sont-ils isoles ?", ROOF_INSULATION_LEVELS)


def collect_floor_insulation(dwelling_type: str, dwelling_position: str) -> dict[str, Any]:
    if not dwelling_has_floor_contact(dwelling_type, dwelling_position):
        return option_by_id(FLOOR_INSULATION_LEVELS, "not_concerned")
    return choose_one("Le plancher bas est-il isole ?", FLOOR_INSULATION_LEVELS)


def option_by_id(options: list[dict[str, Any]], option_id: str) -> dict[str, Any]:
    return next(option for option in options if option["id"] == option_id)


def infer_climate_zone(catalog: dict[str, Any], postal_code: str) -> str | None:
    department_code = postal_code[:2]
    try:
        return catalog["department_zone_map"][department_code]["climate_zone_id"]
    except (KeyError, ReferenceDataError):
        return None


def envelope_period_options(catalog: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"id": period["id"], "label": period["name"]}
        for period in catalog["envelope_defaults"].values()
    ]


def collect_room(
    index: int,
    dwelling_type: str,
    dwelling_position: str,
    change_id: str,
) -> dict[str, Any]:
    print()
    print(f"Piece {index}")
    name = ask_text("Nom de la piece", f"Piece {index}")
    room_type = choose_one("Type de piece", ROOM_TYPES)
    area_m2 = ask_float("Surface de la piece en m2", minimum=1.0)
    height_m = ask_float("Hauteur sous plafond en m", default=2.5, minimum=1.5)
    exterior_contact = choose_one("Cette piece a-t-elle un mur qui donne dehors ?", EXTERIOR_CONTACTS)
    facades = []
    if exterior_contact["id"] == "exterior":
        facade_count = ask_int("Nombre de facades donnant dehors", default=1, minimum=1)
        facade_count = min(facade_count, 4)
        used_orientations = set()
        for facade_index in range(facade_count):
            while True:
                orientation = choose_orientation(f"Orientation facade {facade_index + 1}")
                if orientation not in used_orientations:
                    used_orientations.add(orientation)
                    break
                print("Cette orientation est deja saisie pour la piece.")
            window_area = choose_window_area(room_type["id"], area_m2, orientation)
            wall_length_m = ask_float(
                "Longueur approximative de cette facade en m",
                default=round(math.sqrt(area_m2), 1),
                minimum=0.5,
            )
            mask = collect_solar_mask(window_area, change_id)
            window_ref = None
            if change_id in {"better_windows", "solar_protection"} and window_area > 0:
                window_ref = choose_one("Type de vitrage sur cette facade", WINDOW_LEVELS)["id"]
            facades.append(
                {
                    "orientation": orientation,
                    "window_area_m2": window_area,
                    "wall_length_m": wall_length_m,
                    "mask_factor": mask["mask_factor"],
                    "window_ref": window_ref,
                },
            )

    has_roof = default_has_roof(dwelling_type, dwelling_position)
    has_ground_floor = default_has_ground_floor(dwelling_type, dwelling_position)
    if should_ask_room_roof(dwelling_type, dwelling_position):
        label = (
            "Cette piece est-elle directement sous toiture ou combles"
            if dwelling_type == "house"
            else "Cette piece est-elle directement sous la toiture"
        )
        has_roof = ask_yes_no(label, has_roof)
    if should_ask_room_ground_floor(dwelling_type, dwelling_position):
        label = (
            "Cette piece est-elle au contact du sol"
            if dwelling_type == "house"
            else "Cette piece est-elle au-dessus d'un local non chauffe ou du sol"
        )
        has_ground_floor = ask_yes_no(label, has_ground_floor)

    return {
        "id": slugify(name, f"room_{index}"),
        "name": name,
        "type": room_type["id"],
        "floor_area_m2": area_m2,
        "height_m": height_m,
        "exterior_contact": exterior_contact["id"],
        "facades": facades,
        "has_roof": has_roof,
        "has_ground_floor": has_ground_floor,
    }


def should_ask_room_roof(dwelling_type: str, dwelling_position: str) -> bool:
    if dwelling_type == "house":
        return dwelling_position == "multi_storey_house"
    return False


def should_ask_room_ground_floor(dwelling_type: str, dwelling_position: str) -> bool:
    if dwelling_type == "house":
        return dwelling_position == "multi_storey_house"
    return False


def collect_solar_mask(window_area_m2: float, change_id: str) -> dict[str, Any]:
    if window_area_m2 <= 0:
        return SOLAR_MASK_LEVELS[0]
    if change_id not in {"reflective_roof", "better_windows", "solar_protection"}:
        return SOLAR_MASK_LEVELS[0]
    return choose_one("Masque solaire devant cette fenetre", SOLAR_MASK_LEVELS)


def default_has_roof(dwelling_type: str, dwelling_position: str) -> bool:
    return dwelling_has_roof_contact(dwelling_type, dwelling_position)


def default_has_ground_floor(dwelling_type: str, dwelling_position: str) -> bool:
    return dwelling_has_floor_contact(dwelling_type, dwelling_position)


def dwelling_has_roof_contact(dwelling_type: str, dwelling_position: str) -> bool:
    if dwelling_type == "house":
        return True
    return dwelling_position in {"apartment_top_floor", "apartment_ground_top_floor"}


def dwelling_has_floor_contact(dwelling_type: str, dwelling_position: str) -> bool:
    if dwelling_type == "house":
        return dwelling_position == "single_storey_house"
    return dwelling_position in {"apartment_ground_floor", "apartment_ground_top_floor"}


def collect_thermal_layout(rooms: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rooms) < 2:
        return {"type": "single_room", "connections": []}

    layout = choose_one("Comment les pieces communiquent-elles entre elles ?", THERMAL_LAYOUTS)
    if layout["id"] != "manual":
        return {"type": layout["id"], "connections": []}

    print()
    print("Portes ou ouvertures principales")
    print("Repondez oui si les deux pieces sont reliees par une porte ou une ouverture souvent ouverte.")
    connections = []
    for index, first_room in enumerate(rooms):
        for second_room in rooms[index + 1:]:
            if ask_yes_no(
                f"Porte ou ouverture souvent ouverte entre {first_room['name']} et {second_room['name']}",
                False,
            ):
                connections.append(
                    {
                        "room_a": first_room["id"],
                        "room_b": second_room["id"],
                    },
                )
    return {"type": "manual", "connections": connections}


def ensure_unique_room_ids(rooms: list[dict[str, Any]]) -> None:
    seen: dict[str, int] = {}
    for index, room in enumerate(rooms, start=1):
        base_id = room["id"] or f"room_{index}"
        count = seen.get(base_id, 0) + 1
        seen[base_id] = count
        if count > 1:
            room["id"] = f"{base_id}_{count}"


def default_window_area(room_type: str, area_m2: float, orientation: str) -> float:
    if room_type == "bathroom":
        return 0.6
    if room_type == "corridor":
        return 0.0
    if room_type == "living":
        factor = 0.18 if orientation in {"S", "SE", "SW", "W"} else 0.1
        return round(max(1.5, area_m2 * factor), 1)
    if room_type == "bedroom":
        return round(max(1.2, area_m2 * 0.12), 1)
    return round(max(0.8, area_m2 * 0.1), 1)


def build_dwelling(customer: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    period = get_catalog_item(catalog, "envelope_defaults", customer["period_id"])
    ventilation = get_catalog_item(catalog, "ventilation", customer["ventilation_id"])
    ach_factor = customer["airtightness"]["ach_factor"]
    ventilation_split = ventilation_components(
        customer["ventilation_id"],
        ventilation,
        ach_factor,
    )
    dwelling_id = slugify(customer["project_name"], "customer_dwelling")

    rooms = [
        build_room(room, customer, catalog, period, ventilation_split)
        for room in customer["rooms"]
    ]
    total_area_m2 = sum(room["floor_area_m2"] for room in rooms)
    room_ids = [room["id"] for room in rooms]

    return {
        "schema_version": "0.1",
        "dwelling_id": dwelling_id,
        "metadata": {
            "name": customer["project_name"],
            "description": build_dwelling_description(customer),
            "created_by": "create_customer_experience.py",
        },
        "location": {
            "country": "FR",
            "postal_code": customer["postal_code"],
            "city": customer["city"],
            "climate_zone_id": customer["climate_zone_id"],
            "ground_albedo": 0.2,
        },
        "defaults": {
            "initial_temperature_c": 20.0,
            "building_period_ref": customer["period_id"],
            "equivalent_capacity_j_m2k": period["equivalent_capacity_j_m2k"],
            "thermal_bridge_factor": period["thermal_bridge_factor"],
            "internal_gain_w_m2": 4.0,
            "ach_h": ventilation_split["legacy_ach_h"],
            "infiltration_ach": ventilation_split["infiltration_ach"],
            "mechanical_ach": ventilation_split["mechanical_ach"],
            "recovery_efficiency": ventilation_split["recovery_efficiency"],
        },
        "rooms": rooms,
        "thermal_links": build_thermal_links(rooms, customer["thermal_layout"]),
        "systems": {
            "heating": [
                build_heating_system(
                    customer["heating_ref"],
                    room_ids,
                    total_area_m2,
                    catalog,
                ),
            ],
            "cooling": build_cooling_systems(
                customer["has_cooling"],
                rooms,
                total_area_m2,
            ),
            "ventilation": {
                "ventilation_ref": customer["ventilation_id"],
                "type": ventilation_type(customer["ventilation_id"]),
                "default_ach_h": ventilation_split["legacy_ach_h"],
                "infiltration_ach": ventilation_split["infiltration_ach"],
                "mechanical_ach": ventilation_split["mechanical_ach"],
                "recovery_efficiency": ventilation_split["recovery_efficiency"],
            },
        },
    }


def build_dwelling_description(customer: dict[str, Any]) -> str:
    position = customer.get("position", {}).get("label")
    adjacency = customer.get("adjacency", {}).get("label")
    details = [
        value
        for value in (position, adjacency)
        if value
    ]
    if not details:
        return "Logement cree depuis la CLI client ThermalTwin."
    return "Logement cree depuis la CLI client ThermalTwin. " + " / ".join(details)


def build_room(
    room_input: dict[str, Any],
    customer: dict[str, Any],
    catalog: dict[str, Any],
    period: dict[str, Any],
    ventilation_split: dict[str, float],
) -> dict[str, Any]:
    room_id = room_input["id"]
    area_m2 = room_input["floor_area_m2"]
    height_m = room_input["height_m"]
    volume_m3 = area_m2 * height_m
    windows = build_windows(room_input, customer, catalog)

    return {
        "id": room_id,
        "name": room_input["name"],
        "type": room_input["type"],
        "floor_area_m2": area_m2,
        "height_m": height_m,
        "volume_m3": round(volume_m3, 2),
        "initial_temperature_c": 20.0,
        "equivalent_capacity_j_m2k": period["equivalent_capacity_j_m2k"],
        "internal_gain_w_m2": internal_gain_for_room(room_input["type"]),
        "ventilation": {
            "mode": "ach",
            "ach_h": ventilation_split["legacy_ach_h"],
            "infiltration_ach": ventilation_split["infiltration_ach"],
            "mechanical_ach": ventilation_split["mechanical_ach"],
            "recovery_efficiency": ventilation_split["recovery_efficiency"],
            "ventilation_ref": customer["ventilation_id"],
        },
        "surfaces": build_surfaces(room_input, windows, customer, period),
        "windows": windows,
    }


def build_surfaces(
    room_input: dict[str, Any],
    windows: list[dict[str, Any]],
    customer: dict[str, Any],
    period: dict[str, Any],
) -> list[dict[str, Any]]:
    room_id = room_input["id"]
    area_m2 = room_input["floor_area_m2"]
    height_m = room_input["height_m"]
    side_width_m = math.sqrt(area_m2)
    window_area_by_orientation = {
        orientation: sum(
            window["area_m2"]
            for window in windows
            if orientation_key(window["azimuth_deg"]) == orientation
        )
        for orientation in ("north", "east", "south", "west")
    }

    surfaces = []
    for facade in room_input["facades"]:
        orientation_key_name, azimuth_deg, _label = ORIENTATIONS[facade["orientation"]]
        solar_orientation = orientation_key(azimuth_deg)
        wall_length_m = facade.get("wall_length_m", side_width_m)
        gross_wall_area = wall_length_m * height_m
        net_wall_area = max(1.0, gross_wall_area - window_area_by_orientation[solar_orientation])
        surfaces.append(
            {
                "id": f"{room_id}_{orientation_key_name}_wall",
                "type": "external_wall",
                "boundary": "exterior",
                "area_m2": round(net_wall_area, 2),
                "u_value_w_m2k": rounded_u(
                    period,
                    "external_wall",
                    customer["wall_insulation"]["u_factor"],
                ),
                "azimuth_deg": azimuth_deg,
                "tilt_deg": 90,
                "albedo": 0.35,
                "solar_to_room_factor": 0.08,
                "mask_factor": facade.get("mask_factor", 1.0),
            },
        )

    if room_input["exterior_contact"] in {"unheated_space", "party"}:
        surfaces.append(
            {
                "id": f"{room_id}_{room_input['exterior_contact']}_wall",
                "type": "party_wall",
                "boundary": room_input["exterior_contact"],
                "area_m2": round(side_width_m * height_m, 2),
                "u_value_w_m2k": rounded_u(
                    period,
                    "external_wall",
                    customer["wall_insulation"]["u_factor"],
                ),
            },
        )

    if room_input["has_roof"]:
        roof_color = customer.get("change_details", {}).get("roof_color", {})
        attic_ventilation = customer.get("change_details", {}).get("attic_ventilation", {})
        surfaces.append(
            {
                "id": f"{room_id}_roof",
                "type": "roof",
                "boundary": "exterior",
                "area_m2": round(area_m2, 2),
                "u_value_w_m2k": rounded_u(
                    period,
                    "roof",
                    customer["roof_insulation"]["u_factor"],
                ),
                "azimuth_deg": 180,
                "tilt_deg": 25,
                "albedo": roof_color.get("albedo", 0.25),
                "solar_to_room_factor": attic_ventilation.get("solar_to_room_factor", 0.02),
                "mask_factor": 1.0,
            },
        )

    if room_input["has_ground_floor"]:
        surfaces.append(
            {
                "id": f"{room_id}_floor",
                "type": "floor",
                "boundary": "ground",
                "area_m2": round(area_m2, 2),
                "u_value_w_m2k": rounded_u(
                    period,
                    "floor",
                    customer["floor_insulation"]["u_factor"],
                ),
            },
        )

    return surfaces


def build_windows(
    room_input: dict[str, Any],
    customer: dict[str, Any],
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    shutter_ref = get_catalog_item(catalog, "shutters", customer["shutter_ref"])
    windows = []
    for index, facade in enumerate(room_input["facades"], start=1):
        if facade["window_area_m2"] <= 0:
            continue
        orientation_name, azimuth_deg, _label = ORIENTATIONS[facade["orientation"]]
        window_ref_id = facade.get("window_ref") or customer["window_ref"]
        window_ref = get_catalog_item(catalog, "windows", window_ref_id)
        window_data = {
            "id": f"{room_input['id']}_{orientation_name}_window_{index}",
            "window_ref": window_ref_id,
            "area_m2": round(facade["window_area_m2"], 2),
            "u_value_w_m2k": window_ref["u_value_w_m2k"],
            "g_value": window_ref["g_value"],
            "azimuth_deg": azimuth_deg,
            "tilt_deg": 90,
            "mask_factor": facade.get("mask_factor", 1.0),
            "shutter_ref": customer["shutter_ref"],
        }
        if customer["shutter_ref"] != "none":
            window_data["shutter"] = {
                "type": shutter_ref["type"],
                "solar_factor_closed": shutter_ref["solar_factor_closed"],
                "solar_factor_open": shutter_ref["solar_factor_open"],
                "u_factor_closed": shutter_ref["u_factor_closed"],
            }
        windows.append(window_data)
    return windows


def internal_gain_for_room(room_type: str) -> float:
    if room_type in {"living", "kitchen"}:
        return 5.0
    if room_type in {"bedroom", "office"}:
        return 3.0
    return 2.0


def rounded_u(period: dict[str, Any], surface_type: str, u_factor: float) -> float:
    return round(period["u_values"][surface_type] * u_factor, 3)


def ventilation_components(
    ventilation_id: str,
    ventilation: dict[str, Any],
    ach_factor: float,
) -> dict[str, float]:
    default_ach = ventilation["default_ach_h"]
    base_infiltration_ach = 0.15 * ach_factor
    if "natural" in ventilation_id:
        infiltration_ach = default_ach * ach_factor
        mechanical_ach = 0.0
    else:
        infiltration_ach = base_infiltration_ach
        mechanical_ach = max(0.0, default_ach - 0.15)
    return {
        "legacy_ach_h": round(default_ach * ach_factor, 2),
        "infiltration_ach": round(infiltration_ach, 2),
        "mechanical_ach": round(mechanical_ach, 2),
        "recovery_efficiency": ventilation.get("recovery_efficiency", 0.0),
    }


def orientation_key(azimuth_deg: float) -> str:
    if azimuth_deg < 45 or azimuth_deg >= 315:
        return "north"
    if azimuth_deg < 135:
        return "east"
    if azimuth_deg < 225:
        return "south"
    return "west"


def build_thermal_links(
    rooms: list[dict[str, Any]],
    thermal_layout: dict[str, Any],
) -> list[dict[str, Any]]:
    if len(rooms) < 2:
        return []

    rooms_by_id = {room["id"]: room for room in rooms}
    if thermal_layout["type"] == "manual":
        connections = thermal_layout["connections"]
    elif thermal_layout["type"] == "corridor":
        hub = next(
            (room for room in rooms if room["type"] == "corridor"),
            next((room for room in rooms if room["type"] == "living"), rooms[0]),
        )
        connections = [
            {"room_a": hub["id"], "room_b": room["id"]}
            for room in rooms
            if room["id"] != hub["id"]
        ]
    else:
        hub = next((room for room in rooms if room["type"] == "living"), rooms[0])
        connections = [
            {"room_a": hub["id"], "room_b": room["id"]}
            for room in rooms
            if room["id"] != hub["id"]
        ]

    links = []
    seen_pairs = set()
    for connection in connections:
        room_a_id = connection["room_a"]
        room_b_id = connection["room_b"]
        if room_a_id == room_b_id:
            continue
        pair_key = tuple(sorted((room_a_id, room_b_id)))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        room_b = rooms_by_id[room_b_id]
        default_area_m2 = min(10.0, max(4.0, math.sqrt(room_b["floor_area_m2"]) * room_b["height_m"]))
        area_m2 = connection.get("area_m2", default_area_m2)
        links.append(
            {
                "id": f"{room_a_id}_{room_b_id}_link",
                "room_a": room_a_id,
                "room_b": room_b_id,
                "type": "internal_wall",
                "area_m2": round(area_m2, 2),
                "u_value_w_m2k": connection.get("u_value_w_m2k", 1.8),
                "opening_factor": connection.get("opening_factor", 0.8),
            },
        )
    return links


def build_heating_system(
    heating_ref: str,
    room_ids: list[str],
    total_area_m2: float,
    catalog: dict[str, Any],
) -> dict[str, Any]:
    reference = get_catalog_item(catalog, "heating_systems", heating_ref)
    return {
        "id": "main_heating",
        "system_ref": heating_ref,
        "type": reference["type"],
        "served_rooms": room_ids,
        "max_power_w": round(max(1500.0, total_area_m2 * 95.0), 0),
        "performance_ref": deepcopy(reference["performance_ref"]),
    }


def build_cooling_systems(
    has_cooling: bool,
    rooms: list[dict[str, Any]],
    total_area_m2: float,
) -> list[dict[str, Any]]:
    if not has_cooling:
        return []
    served_rooms = [
        room["id"]
        for room in rooms
        if room["type"] in {"living", "bedroom", "office"}
    ] or [room["id"] for room in rooms]
    return [
        {
            "id": "main_cooling",
            "system_ref": "air_conditioner_standard",
            "type": "air_conditioner",
            "served_rooms": served_rooms,
            "max_power_w": round(max(1200.0, total_area_m2 * 70.0), 0),
            "performance_ref": {"mode": "constant", "eer": 3.0},
        },
    ]


def ventilation_type(ventilation_id: str) -> str:
    if "double_flow" in ventilation_id:
        return "double_flow"
    if "natural" in ventilation_id:
        return "natural"
    if "simple_flow" in ventilation_id:
        return "simple_flow"
    return "other"


def selected_room_ids(customer: dict[str, Any], dwelling: dict[str, Any]) -> list[str]:
    if customer["target_scope"] == "all":
        return [room["id"] for room in dwelling["rooms"]]
    return [customer["target_scope"]]


def ensure_applicable_target(customer: dict[str, Any], dwelling: dict[str, Any]) -> bool:
    room_ids = selected_room_ids(customer, dwelling)
    if change_applies(dwelling, customer["change"]["id"], room_ids):
        return True

    print()
    print("Le changement choisi ne s'applique pas a la zone selectionnee.")
    print(change_inapplicable_reason(dwelling, customer["change"]["id"], room_ids))
    options = applicable_target_options(customer, dwelling)
    if not options:
        return False

    if not ask_yes_no("Choisir une autre zone compatible", True):
        return False

    target = choose_one("Zone compatible", options)
    customer["target_scope"] = target["id"]
    return True


def applicable_target_options(
    customer: dict[str, Any],
    dwelling: dict[str, Any],
) -> list[dict[str, str]]:
    change_id = customer["change"]["id"]
    options = []
    all_room_ids = [room["id"] for room in dwelling["rooms"]]
    if change_applies(dwelling, change_id, all_room_ids):
        options.append({"id": "all", "label": "Tout le logement"})
    for room in dwelling["rooms"]:
        if change_applies(dwelling, change_id, [room["id"]]):
            options.append({"id": room["id"], "label": room["name"]})
    return options


def change_inapplicable_reason(
    dwelling: dict[str, Any],
    change_id: str,
    room_ids: list[str],
) -> str:
    if change_id in {"roof_insulation", "reflective_roof"}:
        return "Aucune toiture n'a ete decrite dans la zone cible."
    if change_id in {"better_windows", "solar_protection"}:
        return "Aucune fenetre n'a ete decrite dans la zone cible."
    if change_id == "heat_pump":
        return "Aucun systeme de chauffage ne dessert la zone cible."
    return "La zone cible ne contient aucun element compatible."


def build_experiments(
    customer: dict[str, Any],
    dwelling: dict[str, Any],
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    change = customer["change"]
    room_ids = selected_room_ids(customer, dwelling)
    if not change_applies(dwelling, change["id"], room_ids):
        return []

    experiments = []
    for experiment_spec in selected_experiment_specs(
        change,
        dwelling,
        room_ids,
        customer.get("include_annual_experiment", True),
    ):
        base_id = f"{dwelling['dwelling_id']}_{change['id']}_{experiment_spec['id']}"
        before = build_scenario(
            base_id,
            dwelling,
            experiment_spec,
            change,
            False,
            room_ids,
            catalog,
            customer.get("setpoints"),
            customer.get("shutter_usage"),
            customer.get("annual_weather_year", 2023),
            customer.get("annual_weather_dir", "data/weather/openmeteo"),
        )
        after = build_scenario(
            base_id,
            dwelling,
            experiment_spec,
            change,
            True,
            room_ids,
            catalog,
            customer.get("setpoints"),
            customer.get("shutter_usage"),
            customer.get("annual_weather_year", 2023),
            customer.get("annual_weather_dir", "data/weather/openmeteo"),
        )
        experiments.append(
            {
                "id": base_id,
                "season": experiment_spec["season"],
                "role": experiment_spec["role"],
                "before": before,
                "after": after,
            },
        )
    return experiments


def selected_experiment_specs(
    change: dict[str, Any],
    dwelling: dict[str, Any],
    room_ids: list[str],
    include_annual_experiment: bool = True,
) -> list[dict[str, Any]]:
    specs = []
    for experiment_id in change["experiments"]:
        spec = EXPERIMENT_SPECS[experiment_id]
        if spec.get("condition") == "exposed_windows" and not has_exposed_windows(
            dwelling,
            room_ids,
        ):
            continue
        specs.append(spec)
    if include_annual_experiment:
        specs.append(EXPERIMENT_SPECS["annual_openmeteo"])
    return specs


def has_exposed_windows(dwelling: dict[str, Any], room_ids: list[str]) -> bool:
    rooms = [room for room in dwelling["rooms"] if room["id"] in room_ids]
    return any(
        orientation_key(window["azimuth_deg"]) in {"east", "south", "west"}
        for room in rooms
        for window in room["windows"]
    )


def change_applies(
    dwelling: dict[str, Any],
    change_id: str,
    room_ids: list[str],
) -> bool:
    rooms = [room for room in dwelling["rooms"] if room["id"] in room_ids]
    if change_id in {"roof_insulation", "reflective_roof"}:
        return any(
            surface["type"] == "roof"
            for room in rooms
            for surface in room["surfaces"]
        )
    if change_id in {"better_windows", "solar_protection"}:
        return any(room["windows"] for room in rooms)
    if change_id == "heat_pump":
        return any(
            any(room_id in system["served_rooms"] for room_id in room_ids)
            for system in dwelling["systems"]["heating"]
        )
    return False


def build_scenario(
    base_id: str,
    dwelling: dict[str, Any],
    experiment_spec: dict[str, Any],
    change: dict[str, Any],
    apply_change: bool,
    room_ids: list[str],
    catalog: dict[str, Any],
    setpoints: dict[str, float] | None = None,
    shutter_usage: dict[str, Any] | None = None,
    annual_weather_year: int = 2023,
    annual_weather_dir: str | Path = "data/weather/openmeteo",
) -> dict[str, Any]:
    season = experiment_spec["season"]
    scenario_setpoints = setpoints or default_setpoints_for_experiment(experiment_spec)
    weather_city = {}
    if experiment_spec["weather_mode"] == "openmeteo_annual":
        weather_city = resolve_weather_city(
            dwelling["location"].get("city"),
            dwelling["location"].get("postal_code"),
            dwelling["location"].get("climate_zone_id"),
        )
    scenario = {
        "schema_version": "0.1",
        "scenario_id": f"{base_id}_{'after' if apply_change else 'before'}",
        "dwelling_id": dwelling["dwelling_id"],
        "description": f"{experiment_spec['label']} {'apres' if apply_change else 'avant'}",
        "experiment": {
            "adaptation_id": change["id"],
            "adaptation_label": change["label"],
            "role": experiment_spec["role"],
            "label": experiment_spec["label"],
            "season": season,
            "weather_variant": experiment_spec["weather_variant"],
            "simulation_type": experiment_spec["simulation_type"],
            "weather_mode": experiment_spec["weather_mode"],
            "reason": experiment_spec["reason"],
        },
        "timestep_h": 1.0,
        "initial_temperatures_c": {
            room["id"]: initial_temperature_for_experiment(experiment_spec)
            for room in dwelling["rooms"]
        },
        "climate_zone_id": dwelling["location"]["climate_zone_id"],
        "setpoints": scenario_setpoints,
        "weather": build_scenario_weather(
            experiment_spec,
            dwelling,
            catalog,
            weather_city,
            annual_weather_year,
            annual_weather_dir,
        ),
        "energy_prices": {"electricity_eur_kwh": 0.25},
        "co2_factors": {"electricity_kg_kwh": 0.06},
    }
    if weather_city:
        scenario["experiment"].update(
            {
                "requested_city": weather_city["requested_city"],
                "weather_city": weather_city["weather_city"],
                "weather_match_mode": weather_city["match_mode"],
                "weather_year": annual_weather_year,
            },
        )
    if season in {"summer", "annual"}:
        scenario["controls"] = {
            "shutters": build_summer_shutter_controls(
                experiment_spec["duration_days"],
                shutter_usage,
            ),
        }
        if season == "summer":
            scenario["controls"]["natural_ventilation"] = build_summer_natural_ventilation_controls()
    if apply_change:
        retrofit = build_retrofit(dwelling, change["id"], room_ids, catalog)
        if retrofit:
            scenario["retrofit"] = retrofit
    return scenario


def default_setpoints_for_experiment(experiment_spec: dict[str, Any]) -> dict[str, float]:
    if experiment_spec["season"] == "summer":
        return {"heating_c": 18.0, "cooling_c": 26.0}
    if experiment_spec["season"] == "annual":
        return {"heating_c": 19.0, "cooling_c": 26.0}
    return {"heating_c": 19.0, "cooling_c": 28.0}


def initial_temperature_for_experiment(experiment_spec: dict[str, Any]) -> float:
    if experiment_spec["season"] == "summer":
        return 26.0
    if experiment_spec["season"] == "annual":
        return 20.0
    return 19.0


def build_scenario_weather(
    experiment_spec: dict[str, Any],
    dwelling: dict[str, Any],
    catalog: dict[str, Any],
    weather_city: dict[str, str],
    annual_weather_year: int,
    annual_weather_dir: str | Path,
) -> dict[str, Any]:
    if experiment_spec["weather_mode"] == "openmeteo_annual":
        city = weather_city["weather_city"]
        return {
            "source": f"openmeteo_{city}_{annual_weather_year}",
            "weather_ref": thermal_weather_ref(
                city,
                annual_weather_year,
                output_dir=annual_weather_dir,
            ),
        }
    return build_weather(experiment_spec, dwelling["location"]["climate_zone_id"], catalog)


def build_weather(
    experiment_spec: dict[str, Any],
    climate_zone_id: str,
    catalog: dict[str, Any],
) -> dict[str, Any]:
    weather_variant = experiment_spec["weather_variant"]
    duration_days = experiment_spec["duration_days"]
    default_profile = weather_profile_for_variant(climate_zone_id, weather_variant)

    hourly = []
    for hour in range(duration_days * 24):
        day = hour // 24
        hour_in_day = hour % 24
        if weather_variant == "summer_long_with_heatwave" and 27 <= day <= 29:
            profile_id = weather_profile_for_variant(climate_zone_id, "summer_heatwave")
        else:
            profile_id = default_profile
        weather_profile = get_weather_profile_reference(catalog, profile_id)
        temperature_profile = weather_profile["temperature_profile"]
        base_temp = temperature_profile["base_temp_c"]
        amplitude = temperature_profile["amplitude_c"]
        phase_hour = temperature_profile.get("phase_hour", 8)
        outdoor_temperature_c = base_temp + amplitude * math.sin(
            2.0 * math.pi * (hour_in_day - phase_hour) / 24.0,
        )
        weather_point = {
            "hour": hour,
            "month": month_for_weather_profile(weather_profile),
            "outdoor_temperature_c": round(outdoor_temperature_c, 2),
            "solar_irradiance_w_m2": solar_profile(weather_profile, hour_in_day),
        }
        hourly.append(weather_point)
    return {"source": f"generated_{default_profile}_{climate_zone_id}", "hourly": hourly}


def weather_profile_for_variant(climate_zone_id: str, weather_variant: str) -> str:
    climate_family = climate_family_for_zone(climate_zone_id)
    if weather_variant == "summer_heatwave":
        profile_type = "heatwave_reference"
    elif weather_variant == "summer_long_with_heatwave":
        profile_type = "summer_typical"
    else:
        profile_type = "winter_design"
    return f"{climate_family}_{profile_type}"


def climate_family_for_zone(climate_zone_id: str) -> str:
    if climate_zone_id == "FR_H3":
        return "H3"
    if climate_zone_id.startswith("FR_H1"):
        return "H1"
    return "H2"


def month_for_weather_profile(weather_profile: dict[str, Any]) -> int:
    if weather_profile["profile_type"] == "winter_design":
        return 1
    return 7


def solar_profile(weather_profile: dict[str, Any], hour_in_day: int) -> dict[str, float]:
    profile = weather_profile["solar_profile"]
    if profile["mode"] == "winter_reference":
        peak = max(0.0, math.sin(math.pi * (hour_in_day - 8) / 8.0))
        return {
            "north": round(profile["north_peak_w_m2"] * peak, 2),
            "east": round(
                (
                    profile["east_morning_peak_w_m2"]
                    if hour_in_day < 13
                    else profile["east_afternoon_peak_w_m2"]
                )
                * peak,
                2,
            ),
            "south": round(profile["south_peak_w_m2"] * peak, 2),
            "west": round(
                (
                    profile["west_afternoon_peak_w_m2"]
                    if hour_in_day > 12
                    else profile["west_morning_peak_w_m2"]
                )
                * peak,
                2,
            ),
            "roof": round(profile["roof_peak_w_m2"] * peak, 2),
        }

    peak = max(0.0, math.sin(math.pi * (hour_in_day - 6) / 13.0))
    return {
        "north": round(profile["north_peak_w_m2"] * peak, 2),
        "east": round(
            (
                profile["east_morning_peak_w_m2"]
                if hour_in_day < 13
                else profile["east_afternoon_peak_w_m2"]
            )
            * peak,
            2,
        ),
        "south": round(profile["south_peak_w_m2"] * peak, 2),
        "west": round(
            (
                profile["west_afternoon_peak_w_m2"]
                if hour_in_day > 12
                else profile["west_morning_peak_w_m2"]
            )
            * peak,
            2,
        ),
        "roof": round(profile["roof_peak_w_m2"] * peak, 2),
    }


def build_summer_shutter_controls(
    duration_days: int,
    shutter_usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    usage_id = (shutter_usage or {}).get("id", "partial")
    if usage_id == "none":
        return {"default_opening_ratio": 1.0, "hourly": []}
    if usage_id == "day_closed":
        daytime_opening_ratio = 0.1
    elif usage_id == "rare":
        daytime_opening_ratio = 0.75
    else:
        daytime_opening_ratio = 0.25

    return {
        "default_opening_ratio": 1.0,
        "hourly": [
            {"hour": hour, "opening_ratio": daytime_opening_ratio}
            for hour in range(duration_days * 24)
            if 8 <= hour % 24 <= 19
        ],
    }


def build_summer_natural_ventilation_controls() -> dict[str, Any]:
    return {
        "default_ach": 0.0,
        "smart_night_cooling": True,
        "smart_ach": 4.0,
    }


def build_retrofit(
    dwelling: dict[str, Any],
    change_id: str,
    room_ids: list[str],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    rooms = [room for room in dwelling["rooms"] if room["id"] in room_ids]
    if change_id == "roof_insulation":
        return clean_retrofit({
            "surface_overrides": [
                {"surface_id": surface["id"], "u_value_w_m2k": 0.18}
                for room in rooms
                for surface in room["surfaces"]
                if surface["type"] == "roof"
            ],
        })
    if change_id == "reflective_roof":
        return clean_retrofit({
            "surface_overrides": [
                {
                    "surface_id": surface["id"],
                    "albedo": 0.75,
                }
                for room in rooms
                for surface in room["surfaces"]
                if surface["type"] == "roof"
            ],
        })
    if change_id == "better_windows":
        window_ref = get_catalog_item(catalog, "windows", "double_glazing_low_e")
        return clean_retrofit({
            "window_overrides": [
                {
                    "window_id": window["id"],
                    "window_ref": "double_glazing_low_e",
                    "u_value_w_m2k": window_ref["u_value_w_m2k"],
                    "g_value": window_ref["g_value"],
                }
                for room in rooms
                for window in room["windows"]
            ],
        })
    if change_id == "solar_protection":
        shutter_ref = get_catalog_item(catalog, "shutters", "roller_shutter_standard")
        return clean_retrofit({
            "shutter_overrides": [
                {
                    "window_id": window["id"],
                    "type": shutter_ref["type"],
                    "solar_factor_closed": 0.08,
                    "solar_factor_open": shutter_ref["solar_factor_open"],
                    "u_factor_closed": shutter_ref["u_factor_closed"],
                }
                for room in rooms
                for window in room["windows"]
            ],
        })
    if change_id == "heat_pump":
        reference = get_catalog_item(catalog, "heating_systems", "air_air_heat_pump_standard")
        return clean_retrofit({
            "system_overrides": [
                {
                    "category": "heating",
                    "system_id": system["id"],
                    "system_ref": "air_air_heat_pump_standard",
                    "type": reference["type"],
                    "energy_vector": reference["energy_vector"],
                    "performance_ref": reference["performance_ref"],
                }
                for system in dwelling["systems"]["heating"]
                if any(room_id in system["served_rooms"] for room_id in room_ids)
            ],
        })
    return {}


def clean_retrofit(retrofit: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        key: value
        for key, value in retrofit.items()
        if value
    }


def write_json(output_path: str | Path, payload: dict[str, Any]) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def write_text(output_path: str | Path, content: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_customer_experience(args: argparse.Namespace) -> None:
    catalog = load_reference_catalog(args.reference_dir)
    customer = collect_customer_input(catalog)
    customer["annual_weather_year"] = args.annual_weather_year
    customer["annual_weather_dir"] = args.annual_weather_dir
    dwelling = build_dwelling(customer, catalog)
    validate_dwelling(dwelling)
    resolved_dwelling = resolve_dwelling_references(dwelling, catalog)
    target_is_applicable = ensure_applicable_target(customer, resolved_dwelling)
    experiments = build_experiments(customer, resolved_dwelling, catalog)

    output_dir = Path(args.output_dir) / dwelling["dwelling_id"]
    write_json(output_dir / "dwelling.json", dwelling)
    print()
    print(f"Logement exporte: {output_dir / 'dwelling.json'}")

    if not target_is_applicable or not experiments:
        print("Aucune expérience lancée: le changement choisi ne s'applique pas aux elements saisis.")
        return

    for experiment in experiments:
        prepare_experiment_weather(experiment, args)
        before = experiment["before"]
        after = experiment["after"]
        validate_scenario(before)
        validate_scenario(after)
        before_path = output_dir / f"{experiment['id']}_before.json"
        after_path = output_dir / f"{experiment['id']}_after.json"
        comparison_path = output_dir / f"{experiment['id']}_comparison.json"
        report_path = output_dir / f"{experiment['id']}_comparison_report.json"
        html_path = output_dir / f"{experiment['id']}_report.html"
        summary_path = output_dir / f"{experiment['id']}_customer_summary.json"
        write_json(before_path, before)
        write_json(after_path, after)

        comparison = compare_scenarios(
            resolved_dwelling,
            before,
            after,
            args.air_density_kg_m3,
            args.air_heat_capacity_j_kgk,
        )
        write_json(comparison_path, comparison)
        report = build_report_model(comparison)
        write_json(report_path, report)
        write_text(html_path, render_report_html(report))
        customer_summary = build_customer_summary(experiment["season"], comparison)
        write_json(summary_path, customer_summary)
        print(f"Scenario avant: {before_path}")
        print(f"Scenario apres: {after_path}")
        print(f"Comparaison: {comparison_path}")
        print(f"Rapport JSON: {report_path}")
        print(f"Rapport HTML: {html_path}")
        print(f"Resume client: {summary_path}")
        print_customer_summary(customer_summary)


def prepare_experiment_weather(experiment: dict[str, Any], args: argparse.Namespace) -> None:
    """Ensure external annual weather exists and resolve it before simulation."""
    if experiment["role"] != "annual":
        return

    weather_city = experiment["before"]["experiment"]["weather_city"]
    weather_year = experiment["before"]["experiment"]["weather_year"]
    weather_path = ensure_openmeteo_thermal_weather(
        weather_city,
        weather_year,
        output_dir=args.annual_weather_dir,
        model=args.openmeteo_model,
        cache_dir=args.openmeteo_cache_dir,
    )
    print(f"Meteo annuelle Open-Meteo: {weather_city} {weather_year} -> {weather_path}")

    for scenario_key in ("before", "after"):
        resolve_scenario_weather_reference(experiment[scenario_key], Path.cwd())


def build_customer_summary(season: str, comparison: dict[str, Any]) -> dict[str, Any]:
    key_room_id, room = most_improved_room(comparison)
    energy = comparison["summary"]["energy_savings"]
    driver = comparison["summary"]["main_gain_driver"]
    experiment = comparison["experiment"]
    return {
        "season": season,
        "dwelling_id": comparison["dwelling_id"],
        "before_scenario_id": comparison["before_scenario_id"],
        "after_scenario_id": comparison["after_scenario_id"],
        "experiment": {
            "adaptation_id": experiment.get("adaptation_id", "unknown"),
            "adaptation_label": experiment.get("adaptation_label", ""),
            "role": experiment.get("role", "primary"),
            "label": experiment.get("label", ""),
            "weather_variant": experiment.get("weather_variant", ""),
            "simulation_type": experiment.get("simulation_type", ""),
            "weather_mode": experiment.get("weather_mode", ""),
            "requested_city": experiment.get("requested_city", ""),
            "weather_city": experiment.get("weather_city", ""),
            "weather_match_mode": experiment.get("weather_match_mode", ""),
            "weather_year": experiment.get("weather_year"),
            "reason": experiment.get("reason", ""),
            "duration_hours": round(experiment["duration_hours"], 2),
            "duration_days": round(experiment["duration_days"], 2),
            "scope_notice": (
                "Ces resultats portent uniquement sur une simulation de "
                f"{experiment['duration_days']:.2f} jours."
            ),
            "annual_projection_notice": (
                "Cette experience est une simulation annuelle."
                if experiment.get("simulation_type") == "annual"
                else "Aucune projection annuelle n'est calculee dans ce rapport."
            ),
            "weather_source": experiment["weather_source"],
            "outdoor_temperature_min_c": round(
                experiment["weather_summary"]["outdoor_temperature_min_c"],
                1,
            ),
            "outdoor_temperature_max_c": round(
                experiment["weather_summary"]["outdoor_temperature_max_c"],
                1,
            ),
            "heating_setpoint_c": experiment["setpoints"]["heating_c"],
            "cooling_setpoint_c": experiment["setpoints"]["cooling_c"],
            "before_description": experiment["before_description"],
            "after_description": experiment["after_description"],
        },
        "headline": {
            "electricity_saved_kwh": round(energy["electricity_saved_kwh"], 2),
            "cost_saved_eur": round(energy["cost_saved_eur"], 2),
            "co2_saved_kg": round(energy["co2_saved_kg"], 2),
            "main_gain_driver": driver["label"],
        },
        "comfort": {
            "room_id": key_room_id,
            "room_name": room["room_name"],
            "max_temperature_before_c": round(room["before_max_temperature_c"], 1),
            "max_temperature_after_c": round(room["after_max_temperature_c"], 1),
            "max_temperature_reduction_c": round(room["delta_max_temperature_c"], 1),
            "hot_discomfort_before_c_h": round(room["before_hot_degree_hours"], 0),
            "hot_discomfort_after_c_h": round(room["after_hot_degree_hours"], 0),
            "hot_discomfort_reduced_c_h": round(room["delta_hot_degree_hours"], 0),
            "cold_discomfort_before_c_h": round(room["before_cold_degree_hours"], 0),
            "cold_discomfort_after_c_h": round(room["after_cold_degree_hours"], 0),
            "cold_discomfort_reduced_c_h": round(room["delta_cold_degree_hours"], 0),
            "explanation": discomfort_explanation(room),
        },
    }


def most_improved_room(comparison: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    rooms = comparison["deltas"]["rooms"]
    return max(
        rooms.items(),
        key=lambda item: (
            item[1]["delta_hot_degree_hours"]
            + item[1]["delta_cold_degree_hours"]
            + max(0.0, item[1]["delta_max_temperature_c"]) * 24.0
        ),
    )


def discomfort_explanation(room: dict[str, Any]) -> str:
    if room["delta_hot_degree_hours"] > 0:
        return (
            "L'inconfort chaud cumule correspond aux heures passees au-dessus "
            "de la consigne de confort, ponderees par l'ecart de temperature."
        )
    if room["delta_cold_degree_hours"] > 0:
        return (
            "L'inconfort froid cumule correspond aux heures passees sous la "
            "consigne de chauffage, ponderees par l'ecart de temperature."
        )
    if room["delta_max_temperature_c"] > 0:
        return "La temperature maximale baisse, sans gain significatif sur l'inconfort cumule."
    return "Le confort simule reste globalement stable."


def print_customer_summary(summary: dict[str, Any]) -> None:
    comfort = summary["comfort"]
    experiment = summary["experiment"]
    headline = summary["headline"]
    print(f"Lecture {summary['season']}:")
    role_labels = {
        "primary": "principale",
        "secondary": "secondaire",
        "annual": "annuelle",
    }
    role_label = role_labels.get(experiment["role"], "simulation")
    print(
        "- Experience: "
        f"{role_label}, {experiment['label'] or summary['season']}, "
        f"{experiment['duration_days']:.1f} jours "
        f"({experiment['duration_hours']:.0f} h), "
        f"meteo {experiment['weather_source']}, "
        f"{experiment['outdoor_temperature_min_c']:.1f} C -> "
        f"{experiment['outdoor_temperature_max_c']:.1f} C ext."
    )
    if experiment.get("simulation_type") == "annual":
        print("- Portee: resultats simules sur une annee meteo complete.")
    else:
        print("- Portee: resultats simules sur cette periode, sans projection annuelle.")
    if headline["electricity_saved_kwh"] > 0:
        print(
            "- Energie: "
            f"{headline['electricity_saved_kwh']:.2f} kWh, "
            f"{headline['cost_saved_eur']:.2f} EUR, "
            f"{headline['co2_saved_kg']:.2f} kg CO2 economises"
        )
    elif headline["electricity_saved_kwh"] < 0:
        print(
            "- Energie: "
            f"{abs(headline['electricity_saved_kwh']):.2f} kWh supplementaires"
        )
    else:
        print("- Energie: consommation inchangee dans cette simulation")
    print(
        "- Piece la plus impactee: "
        f"{comfort['room_name']} "
        f"({comfort['max_temperature_before_c']:.1f} C -> "
        f"{comfort['max_temperature_after_c']:.1f} C en temperature max)"
    )
    if comfort["hot_discomfort_reduced_c_h"] > 0:
        print(
            "- Confort ete: inconfort chaud reduit de "
            f"{comfort['hot_discomfort_reduced_c_h']:.0f} C.h "
            f"({comfort['hot_discomfort_before_c_h']:.0f} -> "
            f"{comfort['hot_discomfort_after_c_h']:.0f} C.h)"
        )
    elif comfort["cold_discomfort_reduced_c_h"] > 0:
        print(
            "- Confort hiver: inconfort froid reduit de "
            f"{comfort['cold_discomfort_reduced_c_h']:.0f} C.h "
            f"({comfort['cold_discomfort_before_c_h']:.0f} -> "
            f"{comfort['cold_discomfort_after_c_h']:.0f} C.h)"
        )
    else:
        print("- Confort: stable dans cette simulation")
    print(f"- Explication principale: {headline['main_gain_driver']}")


def main() -> None:
    run_customer_experience(parse_args())


if __name__ == "__main__":
    main()
