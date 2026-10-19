from pathlib import Path

import pytest

pytest.importorskip("flask")
gpd = pytest.importorskip("geopandas")

from app import create_app
from app.modules import municipal

ROOT = Path(__file__).resolve().parents[1]
PROPERTIES = {"CVEGEO", "estado", "municipio", "esperado", "p10", "p90", "prob_bajo_2", "confianza",
              "siap_media", "siap_anios", "siap_frac_bajo_2", "dist_siap_km", "con_siap", "agricola_ha",
              "tmax_jul_ago", "tmax_media", "pendiente_tmax", "parte_media", "parte_tmax", "parte_vecinos",
              "esperado_sin_corte", "dist_datos_km", "error_tipico", "elev_m",
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
    assert len(data["features"]) == 361
    # NaN no es JSON válido: debe salir como null
    assert "NaN" not in res.get_data(as_text=True)


def test_municipal_cvegeo_unique(municipios):
    ids = [f["properties"]["CVEGEO"] for f in municipios]
    assert len(set(ids)) == 361
    assert all(len(i) == 5 and i.isdigit() for i in ids)


def test_municipal_properties(municipios):
    assert all(set(f["properties"]) == PROPERTIES for f in municipios)


def test_municipal_todos_con_estimacion(municipios):
    props = [f["properties"] for f in municipios]
    assert sum(p["esperado"] is not None for p in props) == 361
    assert all(p["p10"] is not None and p["p90"] is not None and p["prob_bajo_2"] is not None for p in props)
    # Fuera del rango ambiental es extrapolación: se conserva la bandera
    assert sum(not p["dentro_rango_ambiental"] for p in props) == 193


def test_municipal_confianza_values(municipios):
    props = [f["properties"] for f in municipios]
    assert all(p["confianza"] in {"alta", "media", "baja"} for p in props)
    assert all(p["confianza"] == "baja" for p in props if not p["dentro_rango_ambiental"])


def test_municipal_interval_and_probability(municipios):
    props = [f["properties"] for f in municipios]
    assert all(0 <= p["p10"] <= p["esperado"] <= p["p90"] for p in props)
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


def test_municipal_csv(client):
    res = client.get("/api/municipal?format=csv")
    assert res.status_code == 200
    assert res.mimetype == "text/csv"
    assert "attachment" in res.headers["Content-Disposition"]
    lines = res.get_data(as_text=True).strip().splitlines()
    # Encabezado con las propiedades de la API, sin geometría, y una fila por municipio
    assert set(lines[0].split(",")) == PROPERTIES
    assert len(lines) == 362


def test_municipal_bad_format(client):
    assert client.get("/api/municipal?format=xml").status_code == 400


def test_municipal_parts_add_up(municipios):
    # Media regional + efecto de la Tmax + corrección por vecinos = predicción antes del corte en 0
    for f in municipios:
        p = f["properties"]
        assert abs(p["parte_media"] + p["parte_tmax"] + p["parte_vecinos"] - p["esperado_sin_corte"]) < 1e-3
        assert abs(max(p["esperado_sin_corte"], 0) - p["esperado"]) < 1e-3
        # El efecto de la Tmax es la pendiente por la diferencia contra la Tmax media
        assert abs(p["pendiente_tmax"] * (p["tmax_jul_ago"] - p["tmax_media"]) - p["parte_tmax"]) < 2e-3
    # Las extrapolaciones usan solo la regresión: sin corrección por vecinos
    assert all(f["properties"]["parte_vecinos"] == 0 for f in municipios if not f["properties"]["dentro_rango_ambiental"])


def test_municipal_states(client):
    res = client.get("/api/municipal/estados")
    assert res.status_code == 200
    features = res.get_json()["features"]
    assert sorted(f["properties"]["estado"] for f in features) == ["Hidalgo", "Puebla", "Tlaxcala"]
    assert all(isinstance(f["properties"]["label_lon"], float) for f in features)


def test_municipal_only_challenge_states(municipios):
    # La app solo muestra los estados del reto
    assert {f["properties"]["estado"] for f in municipios} == {"Hidalgo", "Puebla", "Tlaxcala"}


def test_municipal_typical_error(municipios):
    # Error típico validado según la distancia a datos: menor con datos propios; sin cifra en las extrapolaciones
    props = [f["properties"] for f in municipios]
    assert all((p["error_tipico"] is None) == (not p["dentro_rango_ambiental"]) for p in props)
    con = [p["error_tipico"] for p in props if p["con_siap"]]
    otros = [p["error_tipico"] for p in props if not p["con_siap"] and p["error_tipico"] is not None]
    assert max(con) <= min(otros)
