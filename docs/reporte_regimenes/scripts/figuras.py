"""Figuras y cifras del reporte de regímenes.

Uso, desde la raíz del repositorio:
    uv run python docs/reporte_regimenes/scripts/figuras.py

Lee data/processed (parcelas y variables) y data/externos (SIAP e INEGI). Escribe las figuras en
docs/reporte_regimenes/figuras y todas las cifras que cita el texto en docs/reporte_regimenes/scripts/cifras.json.
"""
import html
import json
import math
import re
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parents[3]
FIG = RAIZ / "docs/reporte_regimenes/figuras"
EXT = RAIZ / "data/externos"
CIFRAS = {}

AZUL, NARANJA, VERDE, GRIS, TINTA, REJILLA = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984", "#0b0b0b", "#e6e5e1"
COL = {"A": AZUL, "B": NARANJA}
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": GRIS, "axes.labelcolor": TINTA,
                     "xtick.color": TINTA, "ytick.color": TINTA, "legend.frameon": False})
ANCHO = 3.45
CORTO = {"Nanacamilpa de Mariano Arista": "Nanacamilpa", "Cuautepec de Hinojosa": "Cuautepec",
         "Emiliano Zapata": "E. Zapata"}
ESTADO = {"Chignahuapan": "Puebla", "Almoloya": "Hidalgo", "Cuautepec de Hinojosa": "Hidalgo",
          "Tepeapulco": "Hidalgo", "Singuilucan": "Hidalgo", "Apan": "Hidalgo", "Emiliano Zapata": "Hidalgo",
          "Calpulalpan": "Tlaxcala", "Nanacamilpa de Mariano Arista": "Tlaxcala"}
POPO = (19.023, -98.622)  # cráter del Popocatépetl, lat y lon


def guardar(fig, nombre):
    fig.tight_layout()
    fig.savefig(FIG / f"{nombre}.pdf")
    plt.close(fig)


def r(x, n=2):
    return round(float(x), n)


# ---------------------------------------------------------------- datos
p = pd.read_parquet(RAIZ / "data/processed/parcelas.parquet")
f = pd.read_parquet(RAIZ / "data/processed/features.parquet")
d = f.merge(p[["ID_POLIGONO", "rendimiento"]], on="ID_POLIGONO")
t = d[d.rendimiento.notna()].reset_index(drop=True)
y, mun = t.rendimiento.to_numpy(), t.municipio.to_numpy()
clima = [c for c in d if c.startswith("clima_")]
topo = [c for c in d if c.startswith("topo_")]
sat = [c for c in d if c.startswith(("sat25_", "hist_", "het_", "lab_", "tsup_"))]
CIFRAS["brecha"] = r(t[t.regimen == "A"].rendimiento.mean() - t[t.regimen == "B"].rendimiento.mean())
CIFRAS["media_A"], CIFRAS["media_B"] = r(t[t.regimen == "A"].rendimiento.mean()), r(t[t.regimen == "B"].rendimiento.mean())


# ---------------------------------------------------------------- 1. dejar fuera un municipio
def lomo(cols, modelo=None, filtro=None):
    idx = np.arange(len(t)) if filtro is None else np.where(filtro)[0]
    yy, mm, pred = y[idx], mun[idx], np.empty(len(idx))
    for m in np.unique(mm):
        te = mm == m
        if not cols:
            pred[te] = yy[~te].mean()
            continue
        pipe = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), modelo())
        X = t.loc[idx, cols]
        pipe.fit(X[~te], yy[~te])
        pred[te] = pipe.predict(X[te])
    return float(np.sqrt(np.mean((pred - yy) ** 2)))


rf = lambda: RandomForestRegressor(300, max_depth=4, min_samples_leaf=5, random_state=0, n_jobs=-1)
rg = lambda: RidgeCV(alphas=np.logspace(-2, 4, 30))
lomo_tab = {"Media global": lomo([]),
            "Topografía": min(lomo(topo, rg), lomo(topo, rf)),
            "Satélite": min(lomo(sat, rg), lomo(sat, rf)),
            "Clima y topografía": min(lomo(clima + topo, rg), lomo(clima + topo, rf)),
            "Clima": min(lomo(clima, rg), lomo(clima, rf))}
reg = t.regimen.to_numpy()
pred_reg = np.array([y[(mun != m) & (reg == g)].mean() for m, g in zip(mun, reg)])
lomo_tab["Régimen conocido"] = float(np.sqrt(np.mean((pred_reg - y) ** 2)))
CIFRAS["lomo"] = {k: r(v, 3) for k, v in lomo_tab.items()}
CIFRAS["lomo_dentro"] = {g: {"media": r(lomo([], None, reg == g), 3),
                             "clima_topo": r(lomo(clima + topo, rg, reg == g), 3)} for g in "AB"}

fig, ax = plt.subplots(figsize=(ANCHO, 1.75))
nombres = list(lomo_tab)
for i, k in enumerate(nombres):
    v = lomo_tab[k]
    c = AZUL if k == "Régimen conocido" else (GRIS if k == "Media global" else NARANJA)
    ax.plot([0, v], [i, i], color=REJILLA, lw=1, zorder=1)
    ax.scatter(v, i, s=28, color=c, zorder=3)
    ax.text(v + 0.02, i, f"{v:.2f}", va="center", fontsize=7)
ax.set_yticks(range(len(nombres)), nombres)
ax.set_xlim(0.3, 1.45)
ax.set_xlabel("RMSE dejando fuera el municipio (t/ha)")
guardar(fig, "r1_generalizacion")

# ---------------------------------------------------------------- 2. clima: diferencia entre regímenes y efecto dentro
A, B = t[t.regimen == "A"], t[t.regimen == "B"]
filas = []
for c in clima + topo:
    sd = t[c].std()
    if not sd or np.isnan(sd):
        continue
    dz = (A[c].mean() - B[c].mean()) / sd
    u = t[[c, "rendimiento", "regimen"]].dropna()
    X = np.column_stack([np.ones(len(u)), (u[c] - u[c].mean()) / sd, (u.regimen == "B").astype(float)])
    b = np.linalg.lstsq(X, u.rendimiento.to_numpy(), rcond=None)[0]
    e = u.rendimiento.to_numpy() - X @ b
    se = np.sqrt(e @ e / (len(u) - 3) * np.linalg.inv(X.T @ X)[1, 1])
    z = abs(b[1] / se)
    pval = 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))
    filas.append((c, dz, b[1], pval, dz * b[1]))
cl = pd.DataFrame(filas, columns=["var", "dz", "pend", "p", "brecha"])
cl = cl.reindex(cl.dz.abs().sort_values(ascending=False).index)
CIFRAS["clima_top"] = [{"var": v.var, "dz": r(v.dz), "pend": r(v.pend, 3), "p": r(v.p), "brecha": r(v.brecha)}
                       for v in cl.head(4).itertuples()]
CIFRAS["clima_brecha_max"] = r(cl.brecha.max())
CIFRAS["elevacion"] = {g: r(t[t.regimen == g].topo_elevacion.mean(), 0) for g in "AB"}

# ---------------------------------------------------------------- 3. experimento natural de Singuilucan
d["zona"] = np.where(d.regimen == "A", "A", np.where(d.municipio == "Singuilucan", "B norte", "B sur"))
d["fin_doy"] = d.fen_sos_doy + d.sat25_planet_ndvi_duracion
vz = ["rendimiento", "clima_tmin_media_may_sep", "clima_amplitud_termica", "clima_prec_total_may_oct",
      "sat25_planet_ndvi_max", "sat25_planet_ndvi_auc_pico", "fen_sos_doy", "fin_doy", "sat25_planet_ndvi_duracion"]
CIFRAS["zonas"] = d.groupby("zona")[vz].median().round(2).to_dict(orient="index")
xy = t[["x_m", "y_m"]].to_numpy()
D = np.sqrt(((xy[:, None] - xy[None]) ** 2).sum(-1)) / 1000
ia = np.where((t.municipio == "Cuautepec de Hinojosa").to_numpy())[0]
ib = np.where((t.municipio == "Singuilucan").to_numpy())[0]
CIFRAS["dist_cuautepec_singuilucan_km"] = r(D[np.ix_(ia, ib)].min(), 1)

# ---------------------------------------------------------------- 4. mapa
g = t.groupby(["municipio", "regimen"]).agg(lon=("lon", "mean"), lat=("lat", "mean"), y=("rendimiento", "mean"),
                                             n=("rendimiento", "size")).reset_index()
la1, lo1 = np.radians(POPO)
la2, lo2 = np.radians(g.lat), np.radians(g.lon)
g["km_popo"] = 6371 * 2 * np.arcsin(np.sqrt(np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2)
                                            * np.sin((lo2 - lo1) / 2) ** 2))
CIFRAS["municipios"] = {m.municipio: {"regimen": m.regimen, "n": int(m.n), "reto": r(m.y), "km_popo": r(m.km_popo, 0)}
                        for m in g.itertuples()}

fig, ax = plt.subplots(figsize=(ANCHO, 3.0))
for grp in "AB":
    s = d[d.regimen == grp]
    ax.scatter(s.lon, s.lat, s=6, color=COL[grp], alpha=0.75, lw=0,
               label=f"Régimen {grp}, media {CIFRAS['media_' + grp]:.2f} t/ha")
desp = {"Chignahuapan": (0.04, -0.045), "Almoloya": (0.04, -0.02), "Cuautepec de Hinojosa": (0.04, 0.03),
        "Tepeapulco": (-0.04, -0.03), "Singuilucan": (-0.05, -0.01), "Apan": (0.06, 0.03),
        "Emiliano Zapata": (-0.05, 0.03), "Calpulalpan": (-0.06, -0.01),
        "Nanacamilpa de Mariano Arista": (0.06, -0.035)}
for m in g.itertuples():
    dx, dy = desp[m.municipio]
    ax.annotate(f"{CORTO.get(m.municipio, m.municipio)}\n{m.y:.2f}", (m.lon, m.lat), (m.lon + dx, m.lat + dy),
                fontsize=6.3, ha="left" if dx > 0 else "right", va="center", color=COL[m.regimen],
                arrowprops=dict(arrowstyle="-", color=GRIS, lw=0.4))
ax.text(-98.79, 19.415, "↓ Popocatépetl\n   60 a 107 km al sur", fontsize=6.3, color=GRIS, ha="left", va="bottom")
ax.set_xlim(-98.8, -98.05)
ax.set_ylim(19.40, 20.05)
ax.set_aspect(1 / np.cos(np.radians(19.75)))
ax.set_xlabel("Longitud")
ax.set_ylabel("Latitud")
ax.legend(loc="lower right", bbox_to_anchor=(1.03, -0.02), fontsize=6.0, handletextpad=0.1, markerscale=2)
ax.grid(color=REJILLA, lw=0.4)
guardar(fig, "r2_mapa")

# ---------------------------------------------------------------- 5. fenología: emergencia contra rendimiento
CIFRAS["sos_mediana"] = {grp: r(t[t.regimen == grp].fen_sos_doy.median(), 0) for grp in "AB"}
CIFRAS["fin_mediana"] = {grp: r(t.assign(f=t.fen_sos_doy + t.sat25_planet_ndvi_duracion)[t.regimen == grp].f.median(), 0)
                         for grp in "AB"}
temp = t.assign(temprana=t.fen_sos_doy <= 158)
CIFRAS["siembra"] = {f"{k[0]}_{'temprana' if k[1] else 'tardia'}": {"n": int(v["count"]), "media": r(v["mean"])}
                     for k, v in temp.groupby(["regimen", "temprana"]).rendimiento.agg(["count", "mean"]).iterrows()}
CIFRAS["corr_fen_dentro"] = {grp: {c: r(t[t.regimen == grp][[c, "rendimiento"]].corr().iloc[0, 1])
                                   for c in ["fen_sos_doy", "sat25_planet_ndvi_duracion", "sat25_planet_ndvi_max"]}
                             for grp in "AB"}
fig, ax = plt.subplots(figsize=(ANCHO, 2.1))
for grp in "AB":
    s = t[t.regimen == grp]
    ax.scatter(s.fen_sos_doy, s.rendimiento, s=9, color=COL[grp], alpha=0.75, lw=0, label=f"Régimen {grp}")
    ax.axhline(s.rendimiento.mean(), color=COL[grp], ls="--", lw=0.8)
ax.axvline(158, color=GRIS, lw=0.6, ls=":")
ax.text(157, 5.7, "7 jun", fontsize=6.3, color=GRIS, ha="right")
ticks = [140, 152, 162, 172, 182, 192]
ax.set_xticks(ticks, ["20 may", "1 jun", "11 jun", "21 jun", "1 jul", "11 jul"])
ax.set_xlabel("Emergencia estimada con Planet (2025)")
ax.set_ylabel("Rendimiento (t/ha)")
ax.set_ylim(1.8, 5.9)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.13), fontsize=6.5, ncol=2, handletextpad=0.1)
guardar(fig, "r3_fenologia")

# ---------------------------------------------------------------- 6. suelo
par = gpd.read_file(RAIZ / "data/processed/parcelas.gpkg").to_crs(32614)[["ID_POLIGONO", "geometry"]]


def suelo_dominante(ruta, cols):
    s = gpd.read_file(ruta, encoding="latin1").set_crs(32614)
    x = gpd.overlay(par, s[cols + ["geometry"]], how="intersection")
    x["a"] = x.area
    return x.sort_values("a", ascending=False).drop_duplicates("ID_POLIGONO")[["ID_POLIGONO"] + cols]


s2 = suelo_dominante(EXT / "inegi_edafologia/serie2/E1402e.shp", ["CLAVE_WRB", "GRUPO1"])
s1 = suelo_dominante(EXT / "inegi_edafologia/serie1/e1402e.shp", ["NOM_SUE1", "FAS_FISCA"])
ts = t.merge(s2, on="ID_POLIGONO", how="left").merge(s1, on="ID_POLIGONO", how="left")
CIFRAS["suelo_cubiertas"] = int(ts.GRUPO1.notna().sum())
grupos = {"PH": "Phaeozem", "UM": "Umbrisol", "PL": "Planosol", "VR": "Vertisol", "LP": "Leptosol"}
CIFRAS["suelo_grupo"] = {grupos[k]: {grp: {"n": int(v["count"]), "media": r(v["mean"])}
                                     for grp, v in s.groupby("regimen").rendimiento.agg(["count", "mean"]).iterrows()}
                         for k, s in ts.groupby("GRUPO1")}
unid = ts.groupby(["CLAVE_WRB", "regimen"]).rendimiento.agg(["count", "mean"]).unstack()
compart = unid.dropna().index.tolist()
CIFRAS["suelo_unidades_compartidas"] = {
    u: {grp: {"n": int(unid.loc[u, ("count", grp)]), "media": r(unid.loc[u, ("mean", grp)]),
              "municipios": sorted(ts[(ts.CLAVE_WRB == u) & (ts.regimen == grp)].municipio.unique().tolist())}
        for grp in "AB"} for u in compart}
CIFRAS["fase_dura"] = {str(k): {grp: {"n": int(v["count"]), "media": r(v["mean"])}
                                for grp, v in s.groupby("regimen").rendimiento.agg(["count", "mean"]).iterrows()}
                       for k, s in ts.groupby("FAS_FISCA")}

# Panel (a): distinto suelo, mismo régimen. Panel (b): mismo suelo, distinto régimen.
orden_a = ["LP", "PL", "PH", "VR", "UM"]
filas_a = [(grp, k) for grp in "AB" for k in orden_a if ((ts.regimen == grp) & (ts.GRUPO1 == k)).any()]
filas_b = [(f"{grupos['PH']}, todas", ts.GRUPO1 == "PH"), (f"{grupos['UM']}, todas", ts.GRUPO1 == "UM")]
filas_b += [(u.split("/")[0], ts.CLAVE_WRB == u) for u in compart]
filas_b += [("Tepetate (fase dúrica)", ts.FAS_FISCA == "Dúrica"), ("Sin fase física", ts.FAS_FISCA == "NINGUNO")]
CIFRAS["suelo_brecha_mismo_suelo"] = {}
fig, (a1, a2) = plt.subplots(2, 1, figsize=(ANCHO, 3.3), gridspec_kw={"height_ratios": [len(filas_a), len(filas_b)]})
for i, (grp, k) in enumerate(filas_a[::-1]):
    s = ts[(ts.regimen == grp) & (ts.GRUPO1 == k)]
    a1.plot([1.9, s.rendimiento.mean()], [i, i], color=REJILLA, lw=1, zorder=1)
    a1.scatter(s.rendimiento.mean(), i, s=26, color=COL[grp], zorder=3)
    a1.text(s.rendimiento.mean() + 0.07, i, f"{s.rendimiento.mean():.2f} ({len(s)})", va="center", fontsize=6.3)
a1.set_yticks(range(len(filas_a)), [f"{grupos[k]} ({grp})" for grp, k in filas_a[::-1]], fontsize=7)
a1.set_xlim(1.9, 5.6)
a1.set_title("(a) Distinto suelo, mismo régimen", fontsize=7.5, loc="left")
for i, (nom, msk) in enumerate(filas_b[::-1]):
    s = ts[msk]
    ma, mb = s[s.regimen == "A"].rendimiento.mean(), s[s.regimen == "B"].rendimiento.mean()
    na, nb = (s.regimen == "A").sum(), (s.regimen == "B").sum()
    CIFRAS["suelo_brecha_mismo_suelo"][nom] = r(ma - mb)
    a2.plot([mb, ma], [i, i], color=REJILLA, lw=2, zorder=1)
    a2.scatter(ma, i, s=26, color=AZUL, zorder=3)
    a2.scatter(mb, i, s=26, color=NARANJA, zorder=3)
    a2.text((ma + mb) / 2, i + 0.18, f"brecha {ma - mb:.2f}", ha="center", va="bottom", fontsize=6, color=GRIS)
    a2.text(ma + 0.07, i, f"{ma:.2f} ({na})", va="center", fontsize=6.3)
    a2.text(mb - 0.07, i, f"({nb}) {mb:.2f}", va="center", ha="right", fontsize=6.3)
a2.set_yticks(range(len(filas_b)), [n for n, _ in filas_b][::-1], fontsize=7)
a2.set_xlim(1.9, 5.6)
a2.set_ylim(-0.5, len(filas_b) - 0.2)
a2.set_title("(b) Mismo suelo, distinto régimen", fontsize=7.5, loc="left")
a2.set_xlabel("Rendimiento medio (t/ha)")
a1.scatter([], [], s=26, color=AZUL, label="Régimen A")
a1.scatter([], [], s=26, color=NARANJA, label="Régimen B")
a1.legend(loc="lower right", fontsize=6.3, handletextpad=0.1)
guardar(fig, "r4_suelo")

# ---------------------------------------------------------------- 7. volcán: distancia contra rendimiento
fig, ax = plt.subplots(figsize=(ANCHO, 1.9))
for m in g.itertuples():
    ax.scatter(m.km_popo, m.y, s=10 + 2.2 * m.n, color=COL[m.regimen], alpha=0.8, lw=0)
    dx, dy, ha = {"Singuilucan": (0, -0.22, "center"), "Cuautepec de Hinojosa": (1, 0.2, "center"),
                  "Tepeapulco": (-1.5, -0.3, "center"), "Chignahuapan": (3, -0.36, "left"),
                  "Almoloya": (-1, 0.2, "center"), "Nanacamilpa de Mariano Arista": (0, -0.2, "center"),
                  "Calpulalpan": (0, 0.22, "center"), "Apan": (0, -0.22, "center"),
                  "Emiliano Zapata": (0, 0.2, "center")}[m.municipio]
    ax.text(m.km_popo + dx, m.y + dy, CORTO.get(m.municipio, m.municipio), fontsize=6.2, ha=ha, va="center",
            color=COL[m.regimen])
ax.set_xlabel("Distancia al cráter del Popocatépetl (km)")
ax.set_ylabel("Rendimiento medio (t/ha)")
ax.set_xlim(52, 114)
ax.set_ylim(2.1, 5.0)
ax.grid(color=REJILLA, lw=0.4)
guardar(fig, "r5_volcan")

# ---------------------------------------------------------------- 8. SIAP contra el reto
filas = []
for ruta in sorted((EXT / "siap").glob("*.xls")):
    crudo = ruta.read_text(encoding="latin1")
    celdas = [[html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
              for tr in re.findall(r"<tr>(.*?)</tr>", crudo, re.S)]
    for c in celdas:
        if len(c) == 10 and c[0].isdigit():
            filas.append({"anio": int(ruta.stem.split("_")[1]), "estado": c[1], "municipio": c[2],
                          "sembrada_ha": float(c[3].replace(",", "")), "rendimiento": float(c[7].replace(",", ""))})
siap = pd.DataFrame(filas)
siap.to_csv(EXT / "siap/cebada_temporal_pv_municipal_2023_2025.csv", index=False)
CIFRAS["siap_estatal"] = {f"{e}_{a}": r(v) for (e, a), v in siap.assign(prod=siap.sembrada_ha * siap.rendimiento)
                          .groupby(["estado", "anio"]).apply(lambda s: s["prod"].sum() / s.sembrada_ha.sum()).items()}
sp = siap.pivot_table(index=["estado", "municipio"], columns="anio", values="rendimiento")
g["estado"] = g.municipio.map(ESTADO)
for a in (2023, 2024, 2025):
    g[f"siap_{a}"] = [sp.loc[(e, m), a] for e, m in zip(g.estado, g.municipio)]
g["siap_media"] = g[["siap_2023", "siap_2024", "siap_2025"]].mean(axis=1)
CIFRAS["siap_municipios"] = {m.municipio: {"reto": r(m.y), "s2023": r(m.siap_2023), "s2024": r(m.siap_2024),
                                           "s2025": r(m.siap_2025), "dif_2025": r(m.y - m.siap_2025)}
                             for m in g.itertuples()}
CIFRAS["siap_por_regimen"] = g.groupby("regimen")[["y", "siap_2023", "siap_2024", "siap_2025", "siap_media"]] \
    .mean().round(2).to_dict(orient="index")
CIFRAS["corr_reto_siap"] = {"2025": r(np.corrcoef(g.y, g.siap_2025)[0, 1]),
                            "media": r(np.corrcoef(g.y, g.siap_media)[0, 1])}
ts2 = t.merge(g[["municipio", "siap_2025"]], on="municipio")
pr = pd.Series(index=ts2.index, dtype=float)
for m in ts2.municipio.unique():
    a, b = ts2[ts2.municipio != m], ts2[ts2.municipio == m]
    pr[b.index] = np.polyval(np.polyfit(a.siap_2025, a.rendimiento, 1), b.siap_2025)
CIFRAS["lomo_siap_2025"] = r(np.sqrt(((pr - ts2.rendimiento) ** 2).mean()), 3)

orden = g.sort_values(["regimen", "y"], ascending=[True, False])
fig, ax = plt.subplots(figsize=(ANCHO, 2.9))
for i, m in enumerate(orden.itertuples()):
    lo, hi = min(m.siap_2023, m.siap_2024, m.siap_2025), max(m.siap_2023, m.siap_2024, m.siap_2025)
    ax.plot([lo, hi], [i, i], color=GRIS, lw=2.2, alpha=0.45, solid_capstyle="round", zorder=1)
    ax.scatter(m.siap_2025, i, s=24, marker="D", facecolor="white", edgecolor=TINTA, lw=0.9, zorder=3)
    ax.scatter(m.y, i, s=10 + 1.5 * m.n, color=COL[m.regimen], zorder=4)
ax.scatter([], [], s=24, color=GRIS, label="Reto, media del municipio")
ax.scatter([], [], s=24, marker="D", facecolor="white", edgecolor=TINTA, label="SIAP 2025")
ax.plot([], [], color=GRIS, lw=2.2, alpha=0.45, label="SIAP, rango 2023 a 2025")
ax.axhline(3.5, color=REJILLA, lw=0.8)
ax.set_yticks(range(len(orden)), [f"{CORTO.get(m, m)} ({ESTADO[m][:3]}.)" for m in orden.municipio])
ax.text(5.05, 1.5, "Régimen A", color=AZUL, fontsize=7, ha="right")
ax.text(5.05, 6.0, "Régimen B", color=NARANJA, fontsize=7, ha="right")
ax.invert_yaxis()
ax.set_xlim(1.6, 5.1)
ax.set_xlabel("Rendimiento (t/ha)")
ax.legend(loc="lower left", bbox_to_anchor=(-0.45, 1.0), ncol=2, fontsize=6.2, handletextpad=0.2, columnspacing=0.8)
ax.grid(axis="x", color=REJILLA, lw=0.4)
guardar(fig, "r6_siap")

(Path(__file__).parent / "cifras.json").write_text(json.dumps(CIFRAS, ensure_ascii=False, indent=1))
print(json.dumps(CIFRAS, ensure_ascii=False, indent=1))
