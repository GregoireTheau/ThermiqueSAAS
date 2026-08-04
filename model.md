# Modèle thermique ThermalTwin

État du code au 4 août 2026 — moteur `1r1c-mvp-0.2`.

Ce document est la référence technique du modèle réellement exécuté. ThermalTwin est un outil
d'aide à la vente : ses résultats sont des estimations indicatives, pas un HERS rating, un Manual J,
un audit énergétique, une étude d'ingénierie, une vérification de code, un DPE ou une garantie
d'économies.

## 1. État actuel en une phrase

Le moteur est un modèle thermique horaire multi-pièces 1R1C, cohérent pour comparer un même
logement avant/après avec la même météo et les mêmes usages, mais il n'est pas encore calibré ni
validé sur un échantillon de logements US mesurés. Il est donc plus fiable pour classer des variantes
et expliquer des mécanismes que pour annoncer une consommation absolue précise.

Niveau de maturité par composant :

| Composant | État | Niveau de confiance actuel |
|---|---|---|
| Conservation de l'énergie, unités, conversions | Testé dans le code | Élevé |
| Météo historique locale et traçabilité | Implémenté, mis en cache et haché | Bon |
| TMY NSRDB | Implémenté ; dépend de l'API et des identifiants NLR | Bon pour le contexte météo |
| Transmission par R-value saisie | Formule physique simple | Bon si la R-value effective est correcte |
| Géométrie, murs, fenêtres, infiltration | Valeurs déclarées ou estimées | Moyen à faible |
| Gains solaires orientés | Approximation MVP, sans géométrie solaire | Faible à moyen |
| HVAC et gaines | Courbes/efficacités génériques | Moyen à faible |
| Confort horaire | Température d'air sensible seulement | Indicatif |
| Validation sur factures/capteurs | Pas encore réalisée | Non démontré |

La zone IECC/ASHRAE est une métadonnée bâtiment. Elle ne remplace jamais la météo locale et ne
modifie pas directement les températures ou le rayonnement de la simulation.

## 2. Chaîne de calcul

Pour chaque pièce, le moteur conserve une température d'air `T_room` et une capacité thermique
équivalente `C_room`. À chaque pas horaire :

```text
Phi_free = Phi_transmission + Phi_ventilation
           + Phi_internal + Phi_solar + Phi_coupling

T_free_next = T_room + dt / C_room * Phi_free
```

Le chauffage ou la climatisation cherche ensuite à ramener la pièce à la consigne, dans la limite de
la puissance installée :

```text
P_heat_required = max(0, (T_heat - T_free_next) * C_room / dt)
P_cool_required = max(0, (T_free_next - T_cool) * C_room / dt)

T_next = T_room + dt / C_room * (Phi_free + P_heat - P_cool)
```

Convention : une puissance positive entre dans la pièce ; une puissance négative en sort. Le pas
utilisé par les parcours SaaS est `dt = 1 h`. L'intégration est explicite : une faible inertie associée
à un grand coefficient de pertes peut donc amplifier les erreurs numériques ou produire des pics.

Le before et l'after sont simulés séparément à partir d'une même description du logement et d'une
même série météo. Le scénario after n'applique que les overrides de la mesure étudiée. Cette symétrie
annule une partie des biais communs, sans supprimer les interactions mal modélisées.

## 3. Localisation et météo annuelle

### Localisation

Le ZIP code US est obligatoire et l'adresse est optionnelle. La résolution produit :

- latitude et longitude ;
- ville, État, county et county FIPS quand disponibles ;
- fuseau IANA local ;
- précision et fournisseur du géocodage ;
- zone IECC/ASHRAE par county, uniquement comme contexte.

Le cache météo est mutualisé sur une grille arrondie à `0,1°`. Deux ZIP proches qui tombent dans la
même cellule et le même fuseau réutilisent donc le même fichier météo ; le produit ne télécharge pas
une année par ville. C'est un compromis volontaire entre localité et nombre de fichiers.

### Année historique réelle

Une année historique complète explicitement choisie est téléchargée via l'archive Open-Meteo avec
le modèle `era5_seamless`, aux coordonnées de la cellule météo et dans le fuseau IANA du logement.
Le 29 février est retiré : une simulation annuelle contient 8 760 heures. Cette année est un scénario
contextuel daté, pas une promesse de climat futur ni une année « normale ».

Variables utilisées :

```text
temperature_2m
shortwave_radiation
direct_radiation
diffuse_radiation
```

### Année météorologique typique

Le scénario annuel de référence peut utiliser un TMY NSRDB/NLR, actuellement
`GOES Typical Meteorological Year PSM v4`, référence par défaut `tmy-2024`. Un TMY assemble des
mois représentatifs ; il ne correspond pas à une année civile vécue. Il convient mieux à une
estimation annuelle centrale, mais ne décrit ni un hiver extrême ni une vague de chaleur précise.

### Rayonnement reçu par les parois

Le fichier fournit un rayonnement horizontal. ThermalTwin le répartit actuellement avec des poids
horaires simplifiés :

```text
north = 0.35 * diffuse
east  = 0.50 * diffuse + direct * weight(hour, 5, 12)
south = 0.60 * diffuse + direct * weight(hour, 8, 16)
west  = 0.50 * diffuse + direct * weight(hour, 12, 19)
roof  = shortwave
```

Ce calcul ne tient pas compte de la latitude solaire, du jour de l'année, de l'azimut solaire exact,
de la pente réelle, de l'horizon ou des masques géométriques. C'est l'une des principales sources
d'erreur, notamment pour le confort d'été et les toitures réfléchissantes.

### Reproductibilité

Chaque météo sauvegardée contient le fournisseur, dataset, modèle, année ou référence TMY, cellule
et coordonnées source, station/grid, fuseau, date de création, version moteur et SHA-256 des 8 760
points. Le rapport reprend ces informations. Une reproduction exacte exige de conserver le fichier
météo identifié par ce hash, les réponses du projet, les catalogues de paramètres et la même version
du moteur.

## 4. Enveloppe, géométrie et inertie

### Transmission

Pour une surface opaque :

```text
UA_surface = U * A * b_boundary
```

| Limite | `b_boundary` |
|---|---:|
| Extérieur | 1,00 |
| Mitoyen/voisin | 0,50 |
| Espace non chauffé | 0,70 |
| Sol | 0,60 |

Les facteurs mitoyen, espace non chauffé et sol sont des raccourcis constants. Ils ne calculent ni la
température du voisin, ni celle du vide sanitaire, ni le transfert transitoire vers le sol.

Les ponts thermiques sont ajoutés comme fraction globale de tout le `UA` :

```text
H_transmission = (1 + thermal_bridge_factor) * sum(UA)
```

Ce n'est pas un calcul par longueurs et coefficients linéiques `psi * L`. Si les U saisis sont déjà
des valeurs effectives issues d'une mesure ou d'un modèle complet, cette majoration peut compter
deux fois certains ponts thermiques.

### R-value toiture

La R-value US saisie doit représenter l'assemblage effectif à la frontière du volume conditionné :
plancher de l'attic pour un attic ventilé, roof deck pour un attic conditionné ou une toiture compacte.

```text
1 R_US = 0.1761101838 m2.K/W
U_roof = 1 / (R_US * 0.1761101838)
```

La valeur proposée par défaut est R-49, mais ce n'est ni une prescription de code ni la bonne cible
universelle. Le commercial doit saisir la R-value réellement vendue. Le modèle traite cette R-value
comme effective et homogène : compression, gaps, humidité, framing fraction et défauts de pose ne
sont pas calculés séparément.

### Valeurs de repli par époque US

Ces valeurs servent aux murs/planchers et à la toiture uniquement lorsque l'utilisateur ne fournit
pas une R-value. Elles sont des hypothèses MVP non calibrées, pas des caractéristiques statistiques
US validées :

| Époque | Mur U | Toiture U | Plancher U | Ponts | Capacité J/m2.K |
|---|---:|---:|---:|---:|---:|
| Avant 1940 | 1,80 | 1,50 | 1,20 | 0,18 | 190 000 |
| 1940–1979 | 1,00 | 0,70 | 0,80 | 0,15 | 175 000 |
| 1980–1999 | 0,65 | 0,40 | 0,55 | 0,12 | 165 000 |
| 2000–2009 | 0,45 | 0,28 | 0,40 | 0,10 | 160 000 |
| 2010+ | 0,28 | 0,18 | 0,25 | 0,06 | 155 000 |

Les coefficients qualitatifs d'isolation multiplient ensuite les U (`poor`, `standard`, `renovated`,
etc.). L'âge seul prédit mal un logement rénové et les pratiques varient fortement par État, climat,
ossature et code applicable. Ces valeurs sont une priorité de remplacement par des distributions
ResStock conditionnées par vintage, zone, type de mur et type de logement.

### Géométrie générée

```text
volume = floor_area * ceiling_height
side_width = sqrt(floor_area)
gross_wall_area = entered_wall_length * height
net_wall_area = max(1 m2, gross_wall_area - windows_same_orientation)
roof_area = floor_area
```

Une toiture générée utilise par défaut pente `25°`, azimut sud et surface égale à la surface de
plancher. Une pente réelle devrait augmenter la surface (`floor_area / cos(tilt)`), et un logement à
plusieurs niveaux ne doit pas exposer tous ses planchers à la toiture. Les simplifications de géométrie
peuvent dominer l'erreur même avec un U exact.

### Inertie 1R1C

```text
C_room = floor_area * equivalent_capacity
```

Une seule capacité représente l'air, la structure, les cloisons et le mobilier. Le modèle n'a pas de
température de surface ni de paroi multicouche dynamique. Les maxima/minima horaires et le déphasage
estival sont donc beaucoup plus sensibles à cette valeur que l'énergie annuelle de chauffage.

## 5. Fenêtres, solaire et gains internes

| Vitrage | U W/m2.K | facteur solaire g |
|---|---:|---:|
| Simple ancien | 5,0 | 0,85 |
| Double ancien | 2,8 | 0,70 |
| Double standard | 1,6 | 0,55 |
| Double low-e | 1,2 | 0,50 |
| Triple | 0,8 | 0,45 |

```text
Phi_window_solar = area * irradiance_orientation * g * shutter * mask
Phi_opaque_solar = area * irradiance * (1 - albedo) * solar_to_room_factor * mask
```

Les valeurs vitrage sont des archétypes, pas les données NFRC du produit posé. Le masque est un
coefficient constant et les protections suivent un horaire déclaratif. Pour une toiture, les albedos
de travail sont 0,18 sombre, 0,25 moyen/inconnu, 0,40 clair et 0,75 après cool-roof. Le passage de
l'énergie solaire absorbée à la pièce utilise `solar_to_room_factor` = 0,0225 attic ventilé, 0,05
plafond incliné et 0,07 toiture plate. Ces trois facteurs sont empiriques et doivent être remplacés par
un nœud d'attic/roof deck ou calibrés.

Gains internes constants :

| Pièce | W/m2 |
|---|---:|
| Séjour, cuisine | 5 |
| Chambre, bureau | 3 |
| Escalier | 1 |
| Autre | 2 |

Ils n'ont ni horaire d'occupation, ni appareils, ni humidité. Ils peuvent sous-estimer les pointes de
cuisine et surestimer une maison vide.

## 6. Air neuf, infiltration et pièces

```text
q = ACH * volume / 3600
H_air = rho_air * cp_air * q
```

avec `rho_air = 1,2 kg/m3` et `cp_air = 1005 J/kg.K`. Les composantes infiltration, ventilation
mécanique et ouverture naturelle sont séparées. La récupération ne s'applique qu'au débit mécanique.

| Profil | ACH total de travail | Récupération |
|---|---:|---:|
| Ancien fuyard naturel | 0,90 | 0 |
| Naturel moyen | 0,60 | 0 |
| Mécanique simple | 0,50 | 0 |
| Hygro A / B | 0,42 / 0,35 | 0 |
| Double flux standard / performante | 0,45 / 0,40 | 0,75 / 0,85 |
| Récent étanche | 0,35 | 0 |

Ces catégories conservent des concepts européens et ne décrivent pas correctement tous les logements
US. Surtout, un ACH naturel supposé n'est pas un ACH50 de blower-door : les deux ne sont pas
interchangeables sans un modèle dépendant du climat, de la hauteur et de l'exposition. L'infiltration
constante est probablement l'une des premières causes d'erreur annuelle.

Le free-cooling estival synthétique ouvre à `4 ACH` dès que l'extérieur est plus froid que la pièce,
sans contrainte d'heure, d'humidité, de pluie, de bruit ou d'occupation. Il peut surestimer fortement
le confort réel.

Les pièces sont reliées par :

```text
H_link = opening_factor * U_link * area
```

avec repli `U_link = 1,8 W/m2.K` et `opening_factor = 0,8`. Il s'agit d'une conductance, pas d'un
débit d'air à travers une porte.

## 7. Chauffage, climatisation et gaines

### Chauffage

| Système | Performance de travail |
|---|---|
| Résistance électrique | 1,00 |
| Furnace gaz | rendement constant 0,80 |
| Furnace propane | rendement constant 0,80 |
| PAC air-source | COP 2,0 à -7 °C ; 3,2 à 7 °C ; 4,0 à 15 °C |

La PAC est interpolée linéairement entre les points et constante au-delà. Le modèle n'inclut pas la
baisse de capacité, les cycles, le dégivrage, la chaleur auxiliaire, le thermostat ni un équipement
réel. Pour un furnace, le champ interne historique s'appelle `cop`, mais représente ici un rendement
fuel-to-heat simplifié ; `0,80` est un proxy de furnace standard, pas un AFUE mesuré du logement.

Puissance de repli :

```text
P_heat_max = max(1 500 W, floor_area * 95 W/m2)
```

### Climatisation

```text
P_cool_max = max(1 200 W, floor_area * 70 W/m2)
performance standard = 3,0 W froid / W électrique
```

Le champ historique s'appelle `eer`, mais la valeur dimensionnelle W/W est un **COP froid**, pas
un EER US en Btu/Wh. Il ne faut jamais afficher « EER 3.0 » à un client américain. Le modèle ne
calcule que la charge sensible : pas de latent, humidité, SHR, débit d'air, fan power, cycling ou
SEER2. La climatisation est donc un composant particulièrement peu validé.

### Efficacité de distribution des gaines

L'énergie finale est divisée par l'efficacité de distribution ; la chaleur utile livrée à la pièce ne
change pas :

| Emplacement | Efficacité de travail après audit 2026-08-03 |
|---|---:|
| Sans gaines / volume conditionné / attic conditionné | 1,00 |
| Sous-sol non conditionné | 0,90 |
| Mixte ou inconnu | 0,85 |
| Attic ventilé / crawlspace / garage | 0,80 |

La révision remplace les anciennes valeurs 0,92 / 0,90 / 0,85. Le DOE indique qu'un réseau typique
peut perdre environ 20–30 % de l'air transporté ; `0,80` est donc un meilleur centre de travail pour
les gaines en espace non conditionné. Ce n'est pas une prédiction par logement : duct-blaster,
pourcentage de gaines hors volume, isolation et températures d'attic doivent remplacer ce proxy.

## 8. Énergie, prix et confort

```text
energy_kwh = power_w * timestep_h / 1000
gas_cost = gas_kwh / 29.308324 * USD_per_therm
propane_cost = propane_kwh / 26.803048 * USD_per_gallon
```

Conversions : `1 therm = 100 000 Btu` et `1 gallon propane = 91 452 Btu` (U.S. EIA). Prix de repli :

| Énergie | Valeur | Statut |
|---|---:|---|
| Électricité | 0,18 $/kWh | Exemple, à remplacer par le tarif client |
| Gaz naturel | 1,50 $/therm | Exemple, à remplacer par la facture locale |
| Propane | 2,50 $/gal | Exemple, à remplacer par le prix livré |

Ces prix ne sont pas des paramètres physiques et ne doivent pas être « calibrés » globalement. Les
tarifs fixes, taxes, tranches, frais de livraison et variation saisonnière ne sont pas modélisés. Le
gain en dollars est donc proportionnel au prix saisi et peut être faux même si le gain en kWh est bon.

Le KPI CO2 commercial est désactivé : les facteurs valent zéro. Il ne doit revenir qu'avec une source
électrique régionale, une année et une version explicites.

Inconfort :

```text
cold_degree_hours = sum(max(0, 19 °C - T_room) * dt)
hot_degree_hours  = sum(max(0, T_room - 26 °C) * dt)
```

Dans le parcours SaaS, les valeurs proposées par défaut sont 68 °F (20 °C) pour le chauffage et
78 °F (25,6 °C) pour la climatisation de jour comme de nuit ; l'utilisateur peut les modifier.
La température initiale annuelle de repli est 20 °C. Les générateurs de scénarios hors SaaS conservent
des replis historiques par saison (19 °C chauffage annuel/hiver, 26 °C refroidissement annuel/été).

Les consignes saisies par le client sont utilisées pour piloter les systèmes ; les seuils génériques de
résumé restent 19 °C / 26 °C. La température d'air seule ne mesure ni température opérative, ni
humidité, ni courant d'air, ni confort adaptatif.

## 9. Contrôles automatiques existants

Des warnings non bloquants sont produits pour :

- fenêtres > 60 % de la surface de plancher d'une pièce ;
- ventilation totale > 3 ACH ;
- chauffage insuffisant au point météo le plus froid ;
- température simulée > 45 °C.

Le banc `scripts/run_model_validation.py` ajoute, sur une matrice US annuelle,
la fermeture du bilan énergétique, la non-négativité des énergies, la monotonie
des principaux paramètres et la conservation de la puissance totale des systèmes
centraux. Il marque aussi les cas à demande de chauffage négligeable ou limités
par la puissance installée. Le protocole et la baseline sont dans
`docs/ModelValidationBenchmark.md`.

Ils détectent quelques sorties manifestement suspectes, mais ne constituent pas une validation du
modèle. Il manque notamment des contrôles sur la surface totale exposée, les R-values incompatibles
avec l'assemblage et les discontinuités horaires.

## 10. Ce qui peut induire les plus grosses erreurs

Par ordre de risque actuel :

1. **Mauvaise frontière thermique.** Confondre insulation at attic floor et roof deck change la
   surface et le volume conditionné ; aucun réglage numérique ne corrige cette erreur de structure.
2. **Infiltration supposée.** Une description « drafty/average/tight » ne remplace pas un blower-door.
3. **Géométrie simplifiée.** Surface de toiture, murs réellement exposés, nombre d'étages et fenêtres
   ont un effet quasi linéaire sur les charges.
4. **Solaire approximatif.** L'orientation horaire MVP peut déplacer ou amplifier les apports.
5. **HVAC générique.** COP, capacité, AFUE, auxiliaire et gaines peuvent fausser énergie et confort.
6. **Archétypes par âge.** Les U et inerties actuels ne sont pas encore des distributions US validées.
7. **Usages constants.** Occupation, consignes, ouvrants et gains internes réels sont inconnus.
8. **1R1C.** Les pics, le déphasage et le confort radiant sont moins fiables que les tendances annuelles.
9. **Météo de grille.** Elle décrit une cellule, pas le microclimat, l'ombre, l'altitude exacte ou le
   futur. Une seule année historique peut être atypique.
10. **Prix.** Le coût peut sembler précis malgré un tarif incomplet ou obsolète.

Un résultat before/after peut aussi être biaisé favorablement si la mesure change en réalité
l'étanchéité, l'humidité ou les gaines mais que le scénario ne modifie que le U de toiture.

## 11. Comment mesurer les performances du modèle

### Étape A — tests physiques et benchmark

Créer un jeu de cas déterministes : boîte adiabatique, décroissance analytique RC, `UA * deltaT`,
absence de gains, conservation des échanges entre pièces, COP/rendement et limites de puissance.
Ajouter ensuite des cas ASHRAE Standard 140/BESTEST comparables. L'objectif est de trouver les bugs
de calcul avant toute calibration sur des factures.

Première étape réalisée le 4 août 2026 : 10 archétypes US et 23 variations
one-at-a-time ont été exécutés sur météo historique 2023. Les 33 runs et 140
contrôles passent avec `1r1c-mvp-0.2`. Cette baseline mesure la cohérence et la
sensibilité, pas encore l'erreur face à une référence indépendante.

Comparer un échantillon de maisons types à EnergyPlus/OpenStudio ou ResStock, composant par
composant : chauffage utile, refroidissement sensible, heures hors consigne et delta before/after.
Une concordance sur la consommation totale seule peut masquer des erreurs qui se compensent.

### Étape B — protocole pilote mesuré

Pour chaque logement pilote, collecter avec consentement :

- 12 à 24 mois de factures électricité/gaz/propane, idéalement données horaires ou quotidiennes ;
- météo correspondant exactement à la période de facture ;
- consignes et horaires, occupation approximative et autres gros usages ;
- surface/plans, orientation, pente et photos de l'attic ;
- R-value, épaisseur, matériau, continuité et emplacement réel de l'isolant ;
- blower-door ACH50 et, pour systèmes gainés, duct leakage ;
- marque/modèle, AFUE, SEER2/HSPF2, tables capacité/COP et chauffage auxiliaire ;
- mesures de température intérieure avant/après, dans plusieurs pièces si possible.

Séparer l'énergie HVAC des autres usages quand c'est possible. Sinon, ajuster une base non-HVAC
explicite et conserver son incertitude.

### Étape C — métriques et séparation des données

Mesurer au minimum :

```text
MBE ou NMBE      = biais moyen signé
CV(RMSE)         = dispersion normalisée
MAE              = erreur absolue lisible
erreur du delta  = (saving_predicted - saving_measured)
couverture       = part des mesures dans l'intervalle annoncé
```

À titre de repère de calibration, les lignes directrices FEMP/ASHRAE citées par le DOE donnent pour
des modèles calibrés : mensuel MBE ±5 % et CV(RMSE) 15 % ; horaire MBE ±10 % et CV(RMSE) 30 %.
Ce sont des seuils de calibration de bâtiment, pas la preuve qu'un modèle prédit correctement une
rénovation future.

Séparer obligatoirement :

- calibration/train : logements utilisés pour ajuster les paramètres ;
- validation : logements jamais vus pendant l'ajustement ;
- test avant/après : chantiers avec mesure post-travaux et normalisation météo.

Publier les résultats par zone climatique, époque, type d'attic, fuel et qualité des données, pas
seulement une moyenne nationale.

### Étape D — incertitude

Faire varier les entrées incertaines dans des plages documentées (R effectif, infiltration, gains,
consigne, surface, gaines, COP) par analyse de sensibilité ou Monte Carlo. Le rapport commercial doit
à terme afficher une plage P10–P90 ou basse/centrale/haute, jamais uniquement un nombre décimal.

## 12. Roadmap d'amélioration du modèle

Ordre recommandé :

1. Instrumenter 10–20 maisons pilotes et obtenir au moins quelques chantiers before/after.
2. Ajouter la saisie ou mesure ACH50, duct leakage et caractéristiques exactes de l'équipement.
3. Remplacer les U/inerties par des distributions ResStock conditionnées par région, vintage,
   ossature et type de logement ; conserver la provenance/version de chaque tirage.
4. Remplacer la projection solaire par une transposition physique utilisant position solaire,
   azimut, pente et DNI/DHI ; ajouter des masques simples.
5. Ajouter un nœud attic/roof deck puis humidité/latent si le marché vend le confort d'été.
6. Utiliser des courbes constructeur PAC/AC avec capacité, dégivrage et auxiliaire ; séparer COP,
   AFUE, EER2/SEER2 dans le schéma au lieu du champ legacy `cop/eer`.
7. Calibrer seulement les paramètres observables et globalement identifiables ; ne pas ajuster dix
   coefficients pour reproduire une facture unique.
8. Versionner moteur et catalogue séparément, geler les artefacts météo et ajouter une suite
   ASHRAE 140 à la CI.
9. N'autoriser des promesses plus précises qu'après validation hors échantillon et mise en place
   d'intervalles d'incertitude.

## 13. Décisions prises lors de cet audit

- Les valeurs d'enveloppe, inertie, ventilation, solaire et HVAC restent explicitement marquées
  `mvp_working_assumptions_to_calibrate` : aucune source ne justifie de les rendre universelles.
- Les efficacités de gaines hors volume conditionné ont été rendues moins optimistes, conformément
  à l'ordre de grandeur DOE de 20–30 % de pertes courantes.
- Le champ de climatisation `eer` est désormais documenté comme un COP W/W legacy pour éviter une
  interprétation erronée en EER US.
- Les prix restent modifiables et ne sont pas remplacés par une moyenne nationale qui serait vite
  obsolète et peu pertinente localement.
- Les facteurs CO2 restent neutralisés.
- Depuis `1r1c-mvp-0.2`, la puissance maximale d'un système central est une
  capacité totale répartie entre les pièces desservies au prorata de leur surface ;
  elle n'est plus dupliquée dans chaque pièce.

## 14. Sources de référence pour la suite

- Météo historique : Open-Meteo Historical Weather API, modèle demandé `era5_seamless`.
- TMY : NLR NSRDB GOES TMY PSM v4.
- Archétypes et validation US : NLR/DOE ResStock Technical Reference et End-Use Load Profiles.
- Conversions fuels : U.S. EIA, *Energy units and calculators explained*.
- Pertes de gaines : U.S. DOE Energy Saver, ordre de grandeur 20–30 % pour un réseau typique.
- Mesure et vérification : U.S. DOE FEMP, *M&V Guidelines*, version 5.0.
- Benchmark de simulation : ASHRAE Standard 140 / BESTEST et cas EnergyPlus associés.

Sources de code faisant foi :

- `thermal_model/simulation.py`
- `thermal_model/static_losses.py`
- `thermal_model/weather.py`
- `thermal_model/physical_validation.py`
- `scripts/create_customer_experience.py`
- `thermal_saas/business_flow.py`
- `data/reference/*.json`
