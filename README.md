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

## Export PDF SaaS

L'endpoint SaaS `GET /simulation-runs/{id}/report-pdf` genere un PDF serveur a
partir du rapport HTML stocke. Il utilise Chrome ou Chromium en mode headless.

Prerequis runtime :

- installer Chrome ou Chromium sur le serveur applicatif ;
- verifier que le binaire est dans le `PATH`, ou definir explicitement
  `THERMAL_PDF_BROWSER_PATH`, par exemple :

```bash
export THERMAL_PDF_BROWSER_PATH="/usr/bin/chromium"
```

Sur macOS local, l'application cherche aussi
`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`.

Si aucun binaire Chrome/Chromium n'est disponible, ou si le rendu echoue, l'API
renvoie `503 Service Unavailable` avec le detail de l'erreur. Le rapport HTML
reste accessible via `/simulation-runs/{id}/report-html`.

Les fichiers telecharges sont nommes avec le client ou projet, le scenario, la
saison, le role et la date de simulation, par exemple :

```text
rapport-mme-dupont-better-windows-annual-annual-2026-05-22.pdf
```

## Configuration securite SaaS

Variables d'environnement recommandees avant beta fermee :

- `THERMAL_SAAS_SECRET_KEY` : secret serveur long aleatoire utilise pour signer
  les tokens de session stockes sous forme de hash HMAC. Obligatoire et 32
  caracteres minimum si `THERMAL_SAAS_ENV=production`.
- `THERMAL_SAAS_ENV=production` : active l'exigence de secret explicite.
- `THERMAL_SAAS_SESSION_TTL_HOURS` : duree de validite des sessions bearer.
  Valeur par defaut : `12`.
- `THERMAL_SAAS_CORS_ORIGINS` : origines autorisees separees par virgule.
  Valeur locale par defaut :
  `http://127.0.0.1:8000,http://127.0.0.1:8010`. En production, aucune origine
  locale n'est ajoutee par defaut et `*` est refuse.
- `THERMAL_SAAS_ALLOWED_HOSTS` : hosts HTTP acceptes par l'application.
  Valeur locale par defaut : `127.0.0.1,localhost,testserver`. En production,
  aucun host local n'est ajoute par defaut.
- `THERMAL_SAAS_MAX_REQUEST_BYTES` : taille maximale acceptee pour un payload
  HTTP. Valeur par defaut : `1000000`.
- `THERMAL_SAAS_AUTH_RATE_LIMIT_ATTEMPTS` : nombre de tentatives login/register
  autorisees par IP + email dans la fenetre de temps. Valeur par defaut : `10`.
- `THERMAL_SAAS_AUTH_RATE_LIMIT_WINDOW_SECONDS` : fenetre du rate limit auth.
  Valeur par defaut : `300`.

L'interface n'ecrit plus le token en `localStorage`. Le serveur pose un cookie
`HttpOnly`, `SameSite=Lax`, `Secure` en production, tout en gardant le bearer
token dans la reponse API pour compatibilite avec les tests et clients internes.

Exemple :

```bash
export THERMAL_SAAS_ENV=production
export THERMAL_SAAS_SECRET_KEY="change-this-long-random-secret-32chars-min"
export THERMAL_SAAS_SESSION_TTL_HOURS=12
export THERMAL_SAAS_CORS_ORIGINS="https://beta.example.com"
export THERMAL_SAAS_ALLOWED_HOSTS="beta.example.com"
```

## Migrations DB

Le schema SaaS est versionne avec Alembic. Au startup FastAPI et sur `/health`,
`init_db()` execute `alembic upgrade head` sur la base configuree par
`THERMAL_SAAS_DB_PATH`. Sur un disque Render neuf et vide, le fichier SQLite est
donc cree et migre automatiquement avant que le service soit considere healthy.
Alembic maintient la version courante dans `alembic_version`.

Regles de modification :

- ajouter une revision dans `migrations/versions/` ;
- renseigner `revision` et `down_revision` ;
- garder les migrations idempotentes autant que possible pour supporter les bases
  SQLite deja creees avant Alembic (`create table if not exists`, verification de
  colonnes avant `alter table`, `create index if not exists`) ;
- ajouter un test de migration legacy dans `tests/test_saas_storage.py` si la
  migration modifie une table existante.

Les migrations actuelles couvrent le schema initial, la normalisation des noms
d'organisation, le branding organisation et l'expiration des sessions.

## Deploiement beta fermee

Le deploiement beta vise une instance unique, quelques utilisateurs internes ou
clients pilotes, et une base persistante simple. Le code SaaS utilise encore
`sqlite3` directement : la strategie retenue pour cette etape est donc
**SQLite persistant temporaire**, pas PostgreSQL immediat.

### Lancement Docker local

```bash
cp .env.example .env
# Modifier THERMAL_SAAS_SECRET_KEY, CORS, allowed hosts et domaine.
docker compose up --build
```

Application :

```text
http://127.0.0.1:8000/app
```

Healthcheck :

```text
http://127.0.0.1:8000/health
```

Validation locale du conteneur :

```bash
docker compose ps
curl http://127.0.0.1:8000/health
docker compose exec thermal-saas python - <<'PY'
import sqlite3
con = sqlite3.connect("/app/storage/thermal_saas.sqlite")
print(con.execute("select version_num from alembic_version").fetchone()[0])
PY
```

`/health` verifie aussi que la base est migrable avec Alembic. Si le volume
SQLite est inaccessible ou si une migration echoue, le healthcheck doit passer
en erreur.

### Variables d'environnement beta

Valeurs minimales a renseigner :

```bash
THERMAL_SAAS_ENV=production
THERMAL_SAAS_SECRET_KEY=<secret long aleatoire>
THERMAL_SAAS_DB_PATH=/app/storage/thermal_saas.sqlite
THERMAL_SAAS_CORS_ORIGINS=https://thermal-saas-beta.onrender.com,https://thermal-beta.example.com
THERMAL_SAAS_ALLOWED_HOSTS=thermal-saas-beta.onrender.com,thermal-beta.example.com
THERMAL_PDF_BROWSER_PATH=/usr/bin/chromium
```

Le Dockerfile installe Chromium pour l'export PDF serveur et expose `/health`.
Le volume Docker `thermal_saas_data` persiste `/app/storage`, donc la base
SQLite survit aux redemarrages et redeploiements du conteneur.

### Choix hebergement

Option recommandee pour la beta fermee : **Render Web Service Docker + Persistent
Disk**.

Raisons :

- Dockerfile supporte nativement ;
- persistent disk disponible pour garder `/app/storage` ;
- healthcheck HTTP configurable sur `/health` ;
- domaine de test et TLS geres rapidement ;
- complexite operationnelle plus faible qu'un VPS.

Alternatives :

- **Fly.io + Volume** : bon choix technique Docker/volumes, surtout si on veut
  garder la main sur la region et migrer ensuite vers Postgres. Un peu plus
  d'ops que Render.
- **Railway + Volume** : rapide pour prototypes, volumes et bases managees
  disponibles, mais a valider avec un vrai test de persistance avant beta.
- **VPS Docker Compose** : controle maximum, mais il faut gerer TLS, backups,
  firewall, updates systeme et monitoring soi-meme.

### Deploiement Render

Le fichier `render.yaml` decrit le service beta Docker :

- service web Docker `thermal-saas-beta` ;
- region `frankfurt` ;
- healthcheck HTTP `/health` ;
- disque persistant `thermal-saas-storage` monte sur `/app/storage` ;
- base SQLite `/app/storage/thermal_saas.sqlite` ;
- Chromium `/usr/bin/chromium` pour l'export PDF.

Variables a renseigner dans Render au premier deploiement :

- `THERMAL_SAAS_SECRET_KEY` : secret long aleatoire, obligatoire ;
- `THERMAL_SAAS_CORS_ORIGINS` : domaine beta public, par exemple
  `https://thermal-saas-beta.onrender.com,https://thermal-beta.example.com` ;
- `THERMAL_SAAS_ALLOWED_HOSTS` : host beta public, par exemple
  `thermal-saas-beta.onrender.com,thermal-beta.example.com`.

L'application ajoute automatiquement `RENDER_EXTERNAL_HOSTNAME` aux hosts
autorises et `RENDER_EXTERNAL_URL` aux origines CORS. Cela permet de valider
l'URL `*.onrender.com` avant de brancher le domaine beta.

### Backups SQLite beta

Le disque Render reste le stockage primaire de la beta, mais il ne doit pas etre
le seul endroit ou les donnees existent. L'API expose donc une route admin :

```bash
curl -X POST https://thermal-saas-beta.onrender.com/admin/backups \
  -H "X-Thermal-Admin-Token: $THERMAL_SAAS_ADMIN_TOKEN"
```

La route execute `init_db()`, cree un snapshot SQLite coherent via l'API backup
SQLite, compresse le fichier en gzip, puis l'envoie vers un stockage objet
S3-compatible en path-style. Elle ne fonctionne que si toutes ces variables sont
configurees :

```bash
THERMAL_SAAS_ADMIN_TOKEN=<secret long aleatoire>
THERMAL_BACKUP_S3_ENDPOINT=https://s3.example.com
THERMAL_BACKUP_S3_REGION=fr-par
THERMAL_BACKUP_S3_BUCKET=thermal-saas-backups
THERMAL_BACKUP_S3_PREFIX=thermal-saas/sqlite
THERMAL_BACKUP_S3_ACCESS_KEY_ID=<access key>
THERMAL_BACKUP_S3_SECRET_ACCESS_KEY=<secret key>
```

Pour la beta, planifier un appel quotidien de cette route depuis un scheduler
externe suffit. Le resultat contient le bucket, la cle objet et la taille du
backup. Verifier aussi dans Render si des snapshots automatiques de Persistent
Disk sont disponibles sur le plan choisi, mais ne pas en faire le seul backup.

Validation post-deploiement :

```bash
python3 scripts/smoke_beta.py \
  --base-url https://thermal-saas-beta.onrender.com \
  --admin-token "$THERMAL_SAAS_ADMIN_TOKEN"
```

Le script teste `/health`, `/app`, inscription, cookie/session, lookup
organisation, creation projet, sauvegarde questionnaire, simulation, rapport
HTML, export PDF et, si `--admin-token` est fourni, backup objet. Pour verifier
la persistance apres redemarrage Render, relancer le script avec les memes
`--email`, `--password` et `--organization` : le lookup organisation doit
toujours repondre `exists=true`.

### SQLite ou PostgreSQL

Decision beta : **SQLite persistant temporaire**.

Pourquoi :

- le storage applicatif utilise encore `sqlite3` ;
- Alembic est maintenant en place, ce qui prepare la suite ;
- pour une beta fermee mono-instance, SQLite avec volume persistant suffit si on
  ajoute un backup regulier du fichier `/app/storage/thermal_saas.sqlite`.

Limites assumeees :

- pas de scaling horizontal ;
- ecritures concurrentes limitees ;
- backups a mettre en place explicitement ;
- migration PostgreSQL necessite de remplacer la couche `sqlite3` par SQLAlchemy
  ou un repository compatible PostgreSQL.

### Domaine de test

Proposition :

```text
thermal-beta.<domaine-principal>
```

Exemple de configuration :

```bash
THERMAL_SAAS_CORS_ORIGINS=https://thermal-beta.example.com
THERMAL_SAAS_ALLOWED_HOSTS=thermal-beta.example.com
```

Sur Render, pointer le sous-domaine vers le service via la configuration DNS
fournie, puis laisser Render provisionner le TLS.

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
