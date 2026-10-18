from pathlib import Path

import pytest

pytest.importorskip("flask")
gpd = pytest.importorskip("geopandas")

from app import create_app
from app.modules import municipal

ROOT = Path(__file__).resolve().parents[1]
PROPERTIES = {"CVEGEO", "estado", "municipio", "esperado", "p10", "p90", "prob_bajo_2", "confianza",
              "siap_media", "siap_anios", "siap_frac_bajo_2", "dist_siap_km", "con_siap",
              "dentro_rango_ambiental", "dentro_dominio", "modelo", "escala", "anio_referencia"}


@pytest.fixture(scope="module")
def client():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def municipios(client):
    return client.get("/api/municipal").get_json()["features"]


def test_municipal_geojson(client):
    res = client.get("/api/municipal")
    assert res.status_code == 200
    assert res.mimetype == "application/geo+json"
    assert res.headers["Cache-Control"] == "public, max-age=3600"
    data = res.get_json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 486
    # NaN no es JSON válido: debe salir como null
    assert "NaN" not in res.get_data(as_text=True)


def test_municipal_cvegeo_unique(municipios):
    ids = [f["properties"]["CVEGEO"] for f in municipios]
    assert len(set(ids)) == 486
    assert all(len(i) == 5 and i.isdigit() for i in ids)


def test_municipal_properties(municipios):
    assert all(set(f["properties"]) == PROPERTIES for f in municipios)


def test_municipal_esperado_null_outside_range(municipios):
    props = [f["properties"] for f in municipios]
    assert sum(p["esperado"] is not None for p in props) == 268
    assert sum(p["esperado"] is None for p in props) == 218
    assert all((p["esperado"] is None) == (not p["dentro_rango_ambiental"]) for p in props)


def test_municipal_confianza_values(municipios):
    assert all(f["properties"]["confianza"] in {"alta", "media", "baja", None} for f in municipios)


def test_municipal_interval_and_probability(municipios):
    props = [f["properties"] for f in municipios if f["properties"]["esperado"] is not None]
    assert all(p["p10"] <= p["esperado"] <= p["p90"] for p in props)
    assert all(0 <= p["prob_bajo_2"] <= 1 for p in props)


def test_municipal_size(client):
    assert len(client.get("/api/municipal").get_data()) < 2.5 * 1024 * 1024


def test_municipal_covers_parcel_municipalities(municipios):
    # Los municipios de las parcelas deben estar en la capa municipal (cruce por nombres)
    parcelas = gpd.read_file(ROOT / "data" / "processed" / "parcelas.gpkg")
    pares = set(zip(parcelas["estado"], parcelas["municipio"]))
    assert len(pares) == 9
    municipales = {(f["properties"]["estado"], f["properties"]["municipio"]) for f in municipios}
    assert pares <= municipales


def test_municipal_missing_file(client, monkeypatch, tmp_path):
    # Sin el gpkg la API responde 503 en español, no 500
    monkeypatch.setattr(municipal, "MUNICIPAL_GPKG", tmp_path / "no_existe.gpkg")
    res = client.get("/api/municipal")
    assert res.status_code == 503
    assert "error" in res.get_json()
