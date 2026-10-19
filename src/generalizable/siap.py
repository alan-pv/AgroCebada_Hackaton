"""Tabla municipio-año del SIAP: lectura, limpieza y marcas de calidad.

Parte del consolidado que escribe `scripts/descargas/siap.py`. Cada fila es un municipio en un
año, con la cebada grano de temporal del ciclo primavera-verano.

Columnas que agrega.
  - rend: rendimiento oficial, producción entre superficie cosechada (t/ha). Es el objetivo.
  - rend_sembrada: producción entre superficie sembrada. Incluye la pérdida por siniestro y
    es el objetivo de riesgo.
  - frac_siniestro: superficie siniestrada entre sembrada.
  - marca_siniestro: frac_siniestro mayor a UMBRAL_SINIESTRO.
  - marca_entero: rendimiento entero exacto (4.00, 5.00), señal de cifra redondeada.
  - marca_bajo: rendimiento menor a RENDIMIENTO_BAJO.
  - marca_repetido: el mismo rendimiento (a dos decimales) aparece en otro municipio del
    mismo estado y año. El SIAP estima muchas veces por distrito o por CADER y copia la cifra
    en los municipios del bloque. Esas filas no son mediciones independientes y hacen ver
    más parecidos a los vecinos de lo que son.
  - clave: nombre del municipio normalizado (sin acentos, minúsculas) para cruzar con INEGI.
  - ddr: Distrito de Desarrollo Rural del SIAP (solo en `tabla`), de
    `scripts/descargas/ddr.py`.

Filtro de superficie. Para el rendimiento oficial se excluyen las filas con superficie
cosechada menor a MIN_COSECHADA_HA, porque su rendimiento depende de unas pocas parcelas. Para
el rendimiento sobre sembrada el filtro va sobre la superficie sembrada. Si se filtrara por la
cosechada se perderían justo los años con pérdida casi total, que son el riesgo que se quiere
medir. Los municipios con menos de MIN_ANIOS años válidos también se excluyen.
"""
import unicodedata

import numpy as np
import pandas as pd

from . import EXTERNOS

ARCHIVO = EXTERNOS / "siap" / "cebada_temporal_pv_municipal.csv"
ARCHIVO_DDR = EXTERNOS / "siap" / "ddr_municipio.csv"
MIN_COSECHADA_HA = 50.0
MIN_ANIOS = 5
UMBRAL_SINIESTRO = 0.2
RENDIMIENTO_BAJO = 1.0


def normalizar(nombre):
    """Nombre sin acentos, en minúsculas y con espacios simples."""
    s = unicodedata.normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode()
    return " ".join(s.lower().replace(".", " ").split())


def leer(ruta=ARCHIVO):
    """Consolidado crudo, sin filtrar."""
    return pd.read_csv(ruta)


def marca_repetido(df, columna="rend"):
    """True si el valor de `columna` (a dos decimales) se repite en otro municipio del mismo estado y año.

    Se calcula sobre todas las filas con valor positivo, antes de filtrar por superficie,
    porque un municipio chico con la misma cifra también delata una estimación de bloque.
    """
    v = df[columna].round(2)
    ok = v > 0
    n = df[ok].assign(_v=v[ok]).groupby(["estado", "anio", "_v"]).municipio.transform("size")
    return (n.reindex(df.index).fillna(0) > 1).to_numpy()


def limpiar(df, min_cosechada=MIN_COSECHADA_HA, min_anios=MIN_ANIOS, filtro="cosechada"):
    """Aplica filtros y marcas. Devuelve una copia ordenada por estado, municipio y año.

    filtro="cosechada" filtra por superficie cosechada y exige rend > 0 (objetivo rend).
    filtro="sembrada" filtra por superficie sembrada y conserva las pérdidas totales
    (objetivo rend_sembrada).
    """
    d = df.dropna(subset=["municipio"]).copy()
    d["clave"] = d.municipio.map(normalizar)
    d["rend"] = d.rendimiento
    d["rend_sembrada"] = d.produccion_t / d.sembrada_ha
    d["frac_siniestro"] = (d.siniestrada_ha / d.sembrada_ha).clip(0, 1)
    d["marca_siniestro"] = d.frac_siniestro > UMBRAL_SINIESTRO
    d["marca_entero"] = np.isclose(d.rend, d.rend.round(0))
    d["marca_bajo"] = d.rend < RENDIMIENTO_BAJO
    d["marca_repetido"] = marca_repetido(d)
    if filtro == "sembrada":
        d = d[(d.sembrada_ha >= min_cosechada) & d.rend_sembrada.notna()]
    else:
        d = d[(d.cosechada_ha >= min_cosechada) & (d.rend > 0)]
    n = d.groupby(["estado", "clave"]).anio.transform("size")
    d = d[n >= min_anios]
    return d.sort_values(["estado", "clave", "anio"]).reset_index(drop=True)


def asignacion_ddr(ruta=ARCHIVO_DDR):
    """Distrito de cada municipio (estado, clave, ddr). Se toma el más frecuente entre años."""
    a = pd.read_csv(ruta)
    a["clave"] = a.municipio.map(normalizar)
    return a.groupby(["estado", "clave"]).ddr.agg(lambda s: s.mode().iloc[0]).reset_index()


def tabla(min_cosechada=MIN_COSECHADA_HA, min_anios=MIN_ANIOS, filtro="cosechada"):
    """Atajo: leer, limpiar y agregar el DDR cuando el archivo existe."""
    d = limpiar(leer(), min_cosechada, min_anios, filtro)
    if ARCHIVO_DDR.exists():
        d = d.merge(asignacion_ddr(), on=["estado", "clave"], how="left")
    return d
