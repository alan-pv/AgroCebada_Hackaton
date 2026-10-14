"""Figuras, tabla y cifras del reporte del modelo generalizable.

Uso, desde la raíz del repositorio:
    uv run python docs/reporte_generalizable/scripts/figuras.py

Lee el SIAP limpio (agrocebada.generalizable), los resultados de experimentos/generalizable y la capa
outputs/generalizable_municipios.{parquet,gpkg}. No vuelve a correr ningún experimento. Escribe las figuras y
la tabla de modelos en docs/reporte_generalizable/figuras y todas las cifras que cita el texto en
docs/reporte_generalizable/scripts/cifras.json.
"""
import json
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch

from agrocebada.generalizable import modelos as M
from agrocebada.generalizable import siap
from agrocebada.generalizable import validacion as V
import importlib.util

warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parents[3]
FIG = RAIZ / "docs/reporte_generalizable/figuras"
EXP = RAIZ / "experimentos/generalizable"
OUT = RAIZ / "outputs"
CIFRAS = {}
_spec = importlib.util.spec_from_file_location("capa", RAIZ / "scripts/generalizable_capa.py")
CAPA = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CAPA)

AZUL, NARANJA, VERDE, GRIS, TINTA, REJILLA = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984", "#0b0b0b", "#e6e5e1"
COL_REG = {"A": AZUL, "B": NARANJA}
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": GRIS, "axes.labelcolor": TINTA,
                     "xtick.color": TINTA, "ytick.color": TINTA, "legend.frameon": False,
                     "hatch.linewidth": 0.5})
ANCHO = 3.45
ANCHO_DOBLE = 7.16
FINAL = "kriging_residuos_simple_a_tmax"
NOMBRE = {"media_global": "Media global", "media_estatal": "Media estatal", "idw_vecinos": "IDW de vecinos",
          "kriging_vecinos": "Kriging de vecinos", "simple_a_tmax": "Tmax jul-ago",
          "simple_b_elev": "Elevación", "simple_c_tmax_prec": "Tmax y lluvia",
          "simple_d_tmax_prec_durica": "Tmax, lluvia y dúrica",
          "simple_e_tmax_prec_estado": "Tmax y lluvia con estado",
          "kriging_residuos_simple_a_tmax": "Tmax con kriging de residuos",
          "kriging_residuos_simple_c_tmax_prec": "Tmax y lluvia con kriging de residuos",
          "ridge_ambiente": "Ridge, 14 variables", "lasso_ambiente": "Lasso, 14 variables"}


def guardar(fig, nombre):
    fig.savefig(FIG / f"{nombre}.pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(FIG / f"{nombre}.png", dpi=170, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def r(x, n=2):
    return None if pd.isna(x) else round(float(x), n)


# ---------------------------------------------------------------- 1. datos del SIAP
crudo = siap.leer()
limpia = M.tabla_modelado("rend")
sembrada = M.tabla_modelado("rend_sembrada")
sin_rep = M.tabla_modelado("rend", sin_repetidos=True)
anual = crudo.groupby("anio")[["sembrada_ha", "cosechada_ha", "siniestrada_ha", "produccion_t"]].sum()
anual["rend"] = anual.produccion_t / anual.cosechada_ha
anual["rend_sembrada"] = anual.produccion_t / anual.sembrada_ha
anual["siniestro"] = anual.siniestrada_ha / anual.sembrada_ha
pend = M.pendiente_comun(limpia, limpia.y.to_numpy())
CIFRAS["datos"] = {
    "anio_ini": int(crudo.anio.min()), "anio_fin": int(crudo.anio.max()),
    "filas_crudas": len(crudo), "municipios_crudos": int(crudo.groupby(["estado", "municipio"]).ngroups),
    "filas_limpias": len(limpia), "municipios_limpios": int(limpia.CVEGEO.nunique()),
    "municipios_por_estado": limpia.groupby("estado").CVEGEO.nunique().astype(int).to_dict(),
    "filas_sembrada": len(sembrada),
    "min_cosechada_ha": siap.MIN_COSECHADA_HA, "min_anios": siap.MIN_ANIOS,
    "frac_repetido_pct": r(100 * limpia.marca_repetido.mean(), 0),
    "frac_repetido_estado_pct": {e: r(100 * v, 0) for e, v in limpia.groupby("estado").marca_repetido.mean().items()},
    "filas_sin_repetidos": len(sin_rep), "municipios_sin_repetidos": int(sin_rep.CVEGEO.nunique()),
    "ddr_modelado": int(limpia.ddr.nunique()),
    "ddr_total": int(pd.read_csv(RAIZ / "data/externos/siap/ddr_municipio.csv").ddr.nunique()),
    "siniestro_pct": {int(a): r(100 * v, 0) for a, v in anual.siniestro.items()},
    "rend_anual": {int(a): r(v) for a, v in anual.rend.items()},
    "rend_sembrada_anual": {int(a): r(v) for a, v in anual.rend_sembrada.items()},
    "tendencia_t_ha_anio": r(pend, 3),
    "tendencia_23_anios": r(pend * 22, 2),
}
mun = pd.read_parquet(RAIZ / "data/processed/generalizable/municipios.parquet")
CIFRAS["datos"]["municipios_inegi"] = len(mun)
CIFRAS["datos"]["municipios_sin_temporal"] = int((mun.agricola_ha == 0).sum())

fig, ax = plt.subplots(figsize=(ANCHO, 1.9))
ax.plot(anual.index, anual.rend, color=AZUL, lw=1.4, marker="o", ms=2.5)
ax.plot(anual.index, anual.rend_sembrada, color=NARANJA, lw=1.4, marker="o", ms=2.5)
for yy, txt, c in ((anual.rend.iloc[-1] + 0.14, "Sobre cosechada", AZUL),
                   (anual.rend_sembrada.iloc[-1] - 0.16, "Sobre sembrada", NARANJA)):
    ax.plot([2025.6, 2026.4], [yy, yy], color=c, lw=1.4)
    ax.text(2026.7, yy, txt, color=TINTA, fontsize=6.5, va="center")
for a, (xt, yt, ha) in {2009: (2007.6, 0.72, "right"), 2011: (2012.6, 0.62, "left")}.items():
    ax.annotate(f"{a}\nsiniestro {100 * anual.siniestro[a]:.0f} %", (a, anual.rend_sembrada[a]), (xt, yt),
                fontsize=6.3, color=TINTA, ha=ha, va="center",
                arrowprops=dict(arrowstyle="-", color=GRIS, lw=0.5, shrinkA=1, shrinkB=2))
ax.set_xlim(2002.5, 2033)
ax.set_xticks([2003, 2007, 2011, 2015, 2019, 2023])
ax.set_ylim(0.25, 3.0)
ax.set_ylabel("Rendimiento regional (t/ha)")
ax.grid(axis="y", color=REJILLA, lw=0.4)
guardar(fig, "g1_siap")

# ---------------------------------------------------------------- 2. tabla de modelos y curva de exclusión
res = pd.read_csv(EXP / "resultados.csv")
niv = res[(res.objetivo == "rend") & (res.unidad == "nivel") & (res.subconjunto == "todos")]


def metrica(modelo, esquema="espacial_buffer", B=0, pond=True, datos="completos", sub=None):
    t = niv if sub is None else res[(res.objetivo == "rend") & (res.unidad == "nivel") & (res.subconjunto == sub)]
    s = t[(t.modelo == modelo) & (t.esquema == esquema) & (t.ponderado == pond) & (t.datos == datos)]
    if esquema == "espacial_buffer":
        s = s[s.buffer_km == B]
    return float(s.rmse.iloc[0]) if len(s) else np.nan


TABLA = ["media_global", "media_estatal", "idw_vecinos", "kriging_vecinos", "simple_a_tmax", "simple_b_elev",
         "simple_c_tmax_prec", "simple_d_tmax_prec_durica", "simple_e_tmax_prec_estado",
         "kriging_residuos_simple_a_tmax", "kriging_residuos_simple_c_tmax_prec", "ridge_ambiente", "lasso_ambiente"]
COLS = [("B0_pond", dict(B=0)), ("B0_sin", dict(B=0, pond=False)), ("B50_pond", dict(B=50)),
        ("B50_sin", dict(B=50, pond=False)), ("ddr_pond", dict(esquema="ddr")),
        ("sinrep_B0_pond", dict(B=0, datos="sin_repetidos"))]
tab = pd.DataFrame({c: [metrica(m, **kw) for m in TABLA] for c, kw in COLS}, index=TABLA)
CIFRAS["tabla"] = {m: {c: r(v, 3) for c, v in fila.items()} for m, fila in tab.iterrows()}
lineas = []
for m in TABLA:
    celdas = []
    for c, _ in COLS:
        v = tab.loc[m, c]
        txt = "n.d." if np.isnan(v) else f"{v:.3f}"
        celdas.append(f"\\textbf{{{txt}}}" if v == tab[c].min() else txt)
    if m in ("kriging_vecinos", "simple_e_tmax_prec_estado", "kriging_residuos_simple_c_tmax_prec"):
        sep = "\\midrule"
    else:
        sep = ""
    nom = NOMBRE[m] + (" (final)" if m == FINAL else "")
    lineas.append(f"{nom} & " + " & ".join(celdas) + " \\\\" + sep)
ENCABEZADO = r"""\begin{table*}[t]
\centering
\caption{RMSE de nivel municipal (t/ha), media de 10 repeticiones. Pond. indica ponderado por superficie sembrada.
En negritas, el menor de cada columna. n.d. indica que el modelo no se evaluó en ese escenario.}
\label{tab:modelos}
\footnotesize
\begin{tabular}{@{}lcccccc@{}}
\toprule
 & \multicolumn{2}{c}{$B = 0$\,km} & \multicolumn{2}{c}{$B = 50$\,km} & Por distrito & Sin repetidos, $B = 0$ \\
\cmidrule(lr){2-3}\cmidrule(lr){4-5}
Modelo & Pond. & Sin ponderar & Pond. & Sin ponderar & Pond. & Pond. \\
\midrule
"""
CIERRE = r"""
\bottomrule
\end{tabular}
\end{table*}"""
(FIG / "tabla_modelos.tex").write_text(ENCABEZADO + "\n".join(lineas) + CIERRE, encoding="utf-8")

# Regla de decisión
dec = json.loads((EXP / "decisiones.json").read_text())
CIFRAS["regla"] = {}
for B in (0, 50):
    for m in ("simple_a_tmax", "simple_c_tmax_prec", FINAL, "simple_b_elev", "ridge_ambiente", "lasso_ambiente"):
        x = dec[f"rend: B={B} {m} vs kriging_vecinos"]
        CIFRAS["regla"][f"B{B}_{m}"] = {"victorias": x["principal"]["victorias"],
                                        "victorias_sin_pond": x["nivel_sin_ponderar"]["victorias"],
                                        "aceptada": x["principal"]["aceptada"]}
for k, v in dec.items():
    if " regla " in k and "permutacion" in v:
        B = k.split("B=")[1].split(" ")[0]
        m = k.split(" regla ")[1].split(" vs ")[0]
        CIFRAS["regla"].setdefault(f"B{B}_{m}", {})["p"] = v["p"]
        CIFRAS["regla"][f"B{B}_{m}"]["p_sin_pond"] = v["permutacion"]["nivel_sin_ponderar"]["p"]
        CIFRAS["regla"][f"B{B}_{m}"]["a_priori"] = v.get("a_priori")
CIFRAS["regla"]["promedio_B0_B50"] = {m: r((tab.loc[m, "B0_pond"] + tab.loc[m, "B50_pond"]) / 2, 3)
                                      for m in ("kriging_vecinos", "simple_a_tmax", FINAL, "simple_c_tmax_prec",
                                                "kriging_residuos_simple_c_tmax_prec")}
CIFRAS["regla"]["promedio_B0_B50_4dec"] = {m: r((tab.loc[m, "B0_pond"] + tab.loc[m, "B50_pond"]) / 2, 4)
                                           for m in (FINAL, "kriging_residuos_simple_c_tmax_prec")}
CIFRAS["grandes"] = {m: {"B0": r(metrica(m, B=0, sub="grandes"), 3), "B50": r(metrica(m, B=50, sub="grandes"), 3)}
                     for m in ("kriging_vecinos", "simple_c_tmax_prec", FINAL)}

CURVA = ["media_global", "kriging_vecinos", "simple_a_tmax", "simple_c_tmax_prec", FINAL]
Bs = sorted(niv[niv.esquema == "espacial_buffer"].buffer_km.unique())
curva = {m: [metrica(m, B=b) for b in Bs] for m in CURVA}
CIFRAS["curva"] = {m: {int(b): r(v, 3) for b, v in zip(Bs, vals)} for m, vals in curva.items()}
CIFRAS["buffers_km"] = [int(b) for b in Bs]
CIFRAS["validacion"] = {"n_grupos": V.N_GRUPOS, "n_rep": V.N_REP, "n_perm": V.N_PERM,
                        "umbral_grande_ha": V.UMBRAL_GRANDE_HA, "anio_referencia": M.ANIO_REFERENCIA,
                        "potencia_idw": M.POTENCIA_IDW}
estilo = {"media_global": (GRIS, "--"), "kriging_vecinos": (NARANJA, "-"), "simple_a_tmax": (VERDE, "-"),
          "simple_c_tmax_prec": (VERDE, ":"), FINAL: (AZUL, "-")}
etiqueta = {"media_global": "Media global", "kriging_vecinos": "Kriging", "simple_a_tmax": "Tmax",
            "simple_c_tmax_prec": "Tmax y lluvia", FINAL: "Tmax con kriging\nde residuos (final)"}
desplaza = {"media_global": 0.0, "kriging_vecinos": 0.012, "simple_a_tmax": -0.01, "simple_c_tmax_prec": -0.012,
            FINAL: -0.012}
fig, ax = plt.subplots(figsize=(ANCHO, 2.3))
for m in CURVA:
    c, ls = estilo[m]
    ax.plot(Bs, curva[m], color=c, ls=ls, lw=1.5 if m == FINAL else 1.1, marker="o", ms=2.5)
    yy = curva[m][-1] + desplaza[m]
    ax.plot([Bs[-1] + 2, Bs[-1] + 6], [yy, yy], color=c, ls=ls, lw=1.2)
    ax.text(Bs[-1] + 7.5, yy, etiqueta[m], color=TINTA, fontsize=6.5, va="center")
for b in (0, 50):
    ax.axvline(b, color=REJILLA, lw=0.8, zorder=0)
ax.text(50, 0.255, " 50 km, sin datos cerca", fontsize=6, color=GRIS, ha="left", va="bottom")
ax.set_xlim(-3, 120)
ax.set_xticks(Bs)
ax.set_ylim(0.25, 0.66)
ax.set_xlabel("Zona de exclusión alrededor del grupo de prueba (km)")
ax.set_ylabel("RMSE de nivel ponderado (t/ha)")
ax.grid(axis="y", color=REJILLA, lw=0.4)
guardar(fig, "g2_exclusion")

# ---------------------------------------------------------------- 3. importancia por bloque
imp = pd.read_csv(EXP / "importancia.csv")
corr = pd.read_csv(EXP / "correlaciones_bloques.csv", index_col=0)
CIFRAS["importancia"] = {f"B{int(f.buffer_km)}_{f.bloque}": {"condicional": r(f.aumento_condicional, 3),
                                                            "p_condicional": r(f.p_condicional),
                                                            "marginal": r(f.mejora_marginal, 3),
                                                            "p_marginal": r(f.p_marginal),
                                                            "rmse_completo": r(f.rmse_completo, 3),
                                                            "rmse_media_global": r(f.rmse_media_global, 3)}
                         for f in imp.itertuples()}
CIFRAS["corr_elev_tmax"] = r(corr.loc["elev_m", "clim_tmax_jul_ago"])
CIFRAS["corr_prec_mayoct_mayjun"] = r(corr.loc["clim_prec_may_oct", "clim_prec_may_jun"])
BLOQ = ["temperatura", "lluvia", "topografia", "suelo"]
NBLOQ = {"temperatura": "Temperatura", "lluvia": "Lluvia", "topografia": "Topografía", "suelo": "Suelo"}
fig, axs = plt.subplots(1, 2, figsize=(ANCHO, 1.85), sharey=True)
for ax, B in zip(axs, (0, 50)):
    s = imp[imp.buffer_km == B].set_index("bloque").loc[BLOQ]
    for i, b in enumerate(BLOQ[::-1]):
        f = s.loc[b]
        ax.scatter(f.aumento_condicional, i + 0.13, s=18, color=AZUL, zorder=3)
        ax.scatter(f.mejora_marginal, i - 0.13, s=18, color=NARANJA, zorder=3, marker="s")
    ax.axvline(0, color=GRIS, lw=0.6)
    ax.set_xlim(-0.34, 0.22)
    ax.set_xticks([-0.3, -0.2, -0.1, 0, 0.1, 0.2])
    ax.set_xticklabels(["−0.3", "", "", "0", "", "0.2"], fontsize=7)
    ax.set_title(f"B = {B} km", fontsize=7.5, loc="left")
    ax.grid(axis="x", color=REJILLA, lw=0.4)
axs[0].set_yticks(range(len(BLOQ)), [NBLOQ[b] for b in BLOQ[::-1]])
axs[0].set_ylim(-0.6, 3.9)
axs[0].scatter([-0.315], [3.62], s=12, color=AZUL)
axs[0].scatter([-0.315], [3.32], s=12, color=NARANJA, marker="s")
axs[0].text(-0.29, 3.62, "condicional", color=TINTA, fontsize=6.3, va="center")
axs[0].text(-0.29, 3.32, "marginal", color=TINTA, fontsize=6.3, va="center")
fig.supxlabel("Cambio en el RMSE de nivel ponderado (t/ha)", fontsize=8, y=-0.06)
guardar(fig, "g3_importancia")

# Coeficientes del modelo final y del de dos variables, ajustados con todos los datos.
y = limpia.y.to_numpy()
base = limpia.drop_duplicates("CVEGEO").iloc[[0, 0]].copy().assign(anio=M.ANIO_REFERENCIA)
b1 = base.copy()
b1["clim_tmax_jul_ago"] = b1.clim_tmax_jul_ago.iloc[0] + np.array([0.0, 1.0])
pa = M.modelo("simple_a_tmax")(limpia, y, b1)
pc = M.modelo("simple_c_tmax_prec")(limpia, y, b1)
b2 = base.copy()
b2["clim_prec_may_oct"] = b2.clim_prec_may_oct.iloc[0] + np.array([0.0, 100.0])
pc2 = M.modelo("simple_c_tmax_prec")(limpia, y, b2)
CIFRAS["coef"] = {"tmax_sola_por_grado": r(pa[1] - pa[0]), "tmax_con_lluvia_por_grado": r(pc[1] - pc[0]),
                  "lluvia_por_100mm": r(pc2[1] - pc2[0])}
niv_mun = limpia.groupby("CVEGEO").agg(t=("clim_tmax_jul_ago", "first"), y=("y", "mean"))
CIFRAS["tmax_rango_con_siap"] = [r(niv_mun.t.min(), 1), r(niv_mun.t.max(), 1)]
CIFRAS["corr_tmax_nivel"] = r(np.corrcoef(niv_mun.t, niv_mun.y)[0, 1])

# ---------------------------------------------------------------- 4. clima del año
fila = res[(res.objetivo == "rend") & (res.unidad == "fila") & (res.subconjunto == "todos")
           & (res.datos == "completos") & res.esquema.isin(["espacial", "anio"])]
ORD_ESP = ["kriging_vecinos", "lgbm_ubicacion", "lgbm_ubicacion_anomalias", "lgbm_ubicacion_indicadoras_anio",
           "kriging_mas_efecto_estado_anio", "idw_vecinos_anio"]
ORD_ANIO = ["media_propia_tendencia", "propia_mas_anomalia_ridge", "propia_mas_anomalia_lgbm"]
NOM_CA = {"kriging_vecinos": "Kriging de niveles", "lgbm_ubicacion": "Árboles sobre coordenadas",
          "lgbm_ubicacion_anomalias": "Coordenadas y anomalías del año",
          "lgbm_ubicacion_indicadoras_anio": "Coordenadas e indicadoras del año",
          "kriging_mas_efecto_estado_anio": "Kriging y efecto estado-año",
          "idw_vecinos_anio": "Vecinos del mismo año",
          "media_propia_tendencia": "Media propia con tendencia",
          "propia_mas_anomalia_ridge": "Media propia y anomalías, ridge",
          "propia_mas_anomalia_lgbm": "Media propia y anomalías, árboles"}


def rf(esq, m, pond):
    s = fila[(fila.esquema == esq) & (fila.modelo == m) & (fila.ponderado == pond)]
    return float(s.rmse.iloc[0])


CIFRAS["clima_anio"] = {f"{esq}_{m}": {"sin_pond": r(rf(esq, m, False), 3), "pond": r(rf(esq, m, True), 3)}
                        for esq, ms in (("espacial", ORD_ESP), ("anio", ORD_ANIO)) for m in ms}
x = dec["rend: espacial 5 folds, fila: lgbm_ubicacion_anomalias vs lgbm_ubicacion_indicadoras_anio"]
CIFRAS["clima_anio"]["victorias_anom_vs_indicadoras"] = x["victorias"]
x = dec["rend: espacial 5 folds, fila: lgbm_ubicacion_anomalias vs lgbm_ubicacion"]
CIFRAS["clima_anio"]["victorias_anom_vs_ubicacion"] = x["victorias"]
filas_ca = [("espacial", m) for m in ORD_ESP] + [("anio", m) for m in ORD_ANIO]
fig, ax = plt.subplots(figsize=(ANCHO, 2.45))
ys = []
for i, (esq, m) in enumerate(filas_ca):
    yy = len(filas_ca) - i + (0.6 if esq == "espacial" else 0)
    ys.append(yy)
    v = rf(esq, m, False)
    c = AZUL if "anomal" in m else (NARANJA if ("indicadoras" in m or "estado_anio" in m or "_anio" in m and esq == "espacial") else GRIS)
    ax.plot([0.55, v], [yy, yy], color=REJILLA, lw=1, zorder=1)
    ax.scatter(v, yy, s=20, color=c, zorder=3)
    ax.text(v + 0.004, yy, f"{v:.3f}", va="center", fontsize=6.3)
ax.set_yticks(ys, [NOM_CA[m] for _, m in filas_ca], fontsize=6.5)
ax.text(0.551, ys[0] + 0.75, "Lugar nuevo, año ya cosechado en los vecinos", fontsize=6.3, color=GRIS)
ax.text(0.551, ys[len(ORD_ESP)] + 0.75, "Año nuevo (pronóstico)", fontsize=6.3, color=GRIS)
ax.set_xlim(0.55, 0.72)
ax.set_ylim(0.4, ys[0] + 1.2)
ax.set_xlabel("RMSE por municipio y año, sin ponderar (t/ha)")
ax.grid(axis="x", color=REJILLA, lw=0.4)
guardar(fig, "g4_clima_anio")

# ---------------------------------------------------------------- 5. riesgo y cobertura
cob = pd.read_csv(EXP / "cobertura.csv")
capa = pd.read_parquet(OUT / "generalizable_municipios.parquet")
escala = capa.escala.iloc[0]
CIFRAS["escala"] = escala


def cv(obj, B, esc, pond, est="Todos", col="cobertura"):
    s = cob[(cob.objetivo == obj) & (cob.buffer_km == B) & (cob.escala == esc) & (cob.ponderado == pond)
            & (cob.estado == est)]
    return r(s[col].iloc[0], 3)


ESTADOS = ["Hidalgo", "México", "Puebla", "Tlaxcala"]
CIFRAS["cobertura"] = {f"{obj}_B{B}_{esc}": {"todos": cv(obj, B, esc, False), "todos_pond": cv(obj, B, esc, True),
                                             "ancho": cv(obj, B, esc, False, col="ancho"),
                                             "brier": cv(obj, B, esc, False, col="brier"),
                                             "prob_media": cv(obj, B, esc, False, col="prob_bajo_media"),
                                             "frac_obs": cv(obj, B, esc, False, col="frac_bajo_obs"),
                                             **{e: cv(obj, B, esc, False, e) for e in ESTADOS}}
                       for obj in ("rend", "rend_sembrada") for B in (0, 50) for esc in ("global", "local")}

# ---------------------------------------------------------------- 6. capa y mapas
con_pred = capa.esperado.notna()
CIFRAS["capa"] = {
    "municipios": len(capa), "con_prediccion": int(con_pred.sum()), "sin_prediccion": int((~con_pred).sum()),
    "dentro_dominio": int(capa.dentro_dominio.sum()), "con_siap": int(capa.con_siap.sum()),
    "confianza": {k: int(v) for k, v in capa.confianza.value_counts().items()},
    "dist_cerca_km": CAPA.DIST_CERCA_KM, "dist_media_km": CAPA.DIST_CONFIANZA_MEDIA_KM,
    "dist_dominio_km": CAPA.DIST_DOMINIO_KM, "cobertura_minima": CAPA.COBERTURA_MINIMA,
    "esperado_alta_mediana": r(capa[capa.confianza == "alta"].esperado.median()),
    "esperado_rango": [r(capa.esperado.min()), r(capa.esperado.max())],
    "prob_bajo_2_alta_mediana": r(capa[capa.confianza == "alta"].prob_bajo_2.median()),
    "prob_sembrada_alta_mediana": r(capa[capa.confianza == "alta"].prob_bajo_2_sembrada.median()),
    "ancho_mediano": r((capa.p90 - capa.p10).median()),
}
top = capa[con_pred].sort_values("esperado", ascending=False).head(10)
CIFRAS["capa"]["top10"] = [{"municipio": f.municipio, "estado": f.estado, "esperado": r(f.esperado),
                            "confianza": f.confianza, "dist_siap_km": r(f.dist_siap_km, 0)} for f in top.itertuples()]
CIFRAS["capa"]["top10_por_confianza"] = top.confianza.value_counts().to_dict()
alta = capa[capa.confianza == "alta"].sort_values("esperado", ascending=False)
CIFRAS["capa"]["top5_alta"] = [{"municipio": f.municipio, "estado": f.estado, "esperado": r(f.esperado),
                                "prob_bajo_2": r(f.prob_bajo_2)} for f in alta.head(5).itertuples()]
CIFRAS["capa"]["bottom3_alta"] = [{"municipio": f.municipio, "estado": f.estado, "esperado": r(f.esperado),
                                   "prob_bajo_2": r(f.prob_bajo_2)} for f in alta.tail(3).itertuples()]
pa_ = alta.sort_values("prob_bajo_2")
CIFRAS["capa"]["prob_alta_min"] = {"municipio": pa_.municipio.iloc[0], "estado": pa_.estado.iloc[0],
                                   "prob": r(pa_.prob_bajo_2.iloc[0]), "esperado": r(pa_.esperado.iloc[0])}
CIFRAS["capa"]["prob_alta_max"] = {"municipio": pa_.municipio.iloc[-1], "estado": pa_.estado.iloc[-1],
                                   "prob": r(pa_.prob_bajo_2.iloc[-1]), "esperado": r(pa_.esperado.iloc[-1])}
casos = capa[capa.municipio.isin(["Jilotzingo", "Tlalmanalco", "Huixquilucan"])]
CIFRAS["capa"]["casos_bosque"] = {f.municipio: {"esperado": r(f.esperado), "confianza": f.confianza,
                                                "dist_siap_km": r(f.dist_siap_km, 0), "agricola_ha": r(f.agricola_ha, 0)}
                                  for f in casos.itertuples()}

geo = gpd.read_file(OUT / "generalizable_municipios.gpkg", layer="municipios").to_crs("EPSG:6372")
estados = gpd.read_file(RAIZ / "data/externos/inegi_marcogeo/municipios_13_15_21_29.gpkg",
                        layer="municipios").to_crs("EPSG:6372").dissolve("estado")
estados["geometry"] = estados.geometry.simplify(200)
bordes_x = geo.total_bounds


def mapa(ax, col, cortes, cmap_nombre, titulo, fmt):
    cmap = plt.get_cmap(cmap_nombre)
    colores = ListedColormap([cmap(v) for v in np.linspace(0.12, 0.92, len(cortes) - 1)])
    norm = BoundaryNorm(cortes, colores.N)
    sin = geo[geo[col].isna()]
    sin.plot(ax=ax, color="#f1f0ec", edgecolor="white", lw=0.2)
    con = geo[geo[col].notna()]
    con.plot(ax=ax, column=col, cmap=colores, norm=norm, edgecolor="white", lw=0.2)
    con[con.confianza == "baja"].plot(ax=ax, facecolor="none", edgecolor="#4a4a46", hatch="////", lw=0)
    con[con.confianza == "media"].plot(ax=ax, facecolor="none", edgecolor="#4a4a46", hatch="...", lw=0)
    estados.boundary.plot(ax=ax, color=TINTA, lw=0.6)
    ax.set_axis_off()
    ax.set_aspect("equal")
    ax.set_title(titulo, fontsize=8, loc="left")
    sm = plt.cm.ScalarMappable(cmap=colores, norm=norm)
    cb = plt.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.04, pad=0.01, aspect=30, shrink=0.85)
    cb.set_ticks(cortes)
    cb.set_ticklabels([fmt(c) for c in cortes])
    cb.ax.tick_params(labelsize=6.5, length=2)
    cb.outline.set_visible(False)


fig, axs = plt.subplots(1, 2, figsize=(ANCHO_DOBLE, 4.3))
mapa(axs[0], "esperado", [1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25], "Blues", "(a) Rendimiento esperado en 2025 (t/ha)",
     lambda c: f"{c:.2f}")
mapa(axs[1], "prob_bajo_2", [0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0], "Oranges",
     "(b) Probabilidad de quedar bajo 2 t/ha en un año cualquiera", lambda c: f"{c:.1f}")
for nombre, (dx, dy) in {"Hidalgo": (0, 0), "México": (-40e3, 20e3), "Puebla": (35e3, -60e3),
                         "Tlaxcala": (55e3, 30e3)}.items():
    p = estados.loc[nombre].geometry.representative_point()
    for ax in axs:
        ax.annotate(nombre, (p.x, p.y), (p.x + dx, p.y + dy), fontsize=7, color=TINTA, ha="center",
                    fontweight="bold", arrowprops=None if dx == 0 else dict(arrowstyle="-", color=TINTA, lw=0.4))
leyenda = [Patch(facecolor="#f1f0ec", edgecolor=GRIS, lw=0.4, label="Fuera del rango ambiental, sin valor"),
           Patch(facecolor="white", edgecolor=TINTA, lw=0.4, label="Confianza alta, con historia SIAP"),
           Patch(facecolor="white", edgecolor="#4a4a46", hatch="...", lw=0.4, label="Confianza media"),
           Patch(facecolor="white", edgecolor="#4a4a46", hatch="////", lw=0.4, label="Confianza baja")]
fig.legend(handles=leyenda, loc="lower center", ncol=4, fontsize=6.8, bbox_to_anchor=(0.5, -0.02),
           handlelength=1.6, columnspacing=1.4)
fig.subplots_adjust(wspace=0.04, bottom=0.08)
guardar(fig, "g5_mapas")

# ---------------------------------------------------------------- 7. reto
reto = pd.read_csv(EXP / "reto.csv")
# Promedios por régimen ponderados por parcelas, con la precisión completa de reto.csv (el resumen en json
# viene redondeado a tres decimales y al redondear otra vez cambia el segundo decimal).
CIFRAS["reto"] = {}
for g, s in reto.groupby("regimen"):
    w = s.n.to_numpy(float)
    prom = {c: float(np.average(s[c], weights=w)) for c in ("reto", "nivel_fuera_muestra_B0",
                                                            "nivel_fuera_muestra_B50", "siap_2025")}
    CIFRAS["reto"][g] = {"parcelas": int(w.sum()), "municipios": len(s), **{k: r(v) for k, v in prom.items()},
                         "dif_reto_nivel_B0": r(prom["reto"] - prom["nivel_fuera_muestra_B0"]),
                         "dif_reto_nivel_B50": r(prom["reto"] - prom["nivel_fuera_muestra_B50"]),
                         "dif_reto_siap_2025": r(prom["reto"] - prom["siap_2025"])}
CIFRAS["reto_municipios"] = int(len(reto))
CIFRAS["reto_brecha"] = r(CIFRAS["reto"]["A"]["reto"] - CIFRAS["reto"]["B"]["reto"])
CIFRAS["reto_dif_A_rango"] = [r(reto[reto.regimen == "A"].dif_reto_nivel_B0.min()),
                              r(reto[reto.regimen == "A"].dif_reto_nivel_B0.max())]
CIFRAS["reto_dif_B_rango"] = [r(reto[reto.regimen == "B"].dif_reto_nivel_B0.min()),
                              r(reto[reto.regimen == "B"].dif_reto_nivel_B0.max())]
CORTO = {"Nanacamilpa de Mariano Arista": "Nanacamilpa", "Cuautepec de Hinojosa": "Cuautepec",
         "Emiliano Zapata": "E. Zapata"}
orden = reto.sort_values(["regimen", "reto"], ascending=[True, False]).reset_index(drop=True)
fig, ax = plt.subplots(figsize=(ANCHO, 2.7))
for i, m in orden.iterrows():
    ax.plot([m.p10, m.p90], [i, i], color=GRIS, lw=2.2, alpha=0.35, solid_capstyle="round", zorder=1)
    ax.scatter(m.nivel_fuera_muestra_B0, i, s=22, marker="D", facecolor="white", edgecolor=TINTA, lw=0.9, zorder=3)
    ax.scatter(m.siap_2025, i, s=18, marker="x", color=GRIS, lw=1, zorder=3)
    ax.scatter(m.reto, i, s=10 + 1.2 * m.n, color=COL_REG[m.regimen], zorder=4)
ax.scatter([], [], s=22, color=GRIS, label="Reto, media del municipio")
ax.scatter([], [], s=22, marker="D", facecolor="white", edgecolor=TINTA, label="Modelo, fuera de muestra")
ax.scatter([], [], s=18, marker="x", color=GRIS, label="SIAP 2025")
ax.plot([], [], color=GRIS, lw=2.2, alpha=0.35, label="Intervalo p10 a p90 del modelo")
ax.set_yticks(range(len(orden)), [f"{CORTO.get(m, m)} ({e[:3]}.)" for m, e in zip(orden.municipio, orden.estado)])
n_a = int((orden.regimen == "A").sum())
ax.axhline(n_a - 0.5, color=REJILLA, lw=0.8)
ax.text(5.17, n_a - 0.56, "Régimen A ↑", color=TINTA, fontsize=6.5, ha="right", va="bottom")
ax.text(5.17, n_a - 0.44, "Régimen B ↓", color=TINTA, fontsize=6.5, ha="right", va="top")
ax.invert_yaxis()
ax.set_xlim(1.4, 5.2)
ax.set_xlabel("Rendimiento (t/ha)")
ax.legend(loc="lower left", bbox_to_anchor=(-0.42, 1.0), ncol=2, fontsize=6.2, handletextpad=0.2, columnspacing=0.8)
ax.grid(axis="x", color=REJILLA, lw=0.4)
guardar(fig, "g6_reto")

# ---------------------------------------------------------------- 8. figuras de proceso y evidencia
# Todas salen de los parquet y csv de experimentos/generalizable. Las predicciones fuera de fold por
# repetición permiten el RMSE de cada repetición. La única cifra recalculada son las 99 permutaciones
# del modelo de Tmax con B = 50, que la prueba original no guardó una por una. Se recalculan con la
# misma semilla y se guardan en experimentos/generalizable/permutaciones_figura.csv.
from matplotlib.lines import Line2D
from agrocebada.config import SEED
from agrocebada.generalizable import riesgo as R

AMARILLO = "#eda100"  # cuarto color de estado, validado con el validador de paleta (modo claro)
COL_EST = {"Hidalgo": AZUL, "México": NARANJA, "Puebla": VERDE, "Tlaxcala": AMARILLO}
FONDO = "#f1f0ec"
ctx = V.contexto(limpia)
reps = V.particiones_grupo(limpia)
oof = pd.read_parquet(EXP / "oof_rend.parquet")
assert (oof.CVEGEO.to_numpy() == limpia.CVEGEO.to_numpy()).all()
y = limpia.y.to_numpy()


def col_oof(m, B, i):
    return oof[f"espacial_buffer|{B}|{m}|{i}"].to_numpy()


def rmse_reps(m, B, pond=True):
    return np.array([V.metricas_rep(y, col_oof(m, B, i), ctx, ponderado=pond)["rmse"] for i in range(V.N_REP)])


# Nivel municipal observado, llevado a 2025 con la tendencia común (descriptivo, con todos los datos).
lim = limpia.assign(y25=limpia.y - pend * (limpia.anio - M.ANIO_REFERENCIA))
nm = lim.groupby("CVEGEO").agg(estado=("estado", "first"), municipio=("municipio", "first"), nivel=("y25", "mean"),
                               w=("sembrada_ha", "mean"), anios=("anio", "size"),
                               **{c: (c, "first") for c in M.VARIABLES_BLOQUES})
geo_mun = gpd.read_file(RAIZ / "data/externos/inegi_marcogeo/municipios_13_15_21_29.gpkg",
                        layer="municipios").to_crs("EPSG:6372")
geo_mun["geometry"] = geo_mun.geometry.simplify(150)
geo_mun = geo_mun.merge(mun[["CVEGEO", "x_m", "y_m", "agricola_ha", "clim_tmax_jul_ago"]], on="CVEGEO", how="left")


def wcorr(a, b, w):
    a, b, w = map(np.asarray, (a, b, w))
    am, bm = np.average(a, weights=w), np.average(b, weights=w)
    return float(np.average((a - am) * (b - bm), weights=w)
                 / np.sqrt(np.average((a - am) ** 2, weights=w) * np.average((b - bm) ** 2, weights=w)))


def recta_pond(x, yv, w):
    x, yv, w = (np.asarray(v, float) for v in (x, yv, w))
    X = np.column_stack([np.ones(len(x)), x])
    sw = np.sqrt(w)
    return np.linalg.lstsq(X * sw[:, None], yv * sw, rcond=None)[0]


CIFRAS["nivel_2025"] = {
    "rango": [r(nm.nivel.min()), r(nm.nivel.max())],
    "corr_tmax": r(np.corrcoef(nm.clim_tmax_jul_ago, nm.nivel)[0, 1]),
    "corr_tmax_pond": r(wcorr(nm.clim_tmax_jul_ago, nm.nivel, nm.w)),
    "corr_prec": r(np.corrcoef(nm.clim_prec_may_oct, nm.nivel)[0, 1]),
    "corr_prec_pond": r(wcorr(nm.clim_prec_may_oct, nm.nivel, nm.w)),
    "pend_tmax_pond": r(recta_pond(nm.clim_tmax_jul_ago, nm.nivel, nm.w)[1]),
    "pend_prec_100mm_pond": r(100 * recta_pond(nm.clim_prec_may_oct, nm.nivel, nm.w)[1]),
    "tmax_rango_todos": [r(mun[mun.agricola_ha > 0].clim_tmax_jul_ago.min(), 1),
                         r(mun[mun.agricola_ha > 0].clim_tmax_jul_ago.max(), 1)],
}

# ---- 8a. diagrama del proceso (TikZ, con las cifras de este archivo)
cap = CIFRAS["capa"]
PROCESO = r"""\begin{figure*}[t]
\centering
\begin{tikzpicture}[caja/.style={draw=black!55, rounded corners=2pt, align=center, text width=1.92cm,
  minimum height=1.75cm, font=\scriptsize, fill=black!3, inner sep=3pt},
  clave/.style={caja, draw=black, line width=0.8pt},
  flecha/.style={-{Stealth[length=4pt]}, black!70, line width=0.6pt}, node distance=0.36cm]
\node[caja] (f) {\textbf{Fuentes públicas}\\[2pt] SIAP %(a0)d a %(a1)d, CHIRPS, CHIRTS-ERA5, Copernicus DEM e INEGI};
\node[caja, right=of f] (v) {\textbf{Variables por municipio}\\[2pt] promedio sobre la agricultura de temporal, ventanas del ciclo};
\node[caja, right=of v] (t) {\textbf{Tabla municipio-año}\\[2pt] %(filas)s filas de %(mun)d municipios, nivel llevado a %(ref)d};
\node[clave, right=of t] (val) {\textbf{Validación}\\[2pt] espacial con exclusión de 0 a %(bmax)d km, por DDR, sin repetidos y por año};
\node[caja, right=of val] (m) {\textbf{Modelos}\\[2pt] bases sin ambiente, simples, kriging de residuos y %(nvar)d variables};
\node[clave, right=of m] (r) {\textbf{Regla de decisión}\\[2pt] gana en %(vmin)d de %(nrep)d y $p \le %(pmax)s$ contra el kriging};
\node[caja, right=of r] (c) {\textbf{Capa de riesgo}\\[2pt] %(npred)d municipios con p10 a p90, probabilidad bajo %(umbral)d\,t/ha y confianza};
\foreach \a/\b in {f/v, v/t, t/val, val/m, m/r, r/c} \draw[flecha] (\a) -- (\b);
\end{tikzpicture}
\caption{Proceso del modelo. Los recuadros con borde grueso se fijaron antes de correr la versión final de los
experimentos.}
\label{fig:proceso}
\end{figure*}
""" % {"a0": CIFRAS["datos"]["anio_ini"], "a1": CIFRAS["datos"]["anio_fin"],
       "filas": f"{CIFRAS['datos']['filas_limpias']:,}".replace(",", "\\,"), "mun": CIFRAS["datos"]["municipios_limpios"],
       "ref": M.ANIO_REFERENCIA, "bmax": max(CIFRAS["buffers_km"]), "nvar": len(M.FIJAS), "vmin": 7, "nrep": V.N_REP,
       "pmax": "0.05", "npred": cap["con_prediccion"], "umbral": 2}
(FIG / "proceso.tex").write_text(PROCESO, encoding="utf-8")

# ---- 8b. esquema de la validación con zona de exclusión sobre el mapa real
B_ESQ = 50
grupos0 = pd.Series(reps[0], index=limpia.CVEGEO).groupby(level=0).first()
cent = nm.join(mun.set_index("CVEGEO")[["x_m", "y_m"]])
g_cent = cent.groupby(grupos0)[["x_m", "y_m"]].mean()
centro = cent[["x_m", "y_m"]].mean()
g_sel = int(((g_cent - centro) ** 2).sum(1).idxmin())
te_rows = (reps[0] == g_sel)
tr_rows = V.mascara_entrenamiento(limpia, te_rows, B_ESQ)
prueba = set(limpia.CVEGEO[te_rows])
entrena = set(limpia.CVEGEO[tr_rows])
excluidos = set(nm.index) - prueba - entrena
CIFRAS["esquema_validacion"] = {"B_km": B_ESQ, "prueba": len(prueba), "excluidos": len(excluidos),
                                "entrenamiento": len(entrena)}
from shapely.geometry import Point
from shapely.ops import unary_union
anillo = unary_union([Point(xy).buffer(B_ESQ * 1000) for xy in cent.loc[list(prueba), ["x_m", "y_m"]].to_numpy()])
estados_s = estados.copy()
fig, ax = plt.subplots(figsize=(ANCHO, 2.6))
geo_mun.plot(ax=ax, color=FONDO, edgecolor="white", lw=0.2)
for conj, c in ((entrena, AZUL), (excluidos, GRIS), (prueba, NARANJA)):
    geo_mun[geo_mun.CVEGEO.isin(conj)].plot(ax=ax, color=c, edgecolor="white", lw=0.2)
gpd.GeoSeries([anillo], crs="EPSG:6372").boundary.plot(ax=ax, color=TINTA, lw=0.9, linestyle="--")
estados_s.boundary.plot(ax=ax, color=TINTA, lw=0.5)
ax.set_axis_off()
ax.set_aspect("equal")
leyenda = [Patch(facecolor=NARANJA, label=f"Grupo de prueba ({len(prueba)} municipios)"),
           Patch(facecolor=GRIS, label=f"Excluidos, a menos de {B_ESQ} km ({len(excluidos)})"),
           Patch(facecolor=AZUL, label=f"Entrenamiento ({len(entrena)})"),
           Line2D([], [], color=TINTA, lw=0.9, ls="--", label=f"Límite de {B_ESQ} km"),
           Patch(facecolor=FONDO, edgecolor=GRIS, lw=0.3, label="Sin historia en el SIAP")]
fig.legend(handles=leyenda, loc="upper center", bbox_to_anchor=(0.5, 0.16), ncol=2, fontsize=6.3,
           handlelength=1.3, labelspacing=0.35, columnspacing=1.0)
guardar(fig, "g_validacion")

# ---- 8c. mapas del nivel observado y de la Tmax de julio y agosto
def mapa_simple(ax, gdf, col, cortes, cmap_nombre, titulo, fmt, extend="neither"):
    cmap = plt.get_cmap(cmap_nombre)
    extra = {"neither": 0, "both": 2}[extend]
    colores = ListedColormap([cmap(v) for v in np.linspace(0.15, 0.92, len(cortes) - 1 + extra)])
    norm = BoundaryNorm(cortes, colores.N, extend=extend)
    geo_mun.plot(ax=ax, color=FONDO, edgecolor="white", lw=0.2)
    gdf.plot(ax=ax, column=col, cmap=colores, norm=norm, edgecolor="white", lw=0.2)
    estados.boundary.plot(ax=ax, color=TINTA, lw=0.6)
    ax.set_axis_off()
    ax.set_aspect("equal")
    ax.set_title(titulo, fontsize=8, loc="left")
    sm = plt.cm.ScalarMappable(cmap=colores, norm=norm)
    cb = plt.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.04, pad=0.01, aspect=30, shrink=0.85,
                      extend=extend)
    cb.set_ticks(cortes)
    cb.set_ticklabels([fmt(c) for c in cortes])
    cb.ax.tick_params(labelsize=6.5, length=2)
    cb.outline.set_visible(False)


obs = geo_mun.merge(nm[["nivel"]], left_on="CVEGEO", right_index=True)
tmx = geo_mun[geo_mun.agricola_ha > 0]
fig, axs = plt.subplots(1, 2, figsize=(ANCHO_DOBLE, 3.7))
mapa_simple(axs[0], obs, "nivel", [1.0, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.5], "Blues",
            f"(a) Nivel del SIAP llevado a {M.ANIO_REFERENCIA} (t/ha)", lambda c: f"{c:.2f}")
mapa_simple(axs[1], tmx, "clim_tmax_jul_ago", [23, 23.5, 24, 24.5, 25, 25.5, 26, 27, 28], "Reds",
            "(b) Tmax de julio y agosto (°C)", lambda c: f"{c:g}", extend="both")
for nombre, (dx, dy) in {"Hidalgo": (0, 0), "México": (-40e3, 20e3), "Puebla": (35e3, -60e3),
                         "Tlaxcala": (55e3, 30e3)}.items():
    p = estados.loc[nombre].geometry.representative_point()
    for ax in axs:
        ax.annotate(nombre, (p.x, p.y), (p.x + dx, p.y + dy), fontsize=7, color=TINTA, ha="center",
                    fontweight="bold", arrowprops=None if dx == 0 else dict(arrowstyle="-", color=TINTA, lw=0.4))
fig.subplots_adjust(wspace=0.04)
guardar(fig, "g_mapas_obs")

# ---- 8d. dispersión del nivel contra Tmax y lluvia
fig, axs = plt.subplots(1, 2, figsize=(ANCHO, 2.25), sharey=True)
tam = 4 + 60 * np.sqrt(nm.w / nm.w.max())
for ax, col, xl, esc in ((axs[0], "clim_tmax_jul_ago", "Tmax jul-ago (°C)", 1.0),
                         (axs[1], "clim_prec_may_oct", "Lluvia may-oct (mm)", 1.0)):
    for e in ESTADOS:
        s = nm.estado == e
        ax.scatter(nm.loc[s, col], nm.loc[s, "nivel"], s=tam[s], color=COL_EST[e], alpha=0.75,
                   edgecolor="white", lw=0.3, zorder=3)
    b0, b1_ = recta_pond(nm[col], nm.nivel, nm.w)
    xx = np.linspace(nm[col].min(), nm[col].max(), 10)
    ax.plot(xx, b0 + b1_ * xx, color=TINTA, lw=1.1, zorder=4)
    rp = wcorr(nm[col], nm.nivel, nm.w)
    ax.text(0.97, 0.03, f"r pond. = {rp:.2f}".replace("-", "−"), transform=ax.transAxes, ha="right",
            va="bottom", fontsize=6.5)
    ax.set_xlabel(xl, fontsize=7)
    ax.grid(color=REJILLA, lw=0.4)
    ax.tick_params(labelsize=6.5)
axs[0].set_ylabel(f"Nivel municipal en {M.ANIO_REFERENCIA} (t/ha)")
manos = [Line2D([], [], marker="o", ls="", color=COL_EST[e], ms=4, label=e) for e in ESTADOS]
fig.legend(handles=manos, loc="upper center", ncol=4, fontsize=6.5, bbox_to_anchor=(0.55, 1.06),
           handletextpad=0.1, columnspacing=0.9)
guardar(fig, "g_dispersion")

# ---- 8e. matriz de correlación entre municipios
NV = {"clim_tmax_jul_ago": "Tmax jul-ago", "clim_tmin_may_oct": "Tmin may-oct", "clim_prec_may_oct": "Lluvia may-oct",
      "clim_prec_may_jun": "Lluvia may-jun", "elev_m": "Elevación", "pendiente": "Pendiente",
      "frac_durica": "Fase dúrica", "frac_litica": "Fase lítica", "textura_fina": "Textura fina",
      "nivel": f"Nivel {M.ANIO_REFERENCIA}"}
cm = nm[M.VARIABLES_BLOQUES + ["nivel"]].corr()
assert np.allclose(cm.loc[M.VARIABLES_BLOQUES, M.VARIABLES_BLOQUES].round(3), corr.loc[M.VARIABLES_BLOQUES, M.VARIABLES_BLOQUES], atol=2e-3)
CIFRAS["corr_nivel"] = {NV[c]: r(cm.loc[c, "nivel"]) for c in M.VARIABLES_BLOQUES}
from matplotlib.colors import LinearSegmentedColormap
DIVERG = LinearSegmentedColormap.from_list("div", ["#e34948", "#f0efec", AZUL])
orden_v = ["nivel"] + M.VARIABLES_BLOQUES
cm = cm.loc[orden_v, orden_v]
n = len(orden_v)
fig, ax = plt.subplots(figsize=(ANCHO, 3.0))
for i in range(n):
    for j in range(i):
        v = cm.iloc[i, j]
        ax.add_patch(plt.Rectangle((j, n - 1 - i), 0.96, 0.96, color=DIVERG((v + 1) / 2)))
        ax.text(j + 0.48, n - 1 - i + 0.48, f"{v:.2f}".replace("-", "−").replace("0.", "."), ha="center",
                va="center", fontsize=5.6, color="white" if abs(v) > 0.6 else TINTA,
                fontweight="bold" if abs(v) >= 0.5 else "normal")
ax.set_xlim(0, n - 1)
ax.set_ylim(0, n - 1)
ax.set_xticks(np.arange(n - 1) + 0.48, [NV[c] for c in orden_v[:-1]], rotation=50, ha="right", fontsize=6.3)
ax.set_yticks(np.arange(n - 1) + 0.48, [NV[c] for c in orden_v[1:]][::-1], fontsize=6.3)
ax.tick_params(length=0)
for s_ in ax.spines.values():
    s_.set_visible(False)
ax.set_aspect("equal")
sm = plt.cm.ScalarMappable(cmap=DIVERG, norm=plt.Normalize(-1, 1))
cb = plt.colorbar(sm, ax=ax, fraction=0.035, pad=0.02, shrink=0.7)
cb.set_ticks([-1, -0.5, 0, 0.5, 1])
cb.set_ticklabels(["−1", "−0.5", "0", "0.5", "1"])
cb.ax.tick_params(labelsize=6, length=2)
cb.outline.set_visible(False)
guardar(fig, "g_correlacion")

# ---- 8f. comparación de modelos por escenario (gráfica de puntos)
ESC = [("$B$ = 0 km", dict(esquema="espacial_buffer", B=0, datos="completos"), 0),
       ("$B$ = 50 km", dict(esquema="espacial_buffer", B=50, datos="completos"), 50),
       ("Por distrito", dict(esquema="ddr", B=0, datos="completos"), None),
       ("Sin repetidos, $B$ = 0 km", dict(esquema="espacial_buffer", B=0, datos="sin_repetidos"), None)]
NOMC = {**NOMBRE, "kriging_residuos_simple_a_tmax": "Tmax + kriging res. (final)",
        "kriging_residuos_simple_c_tmax_prec": "Tmax y lluvia + kriging res.",
        "simple_a_tmax": "(a) Tmax jul-ago", "simple_b_elev": "(b) Elevación", "simple_c_tmax_prec": "(c) Tmax y lluvia",
        "simple_d_tmax_prec_durica": "(d) (c) y dúrica", "simple_e_tmax_prec_estado": "(e) (c) y estado"}
ypos, yy_ = {}, 0.0
for m in TABLA[::-1]:
    ypos[m] = yy_
    yy_ += 1 + (0.7 if m in ("ridge_ambiente", "kriging_residuos_simple_a_tmax", "simple_a_tmax") else 0)


def fila_res(m, esquema, B, datos):
    s = niv[(niv.modelo == m) & (niv.esquema == esquema) & (niv.ponderado) & (niv.datos == datos)]
    if esquema == "espacial_buffer":
        s = s[s.buffer_km == B]
    return (float(s.rmse.iloc[0]), float(s.rmse_std.iloc[0])) if len(s) else (np.nan, np.nan)


fig, axs = plt.subplots(1, 4, figsize=(ANCHO_DOBLE, 3.0), sharey=True)
CIFRAS["forest_std"] = {}
for ax, (tit, kw, Bdec) in zip(axs, ESC):
    kr, _ = fila_res("kriging_vecinos", **kw)
    ax.axvline(kr, color=NARANJA, lw=0.8, ls=(0, (3, 2)), zorder=1)
    xmax = 0
    for m in TABLA:
        v, sd = fila_res(m, **kw)
        if np.isnan(v):
            continue
        c = AZUL if m == FINAL else (NARANJA if m == "kriging_vecinos" else GRIS)
        ax.plot([v - sd, v + sd], [ypos[m]] * 2, color=c, lw=1.2, zorder=2)
        ax.scatter(v, ypos[m], s=16, color=c, zorder=3, edgecolor="white", lw=0.4)
        xmax = max(xmax, v + sd)
        if Bdec is not None and m not in ("media_global", "media_estatal", "idw_vecinos", "kriging_vecinos"):
            key = f"rend: B={Bdec} {m} vs kriging_vecinos"
            if key in dec:
                vic = dec[key]["principal"]["victorias"]
                ax.text(v + sd + 0.008, ypos[m], f"{vic}/10", fontsize=5.8, va="center", color=TINTA)
    ax.set_title(tit, fontsize=7.5, loc="left")
    ax.grid(axis="x", color=REJILLA, lw=0.4)
    ax.tick_params(labelsize=6.5)
    lo = min(fila_res(m, **kw)[0] - fila_res(m, **kw)[1] for m in TABLA if not np.isnan(fila_res(m, **kw)[0]))
    ax.set_xlim(np.floor((lo - 0.02) * 20) / 20, xmax + (0.07 if Bdec is not None else 0.03))
    ax.spines["left"].set_visible(False) if ax is not axs[0] else None
    ax.tick_params(axis="y", length=0)
axs[0].set_yticks([ypos[m] for m in TABLA], [NOMC[m] for m in TABLA], fontsize=6.5)
axs[0].set_ylim(-0.7, yy_ - 0.3)
fig.supxlabel("RMSE de nivel ponderado (t/ha), media y desviación entre repeticiones", fontsize=7.5, y=0.0)
fig.subplots_adjust(wspace=0.08)
guardar(fig, "g_modelos")

# ---- 8f'. comparación simple, un solo escenario (B = 50 km), barras ordenadas
NOMS = {"media_global": "Promedio global", "media_estatal": "Promedio estatal",
        "idw_vecinos": "Distancia inversa de vecinos", "kriging_vecinos": "Kriging de vecinos",
        "simple_a_tmax": "Tmax", "simple_b_elev": "Elevación", "simple_c_tmax_prec": "Tmax y lluvia",
        "simple_d_tmax_prec_durica": "Tmax, lluvia y suelo", "simple_e_tmax_prec_estado": "Tmax, lluvia y estado",
        FINAL: "Tmax + kriging (final)", "kriging_residuos_simple_c_tmax_prec": "Tmax y lluvia + kriging",
        "ridge_ambiente": "14 variables (ridge)", "lasso_ambiente": "14 variables (lasso)"}
v50 = {m: fila_res(m, "espacial_buffer", 50, "completos")[0] for m in TABLA}
orden = sorted(v50, key=v50.get, reverse=True)
fig, ax = plt.subplots(figsize=(ANCHO, 2.9))
for i, m in enumerate(orden):
    c = AZUL if m == FINAL else (NARANJA if m == "kriging_vecinos" else GRIS)
    ax.barh(i, v50[m], color=c, height=0.68)
    ax.text(v50[m] + 0.005, i, f"{v50[m]:.2f}", va="center", fontsize=6.3, color=TINTA)
ax.set_yticks(range(len(orden)), [NOMS[m] for m in orden], fontsize=6.5)
ax.set_xlim(0.3, max(v50.values()) + 0.06)
ax.set_xlabel("Error del rendimiento municipal (t/ha), menor es mejor", fontsize=7)
ax.tick_params(axis="y", length=0)
ax.tick_params(axis="x", labelsize=6.5)
ax.grid(axis="x", color=REJILLA, lw=0.4)
ax.set_axisbelow(True)
CIFRAS["modelos_B50"] = {m: r(v, 3) for m, v in v50.items()}
guardar(fig, "g_modelos_simple")

# ---- 8g. comparación emparejada por repetición
CIFRAS["pareada"] = {}
fig, axs = plt.subplots(1, 2, figsize=(ANCHO, 2.1), sharey=False)
for ax, B in zip(axs, (0, 50)):
    a = rmse_reps("kriging_vecinos", B)
    b = rmse_reps(FINAL, B)
    assert abs(a.mean() - tab.loc["kriging_vecinos", f"B{B}_pond"]) < 1e-9 and abs(b.mean() - tab.loc[FINAL, f"B{B}_pond"]) < 1e-9
    gana = b < a
    CIFRAS["pareada"][f"B{B}"] = {"victorias": int(gana.sum()), "kriging_min_max": [r(a.min(), 3), r(a.max(), 3)],
                                  "final_min_max": [r(b.min(), 3), r(b.max(), 3)],
                                  "dif_media": r((b - a).mean(), 3)}
    for ai, bi, g in zip(a, b, gana):
        ax.plot([0, 1], [ai, bi], color=AZUL if g else NARANJA, lw=0.9, alpha=0.85, marker="o", ms=3)
    ax.set_xticks([0, 1], ["Kriging", "Final"], fontsize=7)
    ax.set_xlim(-0.35, 1.35)
    ax.set_title(f"B = {B} km, gana en {int(gana.sum())} de {V.N_REP}", fontsize=7, loc="left")
    ax.grid(axis="y", color=REJILLA, lw=0.4)
    ax.tick_params(axis="y", labelsize=6.5)
axs[0].set_ylabel("RMSE de nivel ponderado (t/ha)", fontsize=7)
fig.subplots_adjust(wspace=0.45)
guardar(fig, "g_pareada")

# ---- 8h. distribución nula de la prueba de permutación (Tmax, B = 50)
PERM = EXP / "permutaciones_figura.csv"
f_tmax = M.catalogo_buffer()["simple_a_tmax"][1]


def _valor_perm(t):
    return float(V.rmse_rep(V.evaluar(f_tmax, t, y, reps, "perm", 50), ctx).mean())


if not PERM.exists():
    from joblib import Parallel, delayed
    rng = np.random.default_rng(SEED)
    tablas = [V._permutar(limpia, M.SIMPLES["simple_a_tmax"][0], rng, "CVEGEO") for _ in range(V.N_PERM)]
    vals = Parallel(n_jobs=V.N_JOBS)(delayed(_valor_perm)(tp) for tp in tablas)
    pd.DataFrame({"permutacion": range(1, V.N_PERM + 1), "rmse_nivel_ponderado": vals}).to_csv(PERM, index=False)
perm = pd.read_csv(PERM).rmse_nivel_ponderado.to_numpy()
real = tab.loc["simple_a_tmax", "B50_pond"]
dperm = dec["rend: B=50 regla simple_a_tmax vs kriging_vecinos"]["permutacion"]["principal"]
assert abs(perm.mean() - dperm["metrica_perm_media"]) < 1e-6, (perm.mean(), dperm["metrica_perm_media"])
CIFRAS["permutacion_fig"] = {"n": len(perm), "real": r(real, 3), "min_perm": r(perm.min(), 3),
                             "media_perm": r(perm.mean(), 3), "max_perm": r(perm.max(), 3),
                             "p": r((1 + (perm <= real).sum()) / (len(perm) + 1)),
                             "kriging": r(tab.loc["kriging_vecinos", "B50_pond"], 3)}
fig, ax = plt.subplots(figsize=(ANCHO, 1.75))
ax.hist(perm, bins=np.arange(0.60, 0.76, 0.005), color=GRIS, edgecolor="white", lw=0.4)
for v, c, txt, ls in ((real, AZUL, f"Tmax real\n{real:.3f}", "-"),
                      (tab.loc["kriging_vecinos", "B50_pond"], NARANJA,
                       f"Kriging\n{tab.loc['kriging_vecinos', 'B50_pond']:.3f}", (0, (3, 2)))):
    ax.axvline(v, color=c, lw=1.4, ls=ls)
    ax.text(v - 0.004, ax.get_ylim()[1] * 0.95, txt, ha="right", va="top", fontsize=6.3, color=TINTA)
ax.text(perm.mean(), ax.get_ylim()[1] * 0.95, f"{len(perm)} permutaciones\nmedia {perm.mean():.3f}",
        ha="center", va="top", fontsize=6.3, color=TINTA)
ax.set_xlabel("RMSE de nivel ponderado con B = 50 km (t/ha)")
ax.set_xlim(0.45, 0.77)
ax.set_ylabel("Permutaciones")
ax.grid(axis="y", color=REJILLA, lw=0.4)
guardar(fig, "g_permutacion")

# ---- 8i. observado contra predicho fuera de muestra, B = 50
fig, axs = plt.subplots(1, 2, figsize=(ANCHO, 1.95), sharey=True, sharex=True)
w_m = ctx.w_mun
for ax, m, c in ((axs[0], "kriging_vecinos", NARANJA), (axs[1], FINAL, AZUL)):
    pr = np.mean([pd.Series(col_oof(m, 50, i)).groupby(limpia.CVEGEO.to_numpy()).mean() for i in range(V.N_REP)],
                 axis=0)
    ob = pd.Series(y).groupby(limpia.CVEGEO.to_numpy()).mean()
    ww = w_m.reindex(ob.index).to_numpy()
    ax.scatter(pr, ob, s=3 + 40 * np.sqrt(ww / ww.max()), color=c, alpha=0.7, edgecolor="white", lw=0.3, zorder=3)
    ax.plot([0.5, 3.5], [0.5, 3.5], color=TINTA, lw=0.7, ls=(0, (3, 2)), zorder=2)
    ax.set_title(f"{'Kriging' if m != FINAL else 'Final'}, RMSE {tab.loc[m, 'B50_pond']:.3f}", fontsize=7, loc="left")
    ax.grid(color=REJILLA, lw=0.4)
    ax.tick_params(labelsize=6.5)
    ax.set_xlabel("Predicho (t/ha)", fontsize=7)
    CIFRAS.setdefault("obs_pred_B50", {})[m] = {"rango_pred": [r(pr.min()), r(pr.max())]}
axs[0].set_ylabel("Observado (t/ha)", fontsize=7)
axs[0].set_xlim(0.6, 3.4)
axs[0].set_ylim(0.6, 3.4)
for ax in axs:
    ax.set_aspect("equal")
guardar(fig, "g_obs_pred")
CIFRAS["obs_pred_B50"]["rango_obs"] = [r(pd.Series(y).groupby(limpia.CVEGEO.to_numpy()).mean().min()),
                                       r(pd.Series(y).groupby(limpia.CVEGEO.to_numpy()).mean().max())]

# ---- 8j. riesgo, confiabilidad de la probabilidad y cobertura por estado
pt = []
for i in range(V.N_REP):
    t = R.cobertura(limpia, y, col_oof(FINAL, 0, i), reps[i], escala=escala)
    pt.append(t)
pt = pd.concat(pt)
assert abs(pt.prob_bajo.astype(float).mean() - CIFRAS["cobertura"]["rend_B0_" + escala]["prob_media"]) < 1e-3
cortes_p = np.linspace(0, 1, 11)
pt["bin"] = pd.cut(pt.prob_bajo.astype(float), cortes_p, include_lowest=True)
cal = pt.groupby("bin", observed=True).agg(p=("prob_bajo", "mean"), o=("bajo", "mean"), n=("bajo", "size"))
CIFRAS["confiabilidad"] = {"bins": [{"p": r(f.p), "obs": r(f.o), "n": int(f.n)} for f in cal.itertuples()]}
fig, axs = plt.subplots(1, 2, figsize=(ANCHO, 1.95), gridspec_kw={"width_ratios": [1, 1.15]})
ax = axs[0]
ax.plot([0, 1], [0, 1], color=TINTA, lw=0.7, ls=(0, (3, 2)))
ax.plot(cal.p, cal.o, color=AZUL, lw=1.2, zorder=2)
ax.scatter(cal.p, cal.o, s=4 + 30 * cal.n / cal.n.max(), color=AZUL, zorder=3, edgecolor="white", lw=0.3)
cb0 = CIFRAS["cobertura"]["rend_B0_" + escala]
ax.text(0.03, 0.97, f"Predicha {cb0['prob_media']:.3f}\nObservada {cb0['frac_obs']:.3f}",
        transform=ax.transAxes, fontsize=5.8, va="top", ha="left")
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.set_aspect("equal")
ax.set_xlabel("Probabilidad predicha", fontsize=7)
ax.set_ylabel("Frecuencia observada", fontsize=7)
ax.set_title("(a) Bajo 2 t/ha, B = 0", fontsize=7, loc="left")
ax.grid(color=REJILLA, lw=0.4)
ax.tick_params(labelsize=6.5)
ax = axs[1]
filas_c = ESTADOS + ["Todos"]
for i, e in enumerate(filas_c):
    yy = len(filas_c) - 1 - i
    v0 = CIFRAS["cobertura"][f"rend_B0_{escala}"]["todos" if e == "Todos" else e]
    v5 = CIFRAS["cobertura"][f"rend_B50_{escala}"]["todos" if e == "Todos" else e]
    ax.plot([v0, v5], [yy + 0.13, yy - 0.13], color=REJILLA, lw=1.2, zorder=1)
    ax.scatter(v0, yy + 0.13, s=16, color=TINTA, zorder=3)
    ax.scatter(v5, yy - 0.13, s=16, facecolor="white", edgecolor=TINTA, lw=0.9, zorder=3)
ax.axvline(0.8, color=GRIS, lw=0.8)
ax.axvline(CAPA.COBERTURA_MINIMA, color=GRIS, lw=0.6, ls=(0, (2, 2)))
ax.set_yticks(range(len(filas_c)), filas_c[::-1], fontsize=6.5)
ax.set_xlim(0.72, 0.92)
ax.set_xticks([0.75, 0.8, 0.85, 0.9])
ax.tick_params(labelsize=6.5)
ax.set_xlabel("Cobertura del p10 a p90", fontsize=7)
ax.set_title("(b) Cobertura", fontsize=7, loc="left")
ax.scatter([], [], s=14, color=TINTA, label="B = 0 km")
ax.scatter([], [], s=14, facecolor="white", edgecolor=TINTA, label="B = 50 km")
ax.legend(loc="upper right", fontsize=5.8, handletextpad=0.1, borderaxespad=0.1)
ax.grid(axis="x", color=REJILLA, lw=0.4)
fig.subplots_adjust(wspace=0.75)
guardar(fig, "g_riesgo")


# Constantes de diseño citadas en el texto (resolución de las fuentes, regla y ejemplo de la ponderación).
CIFRAS["constantes"] = {"dem_resolucion_m": 90, "clima_rejilla_grados": 0.05, "edafologia_escala": 250000,
                        "regla_victorias_min": 7, "regla_p_max": 0.05, "umbral_riesgo_t_ha": 2.0,
                        "cobertura_nominal": 0.8, "variables_ridge_lasso": len(M.FIJAS),
                        "ejemplo_ponderacion_ha": [60, 20000]}
(Path(__file__).parent / "cifras.json").write_text(json.dumps(CIFRAS, ensure_ascii=False, indent=1))
print(json.dumps(CIFRAS, ensure_ascii=False, indent=1))
