# Documentation thermique MVP - equations de reference

Ce document definit le modele thermique de depart pour ThermalTwin. L'objectif n'est pas de faire un solveur physique complet, mais un modele robuste, explicable et rapide pour :

- calculer les deperditions par piece et par type de paroi ;
- estimer les temperatures interieures, notamment en canicule ;
- comparer des scenarios avant/apres : isolation, vitrage, volets, PAC, climatisation, peinture reflective ;
- produire des resultats commerciaux comprehensibles : kWh, dollars US et zones de pertes.

Les valeurs numeriques ne sont pas definies ici. Elles devront venir de la base materiaux, de la meteo, des scenarios et des hypotheses produit.

---

## 1. Philosophie du modele

### 1.1 Ce que le MVP modelise

Le modele retenu est un modele dynamique 1R1C par piece :

- une temperature d'air par piece ;
- une capacite thermique equivalente par piece ;
- des pertes par transmission `U * A * DeltaT` ;
- une ventilation/infiltration simplifiee par taux de renouvellement d'air `ACH` ;
- des apports solaires sur vitrages et parois opaques ;
- un effet simple des volets/stores ;
- un effet simple de l'albedo des murs et toitures ;
- un couplage thermique entre pieces ;
- chauffage et climatisation comme puissances instantanees plafonnees.

Ce niveau est suffisant pour simuler une annee au pas horaire et afficher des differences utiles entre scenarios.

### 1.2 Ce que le MVP ne modelise pas

Ces elements sont volontairement exclus au depart :

- humidite, condensation, point de rosee et chaleur latente ;
- ouverture courte d'une porte pendant quelques secondes ;
- calculs aerodynamiques par pression au vent, tirage thermique et coefficients de facade ;
- rayonnement infrarouge exact en `T^4` entre surfaces ;
- reflexions solaires 3D entre batiments voisins ;
- inertie detaillee des radiateurs, planchers chauffants ou reseaux d'eau ;
- regulation PI/PID avancee ;
- cavite thermique detaillee entre volet et vitrage ;
- ponts thermiques ponctuels ;
- asymetrie radiative fine pres des fenetres ;
- modele multicouche dynamique des murs.

Si un besoin produit le justifie plus tard, ces effets pourront etre ajoutes apres validation sur cas reels.

---

## 2. Grandeurs et conventions

### 2.1 Variables principales

- `T_i` : temperature de la piece `i`
- `T_ext` : temperature exterieure
- `T_adj` : temperature d'une zone adjacente non simulee
- `T_consigne_ch` : consigne de chauffage
- `T_consigne_clim` : consigne de climatisation
- `A` : surface d'une paroi ou d'un vitrage
- `V_i` : volume d'air de la piece `i`
- `S_i` : surface habitable de la piece `i`
- `C_i` : capacite thermique equivalente de la piece `i`
- `U` : coefficient de transmission thermique d'une paroi ou fenetre
- `R` : resistance thermique
- `lambda` : conductivite thermique d'un materiau
- `ACH_i` : taux de renouvellement d'air de la piece `i`
- `q_air_i` : debit volumique d'air entrant dans la piece `i`
- `rho_air` : masse volumique de l'air
- `c_p_air` : capacite thermique massique de l'air
- `I_plan` : irradiance solaire recue par une surface
- `g_vitre` : facteur solaire du vitrage
- `alpha` : absorptivite solaire d'une surface opaque
- `rho` : albedo ou reflectivite solaire d'une surface opaque
- `F_volet` : facteur de reduction solaire par protection
- `Phi` : puissance thermique
- `Q` : energie thermique
- `dt` : pas de temps de simulation

### 2.2 Convention de signe

Une puissance positive chauffe la piece.

```text
C_i * dT_i/dt = Phi_net_i
```

Discretisation explicite au pas `dt` :

```text
T_i(t + dt) = T_i(t) + dt / C_i * Phi_net_i(t)
```

Si `dt` est en secondes, `C_i` est en `J/K` et `Phi` en `W`.

---

## 3. Modele dynamique par piece

### 3.1 Equation generale MVP

Pour chaque piece `i` :

```text
C_i * dT_i/dt =
    Phi_chauffage_i
  - Phi_clim_i
  + Phi_solaire_vitrages_i
  + Phi_solaire_opaque_i
  + Phi_internes_i
  + somme_j(H_ij * (T_j - T_i))
  + H_ext_i * (T_ext - T_i)
  + H_air_i * (T_ext - T_i)
```

Cette equation est le coeur du moteur thermique MVP.

### 3.2 Coefficient de deperdition exterieur

```text
H_ext_i =
    somme_parois_exterieures(U_p * A_p)
  + somme_vitrages(U_v * A_v)
  + H_ponts_i
```

Pour un MVP, `H_ponts_i` peut etre une majoration des pertes par parois :

```text
H_ponts_i = f_ponts_i * somme_parois_exterieures(U_p * A_p)
```

ou directement :

```text
H_ext_i = (1 + f_ponts_i) * somme_parois_et_vitrages(U * A)
```

`f_ponts_i` depend typiquement de l'age du batiment, de la qualite d'isolation et du type constructif.

### 3.3 Couplage entre pieces

Pour deux pieces `i` et `j` separees par une paroi ou une ouverture interieure :

```text
Phi_j_vers_i = H_ij * (T_j - T_i)
```

avec :

```text
H_ij = U_ij * A_ij
```

Pour une porte interieure souvent ouverte, on peut augmenter `H_ij` par un coefficient empirique :

```text
H_ij_eff = F_ouverture_interieure * U_ij * A_ij
```

Le modele ne simule pas les ouvertures seconde par seconde. Il represente seulement le niveau moyen de couplage thermique entre pieces.

### 3.4 Forme matricielle

Pour `N` pieces :

```text
C * dT/dt = A * T + B * U_entrees
```

Cette forme sera utile pour une implementation stable et rapide, mais l'implementation peut commencer par une boucle piece par piece.

---

## 4. Transmission par conduction

### 4.1 Resistance multicouche

Pour une paroi composee de couches en serie :

```text
R_paroi = somme_k(e_k / lambda_k)
```

Avec resistances superficielles si elles ne sont pas deja incluses dans la valeur `U` :

```text
R_total = R_si + somme_k(e_k / lambda_k) + R_se
U = 1 / R_total
```

### 4.2 Flux par paroi exterieure

```text
Phi_paroi = U * A * (T_ext - T_i)
```

Dans cette convention, si l'exterieur est plus froid que la piece, `Phi_paroi` est negatif et refroidit la piece.

Pour afficher une deperdition positive :

```text
Phi_deperdition = U * A * (T_i - T_ext)
```

### 4.3 Paroi vers local non chauffe ou mur mitoyen

Si la zone adjacente a une temperature estimee :

```text
Phi_adj = U * A * (T_adj - T_i)
```

Si on veut eviter de simuler `T_adj`, on utilise un facteur reducteur :

```text
Phi_adj = b_loss * U * A * (T_ext - T_i)
```

`b_loss` represente la fraction de perte effective vers l'exterieur.

### 4.4 Sol

MVP simple :

```text
Phi_sol = U_sol * A_sol * (T_sol - T_i)
```

`T_sol` peut etre une temperature exterieure lissee ou une hypothese saisonniere issue du scenario.

---

## 5. Ventilation et infiltration simplifiees

### 5.1 Taux de renouvellement d'air

Le MVP utilise un taux `ACH` fixe ou semi-parametre, au lieu de calculer les pressions au vent.

```text
q_air_i = ACH_i * V_i / temps_reference
```

Si `ACH_i` est en volumes par heure :

```text
q_air_i = ACH_i * V_i / 3600
```

### 5.2 Puissance thermique associee

```text
H_air_i = rho_air * c_p_air * q_air_i
```

Flux dans le bilan :

```text
Phi_air_i = H_air_i * (T_ext - T_i)
```

### 5.3 VMC avec recuperation de chaleur

Si une VMC double flux est modelisee :

```text
T_soufflage = T_ext + eta_recup * (T_i - T_ext)
```

Flux equivalent :

```text
Phi_air_i = rho_air * c_p_air * q_air_i * (T_soufflage - T_i)
```

ou :

```text
H_air_eff_i = rho_air * c_p_air * q_air_i * (1 - eta_recup)
Phi_air_i = H_air_eff_i * (T_ext - T_i)
```

### 5.4 Effet simplifie du vent

Le vent peut etre integre par une correction simple du renouvellement d'air, sans modele de pression :

```text
ACH_i = ACH_base_i * F_vent
```

Exemple de forme generique :

```text
F_vent = 1 + k_vent * max(0, v_vent - v_ref)
```

Cette correction doit rester bornee :

```text
ACH_i = clamp(ACH_i, ACH_min_i, ACH_max_i)
```

---

## 6. Apports solaires

### 6.1 Irradiance sur une surface

L'irradiance recue par une paroi ou un vitrage est :

```text
I_plan = I_direct_plan + I_diffus_plan + I_reflechi_sol_plan
```

Composante directe :

```text
I_direct_plan = DNI * max(0, cos(theta_incidence))
```

Composante diffuse simplifiee :

```text
I_diffus_plan = DHI * F_ciel
```

Composante reflechie par le sol :

```text
I_reflechi_sol_plan = GHI * rho_sol * F_sol
```

Facteurs de vue simplifiees pour une surface inclinee d'angle `beta` :

```text
F_ciel = (1 + cos(beta)) / 2
F_sol = (1 - cos(beta)) / 2
```

Angle d'incidence :

```text
cos(theta_incidence) = max(0, dot(n_surface, s_soleil))
```

### 6.2 Masques simples

Les masques solaires sont representes par un facteur multiplicatif :

```text
I_plan_eff = I_plan * F_masque
```

avec :

```text
0 <= F_masque <= 1
```

Le MVP peut commencer avec `F_masque` constant par vitrage/paroi, puis passer a un masque geometrique simple selon la position du soleil.

---

## 7. Vitrages et protections solaires

### 7.1 Apport solaire par vitrage

```text
Phi_solaire_vitre =
    A_vitre * I_plan_eff * g_vitre * F_volet
```

Pour une piece :

```text
Phi_solaire_vitrages_i =
    somme_vitrages_i(A_v * I_plan_v * F_masque_v * g_v * F_volet_v)
```

`g_vitre` suffit pour le MVP : il integre la transmission directe et la part absorbee par le vitrage qui revient vers l'interieur.

### 7.2 Transmission thermique par vitrage

```text
Phi_vitrage = U_vitre * A_vitre * (T_ext - T_i)
```

### 7.3 Volets et stores

Le volet/store agit avec deux effets simples.

Reduction solaire :

```text
Phi_solaire_vitre_protegee =
    A_vitre * I_plan_eff * g_vitre * F_volet
```

Amelioration eventuelle de transmission :

```text
U_vitre_eff = F_U_volet * U_vitre
```

Puis :

```text
Phi_vitrage = U_vitre_eff * A_vitre * (T_ext - T_i)
```

`F_volet` et `F_U_volet` peuvent dependre de l'etat du volet :

```text
F_volet = F_ferme + ouverture_volet * (F_ouvert - F_ferme)
```

Le MVP ne modelise pas la cavite entre volet et vitrage.

---

## 8. Albedo, murs et toitures

### 8.1 Absorption solaire d'une surface opaque

Pour une surface opaque :

```text
alpha = 1 - rho
```

Puissance solaire absorbee :

```text
Phi_abs_opaque = alpha * I_plan_eff * A
```

Une peinture reflective ou une toiture claire reduit `alpha` et augmente `rho`.

### 8.2 Part transmise vers l'interieur

Le MVP ne resout pas la temperature detaillee de surface. Il utilise un coefficient simple qui represente la fraction de chaleur solaire absorbee finissant dans la piece :

```text
Phi_solaire_opaque_vers_piece =
    eta_opaque * alpha * I_plan_eff * A
```

Pour une piece :

```text
Phi_solaire_opaque_i =
    somme_parois_opaques_i(eta_p * alpha_p * I_plan_p * F_masque_p * A_p)
```

`eta_opaque` depend de la paroi, de son isolation et de son inertie. Il doit etre calibre ou choisi par typologie.

### 8.3 Scenario peinture reflective

Reduction d'apport solaire absorbe :

```text
Delta_Phi_abs = (alpha_avant - alpha_apres) * I_plan_eff * A
```

Reduction estimee de l'apport interieur :

```text
Delta_Phi_piece = eta_opaque * Delta_Phi_abs
```

Cette equation est centrale pour vendre l'effet anti-canicule d'une toiture ou peinture reflective.

---

## 9. Inertie thermique 1R1C

### 9.1 Capacite thermique equivalente

Chaque piece a une seule capacite thermique equivalente :

```text
C_i = C_air_i + C_mobilier_i + C_masse_active_i
```

Air :

```text
C_air_i = rho_air * V_i * c_p_air
```

Masse thermique simplifiee :

```text
C_masse_active_i = c_surface_type_i * S_i
```

ou plus generalement :

```text
C_i = c_equiv_i * S_i
```

`c_equiv_i` est une hypothese par typologie : logement leger, moyen, lourd.

### 9.2 Modele 1R1C

Forme simplifiee :

```text
C_i * dT_i/dt =
    Phi_apports_i
  + H_ext_i * (T_ext - T_i)
  + H_air_i * (T_ext - T_i)
  + somme_j(H_ij * (T_j - T_i))
```

Ce modele suffit pour simuler un dephasage global en canicule sans modeliser chaque couche de mur.

---

## 10. Apports internes simplifiés

Le MVP ne demande pas au client de detailler ses appareils.

### 10.1 Apport moyen au m2

```text
Phi_internes_i = p_interne_scenario * S_i
```

`p_interne_scenario` depend du scenario d'occupation : absent, standard, forte occupation.

### 10.2 Planning d'occupation

Avec planning :

```text
Phi_internes_i(t) = p_interne_scenario(t) * S_i
```

Cela suffit pour representer un logement vide en journee ou occupe en soiree.

---

## 11. Chauffage

### 11.1 Chauffage instantane plafonne

Le chauffage injecte directement une puissance thermique dans la piece :

```text
0 <= Phi_chauffage_i <= P_chauffage_max_i
```

Besoin pour atteindre la consigne au pas suivant :

```text
Phi_chauffage_requise_i =
    max(0, (T_consigne_ch - T_i_libre_apres_dt) * C_i / dt)
```

Puissance appliquee :

```text
Phi_chauffage_i = min(Phi_chauffage_requise_i, P_chauffage_max_i)
```

### 11.2 Consommation energetique

Radiateur electrique :

```text
P_elec_i = Phi_chauffage_i
```

Pompe a chaleur :

```text
P_elec_i = Phi_chauffage_i / COP_t
```

Energie :

```text
E_chauffage = somme_t(P_elec_t * dt)
```

`COP_t` peut dependre de la temperature exterieure et du type d'equipement, mais cette dependance peut etre tabulee.

---

## 12. Climatisation

### 12.1 Refroidissement sensible uniquement

Le MVP ignore la chaleur latente et la deshumidification.

```text
0 <= Phi_clim_i <= P_clim_max_i
```

Besoin pour atteindre la consigne au pas suivant :

```text
Phi_clim_requise_i =
    max(0, (T_i_libre_apres_dt - T_consigne_clim) * C_i / dt)
```

Puissance appliquee :

```text
Phi_clim_i = min(Phi_clim_requise_i, P_clim_max_i)
```

Dans le bilan :

```text
C_i * dT_i/dt = ... - Phi_clim_i
```

### 12.2 Consommation energetique

```text
P_elec_i = Phi_clim_i / EER_t
```

Energie :

```text
E_clim = somme_t(P_elec_t * dt)
```

`EER_t` peut etre constant au depart ou tabule selon la temperature exterieure.

---

## 13. Ponts thermiques simplifiés

### 13.1 Majoration MVP

Au lieu de demander tous les ponts lineiques, le MVP applique une majoration :

```text
H_transmission_corrige =
    (1 + f_ponts) * somme_parois_et_vitrages(U * A)
```

`f_ponts` est choisi selon l'annee de construction, le niveau d'isolation ou une classe simple du batiment.

### 13.2 Option plus precise

Si le modele de donnees contient les longueurs principales :

```text
H_ponts = somme_l(psi_l * L_l)
```

Puis :

```text
H_ext = somme(U * A) + H_ponts
```

Les ponts ponctuels sont exclus du MVP.

---

## 14. Confort thermique simplifié

### 14.1 Temperature d'air

La temperature de reference du MVP est :

```text
T_confort_i = T_i
```

C'est la grandeur principale affichee pour les scenarios ete/hiver.

### 14.2 Temperature operatoire optionnelle

Pour montrer un effet de paroi froide ou chaude sans modele radiatif complexe :

```text
T_oper_i = (T_i + T_parois_moy_i) / 2
```

Approximation de la temperature moyenne des parois :

```text
T_parois_moy_i =
    moyenne_ponderee_surfaces(T_surface_estimee_p)
```

Cette option peut etre ajoutee plus tard. Elle n'est pas necessaire pour le premier moteur.

### 14.3 Degres-heures d'inconfort

Surchauffe :

```text
DH_chaud_i = somme_t(max(0, T_i(t) - T_seuil_chaud) * dt)
```

Froid :

```text
DH_froid_i = somme_t(max(0, T_seuil_froid - T_i(t)) * dt)
```

---

## 15. Energie et facture US

### 15.1 Energie thermique et finale

Energie thermique :

```text
Q_thermique = somme_t(Phi_thermique_t * dt)
```

Energie finale :

```text
E_finale = somme_t(P_elec_ou_combustible_t * dt)
```

### 15.2 Cout

```text
Cout = somme_energies(E_finale_energie * prix_unitaire_energie)
```

Avec abonnement :

```text
Cout_total = Cout_variable + Cout_fixe
```

Comparaison scenario :

```text
Delta_E = E_avant - E_apres
Delta_Cout = Cout_avant - Cout_apres
```

Le rapport commercial US ne publie aucun KPI CO2 au lancement. Une future
réintégration exigera un facteur électrique régional, une source explicite et
une version datée.

---

## 16. Scenarios avant / apres

### 16.1 Isolation

Avant :

```text
Phi_avant = U_avant * A * (T_ext - T_i)
```

Apres :

```text
U_apres = 1 / (R_avant + R_isolant)
Phi_apres = U_apres * A * (T_ext - T_i)
```

Gain de deperdition en hiver :

```text
Delta_Phi_deperdition = (U_avant - U_apres) * A * (T_i - T_ext)
```

### 16.2 Vitrage

Transmission :

```text
Delta_Phi_transmission =
    (U_avant - U_apres) * A_vitre * (T_i - T_ext)
```

Solaire :

```text
Delta_Phi_solaire =
    (g_apres - g_avant) * A_vitre * I_plan_eff
```

Un vitrage avec un `g` plus faible reduit la surchauffe d'ete, mais peut aussi reduire les apports gratuits d'hiver.

### 16.3 Volets et stores

```text
Delta_Phi_solaire =
    A_vitre * I_plan_eff * g_vitre * (F_volet_avant - F_volet_apres)
```

Transmission :

```text
Delta_Phi_transmission =
    (U_eff_avant - U_eff_apres) * A_vitre * (T_i - T_ext)
```

### 16.4 Peinture reflective ou toiture claire

```text
Delta_Phi_abs =
    (alpha_avant - alpha_apres) * I_plan_eff * A
```

```text
Delta_Phi_piece = eta_opaque * Delta_Phi_abs
```

### 16.5 Pompe a chaleur ou chauffage

Le besoin thermique du logement est calcule par le modele. L'equipement change la consommation finale :

```text
E_finale_avant = somme_t(Phi_chauffage_t / performance_avant_t * dt)
E_finale_apres = somme_t(Phi_chauffage_t / performance_apres_t * dt)
```

### 16.6 Climatisation

Temperature libre sans clim :

```text
T_libre(t + dt) = T(t) + dt / C * Phi_net_sans_clim(t)
```

Besoin de froid :

```text
Phi_clim_requise =
    max(0, (T_libre(t + dt) - T_consigne_clim) * C / dt)
```

Consommation :

```text
E_clim = somme_t(Phi_clim_t / EER_t * dt)
```

---

## 17. Donnees a prevoir

### 17.1 Logement

- pieces : surface, volume, temperature initiale, typologie d'inertie ;
- parois exterieures : surface, orientation, inclinaison, `U`, albedo ou couleur, masque eventuel ;
- vitrages : surface, orientation, inclinaison, `U`, `g`, protections ;
- parois interieures : surface et coefficient de couplage entre pieces ;
- ventilation : `ACH` ou type de VMC ;
- equipements : puissance maximale, performance, piece desservie ;
- ponts thermiques : facteur de majoration ou longueurs lineiques principales.

### 17.2 Meteo

- temperature exterieure horaire ;
- irradiance solaire : `DNI`, `DHI`, `GHI` ou donnees equivalents ;
- position solaire ;
- vitesse du vent optionnelle pour corriger `ACH` ;
- albedo du sol/environnement proche.

### 17.3 Scenario

- consignes chauffage et climatisation ;
- planning d'occupation simplifie ;
- planning volets/stores ;
- scenario travaux avant/apres ;
- prix energie en $/kWh, $/therm et $/gallon de propane.

---

## 18. Ordre d'implementation recommande

### 18.1 Version 1 - Deperditions statiques

Objectif : calculer les pertes par piece.

```text
H_piece = (1 + f_ponts) * somme(U * A) + rho_air * c_p_air * q_air
Phi_deperdition = H_piece * (T_i - T_ext)
```

Sorties :

- pertes par mur, toit, sol, vitrage ;
- pertes par ventilation ;
- pertes par piece ;
- puissance de chauffage requise a temperature exterieure donnee.

### 18.2 Version 2 - Dynamique 1R1C

Objectif : simuler les temperatures heure par heure.

```text
T_i(t + dt) = T_i(t) + dt / C_i * Phi_net_i(t)
```

Sorties :

- temperature interieure libre ;
- temperature avec chauffage/clim ;
- temperature maximale en canicule ;
- degres-heures d'inconfort.

### 18.3 Version 3 - Solaire et volets

Objectif : expliquer la surchauffe et l'effet des protections.

```text
Phi_solaire_vitrages_i =
    somme(A_v * I_plan_v * F_masque_v * g_v * F_volet_v)
```

Sorties :

- apports solaires par facade ;
- effet fermeture des volets ;
- comparaison vitrage avant/apres.

### 18.4 Version 4 - Albedo et peintures reflectives

Objectif : simuler toiture claire, peinture reflective ou revetement anti-chaleur.

```text
Phi_solaire_opaque_i =
    somme(eta_p * alpha_p * I_plan_p * F_masque_p * A_p)
```

Sorties :

- baisse de temperature max estimee ;
- baisse de besoin clim ;
- comparaison avant/apres albedo.

### 18.5 Version 5 - Couplage pieces

Objectif : afficher des flux entre pieces et des zones chaudes/froides.

```text
Phi_j_vers_i = H_ij * (T_j - T_i)
```

Sorties :

- carte thermique par piece ;
- effet d'un equipement localise ;
- propagation thermique dans le logement.

---

## 19. Pieges a eviter

### 19.1 Doubles comptes

Ne pas compter deux fois :

- les ponts thermiques si `U` ou `H` les inclut deja ;
- les resistances superficielles si `U` est deja fourni complet ;
- la ventilation naturelle et l'infiltration si elles sont representees par le meme `ACH` ;
- la part absorbee du vitrage si `g_vitre` est deja utilise ;
- les apports solaires des parois opaques si on utilise deja une temperature exterieure equivalente.

### 19.2 Trop d'inputs utilisateur

Pour le MVP, eviter de demander :

- le nombre exact d'appareils electriques ;
- les coefficients de pression de facade ;
- les longueurs detaillees de tous les ponts thermiques ;
- les couches dynamiques completes des murs ;
- les habitudes exactes d'ouverture des portes.

Preferer des typologies simples : age du batiment, niveau d'isolation, type de ventilation, type de vitrage, orientation, presence de volets.

### 19.3 Stabilite numerique

Le pas de temps doit rester coherent avec l'inertie :

```text
Delta_T = dt / C_i * Phi_net_i
```

Si `Delta_T` devient trop grand sur un pas, il faut reduire `dt`, augmenter l'inertie equivalente ou passer a une integration semi-implicite.

---

## 20. Synthese des equations MVP

Transmission :

```text
Phi = U * A * (T_ext - T_i)
```

Deperdition affichee :

```text
Phi_deperdition = U * A * (T_i - T_ext)
```

Ventilation ACH :

```text
q_air = ACH * V / 3600
Phi_air = rho_air * c_p_air * q_air * (T_ext - T_i)
```

Solaire vitrage :

```text
Phi_solaire_vitre = A * I_plan * F_masque * g * F_volet
```

Solaire opaque et albedo :

```text
Phi_solaire_opaque = eta_opaque * alpha * I_plan * F_masque * A
alpha = 1 - rho
```

Ponts thermiques simplifiés :

```text
H_corrige = (1 + f_ponts) * somme(U * A)
```

Couplage entre pieces :

```text
Phi_j_vers_i = H_ij * (T_j - T_i)
```

Modele 1R1C :

```text
C_i * dT_i/dt =
    Phi_chauffage_i
  - Phi_clim_i
  + Phi_solaire_vitrages_i
  + Phi_solaire_opaque_i
  + Phi_internes_i
  + somme_j(H_ij * (T_j - T_i))
  + H_ext_i * (T_ext - T_i)
  + H_air_i * (T_ext - T_i)
```

Integration :

```text
T_i(t + dt) = T_i(t) + dt / C_i * Phi_net_i(t)
```

Chauffage :

```text
Phi_chauffage = min(max(0, (T_consigne_ch - T_libre) * C / dt), P_chauffage_max)
P_elec = Phi_chauffage / performance
```

Climatisation :

```text
Phi_clim = min(max(0, (T_libre - T_consigne_clim) * C / dt), P_clim_max)
P_elec = Phi_clim / EER
```
