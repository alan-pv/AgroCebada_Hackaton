# Ejecuta el modelo final en vivo sobre las parcelas que se elijan
# Solo predice: el modelo se carga ya entrenado de models/ y ninguna petición lo reentrena
from functools import cache, lru_cache

import pandas as pd
from flask import Blueprint, jsonify, request

from agrocebada.config import PROCESSED
from agrocebada.predict import cargar_modelo, predict

bp = Blueprint("model", __name__)

# Límites por petición, para que nadie sature el CPU del servidor
MAX_PARCELS = 59
THRESHOLD_RANGE = (1.0, 6.0)  # t/ha


@cache
def load_model():
    # Tarda unos segundos; se carga una sola vez y queda en memoria
    return cargar_modelo()


@cache
def features_table():
    # Variables ya procesadas de las 197 parcelas, indexadas por ID
    return pd.read_parquet(PROCESSED / "features.parquet").set_index("ID_POLIGONO")


# Con tope: @cache crecería sin límite si cada petición pide una selección distinta
@lru_cache(maxsize=256)
def predict_cached(ids, threshold):
    # ids es una tupla ordenada y sin repetidos, para que la misma selección reutilice el resultado
    out = predict(features_table().loc[list(ids)], umbral=threshold, modelo=load_model())
    # la API conserva su contrato. La marca de confianza se expone en un cambio aparte (#12)
    out = out[["ID_POLIGONO", "pred", "p10", "p90", "prob_bajo_umbral"]]
    out = out.rename(columns={"ID_POLIGONO": "id", "prob_bajo_umbral": "prob_below"})
    return out.round({"pred": 3, "p10": 3, "p90": 3, "prob_below": 3}).to_dict(orient="records")


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

    return jsonify(
        model_version=model.version,
        threshold=threshold,
        predictions=predict_cached(ids, threshold),
    )
