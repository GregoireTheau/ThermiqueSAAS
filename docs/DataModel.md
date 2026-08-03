# Data model MVP

Ce document definit la structure de donnees minimale pour representer un logement ThermalTwin. Le but est d'avoir un format stable que le formulaire, l'import de plan, la maquette et le moteur thermique pourront partager.

Le format de depart est du JSON statique. On passera a une base SQLite seulement si le volume de donnees ou les besoins d'administration le justifient.

---

## 1. Principes

### 1.1 Objectif du format

Un fichier logement doit permettre de calculer :

- les deperditions par piece ;
- les apports solaires par vitrage et par paroi opaque ;
- le couplage thermique entre pieces ;
- les effets de ventilation simplifiee ;
- les besoins chauffage/climatisation par scenario.

### 1.2 Ce qui n'est pas dans ce fichier

Le logement ne doit pas contenir les resultats de simulation. Les resultats seront produits par le moteur et stockes ailleurs.

Le logement ne doit pas non plus contenir toute la base materiaux. Il peut soit referencer un materiau par ID, soit embarquer une valeur simplifiee comme `u_value_w_m2k` pour les premiers tests.

Quand un champ reference existe, par exemple `window_ref`, le moteur doit charger les valeurs depuis `data/reference`. Si une valeur explicite est aussi presente dans le logement, elle est prioritaire. Cela permet de partir d'un choix standard puis de le corriger manuellement.

---

## 2. Unites

Toutes les donnees doivent suivre ces unites :

| Grandeur | Champ type | Unite |
|---|---:|---|
| Surface | `area_m2` | m2 |
| Volume | `volume_m3` | m3 |
| Hauteur | `height_m` | m |
| Temperature | `temperature_c` | deg C |
| Coefficient U | `u_value_w_m2k` | W/m2.K |
| Facteur solaire vitrage | `g_value` | sans unite |
| Albedo | `albedo` | sans unite, 0 a 1 |
| Absorptivite | `absorptivity` | sans unite, 0 a 1 |
| Capacite thermique | `thermal_capacity_j_k` | J/K |
| Capacite surfacique | `equivalent_capacity_j_m2k` | J/m2.K |
| Debit d'air | `airflow_m3_s` | m3/s |
| Renouvellement d'air | `ach_h` | volumes/heure |
| Puissance | `power_w` | W |
| Energie | `energy_kwh` | kWh |
| Orientation | `azimuth_deg` | degres, 0 nord, 90 est, 180 sud, 270 ouest |
| Inclinaison | `tilt_deg` | degres, 0 horizontal, 90 vertical |

---

## 3. Structure generale d'un logement

```json
{
  "schema_version": "0.1",
  "dwelling_id": "house_simple",
  "metadata": {},
  "location": {},
  "defaults": {},
  "rooms": [],
  "thermal_links": [],
  "systems": {}
}
```

### 3.1 `schema_version`

Version de la structure JSON. Elle permettra de faire evoluer le format sans casser les anciens fichiers.

### 3.2 `dwelling_id`

Identifiant unique du logement dans nos exemples ou dans l'application.

### 3.3 `metadata`

Informations non physiques :

```json
{
  "name": "Maison simple MVP",
  "description": "Exemple de maison de plain-pied pour tester le moteur.",
  "created_by": "manual_example"
}
```

### 3.4 `location`

Informations de localisation et orientation generale :

```json
{
  "country": "US",
  "postal_code": "80202",
  "city": "Denver",
  "state": "Colorado",
  "county": "Denver",
  "county_fips": "08031",
  "latitude": 39.7392,
  "longitude": -104.9903,
  "timezone": "America/Denver",
  "climate_zone_id": "US_IECC_2021_5B",
  "climate_zone_code": "5B",
  "climate_zone_standard": "2021 IECC / ASHRAE 169-2013",
  "ground_albedo": 0.2
}
```

La zone est résolue par comté depuis `climate_zones_us.json`. Elle décrit le
contexte du code bâtiment et ne sélectionne ni ne corrige la météo locale.

### 3.5 `defaults`

Hypotheses utilisees si une piece ou une paroi ne specifie pas tout :

```json
{
  "initial_temperature_c": 20.0,
  "construction_era_ref": "us_2000_2009",
  "equivalent_capacity_j_m2k": 165000,
  "thermal_bridge_factor": 0.1,
  "internal_gain_w_m2": 5.0,
  "ach_h": 0.5
}
```

Ces valeurs sont des hypotheses de test dans l'exemple. Elles devront ensuite venir de la base de reference ou de choix utilisateur.

---

## 4. Pieces

Chaque piece est un objet dans `rooms`.

```json
{
  "id": "living_room",
  "name": "Salon",
  "type": "living",
  "floor_area_m2": 32.0,
  "height_m": 2.5,
  "volume_m3": 80.0,
  "initial_temperature_c": 20.0,
  "equivalent_capacity_j_m2k": 165000,
  "internal_gain_w_m2": 5.0,
  "ventilation": {},
  "surfaces": [],
  "windows": []
}
```

### 4.1 Champs obligatoires MVP

- `id` : identifiant stable, sans espace ;
- `name` : nom affichable ;
- `type` : categorie simple ;
- `floor_area_m2` ;
- `height_m` ;
- `volume_m3` ;
- `surfaces` ;
- `windows`.

### 4.2 `ventilation`

Ventilation simplifiee par ACH :

```json
{
  "mode": "ach",
  "ach_h": 0.5,
  "ventilation_ref": "simple_flow"
}
```

Si absent, le moteur peut utiliser `defaults.ach_h`.

---

## 5. Parois

Les parois sont stockees dans `room.surfaces`.

```json
{
  "id": "living_south_wall",
  "type": "external_wall",
  "boundary": "exterior",
  "area_m2": 18.0,
  "u_value_w_m2k": 0.55,
  "azimuth_deg": 180,
  "tilt_deg": 90,
  "albedo": 0.35,
  "solar_to_room_factor": 0.08,
  "mask_factor": 1.0
}
```

### 5.1 Types de parois

Valeurs conseillees :

- `external_wall`
- `roof`
- `floor`
- `internal_wall`
- `party_wall`

### 5.2 `boundary`

Indique ce qu'il y a de l'autre cote :

- `exterior` : dehors ;
- `ground` : sol ;
- `unheated_space` : garage, cave, combles non chauffes ;
- `room` : autre piece simulee ;
- `party` : voisin / mur mitoyen.

### 5.3 Champs solaires

Pour les parois exposees au soleil :

- `azimuth_deg` ;
- `tilt_deg` ;
- `albedo` ;
- `solar_to_room_factor` ;
- `mask_factor`.

`solar_to_room_factor` correspond au `eta_opaque` de `DocumentationThermique.md`.

Pour les surfaces non exposees, ces champs peuvent etre absents.

---

## 6. Vitrages

Les vitrages sont stockes dans `room.windows`.

```json
{
  "id": "living_south_window",
  "window_ref": "double_glazing_standard",
  "area_m2": 4.0,
  "u_value_w_m2k": 1.6,
  "g_value": 0.55,
  "azimuth_deg": 180,
  "tilt_deg": 90,
  "mask_factor": 1.0,
  "shutter_ref": "roller_shutter_standard",
  "shutter": {
    "type": "roller_shutter",
    "solar_factor_closed": 0.15,
    "solar_factor_open": 1.0,
    "u_factor_closed": 0.8
  }
}
```

### 6.1 Champs obligatoires MVP

- `id` ;
- `area_m2` ;
- `u_value_w_m2k` ;
- `g_value` ;
- `azimuth_deg` ;
- `tilt_deg`.

### 6.2 Volets et stores

Le bloc `shutter` est optionnel. Il sert a calculer :

- `F_volet` pour reduire l'apport solaire ;
- `F_U_volet` pour corriger le coefficient U si le volet est ferme.

Le planning d'ouverture ne doit pas etre dans le logement. Il appartient au scenario.

---

## 7. Couplage entre pieces

Les liens thermiques entre pieces sont stockes dans `thermal_links`.

```json
{
  "id": "living_bedroom_link",
  "room_a": "living_room",
  "room_b": "bedroom",
  "type": "internal_wall",
  "area_m2": 10.0,
  "u_value_w_m2k": 1.8,
  "opening_factor": 1.0
}
```

Le moteur peut calculer :

```text
H_ij = opening_factor * U * A
Phi_j_vers_i = H_ij * (T_j - T_i)
```

Pour une porte souvent ouverte, `opening_factor` peut etre superieur a 1. Pour une separation forte, il peut rester a 1 ou moins selon l'hypothese retenue.

---

## 8. Systemes

Le bloc `systems` liste les equipements disponibles dans le logement.

```json
{
  "heating": [],
  "cooling": [],
  "ventilation": {}
}
```

### 8.1 Chauffage

```json
{
  "id": "living_heat_pump_unit",
  "system_ref": "air_source_heat_pump_standard",
  "type": "heat_pump",
  "served_rooms": ["living_room"],
  "max_power_w": 3500,
  "performance_ref": {
    "mode": "constant",
    "cop": 3.2
  }
}
```

Pour un chauffage électrique résistif :

```json
{
  "id": "bedroom_resistance_heat",
  "type": "electric_resistance",
  "served_rooms": ["bedroom"],
  "max_power_w": 1500,
  "performance_ref": {
    "mode": "constant",
    "cop": 1.0
  }
}
```

### 8.2 Climatisation

```json
{
  "id": "living_ac",
  "type": "air_conditioner",
  "served_rooms": ["living_room"],
  "max_power_w": 3000,
  "performance_ref": {
    "mode": "constant",
    "eer": 3.0
  }
}
```

---

## 9. Structure d'un scenario futur

Le scenario ne sera pas cree dans cette etape, mais il devra contenir :

- consignes chauffage/climatisation ;
- planning volets/stores ;
- planning occupation ;
- meteo ou reference meteo ;
- modifications avant/apres travaux ;
- prix energie ;
- aucun facteur CO2 commercial au lancement US ; une future version devra référencer une source électrique régionale datée.

Exemple de direction :

```json
{
  "scenario_id": "scenario_reflective_roof",
  "dwelling_id": "house_simple",
  "setpoints": {
    "heating_c": 19.0,
    "cooling_c": 26.0
  },
  "retrofit": {
    "surfaces": [
      {
        "surface_id": "living_roof",
        "after": {
          "albedo": 0.75
        }
      }
    ]
  }
}
```

---

## 10. Premieres validations a coder plus tard

Avant de lancer une simulation, il faudra verifier :

- chaque `room.id` est unique ;
- chaque `surface.id` et `window.id` est unique ;
- les `thermal_links` referencent des pieces existantes ;
- les surfaces et volumes sont positifs ;
- les `u_value_w_m2k` sont positifs ;
- les facteurs `g_value`, `albedo`, `mask_factor`, `solar_factor_*` sont entre 0 et 1 ;
- les orientations sont entre 0 et 360 degres ;
- les inclinaisons sont entre 0 et 180 degres ;
- chaque equipement reference des pieces existantes.

---

## 11. Prochaine evolution

Apres ce document et `data/examples/house_simple.json`, les prochaines etapes naturelles sont :

1. creer `schemas/dwelling.schema.json` pour valider automatiquement les logements ;
2. creer `data/reference/materials.json`, `windows.json`, `heating_systems.json`, `cooling_systems.json` ;
3. creer `data/examples/scenario_simple.json` ;
4. coder un loader Python qui lit le JSON et appelle les fonctions de `utils/`.
