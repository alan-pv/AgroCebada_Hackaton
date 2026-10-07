"""Experimentos de la versión 1 del modelo, en el orden de la Tabla XI del documento de contexto.

Uso:
    uv run python scripts/experimentos_v1.py

Cada paso se compara con la mejor versión aceptada hasta ese momento, con la regla de
decisión (7 de 10 victorias en el esquema A y prueba de permutación con p <= 0.05), y se
registra en experimentos/registro.csv. Las ideas descartadas también quedan registradas.
Las filas de este script usan bloques que empiezan con "v1_", y se reemplazan al repetir.
"""
import copy
import csv
import os
import time
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from agrocebada import cv, modelos
from agrocebada.config import EXPERIMENTOS, OUTPUTS, PROCESSED, REPORTE, SEED
from agrocebada.registro import ARCHIVO_REGISTRO, ENCABEZADO, registrar
from agrocebada.transformers import MediaPorGrupo

warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"  # también en los procesos de joblib
N_JOBS = 8
N_PERM = 50
REP_PERM = 3

TABLA = []       # una fila por experimento para el documento
CANDIDATOS = []  # (nombre, spec, resultado, decisión)


# ---------------------------------------------------------------------- datos

def cargar():
    f = pd.read_parquet(PROCESSED / "features.parquet").set_index("ID_POLIGONO")
    p = pd.read_parquet(PROCESSED / "parcelas.parquet").set_index("ID_POLIGONO")
    d = f.join(p[["rendimiento"]])
    d = d[d["conjunto"] == "ENTRENAMIENTO"].sort_index()
    return d.drop(columns="rendimiento"), d["rendimiento"], f


def bloques(X):
    def con(*pref):
        return [c for c in X.columns if c.startswith(pref)]
    return {"sat25_fen": con("sat25_", "fen_"), "hist": con("hist_"), "het": con("het_"),
            "lab": con("lab_"), "tsup": con("tsup_"), "clima": con("clima_"),
            "topo": con("topo_")}


# ------------------------------------------------------------ especificaciones

def spec(modelo="ridge", columnas=(), **args):
    a = {"contexto": [], "residuos": True}
    a.update(args)
    return {"modelo": modelo, "columnas": list(columnas), "args": a}


def variante(s, columnas_extra=(), **cambios):
    n = copy.deepcopy(s)
    n["columnas"] = list(dict.fromkeys(n["columnas"] + list(columnas_extra)))
    for k, v in cambios.items():
        if k == "modelo":
            n["modelo"] = v
        elif k == "params":
            n["args"]["params"] = {**n["args"].get("params", {}), **v}
        else:
            n["args"][k] = v
    return n


def con_seleccion(s):
    """Selección de 15 variables dentro del fold cuando hay más de 20 columnas."""
    s = copy.deepcopy(s)
    s["args"]["seleccion_k"] = 15 if len(s["columnas"]) > 20 else None
    return s


def con_info(s):
    """Verdadero si el modelo usa variables o rezago espacial, además de la media por régimen."""
    return bool(s["columnas"]) or bool(s["args"].get("rezago"))


def columnas_permutar(s):
    cols = list(s["columnas"])
    if s["args"].get("rezago"):
        cols += ["x_m", "y_m"]
    return cols


def columnas_nuevas(s, base):
    """Columnas que la prueba de permutación revuelve: solo las que `s` agrega a `base`.

    Si `s` no agrega columnas (cambia el algoritmo o el enfoque), no hay bloque nuevo que
    revolver y se revuelven todas las del modelo. En ese caso la prueba solo confirma que el
    modelo usa información además del régimen, y lo que decide es la comparación emparejada.
    """
    previas = set(columnas_permutar(base["spec"])) if base.get("spec") else set()
    nuevas = [c for c in columnas_permutar(s) if c not in previas]
    return nuevas or columnas_permutar(s)


# ------------------------------------------------------------------ evaluación

def permutacion(mod, X, y, columnas, sw=None, dentro_de="regimen"):
    """Prueba de permutación de cv.prueba_permutacion, con las permutaciones en paralelo."""
    X = X.sort_index()
    y = y.loc[X.index]
    real = cv.evaluate(mod, X, y, "A", repeticiones=REP_PERM, sample_weight=sw).rmse
    rng = np.random.default_rng(SEED)
    Xps = [cv._permutar_bloque(X, columnas, rng, dentro_de) for _ in range(N_PERM)]
    perm = np.array(Parallel(n_jobs=N_JOBS)(
        delayed(lambda Xp: cv.evaluate(mod, Xp, y, "A", repeticiones=REP_PERM,
                                       sample_weight=sw, ref=X).rmse)(Xp) for Xp in Xps))
    p = (1 + int((perm <= real).sum())) / (N_PERM + 1)
    return {"rmse_real": float(real), "rmse_perm_media": float(perm.mean()), "p": float(p)}


def probar(nombre, bloque, s, base, X, y, perm_cols=None, sw=None, notas="", control=None):
    """Evalúa un modelo, lo compara con `base` y lo registra. Devuelve un dict."""
    t0 = time.time()
    mod = modelos.desde_config(s)
    res = cv.evaluate(mod, X, y, "AB", sample_weight=sw)
    comp = cv.comparacion_emparejada(res["A"], base["res"]["A"])
    perm = None
    if comp["aceptada"]:
        cols = perm_cols if perm_cols is not None else columnas_nuevas(s, base)
        perm = permutacion(mod, X, y, cols, sw)
    dec = {"aceptada": bool(comp["aceptada"] and perm is not None and perm["p"] <= 0.05),
           "victorias": comp["victorias"], "diferencia_media": comp["diferencia_media"],
           "p_permutacion": None if perm is None else perm["p"]}
    extra = "" if perm is not None else "; permutacion no corrida (menos de 7 victorias)"
    cc = None
    if control is not None:
        cc = cv.comparacion_emparejada(res["A"], control["res"]["A"])
        extra += (f"; contra el control {control['nombre']}: {cc['victorias']} de 10 victorias, "
                  f"diferencia media {cc['diferencia_media']:+.4f}")
    registrar(res, nombre, bloque, columnas_permutar(s) or ["(solo media por regimen)"],
              s["modelo"], decision=dec, notas=f"base={base['nombre']}{extra}; {notas}".strip("; "))
    a, b = res["A"], res["B"]
    fila = {"paso": bloque, "modelo": nombre, "n_vars": len(s["columnas"]),
            "rmse_A": a.rmse, "mae_A": a.mae, "r2_A": a.r2, "rmse_B": b.rmse,
            "rmse_A_regA": a.por_regimen["A"]["rmse"], "rmse_A_regB": a.por_regimen["B"]["rmse"],
            "rmse_B_regA": b.por_regimen["A"]["rmse"], "rmse_B_regB": b.por_regimen["B"]["rmse"],
            "victorias": comp["victorias"], "dif_media": comp["diferencia_media"],
            "p": dec["p_permutacion"], "aceptada": dec["aceptada"], "base": base["nombre"],
            "control": None if control is None else control["nombre"],
            "vict_control": None if cc is None else cc["victorias"],
            "dif_control": None if cc is None else cc["diferencia_media"]}
    TABLA.append(fila)
    out = {"nombre": nombre, "spec": s, "res": res, "dec": dec, "sw": sw}
    CANDIDATOS.append(out)
    print(f"{bloque:14s} {nombre:42s} A={a.rmse:.4f} B={b.rmse:.4f} "
          f"vict={comp['victorias']:2d} p={dec['p_permutacion']} acept={dec['aceptada']} "
          f"({time.time() - t0:.0f}s)", flush=True)
    return out


def mejor(base, candidatos):
    """Mejor versión aceptada: la de menor RMSE en A entre `base` y los aceptados."""
    ok = [c for c in candidatos if c["dec"]["aceptada"] and c["res"]["A"].rmse < base["res"]["A"].rmse]
    return min(ok, key=lambda c: c["res"]["A"].rmse) if ok else base


# ------------------------------------------------------------------- descriptivo

def relacion_residuo(X, y, bl):
    """Correlación de cada variable con el residuo de la media por régimen, dentro de cada régimen."""
    res = y - y.groupby(X["regimen"]).transform("mean")
    dueño = {c: b for b, cs in bl.items() for c in cs}
    filas = []
    for c in dueño:
        fila = {"variable": c, "bloque": dueño[c]}
        for r in ("A", "B"):
            m = (X["regimen"] == r).to_numpy()
            v = X.loc[m, c]
            ok = v.notna().to_numpy()
            fila[f"r_{r}"] = np.corrcoef(v[ok], res[m][ok])[0, 1] if ok.sum() > 5 and v[ok].std() > 0 else np.nan
            fila[f"rho_{r}"] = v[ok].corr(res[m][ok], method="spearman") if ok.sum() > 5 else np.nan
            fila[f"n_{r}"] = int(ok.sum())
        v = X[c]
        ok = v.notna().to_numpy()
        fila["r_global"] = np.corrcoef(v[ok], res[ok])[0, 1]
        fila["r_max_abs"] = np.nanmax(np.abs([fila["r_A"], fila["r_B"]]))
        filas.append(fila)
    t = pd.DataFrame(filas).sort_values("r_max_abs", ascending=False)
    t.round(4).to_csv(OUTPUTS / "relacion_residuo_regimen.csv", index=False)
    return t


# ---------------------------------------------------------------------- análisis

def tabla_residuos(X, y, oof, ref):
    e = pd.Series(oof, index=X.index) - y
    cal = pd.read_parquet(PROCESSED / "calidad_series.parquet")
    pl = cal[cal["sensor"] == "planet"].set_index("ID_POLIGONO")["n_validas_jjas_2025"]
    s2 = cal[cal["sensor"] == "s2"].set_index("ID_POLIGONO")["n_validas_jjas_2025"]
    d = pd.DataFrame({"estado": X["estado"], "municipio": X["municipio"], "regimen": X["regimen"],
                      "area_cuartil": pd.qcut(X["area_ha"], 4, labels=["Q1 menor", "Q2", "Q3", "Q4 mayor"]).astype(str),
                      "calidad_s2_tercil": pd.qcut(s2.reindex(X.index).rank(method="first"), 3,
                                                   labels=["baja", "media", "alta"]).astype(str),
                      "calidad_planet_tercil": pd.qcut(pl.reindex(X.index).rank(method="first"), 3,
                                                       labels=["baja", "media", "alta"]).astype(str),
                      "e": e})
    filas = []
    for col in ("estado", "municipio", "regimen", "area_cuartil", "calidad_s2_tercil", "calidad_planet_tercil"):
        for g, sub in d.groupby(col):
            filas.append({"agrupacion": col, "grupo": g, "n": len(sub),
                          "rmse": float(np.sqrt((sub.e ** 2).mean())), "mae": float(sub.e.abs().mean()),
                          "sesgo": float(sub.e.mean())})
    t = pd.DataFrame(filas)
    t.round(4).to_csv(OUTPUTS / "residuos_v1.csv", index=False)
    return t, d


def figura_residuos(X, y, oof, d, ruta):
    e = pd.Series(oof, index=X.index) - y
    col = {"A": "#2a6f97", "B": "#e07a1f"}
    fig, ax = plt.subplots(2, 2, figsize=(11, 8.5))
    a = ax[0, 0]
    for r in ("A", "B"):
        m = X["regimen"] == r
        a.scatter(y[m], np.asarray(oof)[m.to_numpy()], s=22, alpha=.75, color=col[r], label=f"Régimen {r}")
    lim = [y.min() - .1, y.max() + .1]
    a.plot(lim, lim, color="#555", lw=1)
    a.set(xlabel="Rendimiento observado (t/ha)", ylabel="Predicción fuera de muestra (t/ha)",
          title="Predicción contra observado")
    a.legend(frameon=False)
    a = ax[0, 1]
    for r in ("A", "B"):
        m = X["regimen"] == r
        a.scatter(X.loc[m, "area_ha"], e[m], s=22, alpha=.75, color=col[r], label=f"Régimen {r}")
    a.axhline(0, color="#555", lw=1)
    a.set(xscale="log", xlabel="Área (ha, escala log)", ylabel="Residuo (predicción menos observado)",
          title="Residuo contra área")
    a = ax[1, 0]
    mun = d.groupby("municipio").e.agg(lambda s: np.sqrt((s ** 2).mean())).sort_values()
    n = d.groupby("municipio").size().reindex(mun.index)
    reg = d.groupby("municipio").regimen.first().reindex(mun.index)
    a.barh([f"{m} (n={k})" for m, k in zip(mun.index, n)], mun.values, color=[col[r] for r in reg])
    a.set(xlabel="RMSE (t/ha)", title="RMSE por municipio (color = régimen)")
    a = ax[1, 1]
    orden = ["Q1 menor", "Q2", "Q3", "Q4 mayor"]
    for i, r in enumerate(("A", "B")):
        v = [np.sqrt((d[(d.area_cuartil == q) & (d.regimen == r)].e ** 2).mean()) for q in orden]
        a.bar(np.arange(4) + (i - .5) * .38, v, .38, color=col[r], label=f"Régimen {r}")
    a.set_xticks(range(4), orden)
    a.set(ylabel="RMSE (t/ha)", title="RMSE por cuartil de área")
    a.legend(frameon=False)
    for x in ax.flat:
        x.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=140)
    plt.close(fig)


def atipicas(X, y, oof, f_all):
    e = pd.Series(oof, index=X.index) - y
    top = e.abs().sort_values(ascending=False).head(10).index
    cal = pd.read_parquet(PROCESSED / "calidad_series.parquet")
    piv = cal.pivot(index="ID_POLIGONO", columns="sensor", values=["n_validas_jjas_2025", "hueco_max_jjas_2025"])
    piv.columns = [f"{a.replace('_jjas_2025', '')}_{b}" for a, b in piv.columns]
    xy = f_all[["x_m", "y_m"]]
    dm = np.sqrt(((xy.to_numpy()[:, None] - xy.to_numpy()[None]) ** 2).sum(-1))
    np.fill_diagonal(dm, np.inf)
    dist = pd.DataFrame(dm, index=xy.index, columns=xy.index)
    ent = f_all.index[f_all["conjunto"] == "ENTRENAMIENTO"]
    clave = ["sat25_planet_ndvi_max", "sat25_planet_ndre_max", "fen_pico_doy", "fen_dias_sos_pico",
             "hist_s2_ndvi_anom_max", "het_planet_ndvi_cv", "topo_elevacion", "clima_prec_total_may_oct"]
    sal = pd.DataFrame({"ID_POLIGONO": top, "municipio": X.loc[top, "municipio"].to_numpy(),
                        "regimen": X.loc[top, "regimen"].to_numpy(), "area_ha": X.loc[top, "area_ha"].to_numpy(),
                        "rendimiento": y[top].to_numpy(), "prediccion_oof": np.asarray(pd.Series(oof, index=X.index)[top]),
                        "residuo": e[top].to_numpy()})
    for c in clave:
        sal[c] = X.loc[top, c].to_numpy()
    for c in piv.columns:
        sal[f"calidad_{c}"] = piv.loc[top, c].to_numpy()
    sal["dist_vecino_mas_cercano_m"] = dist.loc[top].min(axis=1).to_numpy()
    sal["dist_vecino_entrenamiento_m"] = dist.loc[top, ent].min(axis=1).to_numpy()
    sal["dist_vecino_mismo_regimen_m"] = [
        dist.loc[i, ent[(f_all.loc[ent, "regimen"] == X.loc[i, "regimen"]).to_numpy()]].min() for i in top]
    sal.round(4).to_csv(OUTPUTS / "atipicas.csv", index=False)
    return sal


# --------------------------------------------------------------------------- main

def main():
    t_ini = time.time()
    X, y, f_all = cargar()
    bl = bloques(X)
    # Reemplaza filas de corridas anteriores de este script
    if ARCHIVO_REGISTRO.exists():
        with open(ARCHIVO_REGISTRO, newline="", encoding="utf-8") as fh:
            filas = [f for f in csv.DictReader(fh) if not f["bloque"].startswith("v1_")]
        with open(ARCHIVO_REGISTRO, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=ENCABEZADO)
            w.writeheader()
            w.writerows(filas)
    OUTPUTS.mkdir(exist_ok=True)

    rel = relacion_residuo(X, y, bl)
    print("Mayores |r| con el residuo dentro de régimen:")
    print(rel.head(8)[["variable", "r_A", "r_B", "r_max_abs"]].round(3).to_string(index=False))

    # ---- Base: media por régimen (H1 aceptada)
    res0 = cv.evaluate(MediaPorGrupo("regimen"), X, y, "AB")
    base0 = {"nombre": "media_regimen", "spec": None, "res": res0, "dec": {"aceptada": True}}
    base = base0
    print(f"Base media por régimen A={res0['A'].rmse:.4f} B={res0['B'].rmse:.4f}")

    # ---- Paso 1: filas base
    s_reg = spec("ridge", [], contexto=["regimen"], residuos=False)
    s_est = spec("ridge", [], contexto=["estado"], residuos=False)
    s_res0 = spec("ridge", [], residuos=True)
    probar("solo_regimen_ridge", "v1_base", s_reg, base, X, y, perm_cols=["regimen"], notas="regimen codificado en one-hot")
    probar("solo_regimen_residuos_vacio", "v1_base", s_res0, base, X, y, perm_cols=["regimen"],
           notas="equivale a la media por regimen")
    probar("solo_estado_ridge", "v1_base", s_est, base, X, y, perm_cols=["estado"], notas="referencia, estado en lugar de regimen")
    probar("solo_regimen_te", "v1_base", variante(s_reg, codificacion="te"), base, X, y, perm_cols=["regimen"],
           notas="regimen con TargetEncoderGrupo (leave-one-out)")

    # ---- Paso 2: rezago espacial (#28)
    base_sp = spec("ridge", [])
    vec = []
    for r_m, k in ((400, 5), (400, 10), (1000, 10), (250, 10), (600, 10)):
        vec.append(probar(f"rezago_k{k}_r{r_m}m_residuos", "v1_rezago",
                          variante(base_sp, rezago={"k": k, "radio_m": float(r_m), "mismo_regimen": True}),
                          base, X, y, perm_cols=["x_m", "y_m"],
                          notas="modelo de residuos, rezago de vecinos del mismo regimen"))
    s_rez = spec("ridge", [], contexto=["regimen"], residuos=False,
                 rezago={"k": 10, "radio_m": 400.0, "mismo_regimen": True})
    for r_m, k in ((400, 10), (1000, 10), (250, 10), (600, 10)):
        vec.append(probar(f"rezago_k{k}_r{r_m}m_unico", "v1_rezago",
                          variante(s_rez, rezago={"k": k, "radio_m": float(r_m), "mismo_regimen": True}),
                          base, X, y, perm_cols=["x_m", "y_m"],
                          notas="enfoque unico, regimen mas rezago de rendimiento"))
    vec.append(probar("rezago_k10_r400m_unico_cualquier_regimen", "v1_rezago",
                      variante(s_rez, rezago={"k": 10, "radio_m": 400.0, "mismo_regimen": False}),
                      base, X, y, perm_cols=["x_m", "y_m"], notas="vecinos de cualquier regimen"))
    vec.append(probar("rezago_k10_r400m_unico_solo_valor", "v1_rezago",
                      variante(s_rez, rezago={"k": 10, "radio_m": 400.0, "mismo_regimen": True, "solo_valor": True}),
                      base, X, y, perm_cols=["x_m", "y_m"],
                      notas="el modelo ve solo el rezago, sin numero de vecinos ni distancia"))
    vec.append(probar("rezago_k10_r400m_unico_ridge_a01", "v1_rezago",
                      variante(s_rez, params={"alpha": 0.1}), base, X, y, perm_cols=["x_m", "y_m"],
                      notas="ridge con alfa fijo 0.1 (casi minimos cuadrados)"))
    acept = mejor(base, vec)
    if acept is not base:
        base = acept
        base_sp = base["spec"]
    s_rez = base_sp
    print(f"Tras rezago, base = {base['nombre']}")

    # ---- Paso 3: bloques satelitales (#26)
    etapa = []
    comb = {"sat25_fen": bl["sat25_fen"], "hist": bl["hist"], "het": bl["het"], "lab": bl["lab"], "tsup": bl["tsup"]}
    for b, cols in comb.items():
        etapa.append(probar(f"+{b}", "v1_bloques", con_seleccion(variante(base_sp, cols)), base, X, y,
                            notas=f"{len(cols)} variables" + ("; seleccion k=15 dentro del fold" if len(cols) > 20 else "")))
    todos = sum(comb.values(), [])
    etapa.append(probar("+todos_los_bloques_sat_k15", "v1_bloques", variante(base_sp, todos, seleccion_k=15),
                        base, X, y, notas=f"{len(todos)} variables; seleccion k=15"))
    etapa.append(probar("+todos_los_bloques_sat_k10", "v1_bloques", variante(base_sp, todos, seleccion_k=10),
                        base, X, y, notas=f"{len(todos)} variables; seleccion k=10"))
    etapa.append(probar("+sat25_fen_k5", "v1_bloques", variante(base_sp, comb["sat25_fen"], seleccion_k=5),
                        base, X, y, notas="seleccion k=5"))
    etapa.append(probar("+sat25_fen_por_regimen_k10", "v1_bloques",
                        variante(base_sp, comb["sat25_fen"], seleccion_k=10, por_regimen=True), base, X, y,
                        notas="variables estandarizadas dentro de cada regimen, pendiente propia por regimen"))
    etapa.append(probar("+todos_por_regimen_k10", "v1_bloques",
                        variante(base_sp, todos, seleccion_k=10, por_regimen=True), base, X, y,
                        notas="todos los bloques, por regimen, seleccion k=10"))
    acept = mejor(base, etapa)
    if acept is not base:
        base, base_sp = acept, acept["spec"]
    print(f"Tras bloques, base = {base['nombre']}")

    # ---- Paso 4: clima (#27) y topografía
    etapa = []
    for nombre, cols in (("clima", bl["clima"]), ("topo", bl["topo"]), ("clima+topo", bl["clima"] + bl["topo"])):
        etapa.append(probar(f"+{nombre}", "v1_ambiente", con_seleccion(variante(base_sp, cols)), base, X, y,
                            notas=f"{len(cols)} variables"))
    etapa.append(probar("+clima_k5", "v1_ambiente", variante(base_sp, bl["clima"], seleccion_k=5), base, X, y,
                        notas="seleccion k=5"))
    etapa.append(probar("+clima_por_regimen_k5", "v1_ambiente",
                        variante(base_sp, bl["clima"], seleccion_k=5, por_regimen=True), base, X, y,
                        notas="clima estandarizado dentro de cada regimen"))
    acept = mejor(base, etapa)
    if acept is not base:
        base, base_sp = acept, acept["spec"]
    print(f"Tras ambiente, base = {base['nombre']}")

    # ---- Paso 5: enfoque único contra modelo de residuos (con el rezago aceptado)
    etapa = []
    unico = variante(base_sp, contexto=["regimen"], residuos=False)
    resid = variante(base_sp, contexto=[], residuos=True)
    etapa.append(probar("enfoque_unico", "v1_enfoque", unico, base, X, y, notas="regimen one-hot mas todo en un ridge"))
    etapa.append(probar("enfoque_residuos", "v1_enfoque", resid, base, X, y, notas="media por regimen mas ridge del residuo"))
    acept = mejor(base, etapa)
    if acept is not base:
        base, base_sp = acept, acept["spec"]

    # ---- Paso 6: algoritmos. Con el mejor conjunto aceptado y con un conjunto rico (exploratorio)
    etapa = []
    rico = variante(base_sp, todos, seleccion_k=10)
    algoritmos = {
        "ridge_cv": {},
        "elasticnet_cv": dict(modelo="elasticnet"),
        "pls_2": dict(modelo="pls", params={"n_components": 2}),
        "pls_3": dict(modelo="pls", params={"n_components": 3}),
        "rf": dict(modelo="rf"),
        "lgbm": dict(modelo="lgbm"),
        "gp": dict(modelo="gp"),
    }
    for sustrato, etiqueta in ((base_sp, "mejor"), (rico, "rico")):
        for nombre, cfg in algoritmos.items():
            if etiqueta == "mejor" and nombre in ("ridge_cv", "pls_3"):
                continue  # ridge ya está en el rezago; PLS de 3 componentes no cabe en 3 columnas
            s = copy.deepcopy(sustrato)
            s["modelo"] = cfg.get("modelo", s["modelo"])
            s["args"]["params"] = cfg.get("params", {})
            etapa.append(probar(f"alg_{nombre}_{etiqueta}", "v1_algoritmo", s, base, X, y,
                                notas=("columnas del mejor conjunto aceptado" if etiqueta == "mejor"
                                       else "rezago aceptado mas todos los bloques sat, k=10 (exploratorio)")))
    acept = mejor(base, etapa)
    if acept is not base:
        base = acept

    # ---- H2: ruido de etiqueta. Sustrato lineal con sus controles
    etapa = []
    lin = copy.deepcopy(base_sp)
    lin["modelo"] = "ridge"
    lin["args"]["params"] = {"alpha": 0.1}
    sw_area = (X["area_ha"] / X["area_ha"].mean()).rename("w")
    sw_log = (np.log1p(X["area_ha"]) / np.log1p(X["area_ha"]).mean()).rename("w")
    c_r = probar("H2_control_ridge", "v1_H2", lin, base, X, y, notas="control sin cambios, ridge alfa 0.1")
    etapa.append(c_r)
    etapa.append(probar("H2_huber", "v1_H2", variante(lin, modelo="huber", params={"alpha": 0.1}), base, X, y,
                        notas="HuberRegressor epsilon 1.35", control=c_r))
    sl = variante(lin, modelo="lgbm", params={})
    sl["args"]["params"] = {}
    c_l = probar("H2_control_lgbm", "v1_H2", sl, base, X, y, notas="control LightGBM perdida cuadratica")
    etapa.append(c_l)
    sh = copy.deepcopy(sl)
    sh["args"]["params"] = {"objective": "huber", "alpha": 0.5}
    etapa.append(probar("H2_lgbm_huber", "v1_H2", sh, base, X, y, notas="LightGBM con perdida huber, delta 0.5", control=c_l))
    etapa.append(probar("H2_peso_area", "v1_H2", lin, base, X, y, sw=sw_area,
                        notas="ridge con sample_weight proporcional al area", control=c_r))
    etapa.append(probar("H2_peso_log_area", "v1_H2", lin, base, X, y, sw=sw_log,
                        notas="ridge con sample_weight proporcional a log(1 + area)", control=c_r))
    etapa.append(probar("H2_intervalo_B_025_ridge", "v1_H2", variante(lin, intervalo_b=0.25), base, X, y, control=c_r,
                        notas="etiqueta de B como intervalo +-0.25 (3 iteraciones); evaluacion con etiqueta original"))
    etapa.append(probar("H2_intervalo_B_025_mejor", "v1_H2", variante(base["spec"], intervalo_b=0.25), base, X, y,
                        control=base, notas="mismo intervalo sobre el modelo de la mejor version aceptada"))
    acept = mejor(base, etapa)
    if acept is not base:
        base = acept

    # ---- Modelo candidato y diagnósticos
    exploratorios = [c for c in CANDIDATOS if con_info(c["spec"])]
    aceptados = [c for c in CANDIDATOS if c["dec"]["aceptada"] and con_info(c["spec"])]
    if aceptados:
        cand = min(aceptados, key=lambda c: c["res"]["A"].rmse)
        aceptado_regla = True
    else:
        cand = min(exploratorios, key=lambda c: c["res"]["A"].rmse)
        aceptado_regla = False
    print(f"\nCandidato: {cand['nombre']} A={cand['res']['A'].rmse:.4f} B={cand['res']['B'].rmse:.4f} aceptado={aceptado_regla}")
    cfg = {"nombre": cand["nombre"], "modelo": cand["spec"]["modelo"], "columnas": cand["spec"]["columnas"],
           "args": cand["spec"]["args"], "aceptado_por_regla": aceptado_regla,
           "peso_muestras": None if cand["sw"] is None else "area",
           "rmse_A": round(cand["res"]["A"].rmse, 4), "rmse_B": round(cand["res"]["B"].rmse, 4),
           "referencia_media_regimen_A": round(res0["A"].rmse, 4)}
    modelos.guardar_candidato(cfg)

    oof = cand["res"]["A"].oof.mean(axis=1).to_numpy()
    tr, d = tabla_residuos(X, y, oof, X)
    figura_residuos(X, y, oof, d, REPORTE / "figuras" / "residuos_v1.png")
    at = atipicas(X, y, oof, f_all)
    print("\nResiduos por grupo:")
    print(tr.round(3).to_string(index=False))
    print("\nAtípicas:")
    print(at[["ID_POLIGONO", "municipio", "regimen", "area_ha", "rendimiento", "prediccion_oof", "residuo",
              "dist_vecino_mas_cercano_m"]].round(2).to_string(index=False))

    # ---- Prueba de fuga: y permutado
    mod = modelos.desde_config(cand["spec"])
    rng = np.random.default_rng(SEED)
    ys = [pd.Series(rng.permutation(y.to_numpy()), index=y.index) for _ in range(20)]
    def un_perm(yp):
        return (cv.evaluate(mod, X, yp, "A", repeticiones=REP_PERM).rmse,
                cv.evaluate(MediaPorGrupo(None), X, yp, "A", repeticiones=REP_PERM).rmse)
    par = np.array(Parallel(n_jobs=N_JOBS)(delayed(un_perm)(yp) for yp in ys))
    rm, rg = par[:, 0], par[:, 1]
    ref_global = float(cv.evaluate(MediaPorGrupo(None), X, y, "A", repeticiones=REP_PERM).rmse)
    print(f"\nFuga: RMSE del modelo con y permutado, media {rm.mean():.4f}, minimo {rm.min():.4f}; "
          f"media global con las mismas y permutadas {rg.mean():.4f} (minimo {rg.min():.4f}); "
          f"media global con y real {ref_global:.4f}; modelo menos media global, media {np.mean(rm - rg):+.4f}, "
          f"minimo {np.min(rm - rg):+.4f}")
    fuga = {"rmse_modelo_y_permutado_media": float(rm.mean()), "rmse_modelo_y_permutado_min": float(rm.min()),
            "rmse_media_global_y_permutado_media": float(rg.mean()), "rmse_media_global_y_permutado_min": float(rg.min()),
            "dif_media": float(np.mean(rm - rg)), "dif_min": float(np.min(rm - rg)),
            "rmse_media_global_y_real": ref_global, "n": len(rm)}
    pd.Series(fuga).to_csv(OUTPUTS / "prueba_fuga_v1.csv")

    pd.DataFrame(TABLA).round(4).to_csv(OUTPUTS / "ablaciones_v1.csv", index=False)
    print(f"\nTiempo total: {(time.time() - t_ini) / 60:.1f} min")


if __name__ == "__main__":
    main()
