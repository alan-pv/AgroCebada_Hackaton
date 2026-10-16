"""Genera las figuras del reporte docs/reporte_dataset.

Uso (desde docs/reporte_dataset):
    pip install pandas numpy pyshp rasterio matplotlib
    python figuras/generar_figuras.py

Solo genera figuras descriptivas (rendimiento por municipio, rendimiento contra área y lluvia
mensual). Lee los archivos originales de DATASET_RETO_AGRO_2026 en la raíz del repositorio.
"""
from pathlib import Path
import glob
import tempfile
import zipfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
import rasterio
import shapefile

AQUI = Path(__file__).resolve().parent
RAW = AQUI.parents[2] / "DATASET_RETO_AGRO_2026"

# Municipios cuyos rendimientos traen dos decimales (régimen A). El resto viene redondeado (régimen B).
REGIMEN_A = {"Chignahuapan", "Almoloya", "Cuautepec de Hinojosa", "Tepeapulco"}


def cargar_parcelas(tmp):
    """Une el CSV de rendimientos con el shapefile y agrega municipio, estado, centroide y régimen."""
    y = pd.read_csv(RAW / "ID_area_rendimiento_70_30_Reto_AgroCebada.csv", encoding="utf-8-sig").iloc[:, :4]
    shp = shapefile.Reader(str(next(tmp.rglob("Parcelas_Reto_AGC_CONJUNTO.shp"))))
    rows = []
    for sr in shp.shapeRecords():
        rec = sr.record.as_dict()
        pts = np.array(sr.shape.points)
        rows.append({"ID_POLIGONO": rec["ID_POLIGON"], "municipio": rec["Municipio"], "estado": rec["Estado"],
                     "lon": pts[:, 0].mean(), "lat": pts[:, 1].mean()})
    parc = pd.DataFrame(rows).merge(y, on="ID_POLIGONO")
    parc["regimen"] = np.where(parc.municipio.isin(REGIMEN_A), "A", "B")
    return parc.set_index("ID_POLIGONO")

# Tipografía igual a la del reporte (TeX Gyre Termes) si está instalada.
for f in glob.glob("/usr/share/fonts/**/texgyretermes-*.otf", recursive=True):
    font_manager.fontManager.addfont(f)
plt.rcParams.update({
    "font.family": ["TeX Gyre Termes", "DejaVu Serif"], "font.size": 8, "axes.titlesize": 8,
    "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#555555",
    "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.6, "axes.axisbelow": True,
    "pdf.fonttype": 42,
})
COLOR = {"A": "#2a78d6", "B": "#eb6834"}
TINTA = "#222222"
ANCHO_COL, ANCHO_PAG = 3.5, 7.16


def guardar(fig, nombre):
    fig.savefig(AQUI / f"{nombre}.pdf", bbox_inches="tight")
    plt.close(fig)
    print("figura:", nombre)


def fig_regimenes(tr):
    muns = ["Chignahuapan", "Almoloya", "Cuautepec de Hinojosa", "Tepeapulco",
            "Singuilucan", "Emiliano Zapata", "Apan", "Calpulalpan", "Nanacamilpa de Mariano Arista"]
    corto = {"Cuautepec de Hinojosa": "Cuautepec", "Nanacamilpa de Mariano Arista": "Nanacamilpa",
             "Emiliano Zapata": "E. Zapata"}
    fig, ax = plt.subplots(figsize=(ANCHO_PAG, 2.1))
    rng = np.random.default_rng(3)
    for i, m in enumerate(muns):
        g = tr[tr.municipio == m]
        # dispersión horizontal según cuántas parcelas comparten valor, para ver los escalones
        x = i + rng.uniform(-0.28, 0.28, len(g)) * np.minimum(1, g.groupby("RENDIMIENTO_T_HA").RENDIMIENTO_T_HA.transform("size") / 4 + 0.25)
        ax.scatter(x, g.RENDIMIENTO_T_HA, s=14, color=COLOR[g.regimen.iloc[0]], edgecolor="white", linewidth=0.4, zorder=3)
    ax.axvline(3.5, color="#888888", linestyle=(0, (3, 3)), linewidth=0.8)
    for reg, x0, x1 in (("A", -0.5, 3.5), ("B", 3.5, 8.5)):
        mu = tr.loc[tr.regimen == reg, "RENDIMIENTO_T_HA"].mean()
        ax.hlines(mu, x0 + 0.1, x1 - 0.1, color=COLOR[reg], linewidth=1, alpha=0.6)
        ax.text((x0 + x1) / 2, 5.75, f"Régimen {reg} · media {mu:.2f} t/ha", ha="center", color=TINTA, fontsize=7.5, fontweight="bold")
    ax.set_xticks(range(len(muns)))
    ax.set_xticklabels([f"{corto.get(m, m)}\n{diag_estado[m]}" for m in muns])
    ax.set_xlim(-0.5, len(muns) - 0.5)
    ax.set_ylim(1.8, 6.0)
    ax.set_ylabel("Rendimiento (t/ha)")
    ax.grid(axis="x", visible=False)
    guardar(fig, "fig_regimenes")


def fig_area(tr):
    fig, ax = plt.subplots(figsize=(ANCHO_COL, 2.3))
    for reg in ("A", "B"):
        g = tr[tr.regimen == reg]
        ax.scatter(g.AREA_HA, g.RENDIMIENTO_T_HA, s=12, color=COLOR[reg], edgecolor="white", linewidth=0.4,
                   label=f"Régimen {reg}", zorder=3)
    ax.set_xscale("log")
    ax.set_xticks([0.5, 1, 2, 5, 10, 20, 50])
    ax.set_xticklabels(["0.5", "1", "2", "5", "10", "20", "50"])
    ax.set_xlabel("Superficie de la parcela (ha, escala logarítmica)")
    ax.set_ylabel("Rendimiento (t/ha)")
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
    guardar(fig, "fig_area")


def fig_lluvia(P):
    meses = list(range(4, 12))
    nombres = ["abr", "may", "jun", "jul", "ago", "sep", "oct", "nov"]
    tabla = P.groupby(["anio", "mes"]).v.mean().unstack()[meses]
    fig, ax = plt.subplots(figsize=(ANCHO_COL, 2.0))
    ancho = 0.2
    colores = {2022: "#c9ced2", 2023: "#a9b0b5", 2024: "#7d868c", 2025: COLOR["A"]}
    for k, anio in enumerate(tabla.index):
        ax.bar(np.arange(len(meses)) + (k - 1.5) * ancho, tabla.loc[anio], width=ancho - 0.02,
               color=colores[anio], label=str(anio), zorder=3)
    ax.set_xticks(range(len(meses)))
    ax.set_xticklabels(nombres)
    ax.set_ylabel("Precipitación (mm)")
    ax.legend(frameon=False, ncol=4, loc="upper left", fontsize=6.5)
    ax.grid(axis="x", visible=False)
    guardar(fig, "fig_lluvia")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="agrocebada_fig_"))
    for z in RAW.glob("*.zip"):
        zipfile.ZipFile(z).extractall(tmp)
    parc = cargar_parcelas(tmp)
    global diag_estado
    diag_estado = parc.groupby("municipio").estado.first().to_dict()
    tr = parc[parc.CONJUNTO == "ENTRENAMIENTO"].copy()

    fig_regimenes(tr)
    fig_area(tr)

    # Clima
    rows = []
    for var, carpeta, pref in (("P", "Precipitacion_mensual", "PREC"), ("Tmax", "Tmax", "Tmax")):
        base = next(tmp.rglob(carpeta))
        for yr in range(2022, 2026):
            for m in range(1, 13):
                with rasterio.open(base / str(yr) / f"{pref}_{yr}_{m:02d}.tif") as ds:
                    v = [s[0] for s in ds.sample(list(zip(parc.lon, parc.lat)))]
                rows += [(var, yr, m, float(x)) for x in v]
    C = pd.DataFrame(rows, columns=["var", "anio", "mes", "v"])
    fig_lluvia(C[C["var"] == "P"])
    print("Tmax media mayo-sep por año:",
          C[(C["var"] == "Tmax") & C.mes.between(5, 9)].groupby("anio").v.mean().round(2).to_dict())



if __name__ == "__main__":
    main()
