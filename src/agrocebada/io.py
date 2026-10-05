"""Lectores del dataset crudo del reto."""
import zipfile

import geopandas as gpd
import pandas as pd

from .config import CRS_GEO, INTERIM, RAW

ARCHIVO_BASICO = RAW / "Conjunto_datos_BASICO_AgroCebada2026.csv"
ARCHIVO_PRO = RAW / "Conjunto_datos_PRO_AgroCebada.csv"
ARCHIVO_ETIQUETAS = RAW / "ID_area_rendimiento_70_30_Reto_AgroCebada.csv"
ZIP_PARCELAS = RAW / "Parcelas_Reto_AGC_CONJUNTO_70_30.zip"
ZIP_PRECIPITACION = RAW / "Reto_AgroCebada_CHIRPS_Precipitacion_2022_2025.zip"
ZIP_TEMPERATURA = RAW / "Reto_AgroCebada_Temperatura_2022_2025_RECORTADA_CHIRPS.zip"
ZIP_TOPOGRAFIA = RAW / "Reto_AgroCebada_Topografia_INEGI_CEM4.zip"


def _leer_satelital(ruta):
    df = pd.read_csv(ruta, encoding="utf-8-sig")
    # Las fechas vienen como DD/MM/AAAA; comparar el texto da rangos incorrectos
    df["fecha_captura"] = pd.to_datetime(df["fecha_captura"], dayfirst=True, format="%d/%m/%Y")
    df["sensor"] = df["sensor"].astype("category")
    return df


def leer_basico():
    """Serie satelital del conjunto Básico (Sentinel-2 y Landsat, 2022-2025)."""
    return _leer_satelital(ARCHIVO_BASICO)


def leer_pro():
    """Serie satelital del conjunto PRO (Planet, 2025)."""
    return _leer_satelital(ARCHIVO_PRO)


def leer_etiquetas():
    """ID_POLIGONO, AREA_HA, RENDIMIENTO_T_HA (t/ha, NaN en PREDICCION) y CONJUNTO."""
    df = pd.read_csv(ARCHIVO_ETIQUETAS, encoding="utf-8-sig")
    # El CSV termina cada fila con una coma, lo que genera una columna vacía
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    return df[["ID_POLIGONO", "AREA_HA", "RENDIMIENTO_T_HA", "CONJUNTO"]]


def leer_parcelas():
    """GeoDataFrame de polígonos en EPSG:4326 con ID_POLIGONO, Estado, Municipio y Cultivo.

    El campo Cultivo es "Cebada" en Tlaxcala y "CEBADA" en el resto. El shapefile trae
    también un área (`área_ha`) y el conjunto; se descartan porque las etiquetas son la
    fuente oficial de ambos.
    """
    gdf = gpd.read_file(f"zip://{ZIP_PARCELAS}")
    gdf = gdf.rename(columns={"ID_POLIGON": "ID_POLIGONO"})
    assert str(gdf.crs) == CRS_GEO, f"CRS inesperado: {gdf.crs}"
    return gdf[["ID_POLIGONO", "Estado", "Municipio", "Cultivo", "geometry"]]


def _extraer(zip_ruta):
    """Descomprime un ZIP en data/interim/ solo si aún no se hizo."""
    destino = INTERIM / zip_ruta.stem
    marca = destino / ".extraido"
    if not marca.exists():
        destino.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_ruta) as z:
            z.extractall(destino)
        marca.touch()
    return destino


def extraer_rasteres():
    """Descomprime los ZIP de rásteres en data/interim/ (idempotente) y devuelve sus rutas.

    Devuelve un dict con:
      - "precipitacion": {(año, mes): ruta}. CHIRPS, mm/mes acumulados, EPSG:4326, 0.05°
        (~5 km), 65 columnas x 72 filas, NoData -9999. 2022-2025.
      - "tmax" y "tmin": {(año, mes): ruta}. CHIRTS-ERA5, promedio mensual de la
        temperatura máxima/mínima diaria en °C, EPSG:4326, 0.05°, misma malla que CHIRPS,
        NoData -9999. 2022-2025.
      - "elevacion": ruta. INEGI CEM, m s.n.m., EPSG:6372, 120 m, NoData -9999.
      - "pendiente": ruta. Pendiente en grados (método Horn 3x3) derivada del DEM de 120 m,
        EPSG:6372, NoData -9999.
    Las unidades y el CRS vienen de los LEEME.txt e inventarios de cada ZIP.
    """
    def serie(carpeta, prefijo):
        out = {}
        for ruta in sorted(carpeta.rglob(f"{prefijo}_*.tif")):
            _, anio, mes = ruta.stem.split("_")
            out[(int(anio), int(mes))] = ruta
        return out

    prec = _extraer(ZIP_PRECIPITACION)
    temp = _extraer(ZIP_TEMPERATURA)
    topo = _extraer(ZIP_TOPOGRAFIA)
    return {
        "precipitacion": serie(prec, "PREC"),
        "tmax": serie(temp / "Reto_AgroCebada_Temperatura_2022_2025" / "Tmax", "Tmax"),
        "tmin": serie(temp / "Reto_AgroCebada_Temperatura_2022_2025" / "Tmin", "Tmin"),
        "elevacion": next(topo.rglob("Elevacion_*.tif")),
        "pendiente": next(topo.rglob("Pendiente_*.tif")),
    }
