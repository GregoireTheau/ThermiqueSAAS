# ThermalTwin

ThermalTwin is a small SaaS prototype for roof-insulation sales teams. It turns a short building questionnaire into a before/after thermal simulation and a commercial report that can be attached to a quote.

The product is intentionally positioned as a sales-support tool. It is not an EPC, not a regulatory audit, and not a substitute for an on-site engineering assessment. Its goal is to make the thermal impact of roof insulation easier to explain to a homeowner, with transparent assumptions and repeatable calculations.

## What It Does

- Creates beta SaaS accounts with authentication, organizations, projects, saved answers, simulations, and report history.
- Guides the user through a roof-insulation questionnaire: home type, heating system, heating setpoint, existing wall and roof insulation, roof/attic type, roof color, ventilation, airtightness, and rooms under the roof.
- Runs before/after simulations for roof insulation, with the annual real-weather report as the primary commercial output.
- Resolves US ZIP codes or optional street addresses to coordinates and an IANA timezone, without a default fallback location.
- Resolves the 2021 IECC / ASHRAE 169-2013 building-code climate zone from the Census county FIPS; this metadata never selects or adjusts local weather.
- Uses a pinned NSRDB typical meteorological year for the primary annual estimate, or an explicitly selected Open-Meteo historical year.
- Estimates annual heating demand reduction, final heating energy impact, cost savings, and supporting comfort indicators.
- Generates HTML reports and server-side PDF exports.
- Keeps multiple business profiles in the codebase, while the current visible product focus is roof insulation.

## Product Focus

The current commercial vertical is roof insulation.

The intended user is an installer, craft business, or insulation salesperson who wants to quickly produce a credible estimate before sending a quote.

The core promise is:

> Generate a clear before/after thermal estimate for roof insulation, using a complete real-weather year, and produce a customer-facing report.

The report emphasizes annual heating demand because this is the main decision metric for roof insulation. Summer effects can still be simulated by the model, but they are secondary for this vertical.

## Main Features

### SaaS Workflow

- Email/password authentication with HttpOnly session cookies.
- Organization-level business profile selection.
- Project creation and saved customer answers.
- Simulation history per project.
- HTML and PDF report access.
- Admin route and script for creating beta customer accounts.
- Organization branding fields for report customization.

### Thermal Model

The model is deliberately lightweight and explainable:

- room-by-room 1R1C inertia model;
- transmission and ventilation heat exchanges;
- internal gains;
- simplified solar gains by orientation;
- shutters and solar protection factors;
- opaque-surface albedo;
- thermal coupling between rooms;
- heating and cooling systems with efficiency or COP;
- annual simulations from Open-Meteo weather files.

This is enough for comparative sales estimates while staying transparent about assumptions and limitations.

### Reports

The report layer builds a customer-facing narrative from the simulation output:

- commercial executive summary;
- tested change and assumptions;
- before/after KPIs;
- annual real-weather context;
- room-level details;
- charts for temperature profiles;
- explicit non-regulatory disclaimer;
- PDF export through headless Chrome or Chromium.

## Architecture

```text
thermal_saas/
  api.py                 FastAPI application and SaaS endpoints
  business_flow.py       Questionnaire-to-simulation mapping
  business_profiles.py   Business profile loading
  storage.py             SQLite persistence, auth, projects, sessions
  static/                Browser UI

thermal_model/
  simulation.py          1R1C hourly simulation engine
  comparison.py          Before/after comparison layer
  reporting.py           Report model and HTML rendering
  weather.py             Open-Meteo ingestion and weather conversion
  *_loader.py            JSON loaders and validation

business_profiles/      Product-specific questionnaires and defaults
data/reference/         Thermal reference assumptions
data/examples/          Example dwellings and scenarios
schemas/                JSON schemas
scripts/                CLI tools for simulation, reports, beta users
tests/                  Unit and integration tests
migrations/             Alembic migrations for the SaaS SQLite database
```

## Tech Stack

- Python
- FastAPI
- SQLite
- Alembic
- Vanilla JavaScript, HTML, and CSS
- Pytest
- Open-Meteo weather data
- Headless Chrome/Chromium for PDF export
- Docker for deployment

## Local Setup

Create an environment and install dependencies:

```bash
pip install -r requirements.txt
```

Run the targeted test suite:

```bash
python -m pytest tests/test_weather.py tests/test_loaders.py tests/test_business_profiles_flow.py tests/test_saas_api.py tests/test_reporting.py
```

Run the app locally:

```bash
THERMAL_SAAS_ENV=development \
THERMAL_SAAS_SECRET_KEY=local-development-secret-at-least-32-chars \
THERMAL_SAAS_DB_PATH=outputs/local_dev.sqlite \
python -m uvicorn thermal_saas.api:app --host 127.0.0.1 --port 8808
```

Then open:

```text
http://127.0.0.1:8808/app
```

## Useful Commands

Run a static-loss calculation:

```bash
python scripts/compute_static_losses.py
```

Run an hourly 1R1C simulation:

```bash
python scripts/simulate_1r1c.py
```

Compare two scenarios:

```bash
python scripts/compare_scenarios.py
```

Generate report fixtures:

```bash
python scripts/generate_report_fixtures.py
```

Run the US model-validation matrix:

```bash
python scripts/run_model_validation.py \
  --weather-type historical \
  --weather-year 2023 \
  --output-dir outputs/model_validation/historical_2023
```

The protocol, KPI definitions, first baseline, and interpretation rules are in
[docs/ModelValidationBenchmark.md](docs/ModelValidationBenchmark.md).

Create a beta user through the admin API:

```bash
THERMAL_SAAS_ADMIN_TOKEN=<admin-token> \
python scripts/create_beta_user.py \
  --email customer@example.com \
  --password temporary-password \
  --org "Customer Organization"
```

## Configuration

The most important environment variables are:

```text
THERMAL_SAAS_ENV
THERMAL_SAAS_SECRET_KEY
THERMAL_SAAS_DB_PATH
THERMAL_SAAS_CORS_ORIGINS
THERMAL_SAAS_ALLOWED_HOSTS
THERMAL_SAAS_ADMIN_TOKEN
THERMAL_PDF_BROWSER_PATH
THERMAL_WEATHER_DIR
THERMAL_LOCATION_CACHE_DIR
THERMAL_NSRDB_API_KEY
THERMAL_NSRDB_EMAIL
```

Set `THERMAL_WEATHER_DIR=/app/storage/weather` and
`THERMAL_LOCATION_CACHE_DIR=/app/storage/location-cache` on Railway so downloaded
weather and geocoding results survive deployments. NSRDB typical weather also
requires a National Laboratory of the Rockies developer API key and contact email.

For object-storage backups:

```text
THERMAL_BACKUP_S3_ENDPOINT
THERMAL_BACKUP_S3_REGION
THERMAL_BACKUP_S3_BUCKET
THERMAL_BACKUP_S3_PREFIX
THERMAL_BACKUP_S3_ACCESS_KEY_ID
THERMAL_BACKUP_S3_SECRET_ACCESS_KEY
```

### Automated Railway backups

Keep the S3 credentials on the web service and create a separate Railway cron
service from the same repository. Configure it with:

```text
Start Command: python scripts/run_scheduled_backup.py
Cron Schedule: 0 3 * * *
THERMAL_BACKUP_TRIGGER_URL=https://${{thermal-saas-beta.RAILWAY_PUBLIC_DOMAIN}}/admin/backups
THERMAL_SAAS_ADMIN_TOKEN=${{thermal-saas-beta.THERMAL_SAAS_ADMIN_TOKEN}}
```

Railway cron schedules use UTC. The process exits non-zero when the endpoint or
upload fails, so the failed execution remains visible in Railway. Configure an
object lifecycle rule on the S3 provider to delete backups after the chosen
retention period; 30 days is appropriate for the private beta.

The manual backup, R2 retention, restore-verification procedure, and latest test
record are documented in [docs/BackupRestore.md](docs/BackupRestore.md).

See `.env.example` for placeholders. Real secrets, local `.env` files, generated SQLite databases, weather caches, and outputs are intentionally ignored by Git.

## Deployment Notes

The beta is deployed on Railway from the repository Dockerfile. Attach a persistent volume at `/app/storage` and set `THERMAL_SAAS_DB_PATH=/app/storage/thermal_saas.sqlite`. On startup and on `/health`, the app initializes the database and applies Alembic migrations.

Set `THERMAL_SAAS_ALLOWED_HOSTS` to the Railway public hostname and `THERMAL_SAAS_CORS_ORIGINS` to its full HTTPS URL. Production does not infer these values from a hosting provider.

PDF export requires Chrome or Chromium. Set `THERMAL_PDF_BROWSER_PATH` if the binary is not available in the default system path.

The current database choice is deliberate: SQLite is simple enough for a closed beta or portfolio prototype. A production multi-tenant deployment with heavier traffic would likely move the storage layer to PostgreSQL.

## Current Limitations

- The model is comparative and simplified; it is not a regulatory calculation.
- Weather is resolved from US ZIP/address coordinates and shared by 0.1° geographic cell
  (and timezone), while the dwelling keeps its actual resolved coordinates.
- Typical weather depends on the configured NSRDB API credentials; historical weather uses Open-Meteo.
- Some retrofit assumptions are fixed or profile-driven rather than fully configurable.
- The annual roof-insulation report is the main product output; other profiles remain available in code but are not the current commercial focus.

## Why This Project Exists

ThermalTwin was built to explore a practical gap between complex thermal engineering tools and everyday sales workflows.

The interesting engineering problem is not only the simulation itself. It is the full product loop:

- collect enough building data without overwhelming the user;
- map questionnaire answers into a valid thermal model;
- run reproducible before/after simulations;
- explain the result in business language;
- persist the workflow in a SaaS application;
- keep assumptions visible and limitations explicit.

That makes the project a compact example of product engineering across backend, frontend, data modeling, simulation, reporting, testing, and deployment.
