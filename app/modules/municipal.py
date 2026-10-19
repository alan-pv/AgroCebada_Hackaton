# Modelo municipal: rendimiento esperado, intervalo y partes de la predicción de los municipios de Hidalgo, Puebla y
# Tlaxcala (los estados del reto) en GeoJSON. El modelo se entrenó también con el Estado de México, pero no se muestra.
# Solo lee outputs/generalizable/capa_municipal.gpkg, ya generado, y los límites del INEGI; ninguna ruta reentrena el modelo
# Contrato:
#   GET /api/municipal   GeoJSON (FeatureCollection) de los 361 municipios de los tres estados con las propiedades de
#                        PROPERTIES; los NaN salen como null. Si falta el gpkg, responde 503.
#                        format=csv descarga las mismas propiedades sin geometría
#   GET /api/municipal/estados  GeoJSON de los 4 estados (unión de sus municipios) con estado y el punto
#                        donde va su nombre (label_lon, label_lat)
#   municipal_geojson()  función pura con ese GeoJSON como dict, ya sin NaN
import json
from functools import cache

import geopandas as gpd
from flask import Blueprint, Response, jsonify, request
from shapely.geometry import MultiPolygon, Polygon

from parcelas.config import OUTPUTS_GENERALIZABLE, RAIZ

bp = Blueprint("municipal", __name__)

MUNICIPAL_GPKG = OUTPUTS_GENERALIZABLE / "capa_municipal.gpkg"
# Límites municipales del INEGI a resolución completa (la misma ruta que generalizable.variables, que no se
# importa aquí porque pide exactextract, que no se instala en ARM)
MUNICIPIOS = RAIZ / "data" / "externos" / "inegi_marcogeo" / "municipios_13_15_21_29.gpkg"
# Estados del reto: los únicos que muestra la app
STATES = ("Hidalgo", "Puebla", "Tlaxcala")
# Columnas de la capa municipios que expone la API; el resto de la tabla no sale
PROPERTIES = ["CVEGEO", "estado", "municipio", "esperado", "p10", "p90", "prob_bajo_2", "confianza",
              "siap_media", "siap_anios", "siap_frac_bajo_2", "dist_siap_km", "con_siap", "agricola_ha",
              "dentro_rango_ambiental", "dentro_dominio", "modelo", "escala", "anio_referencia",
              # Partes de la predicción: media regional + efecto de la Tmax + corrección por vecinos = esperado_sin_corte
              "tmax_jul_ago", "tmax_media", "pendiente_tmax", "parte_media", "parte_tmax", "parte_vecinos",
              "esperado_sin_corte",
              # Error típico esperado según la distancia a datos del SIAP (null en las extrapolaciones) y elevación
              "dist_datos_km", "error_tipico", "elev_m"]
# Tolerancia al simplificar el contorno de cada estado, en metros: ~100 m basta para el mapa
STATE_TOLERANCE_M = 100
# Huecos e islas de menos de 5 km² no se dibujan en el contorno del estado
STATE_MIN_PART_M2 = 5e6
# 4 decimales en las coordenadas (~10 m) y en los números de las propiedades
DECIMALS = 4


@cache
def municipal_frame():
    """Capa municipios con las columnas de la API, en WGS84 y redondeada. Se lee una sola vez."""
    gdf = gpd.read_file(MUNICIPAL_GPKG, layer="municipios").to_crs(4326)
    gdf = gdf[gdf.estado.isin(STATES)][[*PROPERTIES, "geometry"]].reset_index(drop=True)
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


def _drop_specks(geom, min_area=STATE_MIN_PART_M2):
    """Polígono sin los huecos ni las partes de menos de min_area (m²)."""
    parts = getattr(geom, "geoms", [geom])
    kept = [Polygon(g.exterior, [r for r in g.interiors if Polygon(r).area >= min_area])
            for g in parts if g.area >= min_area]
    return MultiPolygon(kept) if len(kept) > 1 else kept[0]


@cache
def states_json():
    """GeoJSON de los estados del reto: unión de sus municipios con los límites del INEGI a resolución completa
    (los de la capa municipal están simplificados uno por uno y dejan rendijas), simplificada después de unir."""
    gdf = gpd.read_file(MUNICIPIOS)[["estado", "geometry"]]
    states = gdf[gdf.estado.isin(STATES)].dissolve("estado").reset_index()
    # Fuera los huecos y las islas diminutas que deja la unión: en el mapa se verían como manchas negras
    states["geometry"] = states.geometry.apply(_drop_specks)
    states["geometry"] = states.geometry.simplify(STATE_TOLERANCE_M).to_crs(4326)
    states = states.set_crs(4326, allow_override=True)
    points = states.geometry.representative_point()
    states["label_lon"], states["label_lat"] = points.x.round(DECIMALS), points.y.round(DECIMALS)
    states["geometry"] = states.geometry.set_precision(10 ** -DECIMALS)
    return states.to_json(drop_id=True)


def warm_up():
    """Carga los GeoJSON antes de aceptar peticiones; la primera visita no espera."""
    municipal_json()
    states_json()


@bp.get("/api/municipal")
def municipal():
    fmt = request.args.get("format", "json")
    if fmt not in ("json", "csv"):
        return jsonify(error="format debe ser json o csv"), 400
    # Sin el archivo no hay modelo municipal que servir: 503 en vez de un 500
    if not MUNICIPAL_GPKG.exists():
        return jsonify(error="Falta outputs/generalizable/capa_municipal.gpkg; el modelo municipal no está generado"), 503
    if fmt == "csv":
        res = Response(municipal_frame()[PROPERTIES].to_csv(index=False), mimetype="text/csv")
        res.headers["Content-Disposition"] = "attachment; filename=agrocebada_modelo_municipal.csv"
        return res
    res = Response(municipal_json(), mimetype="application/geo+json")
    # Igual que /api/parcels y /api/economics: el navegador lo reutiliza una hora
    res.headers["Cache-Control"] = "public, max-age=3600"
    return res


@bp.get("/api/municipal/estados")
def states():
    if not MUNICIPAL_GPKG.exists():
        return jsonify(error="Falta outputs/generalizable/capa_municipal.gpkg; el modelo municipal no está generado"), 503
    res = Response(states_json(), mimetype="application/geo+json")
    res.headers["Cache-Control"] = "public, max-age=3600"
    return res
