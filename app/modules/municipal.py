# Modelo municipal: rendimiento esperado, intervalo y probabilidad de rendimiento bajo de los 486 municipios en GeoJSON
# Solo lee outputs/generalizable_municipios.gpkg, ya generado; ninguna ruta reentrena el modelo
# Contrato:
#   GET /api/municipal   GeoJSON (FeatureCollection) de los 486 municipios con las propiedades de
#                        PROPERTIES; los NaN salen como null. Si falta el gpkg, responde 503.
#                        format=csv descarga las mismas propiedades sin geometría
#   municipal_geojson()  función pura con ese GeoJSON como dict, ya sin NaN
import json
from functools import cache

import geopandas as gpd
from flask import Blueprint, Response, jsonify, request

from agrocebada.config import OUTPUTS

bp = Blueprint("municipal", __name__)

MUNICIPAL_GPKG = OUTPUTS / "generalizable_municipios.gpkg"
# Columnas de la capa municipios que expone la API; el resto de la tabla no sale
PROPERTIES = ["CVEGEO", "estado", "municipio", "esperado", "p10", "p90", "prob_bajo_2", "confianza",
              "siap_media", "siap_anios", "siap_frac_bajo_2", "dist_siap_km", "con_siap", "agricola_ha",
              "dentro_rango_ambiental", "dentro_dominio", "modelo", "escala", "anio_referencia"]
# 4 decimales en las coordenadas (~10 m) y en los números de las propiedades
DECIMALS = 4


@cache
def municipal_frame():
    """Capa municipios con las columnas de la API, en WGS84 y redondeada. Se lee una sola vez."""
    gdf = gpd.read_file(MUNICIPAL_GPKG, layer="municipios").to_crs(4326)
    gdf = gdf[[*PROPERTIES, "geometry"]]
    # Las coordenadas quedan con 4 decimales; el redondeo de los floats va en el mismo paso
    gdf["geometry"] = gdf.geometry.set_precision(10 ** -DECIMALS)
    return gdf.round(DECIMALS)


@cache
def municipal_geojson():
    """GeoJSON de los 486 municipios con las propiedades de la API. Se arma una sola vez."""
    # na="null" escribe los NaN como null: el JSON sale válido, sin NaN
    return json.loads(municipal_frame().to_json(na="null", drop_id=True))


@cache
def municipal_json():
    # Texto del GeoJSON, serializado una sola vez como /api/parcels
    return json.dumps(municipal_geojson(), allow_nan=False)


def warm_up():
    """Carga el GeoJSON antes de aceptar peticiones; la primera visita no espera."""
    municipal_json()


@bp.get("/api/municipal")
def municipal():
    fmt = request.args.get("format", "json")
    if fmt not in ("json", "csv"):
        return jsonify(error="format debe ser json o csv"), 400
    # Sin el archivo no hay modelo municipal que servir: 503 en vez de un 500
    if not MUNICIPAL_GPKG.exists():
        return jsonify(error="Falta outputs/generalizable_municipios.gpkg; el modelo municipal no está generado"), 503
    if fmt == "csv":
        res = Response(municipal_frame()[PROPERTIES].to_csv(index=False), mimetype="text/csv")
        res.headers["Content-Disposition"] = "attachment; filename=agrocebada_modelo_municipal.csv"
        return res
    res = Response(municipal_json(), mimetype="application/geo+json")
    # Igual que /api/parcels y /api/economics: el navegador lo reutiliza una hora
    res.headers["Cache-Control"] = "public, max-age=3600"
    return res
