"""Interpretabilidad del modelo: importancia por grupos, ablación, selección y SHAP.

Uso:
    uv run python scripts/parcelas/interpretabilidad.py [--rapido]

Responde las tres preguntas guía separando lo que aporta cada variable de lo que aporta el
régimen. Usa un modelo de análisis (bosque aleatorio poco profundo), que no es el candidato.
Escribe tablas en analisis/parcelas/, los valores SHAP en outputs/parcelas/ y figuras en
outputs/figuras/.
"""
import argparse
import time
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from parcelas import cv, modelos
from parcelas import interpretabilidad as I
from parcelas.config import ANALISIS_PARCELAS, FIGURAS, OUTPUTS_PARCELAS, PROCESSED

warnings.filterwarnings("ignore")
N_JOBS = 8
ALG = "rf"
AZUL, NARANJA, GRIS = "#2a6f97", "#e07a1f", "#8a8f98"


def cargar():
    f = pd.read_parquet(PROCESSED / "features.parquet").set_index("ID_POLIGONO")
    p = pd.read_parquet(PROCESSED / "parcelas.parquet").set_index("ID_POLIGONO")
    f = f.join(p[["rendimiento"]]).sort_index()
    ent = f[f["conjunto"] == "ENTRENAMIENTO"]
    return f.drop(columns="rendimiento"), ent.drop(columns="rendimiento"), ent["rendimiento"]


def _lista(t, escenario, tipo, metodo):
    t = t.rename(columns={"p05": "p05", "p95": "p95"})
    out = t[["grupo", "importancia_media", "p05", "p95"]].copy()
    out.insert(0, "escenario", escenario)
    out["tipo"] = tipo
    out["metodo"] = metodo
    return out


# --------------------------------------------------------------- permutación

def escenarios_permutacion(X, y, cols_sat, cols_cl, cols_tp, rep, n_perm):
    """Permutación agrupada en los escenarios de régimen presente, ausente y dentro de cada régimen."""
    todas = cols_sat + cols_cl + cols_tp
    g_idx = I.grupos_indice(cols_sat)
    g_idx_s = I.grupos_indice(cols_sat, por_sensor=True)
    g_cl = {**I.grupos_clima(cols_cl), **I.grupos_lluvia_cuando(cols_cl)}
    g_bl = I.grupos_bloque(todas)
    reg = X["regimen"].to_numpy()
    filas, detalle = [], []

    def correr(esc, columnas, grupos_tipos, regimen, sub=None, algoritmo=ALG):
        t0 = time.time()
        Xs, ys = (X, y) if sub is None else (X[sub], y[sub])
        mascaras = {"todas": np.ones(len(Xs), bool)}
        if sub is None:
            mascaras |= {"reg_A": Xs["regimen"].to_numpy() == "A", "reg_B": Xs["regimen"].to_numpy() == "B"}
        m = I.modelo_analisis(algoritmo, columnas, regimen)
        grupos = {}
        for g, tipo in grupos_tipos:
            grupos.update({k: v for k, v in g.items()})
        res = I.importancia_permutacion(m, Xs, ys, grupos, repeticiones=rep, n_perm=n_perm,
                                        dentro_de="regimen" if regimen else None,
                                        mascaras=mascaras, n_jobs=N_JOBS)
        tipos = {k: tp for g, tp in grupos_tipos for k in g}
        for nom, t in res.items():
            t = t.assign(escenario=esc, mascara=nom, tipo=t["grupo"].map(tipos))
            detalle.append(t)
        t = res["todas"]
        filas.append(_lista(t, esc, None, "permutacion_agrupada").assign(tipo=t["grupo"].map(tipos).to_numpy()))
        print(f"  {esc:42s} base={t['rmse_base'].iloc[0]:.4f} ({time.time() - t0:.0f}s)", flush=True)

    for nombre, regimen in (("regimen_presente", True), ("regimen_ausente", False)):
        correr(f"{nombre}_satelite", cols_sat, [(g_idx, "indice"), (g_idx_s, "indice")], regimen)
        correr(f"{nombre}_clima", cols_cl, [(g_cl, "clima")], regimen)
        correr(f"{nombre}_completo", todas, [(g_idx, "indice"), (g_cl, "clima"), (g_bl, "bloque")], regimen)
    for r in ("A", "B"):
        sub = (X["regimen"] == r).to_numpy()
        correr(f"dentro_{r}_satelite", cols_sat, [(g_idx, "indice")], True, sub)
        correr(f"dentro_{r}_clima", cols_cl, [(g_cl, "clima")], True, sub)
    # Sensibilidad al algoritmo
    correr("regimen_presente_satelite_lgbm", cols_sat, [(g_idx, "indice")], True, algoritmo="lgbm")
    correr("regimen_ausente_satelite_lgbm", cols_sat, [(g_idx, "indice")], False, algoritmo="lgbm")
    return pd.concat(filas, ignore_index=True), pd.concat(detalle, ignore_index=True)


# ------------------------------------------------------------------ ablación

def escenarios_ablacion(X, y, cols_sat, cols_cl, cols_tp, rep):
    todas = cols_sat + cols_cl + cols_tp
    g_idx = I.grupos_indice(cols_sat)
    g_cl = {**I.grupos_clima(cols_cl), **I.grupos_lluvia_cuando(cols_cl)}
    g_bl = I.grupos_bloque(todas)
    salidas = []
    for nombre, regimen in (("regimen_presente", True), ("regimen_ausente", False)):
        for sufijo, cols, grupos, tipo in (
                ("satelite", cols_sat, g_idx, "indice"), ("clima", cols_cl, g_cl, "clima"),
                ("completo", todas, {**g_idx, **g_cl, **g_bl}, None)):
            t0 = time.time()
            t = I.ablacion_grupos(lambda c, r=regimen: I.modelo_analisis(ALG, c, r), cols, X, y, grupos,
                                  repeticiones=rep, n_jobs=N_JOBS)
            tipos = {k: "indice" for k in g_idx} | {k: "clima" for k in g_cl} | {k: "bloque" for k in g_bl}
            t = t.assign(escenario=f"{nombre}_{sufijo}", rmse_completo=t.attrs["rmse_completo"],
                         tipo=t["grupo"].map(tipos))
            salidas.append(t)
            print(f"  ablación {nombre}_{sufijo:9s} completo={t.attrs['rmse_completo']:.4f} "
                  f"({time.time() - t0:.0f}s)", flush=True)
    return pd.concat(salidas, ignore_index=True)


def cuanto_cuando(X, y, cols_cl, rep):
    """RMSE A de modelos con lluvia total, lluvia por bimestre y toda la lluvia."""
    gl = I.grupos_lluvia_cuando(cols_cl)
    tot, bim = list(gl.values())[0], list(gl.values())[1]
    filas = []
    for esc, regimen in (("regimen_presente", True), ("regimen_ausente", False)):
        ref = None if not regimen else cv.evaluate(I.modelo_analisis(ALG, [], True), X, y, "A", repeticiones=rep)
        for nombre, cols in (("sin lluvia", []), ("solo total (cuánto)", tot),
                             ("solo bimestres (cuándo)", bim), ("total y bimestres", tot + bim),
                             ("todo el clima", cols_cl)):
            if not cols and not regimen:
                continue
            r = cv.evaluate(I.modelo_analisis(ALG, cols, regimen), X, y, "A", repeticiones=rep)
            fila = {"escenario": esc, "variables": nombre, "n_vars": len(cols), "rmse_A": r.rmse,
                    "rmse_A_std": r.rmse_std}
            if regimen and cols:
                c = cv.comparacion_emparejada(r, ref)
                fila.update(victorias_vs_sin_variables=c["victorias"], dif_vs_sin_variables=c["diferencia_media"])
            filas.append(fila)
    return pd.DataFrame(filas)


# ----------------------------------------------------------------------- SHAP

def calcular_shap(Xall, X, y, cols_all, nmax_kernel=None):
    """SHAP del modelo de análisis (régimen presente) y del candidato, para las 197 parcelas."""
    import shap

    ids_ent = X.index
    out = []
    # Modelo de análisis
    m = I.modelo_analisis(ALG, cols_all, True).fit(X, y)
    nombres = I.nombres_variables(m, cols_all)
    Z = I.matriz_explicable(m, Xall, y, ids_ent)
    reg = m.named_steps["reg"].regresor_
    ex = shap.TreeExplainer(reg)
    sv = ex.shap_values(Z)
    base = float(np.ravel(ex.expected_value)[0])
    t = pd.DataFrame(sv, index=Xall.index, columns=nombres)
    t["modelo"] = "analisis_rf"
    t["base_value"] = base
    out.append(t)
    # Candidato
    cfg = modelos.configuracion_candidato()
    g = modelos.desde_config(cfg).fit(X, y)
    ng = I.nombres_variables(g, cfg["columnas"])
    Zg = I.matriz_explicable(g, Xall, y, ids_ent)
    regg = g.named_steps["reg"]
    fn = lambda A: np.asarray(regg.predict(A), dtype=float).ravel()
    bg = Zg[Xall.index.isin(ids_ent)]
    exg = shap.KernelExplainer(fn, bg)
    svg = exg.shap_values(Zg, nsamples=2 ** len(ng), silent=True)
    tg = pd.DataFrame(svg, index=Xall.index, columns=ng)
    tg["modelo"] = "candidato"
    tg["base_value"] = float(np.ravel(exg.expected_value)[0])
    out.append(tg)
    # Comprobación de aditividad
    pred = reg.predict(Z)
    print(f"  SHAP RF: máx |base + suma - predicción| = {np.abs(base + sv.sum(1) - pred).max():.2e}")
    predg = fn(Zg)
    print(f"  SHAP candidato: máx |base + suma - predicción| = "
          f"{np.abs(tg['base_value'].to_numpy() + svg.sum(1) - predg).max():.2e}")
    return out, nombres, Z


def shap_a_importancias(t, cols_sat, cols_cl, cols_tp, ids_ent):
    """Importancia global por grupo con |SHAP| sumado por parcela, en las parcelas de entrenamiento."""
    t = t.loc[ids_ent]
    grupos = {**I.grupos_indice(cols_sat), **I.grupos_clima(cols_cl), **I.grupos_bloque(cols_sat + cols_cl + cols_tp)}
    tipos = {k: "indice" for k in I.grupos_indice(cols_sat)} | {k: "clima" for k in I.grupos_clima(cols_cl)} \
        | {k: "bloque" for k in I.grupos_bloque(cols_sat + cols_cl + cols_tp)}
    grupos |= {"Régimen": ["regimen_A", "regimen_B"], "Rezago espacial": ["rezago_y"]}
    tipos |= {"Régimen": "contexto", "Rezago espacial": "contexto"}
    filas = []
    for g, cs in grupos.items():
        cs = [c for c in cs if c in t.columns]
        if not cs:
            continue
        a = t[cs].sum(axis=1).abs()
        filas.append({"escenario": "regimen_presente_completo", "grupo": g, "tipo": tipos[g],
                      "importancia_media": float(a.mean()), "p05": float(a.quantile(.05)),
                      "p95": float(a.quantile(.95)), "metodo": "shap_abs_media"})
    return pd.DataFrame(filas)


# -------------------------------------------------------------------- figuras

def _barras(ax, t, color, titulo, n=None, xlabel="Aumento del RMSE (t/ha)"):
    t = t.sort_values("importancia_media", ascending=True)
    if n:
        t = t.tail(n)
    y = np.arange(len(t))
    err = np.vstack([t["importancia_media"] - t["p05"], t["p95"] - t["importancia_media"]]).clip(min=0)
    ax.barh(y, t["importancia_media"], color=color, xerr=err, error_kw={"lw": 1, "ecolor": "#333"})
    ax.axvline(0, color="#555", lw=.8)
    ax.set_yticks(y, t["grupo"])
    ax.set(title=titulo, xlabel=xlabel)
    ax.spines[["top", "right"]].set_visible(False)


def fig_indices(imp):
    imp = imp[imp.metodo == "permutacion_agrupada"]
    fig, ax = plt.subplots(1, 2, figsize=(11, 5.5), sharex=False)
    for a, esc, tit, col in ((ax[0], "regimen_presente_satelite", "Régimen presente", AZUL),
                             (ax[1], "regimen_ausente_satelite", "Régimen ausente", NARANJA)):
        t = imp[(imp.escenario == esc) & (imp.tipo == "indice") & ~imp.grupo.str.contains(r"\(Planet|\(Sentinel|\(Landsat")]
        _barras(a, t, col, tit)
    fig.suptitle("Importancia por permutación agrupada de cada índice (media y percentiles 5 a 95 entre repeticiones)", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGURAS / "importancia_indices.png", dpi=140)
    plt.close(fig)


def fig_clima(imp):
    imp = imp[imp.metodo == "permutacion_agrupada"]
    esc = [("regimen_presente_clima", "Régimen presente", AZUL), ("regimen_ausente_clima", "Régimen ausente", NARANJA),
           ("dentro_A_clima", "Dentro del régimen A", "#4c9a6a"), ("dentro_B_clima", "Dentro del régimen B", "#8f6bb3")]
    fig, ax = plt.subplots(2, 2, figsize=(11, 7.5))
    for a, (e, tit, col) in zip(ax.flat, esc):
        t = imp[(imp.escenario == e) & (imp.tipo == "clima")]
        _barras(a, t, col, tit)
    fig.suptitle("Importancia por permutación agrupada de cada variable climática, incluyendo cuánto contra cuándo llovió", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGURAS / "importancia_clima.png", dpi=140)
    plt.close(fig)


def fig_seleccion(sel):
    sel = sel.copy()
    fig, ax = plt.subplots(1, len(sel.modelo.unique()), figsize=(5.8 * len(sel.modelo.unique()), 4.6), squeeze=False)
    for a, (alg, t) in zip(ax[0], sel.groupby("modelo", sort=False)):
        e = t[t.elegido].sort_values("paso")
        a.plot(e["paso"], e["rmse_A"], "-", color=GRIS, lw=1, zorder=1)
        for _, f in e.iterrows():
            a.scatter(f["paso"], f["rmse_A"], s=45, zorder=2,
                      color=AZUL if f["aceptado"] else NARANJA)
            a.annotate(f["candidato"], (f["paso"], f["rmse_A"]), textcoords="offset points",
                       xytext=(4, 7), fontsize=7.5, rotation=20)
        a.set(xlabel="Paso (bloques agregados)", ylabel="RMSE A (t/ha)",
              title=f"Selección hacia adelante, modelo {alg}")
        a.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, 0.005, "Azul: paso aceptado por la regla de decisión. Naranja: rechazado (se muestra solo la curva).", fontsize=8)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(FIGURAS / "seleccion_adelante.png", dpi=140)
    plt.close(fig)


def fig_shap(sv_df, Z, nombres, imp_shap, Xall, ids_ent):
    import shap

    t = imp_shap[imp_shap.tipo.isin(["indice", "clima", "contexto"])]
    # Beeswarm con las variables individuales, en figura propia
    ent = Xall.index.isin(ids_ent)
    shap.summary_plot(sv_df.loc[Xall.index[ent], nombres].to_numpy(), pd.DataFrame(Z[ent], columns=nombres),
                      max_display=14, show=False, plot_size=(8, 5.5))
    plt.title("SHAP por variable (modelo de análisis, régimen presente)", fontsize=10)
    plt.tight_layout()
    plt.savefig(FIGURAS / "shap_resumen.png", dpi=140)
    plt.close()
    # Barras de grupos
    fig, a = plt.subplots(figsize=(6.5, 5))
    _barras(a, t, AZUL, "Importancia SHAP por grupo", n=14, xlabel="|SHAP| medio por parcela (t/ha)")
    fig.tight_layout()
    fig.savefig(FIGURAS / "shap_grupos.png", dpi=140)
    plt.close(fig)


def fig_shap_local(sv_df, nombres, Xall, y):
    """Dos parcelas de ejemplo (una por régimen), con sus 8 contribuciones mayores."""
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    for a, r in zip(ax, ("A", "B")):
        ids = Xall.index[(Xall["regimen"] == r) & Xall.index.isin(y.index)]
        i = (y.loc[ids] - y.loc[ids].median()).abs().idxmax()
        s = sv_df.loc[i, nombres].astype(float)
        s = s.reindex(s.abs().sort_values(ascending=False).index).head(8)[::-1]
        a.barh(s.index, s.values, color=[AZUL if v > 0 else NARANJA for v in s.values])
        a.axvline(0, color="#555", lw=.8)
        a.set(title=f"Parcela {i} (régimen {r}, rendimiento {y[i]:.2f} t/ha)", xlabel="Contribución SHAP (t/ha)")
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIGURAS / "shap_local.png", dpi=140)
    plt.close(fig)


# ------------------------------------------------------------------------ main

def main(rapido=False):
    t_ini = time.time()
    FIGURAS.mkdir(parents=True, exist_ok=True)
    ANALISIS_PARCELAS.mkdir(parents=True, exist_ok=True)
    OUTPUTS_PARCELAS.mkdir(parents=True, exist_ok=True)
    Xall, X, y = cargar()
    cols = list(X.columns)
    cols_sat = I.columnas_satelitales(cols)
    cols_cl = [c for c in cols if c.startswith("clima_")]
    cols_tp = [c for c in cols if c.startswith("topo_")]
    grupos_ind = I.grupos_indice(cols)
    cubiertas = sorted(c for cs in grupos_ind.values() for c in cs)
    assert cubiertas == sorted(cols_sat), "la agrupación por índice no cubre todas las columnas satelitales"
    print(f"{len(cols_sat)} variables satelitales en {len(grupos_ind)} grupos de índice; "
          f"{len(cols_cl)} de clima; {len(cols_tp)} de topografía")
    dup = I.verificar_sin_duplicados(cols)
    print("Variables de índices duplicados de la Tabla IV:", dup if dup else "ninguna")
    # La selección hacia adelante usa siempre 10 repeticiones porque la regla pide 7 victorias de 10
    rep, n_perm, rep_abl, rep_sel = (3, 3, 4, 10) if rapido else (5, 4, 5, 10)

    print("Permutación agrupada")
    imp, detalle = escenarios_permutacion(X, y, cols_sat, cols_cl, cols_tp, rep, n_perm)
    detalle.round(5).to_csv(ANALISIS_PARCELAS / "importancia_permutacion.csv", index=False)

    print("Ablación leave-one-group-out")
    abl = escenarios_ablacion(X, y, cols_sat, cols_cl, cols_tp, rep_abl)
    abl.round(5).to_csv(ANALISIS_PARCELAS / "ablacion_grupos.csv", index=False)
    imp_abl = abl[["escenario", "grupo", "tipo", "importancia_media", "p05", "p95"]].assign(metodo="ablacion_logo")

    print("Lluvia: cuánto contra cuándo")
    cc = cuanto_cuando(X, y, cols_cl, rep_abl)
    cc.round(4).to_csv(ANALISIS_PARCELAS / "clima_cantidad_y_momento.csv", index=False)
    print(cc.round(4).to_string(index=False))

    print("Selección hacia adelante por bloques")
    bl = I.grupos_bloque(cols)
    sel = []
    for alg in ("rf", "ridge"):
        t0 = time.time()
        s = I.seleccion_adelante(X, y, bl, alg, repeticiones=rep_sel, n_jobs=N_JOBS)
        sel.append(s)
        print(f"  {alg}: {time.time() - t0:.0f}s")
        print(s[s.elegido][["paso", "candidato", "rmse_A", "victorias", "p", "aceptado"]].round(4).to_string(index=False))
    sel = pd.concat(sel, ignore_index=True)
    sel.round(5).to_csv(ANALISIS_PARCELAS / "seleccion_bloques.csv", index=False)

    print("SHAP")
    shaps, nombres, Z = calcular_shap(Xall, X, y, cols_sat + cols_cl + cols_tp)
    sv = pd.concat(shaps)
    columnas_shap = list(dict.fromkeys(c for t in shaps for c in t.columns if c not in ("modelo", "base_value")))
    sv = sv.reset_index().rename(columns={"index": "ID_POLIGONO"})
    sv = sv[["ID_POLIGONO"] + columnas_shap + ["modelo", "base_value"]]
    sv.to_parquet(OUTPUTS_PARCELAS / "shap_values.parquet", index=False)
    imp_shap = shap_a_importancias(shaps[0], cols_sat, cols_cl, cols_tp, X.index)
    print(imp_shap.sort_values("importancia_media", ascending=False).head(10).round(4).to_string(index=False))

    todo = pd.concat([imp, imp_abl, imp_shap], ignore_index=True)
    todo = todo[["escenario", "grupo", "tipo", "importancia_media", "p05", "p95", "metodo"]]
    todo.to_parquet(ANALISIS_PARCELAS / "importancias.parquet", index=False)

    fig_indices(todo)
    fig_clima(todo)
    fig_seleccion(sel[sel.modelo.isin(["rf", "ridge"])])
    fig_shap(shaps[0].drop(columns=["modelo", "base_value"]), Z, nombres, imp_shap, Xall, X.index)
    fig_shap_local(shaps[0].drop(columns=["modelo", "base_value"]), nombres, Xall, y)
    print(f"Total {time.time() - t_ini:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true", help="menos repeticiones, para probar")
    main(ap.parse_args().rapido)
