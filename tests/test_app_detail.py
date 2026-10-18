import json
import math
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("flask")

from app import create_app

ROOT = Path(__file__).resolve().parents[1]
PREDICCIONES = ROOT / "outputs" / "predicciones.parquet"
SERIE = ROOT / "data" / "processed" / "serie_ficha.parquet"

NOTA_ENTRENAMIENTO = ("Esta parcela se usó para entrenar el modelo; la predicción que se muestra es la "
                      "validada fuera de entrenamiento y no se desglosa con el mismo método.")
CLAVES = {"id", "state", "municipality", "set", "regime", "area_ha", "lon", "lat", "observed", "pred",
          "p10", "p90", "threshold", "prob_below", "confidence", "breakdown", "breakdown_note",
          "model_inputs", "context_2025", "series"}
CLAVES_CONTEXTO = ["clima_prec_total_may_oct", "clima_anom_prec_total_may_oct", "sat25_s2_nddi_max",
                   "fen_pico_doy", "hist_s2_ndvi_anom_max"]
CLAVES_ENTRADAS = ["regime", "area_ha", "neighbors_400m", "nearest_neighbor_m"]


@pytest.fixture(scope="module")
def client():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def predicciones():
    return pd.read_parquet(PREDICCIONES).set_index("ID_POLIGONO")


def sin_nan(texto):
    # Un JSON válido no trae NaN ni Infinity; json.loads los acepta si no se le dice lo contrario
    def rechazar(constante):
        raise ValueError(f"constante no válida en JSON: {constante}")
    return json.loads(texto, parse_constant=rechazar)


def en_espanol(texto):
    # Texto para la persona: no es un nombre de columna y trae palabras del español
    limpio = texto.lower()
    for signo in ";.,()":
        limpio = limpio.replace(signo, " ")
    palabras = set(limpio.split())
    return bool(texto) and "_" not in texto and bool(palabras & {"de", "la", "el", "en", "a", "y", "del", "se", "es"})


@pytest.mark.parametrize("parcel_id, conjunto", [("AGC_003", "PREDICCION"), ("AGC_001", "ENTRENAMIENTO")])
def test_ficha_responde_con_sus_secciones(client, parcel_id, conjunto):
    res = client.get(f"/api/parcels/{parcel_id}")
    assert res.status_code == 200
    data = res.get_json()
    assert set(data) == CLAVES
    assert data["id"] == parcel_id
    assert data["set"] == conjunto
    assert data["threshold"] == 2.5


def test_parcela_inexistente_responde_404(client):
    res = client.get("/api/parcels/NO_EXISTE")
    assert res.status_code == 404
    assert res.get_json() == {"error": "Parcela desconocida: NO_EXISTE"}


def test_desglose_de_prediccion_suma_la_prediccion(client, predicciones):
    ids = predicciones.index[predicciones["conjunto"] == "PREDICCION"]
    assert len(ids) == 59
    for pid in ids:
        data = client.get(f"/api/parcels/{pid}").get_json()
        row = predicciones.loc[pid]
        desglose = data["breakdown"]
        suma = desglose["base"] + sum(term["value"] for term in desglose["terms"])
        assert desglose["total"] == pytest.approx(row["pred"], abs=1e-6), pid
        assert suma == pytest.approx(row["pred"], abs=1e-6), pid
        assert data["breakdown_note"] is None, pid
        assert data["pred"] == pytest.approx(row["pred"], abs=1e-9), pid
        assert data["p10"] == pytest.approx(row["p10"], abs=1e-9), pid
        assert data["p90"] == pytest.approx(row["p90"], abs=1e-9), pid
        assert data["confidence"]["level"] == row["confianza"], pid
        assert data["confidence"]["neighbors_400m"] == int(row["vecinos_400m"]), pid
        assert data["confidence"]["nearest_neighbor_m"] == pytest.approx(row["dist_vecino_m"], abs=1e-9), pid
        assert data["confidence"]["reason"] == row["motivo_confianza"], pid


def test_entrenamiento_no_tiene_desglose(client, predicciones):
    ids = predicciones.index[predicciones["conjunto"] == "ENTRENAMIENTO"]
    assert len(ids) == 138
    for pid in ids:
        data = client.get(f"/api/parcels/{pid}").get_json()
        assert data["breakdown"] is None, pid
        assert data["breakdown_note"] == NOTA_ENTRENAMIENTO, pid


def test_serie_2025_frente_a_2022_2024(client, predicciones):
    if not SERIE.exists():
        pytest.skip("Falta data/processed/serie_ficha.parquet; genérelo con scripts/exportar_serie_ficha.py")
    for pid in predicciones.index:
        serie = client.get(f"/api/parcels/{pid}").get_json()["series"]
        assert serie["year"] == 2025, pid
        assert serie["history_years"] == [2022, 2023, 2024], pid
        for clave in ("ndvi", "nddi"):
            indice = serie["indices"][clave]
            actual = indice["current"]
            assert actual["doy"] and len(actual["doy"]) == len(actual["value"]), (pid, clave)
            assert all(math.isfinite(v) for v in actual["value"]), (pid, clave)
            historia = indice["history"]
            assert historia["doy"], (pid, clave)
            assert len(historia["mean"]) == len(historia["min"]) == len(historia["max"]) == len(historia["doy"]), (pid, clave)
            for media, minimo, maximo in zip(historia["mean"], historia["min"], historia["max"]):
                assert math.isfinite(media) and math.isfinite(minimo) and math.isfinite(maximo), (pid, clave)
                assert minimo <= media <= maximo, (pid, clave)


def test_json_sin_nan_en_las_197(client, predicciones):
    for pid in predicciones.index:
        res = client.get(f"/api/parcels/{pid}")
        assert res.status_code == 200, pid
        sin_nan(res.get_data(as_text=True))


def test_contexto_y_entradas_con_etiquetas_en_espanol(client):
    data = client.get("/api/parcels/AGC_003").get_json()
    contexto = data["context_2025"]
    assert [item["key"] for item in contexto] == CLAVES_CONTEXTO
    for item in contexto:
        assert set(item) == {"key", "label", "value", "unit", "note"}
        assert en_espanol(item["label"]), item["label"]
        assert item["note"].startswith("Contexto; no entra al modelo final"), item["note"]
    entradas = data["model_inputs"]
    assert [item["key"] for item in entradas] == CLAVES_ENTRADAS
    for item in entradas:
        assert set(item) == {"key", "label", "value", "unit", "help"}
        assert en_espanol(item["label"]), item["label"]
        assert en_espanol(item["help"]), item["help"]
    # Los valores de las entradas son los mismos que la marca de confianza de la respuesta
    por_clave = {item["key"]: item["value"] for item in entradas}
    assert por_clave["regime"] == data["regime"]
    assert por_clave["neighbors_400m"] == data["confidence"]["neighbors_400m"]
    assert por_clave["nearest_neighbor_m"] == pytest.approx(data["confidence"]["nearest_neighbor_m"])
    # El día 263 del año de AGC_001 es el 20 de septiembre de 2025
    pico = next(item for item in client.get("/api/parcels/AGC_001").get_json()["context_2025"]
                if item["key"] == "fen_pico_doy")
    assert pico["value"] == 263
    assert pico["note"].endswith("Es el 20 de septiembre de 2025.")


# Campos de la página que arma _view para el rediseño: medidores, margen con signo y pasos de confianza

def test_ancho_del_medidor_va_de_0_a_100():
    from app.modules import detail
    assert detail._share(None) == 0.0
    assert detail._share(0.2636) == 26.4
    assert detail._share(1.0) == 100.0
    # Fuera de 0 a 1 se recorta, para que el relleno nunca salga del riel
    assert detail._share(-0.1) == 0.0
    assert detail._share(1.2) == 100.0


def test_margen_lleva_el_menos_tipografico():
    from app.modules import detail
    assert detail._money_signed(-12669.05) == "−$12,669"
    assert detail._money_signed(3500) == "$3,500"
    assert detail._money_signed(None) == "—"


@pytest.mark.parametrize("nivel, actual", [("baja", 0), ("media", 1), ("alta", 2)])
def test_pasos_de_confianza_marcan_el_nivel_actual(nivel, actual):
    from app.modules import detail
    pasos = detail._confidence_steps(nivel)
    assert [p["label"] for p in pasos] == ["Baja", "Media", "Alta"]
    assert [p["current"] for p in pasos] == [i == actual for i in range(3)]
    # Los segmentos se rellenan hasta el nivel actual
    assert [p["filled"] for p in pasos] == [i <= actual for i in range(3)]
    assert all(en_espanol(p["help"]) for p in pasos)


def test_sin_nivel_de_confianza_ningun_paso_es_el_actual():
    from app.modules import detail
    pasos = detail._confidence_steps(None)
    assert not any(p["current"] or p["filled"] for p in pasos)
