# ThermalTwin — Description Produit

ThermalTwin crée un modèle thermique numérique de chaque logement — un jumeau virtuel qui simule son comportement face au chaud, au froid, et aux équipements énergétiques.

À partir de l'adresse, des caractéristiques du logement et de son exposition solaire, le produit calcule les déperditions thermiques pièce par pièce, les températures intérieures selon les saisons, et l'impact concret de tout changement d'équipement sur la facture énergétique et les émissions CO₂. Ce jumeau est ensuite mis entre les mains des professionnels qui vendent des solutions thermiques, comme outil d'aide à la décision et argument commercial chiffré face à leur client final.

---

## Entrées

- Adresse et orientation solaire
- Formulaire de caractéristiques du logement (pièces, matériaux, vitrages)
- Photos intérieures et extérieures de la maison
- Plans du logement
- Construction d'une maquette par le client (éditeur de plan)
- Paramètres métier configurables par le revendeur (ex : catalogue produits)

## Sorties

- Modèle thermique du logement
- Visualisation des déperditions par pièce — zones froides / chaudes identifiées
- Températures intérieures max estimées en été
- Simulation d'économies (€, CO₂, kWh) avec un nouvel équipement (clim, radiateur, peinture réfléchissante)
- Comparateur de scénarios côte à côte
- Rapport PDF white-label à destination du client final
- Rapport tunable des paramètres

---

## Clients cibles

### Priorité 1 — Cœur de cible MVP

| Client | Valeur apportée |
|---|---|
| Installateurs clim & PAC | Justifient le devis par des économies projetées précises. Réduisent les objections prix. |
| Revendeurs radiateurs | Passent d'un argument produit à un argument économique personnalisé par logement. |
| Artisans isolation & toiture | Montrent l'impact réel des travaux avant même de les réaliser. Argument canicule fort. |

### Priorité 2 — Extensions naturelles

| Client | Valeur apportée |
|---|---|
| Agences immobilières | Enrichissent la fiche bien au-delà du DPE. Outil de négociation sur les passoires thermiques. |
| Assureurs habitation | Scoring de risque thermique (gel, surchauffe). Incitation aux travaux via réduction de prime. |
| Collectivités & bailleurs sociaux | Priorisation des rénovations sur parc HLM. Reporting CO₂ réglementaire. |

---

## Contraintes techniques notables

- Propriétés thermiques des matériaux (coefficients U, λ) — base de données à constituer
- Prise en compte du mobilier et de sa masse thermique
- Géométrie de la maison
- Impact des murs mitoyens dans immeuble
- Orientation solaire et impact des baies vitrées (apports solaires directs)
- Performances réelles des équipements (radiateurs, clim, peintures réfléchissantes)

---

## Itérations produit

### L'outil commercial du revendeur

**Entrées du logement**
1. Formulaire guidé (pièces, dimensions, matériaux, exposition)
2. Enrichissement automatique par adresse (orientation solaire via API cadastre)
3. Import de plans (lecture assistée)
4. Éditeur de maquette simple par le client

**Moteur thermique**
1. Base de données matériaux (JSON / SQLite) — valeurs RT2012
2. Calcul des déperditions par scénario :
   - Année moyenne
   - Cas extrême (ex : épisode de forte chaleur)

**Visualisation & rapport**
1. Interface de visualisation des déperditions par pièce
2. Tuning des paramètres en temps réel (comparateur avant/après)
3. Rapport PDF white-label exportable, brandé au nom du revendeur

**SaaS & accès revendeur**
1. Authentification revendeur, historique des simulations par client
2. Personnalisation du rapport (logo, couleurs, coordonnées)
3. Compteur d'usage, blocage au quota, upgrade d'abonnement

---
