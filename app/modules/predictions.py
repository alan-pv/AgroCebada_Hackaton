# Predicciones del modelo final para la app, en JSON o CSV
from functools import cache

import pandas as pd
from flask import Blueprint, Response, jsonify, request

from parcelas.config import OUTPUTS

bp = Blueprint("predictions", __name__)

# Columnas de predicciones.parquet y su nombre en la API
FIELDS = {
    "ID_POLIGONO": "id",
    "conjunto": "set",
    "regimen": "regime",
    "estado": "state",
    "municipio": "municipality",
    "area_ha": "area_ha",
    "pred": "pred",
    "p10": "p10",
    "p90": "p90",
    "prob_bajo_umbral": "prob_below",
    "observado": "observed",
}
SETS = ("ENTRENAMIENTO", "PREDICCION")
FORMATS = ("json", "csv")


@cache
def predictions_table():
    # Se lee una sola vez; en las parcelas de entrenamiento la predicción es la fuera de fold
    df = pd.read_parquet(OUTPUTS / "predicciones.parquet")[list(FIELDS)].rename(columns=FIELDS)
    return df.round({"pred": 3, "p10": 3, "p90": 3, "prob_below": 3})


@bp.get("/api/predictions")
def predictions():
    subset = request.args.get("set")
    if subset is not None and subset not in SETS:
        return jsonify(error="set debe ser ENTRENAMIENTO o PREDICCION"), 400
    fmt = request.args.get("format", "json")
    if fmt not in FORMATS:
        return jsonify(error="format debe ser json o csv"), 400

    df = predictions_table()
    for param in ("set", "state", "municipality"):
        value = request.args.get(param)
        if value is not None:
            df = df[df[param] == value]

    if fmt == "csv":
        res = Response(df.to_csv(index=False), mimetype="text/csv")
        res.headers["Content-Disposition"] = "attachment; filename=agrocebada_predicciones.csv"
        return res
    # El rendimiento observado vacío de las 59 sale como null
    return Response(df.to_json(orient="records"), mimetype="application/json")
