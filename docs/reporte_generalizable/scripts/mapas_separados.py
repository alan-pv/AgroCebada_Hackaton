"""Genera los dos mapas del anexo por separado (uno por figura, ancho de una columna).

Reproduce el estilo de los mapas de g5_mapas en figuras.py, sin correr todo el script.
Salida: reporte/entrega/figuras/g5_mapa_a.pdf y g5_mapa_b.pdf
"""
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch

RAIZ = Path(__file__).resolve().parents[3]
OUT = RAIZ / "outputs"
DEST = RAIZ / "reporte/entrega/figuras"
GRIS, TINTA = "#8a8984", "#0b0b0b"
plt.rcParams.update({"font.family": "serif", "font.size": 8, "hatch.linewidth": 0.5})

geo = gpd.read_file(OUT / "generalizable_municipios.gpkg", layer="municipios").to_crs("EPSG:6372")
estados = gpd.read_file(RAIZ / "data/externos/inegi_marcogeo/municipios_13_15_21_29.gpkg",
                        layer="municipios").to_crs("EPSG:6372").dissolve("estado")
estados["geometry"] = estados.geometry.simplify(200)

ETIQ = {"Hidalgo": (0, 0), "México": (-40e3, 20e3), "Puebla": (35e3, -60e3), "Tlaxcala": (55e3, 30e3)}
LEYENDA = [Patch(facecolor="#f1f0ec", edgecolor=GRIS, lw=0.4, label="Fuera del rango ambiental"),
           Patch(facecolor="white", edgecolor=TINTA, lw=0.4, label="Confianza alta"),
           Patch(facecolor="white", edgecolor="#4a4a46", hatch="...", lw=0.4, label="Confianza media"),
           Patch(facecolor="white", edgecolor="#4a4a46", hatch="////", lw=0.4, label="Confianza baja")]


def mapa(col, cortes, cmap_nombre, etiqueta, fmt, nombre):
    fig, ax = plt.subplots(figsize=(3.45, 2.6))
    cmap = plt.get_cmap(cmap_nombre)
    colores = ListedColormap([cmap(v) for v in np.linspace(0.12, 0.92, len(cortes) - 1)])
    norm = BoundaryNorm(cortes, colores.N)
    geo[geo[col].isna()].plot(ax=ax, color="#f1f0ec", edgecolor="white", lw=0.2)
    con = geo[geo[col].notna()]
    con.plot(ax=ax, column=col, cmap=colores, norm=norm, edgecolor="white", lw=0.2)
    con[con.confianza == "baja"].plot(ax=ax, facecolor="none", edgecolor="#4a4a46", hatch="////", lw=0)
    con[con.confianza == "media"].plot(ax=ax, facecolor="none", edgecolor="#4a4a46", hatch="...", lw=0)
    estados.boundary.plot(ax=ax, color=TINTA, lw=0.6)
    ax.set_axis_off()
    ax.set_aspect("equal")
    for est, (dx, dy) in ETIQ.items():
        p = estados.loc[est].geometry.representative_point()
        ax.annotate(est, (p.x, p.y), (p.x + dx, p.y + dy), fontsize=7, color=TINTA, ha="center",
                    fontweight="bold", arrowprops=None if dx == 0 else dict(arrowstyle="-", color=TINTA, lw=0.4))
    sm = plt.cm.ScalarMappable(cmap=colores, norm=norm)
    cb = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.04, pad=0.01, aspect=30, shrink=0.9)
    cb.set_ticks(cortes)
    cb.set_ticklabels([fmt(c) for c in cortes])
    cb.ax.tick_params(labelsize=6.5, length=2)
    cb.outline.set_visible(False)
    ax.set_title(etiqueta, fontsize=7.5, loc="left")
    fig.legend(handles=LEYENDA, loc="lower center", ncol=2, fontsize=6.8, frameon=False,
               bbox_to_anchor=(0.5, -0.03), handlelength=1.6, columnspacing=1.2)
    fig.subplots_adjust(bottom=0.16)
    fig.savefig(DEST / f"{nombre}.pdf", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


mapa("esperado", [1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25], "Blues",
     "Rendimiento esperado en 2025 (t/ha)", lambda c: f"{c:.2f}", "g5_mapa_a")
mapa("prob_bajo_2", [0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0], "Oranges",
     "Probabilidad de quedar bajo 2 t/ha", lambda c: f"{c:.1f}", "g5_mapa_b")
