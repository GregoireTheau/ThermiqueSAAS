# To Do List

## Cadrage & recherche
- [x] Création dépôt GitHub
- [x] Construire une description du projet la plus claire possible (`Project Description`)
- [x] Distinguer les différentes parties du projet
- [ ] Interviewer 2-3 installateurs / revendeurs cibles pour valider ce qu'ils attendent du rapport
- [ ] Documenter les bases de physique thermique nécessaires aux calculs (Q = U·A·ΔT, ponts thermiques, apports solaires)
- [ ] Déterminer les types de simulation à lancer (année moyenne, cas extrême canicule, cas extrême gel)
- [ ] Recenser les valeurs de référence : coefficients U par matériau (source RT2012), zones climatiques France

## Modèle de données
- [ ] Définir la structure JSON du logement (pièces, parois, matériaux, orientation, équipements)
- [ ] Définir la structure JSON d'un scénario (équipement avant / après)
- [ ] Implémenter la base de données matériaux (SQLite ou JSON statique)
- [ ] Implémenter la base de données équipements (radiateurs, clim, isolation) avec leurs performances

## Moteur thermique
- [ ] Coder le calcul des déperditions par paroi et par pièce
- [ ] Coder la simulation scénario "avant / après équipement"
- [ ] Coder la conversion en impact facture (€) et émissions (CO₂)
- [ ] Valider les résultats sur 2-3 cas réels connus (cross-check avec un thermicien ou outil de référence)

## Entrées utilisateur
- [ ] Coder le formulaire de saisie guidée (pièces, matériaux, exposition)
- [ ] Intégrer l'API adresse (BAN) pour récupérer l'orientation automatique
- [ ] Connecter les entrées au modèle de données JSON

## Sorties & rapport
- [ ] Coder la visualisation des déperditions par pièce (carte thermique 2D)
- [ ] Coder le comparateur de scénarios (avant / après, side by side)
- [ ] Générer le rapport PDF white-label (WeasyPrint)

## SaaS & mise en ligne
- [ ] Auth revendeur (login, comptes)
- [ ] Historique des simulations par client
- [ ] Compteur d'usage et gestion des quotas