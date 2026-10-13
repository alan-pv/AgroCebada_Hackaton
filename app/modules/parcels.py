# Parcelas en GeoJSON para el mapa de la página inicial
from functools import cache

import geopandas as gpd
from flask import Blueprint, Response

from agrocebada.config import PROCESSED

bp = Blueprint("parcels", __name__)

# Columnas del GeoPackage y su nombre en el GeoJSON
FIELDS = {
    "ID_POLIGONO": "id",
    "estado": "state",
    "municipio": "municipality",
    "conjunto": "set",
    "rendimiento": "yield_t_ha",
    "area_ha": "area_ha",
}


@cache
def parcels_geojson():
    # Se arma una sola vez y queda en memoria
    gdf = gpd.read_file(PROCESSED / "parcelas.gpkg").to_crs(4326)
    gdf = gdf[[*FIELDS, "geometry"]].rename(columns=FIELDS)
    # 6 decimales (~10 cm) bastan y bajan el GeoJSON de 294 a 211 KB
    gdf["geometry"] = gdf.geometry.set_precision(1e-6)
    return gdf.to_json(drop_id=True)


@bp.get("/api/parcels")
def parcels():
    res = Response(parcels_geojson(), mimetype="application/geo+json")
    # El navegador lo reutiliza una hora sin volver a pedirlo
    res.headers["Cache-Control"] = "public, max-age=3600"
    return res
