"""Capa municipal para la app, cobertura de intervalos y comparación con el reto.

Requiere `scripts/generalizable_experimentos.py`. Usa el modelo final que eligió la regla
(`decisiones.json`, clave "rend: modelo_final") y sus predicciones fuera de fold del esquema
espacial con zona de exclusión.

Intervalos. El residuo fuera de fold junta el error del nivel del lugar y la variación del
año, así que p10, p90 y la probabilidad bajo 2 t/ha responden "sembrar aquí un año
cualquiera". Para un municipio a no más de DIST_CERCA_KM de un municipio con SIAP se usan los
residuos con B = 0 km. Más lejos se usan los de B = 50 km, que miden el error sin datos cerca.

Confianza. Columna `confianza` de cada municipio con predicción.
  - "alta": el municipio tiene historia propia de cebada de temporal en el SIAP.
  - "media": sin historia propia, pero dentro_dominio, con al menos algo de agricultura de
    temporal (agricola_ha > 0) y a no más de DIST_CONFIANZA_MEDIA_KM (25 km) de un municipio
    con SIAP.
  - "baja": el resto de los municipios con predicción.
  Sin predicción (fuera del rango ambiental) queda vacía. Motivo: municipios boscosos y sin
  tradición cebadera cerca de la Ciudad de México (Jilotzingo, Tlalmanalco, Huixquilucan)
  salen arriba solo por ser frescos. El modelo de Tmax no sabe si ahí se siembra cebada, así
  que su predicción vale menos que la de un municipio con historia o rodeado de ellos.

Escala. Se usa la escala global salvo que algún estado quede con cobertura menor a
COBERTURA_MINIMA con B = 0 y la escala local la mejore (regla fijada antes de correr).

Escribe
  - outputs/generalizable_municipios.parquet y .gpkg: por municipio, esperado 2025, p10, p90
    y probabilidad bajo 2 t/ha, para el rendimiento oficial y sobre sembrada, con la historia
    propia del SIAP, la distancia al municipio con SIAP más cercano y dentro_dominio. Fuera
    del rango ambiental de los municipios con SIAP los valores quedan vacíos.
  - experimentos/generalizable/cobertura.csv: cobertura nominal 0.8 por estado, buffer y
    escala, ponderada por superficie sembrada y sin ponderar.
  - experimentos/generalizable/reto.csv y reto_resumen.json: nivel fuera de muestra de los
    municipios del reto contra la media del reto por régimen y el SIAP 2025. Es una
    comparación descriptiva, no causal.

Uso:
    uv run python scripts/generalizable_capa.py [--modelo kriging_vecinos]
"""
import argparse
import json
import os
import warnings

os.environ.setdefault("PYTHONWARNINGS", "ignore")

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agrocebada.config import CRS_METRICO, EXPERIMENTOS, OUTPUTS, PROCESSED  # noqa: E402
from agrocebada.generalizable import SALIDA as TABLAS  # noqa: E402
from agrocebada.generalizable import modelos as M  # noqa: E402
from agrocebada.generalizable import riesgo as R  # noqa: E402
from agrocebada.generalizable import siap  # noqa: E402
from agrocebada.generalizable import validacion as V  # noqa: E402
from agrocebada.generalizable.variables import MUNICIPIOS  # noqa: E402
from agrocebada.intervalos import cuantiles_conformal, prob_bajo_umbral  # noqa: E402

EXP = EXPERIMENTOS / "generalizable"
warnings.filterwarnings("ignore")
DIST_CERCA_KM = 30.0
DIST_DOMINIO_KM = 50.0
DIST_CONFIANZA_MEDIA_KM = 25.0
COBERTURA_MINIMA = 0.75
BUFFERS = V.BUFFERS_DECISION_KM
OBJETIVOS = (("rend", ""), ("rend_sembrada", "_sembrada"))


def oof(objetivo, nombre, buffer_km):
    """Tabla fuera de fold y la lista de columnas (una por repetición) del modelo y buffer."""
    o = pd.read_parquet(EXP / f"oof_{objetivo}.parquet")
    cols = [c for c in o.columns if c.startswith(f"espacial_buffer|{buffer_km}|{nombre}|")]
    if not cols:
        raise KeyError(f"no hay predicciones fuera de fold de {nombre} con B = {buffer_km} para {objetivo}")
    return o, cols


def tabla_cobertura(nombre):
    filas = []
    for objetivo, _ in OBJETIVOS:
        d = M.tabla_modelado(objetivo)
        y = d.y.to_numpy()
        reps = V.particiones_grupo(d)
        for B in BUFFERS:
            o, cols = oof(objetivo, nombre, B)
            assert (o.CVEGEO.to_numpy() == d.CVEGEO.to_numpy()).all()
            for escala in ("global", "local"):
                for i, c in enumerate(cols):
                    t = R.cobertura(d, y, o[c].to_numpy(), reps[i], escala=escala)
                    t["estado"] = d.estado.to_numpy()
                    t["sembrada_ha"] = d.sembrada_ha.to_numpy()
                    for est, s in [("Todos", t)] + list(t.groupby("estado")):
                        for pond in (False, True):
                            r = R.resumen_cobertura(s, pesos="sembrada_ha" if pond else None).iloc[0].to_dict()
                            filas.append({"objetivo": objetivo, "buffer_km": B, "escala": escala, "ponderado": pond,
                                          "rep": i, "estado": est, **r, "brier": R.brier(s)})
    c = pd.DataFrame(filas)
    return c.groupby(["objetivo", "buffer_km", "escala", "ponderado", "estado"]).mean(numeric_only=True) \
        .drop(columns="rep").reset_index()


def elegir_escala(cob):
    """Global salvo que algún estado subcubra con B = 0 y la escala local lo mejore."""
    t = cob[(cob.objetivo == "rend") & (cob.buffer_km == 0) & ~cob.ponderado & (cob.estado != "Todos")]
    g = t[t.escala == "global"].cobertura.min()
    loc = t[t.escala == "local"].cobertura.min()
    return ("local" if g < COBERTURA_MINIMA and loc > g else "global"), float(g), float(loc)


def historia_propia(d):
    """Estadísticas del SIAP de cada municipio, llevadas al año de referencia."""
    b = M.pendiente_comun(d, d.y.to_numpy())
    aj = d.y - b * (d.anio - M.ANIO_REFERENCIA)
    g = d.assign(aj=aj).groupby("CVEGEO")
    return pd.DataFrame({"siap_anios": g.size(), "siap_media": g.aj.mean(), "siap_sd_anios": g.aj.std(),
                         "siap_frac_bajo_2": g.aj.apply(lambda s: (s < R.UMBRAL).mean())}), b


def distancia_siap(mun, d):
    """Distancia (km) de cada municipio al municipio con SIAP más cercano distinto de sí mismo."""
    con = mun[mun.CVEGEO.isin(d.CVEGEO)][["CVEGEO", "x_m", "y_m"]]
    dist = np.sqrt((mun.x_m.to_numpy()[:, None] - con.x_m.to_numpy()[None]) ** 2
                   + (mun.y_m.to_numpy()[:, None] - con.y_m.to_numpy()[None]) ** 2) / 1000
    dist[mun.CVEGEO.to_numpy()[:, None] == con.CVEGEO.to_numpy()[None]] = np.inf
    return dist.min(1)


def confianza(out):
    """Confianza "alta", "media" o "baja" de la predicción (criterio en el docstring del módulo)."""
    con_pred = out.esperado.notna()
    media = (~out.con_siap & out.dentro_dominio & (out.agricola_ha > 0)
             & (out.dist_siap_km <= DIST_CONFIANZA_MEDIA_KM))
    c = np.select([out.con_siap, media], ["alta", "media"], "baja").astype(object)
    c[~con_pred.to_numpy()] = None
    return pd.Series(c, index=out.index)


def capa(nombre, escala):
    mun = pd.read_parquet(TABLAS / "municipios.parquet")
    te = mun.assign(anio=M.ANIO_REFERENCIA)
    f = M.modelo(nombre)
    out = mun[["CVEGEO", "estado", "municipio", "lon", "lat", "agricola_ha", "zona_completa"]].copy()
    d0 = M.tabla_modelado("rend")
    out["dist_siap_km"] = distancia_siap(mun, d0)
    out["con_siap"] = out.CVEGEO.isin(d0.CVEGEO)
    lejos = out.dist_siap_km.to_numpy() > DIST_CERCA_KM
    out["residuos_de"] = np.where(lejos, "B=50", "B=0")
    for objetivo, suf in OBJETIVOS:
        d = M.tabla_modelado(objetivo)
        y = d.y.to_numpy()
        pred = f(d, y, te)
        out[f"esperado{suf}"] = pred
        for B, m in ((0, ~lejos), (50, lejos)):
            if not m.any():
                continue
            o, cols = oof(objetivo, nombre, B)
            r = np.concatenate([o.y.to_numpy() - o[c].to_numpy() for c in cols])
            esc = np.ones(m.sum())
            if escala == "local":
                r = r / np.concatenate([R.desviacion_local(d, y, d) for _ in cols])
                esc = R.desviacion_local(d, y, te[m])
            lo, hi = cuantiles_conformal(r)
            out.loc[m, f"p10{suf}"] = pred[m] + lo * esc
            out.loc[m, f"p90{suf}"] = pred[m] + hi * esc
            out.loc[m, f"prob_bajo_2{suf}"] = prob_bajo_umbral(pred[m], r, R.UMBRAL, esc)
        h, b = historia_propia(d)
        out = out.merge(h.add_suffix(suf), left_on="CVEGEO", right_index=True, how="left")
        out[f"tendencia{suf}"] = b
    # Dominio: superficie agrícola suficiente, SIAP a una distancia validada y ambiente dentro
    # del rango de los municipios de entrenamiento.
    variables = sorted({c for cols, _ in M.SIMPLES.values() for c in cols})
    ent = mun[mun.CVEGEO.isin(d0.CVEGEO)]
    rango = np.all([(mun[c] >= ent[c].min()) & (mun[c] <= ent[c].max()) for c in variables], axis=0)
    out["dentro_rango_ambiental"] = rango
    out["dentro_dominio"] = (out.dist_siap_km <= DIST_DOMINIO_KM) & (out.agricola_ha >= 100) & rango
    # Fuera del rango ambiental el modelo lineal extrapola (tierras bajas y calientes donde no
    # se siembra cebada de temporal) y llega a dar rendimientos negativos. Ahí no se publica
    # nada. Dentro del rango el rendimiento no puede ser negativo, así que se corta en 0.
    for _, suf in OBJETIVOS:
        cols = [f"esperado{suf}", f"p10{suf}", f"p90{suf}", f"prob_bajo_2{suf}"]
        out.loc[~rango, cols] = np.nan
        out[cols[:3]] = out[cols[:3]].clip(lower=0)
    out["confianza"] = confianza(out)
    out["modelo"] = nombre
    out["escala"] = escala
    out["anio_referencia"] = M.ANIO_REFERENCIA
    return out


def nivel_fuera_muestra(f, d, y, reps, claves, buffer_km):
    """Nivel 2025 de cada municipio de `claves` predicho sin él (y sin vecinos a menos de B km)."""
    te = d.drop_duplicates("CVEGEO").set_index("CVEGEO").loc[claves].reset_index().assign(anio=M.ANIO_REFERENCIA)
    acum = {c: [] for c in claves}
    for folds in reps:
        for c in claves:
            fold = folds[(d.CVEGEO == c).to_numpy()][0]
            prueba = folds == fold
            tr = V.mascara_entrenamiento(d, prueba, buffer_km)
            acum[c].append(f(d[tr], y[tr], te[te.CVEGEO == c])[0])
    return pd.Series({c: np.mean(v) for c, v in acum.items()})


def reto(nombre, capa_mun):
    """Nivel fuera de muestra de los municipios del reto contra sus medias por régimen."""
    p = pd.read_parquet(PROCESSED / "parcelas.parquet")
    p = p[p.rendimiento.notna()]
    p["clave"] = p.municipio.map(siap.normalizar)
    g = p.groupby(["estado", "clave", "municipio", "regimen"]).rendimiento.agg(n="size", reto="mean").reset_index()
    mun = pd.read_parquet(TABLAS / "municipios.parquet")[["CVEGEO", "estado", "clave"]]
    g = g.merge(mun, on=["estado", "clave"], how="left")
    d = M.tabla_modelado("rend")
    y = d.y.to_numpy()
    f = M.modelo(nombre)
    reps = V.particiones_grupo(d)
    con = [c for c in g.CVEGEO.unique() if c in set(d.CVEGEO)]
    for B in BUFFERS:
        n = nivel_fuera_muestra(f, d, y, reps, con, B)
        # Sin SIAP propio el municipio nunca está en el entrenamiento, así que vale la predicción de la capa.
        g[f"nivel_fuera_muestra_B{B}"] = g.CVEGEO.map(n).fillna(g.CVEGEO.map(capa_mun.set_index("CVEGEO").esperado))
    g["siap_2025"] = g.CVEGEO.map(d[d.anio == 2025].set_index("CVEGEO").y)
    g = g.merge(capa_mun[["CVEGEO", "siap_media", "p10", "p90", "dist_siap_km"]], on="CVEGEO", how="left")
    g["dif_reto_nivel_B0"] = g.reto - g.nivel_fuera_muestra_B0
    g["dif_reto_nivel_B50"] = g.reto - g.nivel_fuera_muestra_B50
    g["dif_reto_siap_2025"] = g.reto - g.siap_2025
    return g


def resumen_reto(r):
    def f(s):
        w = s.n.to_numpy(float)
        prom = lambda c: float(np.average(s[c], weights=w)) if s[c].notna().all() else float(
            np.average(s[c].dropna(), weights=w[s[c].notna().to_numpy()])) if s[c].notna().any() else np.nan
        return pd.Series({"parcelas": int(w.sum()), "municipios": len(s), "reto": prom("reto"),
                          "nivel_B0": prom("nivel_fuera_muestra_B0"), "nivel_B50": prom("nivel_fuera_muestra_B50"),
                          "siap_2025": prom("siap_2025")})
    t = r.groupby("regimen").apply(f)
    t["dif_reto_nivel_B0"] = t.reto - t.nivel_B0
    t["dif_reto_nivel_B50"] = t.reto - t.nivel_B50
    t["dif_reto_siap_2025"] = t.reto - t.siap_2025
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default=None, help="por omisión, el modelo final de decisiones.json")
    a = ap.parse_args()
    nombre = a.modelo or json.loads((EXP / "decisiones.json").read_text())["rend: modelo_final"]["modelo"]
    print("modelo:", nombre)
    cob = tabla_cobertura(nombre)
    cob.to_csv(EXP / "cobertura.csv", index=False)
    escala, g, loc = elegir_escala(cob)
    print(cob[cob.estado == "Todos"].round(3).to_string())
    print(f"escala elegida: {escala} (cobertura mínima por estado con B = 0: global {g:.3f}, local {loc:.3f})")
    c = capa(nombre, escala)
    OUTPUTS.mkdir(exist_ok=True)
    c.to_parquet(OUTPUTS / "generalizable_municipios.parquet", index=False)
    geo = gpd.read_file(MUNICIPIOS)[["CVEGEO", "geometry"]].to_crs(CRS_METRICO)
    geo["geometry"] = geo.geometry.simplify(100)
    gpd.GeoDataFrame(c.merge(geo, on="CVEGEO"), geometry="geometry", crs=CRS_METRICO).to_crs("EPSG:4326") \
        .to_file(OUTPUTS / "generalizable_municipios.gpkg", layer="municipios", driver="GPKG")
    print(c.describe().T.round(2).to_string())
    r = reto(nombre, c)
    r.to_csv(EXP / "reto.csv", index=False)
    print(r.round(2).to_string())
    t = resumen_reto(r).round(3)
    print(t.to_string())
    (EXP / "reto_resumen.json").write_text(json.dumps({"modelo": nombre, "escala": escala,
                                                       "por_regimen": t.to_dict(orient="index")}, indent=2,
                                                      ensure_ascii=False))


if __name__ == "__main__":
    main()
