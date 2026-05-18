"""Report model builder for ThermalTwin scenario comparisons."""

from __future__ import annotations

from html import escape
from typing import Any


def build_report_model(comparison: dict[str, Any]) -> dict[str, Any]:
    """Build a compact, client-facing report model from a comparison payload."""
    before_totals = comparison["before"]["totals"]
    after_totals = comparison["after"]["totals"]
    deltas = comparison["deltas"]
    headline = comparison["summary"]["headline_metrics"]
    driver = comparison["summary"]["main_gain_driver"]
    experiment = comparison.get("experiment", _legacy_experiment_context(comparison))
    season = _infer_season(experiment)
    title = _build_report_title(experiment, season)
    context_text = _build_context_text(experiment, season)
    scope_notice = (
        f"Ces resultats portent uniquement sur une simulation de "
        f"{experiment['duration_days']:.2f} jours."
    )
    annual_projection_notice = (
        "Aucune projection annuelle n'est calculee dans ce rapport; les valeurs "
        "presentees sont les resultats simules sur la periode de l'experience."
    )
    rooms = [
        _build_room_report(room_id, room_delta)
        for room_id, room_delta in deltas["rooms"].items()
    ]
    most_impacted_room = max(
        rooms,
        key=lambda room: (
            max(0.0, room["comfort"]["hot_degree_hours"]["delta"])
            + max(0.0, room["comfort"]["cold_degree_hours"]["delta"])
            + max(0.0, room["comfort"]["max_temperature_c"]["delta"]) * 24.0
        ),
    )

    return {
        "report_schema_version": "0.1",
        "source": {
            "comparison_schema_version": comparison["comparison_schema_version"],
            "dwelling_id": comparison["dwelling_id"],
            "before_scenario_id": comparison["before_scenario_id"],
            "after_scenario_id": comparison["after_scenario_id"],
        },
        "experiment": {
            "title": title,
            "season": season,
            "adaptation_id": experiment.get("adaptation_id", "unknown"),
            "adaptation_label": experiment.get("adaptation_label", ""),
            "role": experiment.get("role", "primary"),
            "label": experiment.get("label", ""),
            "weather_variant": experiment.get("weather_variant", ""),
            "reason": experiment.get("reason", ""),
            "context_text": context_text,
            "scope_notice": scope_notice,
            "annual_projection_notice": annual_projection_notice,
            "before_description": experiment["before_description"],
            "after_description": experiment["after_description"],
            "duration_hours": round(experiment["duration_hours"], 2),
            "duration_days": round(experiment["duration_days"], 2),
            "timestep_h": experiment["timestep_h"],
            "weather_source": experiment["weather_source"],
            "weather_summary": {
                "outdoor_temperature_min_c": round(
                    experiment["weather_summary"]["outdoor_temperature_min_c"],
                    2,
                ),
                "outdoor_temperature_max_c": round(
                    experiment["weather_summary"]["outdoor_temperature_max_c"],
                    2,
                ),
            },
            "setpoints": experiment["setpoints"],
            "intervention": experiment["intervention"],
        },
        "sign_convention": (
            "delta = avant - apres; une valeur positive signifie une reduction "
            "apres intervention"
        ),
        "headline": {
            "electricity": _metric(
                before_totals["electricity_kwh"],
                after_totals["electricity_kwh"],
                deltas["electricity_kwh"],
                "kWh",
            ),
            "cost": _metric(
                before_totals["electricity_cost_eur"],
                after_totals["electricity_cost_eur"],
                deltas["electricity_cost_eur"],
                "EUR",
            ),
            "co2": _metric(
                before_totals["electricity_co2_kg"],
                after_totals["electricity_co2_kg"],
                deltas["electricity_co2_kg"],
                "kgCO2",
            ),
            "max_temperature_reduction_c": round(
                headline["max_temperature_reduction_c"],
                2,
            ),
            "hot_degree_hours_reduced": round(
                headline["hot_degree_hours_reduced"],
                2,
            ),
            "cold_degree_hours_reduced": round(
                headline["cold_degree_hours_reduced"],
                2,
            ),
        },
        "main_gain_driver": {
            "key": driver["key"],
            "label": driver["label"],
            "value": round(driver["value"], 2),
            "unit": driver["unit"],
            "definition": (
                "Indicateur heuristique: poste du bilan simule qui contribue le "
                "plus au gain calcule, sans constituer une preuve causale mesuree."
            ),
        },
        "comfort": {
            "most_impacted_room_id": most_impacted_room["room_id"],
            "most_impacted_room_name": most_impacted_room["room_name"],
            "definition": (
                "Les degres-heures cumulent les heures passees au-dela de la "
                "consigne de confort, ponderees par l'ecart de temperature."
            ),
        },
        "energy_breakdown": {
            "heating_thermal": _metric(
                before_totals["heating_thermal_kwh"],
                after_totals["heating_thermal_kwh"],
                deltas["heating_thermal_kwh"],
                "kWh_th",
            ),
            "heating_electric": _metric(
                before_totals["heating_electric_kwh"],
                after_totals["heating_electric_kwh"],
                deltas["heating_electric_kwh"],
                "kWh",
            ),
            "cooling_thermal": _metric(
                before_totals["cooling_thermal_kwh"],
                after_totals["cooling_thermal_kwh"],
                deltas["cooling_thermal_kwh"],
                "kWh_th",
            ),
            "cooling_electric": _metric(
                before_totals["cooling_electric_kwh"],
                after_totals["cooling_electric_kwh"],
                deltas["cooling_electric_kwh"],
                "kWh",
            ),
        },
        "rooms": rooms,
        "methodology": {
            "model": "Simulation thermique horaire 1R1C piece par piece",
            "reported_values": (
                "Calculees depuis les simulations avant/apres; aucune performance "
                "mesuree n'est inferee."
            ),
            "limits": [
                "Modele MVP, pas un audit energetique reglementaire.",
                (
                    "Resultats dependants de la geometrie saisie, de la meteo, "
                    "des consignes, des hypotheses d'equipement et des valeurs "
                    "de reference."
                ),
                (
                    "Les traces horaires restent dans le JSON de comparaison et "
                    "sont volontairement exclues de ce modele de rapport."
                ),
            ],
        },
    }


def render_report_html(report: dict[str, Any]) -> str:
    """Render a report model as a standalone HTML document."""
    source = report["source"]
    experiment = report["experiment"]
    headline = report["headline"]
    energy = report["energy_breakdown"]
    rooms_html = "\n".join(_render_room_html(room) for room in report["rooms"])
    limits_html = "\n".join(
        f"<li>{escape(limit)}</li>"
        for limit in report["methodology"]["limits"]
    )

    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rapport thermique - {escape(source["dwelling_id"])}</title>
  <style>
    :root {{
      color-scheme: light;
      --text: #18202a;
      --muted: #5f6b7a;
      --line: #d8dee7;
      --surface: #f6f8fb;
      --accent: #0f766e;
      --warn: #b45309;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--text);
      background: #ffffff;
      line-height: 1.45;
    }}
    main {{
      max-width: 1040px;
      margin: 0 auto;
      padding: 40px 28px 56px;
    }}
    header {{
      border-bottom: 2px solid var(--line);
      padding-bottom: 22px;
      margin-bottom: 28px;
    }}
    h1, h2, h3 {{ margin: 0; line-height: 1.15; }}
    h1 {{ font-size: 30px; }}
    h2 {{ font-size: 20px; margin-top: 34px; margin-bottom: 14px; }}
    h3 {{ font-size: 16px; margin-bottom: 10px; }}
    p {{ margin: 8px 0; }}
    .meta {{ color: var(--muted); margin-top: 10px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: var(--surface);
    }}
    .metric-label {{
      color: var(--muted);
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    .metric-value {{
      font-size: 24px;
      font-weight: 700;
      margin-top: 6px;
    }}
    .reduction {{ color: var(--accent); }}
    .increase {{ color: var(--warn); }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 12px 0 22px;
      font-size: 14px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 9px 8px;
      text-align: right;
      vertical-align: top;
    }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ color: var(--muted); font-weight: 700; background: #fbfcfe; }}
    section {{ margin-top: 26px; }}
    .note {{
      border-left: 4px solid var(--accent);
      padding: 10px 14px;
      background: var(--surface);
      color: var(--muted);
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      background: var(--surface);
      margin: 14px 0;
    }}
    .panel strong {{ display: block; margin-bottom: 6px; }}
    .room {{
      margin-top: 22px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
    }}
    ul {{ padding-left: 20px; }}
    @media (max-width: 760px) {{
      main {{ padding: 26px 16px 42px; }}
      .grid {{ grid-template-columns: 1fr; }}
      table {{ font-size: 13px; }}
      th, td {{ padding: 8px 5px; }}
    }}
    @media print {{
      main {{ max-width: none; padding: 20mm 16mm; }}
      .metric {{ break-inside: avoid; }}
      .room {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{escape(experiment["title"])}</h1>
      <p class="meta">Logement {escape(source["dwelling_id"])} - scenario avant {escape(source["before_scenario_id"])} - scenario apres {escape(source["after_scenario_id"])}</p>
    </header>

    <section>
      <h2>Resultat principal</h2>
      <div class="grid">
        {_render_headline_metric("Electricite", headline["electricity"])}
        {_render_headline_metric("Cout", headline["cost"])}
        {_render_headline_metric("CO2", headline["co2"])}
      </div>
      <p class="note">{escape(experiment["scope_notice"])} {escape(experiment["annual_projection_notice"])}</p>
    </section>

    <section>
      <h2>Ce qui a ete compare</h2>
      <div class="panel">
        <strong>Contexte</strong>
        <p>{escape(experiment["context_text"])}</p>
      </div>
      <div class="panel">
        <strong>Role de l'experience</strong>
        <p>{escape(_format_experiment_role(experiment))}</p>
      </div>
      <div class="panel">
        <strong>Modification testee</strong>
        <p>{escape(_format_intervention(experiment["intervention"]))}</p>
      </div>
    </section>

    <section>
      <h2>Lecture des resultats</h2>
      <p>La piece la plus impactee est {escape(report["comfort"]["most_impacted_room_name"])}.</p>
      <p>La baisse maximale de temperature simulee est de {headline["max_temperature_reduction_c"]:.2f} C. Les degres-heures chauds evites sont de {headline["hot_degree_hours_reduced"]:.2f} C.h et les degres-heures froids evites sont de {headline["cold_degree_hours_reduced"]:.2f} C.h.</p>
      <p>Le principal poste explicatif identifie par le modele est : {escape(report["main_gain_driver"]["label"])} ({report["main_gain_driver"]["value"]:.2f} {escape(report["main_gain_driver"]["unit"])}).</p>
      <p class="note">{escape(report["main_gain_driver"]["definition"])}</p>
      <p class="note">{escape(report["sign_convention"])}</p>
      <p class="note">{escape(report["comfort"]["definition"])}</p>
    </section>

    <section>
      <h2>Limites de la simulation</h2>
      <p>{escape(report["methodology"]["model"])}</p>
      <p>{escape(report["methodology"]["reported_values"])}</p>
      <p>{escape(experiment["annual_projection_notice"])}</p>
      <ul>
        {limits_html}
      </ul>
    </section>

    <section>
      <h2>Tableaux techniques - energie</h2>
      {_render_metric_table([
          ("Chauffage thermique", energy["heating_thermal"]),
          ("Chauffage electrique", energy["heating_electric"]),
          ("Climatisation thermique", energy["cooling_thermal"]),
          ("Climatisation electrique", energy["cooling_electric"]),
      ])}
    </section>

    <section>
      <h2>Tableaux techniques - detail par piece</h2>
      {rooms_html}
    </section>
  </main>
</body>
</html>
"""


def _build_room_report(room_id: str, room_delta: dict[str, Any]) -> dict[str, Any]:
    return {
        "room_id": room_id,
        "room_name": room_delta["room_name"],
        "comfort": {
            "max_temperature_c": _metric(
                room_delta["before_max_temperature_c"],
                room_delta["after_max_temperature_c"],
                room_delta["delta_max_temperature_c"],
                "C",
            ),
            "final_temperature_c": _metric(
                room_delta["before_final_temperature_c"],
                room_delta["after_final_temperature_c"],
                room_delta["delta_final_temperature_c"],
                "C",
            ),
            "hot_degree_hours": _metric(
                room_delta["before_hot_degree_hours"],
                room_delta["after_hot_degree_hours"],
                room_delta["delta_hot_degree_hours"],
                "C.h",
            ),
            "cold_degree_hours": _metric(
                room_delta["before_cold_degree_hours"],
                room_delta["after_cold_degree_hours"],
                room_delta["delta_cold_degree_hours"],
                "C.h",
            ),
        },
        "thermal_balance_deltas": {
            "solar_gain": _delta_metric(room_delta["delta_solar_gain_kwh"], "kWh"),
            "transmission_exchange": _delta_metric(
                room_delta["delta_transmission_exchange_kwh"],
                "kWh",
            ),
            "ventilation_exchange": _delta_metric(
                room_delta["delta_ventilation_exchange_kwh"],
                "kWh",
            ),
            "heating_thermal": _delta_metric(
                room_delta["delta_heating_thermal_kwh"],
                "kWh_th",
            ),
            "cooling_thermal": _delta_metric(
                room_delta["delta_cooling_thermal_kwh"],
                "kWh_th",
            ),
        },
    }


def _metric(before: float, after: float, delta: float, unit: str) -> dict[str, Any]:
    return {
        "before": round(before, 2),
        "after": round(after, 2),
        "delta": round(delta, 2),
        "relative_delta_pct": _relative_delta_pct(before, delta),
        "effect": _effect(delta),
        "unit": unit,
    }


def _delta_metric(delta: float, unit: str) -> dict[str, Any]:
    return {
        "delta": round(delta, 2),
        "effect": _effect(delta),
        "unit": unit,
    }


def _relative_delta_pct(before: float, delta: float) -> float | None:
    if before == 0:
        return None
    return round(delta / before * 100.0, 1)


def _effect(delta: float) -> str:
    if delta > 0:
        return "reduction"
    if delta < 0:
        return "increase"
    return "unchanged"


def _infer_season(experiment: dict[str, Any]) -> str:
    if experiment.get("season") in {"summer", "winter"}:
        return experiment["season"]
    text = " ".join(
        [
            experiment.get("before_description", ""),
            experiment.get("after_description", ""),
            experiment.get("weather_source", ""),
        ],
    ).lower()
    if "winter" in text or "hiver" in text:
        return "winter"
    if "summer" in text or "ete" in text or "canicule" in text or "heatwave" in text:
        return "summer"
    cooling_setpoint = experiment["setpoints"].get("cooling_c", 0.0)
    heating_setpoint = experiment["setpoints"].get("heating_c", 0.0)
    if cooling_setpoint <= 26.0 and heating_setpoint <= 18.0:
        return "summer"
    return "winter"


def _build_report_title(experiment: dict[str, Any], season: str) -> str:
    intervention = _format_intervention_title(experiment["intervention"])
    if experiment.get("label"):
        return f"Simulation {intervention} - {experiment['label'].lower()}"
    season_label = "confort ete" if season == "summer" else "chauffage hiver"
    return f"Simulation {intervention} - {season_label}"


def _format_intervention_title(intervention: dict[str, Any]) -> str:
    if intervention["surface_overrides"]["count"]:
        fields = set(intervention["surface_overrides"]["changed_fields"])
        if "albedo" in fields:
            return "toiture reflechissante"
        if "u_value_w_m2k" in fields:
            return "isolation des parois"
        return "modification des parois"
    if intervention["window_overrides"]["count"]:
        return "amelioration du vitrage"
    if intervention["shutter_overrides"]["count"]:
        return "protections solaires"
    if intervention["system_overrides"]["count"] or intervention["add_systems"]["count"]:
        return "equipement thermique"
    return "scenario avant/apres"


def _build_context_text(experiment: dict[str, Any], season: str) -> str:
    season_label = "ete" if season == "summer" else "hiver"
    weather = experiment["weather_summary"]
    variant = experiment.get("weather_variant") or experiment["weather_source"]
    return (
        f"On simule un cas {season_label} sur {experiment['duration_days']:.2f} "
        f"jours, soit {experiment['duration_hours']:.0f} heures, avec une meteo "
        f"{variant} dont la temperature exterieure varie "
        f"de {weather['outdoor_temperature_min_c']:.2f} C a "
        f"{weather['outdoor_temperature_max_c']:.2f} C. Les consignes retenues "
        f"sont {experiment['setpoints']['heating_c']:.2f} C en chauffage et "
        f"{experiment['setpoints']['cooling_c']:.2f} C en climatisation. "
        f"Le scenario apres applique la modification testee afin de comparer "
        f"les resultats simules avec le scenario avant."
    )


def _format_experiment_role(experiment: dict[str, Any]) -> str:
    role_label = (
        "Experience principale"
        if experiment.get("role") == "primary"
        else "Experience secondaire"
    )
    label = experiment.get("label") or "simulation"
    reason = experiment.get("reason") or "Aucune justification specifique renseignee."
    return f"{role_label}: {label}. {reason}"


def _render_headline_metric(label: str, metric: dict[str, Any]) -> str:
    return (
        f'<div class="metric">'
        f'<div class="metric-label">{escape(label)}</div>'
        f'<div class="metric-value {escape(metric["effect"])}">'
        f'{_format_delta(metric)}</div>'
        f'<p>{_format_before_after(metric)}</p>'
        f'</div>'
    )


def _render_room_html(room: dict[str, Any]) -> str:
    comfort = room["comfort"]
    balance = room["thermal_balance_deltas"]
    return f"""
      <div class="room">
        <h3>{escape(room["room_name"])}</h3>
        {_render_metric_table([
            ("Temperature maximale", comfort["max_temperature_c"]),
            ("Temperature finale", comfort["final_temperature_c"]),
            ("Degres-heures chauds", comfort["hot_degree_hours"]),
            ("Degres-heures froids", comfort["cold_degree_hours"]),
        ])}
        {_render_delta_table([
            ("Apports solaires", balance["solar_gain"]),
            ("Echanges par transmission", balance["transmission_exchange"]),
            ("Echanges par ventilation", balance["ventilation_exchange"]),
            ("Chauffage thermique", balance["heating_thermal"]),
            ("Climatisation thermique", balance["cooling_thermal"]),
        ])}
      </div>
"""


def _render_metric_table(rows: list[tuple[str, dict[str, Any]]]) -> str:
    table_rows = "\n".join(
        "<tr>"
        f"<td>{escape(label)}</td>"
        f"<td>{_format_value(metric['before'], metric['unit'])}</td>"
        f"<td>{_format_value(metric['after'], metric['unit'])}</td>"
        f"<td class=\"{escape(metric['effect'])}\">{_format_delta(metric)}</td>"
        f"<td>{_format_pct(metric)}</td>"
        "</tr>"
        for label, metric in rows
    )
    return f"""
      <table>
        <thead>
          <tr>
            <th>Indicateur</th>
            <th>Avant</th>
            <th>Apres</th>
            <th>Delta</th>
            <th>Variation</th>
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
"""


def _render_delta_table(rows: list[tuple[str, dict[str, Any]]]) -> str:
    table_rows = "\n".join(
        "<tr>"
        f"<td>{escape(label)}</td>"
        f"<td class=\"{escape(metric['effect'])}\">{_format_delta(metric)}</td>"
        "</tr>"
        for label, metric in rows
    )
    return f"""
      <table>
        <thead>
          <tr>
            <th>Delta technique</th>
            <th>Valeur</th>
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
"""


def _format_before_after(metric: dict[str, Any]) -> str:
    return (
        f"Avant {_format_value(metric['before'], metric['unit'])} - "
        f"apres {_format_value(metric['after'], metric['unit'])}"
    )


def _format_delta(metric: dict[str, Any]) -> str:
    return _format_value(metric["delta"], metric["unit"])


def _format_value(value: float, unit: str) -> str:
    return f"{value:.2f} {escape(unit)}"


def _format_pct(metric: dict[str, Any]) -> str:
    value = metric["relative_delta_pct"]
    if value is None:
        return "n/a"
    return f"{value:.1f} %"


def _format_intervention(intervention: dict[str, Any]) -> str:
    parts = []
    labels = {
        "surface_overrides": "parois modifiees",
        "window_overrides": "fenetres modifiees",
        "shutter_overrides": "protections solaires modifiees",
        "system_overrides": "systemes modifies",
        "add_systems": "systemes ajoutes",
    }
    for key, label in labels.items():
        item = intervention[key]
        if item["count"]:
            fields = ", ".join(item["changed_fields"]) or "parametres"
            parts.append(f"{item['count']} {label} ({fields})")
    if not parts:
        return "aucune modification technique appliquee"
    return "; ".join(parts)


def _legacy_experiment_context(comparison: dict[str, Any]) -> dict[str, Any]:
    hourly = comparison["before"]["hourly"]
    duration_hours = len(hourly)
    outdoor_temperatures = [
        hour["outdoor_temperature_c"]
        for hour in hourly
    ]
    return {
        "adaptation_id": "unknown",
        "adaptation_label": "",
        "role": "primary",
        "label": "",
        "season": "",
        "weather_variant": "",
        "reason": "",
        "before_description": "",
        "after_description": "",
        "duration_hours": duration_hours,
        "duration_days": duration_hours / 24.0,
        "timestep_h": 1.0,
        "weather_source": "unknown",
        "weather_summary": {
            "outdoor_temperature_min_c": min(outdoor_temperatures),
            "outdoor_temperature_max_c": max(outdoor_temperatures),
        },
        "setpoints": {"heating_c": 0.0, "cooling_c": 0.0},
        "intervention": {
            "surface_overrides": {"count": 0, "targets": [], "changed_fields": []},
            "window_overrides": {"count": 0, "targets": [], "changed_fields": []},
            "shutter_overrides": {"count": 0, "targets": [], "changed_fields": []},
            "system_overrides": {"count": 0, "targets": [], "changed_fields": []},
            "add_systems": {"count": 0, "targets": [], "changed_fields": []},
        },
    }
