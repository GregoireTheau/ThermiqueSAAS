# Validation du modèle thermique

Ce document est le livrable de la phase 6. Il consolide les cas de référence, les premiers résultats de calibrage et les limites connues du modèle 1R1C horaire.

Les résultats ci-dessous sont des consommations de chauffage en énergie finale, en kWh/m²/an, obtenues en remplaçant la météo 24 h des cas hiver par les fichiers Open-Meteo thermiques 2023 locaux.

## Résultats annuels chauffage

| Cas | Bordeaux 2023 | Paris 2023 | Strasbourg 2023 | Lecture physique |
|---|---:|---:|---:|---|
| Appartement ancien mal isolé | 249.3 | 333.8 | 377.0 | Cas très sévère après ajout toiture et plancher bas exposés. Il dépasse la plage ancien 200-350 à Strasbourg. |
| Appartement ancien moyen | 61.9 | 88.4 | 103.4 | Trop bas pour la cible 150-220 à Strasbourg avec les paramètres imposés. L'exposition est trop faible sans toiture/plancher. |
| Maison récente RT2012 | 3.8 | 6.3 | 8.2 | Très sous-estimé face à une cible usuelle 40-80 kWh/m²/an. |
| Maison années 70 | 101.2 | 141.8 | 164.7 | Cohérent en tendance, mais encore bas pour un logement ancien énergivore. |
| Hiver avec PAC | 4.0 | 6.6 | 8.5 | Besoin final très bas car la PAC du cas a un COP constant de 3.2. |
| Isolation toiture | 13.9 | 22.6 | 28.9 | Cas de comparaison rénovation, pas un niveau annuel réglementaire. |
| Remplacement fenêtres | 18.6 | 29.7 | 37.1 | Cas de comparaison rénovation, dépend fortement des gains solaires sud. |
| Ventilation forte | 29.6 | 44.0 | 52.9 | La hausse de ventilation augmente bien les besoins. |
| Ventilation faible | 2.5 | 5.9 | 8.8 | Cas volontairement très favorable thermiquement, sans jugement qualité d'air. |

## Comparaison aux fourchettes réelles

| Typologie | Fourchette repère | Résultat modèle | Diagnostic |
|---|---:|---:|---|
| Logement ancien énergivore | 200-350 kWh/m²/an | Appartement mal isolé : 249-377 selon météo | Cohérent à Bordeaux/Paris, trop sévère à Strasbourg. |
| Appartement ancien moyen | 150-220 kWh/m²/an cible interne | 62-103 selon météo | Sous-estimé avec les hypothèses actuelles. Il manque de surface déperditive exposée. |
| RT2012 | 40-80 kWh/m²/an | 4-8 selon météo | Fortement sous-estimé. Le cas est trop favorable et la PAC réduit fortement l'énergie finale. |
| Puissance chauffage typique | 30-80 W/m² | Mal isolé : plafonné à 133 W/m² | Le cas mal isolé est très sévère et peut être limité par la puissance installée. |

Conclusion de calibrage : le modèle respecte les signes physiques, mais les cas annuels ne sont pas encore calibrés pour représenter des consommations françaises robustes par typologie. Les cas de référence restent utiles pour la non-régression, pas encore pour une promesse commerciale de consommation annuelle.

## Scénarios canicule

Deux lectures sont conservées pour les cas été :

- `canicule_sans_protection` : volets ouverts, comportement défavorable, logement non protégé.
- `canicule_occupant_raisonnable` : volets fermés de 8h à 19h avec `opening_ratio=0.1`, ventilation nocturne intelligente à 4 ACH quand l'air extérieur est plus frais.

Températures intérieures simulées :

| Cas | Sans protection 20h | Sans protection max | Occupant raisonnable 20h | Occupant raisonnable max |
|---|---:|---:|---:|---:|
| Logement traversant | 35.7 °C | 36.5 °C | 33.5 °C | 33.7 °C |
| Pièce sous toiture | 51.8 °C | 57.0 °C | 40.1 °C | 46.9 °C |
| Grande baie sud | 54.2 °C | 55.8 °C | 38.3 °C | 40.3 °C |
| Canicule avec volets | 54.2 °C | 55.8 °C | 38.3 °C | 40.3 °C |
| Inertie légère | 53.0 °C | 54.8 °C | 37.1 °C | 41.0 °C |
| Inertie lourde | 35.2 °C | 35.2 °C | 31.2 °C | 31.2 °C |

Le scénario occupant raisonnable est commercialement présentable pour les cas traversant et inertie lourde. Les cas sous toiture, grande baie sud et inertie légère restent trop chauds : ce sont des stress tests, pas des cas clients standards.

## Limites connues

- Le modèle est un 1R1C horaire : une pièce est représentée par une seule température d'air et une capacité thermique équivalente.
- Les consommations annuelles sont sensibles à l'exposition. Un appartement sans toiture ni plancher exposés peut rester très bas même avec des U anciens.
- Les apports solaires sont simplifiés et peuvent dominer fortement les résultats, surtout sur les orientations sud et toiture.
- Les scénarios canicule actuels sont sévères. Sans protections solaires déclarées sur les fenêtres, les volets n'ont aucun effet.
- Le COP des PAC peut être variable via un profil de référence, mais plusieurs cas de référence utilisent encore un COP constant.
- Les usages réels ne sont pas encore modélisés finement : intermittence de chauffage, consignes variables, occupation, ouverture manuelle des fenêtres, ECS et auxiliaires.
- Les ponts thermiques sont représentés par un facteur global, pas par des linéiques détaillés.
- Les parois mitoyennes utilisent un facteur de réduction fixe, ce qui simplifie fortement les échanges avec les logements voisins.
- Les résultats des cas Phase 2 sont des bandes de régression du modèle courant. Ils ne constituent pas encore une calibration réglementaire ou DPE.

## Points à calibrer ensuite

- Revoir le cas `old_apartment_average_winter` si la cible 150-220 kWh/m²/an à Strasbourg doit être tenue : augmenter l'exposition extérieure, ajouter un plancher haut/faiblement déperditif, ou revoir l'ACH.
- Créer des profils annuels calibrés par typologie : appartement intermédiaire, appartement sous toiture, maison années 70, maison RT2012.
- Séparer clairement les cas de non-régression physique des cas de démonstration commerciale.
- Calibrer les profils canicule commerciaux pour viser 28-35 °C avec comportement occupant raisonnable sur les logements standards.
