"""Variables ambientales por municipio y año, calculables para cualquier municipio.

Todas se ponderan por área sobre la superficie de agricultura de temporal del municipio
(INEGI, uso de suelo Serie VII). Si un municipio tiene menos de MIN_AGRICOLA_HA de temporal,
se usa el polígono completo y se marca con `zona_completa`.

Variables fijas (una fila por municipio).
  - x_m, y_m, lon, lat: centroide de la zona agrícola (EPSG:6372 y EPSG:4326).
  - agricola_ha, frac_agricola: superficie de temporal y su fracción del municipio.
  - elev_m, pendiente: Copernicus DEM GLO-90 agregado a 0.0025 grados.
  - suelo_<GRUPO>: fracción del grupo de suelo dominante (WRB, Serie II) sobre la zona
    agrícola, para los grupos de GRUPOS_SUELO. El resto va a suelo_otro.
  - textura_fina, textura_gruesa: fracción con clase textural fina (3) o gruesa (1), Serie II.
  - frac_durica: fracción con fase dúrica o dúrica profunda (tepetate), Serie I.
  - frac_litica: fracción con fase lítica o lítica profunda (roca somera), Serie I.
  - clim_*: promedio 2003 a 2025 de las variables de clima de abajo.

Variables por año (una fila por municipio y año). Ventanas del ciclo primavera-verano.
  - prec_may_jun (siembra), prec_jul_ago (crecimiento), prec_sep_oct (llenado y cosecha),
    prec_may_oct (total), en mm.
  - tmax_may_jun, tmax_jul_ago, tmax_sep_oct, tmin_may_oct, amplitud (tmax menos tmin,
    mayo a octubre), en grados C.
  - gdd_may_oct: grados-día con base 0 de mayo a octubre, de la media mensual.
  - anom_*: diferencia contra el promedio 2003 a 2025 del mismo municipio.

Uso:
    uv run python -m generalizable.variables
"""
import calendar

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from exactextract import exact_extract

from parcelas.config import CRS_GEO, CRS_METRICO
from . import EXTERNOS, SALIDA
from .siap import normalizar

MUNICIPIOS = EXTERNOS / "inegi_marcogeo" / "municipios_13_15_21_29.gpkg"
USV = EXTERNOS / "inegi_usv" / "agricultura_temporal_4estados.gpkg"
SUELO2 = EXTERNOS / "inegi_edafologia" / "serie2_4estados.gpkg"
SUELO1 = EXTERNOS / "inegi_edafologia" / "serie1_4estados.gpkg"
CLIMA = EXTERNOS / "clima"
TOPO = EXTERNOS / "topografia"

ANIOS = range(2003, 2026)
MIN_AGRICOLA_HA = 100.0
GRUPOS_SUELO = ("PH", "LP", "RG", "AN", "VR", "LV", "CM", "DU")
VENTANAS = {"may_jun": (5, 6), "jul_ago": (7, 8), "sep_oct": (9, 10)}
TEMPORADA = (5, 6, 7, 8, 9, 10)
NOMBRE_ESTADO = {"13": "Hidalgo", "15": "México", "21": "Puebla", "29": "Tlaxcala"}


def municipios():
    """Polígonos municipales con clave normalizada, en EPSG:6372."""
    g = gpd.read_file(MUNICIPIOS).to_crs(CRS_METRICO)
    g["estado"] = g.CVE_ENT.astype(str).str.zfill(2).map(NOMBRE_ESTADO)
    g["clave"] = g.NOMGEO.map(normalizar)
    return g[["CVEGEO", "estado", "clave", "NOMGEO", "geometry"]]


def _solo_poligonos(g):
    """MultiPolygon con las partes poligonales de una geometría (descarta líneas y puntos)."""
    partes = [p for p in shapely.get_parts(g) if p.geom_type in ("Polygon", "MultiPolygon")]
    partes = [q for p in partes for q in shapely.get_parts(p)]
    return shapely.MultiPolygon(partes) if partes else shapely.MultiPolygon()


def zonas_agricolas(mun):
    """Geometría de agricultura de temporal dentro de cada municipio.

    Devuelve el GeoDataFrame de municipios con la geometría recortada, más agricola_ha,
    frac_agricola y zona_completa.
    """
    usv = gpd.read_file(USV).to_crs(CRS_METRICO)
    temporal = usv[usv.DESCRIPCIO.str.contains("TEMPORAL")].geometry.union_all()
    z = mun.copy()
    area_mun = z.geometry.area
    z["geometry"] = [_solo_poligonos(g) for g in z.geometry.intersection(temporal)]
    z["agricola_ha"] = z.geometry.area / 1e4
    z["frac_agricola"] = z.agricola_ha * 1e4 / area_mun
    z["zona_completa"] = z.agricola_ha < MIN_AGRICOLA_HA
    z.loc[z.zona_completa, "geometry"] = [_solo_poligonos(g) for g in mun.loc[z.zona_completa, "geometry"]]
    return z


def _fracciones(zonas, capa, columna, valores):
    """Fracción del área de cada zona cubierta por cada valor de `columna` de la capa."""
    inter = gpd.overlay(zonas[["CVEGEO", "geometry"]], capa[[columna, "geometry"]], how="intersection",
                        keep_geom_type=True)
    inter["a"] = inter.geometry.area
    total = inter.groupby("CVEGEO").a.sum()
    out = pd.DataFrame(index=zonas.CVEGEO)
    for nombre, cond in valores.items():
        out[nombre] = inter[cond(inter[columna])].groupby("CVEGEO").a.sum().reindex(out.index).fillna(0) \
            / total.reindex(out.index)
    return out


def variables_suelo(zonas):
    s2 = gpd.read_file(SUELO2).to_crs(CRS_METRICO)
    s2 = s2[~s2.GRUPO1.isin(["NA", "N/A"])]
    grupos = {f"suelo_{k.lower()}": (lambda c, k=k: c == k) for k in GRUPOS_SUELO}
    grupos["suelo_otro"] = lambda c: ~c.isin(GRUPOS_SUELO)
    f = _fracciones(zonas, s2, "GRUPO1", grupos)
    t = _fracciones(zonas, s2, "CLASE_TEXT", {"textura_fina": lambda c: c.astype(str) == "3",
                                              "textura_gruesa": lambda c: c.astype(str) == "1"})
    s1 = gpd.read_file(SUELO1).to_crs(CRS_METRICO)
    s1 = s1[~s1.FAS_FISCA.isin(["N/A"])]
    d = _fracciones(zonas, s1, "FAS_FISCA", {"frac_durica": lambda c: c.str.startswith("Dúrica"),
                                             "frac_litica": lambda c: c.str.startswith("Lítica")})
    return pd.concat([f, t, d], axis=1).fillna(0.0)


def variables_topo(zonas):
    z = zonas.to_crs(CRS_GEO)
    out = pd.DataFrame(index=zonas.CVEGEO)
    for nombre, archivo in (("elev_m", "elevacion_m.tif"), ("pendiente", "pendiente_grados.tif")):
        d = exact_extract(str(TOPO / archivo), z, ["mean"], include_cols=["CVEGEO"], output="pandas")
        out[nombre] = d.set_index("CVEGEO")["mean"]
    return out


def _mensual(zonas, variable, anio):
    """DataFrame CVEGEO x mes con la media ponderada de cada banda del año."""
    ruta = CLIMA / variable.lower() / f"{variable.upper()}_{anio}.tif"
    d = exact_extract(str(ruta), zonas, ["mean"], include_cols=["CVEGEO"], output="pandas").set_index("CVEGEO")
    d.columns = range(1, 13)
    return d


def variables_clima(zonas):
    """Tabla larga CVEGEO-año con las variables de clima del ciclo."""
    z = zonas.to_crs(CRS_GEO)
    filas = []
    for anio in ANIOS:
        p, tx, tn = (_mensual(z, v, anio) for v in ("prec", "tmax", "tmin"))
        d = pd.DataFrame(index=p.index)
        d["anio"] = anio
        for nombre, meses in VENTANAS.items():
            d[f"prec_{nombre}"] = p[list(meses)].sum(axis=1)
            d[f"tmax_{nombre}"] = tx[list(meses)].mean(axis=1)
        d["prec_may_oct"] = p[list(TEMPORADA)].sum(axis=1)
        d["tmin_may_oct"] = tn[list(TEMPORADA)].mean(axis=1)
        d["amplitud"] = tx[list(TEMPORADA)].mean(axis=1) - d.tmin_may_oct
        dias = np.array([calendar.monthrange(anio, m)[1] for m in TEMPORADA])
        tmed = (tx[list(TEMPORADA)].to_numpy() + tn[list(TEMPORADA)].to_numpy()) / 2
        d["gdd_may_oct"] = (np.clip(tmed, 0, None) * dias).sum(axis=1)
        filas.append(d.reset_index())
    c = pd.concat(filas, ignore_index=True)
    cols = [k for k in c.columns if k not in ("CVEGEO", "anio")]
    clim = c.groupby("CVEGEO")[cols].transform("mean")
    for k in cols:
        c[f"anom_{k}"] = c[k] - clim[k]
    return c, cols


def construir():
    """Escribe en data/processed/generalizable/ las tablas municipios y clima."""
    mun = municipios()
    zonas = zonas_agricolas(mun)
    cent = zonas.geometry.representative_point()
    fijas = pd.DataFrame({"CVEGEO": zonas.CVEGEO, "estado": zonas.estado, "clave": zonas.clave,
                          "municipio": zonas.NOMGEO, "x_m": cent.x.to_numpy(), "y_m": cent.y.to_numpy(),
                          "agricola_ha": zonas.agricola_ha, "frac_agricola": zonas.frac_agricola,
                          "zona_completa": zonas.zona_completa}).set_index("CVEGEO")
    ll = gpd.GeoSeries(cent, crs=CRS_METRICO).to_crs(CRS_GEO)
    fijas["lon"], fijas["lat"] = ll.x.to_numpy(), ll.y.to_numpy()
    fijas = fijas.join(variables_topo(zonas)).join(variables_suelo(zonas))
    clima, cols = variables_clima(zonas)
    clim = clima.groupby("CVEGEO")[cols].mean().add_prefix("clim_")
    fijas = fijas.join(clim)
    SALIDA.mkdir(parents=True, exist_ok=True)
    fijas.reset_index().to_parquet(SALIDA / "municipios.parquet", index=False)
    clima.to_parquet(SALIDA / "clima_anual.parquet", index=False)
    gpd.GeoDataFrame(zonas[["CVEGEO", "agricola_ha"]], geometry=zonas.geometry) \
        .to_file(SALIDA / "zonas_agricolas.gpkg", layer="zonas", driver="GPKG")
    return fijas, clima


if __name__ == "__main__":
    f, c = construir()
    print(f.describe().T.round(2).to_string())
    print(c.shape)
