"""Variables de clima y topografía por parcela (no usan el rendimiento).

Los valores de cada ráster se extraen con `exactextract`, ponderando cada celda por la
fracción de su área que cubre el polígono de la parcela. El clima (CHIRPS y CHIRTS-ERA5,
mensual, 0.05 grados) está en EPSG:4326. La topografía (INEGI CEM, 120 m) está en EPSG:6372,
así que las parcelas se reproyectan a ese CRS antes de extraer.

Columnas.
  - clima_*: lluvia, temperatura y sus anomalías de 2025 frente al promedio 2022 a 2024.
  - topo_*: elevación, pendiente, aspecto (seno y coseno) e índice de posición topográfica.

Uso:
    uv run python -m agrocebada.features_env
"""
import calendar

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from exactextract import exact_extract

from .config import CRS_GEO, CRS_METRICO, INTERIM, PROCESSED
from .io import extraer_rasteres

ANIO = 2025
ANIOS_HISTORIA = (2022, 2023, 2024)
UMBRAL_TMAX = 23.0  # °C. Meses de mayo a septiembre con Tmax media sobre este valor
PENDIENTE_PLANA = 1.0  # grados. Bajo este valor el aspecto se toma como indefinido (0, 0)
ANILLO_M = (500.0, 1000.0)  # distancia al borde de la parcela del anillo del TPI


def _media(ruta, gdf, col="ID_POLIGONO"):
    """Media ponderada por área de un ráster en cada polígono (Serie indexada por ID)."""
    d = exact_extract(str(ruta), gdf, ["mean"], include_cols=[col], output="pandas")
    return d.set_index(col)["mean"]


def celdas_clima(gdf, ruta):
    """Número de celdas de clima distintas que cubren las parcelas.

    Devuelve (celdas con cobertura mayor a cero, celdas dominantes de cada parcela,
    celdas que contienen al centroide).
    """
    d = exact_extract(str(ruta), gdf, ["cell_id", "coverage"], output="pandas")
    tocadas = {int(c) for ids in d["cell_id"] for c in np.atleast_1d(ids)}
    dominante = {int(np.atleast_1d(i)[int(np.argmax(cv))]) for i, cv in zip(d["cell_id"], d["coverage"])}
    with rasterio.open(ruta) as r:
        cent = gdf.to_crs(CRS_METRICO).geometry.centroid.to_crs(CRS_GEO)
        centroide = {r.index(x, y) for x, y in zip(cent.x, cent.y)}
    return len(tocadas), len(dominante), len(centroide)


def _clima_mensual(rasteres, gdf):
    """Dict variable -> DataFrame (ID x (año, mes)) con la media de cada ráster mensual."""
    out = {}
    for var, clave in (("prec", "precipitacion"), ("tmax", "tmax"), ("tmin", "tmin")):
        cols = {k: _media(ruta, gdf) for k, ruta in rasteres[clave].items()}
        out[var] = pd.DataFrame(cols)
    return out


def _resumen_clima(m, anio):
    """Variables climáticas de un año a partir de las tablas mensuales."""
    p, tx, tn = m["prec"], m["tmax"], m["tmin"]
    suma = lambda tab, meses: tab[[(anio, k) for k in meses]].sum(axis=1)
    media = lambda tab, meses: tab[[(anio, k) for k in meses]].mean(axis=1)
    meses = [5, 6, 7, 8, 9]
    tmed = (tx[[(anio, k) for k in meses]].to_numpy() + tn[[(anio, k) for k in meses]].to_numpy()) / 2
    dias = np.array([calendar.monthrange(anio, k)[1] for k in meses])
    return pd.DataFrame({
        "prec_total_may_oct": suma(p, range(5, 11)),
        "prec_siembra": suma(p, [5, 6]),
        "prec_crecimiento": suma(p, [7, 8]),
        "prec_cosecha": suma(p, [9, 10]),
        "tmax_media_may_sep": media(tx, meses),
        "tmin_media_may_sep": media(tn, meses),
        "amplitud_termica": media(tx, meses) - media(tn, meses),
        "gdd0_may_sep": pd.Series((np.clip(tmed, 0, None) * dias).sum(axis=1), index=p.index),
        "meses_tmax_sobre_umbral": pd.Series(
            (tx[[(anio, k) for k in meses]].to_numpy() > UMBRAL_TMAX).sum(axis=1), index=p.index).astype(float),
    })


def clima(gdf, doy_pico, rasteres):
    """Variables climáticas de 2025, anomalías contra 2022 a 2024 y lluvia cerca del pico."""
    m = _clima_mensual(rasteres, gdf)
    r25 = _resumen_clima(m, ANIO)
    hist = sum(_resumen_clima(m, a) for a in ANIOS_HISTORIA) / len(ANIOS_HISTORIA)
    out = r25.add_prefix("clima_")
    for c in ["prec_total_may_oct", "prec_siembra", "prec_crecimiento", "prec_cosecha",
              "tmax_media_may_sep", "tmin_media_may_sep"]:
        out[f"clima_anom_{c}"] = r25[c] - hist[c]
    # Ventana fenológica con clima mensual: lluvia del mes del pico y del mes anterior
    fecha = pd.Timestamp(f"{ANIO}-01-01") + pd.to_timedelta(doy_pico.reindex(out.index) - 1, unit="D")
    mes = fecha.dt.month
    p = m["prec"]
    out["clima_prec_mes_pico"] = [p.loc[i, (ANIO, int(k))] if pd.notna(k) else np.nan for i, k in mes.items()]
    out["clima_prec_mes_previo"] = [p.loc[i, (ANIO, int(k) - 1)] if pd.notna(k) else np.nan for i, k in mes.items()]
    return out


def _aspecto(ruta_dem, ruta_pend):
    """Escribe en data/interim los rásteres de seno y coseno del aspecto y devuelve sus rutas.

    El aspecto es la dirección de la bajada máxima, medida desde el norte hacia el este. Se
    deriva del DEM con el gradiente de numpy en metros, así que seno = -dz/dx / |gradiente| y
    coseno = -dz/dy_norte / |gradiente|. Donde la pendiente es casi plana ambos valen 0.
    """
    with rasterio.open(ruta_dem) as r:
        dem = r.read(1).astype("float64")
        perfil = r.profile
        res_x, res_y = r.res
        nodata = r.nodata
    dem[dem == nodata] = np.nan
    dz_fila, dz_col = np.gradient(dem, res_y, res_x)  # filas crecen hacia el sur
    dz_este, dz_norte = dz_col, -dz_fila
    g = np.hypot(dz_este, dz_norte)
    pendiente = np.degrees(np.arctan(g))
    plano = pendiente < PENDIENTE_PLANA
    with np.errstate(invalid="ignore", divide="ignore"):
        seno = np.where(plano, 0.0, -dz_este / g)
        coseno = np.where(plano, 0.0, -dz_norte / g)
    seno[np.isnan(dem) | np.isnan(g)] = nodata
    coseno[np.isnan(dem) | np.isnan(g)] = nodata
    perfil.update(dtype="float32", nodata=nodata)
    INTERIM.mkdir(parents=True, exist_ok=True)
    rutas = {}
    for nombre, arr in (("seno", seno), ("coseno", coseno)):
        ruta = INTERIM / f"aspecto_{nombre}.tif"
        with rasterio.open(ruta, "w", **perfil) as w:
            w.write(arr.astype("float32"), 1)
        rutas[nombre] = ruta
    return rutas


def topografia(gdf, rasteres):
    """Elevación, pendiente, aspecto y TPI por parcela (parcelas reproyectadas a EPSG:6372)."""
    g = gdf[["ID_POLIGONO", "geometry"]].to_crs(CRS_METRICO)
    elev = _media(rasteres["elevacion"], g)
    asp = _aspecto(rasteres["elevacion"], rasteres["pendiente"])
    anillo = g.copy()
    anillo["geometry"] = g.buffer(ANILLO_M[1]).difference(g.buffer(ANILLO_M[0]))
    elev_anillo = _media(rasteres["elevacion"], anillo)
    return pd.DataFrame({
        "topo_elevacion": elev,
        "topo_pendiente": _media(rasteres["pendiente"], g),
        "topo_aspecto_seno": _media(asp["seno"], g),
        "topo_aspecto_coseno": _media(asp["coseno"], g),
        "topo_tpi": elev - elev_anillo,
    })


def construir(gdf=None, doy_pico=None):
    """DataFrame con ID_POLIGONO, variables de clima y de topografía."""
    gdf = gpd.read_file(PROCESSED / "parcelas.gpkg") if gdf is None else gdf
    if doy_pico is None:
        fs = pd.read_parquet(PROCESSED / "features_sat.parquet").set_index("ID_POLIGONO")
        doy_pico = fs["fen_pico_doy"]
    r = extraer_rasteres()
    tocadas, dominantes, centroide = celdas_clima(gdf, r["precipitacion"][(ANIO, 6)])
    print(f"Celdas de clima: {tocadas} con cobertura, {dominantes} dominantes, {centroide} por centroide")
    g = gdf[["ID_POLIGONO", "geometry"]]
    c = clima(g, doy_pico, r)
    t = topografia(g, r)
    out = pd.concat([c, t], axis=1).reindex(sorted(g["ID_POLIGONO"]))
    out.index.name = "ID_POLIGONO"
    return out.reset_index()


def main():
    df = construir()
    df.to_parquet(PROCESSED / "features_env.parquet", index=False)
    print(f"{df.shape[0]} filas, {df.shape[1] - 1} columnas -> features_env.parquet")
    print(df.describe().T[["mean", "std", "min", "max"]].round(3).to_string())


if __name__ == "__main__":
    main()
