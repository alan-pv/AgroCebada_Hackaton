# Ejecuta el modelo final en vivo sobre las parcelas que se elijan
# Solo predice: el modelo se carga ya entrenado de models/ y ninguna petición lo reentrena
import math
from functools import cache, lru_cache

import pandas as pd
from flask import Blueprint, jsonify, request

from parcelas.config import PROCESSED
from parcelas.predict import cargar_modelo, predict

bp = Blueprint("model", __name__)

# Límites por petición, para que nadie sature el CPU del servidor
MAX_PARCELS = 59
THRESHOLD_RANGE = (1.0, 6.0)  # t/ha
# Marca de confianza de predict() y su nombre en la API, con include_confidence=true
CONFIDENCE_FIELDS = {"confianza": "confidence", "vecinos_400m": "neighbors_400m",
                     "dist_vecino_m": "nearest_neighbor_m", "motivo_confianza": "confidence_reason"}


@cache
def load_model():
    # Tarda unos segundos; se carga una sola vez y queda en memoria
    return cargar_modelo()


@cache
def features_table():
    # Variables ya procesadas de las 197 parcelas, indexadas por ID
    return pd.read_parquet(PROCESSED / "features.parquet").set_index("ID_POLIGONO")


def _json_record(record):
    # NaN e infinitos no son JSON válido: pasan a null
    return {k: None if isinstance(v, float) and not math.isfinite(v) else v for k, v in record.items()}


# Con tope: @cache crecería sin límite si cada petición pide una selección distinta
@lru_cache(maxsize=256)
def predict_cached(ids, threshold, with_confidence=False):
    # ids es una tupla ordenada y sin repetidos, para que la misma selección reutilice el resultado
    # with_confidence entra en la clave del caché: con y sin la marca son respuestas distintas
    out = predict(features_table().loc[list(ids)], umbral=threshold, modelo=load_model())
    # la API conserva su contrato: la marca de confianza solo sale con include_confidence=true (#12)
    cols = ["ID_POLIGONO", "pred", "p10", "p90", "prob_bajo_umbral"]
    names = {"ID_POLIGONO": "id", "prob_bajo_umbral": "prob_below"}
    if with_confidence:
        cols += list(CONFIDENCE_FIELDS)
        names.update(CONFIDENCE_FIELDS)
    out = out[cols].rename(columns=names)
    out = out.round({"pred": 3, "p10": 3, "p90": 3, "prob_below": 3, "nearest_neighbor_m": 1})
    return [_json_record(record) for record in out.to_dict(orient="records")]


def warm_up():
    load_model()
    features_table()


@bp.post("/api/predict")
def predict_parcels():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error='El cuerpo debe ser JSON, por ejemplo {"ids": ["AGC_001"]}'), 400
    ids = body.get("ids")
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
        return jsonify(error="ids debe ser una lista no vacía de IDs de parcela"), 400
    ids = tuple(sorted(set(ids)))
    if len(ids) > MAX_PARCELS:
        return jsonify(error=f"Se pueden predecir hasta {MAX_PARCELS} parcelas por petición"), 400
    unknown = [i for i in ids if i not in features_table().index]
    if unknown:
        return jsonify(error=f"IDs de parcela desconocidos: {', '.join(unknown)}"), 400

    model = load_model()
    threshold = body.get("threshold", model.umbral)
    low, high = THRESHOLD_RANGE
    # bool es subclase de int en Python; true no debe pasar como 1 t/ha
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not low <= threshold <= high:
        return jsonify(error=f"threshold debe ser un número entre {low} y {high} t/ha"), 400
    # Redondear evita que 2.5 y 2.5000001 ocupen dos lugares del caché
    threshold = round(float(threshold), 2)
    # include_confidence es opcional (false por defecto); si viene, tiene que ser true o false
    with_confidence = body.get("include_confidence", False)
    if not isinstance(with_confidence, bool):
        return jsonify(error="include_confidence debe ser true o false"), 400

    return jsonify(
        model_version=model.version,
        threshold=threshold,
        predictions=predict_cached(ids, threshold, with_confidence),
    )
