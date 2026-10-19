"""Descarga el Copernicus DEM GLO-90 y deriva la elevación y la pendiente para los cuatro estados.

Fuente: Copernicus DEM GLO-90 (90 m, 3 segundos de arco), bucket público de AWS sin autenticación,
https://copernicus-dem-90m.s3.amazonaws.com/ . Cada tesela cubre 1° x 1° y se llama
Copernicus_DSM_COG_30_N<lat>_00_W<lon>_00_DEM/Copernicus_DSM_COG_30_N<lat>_00_W<lon>_00_DEM.tif,
donde <lat> y <lon> son la esquina suroeste.

Pasos:
1. Descarga las teselas que tocan la ventana de longitud -100.75 a -96.60 y latitud 17.75 a 21.45
   (Hidalgo, Estado de México, Puebla y Tlaxcala) al directorio de crudos.
2. Arma el mosaico en EPSG:4326 con un margen de 0.05° alrededor de la ventana.
3. Reproyecta el mosaico a EPSG:6372 (México ITRF2008 LCC) a 90 m con interpolación bilineal y
   calcula ahí la pendiente en grados con el método de Horn (3 x 3), para que las distancias estén
   en metros.
4. Agrega a una rejilla EPSG:4326 de 0.0025° alineada a múltiplos de 0.0025 sobre la ventana.
   La elevación es la media de los píxeles nativos (bloques exactos de 3 x 3) y la pendiente es la
   media de los píxeles de 90 m que caen en cada celda.
5. Compara contra el CEM del INEGI a 120 m que entregó el reto en su ventana común. Agrega ambos a
   la misma rejilla de 0.0025° y reporta correlación, sesgo, RMSE y número de celdas.

Salidas en data/externos/topografia/:
    elevacion_m.tif, pendiente_grados.tif   float32, deflate, nodata -9999
    comparacion_reto.csv                    resumen de la comparación

Uso:
    uv run python scripts/descargar_topografia.py                          # crudos en data/interim/copernicus_dem
    uv run python scripts/descargar_topografia.py --crudos /ruta/vacia     # otro directorio de crudos
    uv run python scripts/descargar_topografia.py --resolucion 0.005       # rejilla más gruesa
"""
import argparse
import math
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.crs import CRS
from rasterio.merge import merge
from rasterio.transform import from_origin
from rasterio.warp import Resampling, calculate_default_transform, reproject

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "data/externos/topografia"
BUCKET = "https://copernicus-dem-90m.s3.amazonaws.com"
VENTANA = (-100.75, 17.75, -96.60, 21.45)  # oeste, sur, este, norte
MARGEN = 0.05
NODATA = -9999.0
CRS_GEO = CRS.from_epsg(4326)
CRS_METRICO = CRS.from_epsg(6372)
RES_METRICA = 90.0


def nombre_tesela(lat, lon):
    ns = f"N{lat:02d}" if lat >= 0 else f"S{-lat:02d}"
    ew = f"W{-lon:03d}" if lon < 0 else f"E{lon:03d}"
    base = f"Copernicus_DSM_COG_30_{ns}_00_{ew}_00_DEM"
    return f"{base}/{base}.tif"


def descargar(crudos):
    oeste, sur, este, norte = VENTANA
    crudos.mkdir(parents=True, exist_ok=True)
    rutas = []
    for lat in range(math.floor(sur - MARGEN), math.ceil(norte + MARGEN)):
        for lon in range(math.floor(oeste - MARGEN), math.ceil(este + MARGEN)):
            clave = nombre_tesela(lat, lon)
            destino = crudos / Path(clave).name
            if not destino.exists():
                print(f"descargando {clave}", flush=True)
                tmp = destino.with_suffix(".part")
                try:
                    urllib.request.urlretrieve(f"{BUCKET}/{clave}", tmp)
                except urllib.error.HTTPError as e:
                    print(f"  sin tesela ({e.code}), se omite")
                    continue
                tmp.rename(destino)
            rutas.append(destino)
    return rutas


def pendiente_horn(z, dx, dy):
    """Pendiente en grados con el método de Horn. Los bordes y vecinos sin dato quedan en NaN."""
    p = np.pad(z, 1, constant_values=np.nan)
    a, b, c = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]
    d, f = p[1:-1, :-2], p[1:-1, 2:]
    g, h, i = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * dx)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * dy)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy))).astype("float32")


def rejilla(res, ventana=VENTANA):
    """Rejilla EPSG:4326 alineada a múltiplos de res que cubre la ventana."""
    oeste, sur, este, norte = ventana
    x0, x1 = math.floor(oeste / res + 1e-9) * res, math.ceil(este / res - 1e-9) * res
    y0, y1 = math.floor(sur / res + 1e-9) * res, math.ceil(norte / res - 1e-9) * res
    ancho, alto = round((x1 - x0) / res), round((y1 - y0) / res)
    return from_origin(x0, y1, res, res), ancho, alto


def agregar(src, src_tf, src_crs, dst_tf, ancho, alto):
    dst = np.full((alto, ancho), np.nan, dtype="float32")
    reproject(np.where(np.isnan(src), NODATA, src).astype("float32"), dst,
              src_transform=src_tf, src_crs=src_crs, src_nodata=NODATA,
              dst_transform=dst_tf, dst_crs=CRS_GEO, dst_nodata=np.nan,
              resampling=Resampling.average)
    return dst


def a_metrico(src, src_tf, src_crs, res, nodata=NODATA):
    alto, ancho = src.shape
    oeste, sur, este, norte = rasterio.transform.array_bounds(alto, ancho, src_tf)
    tf, w, h = calculate_default_transform(src_crs, CRS_METRICO, ancho, alto, oeste, sur, este, norte,
                                           resolution=res)
    dst = np.full((h, w), np.nan, dtype="float32")
    reproject(np.where(np.isnan(src), nodata, src).astype("float32"), dst,
              src_transform=src_tf, src_crs=src_crs, src_nodata=nodata,
              dst_transform=tf, dst_crs=CRS_METRICO, dst_nodata=np.nan,
              resampling=Resampling.bilinear)
    return dst, tf


def guardar(ruta, arr, tf, descripcion):
    perfil = dict(driver="GTiff", dtype="float32", count=1, width=arr.shape[1], height=arr.shape[0],
                  crs=CRS_GEO, transform=tf, nodata=NODATA, compress="deflate", predictor=3,
                  tiled=True, blockxsize=256, blockysize=256)
    with rasterio.open(ruta, "w", **perfil) as dst:
        dst.write(np.where(np.isnan(arr), NODATA, arr).astype("float32"), 1)
        dst.set_band_description(1, descripcion)
        dst.update_tags(fuente="Copernicus DEM GLO-90, " + BUCKET, consulta="2026-10-09")


def leer(ruta):
    with rasterio.open(ruta) as r:
        a = r.read(1).astype("float32")
        if r.nodata is not None:
            a[a == r.nodata] = np.nan
        return a, r.transform, r.crs, r.bounds


def estadisticos(nombre, a, b):
    m = np.isfinite(a) & np.isfinite(b)
    x, y = a[m].astype("float64"), b[m].astype("float64")
    return {"variable": nombre, "celdas": int(m.sum()),
            "correlacion": round(float(np.corrcoef(x, y)[0, 1]), 4),
            "sesgo_copernicus_menos_reto": round(float((x - y).mean()), 3),
            "rmse": round(float(np.sqrt(((x - y) ** 2).mean())), 3),
            "media_copernicus": round(float(x.mean()), 3), "media_reto": round(float(y.mean()), 3)}


def comparar(mosaico, mos_tf, pend90, tf90, res):
    sys.path.insert(0, str(RAIZ / "src"))
    from parcelas.io import extraer_rasteres
    rasteres = extraer_rasteres()
    z_reto, tf_reto, crs_reto, b = leer(rasteres["elevacion"])
    s_reto, _, _, _ = leer(rasteres["pendiente"])
    # Ventana común en grados: bordes del CEM del reto pasados a EPSG:4326, recortados hacia adentro.
    from rasterio.warp import transform_bounds
    oeste, sur, este, norte = transform_bounds(crs_reto, CRS_GEO, *b)
    vent = (max(oeste, VENTANA[0]), max(sur, VENTANA[1]), min(este, VENTANA[2]), min(norte, VENTANA[3]))
    tf, ancho, alto = rejilla(res, vent)

    def g(arr, t, crs):
        return agregar(arr, t, crs, tf, ancho, alto)

    filas = [estadisticos("elevacion_m", g(mosaico, mos_tf, CRS_GEO), g(z_reto, tf_reto, crs_reto)),
             estadisticos("pendiente_grados", g(pend90, tf90, CRS_METRICO),
                          g(s_reto, tf_reto, crs_reto))]
    # Misma pendiente pero calculada a 120 m sobre la malla del reto, para separar el efecto de la resolución.
    z120 = np.full(z_reto.shape, np.nan, dtype="float32")
    reproject(np.where(np.isnan(mosaico), NODATA, mosaico).astype("float32"), z120,
              src_transform=mos_tf, src_crs=CRS_GEO, src_nodata=NODATA,
              dst_transform=tf_reto, dst_crs=crs_reto, dst_nodata=np.nan, resampling=Resampling.average)
    s120 = pendiente_horn(z120, abs(tf_reto.a), abs(tf_reto.e))
    fila = estadisticos("pendiente_grados_copernicus_a_120m", g(s120, tf_reto, crs_reto), g(s_reto, tf_reto, crs_reto))
    filas.append(fila)
    df = pd.DataFrame(filas)
    df.insert(1, "ventana_lon_lat", f"{vent[0]:.4f} {vent[1]:.4f} {vent[2]:.4f} {vent[3]:.4f}")
    df.insert(2, "resolucion_grados", res)
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crudos", type=Path, default=RAIZ / "data/interim/copernicus_dem",
                    help="directorio donde se guardan las teselas descargadas")
    ap.add_argument("--resolucion", type=float, default=0.0025, help="tamaño de celda de salida en grados")
    ap.add_argument("--sin-comparacion", action="store_true", help="no compara contra el CEM del reto")
    args = ap.parse_args()

    rutas = descargar(args.crudos)
    oeste, sur, este, norte = VENTANA
    fuentes = [rasterio.open(r) for r in rutas]
    mosaico, mos_tf = merge(fuentes, bounds=(oeste - MARGEN, sur - MARGEN, este + MARGEN, norte + MARGEN),
                            nodata=NODATA, dtype="float32")
    for f in fuentes:
        f.close()
    mosaico = mosaico[0]
    mosaico[mosaico == NODATA] = np.nan
    print(f"mosaico {mosaico.shape}, celda {mos_tf.a:.8f}°", flush=True)

    z90, tf90 = a_metrico(mosaico, mos_tf, CRS_GEO, RES_METRICA)
    pend90 = pendiente_horn(z90, RES_METRICA, RES_METRICA)
    print(f"malla métrica {z90.shape}", flush=True)

    tf, ancho, alto = rejilla(args.resolucion)
    elev = agregar(mosaico, mos_tf, CRS_GEO, tf, ancho, alto)
    pend = agregar(pend90, tf90, CRS_METRICO, tf, ancho, alto)
    SALIDA.mkdir(parents=True, exist_ok=True)
    guardar(SALIDA / "elevacion_m.tif", elev, tf, "elevacion media, m (Copernicus GLO-90, EGM2008)")
    guardar(SALIDA / "pendiente_grados.tif", pend, tf,
            "pendiente media, grados (Horn 3x3 a 90 m en EPSG:6372)")
    print(f"rejilla {alto} x {ancho} a {args.resolucion}°")
    for nombre in ("elevacion_m.tif", "pendiente_grados.tif"):
        print(f"  {nombre}: {(SALIDA / nombre).stat().st_size / 1e6:.1f} MB")

    if not args.sin_comparacion:
        df = comparar(mosaico, mos_tf, pend90, tf90, args.resolucion)
        df.to_csv(SALIDA / "comparacion_reto.csv", index=False)
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
