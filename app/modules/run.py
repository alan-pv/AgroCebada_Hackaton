# Página «Ejecutar el modelo» y predicción de parcelas nuevas
# Solo predice: el modelo se carga ya entrenado de models/ y ninguna petición lo reentrena
# ni escribe archivos
#   GET /ejecutar           página HTML con run.html; sus predicciones salen de POST /api/predict (módulo model)
#   POST /api/predict/new   predicción de parcelas que no están en el conjunto de datos
import math
import re
from functools import cache

import pandas as pd
from flask import Blueprint, jsonify, render_template, request
from pyproj import Transformer

from agrocebada.config import CRS_GEO, CRS_METRICO
from agrocebada.predict import predict

from . import model

bp = Blueprint("run", __name__)

# Grados de margen alrededor de las 197 parcelas para aceptar una parcela nueva
ZONE_MARGIN = 0.5
# Superficie máxima de una parcela nueva, en ha
AREA_MAX_HA = 1000.0
REGIMES = ("A", "B")
# Identificador de parcela nueva: de 1 a 40 letras, números, guion bajo o guion
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,40}")


def warm_up():
    """Carga lo que el módulo necesita antes de aceptar peticiones: el transformador y la zona."""
    _transformer()
    _zone()


@cache
def _transformer():
    # De longitud y latitud (EPSG:4326) a x_m, y_m (EPSG:6372), el CRS de features.parquet.
    # Se crea una sola vez y lo comparten todas las peticiones
    return Transformer.from_crs(CRS_GEO, CRS_METRICO, always_xy=True)


def to_metres(lon, lat):
    """x_m, y_m en metros (EPSG:6372) de un punto dado en longitud y latitud."""
    x, y = _transformer().transform(lon, lat)
    return float(x), float(y)


@cache
def _zone():
    # Rectángulo de la zona de estudio: mínimo y máximo de lon y lat de las parcelas, con margen
    table = model.features_table()
    return (
        float(table["lon"].min()) - ZONE_MARGIN,
        float(table["lon"].max()) + ZONE_MARGIN,
        float(table["lat"].min()) - ZONE_MARGIN,
        float(table["lat"].max()) + ZONE_MARGIN,
    )


def _number(value):
    """Número finito de un valor JSON, o None. Un bool (true) no cuenta como 1."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        value = float(value)
    except OverflowError:  # un entero demasiado grande para float
        return None
    return value if math.isfinite(value) else None


def _rounded(value, digits):
    """Número redondeado para la respuesta; None si es NaN o infinito, que JSON no admite."""
    value = float(value)
    return round(value, digits) if math.isfinite(value) else None


def _validate_parcel(number, parcel, existing, requested):
    """Revisa una parcela nueva. Devuelve (datos, None) si es válida o (None, mensaje) si no.

    `number` es su lugar en la lista (desde 1), `existing` los IDs del conjunto de datos y
    `requested` los IDs que ya aceptó esta petición.
    """
    label = f"Parcela {number}"
    if not isinstance(parcel, dict):
        return None, f"{label}: cada parcela debe ser un objeto con lon, lat, area_ha y regime"
    parcel_id = parcel.get("id")
    if parcel_id is not None:
        if not isinstance(parcel_id, str) or not ID_PATTERN.fullmatch(parcel_id):
            return None, f"{label}: id solo puede tener de 1 a 40 letras, números, guion bajo o guion"
        label = f"{label} ({parcel_id})"
        if parcel_id in existing:
            return None, f"{label}: ese ID ya es de una parcela del conjunto de datos; elige otro"
        if parcel_id in requested:
            return None, f"{label}: ID repetido en la petición"

    lon = _number(parcel.get("lon"))
    if lon is None:
        return None, f"{label}: lon debe ser un número"
    lat = _number(parcel.get("lat"))
    if lat is None:
        return None, f"{label}: lat debe ser un número"
    lon_min, lon_max, lat_min, lat_max = _zone()
    if not (lon_min <= lon <= lon_max and lat_min <= lat <= lat_max):
        return None, (f"{label}: el punto queda fuera de la zona de estudio (lon entre {lon_min:.2f} y "
                      f"{lon_max:.2f}, lat entre {lat_min:.2f} y {lat_max:.2f})")

    area = _number(parcel.get("area_ha"))
    if area is None:
        return None, f"{label}: area_ha debe ser un número"
    if not 0 < area <= AREA_MAX_HA:
        return None, f"{label}: area_ha debe ser mayor que 0 y como máximo {AREA_MAX_HA:.0f} ha"

    regime = parcel.get("regime")
    if regime not in REGIMES:
        return None, f'{label}: regime debe ser "A" o "B"'
    return {"id": parcel_id, "lon": lon, "lat": lat, "area_ha": area, "regime": regime}, None


@bp.post("/api/predict/new")
def predict_new():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error='El cuerpo debe ser JSON, por ejemplo {"parcels": [{"lon": -98.37, '
                             '"lat": 19.82, "area_ha": 5.2, "regime": "A"}]}'), 400
    parcels = body.get("parcels")
    if not isinstance(parcels, list) or not parcels:
        return jsonify(error=f"parcels debe ser una lista de 1 a {model.MAX_PARCELS} parcelas"), 400
    if len(parcels) > model.MAX_PARCELS:
        return jsonify(error=f"Se pueden predecir hasta {model.MAX_PARCELS} parcelas nuevas por petición"), 400

    loaded = model.load_model()
    low, high = model.THRESHOLD_RANGE
    # _number descarta bool: true no debe pasar como 1 t/ha
    threshold = _number(body.get("threshold", loaded.umbral))
    if threshold is None or not low <= threshold <= high:
        return jsonify(error=f"threshold debe ser un número entre {low} y {high} t/ha"), 400
    # Igual que /api/predict, el umbral se redondea a 2 decimales
    threshold = round(threshold, 2)

    existing = set(model.features_table().index)
    requested = set()
    rows = []
    for number, parcel in enumerate(parcels, start=1):
        data, error = _validate_parcel(number, parcel, existing, requested)
        if error:
            return jsonify(error=error), 400
        if data["id"] is not None:
            requested.add(data["id"])
        rows.append(data)

    # Sin ID, la parcela recibe NUEVA_1, NUEVA_2..., saltando los que ya están en uso
    taken = existing | requested
    counter = 0
    for data in rows:
        if data["id"] is None:
            counter += 1
            while f"NUEVA_{counter}" in taken:
                counter += 1
            data["id"] = f"NUEVA_{counter}"
            taken.add(data["id"])

    xy = [to_metres(data["lon"], data["lat"]) for data in rows]
    new_parcels = pd.DataFrame({
        "ID_POLIGONO": [data["id"] for data in rows],
        "x_m": [x for x, _ in xy],
        "y_m": [y for _, y in xy],
        "regimen": [data["regime"] for data in rows],
        "area_ha": [data["area_ha"] for data in rows],
    })
    # Solo las columnas que pide el modelo, más el identificador. Parcelas nuevas: no hay
    # exclusión por entrenamiento, y predict() devuelve las filas en el orden enviado
    out = predict(new_parcels[["ID_POLIGONO", *loaded.columnas_requeridas]], umbral=threshold, modelo=loaded)

    predictions = []
    for data, row in zip(rows, out.to_dict(orient="records")):
        predictions.append({
            "id": str(row["ID_POLIGONO"]),
            "lon": data["lon"],
            "lat": data["lat"],
            "area_ha": data["area_ha"],
            "regime": data["regime"],
            "pred": _rounded(row["pred"], 3),
            "p10": _rounded(row["p10"], 3),
            "p90": _rounded(row["p90"], 3),
            "prob_below": _rounded(row["prob_bajo_umbral"], 3),
            "confidence": str(row["confianza"]),
            "neighbors_400m": int(row["vecinos_400m"]),
            "nearest_neighbor_m": _rounded(row["dist_vecino_m"], 1),
            "confidence_reason": str(row["motivo_confianza"]),
        })
    return jsonify(model_version=loaded.version, threshold=threshold, predictions=predictions)


@bp.get("/ejecutar")
def page():
    return render_template(
        "run.html",
        max_parcels=model.MAX_PARCELS,
        threshold_min=model.THRESHOLD_RANGE[0],
        threshold_max=model.THRESHOLD_RANGE[1],
        threshold_default=model.load_model().umbral,
    )
