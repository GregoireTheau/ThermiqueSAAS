# Validation du modèle thermique

Ce document est le livrable de la phase 6. Il consolide les cas de référence, les premiers résultats de calibrage et les limites connues du modèle 1R1C horaire.

Les résultats ci-dessous sont des consommations de chauffage en énergie finale, en kWh/m²/an, obtenues en remplaçant la météo 24 h des cas hiver par les fichiers Open-Meteo thermiques 2023 locaux.

## Résultats annuels chauffage

| Cas | Bordeaux 2023 | Paris 2023 | Strasbourg 2023 | Lecture physique |
|---|---:|---:|---:|---|
| Appartement ancien mal isolé | 270.8 | 361.8 | 405.7 | Cas très sévère après ajout toiture et plancher bas exposés. Il dépasse la plage ancien 200-350 à Strasbourg. |
| Appartement ancien moyen | 74.3 | 104.1 | 119.9 | Trop bas pour la cible 150-220 à Strasbourg avec les paramètres imposés. L'exposition est trop faible sans toiture/plancher. |
| Maison récente RT2012 | 5.9 | 9.3 | 11.4 | Besoin thermique corrigé par la nébulosité, mais énergie finale encore basse avec PAC COP 3.2. |
| Maison années 70 | 119.5 | 165.0 | 188.9 | Cohérent en tendance, mais encore bas pour un logement ancien énergivore. |
| Hiver avec PAC | 6.0 | 9.4 | 11.5 | Besoin final très bas car la PAC du cas a un COP constant de 3.2. |
| Isolation toiture | 20.4 | 31.7 | 38.6 | Cas de comparaison rénovation, pas un niveau annuel réglementaire. |
| Remplacement fenêtres | 26.3 | 39.9 | 47.9 | Cas de comparaison rénovation, dépend fortement des gains solaires sud. |
| Ventilation forte | 36.5 | 53.0 | 62.3 | La hausse de ventilation augmente bien les besoins. |
| Ventilation faible | 6.1 | 10.2 | 13.8 | Cas volontairement très favorable thermiquement, sans jugement qualité d'air. |

## Comparaison aux fourchettes réelles

| Typologie | Fourchette repère | Résultat modèle | Diagnostic |
|---|---:|---:|---|
| Logement ancien énergivore | 200-350 kWh/m²/an | Appartement mal isolé : 271-406 selon météo | Cohérent à Bordeaux, trop sévère à Paris/Strasbourg. |
| Appartement ancien moyen | 150-220 kWh/m²/an cible interne | 74-120 selon météo | Sous-estimé avec les hypothèses actuelles. Il manque de surface déperditive exposée. |
| RT2012 | 40-80 kWh/m²/an | 6-11 final, 36 thermique à Strasbourg | Besoin thermique plausible, énergie finale basse car le cas utilise une PAC COP 3.2. |
| Puissance chauffage typique | 30-80 W/m² | Mal isolé : plafonné à 133 W/m² | Le cas mal isolé est très sévère et peut être limité par la puissance installée. |

Conclusion de calibrage : le modèle respecte les signes physiques, mais les cas annuels ne sont pas encore calibrés pour représenter des consommations françaises robustes par typologie. Les cas de référence restent utiles pour la non-régression, pas encore pour une promesse commerciale de consommation annuelle.

## Scénarios canicule

Deux lectures sont conservées pour les cas été :

- `canicule_sans_protection` : volets ouverts, comportement défavorable, logement non protégé.
- `canicule_occupant_raisonnable` : volets fermés de 8h à 19h avec `opening_ratio=0.1`, ventilation nocturne intelligente à 4 ACH quand l'air extérieur est plus frais.

Températures intérieures simulées :

| Cas | Sans protection 20h | Sans protection max | Occupant raisonnable 20h | Occupant raisonnable max |
|---|---:|---:|---:|---:|
| Logement traversant | 34.1 °C | 34.5 °C | 32.4 °C | 32.5 °C |
| Pièce sous toiture | 46.3 °C | 49.9 °C | 38.3 °C | 43.4 °C |
| Grande baie sud | 47.2 °C | 48.2 °C | 36.2 °C | 37.5 °C |
| Canicule avec volets | 47.2 °C | 48.2 °C | 36.2 °C | 37.5 °C |
| Inertie légère | 46.9 °C | 48.0 °C | 35.9 °C | 38.4 °C |
| Inertie lourde | 33.1 °C | 33.1 °C | 30.3 °C | 30.3 °C |

Le scénario occupant raisonnable est commercialement présentable pour les cas traversant et inertie lourde. Les cas sous toiture, grande baie sud et inertie légère restent trop chauds : ce sont des stress tests, pas des cas clients standards.

## Limites connues

- Le modèle est un 1R1C horaire : une pièce est représentée par une seule température d'air et une capacité thermique équivalente.
- Les consommations annuelles sont sensibles à l'exposition. Un appartement sans toiture ni plancher exposés peut rester très bas même avec des U anciens.
- Les apports solaires sont simplifiés et peuvent dominer fortement les résultats, surtout sur les orientations sud et toiture.
- Un facteur de nébulosité mensuel est appliqué dans le moteur à partir de la zone climatique et du mois météo. Sans mois ou zone climatique, le facteur vaut 1.0 pour préserver la rétrocompatibilité.
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
