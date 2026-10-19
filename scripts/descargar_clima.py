"""Descarga y prepara el clima mensual (lluvia, Tmax y Tmin) para el modelo municipio-año.

Fuentes del Climate Hazards Center (UCSB):
  - Lluvia: CHIRPS v2.0 mensual global en COG (o v3.0 con --chirps v3).
    https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/cogs/
  - Temperatura: CHIRTS-ERA5 mensual global (promedio de Tmax y Tmin diarias).
    https://data.chc.ucsb.edu/experimental/CHIRTS-ERA5/{tmax,tmin}/tifs/monthly/

Los archivos globales no se bajan completos. Se leen por HTTP con rangos (GDAL /vsicurl/)
y solo se descarga la ventana de interés, que se guarda como GeoTIFF recortado en la
carpeta de descargas. Si el recorte ya existe no se vuelve a pedir.

Ventana: longitud -100.75 a -96.60, latitud 17.75 a 21.45 (83 columnas x 74 filas de
0.05°). Es la misma rejilla de los rásteres del reto, que caen dentro con un desfase de
16 columnas y 1 fila.

Salidas (carpeta --salida, por omisión data/externos/clima):
  - prec/PREC_AAAA.tif, tmax/TMAX_AAAA.tif, tmin/TMIN_AAAA.tif. Doce bandas (enero a
    diciembre), EPSG:4326, float32, nodata -9999, deflate.
  - comparacion_reto.csv. Comparación celda por celda contra los rásteres del reto en los
    años que se traslapan (2022 a 2025). Para la lluvia compara CHIRPS v2.0 y v3.0.

Uso:
    uv run python scripts/descargar_clima.py
    uv run python scripts/descargar_clima.py --inicio 2003 --fin 2025 \\
        --descargas /ruta/clima_descargas --hilos 6
"""
import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.cog")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import Affine
from rasterio.windows import Window

from parcelas.io import extraer_rasteres

RAIZ = Path(__file__).resolve().parents[1]
NODATA = -9999.0
RES = 0.05
OESTE, NORTE = -100.75, 21.45
ANCHO, ALTO = 83, 74  # (-96.60 - -100.75) / 0.05 y (21.45 - 17.75) / 0.05
TRANSFORM = Affine(RES, 0.0, OESTE, 0.0, -RES, NORTE)
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

CHC = "https://data.chc.ucsb.edu"
FUENTES = {
    "chirps_v2": (f"{CHC}/products/CHIRPS-2.0/global_monthly/cogs/"
                  "chirps-v2.0.{a}.{m:02d}.cog"),
    "chirps_v3": (f"{CHC}/products/CHIRPS/v3.0/monthly/global/cogs/"
                  "chirps-v3.0.{a}.{m:02d}.cog"),
    "chirts_era5_tmax": (f"{CHC}/experimental/CHIRTS-ERA5/tmax/tifs/monthly/"
                         "CHIRTS-ERA5.monthly_Tmax.{a}.{m:02d}.tif"),
    "chirts_era5_tmin": (f"{CHC}/experimental/CHIRTS-ERA5/tmin/tifs/monthly/"
                         "CHIRTS-ERA5.monthly_Tmin.{a}.{m:02d}.tif"),
}


def ventana_de(src):
    """Ventana de la rejilla global que corresponde a la zona de estudio."""
    t = src.transform
    col = round((OESTE - t.c) / t.a)
    fila = round((t.f - NORTE) / -t.e)
    # Comprueba que los centros de celda coinciden (tolerancia de una milésima de celda).
    assert abs(t.c + col * t.a - OESTE) < RES * 1e-3, "rejilla desalineada en longitud"
    assert abs(t.f + fila * t.e - NORTE) < RES * 1e-3, "rejilla desalineada en latitud"
    return Window(col, fila, ANCHO, ALTO)


def limpiar(arr):
    """Marca como nodata los valores de relleno de las fuentes (océano y faltantes)."""
    arr = arr.astype("float32")
    arr[~np.isfinite(arr) | (arr < -900)] = NODATA
    return arr


def escribir(ruta, bandas, descripciones):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    perfil = dict(driver="GTiff", dtype="float32", nodata=NODATA, width=ANCHO,
                  height=ALTO, count=len(bandas), crs="EPSG:4326", transform=TRANSFORM,
                  compress="deflate", predictor=3, tiled=False)
    with rasterio.open(ruta, "w", **perfil) as dst:
        for i, (b, d) in enumerate(zip(bandas, descripciones), start=1):
            dst.write(b, i)
            dst.set_band_description(i, d)


def descargar_mes(fuente, anio, mes, carpeta, intentos=5):
    """Lee la ventana del archivo global por HTTP y la guarda recortada. Devuelve la ruta."""
    url = FUENTES[fuente].format(a=anio, m=mes)
    destino = carpeta / fuente / f"{fuente}_{anio}_{mes:02d}.tif"
    if destino.exists():
        return destino
    for intento in range(1, intentos + 1):
        try:
            with rasterio.open(f"/vsicurl/{url}") as src:
                arr = limpiar(src.read(1, window=ventana_de(src)))
            tmp = destino.with_suffix(".tmp.tif")
            escribir(tmp, [arr], [f"{anio}-{mes:02d}"])
            tmp.rename(destino)
            return destino
        except Exception as e:  # noqa: BLE001
            if intento == intentos:
                raise RuntimeError(f"falló {url}: {e}") from e
            time.sleep(3 * intento)


def descargar(fuentes, anios, carpeta, hilos):
    tareas = [(f, a, m) for f in fuentes for a in anios for m in range(1, 13)]
    rutas, fallos = {}, []
    with ThreadPoolExecutor(hilos) as pool:
        futuros = {pool.submit(descargar_mes, f, a, m, carpeta): (f, a, m)
                   for f, a, m in tareas}
        for i, fut in enumerate(as_completed(futuros), start=1):
            clave = futuros[fut]
            try:
                rutas[clave] = fut.result()
            except Exception as e:  # noqa: BLE001
                fallos.append((clave, str(e)))
            if i % 50 == 0 or i == len(tareas):
                print(f"  {i}/{len(tareas)} archivos listos, {len(fallos)} fallos")
    for clave, err in fallos:
        print("FALLO", clave, err)
    return rutas, fallos


def leer(ruta):
    with rasterio.open(ruta) as src:
        return src.read(1)


def comparar(rutas, salida):
    """Compara celda por celda contra los rásteres del reto (2022 a 2025)."""
    reto = extraer_rasteres()
    pares = [("prec", "precipitacion", "chirps_v2"), ("prec", "precipitacion", "chirps_v3"),
             ("tmax", "tmax", "chirts_era5_tmax"), ("tmin", "tmin", "chirts_era5_tmin")]
    filas = []
    for var, clave_reto, fuente in pares:
        for (anio, mes), ruta_reto in sorted(reto[clave_reto].items()):
            if (fuente, anio, mes) not in rutas:
                continue
            with rasterio.open(ruta_reto) as src:
                r = src.read(1)
                t = src.transform
            col = round((t.c - OESTE) / RES)
            fila = round((NORTE - t.f) / RES)
            ext = leer(rutas[(fuente, anio, mes)])[fila:fila + r.shape[0], col:col + r.shape[1]]
            ok = (r != NODATA) & (ext != NODATA) & np.isfinite(r) & np.isfinite(ext)
            d = ext[ok].astype("float64") - r[ok]
            filas.append(dict(
                variable=var, fuente=fuente, anio=anio, mes=mes, n_celdas=int(ok.sum()),
                correlacion=float(np.corrcoef(ext[ok], r[ok])[0, 1]),
                sesgo_medio=float(d.mean()), error_abs_medio=float(np.abs(d).mean()),
                error_abs_max=float(np.abs(d).max())))
    tabla = pd.DataFrame(filas)
    tabla.to_csv(salida / "comparacion_reto.csv", index=False, float_format="%.6g")
    resumen = tabla.groupby(["variable", "fuente"]).agg(
        meses=("mes", "size"), correlacion_min=("correlacion", "min"),
        sesgo_medio=("sesgo_medio", "mean"), error_abs_medio=("error_abs_medio", "mean"),
        error_abs_max=("error_abs_max", "max"))
    print(resumen.to_string())
    return tabla


def ensamblar(rutas, anios, salida, chirps):
    salidas = {"prec": ("PREC", f"chirps_{chirps}"), "tmax": ("TMAX", "chirts_era5_tmax"),
               "tmin": ("TMIN", "chirts_era5_tmin")}
    for var, (prefijo, fuente) in salidas.items():
        for anio in anios:
            claves = [(fuente, anio, m) for m in range(1, 13)]
            if not all(c in rutas for c in claves):
                print(f"AVISO: {var} {anio} incompleto, no se escribe")
                continue
            escribir(salida / var / f"{prefijo}_{anio}.tif",
                     [leer(rutas[c]) for c in claves], MESES)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--inicio", type=int, default=2003)
    p.add_argument("--fin", type=int, default=2025)
    p.add_argument("--descargas", type=Path, required=True,
                   help="carpeta para los recortes descargados (fuera del repo)")
    p.add_argument("--salida", type=Path, default=RAIZ / "data" / "externos" / "clima")
    p.add_argument("--chirps", choices=["v2", "v3"], default="v2",
                   help="versión de CHIRPS para la lluvia final")
    p.add_argument("--hilos", type=int, default=6)
    a = p.parse_args()

    anios = list(range(a.inicio, a.fin + 1))
    traslape = list(range(2022, 2026))
    fuentes = [f"chirps_{a.chirps}", "chirts_era5_tmax", "chirts_era5_tmin"]
    print(f"Descargando {fuentes} para {anios[0]} a {anios[-1]}")
    rutas, fallos = descargar(fuentes, anios, a.descargas, a.hilos)
    otra = "chirps_v3" if a.chirps == "v2" else "chirps_v2"
    print(f"Descargando {otra} 2022 a 2025 solo para la comparación")
    r2, f2 = descargar([otra], traslape, a.descargas, a.hilos)
    rutas.update(r2)

    a.salida.mkdir(parents=True, exist_ok=True)
    comparar(rutas, a.salida)
    ensamblar(rutas, anios, a.salida, a.chirps)
    if fallos or f2:
        raise SystemExit(f"{len(fallos) + len(f2)} descargas fallaron")


if __name__ == "__main__":
    main()
