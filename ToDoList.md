# To Do List

## Cadrage & recherche
- [x] Création dépôt GitHub
- [x] Construire une description du projet la plus claire possible (`Project Description`)
- [x] Distinguer les différentes parties du projet
- [ ] Interviewer 2-3 installateurs / revendeurs cibles pour valider ce qu'ils attendent du rapport
- [x] Documenter les bases de physique thermique nécessaires aux calculs (Q = U·A·ΔT, ponts thermiques, apports solaires)
- [x] Déterminer les types de simulation à lancer (année moyenne, cas extrême canicule, cas extrême gel)
- [ ] Recenser les valeurs de référence : coefficients U par matériau (source RT2012), zones climatiques France

## Modèle de données
- [x] Définir la structure JSON du logement (pièces, parois, matériaux, orientation, équipements)
- [x] Définir la structure JSON d'un scénario (équipement avant / après)
- [ ] Implémenter la base de données matériaux (SQLite ou JSON statique)
- [ ] Implémenter la base de données équipements (radiateurs, clim, isolation) avec leurs performances

## Moteur thermique
- [x] Coder le calcul des déperditions par paroi et par pièce
- [x] Coder la simulation scénario "avant / après équipement"
- [x] Coder la conversion en impact facture (€) et émissions (CO₂)
- [ ] Valider les résultats sur 2-3 cas réels connus (cross-check avec un thermicien ou outil de référence)

## Entrées utilisateur
- [x] Coder le formulaire de saisie guidée (pièces, matériaux, exposition)
- [ ] Intégrer l'API adresse (BAN) pour récupérer l'orientation automatique
- [x] Connecter les entrées au modèle de données JSON

## Sorties & rapport
- [ ] Coder la visualisation des déperditions par pièce (carte thermique 2D)
- [x] Coder le comparateur de scénarios (avant / après, side by side)
- [x] Générer le rapport html
- [ ] Ajouter au rapport un schéma du logement
- [ ] Générer le rapport PDF

## SaaS & mise en ligne
- [ ] Mini-Interface 
- [ ] Auth revendeur (login, comptes)
- [ ] Historique des simulations par client
- [ ] Compteur d'usage et gestion des quotas