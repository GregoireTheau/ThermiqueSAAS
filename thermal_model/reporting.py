"""Report model builder for ThermalTwin scenario comparisons."""

from __future__ import annotations

from datetime import date
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
    purpose_text = _build_purpose_text(experiment, season)
    tested_change_text = _build_tested_change_text(experiment)
    scenario_type = _scenario_type(experiment)
    rooms = [
        _build_room_report(room_id, room_delta)
        for room_id, room_delta in deltas["rooms"].items()
    ]
    experiment_data = {
        "season": season,
        "scenario_type": scenario_type,
        "total_hot_discomfort_before": sum(
            room["comfort"]["hot_degree_hours"]["before"]
            for room in rooms
        ),
        "total_cold_discomfort_before": sum(
            room["comfort"]["cold_degree_hours"]["before"]
            for room in rooms
        ),
    }
    comfort_mode = get_comfort_mode(experiment_data)
    most_impacted_room = max(
        rooms,
        key=lambda room: (
            max(0.0, room["comfort"]["hot_degree_hours"]["delta"])
            + max(0.0, room["comfort"]["cold_degree_hours"]["delta"])
            + max(0.0, room["comfort"]["max_temperature_c"]["delta"]) * 24.0
        ),
    )

    return {
        "report_schema_version": "0.3",
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
            "scenario_type": scenario_type,
            "adaptation_label": experiment.get("adaptation_label", ""),
            "role": experiment.get("role", "primary"),
            "label": experiment.get("label", ""),
            "weather_variant": experiment.get("weather_variant", ""),
            "simulation_type": experiment.get("simulation_type", ""),
            "weather_mode": experiment.get("weather_mode", ""),
            "requested_city": experiment.get("requested_city", ""),
            "weather_city": experiment.get("weather_city", ""),
            "weather_match_mode": experiment.get("weather_match_mode", ""),
            "weather_year": experiment.get("weather_year"),
            "reason": experiment.get("reason", ""),
            "context_text": context_text,
            "purpose_text": purpose_text,
            "tested_change_text": tested_change_text,
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
        "comfort_mode": comfort_mode,
        "narrative": {
            "context": context_text,
            "purpose": purpose_text,
            "tested_change": tested_change_text,
            "conclusion": _build_conclusion_text(experiment, headline, driver, most_impacted_room),
        },
        "sign_convention": (
            "Delta = avant - après ; une valeur positive signifie une réduction "
            "après intervention."
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
                "Les heures d'inconfort cumulées additionnent les heures passées "
                "au-delà du seuil de confort, pondérées par l'écart de température."
            ),
        },
        "temperature_profiles": _build_temperature_profiles(
            comparison,
            rooms,
            experiment["setpoints"],
            comfort_mode,
        ),
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
        },
    }


def render_report_html(report: dict[str, Any]) -> str:
    """Render a report model as a standalone HTML document."""
    source = report["source"]
    experiment = report["experiment"]
    narrative = report["narrative"]
    headline = report["headline"]
    energy = report["energy_breakdown"]
    generated_date = date.today().strftime("%d/%m/%Y")
    profiles_by_room = {
        profile["room_id"]: profile
        for profile in report["temperature_profiles"]["rooms"]
    }
    comfort_mode = report["comfort_mode"]
    rooms_html = "\n".join(
        _render_room_html(room, profiles_by_room[room["room_id"]], comfort_mode)
        for room in report["rooms"]
    )
    charts_html = "\n".join(
        _render_temperature_profile_html(profile, comfort_mode)
        for profile in report["temperature_profiles"]["rooms"]
    )
    alert_html = _render_temperature_alert(
        report["temperature_profiles"]["rooms"],
        comfort_mode,
    )
    executive_html = _render_executive_summary(report)
    context_params_html = _render_context_params(experiment, report["temperature_profiles"])
    windows_note_html = _render_windows_note(experiment)
    results_sections_html = _render_results_sections(report)

    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rapport thermique - {escape(source["dwelling_id"])}</title>
  <style>
    :root {{
      color-scheme: light;
      --c-bg: #ffffff;
      --c-surface: #f8fafc;
      --c-surface-2: #f1f5f9;
      --c-border: #e2e8f0;
      --c-text: #0f172a;
      --c-muted: #64748b;
      --c-accent: #1d4ed8;
      --c-accent-light: #dbeafe;
      --c-gain: #15803d;
      --c-gain-light: #dcfce7;
      --c-loss: #b91c1c;
      --c-loss-light: #fee2e2;
      --c-neutral: #475569;
      --c-hot-zone: #fef3c7;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--c-text);
      background: var(--c-bg);
      font-size: 13px;
      line-height: 1.5;
    }}
    main {{
      max-width: 1140px;
      margin: 0 auto;
      padding: 34px 30px 42px;
    }}
    .report-header {{
      border-bottom: 1px solid var(--c-border);
      padding-bottom: 16px;
      margin-bottom: 18px;
      page-break-inside: avoid;
    }}
    .header-top {{
      display: grid;
      grid-template-columns: 180px 1fr 220px;
      gap: 20px;
      align-items: center;
    }}
    .logo {{
      width: 126px;
      height: 40px;
      border: 1px solid var(--c-border);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--c-accent);
      font-weight: 700;
      letter-spacing: .04em;
    }}
    h1, h2, h3 {{ margin: 0; line-height: 1.15; }}
    h1 {{
      font-size: 26px;
      text-align: center;
      font-weight: 750;
    }}
    h2 {{
      font-size: 26px;
      margin: 0 0 14px;
      font-weight: 720;
    }}
    h3 {{
      font-size: 20px;
      margin-bottom: 10px;
      font-weight: 700;
    }}
    p {{ margin: 7px 0; }}
    .label {{
      color: var(--c-muted);
      font-size: 11px;
      font-weight: 750;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    .ref-box {{
      text-align: right;
      color: var(--c-muted);
      font-size: 13px;
    }}
    .header-meta {{
      display: grid;
      grid-template-columns: 1fr 1.6fr .7fr;
      gap: 12px;
      margin-top: 16px;
      padding: 12px;
      background: var(--c-surface);
      border: 1px solid var(--c-border);
      border-radius: 8px;
    }}
    section {{
      margin-top: 24px;
      page-break-inside: avoid;
      break-inside: avoid;
    }}
    .print-action {{
      margin-top: 14px;
      text-align: right;
    }}
    .print-action button {{
      border: 1px solid var(--c-accent);
      background: var(--c-accent);
      color: #fff;
      padding: 8px 12px;
      border-radius: 6px;
      font: inherit;
      cursor: pointer;
    }}
    .alert {{
      border-left: 4px solid var(--c-loss);
      background: var(--c-loss-light);
      padding: 12px 14px;
      border-radius: 8px;
      color: var(--c-text);
    }}
    .alert-cold {{
      background: var(--c-accent-light);
      border-left: 4px solid var(--c-accent);
      color: var(--c-text);
    }}
    .info-note {{
      margin-top: 14px;
      border-left: 4px solid var(--c-accent);
      background: var(--c-accent-light);
      padding: 12px 14px;
      border-radius: 8px;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}
    .kpi {{
      border: 1px solid var(--c-border);
      border-radius: 8px;
      padding: 16px;
      background: var(--c-surface);
      min-height: 132px;
    }}
    .kpi-value {{
      font-size: 38px;
      font-weight: 780;
      line-height: 1;
      margin: 9px 0 8px;
      color: var(--c-neutral);
    }}
    .kpi-value.gain, .gain {{ color: var(--c-gain); }}
    .kpi-value.loss, .loss {{ color: var(--c-loss); }}
    .kpi-sub {{
      color: var(--c-muted);
      font-size: 13px;
    }}
    .context-grid {{
      display: grid;
      grid-template-columns: 1.25fr .85fr;
      gap: 18px;
      align-items: start;
    }}
    .context-text {{
      background: var(--c-bg);
      border-left: 4px solid var(--c-accent);
      padding: 4px 0 4px 16px;
      font-size: 15px;
    }}
    .params {{
      border: 1px solid var(--c-border);
      border-radius: 8px;
      overflow: hidden;
    }}
    .params table, .data-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    .params td {{
      border-bottom: 1px solid var(--c-border);
      padding: 9px 10px;
    }}
    .params tr:last-child td {{ border-bottom: 0; }}
    .params td:first-child {{
      color: var(--c-muted);
      width: 38%;
      background: var(--c-surface);
    }}
    .chart-card {{
      border: 1px solid var(--c-border);
      border-radius: 8px;
      padding: 14px 16px 12px;
      margin: 14px 0;
      background: var(--c-bg);
      page-break-inside: avoid;
      break-inside: avoid;
    }}
    .section-title-line {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 9px;
      font-size: 11px;
      font-weight: 750;
      text-transform: uppercase;
      white-space: nowrap;
    }}
    .status-critical {{
      color: var(--c-loss);
      background: var(--c-loss-light);
      border: 1px solid #fecaca;
    }}
    .status-improved {{
      color: var(--c-gain);
      background: var(--c-gain-light);
      border: 1px solid #bbf7d0;
    }}
    .status-stable {{
      color: var(--c-neutral);
      background: var(--c-surface-2);
      border: 1px solid var(--c-border);
    }}
    svg.chart {{
      display: block;
      width: 100%;
      height: auto;
    }}
    .chart-note {{
      color: var(--c-muted);
      font-size: 13px;
      margin-top: 8px;
    }}
    .data-table {{
      margin-top: 8px;
      border: 1px solid var(--c-border);
      border-radius: 8px;
      overflow: hidden;
    }}
    .data-table th, .data-table td {{
      border-bottom: 1px solid var(--c-border);
      padding: 9px 8px;
      text-align: right;
      vertical-align: top;
    }}
    .data-table th:first-child, .data-table td:first-child {{ text-align: left; }}
    .data-table th {{
      color: var(--c-muted);
      font-size: 11px;
      text-transform: uppercase;
      background: var(--c-surface);
      font-weight: 750;
    }}
    .data-table tr:last-child td {{ border-bottom: 0; }}
    .delta-badge {{
      display: inline-block;
      min-width: 54px;
      padding: 3px 7px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 750;
      text-align: center;
    }}
    .delta-badge.gain {{ background: var(--c-gain-light); }}
    .delta-badge.loss {{ background: var(--c-loss-light); }}
    .delta-badge.neutral {{ background: var(--c-surface-2); color: var(--c-neutral); }}
    .room-detail {{
      border-top: 1px solid var(--c-border);
      padding-top: 18px;
      margin-top: 18px;
      page-break-inside: avoid;
      break-inside: avoid;
    }}
    .room-tables {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      align-items: start;
    }}
    .footer {{
      margin-top: 34px;
      padding-top: 16px;
      border-top: 1px solid var(--c-border);
      text-align: center;
      color: var(--c-muted);
      font-size: 11px;
    }}
    @media print {{
      @page {{ margin: 14mm; }}
      main {{ max-width: none; padding: 0; }}
      section, .chart-card, .room-detail, .kpi, .report-header {{
        page-break-inside: avoid;
        break-inside: avoid;
      }}
      .print-action {{ display: none; }}
      body {{ font-size: 12px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header class="report-header">
      <div class="header-top">
        <div class="logo">THERMAL</div>
        <h1>{escape(experiment["title"])}</h1>
        <div class="ref-box">
          <div><strong>Référence</strong></div>
          <div>{escape(source["dwelling_id"])}</div>
          <div>{escape(generated_date)}</div>
        </div>
      </div>
      <div class="header-meta">
        <div><div class="label">Logement</div>{escape(source["dwelling_id"])}</div>
        <div><div class="label">Scénario</div>{escape(_format_scenario_summary(experiment))}</div>
        <div><div class="label">Durée</div>{_format_duration(experiment)}</div>
      </div>
      <div class="print-action"><button type="button" onclick="printReport()">Imprimer / PDF</button></div>
    </header>

    {alert_html}

    <section>
      <h2>Synthèse exécutive</h2>
      {executive_html}
    </section>

    <section>
      <h2>Contexte</h2>
      <div class="context-grid">
        <div class="context-text">
          <p>{escape(narrative["context"])}</p>
          <p>{escape(narrative["purpose"])}</p>
        </div>
        <div class="params">
          {context_params_html}
        </div>
      </div>
      {windows_note_html}
    </section>

    <section>
      <h2>Graphiques de température</h2>
      {charts_html}
    </section>

    <section>
      <h2>Résultats principaux</h2>
      {results_sections_html}
    </section>

    <section>
      <h2>Lecture des résultats</h2>
      <p>{escape(narrative["conclusion"])}</p>
    </section>

    <section>
      <h2>Détail par pièce</h2>
      {rooms_html}
    </section>

    <footer class="footer">Rapport généré automatiquement · Simulation non contractuelle · ThermalTwin</footer>
  </main>
  <script>
    function printReport() {{
      window.print();
    }}
  </script>
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


def _build_temperature_profiles(
    comparison: dict[str, Any],
    rooms: list[dict[str, Any]],
    setpoints: dict[str, float],
    comfort_mode: str,
) -> dict[str, Any]:
    hot_threshold_c = setpoints["cooling_c"]
    cold_threshold_c = setpoints["heating_c"]
    threshold_key = "cold" if comfort_mode in {"cold", "mixed"} else "hot"
    room_names = {room["room_id"]: room["room_name"] for room in rooms}
    before_hourly = comparison["before"]["hourly"]
    after_hourly = comparison["after"]["hourly"]

    return {
        "thresholds": {
            "hot_c": round(hot_threshold_c, 2),
            "cold_c": round(cold_threshold_c, 2),
            "primary": threshold_key,
        },
        "comfort_rule": (
            f"Les zones colorées indiquent les heures au-dessus de "
            f"{hot_threshold_c:.1f} °C, seuil retenu pour compter les heures d'inconfort "
            "chauds."
            if threshold_key == "hot"
            else (
                f"Les zones colorées indiquent les heures sous {cold_threshold_c:.1f} °C, "
                "seuil retenu pour compter les heures d'inconfort froids."
            )
        ),
        "rooms": [
            _build_room_temperature_profile(
                room_id,
                room_name,
                before_hourly,
                after_hourly,
                hot_threshold_c,
                cold_threshold_c,
                threshold_key,
            )
            for room_id, room_name in room_names.items()
        ],
    }


def _build_room_temperature_profile(
    room_id: str,
    room_name: str,
    before_hourly: list[dict[str, Any]],
    after_hourly: list[dict[str, Any]],
    hot_threshold_c: float,
    cold_threshold_c: float,
    primary_discomfort: str,
) -> dict[str, Any]:
    points = []
    for before_hour, after_hour in zip(before_hourly, after_hourly, strict=True):
        before_temperature = before_hour["rooms"][room_id]["temperature_c"]
        after_temperature = after_hour["rooms"][room_id]["temperature_c"]
        points.append(
            {
                "hour": before_hour["hour"],
                "outdoor_temperature_c": round(before_hour["outdoor_temperature_c"], 2),
                "before_temperature_c": round(before_temperature, 2),
                "after_temperature_c": round(after_temperature, 2),
                "before_hot_excess_c": round(max(0.0, before_temperature - hot_threshold_c), 2),
                "after_hot_excess_c": round(max(0.0, after_temperature - hot_threshold_c), 2),
                "before_cold_excess_c": round(max(0.0, cold_threshold_c - before_temperature), 2),
                "after_cold_excess_c": round(max(0.0, cold_threshold_c - after_temperature), 2),
            },
        )

    return {
        "room_id": room_id,
        "room_name": room_name,
        "primary_discomfort": primary_discomfort,
        "points": points,
        "summary": {
            "temp_max_before": round(
                max(point["before_temperature_c"] for point in points),
                2,
            ),
            "temp_max_after": round(
                max(point["after_temperature_c"] for point in points),
                2,
            ),
            "temp_min_before": round(
                min(point["before_temperature_c"] for point in points),
                2,
            ),
            "temp_min_after": round(
                min(point["after_temperature_c"] for point in points),
                2,
            ),
            "before_hot_hours": sum(1 for point in points if point["before_hot_excess_c"] > 0),
            "after_hot_hours": sum(1 for point in points if point["after_hot_excess_c"] > 0),
            "before_hot_degree_hours": round(
                sum(point["before_hot_excess_c"] for point in points),
                2,
            ),
            "after_hot_degree_hours": round(
                sum(point["after_hot_excess_c"] for point in points),
                2,
            ),
            "before_cold_degree_hours": round(
                sum(point["before_cold_excess_c"] for point in points),
                2,
            ),
            "after_cold_degree_hours": round(
                sum(point["after_cold_excess_c"] for point in points),
                2,
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


def _scenario_type(experiment: dict[str, Any]) -> str:
    adaptation_id = experiment.get("adaptation_id", "")
    if adaptation_id == "better_windows":
        return "windows"
    if adaptation_id in {"reflective_roof", "roof_insulation"}:
        return "roof"
    if adaptation_id == "solar_protection":
        return "solar_protection"
    if adaptation_id == "heat_pump":
        return "heat_pump"
    return adaptation_id or "unknown"


def _infer_season(experiment: dict[str, Any]) -> str:
    if experiment.get("season") in {"summer", "winter", "annual"}:
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
    season_label = "confort été" if season == "summer" else "chauffage hiver"
    return f"Simulation {intervention} - {season_label}"


def _format_intervention_title(intervention: dict[str, Any]) -> str:
    if intervention["surface_overrides"]["count"]:
        fields = set(intervention["surface_overrides"]["changed_fields"])
        if "albedo" in fields:
            return "toiture réfléchissante"
        if "u_value_w_m2k" in fields:
            return "isolation des parois"
        return "modification des parois"
    if intervention["window_overrides"]["count"]:
        return "amélioration du vitrage"
    if intervention["shutter_overrides"]["count"]:
        return "protections solaires"
    if intervention["system_overrides"]["count"] or intervention["add_systems"]["count"]:
        return "equipement thermique"
    return "scenario avant/apres"


def _build_context_text(experiment: dict[str, Any], season: str) -> str:
    season_label = "un épisode d'été chaud" if season == "summer" else "une séquence d'hiver froid"
    weather = experiment["weather_summary"]
    variant = experiment.get("weather_variant") or experiment["weather_source"]
    return (
        f"L'expérience reproduit {season_label} pendant "
        f"{_format_number(experiment['duration_days'])} jours ({_format_number(experiment['duration_hours'])} h). "
        f"La météo utilisée ({variant}) fait varier l'extérieur de "
        f"{_format_temperature(weather['outdoor_temperature_min_c'])} à "
        f"{_format_temperature(weather['outdoor_temperature_max_c'])}. Le logement est ensuite "
        f"simulé deux fois, avant puis après intervention, avec les mêmes consignes "
        f"de confort : {_format_temperature(experiment['setpoints']['heating_c'])} en chauffage et "
        f"{_format_temperature(experiment['setpoints']['cooling_c'])} en rafraîchissement."
    )


def _build_purpose_text(experiment: dict[str, Any], season: str) -> str:
    if experiment.get("reason"):
        return experiment["reason"]
    if season == "summer":
        return (
            "Vérifier si la modification réduit les pics de température et le temps "
            "passe au-dessus du seuil de confort."
        )
    return (
        "Vérifier si la modification réduit le besoin de chauffage et le temps "
        "passe sous la consigne de confort."
    )


def _build_tested_change_text(experiment: dict[str, Any]) -> str:
    label = experiment.get("adaptation_label") or _format_intervention_title(
        experiment["intervention"],
    )
    technical_summary = _format_intervention(experiment["intervention"])
    return (
        f"Le scénario après applique : {label}. "
        f"Dans le modèle, cela correspond à {technical_summary}."
    )


def _format_scenario_summary(experiment: dict[str, Any]) -> str:
    period = _scenario_period_label(experiment)
    intervention = _scenario_intervention_label(experiment)
    return f"Simulation thermique {period} avant et après {intervention}."


def _scenario_period_label(experiment: dict[str, Any]) -> str:
    weather_variant = experiment.get("weather_variant", "")
    season = experiment.get("season", "")
    if weather_variant == "summer_long_with_heatwave":
        return "au cours d'un été entier"
    if weather_variant == "summer_heatwave" or season == "summer":
        return "pendant un épisode de canicule"
    if weather_variant == "winter_cold" or season == "winter":
        return "pendant un épisode hivernal froid"
    return "sur la période simulée"


def _scenario_intervention_label(experiment: dict[str, Any]) -> str:
    adaptation_id = experiment.get("adaptation_id", "")
    labels = {
        "reflective_roof": "l'ajout d'une peinture réfléchissante en toiture",
        "roof_insulation": "l'amélioration de l'isolation de la toiture",
        "better_windows": "le remplacement des vitrages",
        "solar_protection": "l'ajout de protections solaires",
        "heat_pump": "l'installation d'une pompe à chaleur",
    }
    return labels.get(adaptation_id, "la modification testée")


def _build_conclusion_text(
    experiment: dict[str, Any],
    headline: dict[str, Any],
    driver: dict[str, Any],
    most_impacted_room: dict[str, Any],
) -> str:
    season = _infer_season(experiment)
    if season == "summer":
        comfort_sentence = (
            f"La piece la plus sensible est {most_impacted_room['room_name']}: "
            f"la température maximale y passe de "
            f"{most_impacted_room['comfort']['max_temperature_c']['before']:.2f} °C à "
            f"{most_impacted_room['comfort']['max_temperature_c']['after']:.2f} °C."
        )
        discomfort_sentence = (
            f"Sur l'ensemble du logement, l'inconfort chaud évité atteint "
            f"{headline['hot_degree_hours_reduced']:.2f} °C·h."
        )
    else:
        comfort_sentence = (
            f"La pièce la plus impactée est {most_impacted_room['room_name']}, "
            "avec le plus fort gain de confort cumulé dans cette séquence froide."
        )
        discomfort_sentence = (
            f"Sur l'ensemble du logement, l'inconfort froid évité atteint "
            f"{headline['cold_degree_hours_reduced']:.2f} °C·h."
        )

    return (
        f"{comfort_sentence} {discomfort_sentence} "
        f"Côté énergie, le delta simulé est de "
        f"{headline['electricity_saved_kwh']:.2f} kWh, soit "
        f"{headline['cost_saved_eur']:.2f} € sur la période. "
        f"Le principal facteur explicatif identifié est : {driver['label']}."
    )


def _format_experiment_role(experiment: dict[str, Any]) -> str:
    role_labels = {
        "primary": "Expérience principale",
        "secondary": "Expérience secondaire",
        "annual": "Expérience annuelle",
    }
    role_label = role_labels.get(experiment.get("role"), "Expérience")
    label = experiment.get("label") or "simulation"
    reason = experiment.get("reason") or "Aucune justification spécifique renseignée."
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


def get_comfort_mode(experiment_data: dict) -> str:
    """
    Détermine le mode de confort dominant de l'expérience.
    "hot"   → épisode chaud, seuil inconfort = 26°C
    "cold"  → épisode froid, seuil inconfort = 18°C
    "mixed" → hybride (ex: fenêtres avec expériences été + hiver)
    """
    season = experiment_data.get("season", "")
    scenario_type = experiment_data.get("scenario_type", "")

    if season in ("summer", "summer_heatwave"):
        return "hot"
    if season in ("winter", "winter_cold"):
        return "cold"
    if scenario_type == "windows":
        return "mixed"

    total_hot = experiment_data.get("total_hot_discomfort_before", 0)
    total_cold = experiment_data.get("total_cold_discomfort_before", 0)
    return "hot" if total_hot >= total_cold else "cold"


def get_room_status(room_data: dict, comfort_mode: str) -> tuple[str, str]:
    """
    Retourne (label, css_class).
    Conserve la logique hot existante, ajoute cold.
    """
    if comfort_mode == "hot":
        temp_max = room_data.get("temp_max_before", 0)
        dh_reduction_pct = room_data.get("hot_dh_reduction_pct", 0)
        if temp_max > 35:
            return ("Critique", "status-critical")
        if dh_reduction_pct > 30:
            return ("Amélioré", "status-improved")
        return ("Stable", "status-stable")

    if comfort_mode in ("cold", "mixed"):
        temp_min = room_data.get("temp_min_before", 99)
        dh_reduction_pct = room_data.get("cold_dh_reduction_pct", 0)
        if temp_min < 16:
            return ("Critique", "status-critical")
        if dh_reduction_pct > 30:
            return ("Amélioré", "status-improved")
        return ("Stable", "status-stable")

    return ("Stable", "status-stable")


def _render_executive_summary(report: dict[str, Any]) -> str:
    headline = report["headline"]
    discomfort = _primary_discomfort_metric(report)
    discomfort_label = (
        "Inconfort chaud cumulé"
        if report["comfort_mode"] == "hot"
        else "Inconfort froid cumulé"
    )
    return f"""
      <div class="summary-grid">
        {_render_kpi("Économie énergie", headline["electricity"])}
        {_render_kpi("Économie coût", headline["cost"])}
        {_render_kpi(discomfort_label, discomfort)}
      </div>
"""


def _render_kpi(label: str, metric: dict[str, Any]) -> str:
    value_class = _value_class(metric["delta"])
    return f"""
        <div class="kpi">
          <div class="label">{escape(label)}</div>
          <div class="kpi-value {value_class}">{_format_delta(metric)}</div>
          <div class="kpi-sub">{_format_before_after(metric)}</div>
          <div class="kpi-sub">{_format_pct(metric)} de variation</div>
        </div>
"""


def _primary_discomfort_metric(report: dict[str, Any]) -> dict[str, Any]:
    primary = report["comfort_mode"]
    summary_key = (
        "hot_degree_hours"
        if primary == "hot"
        else "cold_degree_hours"
    )
    before = sum(
        room["comfort"][summary_key]["before"]
        for room in report["rooms"]
    )
    after = sum(
        room["comfort"][summary_key]["after"]
        for room in report["rooms"]
    )
    return _metric(before, after, before - after, "°C·h")


def _render_temperature_alert(
    profiles: list[dict[str, Any]],
    comfort_mode: str,
) -> str:
    rooms = [_profile_room_data(profile) for profile in profiles]
    return get_alert_banner(rooms, comfort_mode) or ""


def get_alert_banner(rooms: list[dict], comfort_mode: str) -> str | None:
    """
    Retourne le HTML du bandeau d'alerte, ou None si pas d'alerte.
    Conserve la logique chaud existante, ajoute la logique froid.
    """
    if comfort_mode == "hot":
        critical = [room for room in rooms if room.get("temp_max_before", 0) > 35]
        if critical:
            room = critical[0]
            return f"""
    <section class="alert alert-hot">
      <strong>Alerte confort thermique.</strong>
      La pièce <strong>{escape(room['name'])}</strong> dépasse 35 °C dans la simulation, avec un maximum à {_format_temperature(room['temp_max_before'])}.
    </section>
"""

    elif comfort_mode in ("cold", "mixed"):
        critical = [room for room in rooms if room.get("temp_min_before", 99) < 16]
        if critical:
            room = critical[0]
            return f"""
    <section class="alert alert-cold">
      <strong>Alerte confort thermique.</strong>
      La pièce <strong>{escape(room['name'])}</strong> descend sous 16 °C dans la simulation, avec un minimum à {_format_temperature(room['temp_min_before'])}.
    </section>
"""

    return None


def _render_context_params(
    experiment: dict[str, Any],
    temperature_profiles: dict[str, Any],
) -> str:
    weather = experiment["weather_summary"]
    thresholds = temperature_profiles["thresholds"]
    rows = [
        ("Durée", _format_duration(experiment)),
        (
            "Météo",
            (
                f"{escape(experiment['weather_source'])}, "
                f"{_format_temperature(weather['outdoor_temperature_min_c'])} → "
                f"{_format_temperature(weather['outdoor_temperature_max_c'])}"
            ),
        ),
        (
            "Consignes",
            (
                f"Chauffage {_format_temperature(experiment['setpoints']['heating_c'])}, "
                f"rafraîchissement {_format_temperature(experiment['setpoints']['cooling_c'])}"
            ),
        ),
        (
            "Seuil inconfort",
            (
                f"Chaud {_format_temperature(thresholds['hot_c'])}, "
                f"froid {_format_temperature(thresholds['cold_c'])}"
            ),
        ),
        ("Modification testée", escape(experiment["tested_change_text"])),
    ]
    table_rows = "\n".join(
        f"<tr><td>{escape(label)}</td><td>{value}</td></tr>"
        for label, value in rows
    )
    return f"<table>{table_rows}</table>"


def _render_windows_note(experiment: dict[str, Any]) -> str:
    if experiment.get("scenario_type") != "windows":
        return ""
    return """
      <div class="info-note">
        Ce rapport présente deux simulations distinctes pour ce scénario :
        une en conditions estivales (apports solaires) et une en conditions
        hivernales (pertes par transmission). Les résultats sont à lire
        conjointement pour évaluer l'impact annuel du vitrage.
      </div>
"""


def _render_results_sections(report: dict[str, Any]) -> str:
    comfort_table_html = _render_comfort_result_table(report)
    energy_table_html = _render_energy_result_table(report)
    if report["comfort_mode"] == "hot":
        sections = [comfort_table_html, energy_table_html]
    else:
        sections = [energy_table_html, comfort_table_html]
    return "\n".join(sections)


def _render_energy_result_table(report: dict[str, Any]) -> str:
    energy = report["energy_breakdown"]
    headline = report["headline"]
    return _render_metric_table([
        ("Chauffage thermique", energy["heating_thermal"]),
        ("Chauffage électrique", energy["heating_electric"]),
        ("Climatisation thermique", energy["cooling_thermal"]),
        ("Climatisation électrique", energy["cooling_electric"]),
        ("Électricité totale", headline["electricity"]),
        ("Coût estimé", headline["cost"]),
        ("CO₂", headline["co2"]),
    ])


def _render_comfort_result_table(report: dict[str, Any]) -> str:
    hot_before = sum(
        room["comfort"]["hot_degree_hours"]["before"]
        for room in report["rooms"]
    )
    hot_after = sum(
        room["comfort"]["hot_degree_hours"]["after"]
        for room in report["rooms"]
    )
    cold_before = sum(
        room["comfort"]["cold_degree_hours"]["before"]
        for room in report["rooms"]
    )
    cold_after = sum(
        room["comfort"]["cold_degree_hours"]["after"]
        for room in report["rooms"]
    )
    max_before = max(
        room["comfort"]["max_temperature_c"]["before"]
        for room in report["rooms"]
    )
    max_after = max(
        room["comfort"]["max_temperature_c"]["after"]
        for room in report["rooms"]
    )
    return _render_metric_table([
        (
            "Température maximale",
            _metric(max_before, max_after, max_before - max_after, "C"),
        ),
        (
            "Heures d'inconfort cumulées (chaud)",
            _metric(hot_before, hot_after, hot_before - hot_after, "°C·h"),
        ),
        (
            "Heures d'inconfort cumulées (froid)",
            _metric(cold_before, cold_after, cold_before - cold_after, "°C·h"),
        ),
    ])


def _render_room_html(
    room: dict[str, Any],
    profile: dict[str, Any],
    comfort_mode: str,
) -> str:
    comfort = room["comfort"]
    balance = room["thermal_balance_deltas"]
    status_label, status_class = _room_status(profile, comfort_mode)
    return f"""
      <div class="room-detail">
        <div class="section-title-line">
          <h3>{escape(room["room_name"])}</h3>
          {_render_status_badge(status_label, status_class)}
        </div>
        <div class="room-tables">
          {_render_metric_table([
              ("Température maximale", comfort["max_temperature_c"]),
              ("Température finale", comfort["final_temperature_c"]),
              ("Heures d'inconfort cumulées (chaud)", comfort["hot_degree_hours"]),
              ("Heures d'inconfort cumulées (froid)", comfort["cold_degree_hours"]),
          ])}
          {_render_delta_table([
              ("Gains solaires", balance["solar_gain"]),
              ("Pertes par transmission", balance["transmission_exchange"]),
              ("Pertes par ventilation", balance["ventilation_exchange"]),
              ("Chauffage thermique", balance["heating_thermal"]),
              ("Climatisation thermique", balance["cooling_thermal"]),
          ])}
        </div>
      </div>
"""


def _render_temperature_profile_html(profile: dict[str, Any], comfort_mode: str) -> str:
    summary = profile["summary"]
    status_label, status_class = _room_status(profile, comfort_mode)
    if comfort_mode == "hot":
        before_value = summary["before_hot_degree_hours"]
        after_value = summary["after_hot_degree_hours"]
        discomfort_note = (
            "Heures d'inconfort cumulées : "
            f"{_format_value(before_value, '°C·h')} → {_format_value(after_value, '°C·h')} "
            f"({_format_signed_pct(_reduction_pct(before_value, after_value))})"
        )
    else:
        before_value = summary["before_cold_degree_hours"]
        after_value = summary["after_cold_degree_hours"]
        discomfort_note = (
            "Heures d'inconfort cumulées : "
            f"{_format_value(before_value, '°C·h')} → {_format_value(after_value, '°C·h')} "
            f"({_format_signed_pct(_reduction_pct(before_value, after_value))})"
        )
    return f"""
      <div class="chart-card">
        <div class="section-title-line">
          <h3>{escape(profile["room_name"])}</h3>
          {_render_status_badge(status_label, status_class)}
        </div>
        <div class="chart-wrap">
          {_render_temperature_svg(profile, comfort_mode)}
        </div>
        <p class="chart-note">{escape(discomfort_note)}</p>
      </div>
"""


def _render_temperature_svg(profile: dict[str, Any], comfort_mode: str) -> str:
    points = profile["points"]
    width = 1040
    height = 330
    left = 54
    right = 24
    top = 30
    bottom = 48
    plot_width = width - left - right
    plot_height = height - top - bottom
    values = [
        value
        for point in points
        for value in (
            point["outdoor_temperature_c"],
            point["before_temperature_c"],
            point["after_temperature_c"],
        )
    ]
    y_min = min(values) - 1.0
    y_max = max(values) + 1.0
    if y_max == y_min:
        y_max += 1.0

    def x_at(index: int) -> float:
        if len(points) == 1:
            return left
        return left + index / (len(points) - 1) * plot_width

    def y_at(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * plot_height

    outdoor_line = _svg_polyline(
        (x_at(index), y_at(point["outdoor_temperature_c"]))
        for index, point in enumerate(points)
    )
    before_line = _svg_polyline(
        (x_at(index), y_at(point["before_temperature_c"]))
        for index, point in enumerate(points)
    )
    after_line = _svg_polyline(
        (x_at(index), y_at(point["after_temperature_c"]))
        for index, point in enumerate(points)
    )
    before_peak_index, before_peak = _peak(points, "before_temperature_c", comfort_mode)
    after_peak_index, after_peak = _peak(points, "after_temperature_c", comfort_mode)
    discomfort_rects = _svg_discomfort_rects(
        points,
        profile["primary_discomfort"],
        x_at,
        top,
        plot_height,
    )
    grid = _svg_grid_lines(y_min, y_max, left, top, plot_width, plot_height)
    x_labels = _svg_x_labels(points, x_at, height, bottom)
    legend = _svg_legend(left + 18, top + 10, profile["primary_discomfort"])
    annotations = get_svg_annotation(
        x_at(before_peak_index),
        y_at(before_peak),
        before_peak,
        x_at(after_peak_index),
        y_at(after_peak),
        after_peak,
        width,
        comfort_mode,
    )

    return f"""
          <svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Courbes de température - {escape(profile["room_name"])}">
            <rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"></rect>
            {discomfort_rects}
            {grid}
            <polyline points="{outdoor_line}" fill="none" stroke="#64748b" stroke-width="2" stroke-dasharray="5 5"></polyline>
            <polyline points="{before_line}" fill="none" stroke="#1d4ed8" stroke-width="2.5"></polyline>
            <polyline points="{after_line}" fill="none" stroke="#15803d" stroke-width="2.5"></polyline>
            <circle cx="{x_at(before_peak_index):.1f}" cy="{y_at(before_peak):.1f}" r="3.5" fill="#1d4ed8"></circle>
            <circle cx="{x_at(after_peak_index):.1f}" cy="{y_at(after_peak):.1f}" r="3.5" fill="#15803d"></circle>
            {annotations}
            {legend}
            <line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#cbd5e1"></line>
            <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#cbd5e1"></line>
            {x_labels}
          </svg>
"""


def _svg_polyline(points: Any) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def _svg_discomfort_rects(
    points: list[dict[str, Any]],
    primary_discomfort: str,
    x_at: Any,
    top: float,
    plot_height: float,
) -> str:
    rects = []
    start = None
    for index, point in enumerate(points):
        if primary_discomfort == "hot":
            is_uncomfortable = (
                point["before_hot_excess_c"] > 0 or point["after_hot_excess_c"] > 0
            )
        else:
            is_uncomfortable = (
                point["before_cold_excess_c"] > 0 or point["after_cold_excess_c"] > 0
            )
        if is_uncomfortable and start is None:
            start = index
        if start is not None and (not is_uncomfortable or index == len(points) - 1):
            end = index if is_uncomfortable else index - 1
            x = x_at(start)
            next_x = x_at(min(end + 1, len(points) - 1))
            width = max(4.0, next_x - x)
            fill = "#fee2e2" if primary_discomfort == "hot" else "#dbeafe"
            rects.append(
                f'<rect x="{x:.1f}" y="{top:.1f}" width="{width:.1f}" '
                f'height="{plot_height:.1f}" fill="{fill}" opacity="0.30"></rect>'
            )
            start = None
    return "\n".join(rects)


def _svg_grid_lines(
    y_min: float,
    y_max: float,
    left: float,
    top: float,
    plot_width: float,
    plot_height: float,
) -> str:
    lines = []
    for step in range(5):
        ratio = step / 4
        y = top + ratio * plot_height
        value = y_max - ratio * (y_max - y_min)
        lines.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" '
            'stroke="#e2e8f0"></line>'
        )
        lines.append(
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-size="11" fill="#64748b">{value:.0f} °C</text>'
        )
    return "\n".join(lines)


def _svg_x_labels(
    points: list[dict[str, Any]],
    x_at: Any,
    height: float,
    bottom: float,
) -> str:
    if not points:
        return ""
    indexes = sorted({0, len(points) // 2, len(points) - 1})
    labels = []
    for index in indexes:
        labels.append(
            f'<text x="{x_at(index):.1f}" y="{height - bottom + 24:.1f}" '
            f'text-anchor="middle" font-size="11" fill="#64748b">h{points[index]["hour"]}</text>'
        )
    return "\n".join(labels)


def _svg_legend(x: float, y: float, primary_discomfort: str) -> str:
    zone_fill = "#fee2e2" if primary_discomfort == "hot" else "#dbeafe"
    return f"""
            <g aria-hidden="true">
              <rect x="{x - 10:.1f}" y="{y - 14:.1f}" width="454" height="26" rx="5" fill="#ffffff" stroke="#e2e8f0"></rect>
              <line x1="{x:.1f}" y1="{y:.1f}" x2="{x + 24:.1f}" y2="{y:.1f}" stroke="#64748b" stroke-width="2" stroke-dasharray="5 5"></line>
              <text x="{x + 30:.1f}" y="{y + 4:.1f}" font-size="11" fill="#475569">Extérieur</text>
              <line x1="{x + 102:.1f}" y1="{y:.1f}" x2="{x + 126:.1f}" y2="{y:.1f}" stroke="#1d4ed8" stroke-width="2.5"></line>
              <text x="{x + 132:.1f}" y="{y + 4:.1f}" font-size="11" fill="#475569">Avant</text>
              <line x1="{x + 184:.1f}" y1="{y:.1f}" x2="{x + 208:.1f}" y2="{y:.1f}" stroke="#15803d" stroke-width="2.5"></line>
              <text x="{x + 214:.1f}" y="{y + 4:.1f}" font-size="11" fill="#475569">Après</text>
              <rect x="{x + 268:.1f}" y="{y - 7:.1f}" width="22" height="12" fill="{zone_fill}" opacity="0.8"></rect>
              <text x="{x + 296:.1f}" y="{y + 4:.1f}" font-size="11" fill="#475569">Zone d'inconfort</text>
            </g>
"""


def get_svg_annotation(
    before_x: float,
    before_y: float,
    before_value: float,
    after_x: float,
    after_y: float,
    after_value: float,
    width: float,
    comfort_mode: str,
) -> str:
    before_label_x = min(before_x + 8, width - 120)
    after_label_x = min(after_x + 8, width - 120)
    before_label_y = max(18, before_y - 10)
    after_label_y = min(before_label_y + 18, max(18, after_y + 18))
    before_label = (
        f"Pic avant {_format_temperature(before_value)}"
        if comfort_mode == "hot"
        else f"Min. avant {_format_temperature(before_value)}"
    )
    after_label = (
        f"Pic après {_format_temperature(after_value)}"
        if comfort_mode == "hot"
        else f"Min. après {_format_temperature(after_value)}"
    )
    return f"""
            <text x="{before_label_x:.1f}" y="{before_label_y:.1f}" font-size="11" fill="#1d4ed8">{escape(before_label)}</text>
            <text x="{after_label_x:.1f}" y="{after_label_y:.1f}" font-size="11" fill="#15803d">{escape(after_label)}</text>
"""


def _render_metric_table(rows: list[tuple[str, dict[str, Any]]]) -> str:
    table_rows = "\n".join(
        "<tr>"
        f"<td>{escape(label)}</td>"
        f"<td>{_format_value(metric['before'], metric['unit'])}</td>"
        f"<td>{_format_value(metric['after'], metric['unit'])}</td>"
        f"<td class=\"{_value_class(metric['delta'])}\">{_format_delta(metric)}</td>"
        f"<td>{_format_pct_badge(metric)}</td>"
        "</tr>"
        for label, metric in rows
    )
    return f"""
      <table class="data-table">
        <thead>
          <tr>
            <th>Indicateur</th>
            <th>Avant</th>
            <th>Après</th>
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
        f"<td class=\"{_value_class(metric['delta'])}\">{_format_delta(metric)}</td>"
        "</tr>"
        for label, metric in rows
    )
    return f"""
      <table class="data-table">
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
        f"après {_format_value(metric['after'], metric['unit'])}"
    )


def _format_delta(metric: dict[str, Any]) -> str:
    return _format_value(metric["delta"], metric["unit"])


def _format_value(value: float, unit: str) -> str:
    display_unit = _display_unit(unit)
    if display_unit == "€":
        return f"{_format_number(value, 2)} €"
    return f"{_format_number(value, 2)} {escape(display_unit)}"


def _format_pct(metric: dict[str, Any]) -> str:
    value = metric["relative_delta_pct"]
    if value is None:
        return "n/a"
    return f"{_format_number(value, 1)} %"


def _format_pct_badge(metric: dict[str, Any]) -> str:
    value = metric["relative_delta_pct"]
    badge_class = _value_class(metric["delta"])
    if value is None:
        return '<span class="delta-badge neutral">n/a</span>'
    return f'<span class="delta-badge {badge_class}">{_format_number(value, 1)} %</span>'


def _display_unit(unit: str) -> str:
    units = {
        "C": "°C",
        "C.h": "°C·h",
        "EUR": "€",
        "kWh_th": "kWh therm.",
        "kgCO2": "kg CO₂",
    }
    return units.get(unit, unit)


def _format_temperature(value: float) -> str:
    return f"{_format_number(value, 1)} °C"


def _format_duration(experiment: dict[str, Any]) -> str:
    return (
        f"{_format_number(experiment['duration_days'], 1)} j "
        f"({_format_number(experiment['duration_hours'], 0)} h)"
    )


def _format_number(value: float, decimals: int = 1) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.{decimals}f}"


def _value_class(delta: float) -> str:
    if delta > 0:
        return "gain"
    if delta < 0:
        return "loss"
    return "neutral"


def _format_signed_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "−" if value >= 0 else "+"
    return f"{sign}{_format_number(abs(value), 1)} %"


def _reduction_pct(before: float, after: float) -> float | None:
    if before == 0:
        return None
    return (before - after) / before * 100.0


def _peak(
    points: list[dict[str, Any]],
    key: str,
    comfort_mode: str,
) -> tuple[int, float]:
    if comfort_mode == "hot":
        index, point = max(enumerate(points), key=lambda item: item[1][key])
    else:
        index, point = min(enumerate(points), key=lambda item: item[1][key])
    return index, point[key]


def _room_status(profile: dict[str, Any], comfort_mode: str) -> tuple[str, str]:
    return get_room_status(_profile_room_data(profile), comfort_mode)


def _profile_room_data(profile: dict[str, Any]) -> dict[str, Any]:
    summary = profile["summary"]
    return {
        "name": profile["room_name"],
        "temp_max_before": summary["temp_max_before"],
        "temp_max_after": summary["temp_max_after"],
        "temp_min_before": summary["temp_min_before"],
        "temp_min_after": summary["temp_min_after"],
        "hot_dh_reduction_pct": _reduction_pct(
            summary["before_hot_degree_hours"],
            summary["after_hot_degree_hours"],
        ) or 0,
        "cold_dh_reduction_pct": _reduction_pct(
            summary["before_cold_degree_hours"],
            summary["after_cold_degree_hours"],
        ) or 0,
    }


def _render_status_badge(label: str, css_class: str) -> str:
    return f'<span class="badge {escape(css_class)}">{escape(label)}</span>'


def _format_intervention(intervention: dict[str, Any]) -> str:
    parts = []
    labels = {
        "surface_overrides": "parois modifiées",
        "window_overrides": "fenêtres modifiées",
        "shutter_overrides": "protections solaires modifiées",
        "system_overrides": "systèmes modifiés",
        "add_systems": "systèmes ajoutés",
    }
    for key, label in labels.items():
        item = intervention[key]
        if item["count"]:
            fields = ", ".join(item["changed_fields"]) or "paramètres"
            parts.append(f"{item['count']} {label} ({fields})")
    if not parts:
        return "aucune modification technique appliquée"
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
