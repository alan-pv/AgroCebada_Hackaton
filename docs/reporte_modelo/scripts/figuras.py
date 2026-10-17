"""Figuras del reporte del modelo.

Uso: python figuras.py <repo en feat/modelo-final> <carpeta de figuras> <carpeta de la auditoría>
La tercera carpeta es scripts/datos, con permutacion.csv y auditoria_independiente.json
(generados por indep.py, que reimplementa el modelo sin usar el código del proyecto).
"""
import json
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
REPO, FIG, AUD = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(REPO / "src"))
from agrocebada import cv, modelos  # noqa: E402
from agrocebada.predict import cargar_modelo  # noqa: E402
from agrocebada.train_final import cargar_datos  # noqa: E402
from agrocebada.transformers import MediaPorGrupo  # noqa: E402

AZUL, NARANJA, VERDE, GRIS, TINTA, REJILLA = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984", "#0b0b0b", "#e6e5e1"
COL = {"A": AZUL, "B": NARANJA}
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": GRIS, "axes.labelcolor": TINTA,
                     "xtick.color": TINTA, "ytick.color": TINTA, "legend.frameon": False})
ANCHO = 3.45


def guardar(fig, nombre):
    fig.tight_layout()
    fig.savefig(FIG / f"{nombre}.pdf", dpi=600)  # solo afecta las capas rasterizadas
    plt.close(fig)


def puntos_h(ax, etiquetas, valores, colores, ref=None, ref_txt=None, fmt="{:.3f}", xlim=None):
    """Gráfica de puntos horizontal con el valor escrito a la derecha."""
    y = np.arange(len(etiquetas))
    for i, (v, c) in enumerate(zip(valores, colores)):
        ax.plot([xlim[0] if xlim else 0, v], [i, i], color=REJILLA, lw=1, zorder=1)
        ax.scatter(v, i, s=28, color=c, zorder=3)
        ax.text(v + (xlim[1] - xlim[0]) * 0.015, i, fmt.format(v), va="center", fontsize=7)
    if ref is not None:
        ax.axvline(ref, color=GRIS, ls="--", lw=0.8)
        if ref_txt:
            ax.text(ref, len(etiquetas) - 0.15, ref_txt, fontsize=6.5, color=GRIS, ha="center")
    ax.set_yticks(y, etiquetas)
    if xlim:
        ax.set_xlim(*xlim)
    ax.set_ylim(-0.6, len(etiquetas) + 0.3)


p = pd.read_parquet(REPO / "data/processed/parcelas.parquet")
ent = p[p.conjunto == "ENTRENAMIENTO"]
abl = pd.read_csv(REPO / "outputs/ablaciones_v1.csv").set_index("modelo")
bas = pd.read_csv(REPO / "experimentos/baselines_tabla.csv").set_index("modelo")
BASE_REZ = abl.loc["rezago_k10_r400m_unico_solo_valor", "rmse_A"]
MEDIA_REG = bas.loc["media_regimen", "RMSE_A"]

# 1. Rendimiento por municipio y régimen, con el estado de cada municipio a la izquierda
mun = ent.groupby("municipio").agg(r=("regimen", "first"), m=("rendimiento", "mean"), estado=("estado", "first"))
mun["e"] = mun.estado.map({"Puebla": 0, "Hidalgo": 1, "Tlaxcala": 2})
mun = mun.sort_values(["r", "e", "m"], ascending=[True, True, False])
orden = mun.index.tolist()
corto = {"Nanacamilpa de Mariano Arista": "Nanacamilpa", "Cuautepec de Hinojosa": "Cuautepec"}
fig, ax = plt.subplots(figsize=(ANCHO, 2.1))
rng = np.random.default_rng(0)
for i, m in enumerate(orden):
    d = ent[ent.municipio == m]
    # Rasterizados para que los visores de PDF no dejen líneas blancas entre los puntos semitransparentes
    ax.scatter(d.rendimiento, i + rng.uniform(-0.18, 0.18, len(d)), s=8, alpha=0.7,
               color=COL[d.regimen.iloc[0]], lw=0, rasterized=True)
for g in "AB":
    ax.axvline(ent[ent.regimen == g].rendimiento.mean(), color=COL[g], lw=0.8, ls="--")
ax.set_yticks(range(len(orden)), [f"{corto.get(m, m)} ({(ent.municipio == m).sum()})" for m in orden])
# El estado va en gris a la izquierda del nombre, separado por el ancho del nombre más largo (en puntos)
fig.canvas.draw()
ancho = max(t.get_window_extent().width for t in ax.get_yticklabels()) * 72 / fig.dpi
for i, e in enumerate(mun.estado):
    ax.annotate(e, (0, i), xycoords=ax.get_yaxis_transform(), xytext=(-ancho - 10, 0), textcoords="offset points",
                ha="right", va="center", fontsize=7, color=GRIS)
ax.invert_yaxis()
ax.set_xlabel("Rendimiento declarado (t/ha)")
ax.scatter([], [], color=AZUL, s=10, label="Régimen A (dos decimales)")
ax.scatter([], [], color=NARANJA, s=10, label="Régimen B (redondeado)")
ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, fontsize=6.5, handletextpad=0.2,
          bbox_transform=matplotlib.transforms.blended_transform_factory(fig.transFigure, ax.transAxes))
ax.grid(axis="x", color=REJILLA, lw=0.5)
guardar(fig, "f1_regimenes")

# 2. Bases de comparación, esquemas A y B
filas = [("Media global", "media_global"), ("Media por estado", "media_estado"),
         ("Media por municipio", "media_municipio"), ("10 vecinos más cercanos", "knn_espacial_k10"),
         ("Media por régimen", "media_regimen")]
fig, ax = plt.subplots(figsize=(ANCHO, 1.9))
for i, (n, k) in enumerate(filas):
    a, b = bas.loc[k, "RMSE_A"], bas.loc[k, "RMSE_B"]
    ax.plot([a, b], [i, i], color=REJILLA, lw=2, zorder=1)
    ax.scatter(a, i, s=28, color=AZUL, zorder=3, label="Esquema A" if i == 0 else None)
    ax.scatter(b, i, s=28, facecolor="white", edgecolor=AZUL, lw=1.2, zorder=3,
               label="Esquema B" if i == 0 else None)
    ax.text(max(a, b) + 0.025, i, f"{a:.3f}", va="center", fontsize=7)
ax.set_yticks(range(len(filas)), [n for n, _ in filas])
ax.set_xlabel("RMSE fuera de muestra (t/ha)")
ax.set_xlim(0.4, 1.3)
ax.set_ylim(-0.5, 5.2)
ax.legend(loc="upper center", bbox_to_anchor=(0.55, 1.02), ncol=2, fontsize=6.5, handletextpad=0.2)
guardar(fig, "f2_bases")

# 3. Radio del rezago
radios = [250, 400, 600, 1000]
rm = [abl.loc[f"rezago_k10_r{r}m_unico", "rmse_A"] for r in radios]
xy = ent[["x_m", "y_m"]].to_numpy()
reg = ent.regimen.to_numpy()
d = np.sqrt(((xy[:, None] - xy[None]) ** 2).sum(-1))
np.fill_diagonal(d, np.inf)
d[reg[:, None] != reg[None]] = np.inf
frac = [(d.min(1) <= r).mean() for r in radios]
fig, ax = plt.subplots(figsize=(ANCHO, 1.9))
ax.plot(radios, rm, color=AZUL, marker="o", ms=4, lw=1.5)
for r, v, f in zip(radios, rm, frac):
    ax.text(r, v + (0.0025 if r == 250 else -0.0025), f"{f:.0%} con vecino", ha="center",
            va="bottom" if r == 250 else "top", fontsize=6.5, color=GRIS)
ax.axhline(MEDIA_REG, color=GRIS, ls="--", lw=0.8)
ax.text(800, MEDIA_REG - 0.001, "media por régimen", ha="center", va="top", fontsize=6.5, color=GRIS)
ax.set_xticks(radios, [f"{r} m" for r in radios])
ax.set_xlabel("Radio de búsqueda de vecinos")
ax.set_ylabel("RMSE esquema A (t/ha)")
ax.set_ylim(0.468, 0.515)
guardar(fig, "f3_radio")

# 4. Bloques de variables sobre régimen y rezago
bl = [("Heterogeneidad en la parcela", "+het"), ("Historia 2022 a 2024", "+hist"),
      ("Temperatura de superficie", "+tsup"), ("Clima", "+clima"), ("Satélite 2025 y fenología", "+sat25_fen"),
      ("Labranza", "+lab"), ("Topografía", "+topo"), ("Todos los satelitales", "+todos_los_bloques_sat_k10")]
fig, ax = plt.subplots(figsize=(ANCHO, 2.1))
puntos_h(ax, [n for n, _ in bl][::-1], [abl.loc[k, "rmse_A"] for _, k in bl][::-1],
         [GRIS] * len(bl), ref=BASE_REZ, ref_txt=f"régimen y rezago {BASE_REZ:.3f}", xlim=(0.46, 0.51))
ax.set_xlabel("RMSE esquema A (t/ha)")
guardar(fig, "f4_bloques")

# 5. Algoritmos con régimen y rezago, más ensembles y entrenamiento tolerante al ruido
ens = pd.read_csv(REPO / "outputs/ensembles_v2.csv").set_index("modelo")
al = [("Proceso gaussiano", abl.loc["alg_gp_mejor", "rmse_A"], AZUL),
      ("PG + ridge, promedio", ens.loc["ens_cand_ridge", "rmse_A"], GRIS),
      ("PG con etiqueta B como intervalo", abl.loc["H2_intervalo_B_025_mejor", "rmse_A"], GRIS),
      ("Elastic net", abl.loc["alg_elasticnet_cv_mejor", "rmse_A"], GRIS),
      ("Ridge", BASE_REZ, GRIS),
      ("PLS, 2 componentes", abl.loc["alg_pls_2_mejor", "rmse_A"], GRIS),
      ("LightGBM", abl.loc["alg_lgbm_mejor", "rmse_A"], GRIS),
      ("Bosque aleatorio", abl.loc["alg_rf_mejor", "rmse_A"], GRIS)]
fig, ax = plt.subplots(figsize=(ANCHO, 2.1))
puntos_h(ax, [a[0] for a in al][::-1], [a[1] for a in al][::-1], [a[2] for a in al][::-1],
         ref=MEDIA_REG, ref_txt="media por régimen", xlim=(0.44, 0.51))
ax.set_xlabel("RMSE esquema A (t/ha)")
guardar(fig, "f5_algoritmos")

# Datos para las figuras del modelo final
X, y, X59 = cargar_datos()
gp = cv.evaluate(modelos.candidato(), X, y, "A")
mr = cv.evaluate(MediaPorGrupo("regimen"), X, y, "A")
cfg_r = modelos.configuracion_candidato()
cfg_r = {**cfg_r, "modelo": "ridge"}
rr = cv.evaluate(modelos.desde_config(cfg_r), X, y, "A")

# 6. Observado contra predicho fuera de fold
oof = gp.oof.mean(axis=1)
fig, ax = plt.subplots(figsize=(ANCHO, 2.6))
for g in "AB":
    m = (X.loc[oof.index, "regimen"] == g).to_numpy()
    ax.scatter(y[m], oof[m], s=12, color=COL[g], alpha=0.75, lw=0.4, edgecolor="white", label=f"Régimen {g}")
lim = [1.8, 5.8]
ax.plot(lim, lim, color=GRIS, lw=0.8, ls="--")
ax.set_xlim(lim), ax.set_ylim(lim)
ax.set_aspect("equal")
ax.set_xlabel("Rendimiento declarado (t/ha)")
ax.set_ylabel("Predicción fuera de fold (t/ha)")
ax.legend(loc="upper left")
guardar(fig, "f6_observado_predicho")

# 7. RMSE por repetición
fil = [("Media por régimen", mr.rmse_rep, GRIS), ("Ridge, régimen y rezago", rr.rmse_rep, GRIS),
       ("Proceso gaussiano", gp.rmse_rep, AZUL)]
fig, ax = plt.subplots(figsize=(ANCHO, 1.6))
for i, (n, v, c) in enumerate(fil):
    ax.scatter(v, np.full(len(v), i) + np.linspace(-0.12, 0.12, len(v)), s=9, color=c, alpha=0.6, lw=0)
    ax.plot([v.mean()] * 2, [i - 0.28, i + 0.28], color=TINTA, lw=2)
    ax.text(0.512, i, f"{v.mean():.3f}", va="center", fontsize=7)
ax.axvline(0.490, color=NARANJA, ls="--", lw=1)
ax.text(0.4895, 2.45, "validación anidada", fontsize=6.5, color=NARANJA, ha="right")
ax.set_yticks(range(len(fil)), [n for n, _, _ in fil])
ax.set_xlim(0.435, 0.52)
ax.set_ylim(-0.5, 2.7)
ax.set_xlabel("RMSE por repetición (t/ha)")
guardar(fig, "f7_repeticiones")

# 8. Prueba con etiquetas revueltas dentro del régimen
perm = pd.read_csv(AUD / "permutacion.csv").rmse_permutado
real = json.loads((AUD / "auditoria_independiente.json").read_text())["replica"]["gp"][0]
fig, ax = plt.subplots(figsize=(ANCHO, 1.6))
ax.hist(perm, bins=10, color=GRIS, edgecolor="white")
ax.axvline(real, color=AZUL, lw=2)
ax.set_xlim(0.455, 0.55)
ax.text(real + 0.002, ax.get_ylim()[1] * 0.75, f"etiquetas\nreales\n{real:.3f}", fontsize=7)
ax.set_xlabel("RMSE con etiquetas revueltas (t/ha)")
ax.set_ylabel("Sorteos")
guardar(fig, "f8_permutacion")

# 9. Margen de azar de una calificación con 59 parcelas
fin = cargar_modelo(REPO / "models/modelo_final.joblib")
err = (y - fin.oof.loc[y.index]).to_numpy()
ra = X.loc[y.index, "regimen"].to_numpy()
rng = np.random.default_rng(2026)
sim = []
for _ in range(5000):
    e = np.concatenate([rng.choice(err[ra == "A"], 37), rng.choice(err[ra == "B"], 22)])
    sim.append(np.sqrt(np.mean(e ** 2)))
sim = np.array(sim)
q05, q95 = np.quantile(sim, [0.05, 0.95])
fig, ax = plt.subplots(figsize=(ANCHO, 1.6))
ax.hist(sim, bins=40, color=AZUL, alpha=0.8, edgecolor="white", lw=0.3)
for q in (q05, q95):
    ax.axvline(q, color=TINTA, ls="--", lw=0.8)
ax.text((q05 + q95) / 2, ax.get_ylim()[1] * 0.92, f"90 % entre {q05:.2f} y {q95:.2f}", ha="center", fontsize=7)
ax.set_xlabel("RMSE de 59 parcelas sorteadas (t/ha)")
ax.set_ylabel("Sorteos")
guardar(fig, "f9_margen")

# 10. Cobertura de los intervalos
cob = pd.read_csv(REPO / "outputs/cobertura.csv")
c = cob[cob.metodo == "regimen"].set_index(["tipo", "grupo"])
et = ["Todas", "Régimen A", "Régimen B", "Área Q1 (menor)", "Área Q2", "Área Q3", "Área Q4 (mayor)"]
ks = [("global", "todas"), ("regimen", "A"), ("regimen", "B"), ("cuartil_area", "Q1"), ("cuartil_area", "Q2"),
      ("cuartil_area", "Q3"), ("cuartil_area", "Q4")]
fig, ax = plt.subplots(figsize=(ANCHO, 1.9))
puntos_h(ax, et[::-1], [c.loc[k, "cobertura"] for k in ks][::-1], [AZUL] * len(ks), ref=0.8,
         ref_txt="meta 0.80", fmt="{:.2f}", xlim=(0.7, 0.98))
ax.set_xlabel("Cobertura del intervalo p10 a p90")
guardar(fig, "f10_cobertura")

# 11. Importancia de los índices con y sin régimen
imp = pd.read_csv(REPO / "outputs/importancia_permutacion.csv")
fig, axs = plt.subplots(1, 2, figsize=(ANCHO, 1.9), sharey=False)
for ax, esc, tit in ((axs[0], "regimen_ausente_satelite", "Sin régimen"),
                     (axs[1], "regimen_presente_satelite", "Con régimen y rezago")):
    t = imp[(imp.escenario == esc) & (imp.mascara == "todas") & (imp.tipo == "indice")
            & ~imp.grupo.str.contains(r"\(")].sort_values("importancia_media", ascending=False).head(5)[::-1]
    ax.barh(t.grupo, t.importancia_media, color=AZUL if "aus" in esc else VERDE, height=0.6)
    ax.errorbar(t.importancia_media, t.grupo, xerr=[t.importancia_media - t.p05, t.p95 - t.importancia_media],
                fmt="none", ecolor=TINTA, lw=0.7, capsize=1.5)
    ax.set_title(tit, fontsize=7.5)
    ax.tick_params(axis="y", labelsize=7)
fig.supxlabel("Aumento del RMSE al revolver el índice (t/ha)", fontsize=7.5)
guardar(fig, "f11_indices")

# 12. Las 59 predicciones sobre el mapa
pf = pd.read_csv(REPO / "outputs/predicciones_finales.csv").merge(p[["ID_POLIGONO", "lon", "lat", "regimen"]])
fig, ax = plt.subplots(figsize=(ANCHO, 2.6))
vmin, vmax = 2.0, 5.6
ax.scatter(ent.lon, ent.lat, c=ent.rendimiento, cmap="viridis", vmin=vmin, vmax=vmax, s=9, marker="s", lw=0, alpha=0.8)
sc = ax.scatter(pf.lon, pf.lat, c=pf.RENDIMIENTO_T_HA, cmap="viridis", vmin=vmin, vmax=vmax, s=22,
                edgecolor=TINTA, lw=0.7)
cb = fig.colorbar(sc, ax=ax, shrink=0.8)
cb.set_label("t/ha")
ax.set_xticks([]), ax.set_yticks([])
ax.set_aspect("equal")
ax.spines[["left", "bottom"]].set_visible(False)
ax.scatter([], [], marker="s", s=9, color=GRIS, label="Entrenamiento, observado")
ax.scatter([], [], s=22, facecolor="white", edgecolor=TINTA, label="Predicción, 59 parcelas")
ax.legend(loc="lower right", fontsize=6.5)
guardar(fig, "f12_mapa")

res = {"gp": gp.rmse, "gp_regA": gp.por_regimen["A"]["rmse"], "gp_regB": gp.por_regimen["B"]["rmse"],
       "ridge": rr.rmse, "media_reg": mr.rmse, "margen": [float(sim.mean()), float(sim.std()), float(q05), float(q95)],
       "victorias_gp_ridge": int((gp.rmse_rep < rr.rmse_rep).sum()), "victorias_gp_mr": int((gp.rmse_rep < mr.rmse_rep).sum()),
       "frac_vecino": dict(zip(radios, frac)), "pred_ancho": float((pf.p90 - pf.p10).mean())}
print(json.dumps(res, indent=1, default=float))
