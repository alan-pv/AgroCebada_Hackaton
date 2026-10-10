"""Experimentos del modelo generalizable: curva de exclusión, regla de decisión, importancia y modelo final.

Requiere las tablas de `python -m agrocebada.generalizable.variables` y la asignación de DDR de
`scripts/descargar_siap_ddr.py`. La métrica principal y los esquemas están en
`agrocebada.generalizable.validacion`. Los modelos simples, fijados antes de evaluar, están en
`agrocebada.generalizable.modelos.SIMPLES`.

Plan fijado antes de correr (no se cambia después de ver resultados).
  1. Curva con zona de exclusión B = 0, 20, 40, 50, 60 y 80 km, 10 repeticiones, para bases,
     modelos simples, kriging de sus residuos, ridge y lasso de 14 variables.
  2. Regla de decisión en la métrica principal, en B = 0 y B = 50. Para cada simple contra
     kriging_vecinos se cuentan las victorias en 10 repeticiones. La prueba de permutación
     (n = 99, se revuelven las variables ambientales del simple) se corre para el contendiente
     fijado de antemano (simple_c_tmax_prec) y para el mejor simple de cada B. El mejor simple
     se elige mirando el resultado, así que su prueba se marca como posterior a los datos.
  3. Modelo final. Si ningún simple pasa la regla contra el kriging en B = 50, es el kriging.
     Si alguno pasa, s es el que pasa con menor métrica en B = 50 y el modelo final es, entre
     kriging_vecinos, s y kriging de residuos de s, el de menor promedio de la métrica
     principal en B = 0 y B = 50.
  4. Importancia por bloque (temperatura, lluvia, topografía, suelo) con un ridge de las
     nueve variables de los bloques. Condicional: aumento al revolver el bloque dentro del
     modelo completo. Marginal: mejora de un modelo con solo ese bloque sobre la media
     global. Las dos con n = 99 permutaciones, en B = 0 y B = 50.
  5. Variantes de robustez. Validación por DDR (un distrito por fold) y tabla sin las cifras
     repetidas del SIAP.
  6. Clima del año. En el esquema espacial de cinco folds, anomalías contra indicadoras de
     año. En el esquema por año, media propia con y sin anomalías. Solo el segundo es una
     prueba de pronóstico.

Escribe en experimentos/generalizable/
  - resultados.csv: una fila por objetivo, esquema, datos, buffer_km, modelo, unidad (nivel o
    fila), ponderado y subconjunto (todos o grandes), con RMSE, MAE, R², sesgo y desviación
    entre repeticiones.
  - oof_<objetivo>.parquet: predicciones fuera de fold de los esquemas con zona de exclusión
    (columnas buffer|modelo|rep) y del esquema por año.
  - decisiones.json, importancia.csv, correlaciones_bloques.csv y resumen.md.

Uso:
    uv run python scripts/generalizable_experimentos.py            # completo
    uv run python scripts/generalizable_experimentos.py --rapido --salida /tmp/prueba   # 2 repeticiones, 9 permutaciones
"""
import argparse
import json
import os
import time
import warnings

os.environ.setdefault("PYTHONWARNINGS", "ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agrocebada.config import EXPERIMENTOS  # noqa: E402
from agrocebada.generalizable import modelos as M  # noqa: E402
from agrocebada.generalizable import validacion as V  # noqa: E402

warnings.filterwarnings("ignore")
SALIDA = EXPERIMENTOS / "generalizable"
BUFFERS = (0, 20, 40, 50, 60, 80)
BASE = "kriging_vecinos"
CORTOS = ["media_global", "media_estatal", "idw_vecinos", "kriging_vecinos", *M.SIMPLES,
          *[f"kriging_residuos_{s}" for s in M.SIMPLES]]


class Corrida:
    """Acumula filas de resultados, predicciones fuera de fold y resultados por clave."""

    def __init__(self, n_rep, n_perm):
        self.n_rep, self.n_perm = n_rep, n_perm
        self.filas, self.oof, self.res = [], {}, {}

    def evaluar(self, objetivo, esquema, datos, d, y, ctx, reps, cat, buffer_km=0, guardar=False):
        for nombre, (familia, f) in cat.items():
            t = time.time()
            r = V.evaluar(f, d, y, reps, nombre, buffer_km, n_jobs=V.N_JOBS)
            self.res[(objetivo, esquema, datos, buffer_km, nombre)] = r
            for fila in V.tabla_metricas(r, ctx):
                self.filas.append({"objetivo": objetivo, "esquema": esquema, "datos": datos, "buffer_km": buffer_km,
                                   "familia": familia, **fila})
            if guardar:
                for i, p in enumerate(r.oof):
                    self.oof.setdefault(objetivo, {})[f"{esquema}|{buffer_km}|{nombre}|{i}"] = p
            princ = V.rmse_rep(r, ctx).mean()
            sinp = V.rmse_rep(r, ctx, ponderado=False).mean()
            print(f"{objetivo:13s} {esquema:15s} {datos:13s} B={buffer_km:2d} {nombre:44s} "
                  f"principal {princ:.3f} sin ponderar {sinp:.3f} ({time.time() - t:.0f} s)", flush=True)

    def get(self, *k):
        return self.res[k]


def preparar(objetivo, n_rep, sin_repetidos=False):
    d = M.tabla_modelado(objetivo, sin_repetidos=sin_repetidos)
    return d, d.y.to_numpy(), V.contexto(d), V.particiones_grupo(d, n_rep=n_rep)


def decisiones_rend(c, d, y, ctx, reps):
    """Regla de decisión, permutaciones y elección del modelo final (pasos 2 y 3 del plan)."""
    dec = {}
    principal = lambda r: V.rmse_rep(r, ctx)
    metr = {"principal": principal, "nivel_sin_ponderar": lambda r: V.rmse_rep(r, ctx, ponderado=False),
            "nivel_ponderado_grandes": lambda r: V.rmse_rep(r, ctx, subconjunto="grandes")}
    cat = M.catalogo_buffer()
    mejor = {}
    for B in V.BUFFERS_DECISION_KM:
        k = lambda n: c.get("rend", "espacial_buffer", "completos", B, n)
        base = {m: f(k(BASE)) for m, f in metr.items()}
        for s in list(M.SIMPLES) + [f"kriging_residuos_{s}" for s in M.SIMPLES] + ["ridge_ambiente", "lasso_ambiente"]:
            dec[f"B={B} {s} vs {BASE}"] = {m: V.comparacion_emparejada(f(k(s)), base[m]) for m, f in metr.items()}
        mejor[B] = min(M.SIMPLES, key=lambda s: principal(k(s)).mean())
        dec[f"B={B} mejor simple (elegido mirando el resultado)"] = mejor[B]
        for s in dict.fromkeys([M.CONTENDIENTE, mejor[B]]):
            cols, _ = M.SIMPLES[s]
            t = time.time()
            p = V.prueba_permutacion(cat[s][1], d, y, cols, reps, n=c.n_perm, metrica=metr, buffer_km=B)
            v = dec[f"B={B} {s} vs {BASE}"]
            dec[f"B={B} regla {s} vs {BASE}"] = {
                "a_priori": s == M.CONTENDIENTE, "victorias": v["principal"]["victorias"],
                "p": p["principal"]["p"], "aceptada": bool(v["principal"]["aceptada"] and p["principal"]["p"] <= 0.05),
                "permutacion": p}
            print(f"regla B={B} {s}: {dec[f'B={B} regla {s} vs {BASE}']['victorias']}/10, p = {p['principal']['p']:.3f}"
                  f" ({time.time() - t:.0f} s)", flush=True)

    # Paso 3: modelo final.
    pasan = [s for s in M.SIMPLES if f"B=50 regla {s} vs {BASE}" in dec and dec[f"B=50 regla {s} vs {BASE}"]["aceptada"]]
    if not pasan:
        final, motivo = BASE, "ningún simple pasa la regla contra el kriging en B = 50"
    else:
        k50 = lambda n: principal(c.get("rend", "espacial_buffer", "completos", 50, n)).mean()
        s = min(pasan, key=k50)
        prom = {m: np.mean([principal(c.get("rend", "espacial_buffer", "completos", B, m)).mean()
                            for B in V.BUFFERS_DECISION_KM]) for m in (BASE, s, f"kriging_residuos_{s}")}
        final = min(prom, key=prom.get)
        motivo = (f"{s} pasa la regla en B = 50. Promedio de la métrica principal en B = 0 y 50: "
                  + ", ".join(f"{m} {v:.3f}" for m, v in prom.items()))
    dec["modelo_final"] = {"modelo": final, "motivo": motivo}
    # Permutación del modelo final con kriging de residuos en B = 0 (¿el ambiente agrega al kriging cerca de datos?).
    if final.startswith("kriging_residuos_"):
        s = final.removeprefix("kriging_residuos_")
        t = time.time()
        p = V.prueba_permutacion(cat[final][1], d, y, M.SIMPLES[s][0], reps, n=c.n_perm, metrica=metr, buffer_km=0)
        v = dec[f"B=0 {final} vs {BASE}"]
        dec[f"B=0 regla {final} vs {BASE}"] = {
            "victorias": v["principal"]["victorias"], "p": p["principal"]["p"],
            "aceptada": bool(v["principal"]["aceptada"] and p["principal"]["p"] <= 0.05), "permutacion": p}
        print(f"regla B=0 {final}: {v['principal']['victorias']}/10, p = {p['principal']['p']:.3f} "
              f"({time.time() - t:.0f} s)", flush=True)
    return dec


def importancia(d, y, ctx, reps, n_perm):
    """Importancia condicional y marginal por bloque (paso 4 del plan)."""
    principal = lambda r: V.rmse_rep(r, ctx)
    completo = M.T(M.ridge(M.VARIABLES_BLOQUES))
    nulo = M.T(M.media_global)
    filas = []
    for B in V.BUFFERS_DECISION_KM:
        r_comp = principal(V.evaluar(completo, d, y, reps, "completo", B, n_jobs=V.N_JOBS)).mean()
        r_nulo = principal(V.evaluar(nulo, d, y, reps, "nulo", B, n_jobs=V.N_JOBS)).mean()
        for bloque, cols in M.BLOQUES.items():
            t = time.time()
            cond = V.prueba_permutacion(completo, d, y, cols, reps, n=n_perm, metrica=principal, buffer_km=B)
            solo = M.T(M.ridge(cols))
            marg = V.prueba_permutacion(solo, d, y, cols, reps, n=n_perm, metrica=principal, buffer_km=B)
            filas.append({"buffer_km": B, "bloque": bloque, "variables": " ".join(cols),
                          "rmse_completo": r_comp, "rmse_completo_bloque_revuelto": cond["metrica_perm_media"],
                          "aumento_condicional": cond["metrica_perm_media"] - r_comp, "p_condicional": cond["p"],
                          "rmse_media_global": r_nulo, "rmse_solo_bloque": marg["metrica_real"],
                          "mejora_marginal": r_nulo - marg["metrica_real"], "p_marginal": marg["p"]})
            print("importancia", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in filas[-1].items()},
                  f"({time.time() - t:.0f} s)", flush=True)
    return pd.DataFrame(filas)


def correlaciones(d):
    m = d.drop_duplicates("CVEGEO")[M.VARIABLES_BLOQUES]
    return m.corr().round(3)


def tabla_md(df, flotantes=3):
    """DataFrame a tabla Markdown sin depender de tabulate."""
    df = df.copy()
    for c in df.columns:
        if df[c].dtype.kind == "f":
            df[c] = df[c].map(lambda v: "" if pd.isna(v) else f"{v:.{flotantes}f}")
    cab = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "---|" * len(df.columns)
    return "\n".join([cab, sep] + ["| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False)])


def resumen(res, dec, imp, minutos):
    """resumen.md con las tablas clave. El texto interpretativo va en ROADMAP_GENERALIZABLE.md."""
    r = res[(res.objetivo == "rend") & (res.unidad == "nivel")]
    out = ["# Resumen de experimentos del modelo generalizable", "",
           f"Generado por `scripts/generalizable_experimentos.py` en {minutos:.0f} minutos. Objetivo rend (SIAP, "
           "sobre cosechada). RMSE de nivel en t/ha, media de 10 repeticiones. La métrica principal es la "
           "ponderada por superficie sembrada en todos los municipios.", ""]
    cur = r[(r.esquema == "espacial_buffer") & (r.datos == "completos") & (r.subconjunto == "todos")]
    for pond, titulo in ((True, "ponderado por superficie (principal)"), (False, "sin ponderar")):
        t = cur[cur.ponderado == pond].pivot(index="modelo", columns="buffer_km", values="rmse")
        t = t.loc[[m for m in CORTOS + ["ridge_ambiente", "lasso_ambiente"] if m in t.index]]
        out += [f"## Curva de exclusión, RMSE de nivel {titulo}", "", tabla_md(t.reset_index()), ""]
    g = r[(r.esquema == "espacial_buffer") & (r.datos == "completos") & (r.subconjunto == "grandes") & r.ponderado]
    t = g.pivot(index="modelo", columns="buffer_km", values="rmse")
    t = t.loc[[m for m in CORTOS if m in t.index]]
    out += ["## Municipios con mediana de al menos 1 000 ha sembradas, ponderado", "", tabla_md(t.reset_index()), ""]
    filas = []
    for B in V.BUFFERS_DECISION_KM:
        for s in list(M.SIMPLES) + [f"kriging_residuos_{s}" for s in M.SIMPLES] + ["ridge_ambiente", "lasso_ambiente"]:
            v = dec[f"rend: B={B} {s} vs {BASE}"]
            regla = dec.get(f"rend: B={B} regla {s} vs {BASE}")
            filas.append({"B_km": B, "modelo": s,
                          "principal": v["principal"]["metrica_nuevo"], "kriging": v["principal"]["metrica_base"],
                          "victorias": v["principal"]["victorias"],
                          "sin_ponderar": v["nivel_sin_ponderar"]["metrica_nuevo"],
                          "kriging_sin_ponderar": v["nivel_sin_ponderar"]["metrica_base"],
                          "victorias_sin_ponderar": v["nivel_sin_ponderar"]["victorias"],
                          "p": "" if regla is None else f"{regla['p']:.2f}",
                          "regla": "" if regla is None else ("acepta" if regla["aceptada"] else "rechaza")})
    out += ["## Regla de decisión contra el kriging", "",
            "Victorias en 10 repeticiones. p de la permutación de las variables ambientales (n = 99), solo para "
            "el contendiente fijado de antemano, el mejor simple de cada B y el modelo final.", "",
            tabla_md(pd.DataFrame(filas)), "",
            f"Modelo final: **{dec['rend: modelo_final']['modelo']}**. {dec['rend: modelo_final']['motivo']}.", ""]
    rob = r[r.esquema.isin(["ddr", "espacial_buffer"]) & r.ponderado.isin([True, False]) & (r.subconjunto == "todos")
            & r.modelo.isin(CORTOS) & (r.buffer_km.isin([0, 50]))]
    rob = rob.assign(variante=rob.esquema + " " + rob.datos + " B=" + rob.buffer_km.astype(str)
                     + np.where(rob.ponderado, " pond", " sin pond"))
    t = rob.pivot_table(index="modelo", columns="variante", values="rmse").loc[[m for m in CORTOS]]
    out += ["## Robustez: por DDR y sin cifras repetidas del SIAP", "", tabla_md(t.reset_index()), ""]
    out += ["## Importancia por bloque (métrica principal)", "",
            "Condicional: aumento al revolver el bloque en el ridge con los cuatro bloques. Marginal: mejora de "
            "un ridge con solo ese bloque sobre la media global.", "",
            tabla_md(imp.drop(columns=["variables"])), ""]
    e = res[(res.objetivo == "rend") & (res.esquema.isin(["espacial", "anio"])) & (res.unidad == "fila")
            & ~res.ponderado & (res.subconjunto == "todos")]
    e = e[e.modelo.isin(["kriging_vecinos", "lgbm_ubicacion", "lgbm_ubicacion_anomalias",
                         "lgbm_ubicacion_indicadoras_anio", "kriging_mas_efecto_estado_anio", "idw_vecinos_anio",
                         "media_propia_tendencia", "propia_mas_anomalia_ridge", "propia_mas_anomalia_lgbm"])]
    out += ["## Clima del año (RMSE por fila, sin ponderar)", "",
            "En el esquema espacial las anomalías reconocen el año. El esquema por año es la prueba de pronóstico.", "",
            tabla_md(e[["esquema", "familia", "modelo", "rmse"]]), ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--salida", default=None, help="directorio de salida (por omisión experimentos/generalizable)")
    a = ap.parse_args()
    global SALIDA
    if a.salida:
        from pathlib import Path
        SALIDA = Path(a.salida)
    t0 = time.time()
    SALIDA.mkdir(parents=True, exist_ok=True)
    n_rep, n_perm = (2, 9) if a.rapido else (V.N_REP, V.N_PERM)
    c = Corrida(n_rep, n_perm)
    cat_buf = M.catalogo_buffer()
    cortos = {k: cat_buf[k] for k in CORTOS}

    # Paso 1: curva de exclusión.
    d, y, ctx, reps = preparar("rend", n_rep)
    for B in BUFFERS:
        c.evaluar("rend", "espacial_buffer", "completos", d, y, ctx, reps, cat_buf, B, guardar=B in (0, 50))
    ds, ys, ctxs, repss = preparar("rend_sembrada", n_rep)
    for B in V.BUFFERS_DECISION_KM:
        c.evaluar("rend_sembrada", "espacial_buffer", "completos", ds, ys, ctxs, repss, cortos, B, guardar=True)

    # Paso 5: robustez.
    c.evaluar("rend", "ddr", "completos", d, y, ctx, V.particiones_columna(d, "ddr"), cat_buf)
    dr, yr, ctxr, repsr = preparar("rend", n_rep, sin_repetidos=True)
    print(f"sin repetidos: {len(dr)} filas, {dr.CVEGEO.nunique()} municipios", flush=True)
    for B in V.BUFFERS_DECISION_KM:
        c.evaluar("rend", "espacial_buffer", "sin_repetidos", dr, yr, ctxr, repsr, cortos, B)

    # Paso 6: esquema de cinco folds (continuidad y clima del año) y por año.
    mun = d.drop_duplicates("CVEGEO")[["CVEGEO", "x_m", "y_m"]].rename(columns={"CVEGEO": "clave"})
    reps5 = V.particiones_espaciales(d.CVEGEO, V.grupos_espaciales(mun), n_rep=n_rep)
    extra = {k: v for k, v in M.catalogo_espacial().items() if k not in cat_buf or k in ("kriging_vecinos",)}
    c.evaluar("rend", "espacial", "completos", d, y, ctx, reps5, extra)
    for obj, (dd, yy, cc) in {"rend": (d, y, ctx), "rend_sembrada": (ds, ys, ctxs)}.items():
        c.evaluar(obj, "anio", "completos", dd, yy, cc, V.particiones_anio(dd.anio), M.catalogo_anio(), guardar=True)

    res = pd.DataFrame(c.filas)
    res.to_csv(SALIDA / "resultados.csv", index=False)
    for obj, cols in c.oof.items():
        dd = d if obj == "rend" else ds
        o = pd.DataFrame(cols)
        o.insert(0, "y", dd.y.to_numpy())
        o.insert(0, "anio", dd.anio.to_numpy())
        o.insert(0, "CVEGEO", dd.CVEGEO.to_numpy())
        o.to_parquet(SALIDA / f"oof_{obj}.parquet", index=False)

    # Pasos 2 y 3: regla y modelo final. Paso 6: comparaciones del clima del año.
    dec = {f"rend: {k}": v for k, v in decisiones_rend(c, d, y, ctx, reps).items()}
    e = lambda n: c.get("rend", "espacial", "completos", 0, n).rmse_rep
    for a_, b_ in (("lgbm_ubicacion_anomalias", "lgbm_ubicacion"),
                   ("lgbm_ubicacion_anomalias", "lgbm_ubicacion_indicadoras_anio"),
                   ("kriging_mas_anomalia", "kriging_mas_efecto_estado_anio")):
        dec[f"rend: espacial 5 folds, fila: {a_} vs {b_}"] = V.comparacion_emparejada(e(a_), e(b_))
    for obj in ("rend", "rend_sembrada"):
        ea = lambda n: c.get(obj, "anio", "completos", 0, n).rmse_rep[0]
        for m in ("propia_mas_anomalia_ridge", "propia_mas_anomalia_lgbm"):
            dec[f"{obj}: anio (pronóstico), fila: {m} menos media_propia_tendencia"] = float(
                ea(m) - ea("media_propia_tendencia"))
    (SALIDA / "decisiones.json").write_text(json.dumps(dec, indent=2, ensure_ascii=False))

    # Paso 4: importancia.
    imp = importancia(d, y, ctx, reps, n_perm)
    imp.to_csv(SALIDA / "importancia.csv", index=False)
    correlaciones(d).to_csv(SALIDA / "correlaciones_bloques.csv")

    minutos = (time.time() - t0) / 60
    (SALIDA / "resumen.md").write_text(resumen(res, dec, imp, minutos))
    print(f"listo en {minutos:.1f} minutos. Modelo final: {dec['rend: modelo_final']}")


if __name__ == "__main__":
    main()
