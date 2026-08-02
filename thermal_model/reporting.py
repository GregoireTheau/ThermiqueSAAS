"""Report model builder for ThermalTwin scenario comparisons."""

from __future__ import annotations

from datetime import date
from html import escape
from typing import Any


DISCOMFORT_COLD_THRESHOLD_C = 19.0
DISCOMFORT_HOT_THRESHOLD_C = 26.0

PROFILE_BY_ADAPTATION = {
    "heat_pump": "heat_pump_seller",
    "roof_insulation": "roof_insulation_seller",
    "reflective_roof": "reflective_roof_seller",
    "solar_protection": "solar_protection_seller",
    "better_windows": "window_seller",
}

REPORT_PRESENTATION_CONFIG = {
    ("heat_pump_seller", "all"): {
        "hero_kpis": ["final_energy", "cost", "co2"],
        "secondary_kpis": ["heating_thermal", "heating_final"],
        "hidden_summary_kpis": ["hot_discomfort"],
        "reading_template": "heat_pump",
    },
    ("roof_insulation_seller", "winter"): {
        "hero_kpis": ["heating_thermal", "heating_final", "cost"],
        "secondary_kpis": ["hot_discomfort", "max_temperature"],
        "hidden_summary_kpis": [],
        "reading_template": "roof_insulation_winter",
    },
    ("roof_insulation_seller", "annual"): {
        "hero_kpis": ["heating_thermal", "heating_final", "cost"],
        "secondary_kpis": ["hot_discomfort", "max_temperature"],
        "hidden_summary_kpis": [],
        "reading_template": "roof_insulation_winter",
        "fixed_notes": ["roof_insulation_annual_scope"],
    },
    ("roof_insulation_seller", "summer"): {
        "hero_kpis": ["hot_discomfort", "max_temperature"],
        "secondary_kpis": ["cooling_thermal", "final_energy"],
        "hidden_summary_kpis": [],
        "reading_template": "roof_insulation_summer",
        "fixed_notes": ["roof_summer_limited"],
    },
    ("reflective_roof_seller", "all"): {
        "hero_kpis": ["hot_discomfort", "max_temperature"],
        "secondary_kpis": ["heating_final", "cost"],
        "hidden_summary_kpis": ["final_energy_if_negative"],
        "reading_template": "reflective_roof",
        "conditional_notes": ["reduced_winter_solar_gains"],
    },
    ("solar_protection_seller", "all"): {
        "hero_kpis": ["hot_discomfort", "max_temperature"],
        "secondary_kpis": ["heating_final", "cost"],
        "hidden_summary_kpis": ["final_energy_if_negative"],
        "reading_template": "solar_protection",
        "conditional_notes": ["blocked_winter_solar_gains"],
    },
    ("window_seller", "winter"): {
        "hero_kpis": ["final_energy", "cost"],
        "secondary_kpis": ["heating_thermal", "heating_final"],
        "hidden_summary_kpis": [],
        "reading_template": "windows_winter",
        "fixed_notes": ["windows_winter_scope"],
    },
    ("window_seller", "summer"): {
        "hero_kpis": ["hot_discomfort", "max_temperature"],
        "secondary_kpis": ["final_energy", "cost"],
        "hidden_summary_kpis": [],
        "reading_template": "windows_summer",
        "fixed_notes": ["windows_summer_scope"],
    },
    ("window_seller", "annual"): {
        "hero_kpis": ["final_energy", "cost", "hot_discomfort"],
        "secondary_kpis": ["heating_thermal", "max_temperature"],
        "hidden_summary_kpis": [],
        "reading_template": "windows_annual",
        "special_sections": ["windows_double_effect"],
    },
}


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
    profile_id = _profile_id(experiment)
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
    energy_breakdown = _build_energy_breakdown(before_totals, after_totals, deltas)
    presentation_config = _presentation_config(profile_id, season)
    most_impacted_room = max(
        rooms,
        key=lambda room: (
            max(0.0, room["comfort"]["hot_degree_hours"]["delta"])
            + max(0.0, room["comfort"]["cold_degree_hours"]["delta"])
            + max(0.0, room["comfort"]["max_temperature_c"]["delta"]) * 24.0
        ),
    )

    return {
        "report_schema_version": "0.5",
        "source": {
            "comparison_schema_version": comparison["comparison_schema_version"],
            "dwelling_id": comparison["dwelling_id"],
            "dwelling_name": comparison.get("dwelling_name", comparison["dwelling_id"]),
            "location": _report_location(comparison.get("location", {})),
            "before_scenario_id": comparison["before_scenario_id"],
            "after_scenario_id": comparison["after_scenario_id"],
        },
        "experiment": {
            "title": title,
            "season": season,
            "business_profile_id": profile_id,
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
            "weather_reference": experiment.get("weather_reference", ""),
            "climate_zone_code": comparison.get("location", {}).get(
                "climate_zone_code",
                "",
            ),
            "climate_zone_standard": comparison.get("location", {}).get(
                "climate_zone_standard",
                "",
            ),
            "county": comparison.get("location", {}).get("county", ""),
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
            "weather_trace": experiment.get("weather_trace", {}),
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
            "has_cooling": experiment.get("has_cooling", False),
            "intervention": experiment["intervention"],
        },
        "comfort_mode": comfort_mode,
        "narrative": {
            "context": context_text,
            "purpose": purpose_text,
            "tested_change": tested_change_text,
            "conclusion": _build_conclusion_text(
                experiment,
                headline,
                driver,
                most_impacted_room,
                presentation_config,
                energy_breakdown,
                rooms,
            ),
        },
        "sign_convention": (
            "Delta = before - after; a positive value means a reduction "
            "after the intervention."
        ),
        "headline": {
            "electricity": _metric(
                before_totals["electricity_kwh"],
                after_totals["electricity_kwh"],
                deltas["electricity_kwh"],
                "kWh",
            ),
            "final_energy": _metric(
                before_totals["final_energy_kwh"],
                after_totals["final_energy_kwh"],
                deltas["final_energy_kwh"],
                "kWh_final",
            ),
            "cost": _metric(
                before_totals["energy_cost_eur"],
                after_totals["energy_cost_eur"],
                deltas["energy_cost_eur"],
                "EUR",
            ),
            "co2": _metric(
                before_totals["energy_co2_kg"],
                after_totals["energy_co2_kg"],
                deltas["energy_co2_kg"],
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
        "primary_kpis": _build_primary_kpis(
            presentation_config,
            energy_breakdown,
            before_totals,
            after_totals,
            deltas,
            rooms,
        ),
        "secondary_kpis": _build_secondary_kpis(presentation_config, energy_breakdown, rooms),
        "presentation": _build_presentation_notes(
            presentation_config,
            experiment,
            energy_breakdown,
            rooms,
        ),
        "main_gain_driver": {
            "key": driver["key"],
            "label": driver["label"],
            "value": round(driver["value"], 2),
            "unit": driver["unit"],
            "definition": (
                "Heuristic indicator: simulated balance item contributing the most "
                "to the calculated gain, without being measured causal proof."
            ),
        },
        "comfort": {
            "most_impacted_room_id": most_impacted_room["room_id"],
            "most_impacted_room_name": most_impacted_room["room_name"],
            "definition": (
                "Cumulative discomfort hours add up the hours spent beyond the comfort "
                "threshold, weighted by the temperature gap."
            ),
        },
        "temperature_profiles": _build_temperature_profiles(
            comparison,
            rooms,
            comfort_mode,
            season,
        ),
        "energy_breakdown": energy_breakdown,
        "rooms": rooms,
        "methodology": {
            "model": "Hourly 1R1C thermal simulation, room by room",
            "engine_version": experiment.get("weather_trace", {}).get(
                "engine_version",
                "1r1c-mvp-0.1",
            ),
            "reported_values": (
                "Calculated from before/after simulations; no measured performance "
                "is inferred."
            ),
        },
    }


def render_report_html(
    report: dict[str, Any],
    branding: dict[str, Any] | None = None,
) -> str:
    """Render a report model as a standalone HTML document."""
    source = report["source"]
    experiment = report["experiment"]
    narrative = report["narrative"]
    headline = report["headline"]
    energy = report["energy_breakdown"]
    generated_date = date.today().strftime("%d/%m/%Y")
    branding = _normalize_branding(branding)
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
    charts_intro_html = _render_temperature_charts_intro(
        report["temperature_profiles"]["rooms"],
    )
    alert_html = _render_temperature_alert(
        report["temperature_profiles"]["rooms"],
        comfort_mode,
    )
    executive_html = _render_executive_summary(report)
    context_params_html = _render_context_params(experiment, report["temperature_profiles"])
    profile_notes_html = _render_profile_notes(report)
    short_scenario_note_html = _render_short_scenario_note(experiment)
    special_sections_html = _render_special_sections(report)
    results_sections_html = _render_results_sections(report)
    contextual_notes_html = _render_contextual_notes(report)
    header_html = _render_report_header(source, experiment, generated_date, branding)
    footer_html = _render_report_footer(branding)
    custom_color_css = _render_branding_css(branding)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Thermal report - {escape(source["dwelling_id"])}</title>
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
      --c-loss: #c2410c;
      --c-loss-light: #ffedd5;
      --c-neutral: #475569;
      --c-hot-zone: #fef3c7;
      {custom_color_css}
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
    .brand-block {{
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 12px;
      align-items: center;
      min-width: 0;
    }}
    .brand-logo-img {{
      max-width: 126px;
      max-height: 42px;
      object-fit: contain;
    }}
    .brand-name {{
      font-size: 1.4rem;
      font-weight: 750;
      color: var(--c-text);
    }}
    .brand-contact {{
      color: var(--c-muted);
      font-size: 12px;
      margin-top: 2px;
    }}
    .header-center {{
      text-align: center;
    }}
    .header-divider {{
      width: 70%;
      height: 1px;
      background: var(--c-border);
      margin: 12px auto;
    }}
    .legal-mention {{
      margin-top: 6px;
      color: var(--c-muted);
      font-size: 10px;
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
      color: var(--c-accent);
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
      .context-note {{
        margin-top: 12px;
        border-left: 4px solid #f59e0b;
        background: #fffbeb;
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
      grid-template-columns: minmax(0, 1.15fr) minmax(260px, .85fr);
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
      min-width: 0;
    }}
    .params table, .data-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      table-layout: fixed;
    }}
    .params td {{
      border-bottom: 1px solid var(--c-border);
      padding: 9px 10px;
      overflow-wrap: anywhere;
      vertical-align: top;
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
    .section-note {{
      color: var(--c-muted);
      font-size: 14px;
      margin: -5px 0 12px;
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
      .result-block {{
        margin-top: 14px;
      }}
      .result-block h3 {{
        font-size: 18px;
        color: var(--c-text);
      }}
      .value-main {{
        display: block;
        font-weight: 760;
      }}
      .value-sub {{
        display: block;
        color: var(--c-muted);
        font-size: 12px;
        margin-top: 2px;
      }}
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
      .context-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    {header_html}

    {alert_html}

    <section>
      <h2>Executive Summary</h2>
      {executive_html}
    </section>

    <section>
      <h2>Context</h2>
      <div class="context-grid">
        <div class="context-text">
          <p>{_format_prose_html(narrative["context"])}</p>
          <p>{_format_prose_html(narrative["purpose"])}</p>
        </div>
        <div class="params">
          {context_params_html}
        </div>
      </div>
      {profile_notes_html}
      {short_scenario_note_html}
      {special_sections_html}
    </section>

    <section>
      <h2>Temperature Charts</h2>
      {charts_intro_html}
      {charts_html}
    </section>

    <section>
      <h2>Main Results</h2>
      {results_sections_html}
      {contextual_notes_html}
    </section>

    <section>
      <h2>Reading the Results</h2>
      <p>{_format_prose_html(narrative["conclusion"])}</p>
    </section>

    <section>
      <h2>Room Details</h2>
      {rooms_html}
    </section>

    {footer_html}
  </main>
  <script>
    function printReport() {{
      window.print();
    }}
  </script>
</body>
</html>
"""


def _report_location(location: dict[str, Any]) -> dict[str, Any]:
    rounded = dict(location)
    for key in ("latitude", "longitude"):
        if rounded.get(key) is not None:
            rounded[key] = round(float(rounded[key]), 2)
    return rounded


def _normalize_branding(branding: dict[str, Any] | None) -> dict[str, Any] | None:
    if not branding:
        return None
    cleaned = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in branding.items()
    }
    return cleaned if any(cleaned.values()) else None


def _render_branding_css(branding: dict[str, Any] | None) -> str:
    if not branding:
        return ""
    primary_color = branding.get("primary_color")
    if not primary_color:
        return ""
    return f"""
      --c-accent: {escape(primary_color)};
      --c-gain: {escape(primary_color)};
    """


def _render_report_header(
    source: dict[str, Any],
    experiment: dict[str, Any],
    generated_date: str,
    branding: dict[str, Any] | None,
) -> str:
    if not branding:
        return f"""
    <header class="report-header">
      <div class="header-top">
        <div class="logo">THERMAL</div>
        <h1>{escape(experiment["title"])}</h1>
        <div class="ref-box">
          <div><strong>Reference</strong></div>
          <div>{escape(source["dwelling_id"])}</div>
          <div>{escape(generated_date)}</div>
        </div>
      </div>
      <div class="header-meta">
        <div><div class="label">Home</div>{escape(source["dwelling_id"])}</div>
        <div><div class="label">Scenario</div>{escape(_format_scenario_summary(experiment))}</div>
        <div><div class="label">Duration</div>{_format_duration(experiment)}</div>
      </div>
      <div class="print-action"><button type="button" onclick="printReport()">Print / PDF</button></div>
    </header>
"""

    organization_name = branding.get("organization_name") or "ThermalTwin"
    contact = _join_non_empty(
        branding.get("phone"),
        branding.get("email_contact"),
        branding.get("website"),
    )
    logo_url = branding.get("logo_url")
    logo_html = (
        f'<img class="brand-logo-img" src="{escape(logo_url)}" alt="Logo">'
        if logo_url
        else f'<div class="brand-name">{escape(organization_name)}</div>'
    )
    location = source.get("location", {})
    location_text = _join_non_empty(
        location.get("address"),
        experiment.get("requested_city") or location.get("city") or experiment.get("weather_city"),
        location.get("state"),
        location.get("postal_code"),
    )
    project_name = source.get("dwelling_name") or source["dwelling_id"]
    scenario_label = experiment.get("adaptation_label") or _scenario_intervention_label(experiment)
    return f"""
    <header class="report-header">
      <div class="header-top">
        <div class="brand-block">
          {logo_html}
          <div>
            <div class="brand-contact">{escape(contact)}</div>
          </div>
        </div>
        <div class="header-center">
          <div class="header-divider"></div>
          <h1>Thermal Study — {escape(project_name)}</h1>
          <p>Scenario: {escape(scenario_label)}</p>
        </div>
        <div class="ref-box">
          <div>{escape(location_text)}</div>
          <div>{escape(generated_date)}</div>
          <div><strong>Reference</strong> {escape(source["dwelling_id"])}</div>
        </div>
      </div>
      <div class="header-meta">
        <div><div class="label">Home</div>{escape(source["dwelling_id"])}</div>
        <div><div class="label">Report prepared by</div>{escape(organization_name)}</div>
        <div><div class="label">Duration</div>{_format_duration(experiment)}</div>
      </div>
      <div class="print-action"><button type="button" onclick="printReport()">Print / PDF</button></div>
    </header>
"""


def _render_report_footer(branding: dict[str, Any] | None) -> str:
    if not branding:
        return '<footer class="footer">Report generated automatically · ThermalTwin</footer>'
    parts = [
        branding.get("organization_name"),
        branding.get("phone"),
        branding.get("email_contact"),
        branding.get("website"),
        "ThermalTwin",
    ]
    legal = branding.get("legal_mention")
    legal_html = (
        f'<div class="legal-mention">{escape(legal)}</div>'
        if legal
        else ""
    )
    return f"""
    <footer class="footer">
      {escape(_join_non_empty(*parts))}
      {legal_html}
    </footer>
"""


def _join_non_empty(*values: Any) -> str:
    return " · ".join(str(value).strip() for value in values if str(value or "").strip())


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
    comfort_mode: str,
    season: str,
) -> dict[str, Any]:
    hot_threshold_c = DISCOMFORT_HOT_THRESHOLD_C
    cold_threshold_c = DISCOMFORT_COLD_THRESHOLD_C
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
            f"Colored zones indicate hours above "
            f"{hot_threshold_c:.1f} °C, the threshold used to count hot discomfort "
            "hours."
            if threshold_key == "hot"
            else (
                f"Colored zones indicate hours below {cold_threshold_c:.1f} °C, "
                "the threshold used to count cold discomfort hours."
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
                season,
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
    season: str,
) -> dict[str, Any]:
    points = []
    for before_hour, after_hour in zip(before_hourly, after_hourly, strict=True):
        before_temperature = before_hour["rooms"][room_id]["temperature_c"]
        after_temperature = after_hour["rooms"][room_id]["temperature_c"]
        points.append(
            {
                "hour": before_hour["hour"],
                "month": before_hour.get("month"),
                "outdoor_temperature_c": round(before_hour["outdoor_temperature_c"], 2),
                "before_temperature_c": round(before_temperature, 2),
                "after_temperature_c": round(after_temperature, 2),
                "before_hot_excess_c": round(max(0.0, before_temperature - hot_threshold_c), 2),
                "after_hot_excess_c": round(max(0.0, after_temperature - hot_threshold_c), 2),
                "before_cold_excess_c": round(max(0.0, cold_threshold_c - before_temperature), 2),
                "after_cold_excess_c": round(max(0.0, cold_threshold_c - after_temperature), 2),
                "duration_h": 1.0,
            },
        )
    raw_points = points
    summary = _temperature_profile_summary(raw_points)
    critical_markers = []
    if season in {"annual", "summer"} and len(points) > 1000:
        if season == "summer":
            points = _daily_peak_temperature_points(raw_points)
            aggregation = "daily_max"
        else:
            points = _daily_average_temperature_points(raw_points)
            aggregation = "daily_average"
        critical_markers = _daily_critical_markers(raw_points)
    else:
        aggregation = "hourly"

    return {
        "room_id": room_id,
        "room_name": room_name,
        "primary_discomfort": primary_discomfort,
        "thresholds": {
            "hot_c": round(hot_threshold_c, 2),
            "cold_c": round(cold_threshold_c, 2),
        },
        "x_axis": _temperature_x_axis(points, season),
        "aggregation": aggregation,
        "critical_markers": critical_markers,
        "points": points,
        "summary": summary,
    }


def _temperature_profile_summary(points: list[dict[str, Any]]) -> dict[str, Any]:
    return {
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
            sum(
                point["before_hot_excess_c"] * point.get("duration_h", 1.0)
                for point in points
            ),
            2,
        ),
        "after_hot_degree_hours": round(
            sum(
                point["after_hot_excess_c"] * point.get("duration_h", 1.0)
                for point in points
            ),
            2,
        ),
        "before_cold_degree_hours": round(
            sum(
                point["before_cold_excess_c"] * point.get("duration_h", 1.0)
                for point in points
            ),
            2,
        ),
        "after_cold_degree_hours": round(
            sum(
                point["after_cold_excess_c"] * point.get("duration_h", 1.0)
                for point in points
            ),
            2,
        ),
    }


def _daily_average_temperature_points(
    hourly_points: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    daily_points = []
    for index in range(0, len(hourly_points), 24):
        day_points = hourly_points[index:index + 24]
        if not day_points:
            continue
        duration_h = sum(point.get("duration_h", 1.0) for point in day_points)
        outdoor = _average(point["outdoor_temperature_c"] for point in day_points)
        before = _average(point["before_temperature_c"] for point in day_points)
        after = _average(point["after_temperature_c"] for point in day_points)
        before_min = min(point["before_temperature_c"] for point in day_points)
        before_max = max(point["before_temperature_c"] for point in day_points)
        after_min = min(point["after_temperature_c"] for point in day_points)
        after_max = max(point["after_temperature_c"] for point in day_points)
        daily_points.append(
            {
                "hour": day_points[0]["hour"],
                "month": day_points[0].get("month"),
                "outdoor_temperature_c": round(outdoor, 2),
                "before_temperature_c": round(before, 2),
                "after_temperature_c": round(after, 2),
                "before_min_temperature_c": round(before_min, 2),
                "before_max_temperature_c": round(before_max, 2),
                "after_min_temperature_c": round(after_min, 2),
                "after_max_temperature_c": round(after_max, 2),
                "before_hot_excess_c": round(
                    max(0.0, before - DISCOMFORT_HOT_THRESHOLD_C),
                    2,
                ),
                "after_hot_excess_c": round(
                    max(0.0, after - DISCOMFORT_HOT_THRESHOLD_C),
                    2,
                ),
                "before_cold_excess_c": round(
                    max(0.0, DISCOMFORT_COLD_THRESHOLD_C - before),
                    2,
                ),
                "after_cold_excess_c": round(
                    max(0.0, DISCOMFORT_COLD_THRESHOLD_C - after),
                    2,
                ),
                "duration_h": duration_h,
            },
        )
    return daily_points


def _daily_peak_temperature_points(
    hourly_points: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    daily_points = []
    for index in range(0, len(hourly_points), 24):
        day_points = hourly_points[index:index + 24]
        if not day_points:
            continue
        duration_h = sum(point.get("duration_h", 1.0) for point in day_points)
        outdoor_average = _average(point["outdoor_temperature_c"] for point in day_points)
        outdoor_max = max(point["outdoor_temperature_c"] for point in day_points)
        before_average = _average(point["before_temperature_c"] for point in day_points)
        after_average = _average(point["after_temperature_c"] for point in day_points)
        before_min = min(point["before_temperature_c"] for point in day_points)
        before_max = max(point["before_temperature_c"] for point in day_points)
        after_min = min(point["after_temperature_c"] for point in day_points)
        after_max = max(point["after_temperature_c"] for point in day_points)
        daily_points.append(
            {
                "hour": day_points[0]["hour"],
                "month": day_points[0].get("month"),
                "outdoor_temperature_c": round(outdoor_max, 2),
                "outdoor_average_temperature_c": round(outdoor_average, 2),
                "before_temperature_c": round(before_max, 2),
                "after_temperature_c": round(after_max, 2),
                "before_average_temperature_c": round(before_average, 2),
                "after_average_temperature_c": round(after_average, 2),
                "before_min_temperature_c": round(before_min, 2),
                "before_max_temperature_c": round(before_max, 2),
                "after_min_temperature_c": round(after_min, 2),
                "after_max_temperature_c": round(after_max, 2),
                "before_hot_excess_c": round(
                    max(0.0, before_max - DISCOMFORT_HOT_THRESHOLD_C),
                    2,
                ),
                "after_hot_excess_c": round(
                    max(0.0, after_max - DISCOMFORT_HOT_THRESHOLD_C),
                    2,
                ),
                "before_cold_excess_c": round(
                    max(0.0, DISCOMFORT_COLD_THRESHOLD_C - before_min),
                    2,
                ),
                "after_cold_excess_c": round(
                    max(0.0, DISCOMFORT_COLD_THRESHOLD_C - after_min),
                    2,
                ),
                "duration_h": duration_h,
            },
        )
    return daily_points


def _daily_critical_markers(hourly_points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    markers = []
    for index in range(0, len(hourly_points), 24):
        day_points = hourly_points[index:index + 24]
        if not day_points:
            continue
        for series in ("before", "after"):
            temperatures = [point[f"{series}_temperature_c"] for point in day_points]
            max_temperature = max(temperatures)
            min_temperature = min(temperatures)
            hour = day_points[0]["hour"] + 12
            if max_temperature > 35.0:
                markers.append(
                    {
                        "hour": hour,
                        "series": series,
                        "type": "hot",
                        "value": round(max_temperature, 2),
                        "tooltip": (
                            f"{_format_day_month(day_points[0]['hour'])} — "
                            f"max {_format_temperature(max_temperature)}"
                        ),
                    },
                )
            if min_temperature < 16.0:
                markers.append(
                    {
                        "hour": hour,
                        "series": series,
                        "type": "cold",
                        "value": round(min_temperature, 2),
                        "tooltip": (
                            f"{_format_day_month(day_points[0]['hour'])} — "
                            f"min {_format_temperature(min_temperature)}"
                        ),
                    },
                )
    return markers


def _format_day_month(hour: float) -> str:
    day_of_year = int(hour // 24)
    month_days = [
        ("jan", 31),
        ("feb", 28),
        ("mar", 31),
        ("apr", 30),
        ("may", 31),
        ("jun", 30),
        ("jul", 31),
        ("aug", 31),
        ("sep", 30),
        ("oct", 31),
        ("nov", 30),
        ("dec", 31),
    ]
    day = day_of_year
    for month, days in month_days:
        if day < days:
            return f"{day + 1} {month}"
        day -= days
    return "31 dec"


def _average(values: Any) -> float:
    items = list(values)
    return sum(items) / len(items)


def _temperature_x_axis(points: list[dict[str, Any]], season: str) -> dict[str, Any]:
    if season == "annual":
        return {
            "type": "annual",
            "min_hour": 0,
            "max_hour": 8760,
            "labels": [
                ("Jan", 0),
                ("Feb", 744),
                ("Mar", 1416),
                ("Apr", 2160),
                ("May", 2880),
                ("Jun", 3624),
                ("Jul", 4344),
                ("Aug", 5088),
                ("Sep", 5832),
                ("Oct", 6552),
                ("Nov", 7296),
                ("Dec", 8016),
            ],
            "zones": [
                {"label": "Summer", "start_hour": 3624, "end_hour": 5832},
            ],
        }
    if not points:
        return {"type": "hours", "min_hour": 0, "max_hour": 1, "labels": [], "zones": []}
    min_hour = points[0]["hour"]
    max_hour = points[-1]["hour"] + points[-1].get("duration_h", 1.0)
    duration_h = max_hour - min_hour
    if season == "summer" and duration_h >= 24 * 45:
        return {
            "type": "season_months",
            "min_hour": min_hour,
            "max_hour": max_hour,
            "labels": _season_month_labels(points, min_hour, max_hour),
            "zones": [],
        }
    return {
        "type": "hours",
        "min_hour": min_hour,
        "max_hour": max_hour,
        "labels": [],
        "zones": [],
    }


def _season_month_labels(
    points: list[dict[str, Any]],
    min_hour: float,
    max_hour: float,
) -> list[tuple[str, float]]:
    if not points:
        return []
    selected_indexes = [0, len(points) // 2, len(points) - 1]
    return [
        (_month_short_label(points[index].get("month")), points[index]["hour"])
        for index in selected_indexes
    ]


def _month_short_label(month: Any) -> str:
    labels = {
        1: "Jan",
        2: "Feb",
        3: "Mar",
        4: "Apr",
        5: "May",
        6: "Jun",
        7: "Jul",
        8: "Aug",
        9: "Sep",
        10: "Oct",
        11: "Nov",
        12: "Dec",
    }
    try:
        return labels[int(month)]
    except (TypeError, ValueError, KeyError):
        return ""


def _metric(before: float, after: float, delta: float, unit: str) -> dict[str, Any]:
    return {
        "before": round(before, 2),
        "after": round(after, 2),
        "delta": round(delta, 2),
        "variation": round(after - before, 2),
        "relative_delta_pct": _relative_delta_pct(before, delta),
        "relative_variation_pct": _relative_variation_pct(before, after),
        "effect": _effect(delta),
        "unit": unit,
    }


def _delta_metric(delta: float, unit: str) -> dict[str, Any]:
    return {
        "delta": round(delta, 2),
        "effect": _effect(delta),
        "unit": unit,
    }


def _build_energy_breakdown(
    before_totals: dict[str, Any],
    after_totals: dict[str, Any],
    deltas: dict[str, Any],
) -> dict[str, Any]:
    before_vectors = before_totals.get("final_energy_kwh_by_energy", {})
    after_vectors = after_totals.get("final_energy_kwh_by_energy", {})
    vector_keys = sorted(set(before_vectors) | set(after_vectors))
    return {
        "heating_thermal": _metric(
            before_totals["heating_thermal_kwh"],
            after_totals["heating_thermal_kwh"],
            deltas["heating_thermal_kwh"],
            "kWh_th",
        ),
        "heating_final": _metric(
            before_totals["heating_final_kwh"],
            after_totals["heating_final_kwh"],
            deltas["heating_final_kwh"],
            "kWh_final",
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
        "final_energy": _metric(
            before_totals["final_energy_kwh"],
            after_totals["final_energy_kwh"],
            deltas["final_energy_kwh"],
            "kWh_final",
        ),
        "cost": _metric(
            before_totals["energy_cost_eur"],
            after_totals["energy_cost_eur"],
            deltas["energy_cost_eur"],
            "EUR",
        ),
        "co2": _metric(
            before_totals["energy_co2_kg"],
            after_totals["energy_co2_kg"],
            deltas["energy_co2_kg"],
            "kgCO2",
        ),
        "final_energy_by_vector": {
            vector: _metric(
                before_vectors.get(vector, 0.0),
                after_vectors.get(vector, 0.0),
                before_vectors.get(vector, 0.0) - after_vectors.get(vector, 0.0),
                "kWh_final",
            )
            for vector in vector_keys
        },
    }


def _build_primary_kpis(
    config: dict[str, Any],
    energy: dict[str, Any],
    before_totals: dict[str, Any],
    after_totals: dict[str, Any],
    deltas: dict[str, Any],
    rooms: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    del before_totals, after_totals, deltas
    available = _presentation_metrics(energy, rooms)
    kpis = [
        {"label": _kpi_label(key), "metric": available[key]}
        for key in config["hero_kpis"]
        if key in available and _metric_is_relevant(available[key])
    ]
    return kpis[:3]


def _build_secondary_kpis(
    config: dict[str, Any],
    energy: dict[str, Any],
    rooms: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    available = _presentation_metrics(energy, rooms)
    return [
        {"label": _kpi_label(key), "metric": available[key]}
        for key in config.get("secondary_kpis", [])
        if key in available and _metric_is_relevant(available[key])
    ]


def _presentation_metrics(
    energy: dict[str, Any],
    rooms: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        "heating_thermal": energy["heating_thermal"],
        "heating_final": energy["heating_final"],
        "cooling_thermal": energy["cooling_thermal"],
        "cooling_electric": energy["cooling_electric"],
        "final_energy": energy["final_energy"],
        "cost": energy["cost"],
        "co2": energy["co2"],
        "hot_discomfort": _aggregate_comfort_metric(rooms, "hot_degree_hours"),
        "cold_discomfort": _aggregate_comfort_metric(rooms, "cold_degree_hours"),
        "max_temperature": _aggregate_max_temperature_metric(rooms),
    }


def _kpi_label(key: str) -> str:
    labels = {
        "heating_thermal": "Heating demand reduced",
        "heating_final": "Final heating energy",
        "cooling_thermal": "Cooling demand",
        "cooling_electric": "Electric cooling",
        "final_energy": "Final energy saved",
        "cost": "Cost saved",
        "co2": "CO₂ avoided",
        "hot_discomfort": "Hot discomfort avoided",
        "cold_discomfort": "Cold discomfort avoided",
        "max_temperature": "Maximum temperature reduced",
    }
    return labels.get(key, key)


def _metric_is_relevant(metric: dict[str, Any]) -> bool:
    return abs(float(metric.get("delta", 0.0))) > 1e-9


def _aggregate_comfort_metric(
    rooms: list[dict[str, Any]],
    summary_key: str,
) -> dict[str, Any]:
    before = sum(room["comfort"][summary_key]["before"] for room in rooms)
    after = sum(room["comfort"][summary_key]["after"] for room in rooms)
    return _metric(before, after, before - after, "°C·h")


def _aggregate_max_temperature_metric(rooms: list[dict[str, Any]]) -> dict[str, Any]:
    before = max(room["comfort"]["max_temperature_c"]["before"] for room in rooms)
    after = max(room["comfort"]["max_temperature_c"]["after"] for room in rooms)
    return _metric(before, after, before - after, "C")


def _aggregate_balance_delta(rooms: list[dict[str, Any]], summary_key: str) -> float:
    return sum(
        room["thermal_balance_deltas"][summary_key]["delta"]
        for room in rooms
    )


def _relative_delta_pct(before: float, delta: float) -> float | None:
    if before == 0:
        return None
    return round(delta / before * 100.0, 1)


def _relative_variation_pct(before: float, after: float) -> float | None:
    if before == 0:
        return None
    return round((after - before) / before * 100.0, 1)


def _effect(delta: float) -> str:
    if delta > 0:
        return "reduction"
    if delta < 0:
        return "increase"
    return "unchanged"


def _profile_id(experiment: dict[str, Any]) -> str:
    explicit_profile = experiment.get("business_profile_id")
    if explicit_profile:
        return explicit_profile
    return PROFILE_BY_ADAPTATION.get(experiment.get("adaptation_id", ""), "generic")


def _presentation_config(profile_id: str, season: str) -> dict[str, Any]:
    config = REPORT_PRESENTATION_CONFIG.get((profile_id, season))
    if config is None:
        config = REPORT_PRESENTATION_CONFIG.get((profile_id, "all"))
    if config is None:
        config = {
            "hero_kpis": ["heating_thermal", "final_energy", "cold_discomfort"],
            "secondary_kpis": ["hot_discomfort", "max_temperature"],
            "hidden_summary_kpis": [],
            "reading_template": "generic",
        }
    return {
        "profile_id": profile_id,
        "season": season,
        "hero_kpis": list(config.get("hero_kpis", [])),
        "secondary_kpis": list(config.get("secondary_kpis", [])),
        "hidden_summary_kpis": list(config.get("hidden_summary_kpis", [])),
        "reading_template": config.get("reading_template", "generic"),
        "fixed_notes": list(config.get("fixed_notes", [])),
        "conditional_notes": list(config.get("conditional_notes", [])),
        "special_sections": list(config.get("special_sections", [])),
    }


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
    season_labels = {
        "summer": "summer comfort",
        "annual": "full year",
        "winter": "winter heating",
    }
    season_label = season_labels.get(season, "winter heating")
    return f"Simulation {intervention} - {season_label}"


def _format_intervention_title(intervention: dict[str, Any]) -> str:
    if intervention["surface_overrides"]["count"]:
        fields = set(intervention["surface_overrides"]["changed_fields"])
        if "albedo" in fields:
            return "reflective roof"
        if "u_value_w_m2k" in fields:
            return "envelope insulation"
        return "envelope modification"
    if intervention["window_overrides"]["count"]:
        return "glazing improvement"
    if intervention["shutter_overrides"]["count"]:
        return "solar protection"
    if intervention["system_overrides"]["count"] or intervention["add_systems"]["count"]:
        return "thermal equipment"
    return "before/after scenario"


def _build_context_text(experiment: dict[str, Any], season: str) -> str:
    season_labels = {
        "summer": "a hot summer episode",
        "annual": "a full weather year",
        "winter": "a cold winter sequence",
    }
    season_label = season_labels.get(season, "a cold winter sequence")
    weather = experiment["weather_summary"]
    setpoint_text = _format_setpoint_text(experiment)
    return (
        f"The experiment reproduces {season_label} for "
        f"{_format_number(experiment['duration_days'])} days ({_format_number(experiment['duration_hours'])} h). "
        f"The weather used varies the outdoor temperature from "
        f"{_format_temperature(weather['outdoor_temperature_min_c'])} to "
        f"{_format_temperature(weather['outdoor_temperature_max_c'])}. The home is then "
        f"simulated twice, before and after the intervention, with the same comfort "
        f"setpoints: {setpoint_text}."
    )


def _build_purpose_text(experiment: dict[str, Any], season: str) -> str:
    if experiment.get("reason"):
        return experiment["reason"]
    if season == "summer":
        return (
            "Check whether the change reduces temperature peaks and time spent "
            "above the comfort threshold."
        )
    return (
        "Check whether the change reduces heating demand and time spent below "
        "the comfort setpoint."
    )


def _build_tested_change_text(experiment: dict[str, Any]) -> str:
    return experiment.get("adaptation_label") or _format_intervention_title(
        experiment["intervention"],
    )


def _format_scenario_summary(experiment: dict[str, Any]) -> str:
    period = _scenario_period_label(experiment)
    intervention = _scenario_intervention_label(experiment)
    return f"Thermal simulation {period} before and after {intervention}."


def _scenario_period_label(experiment: dict[str, Any]) -> str:
    weather_variant = experiment.get("weather_variant", "")
    season = experiment.get("season", "")
    if weather_variant == "openmeteo_june_september":
        return "from June to September"
    if weather_variant == "summer_long_with_heatwave":
        return "over a full summer"
    if weather_variant == "summer_heatwave" or season == "summer":
        return "during a heatwave episode"
    if weather_variant == "winter_cold" or season == "winter":
        return "during a cold winter episode"
    if weather_variant == "nsrdb_tmy":
        return "over a full typical meteorological year"
    if weather_variant in {"openmeteo_annual", "openmeteo_historical"} or season == "annual":
        return "over a full historical weather year"
    return "over the simulated period"


def _scenario_intervention_label(experiment: dict[str, Any]) -> str:
    adaptation_id = experiment.get("adaptation_id", "")
    labels = {
        "reflective_roof": "adding a reflective roof coating",
        "roof_insulation": "improving roof insulation",
        "better_windows": "replacing glazing",
        "solar_protection": "adding solar protection",
        "heat_pump": "installing a heat pump",
    }
    return labels.get(adaptation_id, "the tested change")


def _build_conclusion_text(
    experiment: dict[str, Any],
    headline: dict[str, Any],
    driver: dict[str, Any],
    most_impacted_room: dict[str, Any],
    config: dict[str, Any],
    energy: dict[str, Any],
    rooms: list[dict[str, Any]],
) -> str:
    del headline
    season = _infer_season(experiment)
    template = config["reading_template"]
    hot_discomfort = _aggregate_comfort_metric(rooms, "hot_degree_hours")
    max_temperature = _aggregate_max_temperature_metric(rooms)
    transmission_delta = _aggregate_balance_delta(rooms, "transmission_exchange")

    if template == "heat_pump":
        return (
            "The heat pump provides the same heat demand "
            f"({_format_value(energy['heating_thermal']['before'], 'kWh_th')}) "
            "with better efficiency, reducing consumed electricity by "
            f"{_format_pct(energy['final_energy'])}."
        )
    if template == "roof_insulation_winter":
        if season == "annual":
            return (
                "Insulation reduces annual heating demand by "
                f"{_format_pct(energy['heating_thermal'])}. "
                "Summer comfort remains shown separately to avoid mixing effects."
            )
        return (
            "Insulation reduces heating demand by "
            f"{_format_pct(energy['heating_thermal'])}. "
            "The summer impact should be read separately."
        )
    if template == "roof_insulation_summer":
        return (
            "Insulation alone has a limited effect in summer. Combined with shutters "
            "and night ventilation, the effect on overheating becomes more significant."
        )
    if template == "reflective_roof":
        return (
            "The reflective coating reduces summer discomfort by "
            f"{_format_pct(hot_discomfort)}. The impact on the annual bill is secondary."
        )
    if template == "solar_protection":
        return (
            "Solar protection reduces hot discomfort by "
            f"{_format_pct(hot_discomfort)}."
        )
    if template == "windows_winter":
        return (
            "High-performance glazing reduces transmission losses by "
            f"{_format_value(max(0.0, transmission_delta), 'kWh')} over the period."
        )
    if template == "windows_summer":
        return (
            "High-performance glazing reduces gains and temperature peaks "
            f"by up to {_format_delta(max_temperature)} over this hot sequence."
        )
    if template == "windows_annual":
        return (
            "Window replacement acts on winter losses and summer comfort. "
            "The annual balance combines both effects."
        )

    if season == "summer":
        return (
            f"The most temperature-sensitive room is {most_impacted_room['room_name']}. "
            f"The main explanatory factor identified is: {driver['label']}."
        )
    return (
        "The change acts on the home's thermal balance. "
        f"The main explanatory factor identified is: {driver['label']}."
    )


def _format_experiment_role(experiment: dict[str, Any]) -> str:
    role_labels = {
        "primary": "Main experiment",
        "secondary": "Secondary experiment",
        "annual": "Annual experiment",
    }
    role_label = role_labels.get(experiment.get("role"), "Experiment")
    label = experiment.get("label") or "simulation"
    reason = experiment.get("reason") or "No specific reason provided."
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
    Determine the dominant comfort mode for the experiment.
    "hot"   -> hot episode, discomfort threshold = 26°C
    "cold"  -> cold episode, discomfort threshold = 18°C
    "mixed" -> hybrid, for example windows with summer and winter experiments
    """
    total_hot = experiment_data.get("total_hot_discomfort_before", 0)
    total_cold = experiment_data.get("total_cold_discomfort_before", 0)
    if total_hot > 0 or total_cold > 0:
        return "hot" if total_hot >= total_cold else "cold"

    season = experiment_data.get("season", "")

    if season in ("summer", "summer_heatwave"):
        return "hot"
    if season in ("winter", "winter_cold"):
        return "cold"

    return "hot"


def get_room_status(room_data: dict, comfort_mode: str) -> tuple[str, str]:
    """
    Return (label, css_class).
    Keep the existing hot logic and add cold.
    """
    if comfort_mode == "hot":
        temp_max = room_data.get("temp_max_before", 0)
        dh_reduction_pct = room_data.get("hot_dh_reduction_pct", 0)
        if temp_max > 35:
            return ("Critical", "status-critical")
        if dh_reduction_pct > 30:
            return ("Improved", "status-improved")
        return ("Stable", "status-stable")

    if comfort_mode in ("cold", "mixed"):
        temp_min = room_data.get("temp_min_before", 99)
        dh_reduction_pct = room_data.get("cold_dh_reduction_pct", 0)
        if temp_min < 16:
            return ("Critical", "status-critical")
        if dh_reduction_pct > 30:
            return ("Improved", "status-improved")
        return ("Stable", "status-stable")

    return ("Stable", "status-stable")


def _render_executive_summary(report: dict[str, Any]) -> str:
    primary_kpis = report["primary_kpis"]
    if not primary_kpis:
        return '<div class="info-note">No significant summary indicator over this period.</div>'
    return f"""
      <div class="summary-grid">
        {"".join(_render_kpi(kpi["label"], kpi["metric"]) for kpi in primary_kpis)}
      </div>
"""


def _render_kpi(label: str, metric: dict[str, Any]) -> str:
    value_class = _value_class(metric["delta"])
    return f"""
        <div class="kpi">
          <div class="label">{escape(label)}</div>
          <div class="kpi-value {value_class}">{_format_delta(metric)}</div>
          <div class="kpi-sub">{_format_before_after(metric)}</div>
          <div class="kpi-sub">{_format_pct(metric)} variation</div>
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
    Return the alert banner HTML, or None when there is no alert.
    Keep the existing hot logic and add cold logic.
    """
    hot_critical = [room for room in rooms if room.get("temp_max_before", 0) > 35]
    if hot_critical:
        room = hot_critical[0]
        return f"""
    <section class="alert alert-hot">
      <strong>Thermal comfort alert.</strong>
      Room <strong>{escape(room['name'])}</strong> exceeds 35 °C in the simulation, with a maximum of {_format_temperature(room['temp_max_before'])}.
    </section>
"""

    cold_critical = [room for room in rooms if room.get("temp_min_before", 99) < 16]
    if cold_critical:
        room = cold_critical[0]
        return f"""
    <section class="alert alert-cold">
      <strong>Thermal comfort alert.</strong>
      Room <strong>{escape(room['name'])}</strong> drops below 16 °C in the simulation, with a minimum of {_format_temperature(room['temp_min_before'])}.
    </section>
"""

    return None


def _render_context_params(
    experiment: dict[str, Any],
    temperature_profiles: dict[str, Any],
) -> str:
    weather = experiment["weather_summary"]
    trace = experiment.get("weather_trace", {})
    thresholds = temperature_profiles["thresholds"]
    rows = [
        ("Duration", _format_duration(experiment)),
        (
            "Weather",
            (
                f"{_format_temperature(weather['outdoor_temperature_min_c'])} → "
                f"{_format_temperature(weather['outdoor_temperature_max_c'])}"
            ),
        ),
        ("Weather basis", escape(_weather_basis_label(trace, experiment))),
        ("Weather source", escape(_weather_source_label(trace, experiment))),
        ("Weather grid cell", escape(_weather_location_label(trace))),
        ("Timezone", escape(str(trace.get("timezone", "Not recorded")))),
        ("Weather model", escape(str(trace.get("model", "Not recorded")))),
        ("Weather station/grid", escape(str(trace.get("station", "Not recorded")))),
        (
            "Building-code climate zone",
            escape(_climate_zone_label(experiment)),
        ),
        (
            "Reproducibility",
            escape(
                f"Engine {trace.get('engine_version', '1r1c-mvp-0.1')} · "
                f"weather {str(trace.get('hourly_sha256', 'not recorded'))[:16]}"
            ),
        ),
        (
            "Setpoints",
            _format_setpoint_text(experiment),
        ),
        (
            "Discomfort threshold",
            (
                f"Hot {_format_temperature(thresholds['hot_c'])}, "
                f"cold {_format_temperature(thresholds['cold_c'])}"
            ),
        ),
        ("Tested change", escape(experiment["tested_change_text"])),
    ]
    table_rows = "\n".join(
        f"<tr><td>{escape(label)}</td><td>{value}</td></tr>"
        for label, value in rows
    )
    return f"<table>{table_rows}</table>"


def _weather_basis_label(trace: dict[str, Any], experiment: dict[str, Any]) -> str:
    if trace.get("weather_type") == "typical":
        return f"Typical meteorological year ({trace.get('weather_reference', 'TMY')})"
    year = trace.get("year") or experiment.get("weather_year")
    if trace.get("weather_type") == "historical" or year:
        return f"Historical weather year {year}"
    return "Synthetic weather scenario"


def _weather_source_label(trace: dict[str, Any], experiment: dict[str, Any]) -> str:
    return _join_non_empty(
        trace.get("provider"),
        trace.get("dataset"),
        experiment.get("weather_source"),
    )


def _weather_location_label(trace: dict[str, Any]) -> str:
    latitude = trace.get("latitude")
    longitude = trace.get("longitude")
    if latitude is None or longitude is None:
        return "Not recorded"
    return f"{latitude:.1f}, {longitude:.1f} (shared 0.1° cell)"


def _climate_zone_label(experiment: dict[str, Any]) -> str:
    code = experiment.get("climate_zone_code")
    standard = experiment.get("climate_zone_standard")
    county = experiment.get("county")
    if not code:
        return "Not recorded"
    context = _join_non_empty(f"Zone {code}", standard, county)
    return f"{context} — building-code metadata only; local weather is used separately"


def _build_presentation_notes(
    config: dict[str, Any],
    experiment: dict[str, Any],
    energy: dict[str, Any],
    rooms: list[dict[str, Any]],
) -> dict[str, Any]:
    del experiment
    context_notes = []
    effect_notes = []
    hot_discomfort = _aggregate_comfort_metric(rooms, "hot_degree_hours")

    for note_key in config.get("fixed_notes", []):
        if note_key == "roof_summer_limited":
            effect_notes.append({
                "title": "Summer effect of insulation alone",
                "text": (
                    "Insulation alone has a limited effect in summer. Combined with shutters "
                    "or night ventilation, the effect on overheating becomes significant."
                ),
            })
        elif note_key == "windows_winter_scope":
            context_notes.append(
                "This report covers the winter effect. See the summer report for "
                "the effect on summer comfort.",
            )
        elif note_key == "windows_summer_scope":
            context_notes.append(
                "High-performance glazing reduces direct solar gains in summer. "
                "The effect on comfort depends on orientation and exposed glazed area.",
            )
        elif note_key == "roof_insulation_annual_scope":
            context_notes.append(
                "This annual report estimates demand before/after roof insulation "
                "with the same weather dataset and the same setpoints. It does not replace "
                "an EPC, an energy audit, or a regulatory study.",
            )

    for note_key in config.get("conditional_notes", []):
        heating_delta = energy["heating_final"]["delta"]
        if heating_delta >= 0:
            continue
        heating_increase = _format_value(abs(heating_delta), "kWh_final")
        if note_key == "reduced_winter_solar_gains":
            effect_notes.append({
                "title": "Why does heating increase slightly?",
                "text": (
                    "The reflective coating also limits free solar gains in winter "
                    f"({heating_increase} of extra heating). "
                    "Over the year, the comfort balance remains very favorable."
                ),
            })
        elif note_key == "blocked_winter_solar_gains":
            effect_notes.append({
                "title": "Why does heating increase slightly?",
                "text": (
                    "Shutters also block free solar gains in winter "
                    f"({heating_increase} of extra heating). Over the year, the comfort "
                    "gain remains the main argument."
                ),
            })

    if (
        config["profile_id"] == "roof_insulation_seller"
        and config["season"] == "annual"
        and hot_discomfort["delta"] < 0
    ):
        effect_notes.append({
            "title": "Summer impact",
            "text": (
                "Insulation also slows heat release in summer. "
                "Combine it with shutters or night ventilation."
            ),
        })

    return {
        "config": config,
        "context_notes": context_notes,
        "effect_notes": effect_notes,
    }


def _render_profile_notes(report: dict[str, Any]) -> str:
    notes = report["presentation"]["context_notes"]
    if not notes:
        return ""
    return "\n".join(
        f'<div class="info-note">{_format_prose_html(note)}</div>'
        for note in notes
    )


def _render_short_scenario_note(experiment: dict[str, Any]) -> str:
    if experiment.get("role") == "annual" or experiment.get("duration_days", 0.0) >= 30:
        return ""
    return """
      <div class="info-note">
        Costs shown correspond to the simulated period. For a 12-month estimate,
        see the annual report.
      </div>
"""


def _render_contextual_notes(report: dict[str, Any]) -> str:
    notes = report["presentation"]["effect_notes"]
    if not notes:
        return ""
    return "\n".join(
        f"""
      <div class="context-note">
        <strong>{escape(note['title'])}</strong>
        <p>{_format_prose_html(note['text'])}</p>
      </div>
"""
        for note in notes
    )


def _render_special_sections(report: dict[str, Any]) -> str:
    config = report["presentation"]["config"]
    if "windows_double_effect" not in config.get("special_sections", []):
        return ""
    energy = report["energy_breakdown"]
    hot_discomfort = _aggregate_comfort_metric(report["rooms"], "hot_degree_hours")
    return f"""
      <div class="info-note">
        <strong>Double effect.</strong>
        Winter: {_format_delta(energy["heating_final"])} saved.
        Summer: {_format_delta(hot_discomfort)} of hot discomfort avoided.
      </div>
"""


def _format_setpoint_text(experiment: dict[str, Any]) -> str:
    setpoints = experiment["setpoints"]
    parts = [f"Heating {_format_temperature(setpoints['heating_c'])}"]
    if experiment.get("has_cooling"):
        day = setpoints.get("cooling_day_c")
        night = setpoints.get("cooling_night_c")
        if day is not None and night is not None:
            parts.append(
                "cooling "
                f"{_format_temperature(day)} during the day, "
                f"{_format_temperature(night)} at night",
            )
        else:
            parts.append(f"cooling {_format_temperature(setpoints['cooling_c'])}")
    return ", ".join(parts)


def _render_results_sections(report: dict[str, Any]) -> str:
    return "\n".join([
        _render_needs_result_block(report),
        _render_energy_cost_result_block(report),
        _render_comfort_result_block(report),
    ])


def _render_result_block(title: str, body_html: str, note: str = "") -> str:
    if not body_html:
        return ""
    note_html = f'<div class="info-note">{_format_prose_html(note)}</div>' if note else ""
    return f"""
      <div class="result-block">
        <h3>{escape(title)}</h3>
        {note_html}
        {body_html}
      </div>
"""


def _render_needs_result_block(report: dict[str, Any]) -> str:
    energy = report["energy_breakdown"]
    return _render_result_block(
        "Home Demand",
        _render_metric_table([
            ("Thermal heating demand", energy["heating_thermal"]),
            ("Thermal cooling demand", energy["cooling_thermal"]),
        ]),
        (
            "Thermal demand = heat to provide or remove to hold the setpoint. "
            "Thermal demand depends on the envelope and weather, "
            "not on the heating system."
        ),
    )


def _render_energy_cost_result_block(report: dict[str, Any]) -> str:
    energy = report["energy_breakdown"]
    vector_rows = [
        (f"Final energy {_energy_vector_label(vector)}", metric)
        for vector, metric in energy["final_energy_by_vector"].items()
    ]
    return _render_result_block(
        "Energy and Cost",
        _render_metric_table(
            vector_rows
            + [
                ("Total final energy", energy["final_energy"]),
                ("Estimated cost", energy["cost"]),
                ("CO₂", energy["co2"]),
            ],
        ),
        (
            "Final energy = billed energy after system efficiency or COP. "
            "In the table, variation is calculated as after - before: a positive value "
            "means an increase, a negative value means a decrease."
        ),
    )


def _render_comfort_result_block(report: dict[str, Any]) -> str:
    return _render_result_block(
        "Thermal Comfort",
        _render_comfort_result_table(report),
    )


def _energy_vector_label(vector: str) -> str:
    labels = {
        "electricity": "electricity",
        "gas": "gas",
        "fuel_oil": "oil",
        "wood": "wood",
    }
    return labels.get(vector, vector.replace("_", " "))


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
            "Maximum temperature",
            _metric(max_before, max_after, max_before - max_after, "C"),
        ),
        (
            "Cumulative discomfort hours (hot)",
            _metric(hot_before, hot_after, hot_before - hot_after, "°C·h"),
        ),
        (
            "Cumulative discomfort hours (cold)",
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
              ("Maximum temperature", comfort["max_temperature_c"]),
              ("Final temperature", comfort["final_temperature_c"]),
              ("Cumulative discomfort hours (hot)", comfort["hot_degree_hours"]),
              ("Cumulative discomfort hours (cold)", comfort["cold_degree_hours"]),
          ])}
          {_render_delta_table([
              ("Solar gains", balance["solar_gain"]),
              ("Transmission losses", balance["transmission_exchange"]),
              ("Ventilation losses", balance["ventilation_exchange"]),
              ("Thermal heating", balance["heating_thermal"]),
              ("Thermal cooling", balance["cooling_thermal"]),
          ])}
        </div>
      </div>
"""


def _render_temperature_profile_html(profile: dict[str, Any], comfort_mode: str) -> str:
    summary = profile["summary"]
    status_label, status_class = _room_status(profile, comfort_mode)
    if profile.get("aggregation") == "daily_max":
        discomfort_note = (
            "Main curves show daily maximum temperature; thin lines = "
            "daily indoor average; outdoor = daily maximum; "
            "colored area = discomfort present before and avoided after."
        )
    elif profile.get("x_axis", {}).get("type") in {"annual", "season_months"}:
        discomfort_note = (
            "Curves show daily average, including outdoor temperature; shaded area = "
            "simulated min/max range for each day."
        )
    elif comfort_mode == "hot":
        before_value = summary["before_hot_degree_hours"]
        after_value = summary["after_hot_degree_hours"]
        discomfort_note = (
            "Cumulative discomfort hours: "
            f"{_format_value(before_value, '°C·h')} → {_format_value(after_value, '°C·h')} "
            f"({_format_signed_pct(_reduction_pct(before_value, after_value))}). "
            "Colored area = discomfort present before and avoided after."
        )
    else:
        before_value = summary["before_cold_degree_hours"]
        after_value = summary["after_cold_degree_hours"]
        discomfort_note = (
            "Cumulative discomfort hours: "
            f"{_format_value(before_value, '°C·h')} → {_format_value(after_value, '°C·h')} "
            f"({_format_signed_pct(_reduction_pct(before_value, after_value))}). "
            "Colored area = discomfort present before and avoided after."
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


def _render_temperature_charts_intro(profiles: list[dict[str, Any]]) -> str:
    if not profiles:
        return ""
    aggregations = {profile.get("aggregation") for profile in profiles}
    if aggregations == {"daily_max"}:
        note = (
            "The curves show the maximum temperature for each day. "
            "Daily indoor averages are shown as thin lines for context."
        )
    elif aggregations == {"hourly"}:
        note = "The curves show the simulated temperature hour by hour."
    elif aggregations == {"daily_average"}:
        note = (
            "The curves show the average temperature for each day. "
            "The shaded area indicates the simulated min/max range."
        )
    else:
        return ""
    return f'<p class="section-note">{escape(note)}</p>'


def _render_temperature_svg(profile: dict[str, Any], comfort_mode: str) -> str:
    points = profile["points"]
    x_axis = profile.get("x_axis", {})
    width = 1040
    height = 370
    left = 54
    right = 24
    legend_y = 26
    top = 70
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
            point.get("before_min_temperature_c", point["before_temperature_c"]),
            point.get("before_max_temperature_c", point["before_temperature_c"]),
            point.get("after_min_temperature_c", point["after_temperature_c"]),
            point.get("after_max_temperature_c", point["after_temperature_c"]),
            point.get("before_average_temperature_c", point["before_temperature_c"]),
            point.get("after_average_temperature_c", point["after_temperature_c"]),
        )
    ]
    threshold = _chart_threshold(profile, comfort_mode)
    values.append(threshold["value"])
    y_min = min(values) - 1.0
    y_max = max(values) + 1.0
    if y_max == y_min:
        y_max += 1.0

    min_hour = x_axis.get("min_hour", points[0]["hour"] if points else 0)
    max_hour = x_axis.get("max_hour", points[-1]["hour"] if points else 1)

    def x_at_hour(hour: float) -> float:
        if max_hour == min_hour:
            return left
        return left + (hour - min_hour) / (max_hour - min_hour) * plot_width

    def y_at(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * plot_height

    outdoor_line = _svg_polyline(
        (x_at_hour(point["hour"]), y_at(point["outdoor_temperature_c"]))
        for point in points
    )
    before_line = _svg_polyline(
        (x_at_hour(point["hour"]), y_at(point["before_temperature_c"]))
        for point in points
    )
    after_line = _svg_polyline(
        (x_at_hour(point["hour"]), y_at(point["after_temperature_c"]))
        for point in points
    )
    average_lines = _svg_average_temperature_lines(points, x_at_hour, y_at)
    range_bands = _svg_daily_range_bands(points, x_at_hour, y_at)
    before_peak_index, before_peak = _peak(points, "before_temperature_c", comfort_mode)
    after_peak_index, after_peak = _peak(points, "after_temperature_c", comfort_mode)
    discomfort_rects = _svg_discomfort_rects(
        points,
        profile["primary_discomfort"],
        x_at_hour,
        top,
        plot_height,
    )
    season_zones = _svg_season_zones(x_axis, x_at_hour, top, plot_height)
    grid = _svg_grid_lines(y_min, y_max, left, top, plot_width, plot_height)
    threshold_line = _svg_threshold_line(
        threshold,
        left,
        left + plot_width,
        y_at(threshold["value"]),
    )
    x_labels = _svg_x_labels(points, x_axis, x_at_hour, height, bottom)
    legend = _svg_legend(
        left + 18,
        legend_y,
        profile["primary_discomfort"],
        threshold,
        profile.get("aggregation", "hourly"),
    )
    annotations = get_svg_annotation(
        x_at_hour(points[before_peak_index]["hour"]),
        y_at(before_peak),
        before_peak,
        x_at_hour(points[after_peak_index]["hour"]),
        y_at(after_peak),
        after_peak,
        width,
        comfort_mode,
    )
    critical_markers = _svg_critical_markers(profile, x_at_hour, y_at)

    return f"""
          <svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Temperature curves - {escape(profile["room_name"])}">
            <rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"></rect>
            {season_zones}
            {discomfort_rects}
            {grid}
            {threshold_line}
            {range_bands}
            {average_lines}
            <polyline points="{outdoor_line}" fill="none" stroke="#64748b" stroke-width="2" stroke-dasharray="5 5"></polyline>
            <polyline points="{before_line}" fill="none" stroke="#1d4ed8" stroke-width="2.5"></polyline>
            <polyline points="{after_line}" fill="none" stroke="#15803d" stroke-width="2.5"></polyline>
            <circle cx="{x_at_hour(points[before_peak_index]["hour"]):.1f}" cy="{y_at(before_peak):.1f}" r="3.5" fill="#1d4ed8"></circle>
            <circle cx="{x_at_hour(points[after_peak_index]["hour"]):.1f}" cy="{y_at(after_peak):.1f}" r="3.5" fill="#15803d"></circle>
            {critical_markers}
            {annotations}
            {legend}
            <line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#cbd5e1"></line>
            <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#cbd5e1"></line>
            {x_labels}
          </svg>
"""


def _chart_threshold(profile: dict[str, Any], comfort_mode: str) -> dict[str, Any]:
    primary = profile["primary_discomfort"]
    if comfort_mode == "cold" or primary == "cold":
        value = profile["thresholds"]["cold_c"]
        return {
            "value": value,
            "label": f"Cold threshold {_format_temperature(value)}",
            "color": "#2563eb",
        }
    value = profile["thresholds"]["hot_c"]
    return {
        "value": value,
        "label": f"Hot threshold {_format_temperature(value)}",
        "color": "#dc2626",
    }


def _svg_polyline(points: Any) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def _svg_threshold_line(
    threshold: dict[str, Any],
    x1: float,
    x2: float,
    y: float,
) -> str:
    return (
        f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" '
        f'stroke="{threshold["color"]}" stroke-width="1.4" stroke-dasharray="6 5" opacity="0.85"></line>'
        f'<text x="{x2 - 6:.1f}" y="{y - 6:.1f}" text-anchor="end" font-size="11" '
        f'fill="{threshold["color"]}">{escape(threshold["label"])}</text>'
    )


def _svg_daily_range_bands(
    points: list[dict[str, Any]],
    x_at_hour: Any,
    y_at: Any,
) -> str:
    if not points or "before_min_temperature_c" not in points[0]:
        return ""
    return "\n".join(
        [
            _svg_range_band(
                points,
                x_at_hour,
                y_at,
                "before_min_temperature_c",
                "before_max_temperature_c",
                "#1d4ed8",
            ),
            _svg_range_band(
                points,
                x_at_hour,
                y_at,
                "after_min_temperature_c",
                "after_max_temperature_c",
                "#15803d",
            ),
        ],
    )


def _svg_range_band(
    points: list[dict[str, Any]],
    x_at_hour: Any,
    y_at: Any,
    min_key: str,
    max_key: str,
    color: str,
) -> str:
    top_points = [
        (x_at_hour(point["hour"]), y_at(point[max_key]))
        for point in points
    ]
    bottom_points = [
        (x_at_hour(point["hour"]), y_at(point[min_key]))
        for point in reversed(points)
    ]
    polygon_points = _svg_polyline([*top_points, *bottom_points])
    return f'<polygon points="{polygon_points}" fill="{color}" opacity="0.12"></polygon>'


def _svg_critical_markers(
    profile: dict[str, Any],
    x_at_hour: Any,
    y_at: Any,
) -> str:
    markers = []
    for marker in profile.get("critical_markers", []):
        fill = "#dc2626" if marker["type"] == "hot" else "#2563eb"
        markers.append(
            f'<circle cx="{x_at_hour(marker["hour"]):.1f}" '
            f'cy="{y_at(marker["value"]):.1f}" r="3" fill="{fill}">'
            f'<title>{escape(marker["tooltip"])}</title>'
            '</circle>'
        )
    return "\n".join(markers)


def _svg_average_temperature_lines(
    points: list[dict[str, Any]],
    x_at_hour: Any,
    y_at: Any,
) -> str:
    if not points or "before_average_temperature_c" not in points[0]:
        return ""
    before_average_line = _svg_polyline(
        (x_at_hour(point["hour"]), y_at(point["before_average_temperature_c"]))
        for point in points
    )
    after_average_line = _svg_polyline(
        (x_at_hour(point["hour"]), y_at(point["after_average_temperature_c"]))
        for point in points
    )
    return "\n".join(
        [
            f'<polyline points="{before_average_line}" fill="none" stroke="#1d4ed8" stroke-width="1.1" opacity="0.36"></polyline>',
            f'<polyline points="{after_average_line}" fill="none" stroke="#15803d" stroke-width="1.1" opacity="0.36"></polyline>',
        ],
    )


def _svg_discomfort_rects(
    points: list[dict[str, Any]],
    primary_discomfort: str,
    x_at_hour: Any,
    top: float,
    plot_height: float,
) -> str:
    rects = []
    start = None
    for index, point in enumerate(points):
        if primary_discomfort == "hot":
            is_uncomfortable = (
                point["before_hot_excess_c"] > 0 and point["after_hot_excess_c"] == 0
            )
        else:
            is_uncomfortable = (
                point["before_cold_excess_c"] > 0 and point["after_cold_excess_c"] == 0
            )
        if is_uncomfortable and start is None:
            start = index
        if start is not None and (not is_uncomfortable or index == len(points) - 1):
            end = index if is_uncomfortable else index - 1
            x = x_at_hour(points[start]["hour"])
            end_point = points[end]
            next_hour = end_point["hour"] + end_point.get("duration_h", 1.0)
            next_x = x_at_hour(next_hour)
            width = max(4.0, next_x - x)
            fill = "#fee2e2" if primary_discomfort == "hot" else "#dbeafe"
            rects.append(
                f'<rect x="{x:.1f}" y="{top:.1f}" width="{width:.1f}" '
                f'height="{plot_height:.1f}" fill="{fill}" opacity="0.30"></rect>'
            )
            start = None
    return "\n".join(rects)


def _svg_season_zones(
    x_axis: dict[str, Any],
    x_at_hour: Any,
    top: float,
    plot_height: float,
) -> str:
    zones = []
    for zone in x_axis.get("zones", []):
        x = x_at_hour(zone["start_hour"])
        width = max(0.0, x_at_hour(zone["end_hour"]) - x)
        zones.append(
            f'<rect x="{x:.1f}" y="{top:.1f}" width="{width:.1f}" '
            f'height="{plot_height:.1f}" fill="rgba(255, 160, 0, 0.08)"></rect>'
        )
        zones.append(
            f'<text x="{x + 8:.1f}" y="{top + 16:.1f}" font-size="11" '
            f'fill="#9a6700">{escape(zone["label"])}</text>'
        )
    return "\n".join(zones)


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
    x_axis: dict[str, Any],
    x_at_hour: Any,
    height: float,
    bottom: float,
) -> str:
    if not points:
        return ""
    if x_axis.get("type") in {"annual", "season_months"}:
        return "\n".join(
            f'<text x="{x_at_hour(hour):.1f}" y="{height - bottom + 24:.1f}" '
            f'text-anchor="middle" font-size="11" fill="#64748b">{escape(label)}</text>'
            for label, hour in x_axis.get("labels", [])
        )
    indexes = sorted({0, len(points) // 2, len(points) - 1})
    labels = []
    for index in indexes:
        labels.append(
            f'<text x="{x_at_hour(points[index]["hour"]):.1f}" y="{height - bottom + 24:.1f}" '
            f'text-anchor="middle" font-size="11" fill="#64748b">h{points[index]["hour"]}</text>'
        )
    return "\n".join(labels)


def _svg_legend(
    x: float,
    y: float,
    primary_discomfort: str,
    threshold: dict[str, Any],
    aggregation: str,
) -> str:
    zone_fill = "#fee2e2" if primary_discomfort == "hot" else "#dbeafe"
    outdoor_label = "Outdoor max/day" if aggregation == "daily_max" else "Outdoor"
    before_label = "Before max/day" if aggregation == "daily_max" else "Before"
    after_label = "After max/day" if aggregation == "daily_max" else "After"
    avoided_label = "Discomfort avoided"
    average_legend = ""
    legend_width = 746
    threshold_x = x + 560
    threshold_label_x = x + 590
    if aggregation == "daily_max":
        average_legend = (
            f'<line x1="{x + 528:.1f}" y1="{y:.1f}" x2="{x + 552:.1f}" y2="{y:.1f}" '
            'stroke="#334155" stroke-width="1.1" opacity="0.36"></line>'
            f'<text x="{x + 558:.1f}" y="{y + 4:.1f}" font-size="11" fill="#475569">Indoor avg/day</text>'
        )
        legend_width = 900
        threshold_x = x + 674
        threshold_label_x = x + 704
    return f"""
            <g aria-hidden="true">
              <rect x="{x - 10:.1f}" y="{y - 14:.1f}" width="{legend_width}" height="26" rx="5" fill="#ffffff" stroke="#e2e8f0"></rect>
              <line x1="{x:.1f}" y1="{y:.1f}" x2="{x + 24:.1f}" y2="{y:.1f}" stroke="#64748b" stroke-width="2" stroke-dasharray="5 5"></line>
              <text x="{x + 30:.1f}" y="{y + 4:.1f}" font-size="11" fill="#475569">{escape(outdoor_label)}</text>
              <line x1="{x + 104:.1f}" y1="{y:.1f}" x2="{x + 128:.1f}" y2="{y:.1f}" stroke="#1d4ed8" stroke-width="2.5"></line>
              <text x="{x + 134:.1f}" y="{y + 4:.1f}" font-size="11" fill="#475569">{escape(before_label)}</text>
              <line x1="{x + 234:.1f}" y1="{y:.1f}" x2="{x + 258:.1f}" y2="{y:.1f}" stroke="#15803d" stroke-width="2.5"></line>
              <text x="{x + 264:.1f}" y="{y + 4:.1f}" font-size="11" fill="#475569">{escape(after_label)}</text>
              <rect x="{x + 366:.1f}" y="{y - 7:.1f}" width="22" height="12" fill="{zone_fill}" opacity="0.8"></rect>
              <text x="{x + 394:.1f}" y="{y + 4:.1f}" font-size="11" fill="#475569">{escape(avoided_label)}</text>
              {average_legend}
              <line x1="{threshold_x:.1f}" y1="{y:.1f}" x2="{threshold_x + 24:.1f}" y2="{y:.1f}" stroke="{threshold["color"]}" stroke-width="1.4" stroke-dasharray="6 5"></line>
              <text x="{threshold_label_x:.1f}" y="{y + 4:.1f}" font-size="11" fill="#475569">{escape(threshold["label"])}</text>
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
        f"Before peak {_format_temperature(before_value)}"
        if comfort_mode == "hot"
        else f"Before min. {_format_temperature(before_value)}"
    )
    after_label = (
        f"After peak {_format_temperature(after_value)}"
        if comfort_mode == "hot"
        else f"After min. {_format_temperature(after_value)}"
    )
    return f"""
            <text x="{before_label_x:.1f}" y="{before_label_y:.1f}" font-size="11" fill="#1d4ed8">{escape(before_label)}</text>
            <text x="{after_label_x:.1f}" y="{after_label_y:.1f}" font-size="11" fill="#15803d">{escape(after_label)}</text>
"""


def _render_metric_table(rows: list[tuple[str, dict[str, Any]]]) -> str:
    rows = [
        (label, metric)
        for label, metric in rows
        if _metric_has_display_value(metric)
    ]
    if not rows:
        return ""
    table_rows = "\n".join(
        "<tr>"
        f"<td>{escape(label)}</td>"
        f"<td>{_format_value(metric['before'], metric['unit'])}</td>"
        f"<td>{_format_value(metric['after'], metric['unit'])}</td>"
        f"<td class=\"{_value_class(metric['delta'])}\">"
        f"<span class=\"value-main\">{_format_variation_pct(metric)}</span>"
        f"<span class=\"value-sub\">{_format_variation(metric)}</span>"
        "</td>"
        "</tr>"
        for label, metric in rows
    )
    return f"""
      <table class="data-table">
        <thead>
          <tr>
            <th>Indicator</th>
            <th>Before</th>
            <th>After</th>
            <th>Variation</th>
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
"""


def _render_delta_table(rows: list[tuple[str, dict[str, Any]]]) -> str:
    rows = [
        (label, metric)
        for label, metric in rows
        if _metric_has_display_value(metric)
    ]
    if not rows:
        return ""
    table_rows = "\n".join(
        "<tr>"
        f"<td>{escape(label)}</td>"
        f"<td class=\"{_value_class(metric['delta'])}\">{_format_variation(metric)}</td>"
        "</tr>"
        for label, metric in rows
    )
    return f"""
      <table class="data-table">
        <thead>
          <tr>
            <th>Technical delta</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
"""


def _metric_has_display_value(metric: dict[str, Any]) -> bool:
    return any(
        abs(float(metric.get(key, 0.0))) > 1e-9
        for key in ("before", "after", "delta")
    )


def _format_before_after(metric: dict[str, Any]) -> str:
    return (
        f"Before {_format_value(metric['before'], metric['unit'])} - "
        f"after {_format_value(metric['after'], metric['unit'])}"
    )


def _format_prose_html(text: str) -> str:
    return escape(text).replace(". ", ".<br>")


def _format_delta(metric: dict[str, Any]) -> str:
    return _format_value(metric["delta"], metric["unit"])


def _format_variation(metric: dict[str, Any]) -> str:
    variation = metric.get("variation")
    if variation is None:
        variation = -metric["delta"]
    return _format_value(variation, metric["unit"])


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


def _format_variation_pct(metric: dict[str, Any]) -> str:
    value = metric.get("relative_variation_pct")
    if value is None:
        relative_delta = metric.get("relative_delta_pct")
        value = None if relative_delta is None else -relative_delta
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
        "kWh_final": "kWh final",
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
        "surface_overrides": "modified surfaces",
        "window_overrides": "modified windows",
        "shutter_overrides": "modified solar protection",
        "system_overrides": "modified systems",
        "add_systems": "added systems",
    }
    for key, label in labels.items():
        item = intervention[key]
        if item["count"]:
            fields = ", ".join(item["changed_fields"]) or "parameters"
            parts.append(f"{item['count']} {label} ({fields})")
    if not parts:
        return "no technical change applied"
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
