"""Genera el mapa de rendimiento esperado del anexo (ancho de una columna).

Reproduce el estilo de los mapas de g5_mapas en figuras.py, sin correr todo el script. Solo dibuja Hidalgo, Puebla y
Tlaxcala, los estados del reto. El modelo municipal se entrena también con el Estado de México, del mismo altiplano.

Qué se dibuja. El modelo final solo usa la Tmax de julio y agosto, así que se predice en todo municipio cuya Tmax cae
dentro del rango de los municipios con SIAP (ahí interpola), aunque su lluvia, elevación o suelo queden fuera. La
predicción se calcula aquí con el modelo final, sin el recorte por rango ambiental de outputs/generalizable_municipios.
En los municipios más cálidos que cualquiera con SIAP la recta extrapola y llega a valores negativos. Se recortan en 0
y todos caen en la primera clase, de 0 a 1.25 t/ha, sin marca de confianza.

Uso: uv run python docs/reporte_generalizable/scripts/mapas_separados.py
Salida: reporte/entrega/figuras/g5_mapa_a.pdf y docs/reporte_generalizable/scripts/mapa_clases.json
"""
import json
import sys
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

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "src"))
warnings.filterwarnings("ignore")
from agrocebada.config import EXPERIMENTOS  # noqa: E402
from agrocebada.generalizable import SALIDA as TABLAS  # noqa: E402
from agrocebada.generalizable import modelos as M  # noqa: E402

OUT = RAIZ / "outputs"
DEST = RAIZ / "reporte/entrega/figuras"
GRIS, TINTA, NARANJA = "#8a8984", "#0b0b0b", "#c2410c"
ESTADOS_MAPA = ["Hidalgo", "Puebla", "Tlaxcala"]
CONFIANZA_MEDIA_KM = 25.0  # igual que scripts/generalizable_capa.py
# La primera clase, de 0 a 1.25, junta los municipios de menor rendimiento, entre ellos los más cálidos
CORTES = [0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25]
plt.rcParams.update({"font.family": "serif", "font.size": 8, "hatch.linewidth": 0.5})

# Predicción del modelo final en todos los municipios, sin recorte
nombre = json.loads((EXPERIMENTOS / "generalizable/decisiones.json").read_text())["rend: modelo_final"]["modelo"]
mun = pd.read_parquet(TABLAS / "municipios.parquet")
d = M.tabla_modelado("rend")
pred = M.modelo(nombre)(d, d.y.to_numpy(), mun.assign(anio=M.ANIO_REFERENCIA))
tabla = mun[["CVEGEO", "clim_tmax_jul_ago"]].assign(pred=pred)
tmax_lo, tmax_hi = mun.loc[mun.CVEGEO.isin(d.CVEGEO), "clim_tmax_jul_ago"].agg(["min", "max"])

geo = gpd.read_file(OUT / "generalizable_municipios.gpkg", layer="municipios").to_crs("EPSG:6372")
geo = geo[geo["estado"].isin(ESTADOS_MAPA)].merge(tabla, on="CVEGEO")
calido = geo["clim_tmax_jul_ago"] > tmax_hi
geo["valor"] = geo["pred"].clip(lower=0)
media = ~geo.con_siap & (geo.dist_siap_km <= CONFIANZA_MEDIA_KM) & (geo.agricola_ha >= 100)
geo["conf"] = np.where(geo.con_siap, "alta", np.where(media, "media", "baja"))
techo_calido = float(geo.loc[calido, "pred"].max())

estados = gpd.read_file(RAIZ / "data/externos/inegi_marcogeo/municipios_13_15_21_29.gpkg",
                        layer="municipios").to_crs("EPSG:6372").dissolve("estado")
estados["geometry"] = estados.geometry.simplify(200)
estados = estados.loc[ESTADOS_MAPA]
# Municipios con parcelas del reto, por estado y nombre (hay un Emiliano Zapata en Hidalgo y otro en Tlaxcala)
reto = pd.read_parquet(RAIZ / "data/processed/parcelas.parquet")[["estado", "municipio"]].drop_duplicates()
geo_reto = geo.merge(reto, on=["estado", "municipio"])

# Desplazamiento de cada etiqueta en metros; con desplazamiento lleva una línea al estado
ETIQ = {"Hidalgo": (0, 0), "Puebla": (0, 0), "Tlaxcala": (-70e3, 0)}


def mapa():
    fig, ax = plt.subplots(figsize=(3.45, 4.3))
    cmap = plt.get_cmap("Blues")
    colores = ListedColormap([cmap(v) for v in np.linspace(0.12, 0.92, len(CORTES) - 1)])
    norm = BoundaryNorm(CORTES, colores.N)
    geo.plot(ax=ax, column="valor", cmap=colores, norm=norm, edgecolor="white", lw=0.2)
    # La confianza se marca solo donde el modelo interpola; los más cálidos ya quedan en la clase más baja
    con = geo[~calido]
    con[con.conf == "baja"].plot(ax=ax, facecolor="none", edgecolor="#4a4a46", hatch="////", lw=0)
    con[con.conf == "media"].plot(ax=ax, facecolor="none", edgecolor="#4a4a46", hatch="...", lw=0)
    estados.boundary.plot(ax=ax, color=TINTA, lw=0.6)
    geo_reto.boundary.plot(ax=ax, color=NARANJA, lw=0.9)
    ax.set_axis_off()
    ax.set_aspect("equal")
    for est, (dx, dy) in ETIQ.items():
        p = estados.loc[est].geometry.representative_point()
        ax.annotate(est, (p.x, p.y), (p.x + dx, p.y + dy), fontsize=7, color=TINTA, ha="center", fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75),
                    arrowprops=None if dx == 0 else dict(arrowstyle="-", color=TINTA, lw=0.4))
    sm = plt.cm.ScalarMappable(cmap=colores, norm=norm)
    cb = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.04, pad=0.01, aspect=30, shrink=0.9,
                      spacing="uniform")
    cb.set_ticks(CORTES)
    cb.set_ticklabels(["0"] + [f"{c:.2f}" for c in CORTES[1:]])
    cb.ax.tick_params(labelsize=6.2, length=2)
    cb.outline.set_visible(False)
    ax.set_title("Rendimiento esperado en 2025 (t/ha)", fontsize=7.5, loc="left")
    leyenda = [Patch(facecolor="white", edgecolor=TINTA, lw=0.4, label="Confianza alta"),
               Patch(facecolor="white", edgecolor="#4a4a46", hatch="...", lw=0.4, label="Confianza media"),
               Patch(facecolor="white", edgecolor="#4a4a46", hatch="////", lw=0.4, label="Confianza baja"),
               Patch(facecolor="none", edgecolor=NARANJA, lw=1.0, label="Municipios del reto")]
    fig.legend(handles=leyenda, loc="upper center", ncol=2, fontsize=6.3, frameon=False,
               bbox_to_anchor=(0.5, 0.075), handlelength=1.5, columnspacing=0.9)
    fig.savefig(DEST / "g5_mapa_a.pdf", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


mapa()
clases = {
    "modelo": nombre,
    "tmax_rango_con_siap": [round(float(tmax_lo), 2), round(float(tmax_hi), 2)],
    "municipios": int(len(geo)),
    "con_valor": int((~calido).sum()),
    "con_siap": int(geo.con_siap.sum()),
    "confianza": {k: int(v) for k, v in geo.loc[~calido, "conf"].value_counts().items()},
    "mas_calidos": int(calido.sum()),
    "mas_calidos_prediccion_max": round(techo_calido, 2),
    "valor_min_max": [round(float(geo.loc[~calido, "valor"].min()), 2), round(float(geo.loc[~calido, "valor"].max()), 2)],
}
Path(__file__).with_name("mapa_clases.json").write_text(json.dumps(clases, indent=1, ensure_ascii=False), encoding="utf-8")
print(json.dumps(clases, indent=1, ensure_ascii=False))
