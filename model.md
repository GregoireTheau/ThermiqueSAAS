# Modèle thermique actuel

Ce document décrit l’état actuel du modèle thermique dans le code. Il ne décrit pas un objectif réglementaire ni une méthode DPE : c’est la trace concrète du moteur utilisé aujourd’hui par l’interface SaaS et par `scripts/create_customer_experience.py`.

Sources principales du code :

- `thermal_model/simulation.py`
- `thermal_model/static_losses.py`
- `utils/*.py`
- `scripts/create_customer_experience.py`
- `thermal_saas/business_flow.py`
- `data/reference/*.json`

## 1. Structure Générale

Le moteur est un modèle horaire multi-pièces de type 1R1C simplifié.

Chaque pièce est représentée par :

- une température d’air unique `T_room` en °C ;
- une capacité thermique équivalente `C_room` en J/K ;
- des pertes par transmission ;
- des pertes ou gains par ventilation ;
- des apports internes ;
- des apports solaires ;
- des échanges éventuels avec d’autres pièces ;
- un système de chauffage et/ou de climatisation plafonné en puissance.

L’intégration temporelle est explicite, avec un pas horaire dans les scénarios générés :

```text
dt = timestep_h * 3600
T_next = T_current + dt / C_room * Phi_net
```

où `Phi_net` est la puissance nette entrant dans la pièce, en W.

Convention de signe :

- puissance positive : chaleur entrant dans la pièce ;
- puissance négative : chaleur sortant de la pièce.

## 2. Constantes Globales

Valeurs par défaut utilisées par le SaaS :

```text
rho_air = 1.2 kg/m3
cp_air = 1005 J/kg.K
dt = 1 h dans les scénarios générés
seuil inconfort froid = 19 °C
seuil inconfort chaud = 26 °C
prix électricité = 0.18 $/kWh
facteurs CO2 = neutralisés ; aucun KPI CO2 n'est publié au lancement US
albédo sol par défaut = 0.2
température initiale dwelling = 20 °C
gain interne défaut dwelling = 4 W/m2
```

Les températures de consigne par défaut des scénarios sont :

```text
hiver : heating_c = 19 °C, cooling_c = 28 °C
été : heating_c = 18 °C, cooling_c = 26 °C
annuel : heating_c = 19 °C, cooling_c = 26 °C
```

Les températures initiales par saison sont :

```text
hiver : 19 °C
été : 26 °C
annuel : 20 °C
```

## 3. Capacité Thermique 1R1C

Pour chaque pièce :

```text
C_room = floor_area_m2 * equivalent_capacity_j_m2k
```

Unités :

- `floor_area_m2` : m2
- `equivalent_capacity_j_m2k` : J/m2.K
- `C_room` : J/K

Valeurs de travail par époque de construction US :

| Époque US | Capacité équivalente J/m2.K |
|---|---:|
| `us_pre_1940` | 190000 |
| `us_1940_1979` | 175000 |
| `us_1980_1999` | 165000 |
| `us_2000_2009` | 160000 |
| `us_2010_or_later` | 155000 |

Remarque : cette capacité est une inertie équivalente globale par m2. Le modèle ne distingue pas explicitement air, murs internes, mobilier et structure.

## 4. Transmission Par Parois

Pour chaque paroi opaque :

```text
UA_surface = U_surface * A_surface * b_boundary
```

avec :

- `U_surface` en W/m2.K ;
- `A_surface` en m2 ;
- `b_boundary` coefficient de réduction de température.

Coefficients `b_boundary` actuellement codés :

| Boundary | Signification | b |
|---|---|---:|
| `exterior` | extérieur | 1.0 |
| `party` | voisin / mitoyen | 0.5 |
| `unheated_space` | local non chauffé | 0.7 |
| `ground` | terre-plein / sol | 0.6 |

Pour les fenêtres :

```text
U_window_effective = U_window * shutter_u_factor_effective
UA_window = U_window_effective * A_window
```

Les fenêtres ne reçoivent pas de coefficient `b_boundary` dans le calcul actuel.
Quand un volet ou une protection possède `u_factor_closed`, le facteur U est
interpolé avec le même `opening_ratio` que les apports solaires :

```text
u_factor_effective = u_factor_closed + opening_ratio * (1 - u_factor_closed)
```

Le coefficient de transmission total avant ponts thermiques est :

```text
UA_transmission = sum(UA_surface) + sum(UA_window)
```

Le facteur de pont thermique est ensuite appliqué globalement :

```text
H_transmission = (1 + thermal_bridge_factor) * UA_transmission
H_bridge = thermal_bridge_factor * UA_transmission
```

La puissance de transmission utilisée dans la simulation est :

```text
Phi_transmission = H_transmission * (T_out - T_room)
```

La perte affichée en statique est :

```text
Loss_transmission = H_transmission * (T_room - T_out)
```

## 5. Valeurs U Par Époque De Construction US

Valeurs U de base, avant correction par niveau d’isolation :

| Époque US | Mur extérieur | Toiture | Plancher | Ponts thermiques |
|---|---:|---:|---:|---:|
| `us_pre_1940` | 1.80 | 1.50 | 1.20 | 0.18 |
| `us_1940_1979` | 1.00 | 0.70 | 0.80 | 0.15 |
| `us_1980_1999` | 0.65 | 0.40 | 0.55 | 0.12 |
| `us_2000_2009` | 0.45 | 0.28 | 0.40 | 0.10 |
| `us_2010_or_later` | 0.28 | 0.18 | 0.25 | 0.06 |

Unités U : W/m2.K.

Pour les murs et planchers, les U finaux sont :

```text
U_final = U_period[type] * u_factor_isolation
```

Dans les parcours toiture US, la toiture n'utilise plus une classe qualitative :

```text
U_roof = 1 / (R_US * 0.1761101838)
```

La R-value saisie décrit l'assemblage qui sépare le volume conditionné de
l'extérieur : plancher du grenier pour un attic ventilé, roof deck pour un
attic conditionné, un plafond cathédrale ou une toiture compacte.

Pour un système aéraulique, l'énergie finale inclut une efficacité de
distribution liée à la position des gaines. Cette hypothèse n'affecte pas la
chaleur livrée au logement et n'est pas appliquée aux systèmes non gainés.

Les `u_factor` viennent des choix métier d’isolation. Le résultat est arrondi à 3 décimales.

## 6. Géométrie Des Parois Générées

Pour une pièce :

```text
volume_m3 = floor_area_m2 * height_m
side_width_m = sqrt(floor_area_m2)
```

Pour une façade saisie :

```text
gross_wall_area = wall_length_m * height_m
net_wall_area = max(1.0, gross_wall_area - window_area_same_orientation)
```

La façade devient une surface :

```text
type = external_wall
boundary = exterior
area_m2 = net_wall_area
albedo = 0.35
solar_to_room_factor = 0.08
tilt_deg = 90
```

Si la pièce est contre un local non chauffé ou un voisin :

```text
area_party_or_unheated = sqrt(floor_area_m2) * height_m
type = party_wall
boundary = party ou unheated_space
```

Si la pièce est sous toiture :

```text
area_roof = floor_area_m2
type = roof
boundary = exterior
tilt_deg = 25
azimuth_deg = 180
```

Si la pièce est en contact avec le sol :

```text
area_floor = floor_area_m2
type = floor
boundary = ground
```

## 7. Fenêtres Et Protections Solaires

Valeurs de vitrage :

| Référence | U W/m2.K | g |
|---|---:|---:|
| `single_glazing_old` | 5.0 | 0.85 |
| `double_glazing_old` | 2.8 | 0.70 |
| `double_glazing_standard` | 1.6 | 0.55 |
| `double_glazing_low_e` | 1.2 | 0.50 |
| `triple_glazing` | 0.8 | 0.45 |

Protections solaires :

| Référence | Facteur fermé | Facteur ouvert | Facteur U fermé |
|---|---:|---:|---:|
| `none` | 1.00 | 1.00 | 1.00 |
| `roller_shutter_standard` | 0.15 | 1.00 | 0.80 |
| `roller_shutter_insulating` | 0.10 | 1.00 | 0.65 |
| `external_blind` | 0.25 | 1.00 | 0.95 |
| `fixed_south_overhang` | 0.35 | 0.55 | 1.00 |
| `interior_blind` | 0.55 | 1.00 | 1.00 |

`u_factor_closed` est maintenant utilisé dans le calcul de transmission horaire.
Les volets fermés réduisent donc à la fois les apports solaires et le U effectif
des fenêtres.

Le facteur solaire effectif des volets est interpolé :

```text
shutter_factor = closed_factor + opening_ratio * (open_factor - closed_factor)
```

Le gain solaire par fenêtre est :

```text
Phi_solar_window = A_window * Irradiance_orientation * g_value * shutter_factor * mask_factor
```

avec `mask_factor` borné entre 0 et 1 dans les fonctions solaires.

Le moteur applique directement l'irradiance du fichier météo local. La zone
IECC/ASHRAE est une métadonnée de contexte bâtiment et ne modifie ni la
température ni le rayonnement météo.

## 8. Apports Solaires Opaques

Certaines surfaces opaques extérieures peuvent recevoir un apport solaire transmis à la pièce.

Formules :

```text
absorptivity = 1 - albedo
Phi_absorbed = A_surface * Irradiance_orientation * mask_factor * absorptivity
Phi_opaque_to_room = solar_to_room_factor * Phi_absorbed
```

Valeurs générées :

```text
mur extérieur : albedo = 0.35, solar_to_room_factor = 0.08
toiture : albedo selon couleur toiture, solar_to_room_factor selon ventilation combles, défaut souvent 0.02
```

Pour le retrofit toiture réfléchissante :

```text
albedo après = 0.75
```

## 9. Ventilation Et Infiltration

Le modèle sépare trois composantes :

```text
infiltration_ach
mechanical_ach
natural_ventilation_ach
```

Conversion ACH vers débit :

```text
q = ACH * volume_m3 / 3600
```

Coefficient thermique d’air :

```text
H_air = rho_air * cp_air * q
```

Composantes :

```text
H_infiltration = rho_air * cp_air * q_infiltration
H_mechanical = rho_air * cp_air * q_mechanical * (1 - recovery_efficiency)
H_natural = rho_air * cp_air * q_natural
H_ventilation = H_infiltration + H_mechanical + H_natural
```

Puissance de ventilation :

```text
Phi_ventilation = H_ventilation * (T_out - T_room)
```

Les sorties horaires exposent aussi :

```text
infiltration_power_w
mechanical_ventilation_power_w
natural_ventilation_power_w
```

## 10. Valeurs De Ventilation

Catalogues ACH :

| Référence | ACH défaut | Récupération |
|---|---:|---:|
| `natural_leaky_old` | 0.90 | 0.00 |
| `natural_average` | 0.60 | 0.00 |
| `simple_flow` | 0.50 | 0.00 |
| `simple_flow_hygro_a` | 0.42 | 0.00 |
| `simple_flow_hygro_b` | 0.35 | 0.00 |
| `double_flow_standard` | 0.45 | 0.75 |
| `double_flow_high_efficiency` | 0.40 | 0.85 |
| `airtight_recent` | 0.35 | 0.00 |

La séparation infiltration / mécanique est faite ainsi :

```text
base_infiltration_ach = 0.15 * ach_factor

si ventilation naturelle :
    infiltration_ach = default_ach * ach_factor
    mechanical_ach = 0

sinon :
    infiltration_ach = 0.15 * ach_factor
    mechanical_ach = max(0, default_ach - 0.15)

legacy_ach_h = default_ach * ach_factor
```

Les valeurs sont arrondies à 2 décimales dans le dwelling généré.

Le `recovery_efficiency` s’applique uniquement sur la composante mécanique.

## 11. Ventilation Naturelle Pilotée

Les scénarios d’été générés ajoutent :

```json
{
  "default_ach": 0.0,
  "smart_night_cooling": true,
  "smart_ach": 4.0
}
```

À chaque heure :

```text
si smart_night_cooling est actif :
    si T_out < T_room : natural_ventilation_ach = smart_ach
    sinon : natural_ventilation_ach = 0
```

Puis les overrides horaires éventuels ont priorité :

```text
si controls.natural_ventilation.hourly contient l’heure :
    natural_ventilation_ach = entry.ach
```

## 12. Apports Internes

Les apports internes sont constants par type de pièce :

| Type de pièce | Gain interne W/m2 |
|---|---:|
| `living` | 5.0 |
| `kitchen` | 5.0 |
| `bedroom` | 3.0 |
| `office` | 3.0 |
| autres | 2.0 |

Formule :

```text
Phi_internal = internal_gain_w_m2 * floor_area_m2
```

## 13. Couplage Entre Pièces

Les liens thermiques sont non orientés dans l’intention métier, mais stockés sous forme `room_a`, `room_b`.

Pour chaque lien :

```text
H_link = opening_factor * u_value_w_m2k * area_m2
Phi_b_to_a = H_link * (T_b - T_a)
```

Ensuite :

```text
Phi_coupling_room_a += Phi_b_to_a
Phi_coupling_room_b -= Phi_b_to_a
```

Valeurs par défaut quand l’interface ne fournit que la surface commune :

```text
u_value_w_m2k = 1.8
opening_factor = 0.8
area_m2 défaut = min(10.0, max(4.0, sqrt(area_room_b) * height_room_b))
```

L’interface actuelle envoie des liens manuels dédupliqués par paire.

## 14. Bilan Horaire D’Une Pièce

À chaque heure, le moteur calcule d’abord la température libre sans chauffage ni climatisation.

Puissances :

```text
Phi_transmission = H_transmission * (T_out - T_room)
Phi_ventilation = H_ventilation * (T_out - T_room)
Phi_envelope = (H_transmission + H_ventilation) * (T_out - T_room)
Phi_free = Phi_envelope + Phi_internal + Phi_solar + Phi_coupling
```

Température libre :

```text
T_free_next = T_room + dt / C_room * Phi_free
```

Puis chauffage et climatisation sont calculés sur `T_free_next`.

## 15. Chauffage

Puissance requise pour atteindre la consigne au pas suivant :

```text
P_heat_required = max(0, (T_heat_setpoint - T_free_next) * C_room / dt)
```

Puissance disponible :

```text
P_heat_max = sum(max_power_w des systèmes desservant la pièce)
P_heat = min(P_heat_required, P_heat_max)
```

Consommation finale de chauffage par vecteur énergétique :

```text
P_heat_final_system = (P_heat * system.max_power_w / P_heat_max) / performance_system
heating_final_kwh_by_energy[energy_vector] += P_heat_final_system * timestep_h / 1000
```

`heating_electric_kwh` ne contient plus que la part électrique du chauffage.
Les autres vecteurs sont exposés dans `heating_final_kwh_by_energy`, puis agrégés
dans `heating_final_kwh` et `final_energy_kwh_by_energy`.

Pour les PAC, `performance_ref.mode = temperature_curve` interpole le COP selon
la température extérieure. Le champ `cop` reste le COP nominal de lecture rapide.

Puissance chauffage générée par défaut :

```text
max_power_w = max(1500, total_area_m2 * 95)
```

Systèmes de chauffage :

| Référence | Type | Énergie | Performance |
|---|---|---|---:|
| `electric_resistance` | `electric_resistance` | électricité | COP 1.00 |
| `air_source_heat_pump_standard` | `heat_pump` | électricité | COP 2.0 à -7 °C, 3.2 à 7 °C, 4.0 à 15 °C |
| `natural_gas_furnace_standard` | `furnace` | gaz naturel | rendement 0.80 |
| `propane_furnace_standard` | `furnace` | propane | rendement 0.80 |

Pour le profil `heat_pump_seller`, le dwelling initial utilise le chauffage existant :

| Saisie actuelle | Système before |
|---|---|
| résistance électrique | `electric_resistance` |
| furnace gaz naturel | `natural_gas_furnace_standard` |
| furnace propane | `propane_furnace_standard` |
| pompe à chaleur air-source | `air_source_heat_pump_standard` |

Le retrofit PAC remplace le système par :

```text
air_source_heat_pump_standard, energy_vector = electricity, COP courbe temperature_curve
```

## 16. Climatisation

La climatisation est ajoutée si `has_cooling = true`.

Pièces desservies :

```text
living, bedroom, office
```

Si aucune pièce de ces types n’existe, toutes les pièces sont desservies.

Puissance installée :

```text
max_power_w = max(1200, total_area_m2 * 70)
```

Système généré :

```text
system_ref = air_conditioner_standard
type = air_conditioner
EER = 3.0
```

Catalogues de froid :

| Référence | Type | EER |
|---|---|---:|
| `air_conditioner_entry_level` | `air_conditioner` | 2.6 |
| `air_conditioner_standard` | `air_conditioner` | 3.0 |
| `air_conditioner_high_efficiency` | `air_conditioner` | 3.6 |
| `reversible_heat_pump_standard` | `reversible_heat_pump` | 3.2 |

Calcul :

```text
P_cool_required = max(0, (T_free_next - T_cool_setpoint) * C_room / dt)
P_cool = min(P_cool_required, P_cool_max)
P_cool_electric = sum((P_cool * system.max_power_w / P_cool_max) / EER_system)
```

La température finale est ensuite :

```text
Phi_final = Phi_free + P_heat - P_cool
T_next = T_room + dt / C_room * Phi_final
```

## 17. Énergie Et Coût US

Conversion puissance vers énergie :

```text
E_kWh = P_W * timestep_h / 1000
```

Totaux scénario :

```text
heating_thermal_kwh
heating_final_kwh_by_energy
heating_final_kwh
heating_electric_kwh = heating_final_kwh_by_energy["electricity"]
cooling_thermal_kwh
cooling_electric_kwh
electricity_kwh = heating_electric_kwh + cooling_electric_kwh
final_energy_kwh_by_energy = heating_final_kwh_by_energy + cooling_electricity
final_energy_kwh
electricity_cost_usd = electricity_kwh * electricity_usd_kwh
natural_gas_cost_usd = natural_gas_kwh / 29.308324 * natural_gas_usd_therm
propane_cost_usd = propane_kwh / 26.803048 * propane_usd_gallon
energy_cost_usd = sum(cost_by_energy)
```

Prix de travail utilisés si le scénario ne fournit pas le vecteur :

| Énergie | Prix | Unité commerciale |
|---|---:|---|
| électricité | 0.18 | $/kWh |
| gaz naturel | 1.50 | $/therm |
| propane | 2.50 | $/gallon |

Les conversions énergétiques utilisent 100 000 Btu par therm et 91 452 Btu
par gallon de propane (U.S. EIA). Aucun KPI CO2 n'est généré pour le lancement
US tant qu'une source électrique régionale, datée et versionnée n'est pas intégrée.

## 18. Inconfort

Par pièce :

```text
cold_degree_hours = sum(max(0, heating_setpoint - T_room) * timestep_h)
hot_degree_hours = sum(max(0, T_room - cooling_setpoint) * timestep_h)
```

Les seuils génériques utilisés ailleurs dans le résumé sont :

```text
DISCOMFORT_COLD_THRESHOLD_C = 19.0
DISCOMFORT_HOT_THRESHOLD_C = 26.0
```

## 19. Météo Générée

Les scénarios non annuels utilisent une météo synthétique.

Température extérieure :

```text
T_out = base_temp + amplitude * sin(2*pi*(hour_in_day - 8)/24)
```

Les trois profils synthétiques fixes sont indépendants de la zone climatique :

| Profil | Base | Amplitude |
|---|---:|---:|
| `generic_heatwave_reference` | 29.0 | 7.0 |
| `generic_summer_typical` | 24.5 | 5.5 |
| `generic_winter_design` | 3.0 | 4.0 |

Irradiance synthétique hiver :

```text
peak = max(0, sin(pi*(hour_in_day - 8)/8))
north = 0
east = 120*peak si h < 13, sinon 30*peak
south = 280*peak
west = 120*peak si h > 12, sinon 30*peak
roof = 240*peak
```

Irradiance synthétique été :

```text
peak = max(0, sin(pi*(hour_in_day - 6)/13))
north = 80*peak
east = 520*peak si h < 13, sinon 160*peak
south = 620*peak
west = 520*peak si h > 12, sinon 160*peak
roof = 760*peak
```

## 20. Météo Open-Meteo Annuelle

Pour les scénarios annuels, les données Open-Meteo sont converties en météo thermique.

À partir de :

```text
temperature_2m
shortwave_radiation
direct_radiation
diffuse_radiation
```

Conversion vers orientations :

```text
north = diffuse * 0.35
east = diffuse * 0.5 + direct * weight(hour, 5, 12)
south = diffuse * 0.6 + direct * weight(hour, 8, 16)
west = diffuse * 0.5 + direct * weight(hour, 12, 19)
roof = shortwave
```

avec :

```text
weight(hour, start, end) = 0 si hour < start ou hour > end
sin(pi*(hour - start)/(end - start)) sinon
```

Les valeurs négatives ou absentes sont ramenées à 0.

## 21. Scénarios Et Retrofits

Les scénarios sont construits en paire before / after.

Les changements actuels :

### Isolation toiture

```text
surface.type == roof
U_after = 0.18 W/m2.K
```

### Toiture réfléchissante

```text
surface.type == roof
albedo_after = 0.75
```

### Remplacement fenêtres

```text
window_ref_after = double_glazing_low_e
U_after = 1.2 W/m2.K
g_after = 0.50
```

### Protection solaire

```text
shutter_after = roller_shutter_standard
solar_factor_closed_after = 0.08
solar_factor_open_after = 1.0
```

### Pompe à chaleur

```text
system_ref_after = air_source_heat_pump_standard
type_after = heat_pump
energy_vector_after = electricity
performance_after = temperature_curve
```

## 22. Contrôles De Volets En Été

Les scénarios été et annuel ajoutent un contrôle de volets.

Valeurs :

```text
default_opening_ratio = 1.0
```

Si usage `day_closed` :

```text
opening_ratio = 0.1 entre 8h et 19h
```

Si usage `partial` :

```text
opening_ratio = 0.25 entre 8h et 19h
```

Si usage `rare` :

```text
opening_ratio = 0.75 entre 8h et 19h
```

Si usage `none` :

```text
opening_ratio = 1.0 partout
```

## 23. Orientations

Les orientations utilisées par les surfaces et fenêtres sont ramenées en quatre directions cardinales plus toiture.

Règle :

```text
azimuth < 45 ou >= 315 -> north
45 <= azimuth < 135 -> east
135 <= azimuth < 225 -> south
225 <= azimuth < 315 -> west
surface roof ou tilt < 60 -> roof
```

## 24. Comparaison Before / After

Le moteur applique les overrides du scénario after sur une copie du dwelling.

Puis il simule :

```text
before_result = simulate_1r1c(dwelling_before, scenario_before)
after_result = simulate_1r1c(dwelling_after, scenario_after)
delta = before - after
```

Pour les métriques d’énergie, un delta positif signifie généralement une économie.

Pour les températures et inconforts, le rapport interprète ensuite selon le contexte.

## 25. Limites Actuelles À Garder En Tête

Le modèle actuel est volontairement simplifié :

- pas de modèle radiatif intérieur détaillé ;
- pas de température de surface intérieure ;
- pas de paroi multicouche dynamique ;
- pas de stockage solaire dans les murs ;
- pas de vraie géométrie solaire ;
- pas d’ombrage géométrique ;
- pas de débit VMC pièce par pièce réel ;
- pas de réseau aéraulique ;
- pas de puissance système saisie finement par pièce ;
- les chaudières gaz/fioul/bois utilisent le champ `cop` comme rendement simplifié ;
- les ponts thermiques sont un facteur global, pas des longueurs `psi * L` ;
- les pièces sont couplées par une conductance simple, sans modèle de porte ni débit d’air réel ;
- la météo synthétique est un ordre de grandeur, pas une météo réglementaire.
