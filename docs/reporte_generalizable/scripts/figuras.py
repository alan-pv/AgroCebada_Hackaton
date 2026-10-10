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
ax.text(2025.4, anual.rend.iloc[-1] + 0.12, "Sobre cosechada", color=AZUL, fontsize=6.5, va="center")
ax.text(2025.4, anual.rend_sembrada.iloc[-1] - 0.12, "Sobre sembrada", color=NARANJA, fontsize=6.5, va="center")
for a, (xt, yt) in {2009: (2005.6, 0.55), 2011: (2014.2, 0.45)}.items():
    ax.annotate(f"{a}, siniestro {100 * anual.siniestro[a]:.0f} %", (a, anual.rend_sembrada[a]), (xt, yt),
                fontsize=6, color=GRIS, ha="center", va="center",
                arrowprops=dict(arrowstyle="-", color=GRIS, lw=0.5, shrinkA=1, shrinkB=2))
ax.set_xlim(2002.5, 2029.5)
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
    ax.text(Bs[-1] + 2, curva[m][-1] + desplaza[m], etiqueta[m], color=c, fontsize=6.5, va="center")
for b in (0, 50):
    ax.axvline(b, color=REJILLA, lw=0.8, zorder=0)
ax.text(50, 0.255, " 50 km, sin datos cerca", fontsize=6, color=GRIS, ha="left", va="bottom")
ax.set_xlim(-3, 112)
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
axs[0].text(-0.33, 3.62, "condicional", color=AZUL, fontsize=6.3, va="center")
axs[0].text(-0.33, 3.32, "marginal", color=NARANJA, fontsize=6.3, va="center")
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
ax.text(5.17, n_a - 0.56, "Régimen A ↑", color=AZUL, fontsize=6.5, ha="right", va="bottom")
ax.text(5.17, n_a - 0.44, "Régimen B ↓", color=NARANJA, fontsize=6.5, ha="right", va="top")
ax.invert_yaxis()
ax.set_xlim(1.4, 5.2)
ax.set_xlabel("Rendimiento (t/ha)")
ax.legend(loc="lower left", bbox_to_anchor=(-0.42, 1.0), ncol=2, fontsize=6.2, handletextpad=0.2, columnspacing=0.8)
ax.grid(axis="x", color=REJILLA, lw=0.4)
guardar(fig, "g6_reto")

# Constantes de diseño citadas en el texto (resolución de las fuentes, regla y ejemplo de la ponderación).
CIFRAS["constantes"] = {"dem_resolucion_m": 90, "clima_rejilla_grados": 0.05, "edafologia_escala": 250000,
                        "regla_victorias_min": 7, "regla_p_max": 0.05, "umbral_riesgo_t_ha": 2.0,
                        "cobertura_nominal": 0.8, "variables_ridge_lasso": len(M.FIJAS),
                        "ejemplo_ponderacion_ha": [60, 20000]}
(Path(__file__).parent / "cifras.json").write_text(json.dumps(CIFRAS, ensure_ascii=False, indent=1))
print(json.dumps(CIFRAS, ensure_ascii=False, indent=1))
