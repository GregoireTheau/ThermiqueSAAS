from thermal_model import load_dwelling, load_reference_catalog, resolve_dwelling_references
from scripts.compute_static_losses import compute_dwelling_static_losses


def test_compute_static_losses_house_simple_total():
    catalog = load_reference_catalog()
    dwelling = load_dwelling("data/examples/house_simple.json", validate=False)
    dwelling = resolve_dwelling_references(dwelling, catalog)

    results = compute_dwelling_static_losses(
        dwelling,
        indoor_temperature_c=20.0,
        outdoor_temperature_c=0.0,
        air_density_kg_m3=1.2,
        air_heat_capacity_j_kgk=1005.0,
    )

    assert round(results["totals"]["total_h_w_k"], 1) == 114.0
    assert round(results["totals"]["total_loss_w"]) == 2281
