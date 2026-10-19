"""Descarga y prepara datos geográficos del INEGI para Hidalgo, México, Puebla y Tlaxcala.

Genera en data/externos/:
    inegi_marcogeo/municipios_13_15_21_29.gpkg     polígonos municipales, Marco Geoestadístico 2025
    inegi_edafologia/serie2_4estados.gpkg          edafología 1:250 000 Serie II (WRB)
    inegi_edafologia/serie1_4estados.gpkg          edafología 1:250 000 Serie I (FAO), con la fase dúrica
    inegi_edafologia/diccionario_serie2.csv        significado de los códigos de las dos series
    inegi_usv/agricultura_temporal_4estados.gpkg   polígonos agrícolas de uso de suelo y vegetación Serie VII

Todo se guarda en EPSG:6372 (México ITRF2008 LCC). Los archivos crudos se quedan en la carpeta
de descargas, que no forma parte del repo. Si un archivo ya está descargado no se vuelve a bajar.

Uso (desde la raíz del repo):
    uv run python scripts/descargas/inegi.py --descargas /ruta/fuera/del/repo
    uv run python scripts/descargas/inegi.py --descargas /ruta --solo municipios suelos

Las hojas 1:250 000 que se usan se eligen solas: son las del catálogo que cruzan la unión
de los cuatro estados. El catálogo cubre un anillo de hojas alrededor, así que el script
falla si algún estado queda en una hoja que no está en el catálogo.
"""
import argparse
import io
import urllib.request
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

RAIZ = Path(__file__).resolve().parents[2]
EXTERNOS = RAIZ / "data" / "externos"
CRS_SALIDA = "EPSG:6372"
LIMITE_MB_MUNICIPIOS = 15
TOLERANCIA_SIMPLIFICACION_M = 20

ESTADOS = {"13": "Hidalgo", "15": "México", "21": "Puebla", "29": "Tlaxcala"}
MUNICIPIOS_ESPERADOS = {"13": 84, "15": 125, "21": 217, "29": 60}

INEGI = "https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos"
URL_MARCOGEO = f"{INEGI}/geografia/marcogeo/794551163061/mg_2025_integrado.zip"
URL_USV = f"{INEGI}/geografia/tematicas/uso_suelo/1_250_000/serie_VII/889463842781_s.zip"
URL_EDAF = f"{INEGI}/geografia/tematicas/Edafologia_hist/1_250_000"

# Clave de hoja 1:250 000 -> UPC del producto en la biblioteca del INEGI.
# Serie II (2007): "Conjunto de Datos Vectorial Edafológico. Escala 1:250 000 Serie II Continuo Nacional <hoja>"
HOJAS_SERIE2 = {
    "E14-1": "702825235185", "E14-2": "702825235222", "E14-3": "702825235239",
    "E14-4": "702825235246", "E14-5": "702825235253", "E14-6": "702825235260",
    "E14-8": "702825235284", "E14-9": "702825235291",
    "F14-7": "702825235703", "F14-8": "702825235710", "F14-9": "702825235727",
    "F14-10": "702825235628", "F14-11": "702825235635", "F14-12": "702825235642",
}
# Serie I: "Conjunto de datos vectoriales de la carta Edafológica escala 1:250 000 serie I <hoja>"
HOJAS_SERIE1 = {
    "E14-1": "702825677558", "E14-2": "702825677565", "E14-3": "702825677572",
    "E14-4": "702825677589", "E14-5": "702825677596", "E14-6": "702825677602",
    "E14-8": "702825234386", "E14-9": "702825234393",
    "F14-7": "702825234621", "F14-8": "702825677787", "F14-9": "702825677794",
    "F14-10": "702825234591", "F14-11": "702825677732", "F14-12": "702825677749",
}
# Las hojas no traen .prj. Según sus metadatos (*_aux.txt) la Serie II está en UTM 14 N ITRF92
# (se lee como WGS 84, difiere en menos de un metro) y la Serie I en UTM 14 N NAD27.
CRS_SERIE2 = "EPSG:32614"
CRS_SERIE1 = "EPSG:26714"
# La Serie VII de uso de suelo viene en Albers con elipsoide GRS80 y datum sin nombre. Es el
# marco ITRF2008 que usa el INEGI desde 2010, así que se declara con ese datum.
CRS_USV = ("+proj=aea +lat_0=12 +lon_0=-102 +lat_1=17.5 +lat_2=29.5 +x_0=2500000 +y_0=0 "
           "+ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs")

COLUMNAS_SERIE2 = ["CLAVE_WRB", "GRUPO1", "CALIFS_G1", "CALIFP_G1", "GRUPO2", "CALIFS_G2", "CALIFP_G2",
                   "GRUPO3", "CALIFS_G3", "CALIFP_G3", "CLASE_TEXT", "FRUDICA"]
COLUMNAS_SERIE1 = ["CLAVE", "NOM_SUE1", "NOM_SUB1", "NOM_SUE2", "NOM_SUB2", "NOM_SUE3", "NOM_SUB3",
                   "CLA_TEX", "FAS_FISCA", "FAS_QUIMI"]

# Significado de los códigos. Fuentes: Diccionario de datos edafológicos 1:250 000 Serie II
# (INEGI 2009, UPC 702825224578), Guía para la interpretación de cartografía Edafología Serie II
# (INEGI 2011, UPC 702825231606) y Guía para la interpretación de cartografía Edafología
# (INEGI 2004, UPC 702825231736) para la Serie I.
DIC_SERIE2 = "Diccionario de datos edafológicos 1:250 000 Serie II, INEGI 2009"
GUIA_SERIE2 = "Guía para la interpretación de cartografía Edafología Serie II, INEGI 2011"
GUIA_SERIE1 = "Guía para la interpretación de cartografía Edafología, INEGI 2004"
WRB = "Base Referencial Mundial del Recurso Suelo (WRB 2006), códigos de calificadores"
CALIFICADORES = "CALIFS_G1 a CALIFS_G3, CALIFP_G1 a CALIFP_G3"
GRUPOS_WRB = {
    "AC": "Acrisol", "AS": "Albeluvisol", "AL": "Alisol", "AN": "Andosol", "AT": "Antrosol",
    "AR": "Arenosol", "CL": "Calcisol", "CM": "Cambisol", "CH": "Chernozem", "CR": "Criosol",
    "DU": "Durisol (capa endurecida con sílice, el tepetate)", "FR": "Ferralsol", "FL": "Fluvisol",
    "GL": "Gleysol", "GY": "Gipsisol", "HS": "Histosol", "KS": "Kastañozem", "LP": "Leptosol",
    "LX": "Lixisol", "LV": "Luvisol", "NT": "Nitisol", "PH": "Phaeozem", "PL": "Planosol",
    "PT": "Plintosol", "PZ": "Podzol", "RG": "Regosol", "SC": "Solonchak", "SN": "Solonetz",
    "UM": "Umbrisol", "VR": "Vertisol",
}
DICCIONARIO = (
    [("serie2", "CLASE_TEXT", "1", "Textura gruesa en los 30 cm superficiales del suelo dominante", DIC_SERIE2),
     ("serie2", "CLASE_TEXT", "2", "Textura media", DIC_SERIE2),
     ("serie2", "CLASE_TEXT", "3", "Textura fina", DIC_SERIE2),
     ("serie2", "CLASE_TEXT", "NA", "No aplica, el polígono es cuerpo de agua o zona urbana", "Inferido de los datos"),
     ("serie2", "FRUDICA", "R", "Fase rúdica con piedras, fragmentos mayores a 7.5 cm en más del 30% de la superficie", GUIA_SERIE2),
     ("serie2", "FRUDICA", "r", "Fase rúdica con gravas, fragmentos de 2 mm a 7.5 cm en más del 30% de la superficie", GUIA_SERIE2),
     ("serie2", "FRUDICA", "NO", "Ninguno, sin limitante física superficial", DIC_SERIE2),
     ("serie2", "FRUDICA", "NA", "No aplica, el polígono es cuerpo de agua o zona urbana", "Inferido de los datos"),
     ("serie2", "CLAVE_WRB", "H2O", "Cuerpo de agua", "Inferido de los datos"),
     ("serie2", "CLAVE_WRB", "ZU", "Zona urbana", "Inferido de los datos"),
     ("serie2", "GRUPO1, GRUPO2, GRUPO3", "NO", "Ninguno, la unidad tiene menos de tres grupos", DIC_SERIE2),
     ("serie2", "GRUPO1, GRUPO2, GRUPO3", "NA", "No aplica, cuerpo de agua o zona urbana", "Inferido de los datos"),
     ("serie2", CALIFICADORES, "pdp", "Epipetrodúrico, capa cementada con sílice (tepetate) somera", GUIA_SERIE2),
     ("serie2", CALIFICADORES, "pdn", "Endopetrodúrico, capa cementada con sílice (tepetate) profunda", GUIA_SERIE2),
     ("serie2", CALIFICADORES, "pd", "Petrodúrico, capa cementada con sílice (tepetate) dentro de los primeros 100 cm", WRB),
     ("serie2", CALIFICADORES, "dup", "Epidúrico, horizonte dúrico (nódulos de sílice) dentro de los primeros 50 cm", WRB),
     ("serie2", CALIFICADORES, "lep", "Epiléptico, roca continua somera", GUIA_SERIE2),
     ("serie2", CALIFICADORES, "len", "Endoléptico, roca continua profunda", GUIA_SERIE2)]
    + [("serie2", "GRUPO1, GRUPO2, GRUPO3", k, v, DIC_SERIE2) for k, v in GRUPOS_WRB.items()]
    + [("serie1", "CLA_TEX", "Gruesa", "Textura gruesa, más de 65% de arena (clase 1 en la carta)", GUIA_SERIE1),
       ("serie1", "CLA_TEX", "Media", "Textura media, suelos francos (clase 2 en la carta)", GUIA_SERIE1),
       ("serie1", "CLA_TEX", "Fina", "Textura fina, más de 35% de arcilla (clase 3 en la carta)", GUIA_SERIE1),
       ("serie1", "CLA_TEX", "N/A", "No aplica, cuerpo de agua o zona urbana", "Inferido de los datos"),
       ("serie1", "FAS_FISCA", "Pedregosa", "Piedras de 7.5 cm o más en la superficie o en los primeros 30 cm", GUIA_SERIE1),
       ("serie1", "FAS_FISCA", "Gravosa", "Gravas menores a 7.5 cm en la superficie o en los primeros 30 cm", GUIA_SERIE1),
       ("serie1", "FAS_FISCA", "Lítica", "Roca dura y continua a menos de 50 cm", GUIA_SERIE1),
       ("serie1", "FAS_FISCA", "Lítica Profunda", "Roca dura y continua entre 50 y 100 cm", GUIA_SERIE1),
       ("serie1", "FAS_FISCA", "Dúrica", "Capa cementada con sílice (tepetate) a menos de 50 cm", GUIA_SERIE1),
       ("serie1", "FAS_FISCA", "Dúrica Profunda", "Capa cementada con sílice (tepetate) entre 50 y 100 cm", GUIA_SERIE1),
       ("serie1", "FAS_FISCA", "Petrocálcica", "Capa de caliche duro cementada con carbonatos a menos de 50 cm", GUIA_SERIE1),
       ("serie1", "FAS_FISCA", "Petrocálcica Profunda", "Capa de caliche duro entre 50 y 100 cm", GUIA_SERIE1),
       ("serie1", "FAS_FISCA", "NINGUNO", "Sin fase física", "Inferido de los datos"),
       ("serie1", "FAS_FISCA", "N/A", "No aplica, cuerpo de agua o zona urbana", "Inferido de los datos")]
)


def descargar(url, destino):
    destino = Path(destino)
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    print(f"  descargando {url}")
    req = urllib.request.Request(url.replace(" ", "%20"), headers={"User-Agent": "Mozilla/5.0"})
    temporal = destino.with_suffix(destino.suffix + ".parcial")
    with urllib.request.urlopen(req, timeout=120) as r, open(temporal, "wb") as f:
        tipo = r.headers.get("Content-Type", "")
        if "html" in tipo:
            raise RuntimeError(f"El INEGI devolvió una página HTML en lugar de un archivo: {url}")
        while bloque := r.read(1 << 20):
            f.write(bloque)
    temporal.rename(destino)
    return destino


def escribir(gdf, ruta, capa):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.unlink(missing_ok=True)
    gdf.to_file(ruta, layer=capa, driver="GPKG")
    print(f"  {ruta.relative_to(RAIZ)}: {len(gdf)} polígonos, {ruta.stat().st_size / 1e6:.1f} MB")


# --- Marco Geoestadístico ---------------------------------------------------------------------

def municipios(descargas):
    print("Marco Geoestadístico 2025, áreas geoestadísticas municipales")
    z = descargar(URL_MARCOGEO, descargas / "marcogeo" / "mg_2025_integrado.zip")
    mun = gpd.read_file(f"/vsizip/{z}/conjunto_de_datos/00mun.shp", encoding="latin1")
    mun = mun[mun.CVE_ENT.isin(ESTADOS)].copy()
    mun["estado"] = mun.CVE_ENT.map(ESTADOS)
    mun = mun[["CVEGEO", "CVE_ENT", "CVE_MUN", "NOMGEO", "estado", "geometry"]].to_crs(CRS_SALIDA)
    mun = mun.sort_values("CVEGEO").reset_index(drop=True)
    conteo = mun.CVE_ENT.value_counts().to_dict()
    for ent, n in MUNICIPIOS_ESPERADOS.items():
        if conteo.get(ent) != n:
            raise ValueError(f"Entidad {ent}: {conteo.get(ent)} municipios, se esperaban {n}")
    ruta = EXTERNOS / "inegi_marcogeo" / "municipios_13_15_21_29.gpkg"
    escribir(mun, ruta, "municipios")
    if ruta.stat().st_size > LIMITE_MB_MUNICIPIOS * 1e6:
        mun["geometry"] = mun.geometry.simplify(TOLERANCIA_SIMPLIFICACION_M, preserve_topology=True)
        print(f"  pasa de {LIMITE_MB_MUNICIPIOS} MB, se simplifica con tolerancia de {TOLERANCIA_SIMPLIFICACION_M} m")
        escribir(mun, ruta, "municipios")
    return mun


def leer_municipios():
    return gpd.read_file(EXTERNOS / "inegi_marcogeo" / "municipios_13_15_21_29.gpkg")


def union_estados(mun):
    return gpd.GeoDataFrame(geometry=[mun.union_all()], crs=mun.crs)


# --- Edafología -------------------------------------------------------------------------------

def caja_hoja(hoja):
    """Caja en grados de una hoja 1:250 000 del INEGI, por ejemplo E14-2.

    La letra marca la franja de 4° de latitud (E 16-20° N, F 20-24° N) y el número de zona UTM
    la de 6° de longitud. Cada carta 1:1 000 000 se divide en 12 hojas de 1° por 2°, numeradas de
    oeste a este y de norte a sur.
    """
    letra, resto = hoja[0], hoja[1:]
    zona, n = (int(x) for x in resto.split("-"))
    lat_sur = 16 + 4 * (ord(letra) - ord("E"))
    lon_oeste = -180 + 6 * (zona - 1)
    fila, col = divmod(n - 1, 3)
    norte = lat_sur + 4 - fila
    oeste = lon_oeste + 2 * col
    return box(oeste, norte - 1, oeste + 2, norte)


def hojas_necesarias(union, catalogo):
    u = union.to_crs("EPSG:4326").geometry.iloc[0]
    hojas = [h for h in catalogo if caja_hoja(h).intersects(u)]
    # Comprueba que el catálogo cubra toda la unión
    cubierto = gpd.GeoSeries([caja_hoja(h) for h in catalogo], crs="EPSG:4326").union_all()
    if not cubierto.buffer(1e-6).contains(u):
        raise ValueError("La unión de los estados sale del catálogo de hojas. Agrega las hojas que faltan.")
    return sorted(hojas, key=lambda h: (h[:3], int(h.split("-")[1])))


def ruta_shp_hoja(z):
    """Ruta /vsizip/ al shapefile de una hoja. La Serie I trae un zip dentro del zip."""
    with zipfile.ZipFile(z) as zf:
        nombres = zf.namelist()
        shp = [n for n in nombres if n.lower().endswith(".shp")]
        if shp:
            return f"/vsizip/{z}/{shp[0]}"
        interno = next(n for n in nombres if n.lower().endswith(".zip"))
        with zipfile.ZipFile(io.BytesIO(zf.read(interno))) as zi:
            shp = next(n for n in zi.namelist() if n.lower().endswith(".shp"))
    return f"/vsizip//vsizip/{z}/{interno}/{shp}"


def suelos(descargas, mun, serie):
    catalogo, crs, columnas, carpeta, subruta = {
        2: (HOJAS_SERIE2, CRS_SERIE2, COLUMNAS_SERIE2, "edafologia_serie2", ""),
        1: (HOJAS_SERIE1, CRS_SERIE1, COLUMNAS_SERIE1, "edafologia_serie1", "serie I/"),
    }[serie]
    print(f"Edafología 1:250 000 Serie {'II' if serie == 2 else 'I'}")
    union = union_estados(mun)
    hojas = hojas_necesarias(union, catalogo)
    print(f"  hojas que cruzan los cuatro estados: {', '.join(hojas)}")
    partes = []
    for hoja in hojas:
        upc = catalogo[hoja]
        z = descargar(f"{URL_EDAF}/{subruta}{upc}_s.zip", descargas / carpeta / f"{hoja}_{upc}.zip")
        g = gpd.read_file(ruta_shp_hoja(z), encoding="latin1")
        g = g.set_crs(crs, allow_override=True)[columnas + ["geometry"]].to_crs(CRS_SALIDA)
        g["HOJA"] = hoja
        g["UPC"] = upc
        partes.append(g)
    suelo = gpd.GeoDataFrame(pd.concat(partes, ignore_index=True), crs=CRS_SALIDA)
    suelo = suelo[suelo.intersects(union.geometry.iloc[0])]
    suelo = gpd.clip(suelo, union).explode(index_parts=False)
    suelo = suelo[suelo.geom_type.isin(["Polygon", "MultiPolygon"]) & (suelo.area > 1)].reset_index(drop=True)
    nombre = "serie2_4estados.gpkg" if serie == 2 else "serie1_4estados.gpkg"
    escribir(suelo, EXTERNOS / "inegi_edafologia" / nombre, f"serie{serie}")
    return suelo


def diccionario():
    df = pd.DataFrame(DICCIONARIO, columns=["serie", "campo", "codigo", "significado", "fuente"])
    ruta = EXTERNOS / "inegi_edafologia" / "diccionario_serie2.csv"
    df.to_csv(ruta, index=False, encoding="utf-8")
    print(f"  {ruta.relative_to(RAIZ)}: {len(df)} códigos")


# --- Uso de suelo y vegetación ----------------------------------------------------------------

def usv(descargas, mun):
    print("Uso de suelo y vegetación 1:250 000 Serie VII, clases agrícolas")
    z = descargar(URL_USV, descargas / "usv" / "889463842781_s.zip")
    union = union_estados(mun)
    ruta = f"/vsizip/{z}/conjunto_de_datos/cdv_usuev250sVII_cnal.shp"
    caja = tuple(union.to_crs(CRS_USV).total_bounds)
    g = gpd.read_file(ruta, bbox=caja, where="DESCRIPCIO LIKE 'AGRICULTURA%'")
    g = g.set_crs(CRS_USV, allow_override=True).to_crs(CRS_SALIDA)
    g = gpd.clip(g, union).explode(index_parts=False)
    g = g[g.geom_type.isin(["Polygon", "MultiPolygon"]) & (g.area > 1)].reset_index(drop=True)
    g = g[["CLAVE", "DESCRIPCIO", "geometry"]]
    escribir(g, EXTERNOS / "inegi_usv" / "agricultura_temporal_4estados.gpkg", "agricultura")
    return g


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--descargas", type=Path, required=True,
                   help="carpeta para los archivos crudos, fuera del repo")
    p.add_argument("--solo", nargs="+", choices=["municipios", "suelos", "usv"],
                   default=["municipios", "suelos", "usv"])
    a = p.parse_args()
    descargas = a.descargas.resolve()
    mun = municipios(descargas) if "municipios" in a.solo else leer_municipios()
    if "suelos" in a.solo:
        suelos(descargas, mun, 2)
        suelos(descargas, mun, 1)
        diccionario()
    if "usv" in a.solo:
        usv(descargas, mun)


if __name__ == "__main__":
    main()
