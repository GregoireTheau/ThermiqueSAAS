# US model validation benchmark

Status: first automated baseline completed on 2026-08-04 with engine
`1r1c-mvp-0.2`. This benchmark diagnoses internal consistency and sensitivity;
it does not by itself validate accuracy against real homes.

## Scope

The matrix in `data/validation/us_roof_validation_matrix.json` contains:

- 10 understandable residential archetypes in Atlanta, Miami, Houston, Phoenix,
  Chicago, Denver, Seattle, and Minneapolis;
- 23 one-at-a-time variants around the Atlanta 1970s ranch;
- detached houses and top-floor apartments;
- several vintages, roof assemblies, R-values, heating systems, duct locations,
  infiltration categories, windows, and setpoints.

Every run uses the production `roof_insulation_seller` flow: ZIP resolution,
local weather, questionnaire mapping, dwelling generation, before/after
simulation, HVAC conversion, and report metrics. It does not use a separate
validation-only thermal engine.

The comparison tariff is deliberately fixed at `$0.18/kWh`, `$1.50/therm`, and
`$2.50/gallon propane`. It isolates physical differences between cases and must
not be interpreted as a local utility tariff.

## Run it

Historical weather baseline:

```bash
python scripts/run_model_validation.py \
  --weather-type historical \
  --weather-year 2023 \
  --output-dir outputs/model_validation/historical_2023
```

Pinned typical meteorological year, with NSRDB credentials configured:

```bash
python scripts/run_model_validation.py \
  --weather-type typical \
  --tmy-name tmy-2024 \
  --output-dir outputs/model_validation/tmy_2024
```

Quick smoke test:

```bash
python scripts/run_model_validation.py \
  --case atlanta_1970_ranch \
  --limit 1 \
  --output-dir outputs/model_validation/smoke
```

Generated files:

- `metrics.csv`: annual energy, cost, capacity, comfort, load-curve, and balance KPIs;
- `monthly.csv`: monthly heating load, outdoor mean temperature, and peak;
- `sensitivities.csv`: change from the reference case for each parameter value;
- `checks.json`: physical invariants and execution failures;
- `summary.json`: complete machine-readable manifest and results;
- `summary.html`: compact side-by-side review for humans.

Hourly arrays are intentionally not persisted. Each result records the matrix
hash, engine version, weather reference, model, timezone, and weather hash.

## Automated checks

Each run checks:

- non-negative energy and cost totals;
- hourly 1R1C energy-balance closure;
- roof insulation does not increase annual heating demand;
- the total power delivered by a central system never exceeds its declared capacity.

The matrix also checks expected monotonic behavior for roof R-value,
airtightness, ventilation, wall insulation, duct losses, heating setpoint,
window type, and heating-system independence of thermal demand.

Quality flags are not failed invariants. They identify results that require a
different interpretation:

- `low_heating_demand_percentage_unstable`: a large percentage is based on a
  very small absolute heating demand;
- `*_heating_capacity_limited`: the system cannot maintain the requested setpoint,
  so consumption alone understates the building load.

## Historical 2023 baseline

All 33 runs completed, with 140/140 checks passing and no execution error.

| Canonical case | Heat before kWh | Heat after kWh | Reduction | Cost saved | Peak kW | Unmet heating degree-hours |
|---|---:|---:|---:|---:|---:|---:|
| Atlanta 1970s detached ranch | 7,228 | 4,791 | 33.7% | $168 | 7.6 | 0 |
| Atlanta 2000s detached ranch | 2,931 | 2,483 | 15.3% | $17 | 5.2 | 0 |
| Atlanta 1980s top-floor apartment | 2,121 | 1,701 | 19.8% | $64 | 3.5 | 0 |
| Miami 1980s compact flat-roof home | 8 | 0 | 100.0% | $1 | 2.0 | 0 |
| Houston 1990s detached ranch | 2,014 | 1,473 | 26.9% | $57 | 5.3 | 0 |
| Phoenix 1980s cathedral-ceiling home | 1,610 | 1,065 | 33.8% | $60 | 5.1 | 0 |
| Chicago pre-1940 top-floor apartment | 30,277 | 25,702 | 15.1% | $293 | 8.4 | 4,037 |
| Denver modern high-performance ranch | 4,395 | 3,655 | 16.8% | $34 | 7.0 | 0 |
| Seattle 1950s detached ranch | 17,417 | 12,838 | 26.3% | $824 | 7.6 | 0 |
| Minneapolis 1960s detached ranch | 31,239 | 24,585 | 21.3% | $473 | 13.2 | 531 |

The Miami percentage is not decision-grade because the absolute heating load is
negligible. Chicago and Minneapolis are capacity-limited stress cases and must
not be used to calibrate annual consumption until equipment sizing is resolved.

## First sensitivity diagnosis

For the Atlanta 1970s anchor, the span in baseline heating demand across tested
values was:

| Parameter | Heating-demand span |
|---|---:|
| Heating setpoint | 71.8% |
| Existing roof R-value | 53.9% |
| Window type | 36.3% |
| Ventilation category | 34.1% |
| Roof assembly | 21.0% |
| Airtightness category | 13.1% |
| Wall-insulation category | 11.4% |
| Duct location | 0% thermal demand; changes final energy/cost |
| Heating system | 0% thermal demand; changes final energy/cost |

This ranking is local to one archetype and the tested ranges. It is not a global
Sobol analysis. It nevertheless shows that setpoint, effective R-value,
ventilation/infiltration, windows, and roof assembly require better observations
before tuning low-influence coefficients.

## Defect found and corrected

The first baseline showed that a central system's full `max_power_w` was applied
independently to every served room. Engine `1r1c-mvp-0.2` allocates that total
capacity across rooms in proportion to floor area. This conserves central-system
capacity and exposes genuine unmet-load hours instead of hiding them with
duplicated capacity.

## What this does not prove

Plausible results and monotonic behavior are necessary but not sufficient. The
next validation layer is a matched comparison against EnergyPlus/OpenStudio-HPXML
or BEopt, followed by measured pilot homes. ResStock can validate distributions
and orders of magnitude, but it is simulated stock data rather than ground truth
for a specific address.

Primary references:

- [DOE building simulation test procedures / ASHRAE Standard 140](https://www.energy.gov/cmei/buildings/articles/test-procedures-building-energy-simulation-tools)
- [DOE EnergyPlus](https://www.energy.gov/cmei/buildings/articles/energyplus)
- [NLR BEopt](https://www.nrel.gov/buildings/beopt.html)
- [NLR ResStock](https://www.nrel.gov/buildings/resstock)
- [DOE FEMP M&V Guidelines](https://www.energy.gov/sites/default/files/2016/01/f28/mv_guide_4_0.pdf)

