# ThermalTwin MVP

ThermalTwin est un prototype de moteur thermique simplifie pour modeliser un logement piece par piece, comparer des scenarios avant/apres, et produire des sorties exploitables pour une future interface ou un rapport.

Le modele actuel est volontairement MVP :

- pertes par transmission et ventilation ;
- inertie 1R1C par piece ;
- apports internes ;
- apports solaires simplifiés par orientation ;
- volets/stores via facteur multiplicatif ;
- albedo des parois opaques ;
- couplage thermique entre pieces ;
- chauffage/climatisation plafonnes par equipement.

## Structure

```text
data/
  examples/      Exemples de logement et scenarios
  reference/     Valeurs de reference MVP
docs/            Documentation data model
schemas/         JSON Schema logement
scripts/         Scripts executables
thermal_model/   Loaders, resolution de references, validation
utils/           Fonctions thermiques pures
tests/           Tests automatises
```

## Commandes utiles

Pertes statiques :

```bash
python3 scripts/compute_static_losses.py
```

Simulation horaire hiver :

```bash
python3 scripts/simulate_1r1c.py
```

Simulation canicule avant toiture reflective :

```bash
python3 scripts/simulate_1r1c.py \
  data/examples/house_simple.json \
  data/examples/scenario_heatwave_before.json \
  --output-json outputs/heatwave_before.json \
  --output-csv outputs/heatwave_before.csv
```

Simulation canicule apres toiture reflective :

```bash
python3 scripts/simulate_1r1c.py \
  data/examples/house_simple.json \
  data/examples/scenario_heatwave.json \
  --output-json outputs/heatwave_after.json \
  --output-csv outputs/heatwave_after.csv
```

Comparaison avant/apres :

```bash
python3 scripts/compare_scenarios.py
```

Export comparaison JSON :

```bash
python3 scripts/compare_scenarios.py --output-json outputs/compare_heatwave.json
```

Generation rapide des rapports HTML sans questionnaire client :

```bash
python3 scripts/generate_report_fixtures.py
```

Pour ne regenerer qu'une adaptation :

```bash
python3 scripts/generate_report_fixtures.py --adaptation better_windows
```

Validation des entrees :

```bash
python3 scripts/validate_inputs.py \
  --scenario data/examples/scenario_simple.json \
  --scenario data/examples/scenario_heatwave_before.json \
  --scenario data/examples/scenario_heatwave.json
```

Recuperation meteo annuelle Open-Meteo pour une ville :

```bash
python3 scripts/fetch_openmeteo_weather.py --city Bordeaux --year 2023
```

Recuperation de toutes les villes cles avec moyenne de plusieurs annees :

```bash
python3 scripts/fetch_openmeteo_weather.py \
  --city all \
  --year 2021 \
  --year 2022 \
  --year 2023 \
  --mode mean
```

Le script ecrit les donnees brutes en Parquet et une meteo JSON compatible avec
les scenarios ThermalTwin dans `data/weather/openmeteo/`. Ces fichiers sont des
artefacts locaux ignores par Git.

Un scenario peut ensuite referencer ce fichier meteo sans embarquer les heures :

```json
{
  "weather": {
    "weather_ref": "data/weather/openmeteo/thermal/bordeaux_2023.weather.json"
  }
}
```

`load_scenario()` resout automatiquement cette reference avant la simulation.

Le questionnaire client ajoute aussi une experience annuelle Open-Meteo pour
chaque changement teste. Si la ville saisie n'est pas dans les villes cles,
elle est rapprochee d'une ville meteo supportee via le code postal puis la zone
climatique.

## Environnement Python

Le code courant fonctionne sans dependance externe pour les scripts principaux.

Pour lancer les tests et les validations JSON Schema, creer un environnement local :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Puis lancer :

```bash
python3 -m pytest
```

Avec conda :

```bash
conda activate thermique
python -m pytest
```

## Etat actuel

Resultat attendu de la comparaison toiture reflective :

```text
Electricite kWh: 13.83 -> 11.29 (gain 2.54)
Cout EUR: 3.46 -> 2.82 (gain 0.63)
CO2 kg: 0.83 -> 0.68 (gain 0.15)
```

Les valeurs de `data/reference/` sont des hypotheses MVP a calibrer. Elles ne doivent pas encore etre traitees comme une base certifiee ou reglementaire.
