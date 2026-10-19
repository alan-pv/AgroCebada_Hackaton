import json

import pandas as pd
import pytest

pytest.importorskip("flask")

from parcelas.config import OUTPUTS_PARCELAS
from app import create_app
from app.modules import model

# Claves de cada fila de /api/predict, y las cuatro que agrega include_confidence=true
BASE_KEYS = {"id", "pred", "p10", "p90", "prob_below"}
CONFIDENCE_KEYS = {"confidence", "neighbors_400m", "nearest_neighbor_m", "confidence_reason"}


def strict_json(text):
    """Parsea JSON de forma estricta: NaN, Infinity y -Infinity no son JSON válido y hacen fallar."""
    def reject(constant):
        raise ValueError(f"constante no permitida en JSON: {constant}")
    return json.loads(text, parse_constant=reject)


def predict_ids(client, ids, **extra):
    return client.post("/api/predict", json={"ids": ids, **extra})


@pytest.fixture(scope="module")
def client():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def pred():
    return pd.read_parquet(OUTPUTS_PARCELAS / "predicciones.parquet").set_index("ID_POLIGONO")


def test_respuesta_por_defecto_tiene_5_claves(client):
    ids = ["AGC_001", "AGC_002", "AGC_003"]
    res = predict_ids(client, ids)
    assert res.status_code == 200
    rows = res.get_json()["predictions"]
    assert all(set(r) == BASE_KEYS for r in rows)
    # include_confidence=false da exactamente la misma respuesta que no mandar la opción
    assert predict_ids(client, ids, include_confidence=False).get_json() == res.get_json()


def test_include_confidence_agrega_la_marca(client, pred):
    ent = list(pred[pred.conjunto == "ENTRENAMIENTO"].index[:5])
    pre = list(pred[pred.conjunto == "PREDICCION"].index[:5])
    res = predict_ids(client, ent + pre, include_confidence=True)
    assert res.status_code == 200
    rows = strict_json(res.get_data(as_text=True))["predictions"]
    assert len(rows) == 10
    for r in rows:
        assert set(r) == BASE_KEYS | CONFIDENCE_KEYS
        ref = pred.loc[r["id"]]
        assert r["confidence"] == ref.confianza
        assert r["confidence"] in {"alta", "media", "baja"}
        assert type(r["neighbors_400m"]) is int and r["neighbors_400m"] == int(ref.vecinos_400m)
        assert r["nearest_neighbor_m"] == round(float(ref.dist_vecino_m), 1)
        assert r["confidence_reason"] == ref.motivo_confianza


@pytest.mark.parametrize("valor", ["si", 1, "true", None])
def test_include_confidence_no_booleano_da_400(client, valor):
    res = predict_ids(client, ["AGC_001"], include_confidence=valor)
    assert res.status_code == 400
    assert res.get_json() == {"error": "include_confidence debe ser true o false"}


def test_bandera_tiene_entrada_propia_en_el_cache(client):
    model.predict_cached.cache_clear()
    ids = ["AGC_020", "AGC_021", "AGC_022"]
    predict_ids(client, ids)
    assert model.predict_cached.cache_info().currsize == 1
    predict_ids(client, ids, include_confidence=True)
    info = model.predict_cached.cache_info()
    assert info.currsize == 2
    assert info.maxsize == 256
    # Repetir la llamada con bandera reutiliza el caché, aunque los IDs vengan en otro orden
    res = predict_ids(client, ids[::-1], include_confidence=True)
    assert res.status_code == 200
    assert model.predict_cached.cache_info().hits == info.hits + 1
    assert model.predict_cached.cache_info().currsize == 2
    # La entrada sin bandera no se contamina: sigue con 5 claves
    assert set(predict_ids(client, ids).get_json()["predictions"][0]) == BASE_KEYS
