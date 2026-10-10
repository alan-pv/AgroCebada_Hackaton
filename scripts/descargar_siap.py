"""Descarga el cierre agrícola municipal del SIAP para la cebada grano de temporal, ciclo primavera-verano.

Consulta el portal https://nube.agricultura.gob.mx/cierre_agricola/ con las mismas llamadas que hace
la página (xajax) y guarda el archivo que ofrece el botón de descarga, uno por estado y año, en
data/externos/siap/<estado>_<año>.xls (son tablas HTML aunque la extensión diga .xls). Después
consolida todo en data/externos/siap/cebada_temporal_pv_municipal.csv.

Filtros: reporte por ubicación geográfica, por municipio; ciclo primavera-verano (2); modalidad
temporal (2); cultivo cebada grano (77); unidad tonelada (200201); variedad, tipo de agricultura,
tipo de producción y tipo de mercado en "todo".

Uso:
    uv run --with requests python scripts/descargar_siap.py                       # 2003 a 2025, los cuatro estados
    uv run --with requests python scripts/descargar_siap.py --anios 2020 2025     # solo un rango
    uv run --with requests python scripts/descargar_siap.py --solo-consolidar     # sin descargar
"""
import argparse
import html
import re
import time
from pathlib import Path

import pandas as pd
import requests

URL = "https://nube.agricultura.gob.mx/cierre_agricola/"
SALIDA = Path(__file__).resolve().parents[1] / "data/externos/siap"
ESTADOS = {13: "hidalgo", 15: "mexico", 21: "puebla", 29: "tlaxcala"}
CICLO_PV, TEMPORAL, CEBADA_GRANO, TONELADA, POR_MUNICIPIO = 2, 2, 77, 200201, 1
COLUMNAS = ["sembrada_ha", "cosechada_ha", "siniestrada_ha", "produccion_t", "rendimiento",
            "precio_rural", "valor_miles"]


def _xajax(sesion, funcion, *args):
    r = sesion.post(URL, data=[("xajax", funcion)] + [("xajaxargs[]", str(a)) for a in args], timeout=120)
    r.raise_for_status()
    r.encoding = "latin1"
    return r.text


def descargar(sesion, entidad, anio):
    """Pide el reporte y devuelve el HTML del botón de descarga, o None si el portal no tiene datos."""
    resp = _xajax(sesion, "reporte", 1, anio, CICLO_PV, TEMPORAL, entidad, 0, 0, CEBADA_GRANO, TONELADA, 0,
                  POR_MUNICIPIO, 0, 0, 0, "")
    if "Sin datos" in resp:
        return None
    r = sesion.get(URL + "Clases/reporte.php", timeout=120)
    r.raise_for_status()
    # El archivo de descarga sale de la sesión. Se comprueba que sea el del año pedido.
    if f"</strong> {anio}<br" not in r.content.decode("utf-8", errors="replace"):
        raise requests.RequestException(f"el archivo descargado no es del año {anio}")
    return r.content


def leer(ruta):
    """Filas de una tabla del SIAP como lista de dicts. El portal escribe el HTML en UTF-8."""
    crudo = ruta.read_bytes().decode("utf-8", errors="replace")
    filas = []
    for tr in re.findall(r"<tr>(.*?)</tr>", crudo, re.S):
        c = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(c) == 10 and c[0].isdigit():
            fila = {"estado": c[1], "municipio": c[2]}
            fila.update({k: float(v.replace(",", "")) for k, v in zip(COLUMNAS, c[3:])})
            filas.append(fila)
    return filas


def consolidar():
    filas = []
    for ruta in sorted(SALIDA.glob("*_*.xls")):
        estado, anio = ruta.stem.rsplit("_", 1)
        filas += [{"anio": int(anio), **f} for f in leer(ruta)]
    df = pd.DataFrame(filas).sort_values(["estado", "municipio", "anio"]).reset_index(drop=True)
    df.to_csv(SALIDA / "cebada_temporal_pv_municipal.csv", index=False)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anios", nargs=2, type=int, default=(2003, 2025))
    ap.add_argument("--solo-consolidar", action="store_true")
    a = ap.parse_args()
    if not a.solo_consolidar:
        sesion = requests.Session()
        sesion.get(URL, timeout=60)
        for anio in range(a.anios[0], a.anios[1] + 1):
            for entidad, nombre in ESTADOS.items():
                ruta = SALIDA / f"{nombre}_{anio}.xls"
                if ruta.exists():
                    continue
                for intento in range(3):
                    try:
                        contenido = descargar(sesion, entidad, anio)
                        break
                    except requests.RequestException:
                        time.sleep(5 * (intento + 1))
                else:
                    raise RuntimeError(f"no se pudo descargar {nombre} {anio}")
                if contenido is None:
                    print(f"{nombre} {anio}: sin datos")
                    continue
                ruta.write_bytes(contenido)
                print(f"{nombre} {anio}: {len(leer(ruta))} municipios")
    df = consolidar()
    print(df.groupby(["anio", "estado"]).size().unstack().to_string())


if __name__ == "__main__":
    main()
