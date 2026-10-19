"""Descarga del SIAP la asignación de cada municipio a su Distrito de Desarrollo Rural (DDR).

El SIAP estima el rendimiento por distrito o por CADER y muchas veces repite la misma cifra en
municipios vecinos. Para validar sin que esa repetición ayude al interpolador, hace falta saber
qué municipios comparten distrito. El portal lo da en el reporte "Por Distrito - Municipio"
(opcionDDRMpio = 3), con los mismos filtros que `scripts/descargas/siap.py` (cebada grano,
temporal, primavera-verano).

Se pide un reporte por estado y año porque la asignación puede cambiar con el tiempo. Escribe
data/externos/siap/ddr_municipio.csv con las columnas anio, estado, ddr y municipio.

Uso:
    uv run --with requests python scripts/descargas/ddr.py
"""
import html
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from siap import (CEBADA_GRANO, CICLO_PV, ESTADOS, SALIDA, TEMPORAL, TONELADA, URL,  # noqa: E402
                            _xajax)

POR_DDR_MUNICIPIO = 3


def descargar(sesion, entidad, anio):
    """Filas (ddr, municipio) del reporte por distrito y municipio, o lista vacía sin datos."""
    resp = _xajax(sesion, "reporte", 1, anio, CICLO_PV, TEMPORAL, entidad, 0, 0, CEBADA_GRANO, TONELADA, 0,
                  POR_DDR_MUNICIPIO, 0, 0, 0, "")
    if "Sin datos" in resp:
        return []
    r = sesion.get(URL + "Clases/reporte.php", timeout=120)
    r.raise_for_status()
    crudo = r.content.decode("utf-8", errors="replace")
    if f"</strong> {anio}<br" not in crudo:
        raise requests.RequestException(f"el archivo descargado no es del año {anio}")
    filas = []
    for tr in re.findall(r"<tr>(.*?)</tr>", crudo, re.S):
        c = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        # Número, estado, distrito, municipio y las siete cifras.
        if len(c) == 11 and c[0].isdigit():
            filas.append({"estado": c[1], "ddr": c[2], "municipio": c[3]})
    return filas


def main():
    sesion = requests.Session()
    sesion.get(URL, timeout=60)
    filas = []
    for anio in range(2003, 2026):
        for entidad, nombre in ESTADOS.items():
            for intento in range(3):
                try:
                    f = descargar(sesion, entidad, anio)
                    break
                except requests.RequestException:
                    time.sleep(5 * (intento + 1))
            else:
                raise RuntimeError(f"no se pudo descargar {nombre} {anio}")
            filas += [{"anio": anio, **x} for x in f]
            print(f"{nombre} {anio}: {len(f)} municipios", flush=True)
    df = pd.DataFrame(filas).sort_values(["estado", "anio", "ddr", "municipio"])
    df.to_csv(SALIDA / "ddr_municipio.csv", index=False)
    print(df.groupby(["estado", "ddr"]).municipio.nunique().to_string())


if __name__ == "__main__":
    main()
