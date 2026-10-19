"""Genera los archivos de la entrega a partir de `models/modelo_final.joblib`.

    uv run python -m parcelas.predict      # equivale a `python -m parcelas.entrega`

Escribe
  outputs/parcelas/predicciones_finales.csv        las 59 con p10, p90 y probabilidad bajo el umbral
  outputs/parcelas/{NOMBRE_EQUIPO}_prediccion.csv  el CSV para FIRA (ID_POLIGONO, AREA_HA, RENDIMIENTO_T_HA, CONJUNTO)
  outputs/parcelas/predicciones.parquet            las 197 parcelas, para la app
  outputs/parcelas/controles_entrega.csv           resultado de los controles
  analisis/parcelas/margen_azar.csv                variación esperada del RMSE sobre 59 parcelas
  outputs/figuras/mapa_predicciones.png            coherencia espacial
Si algún control de tipo "falla" no se cumple, termina con error después de guardar
`controles_entrega.csv`.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import controles
from .cv import N_REP
from .config import ANALISIS_PARCELAS, FIGURAS, NOMBRE_EQUIPO, OUTPUTS_PARCELAS, PROCESSED, SEED
from .io import leer_etiquetas
from .predict import cargar_modelo, predict
from .train_final import cargar_datos

N_SUBMUESTRAS = 5000


def tabla_completa(modelo):
    """Las 197 parcelas con observado, predicción (fuera de fold si es de entrenamiento) e intervalo."""
    f = pd.read_parquet(PROCESSED / "features.parquet")
    p = pd.read_parquet(PROCESSED / "parcelas.parquet")[["ID_POLIGONO", "rendimiento"]]
    pr = predict(f, modelo=modelo)
    t = f[["ID_POLIGONO", "conjunto", "regimen", "estado", "municipio", "lon", "lat", "area_ha"]]
    t = t.merge(p, on="ID_POLIGONO").merge(pr, on="ID_POLIGONO")
    t["observado"] = t["rendimiento"].where(t["conjunto"] == "ENTRENAMIENTO")
    return t.drop(columns="rendimiento").sort_values("ID_POLIGONO").reset_index(drop=True)


def archivos_de_entrega(t):
    """Las 59 predicciones como se entregan: valores redondeados a 2 decimales."""
    e = t[t["conjunto"] == "PREDICCION"].copy()
    out = pd.DataFrame({"ID_POLIGONO": e["ID_POLIGONO"].to_numpy(),
                        "RENDIMIENTO_T_HA": e["pred"].round(2).to_numpy(),
                        "p10": e["p10"].round(2).to_numpy(), "p90": e["p90"].round(2).to_numpy(),
                        "prob_bajo_umbral": e["prob_bajo_umbral"].round(3).to_numpy(),
                        "regimen": e["regimen"].to_numpy()})
    return out.reset_index(drop=True)


def csv_fira(e):
    """Las 59 con las columnas del archivo de FIRA. AREA_HA y CONJUNTO se copian del original."""
    et = leer_etiquetas().drop(columns="RENDIMIENTO_T_HA")
    out = e[["ID_POLIGONO", "RENDIMIENTO_T_HA"]].merge(et, on="ID_POLIGONO", how="left", validate="1:1")
    return out[["ID_POLIGONO", "AREA_HA", "RENDIMIENTO_T_HA", "CONJUNTO"]]


def margen_azar(n_prediccion_por_regimen, semilla=SEED):
    """Variación del RMSE de una calificación sobre 59 parcelas.

    Toma los residuos fuera de fold del esquema A guardados para la calibración (10
    repeticiones x 138 parcelas). En cada sorteo elige una repetición y, sin reemplazo,
    tantas parcelas de cada régimen como tiene PREDICCION (37 de A y 22 de B), y calcula el
    RMSE de esas 59. Es un cálculo aproximado, porque las 138 no son una población
    infinita y el sorteo sin reemplazo subestima algo la dispersión.
    """
    from .train_final import ARCHIVO_CALIBRACION
    c = pd.read_parquet(ARCHIVO_CALIBRACION)
    reg = c["regimen"].to_numpy()
    # La calibración repite el mismo orden de parcelas en cada repetición
    n_rep = N_REP
    n_par = len(c) // n_rep
    res = c["residuo"].to_numpy().reshape(n_rep, n_par)
    reg1 = reg[:n_par]
    rng = np.random.default_rng(semilla)
    idx = {r: np.flatnonzero(reg1 == r) for r in n_prediccion_por_regimen}
    rmse = np.empty(N_SUBMUESTRAS)
    for i in range(N_SUBMUESTRAS):
        k = rng.integers(n_rep)
        sel = np.concatenate([rng.choice(idx[r], n, replace=False)
                              for r, n in n_prediccion_por_regimen.items()])
        rmse[i] = np.sqrt(np.mean(res[k, sel] ** 2))
    q = np.quantile(rmse, [0.05, 0.5, 0.95])
    return pd.DataFrame([{"n_parcelas": int(sum(n_prediccion_por_regimen.values())),
                          "sorteos": N_SUBMUESTRAS, "rmse_media": rmse.mean(),
                          "rmse_desv": rmse.std(ddof=1), "p05": q[0], "mediana": q[1],
                          "p95": q[2], "rmse_completo": float(np.sqrt(np.mean(res ** 2)))}])







def mapa(t, ruta):
    """Mapa de coherencia espacial: observado en entrenamiento y predicho en las 59, misma escala."""
    import geopandas as gpd
    g = gpd.read_file(PROCESSED / "parcelas.gpkg")[["ID_POLIGONO", "geometry"]]
    g = g.merge(t, on="ID_POLIGONO")
    g["valor"] = g["observado"].where(g["conjunto"] == "ENTRENAMIENTO", g["pred"])
    g = g.to_crs("EPSG:6372")
    vmin, vmax = float(g["valor"].min()), float(g["valor"].max())
    fig, ejes = plt.subplots(1, 2, figsize=(12.5, 6.2), gridspec_kw={"width_ratios": [1.15, 1]})
    chig = g[g["municipio"] == "Chignahuapan"]
    cajas = [g.total_bounds, chig.total_bounds]
    titulos = ["Todas las parcelas", "Chignahuapan, ampliado"]
    for ax, caja, tit in zip(ejes, cajas, titulos):
        ent, prd = g[g["conjunto"] == "ENTRENAMIENTO"], g[g["conjunto"] == "PREDICCION"]
        color = lambda v: plt.cm.viridis((v - vmin) / (vmax - vmin))
        # el borde del color del relleno hace visibles los polígonos pequeños
        ent.plot(ax=ax, column="valor", cmap="viridis", vmin=vmin, vmax=vmax, linewidth=0)
        ent.boundary.plot(ax=ax, color=[color(v) for v in ent["valor"]], linewidth=1.0)
        if tit.startswith("Todas"):  # a esta escala los polígonos son puntos, se marcan con un aro
            c = prd.geometry.centroid
            ax.scatter(c.x, c.y, c=prd["valor"], cmap="viridis", vmin=vmin, vmax=vmax, s=26,
                       edgecolors="black", linewidths=0.8, zorder=3)
        else:
            prd.plot(ax=ax, column="valor", cmap="viridis", vmin=vmin, vmax=vmax,
                     edgecolor="black", linewidth=0.9)
        ax.set_xlabel("")
        ax.set_ylabel("")
        mx, my = 0.04 * (caja[2] - caja[0]), 0.04 * (caja[3] - caja[1])
        ax.set_xlim(caja[0] - mx, caja[2] + mx)
        ax.set_ylim(caja[1] - my, caja[3] + my)
        ax.set_title(tit)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
    sm = plt.cm.ScalarMappable(cmap="viridis", norm=plt.Normalize(vmin, vmax))
    cb = fig.colorbar(sm, ax=ejes, shrink=0.8, pad=0.02)
    cb.set_label("Rendimiento (t/ha)")
    fig.suptitle("Observado en entrenamiento (sin borde) y predicho en las 59 (borde negro), misma escala de color")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main():
    m = cargar_modelo()
    X, y, X59 = cargar_datos()
    t = tabla_completa(m)
    e = archivos_de_entrega(t)
    OUTPUTS_PARCELAS.mkdir(parents=True, exist_ok=True)

    # Controles: se guardan siempre, y fallan antes de escribir los archivos de entrega
    xy = pd.concat([X, X59])[["x_m", "y_m"]]
    c = controles.ejecutar(e, X59.index, X["regimen"], y, X[["x_m", "y_m"]],
                           xy.loc[e["ID_POLIGONO"]])
    # sesgo del rezago al predecir parcelas de entrenamiento con el modelo final
    dentro = predict(X.reset_index(), modelo=m, excluir_entrenamiento=False)["pred"].to_numpy()
    rm = lambda p: float(np.sqrt(np.mean((p - y.to_numpy()) ** 2)))
    c = pd.concat([c, pd.DataFrame([{
        "control": "sesgo_rezago_entrenamiento", "tipo": "reporte", "estado": "informativo",
        "valor": round(rm(dentro), 4),
        "detalle": f"RMSE de las 138 con el modelo final {rm(dentro):.3f} contra "
                   f"{rm(m.oof.loc[X.index].to_numpy()):.3f} fuera de fold"}])], ignore_index=True)
    c.to_csv(OUTPUTS_PARCELAS / "controles_entrega.csv", index=False, encoding="utf-8")
    print(c.to_string(index=False))
    controles.verificar(c)

    cols = ["ID_POLIGONO", "RENDIMIENTO_T_HA", "p10", "p90", "prob_bajo_umbral"]
    e[cols].to_csv(OUTPUTS_PARCELAS / "predicciones_finales.csv", index=False, encoding="utf-8",
                   lineterminator="\n")
    csv_fira(e).to_csv(OUTPUTS_PARCELAS / f"{NOMBRE_EQUIPO}_prediccion.csv", index=False,
                       encoding="utf-8", lineterminator="\n")
    t.to_parquet(OUTPUTS_PARCELAS / "predicciones.parquet", index=False)
    cuenta = e["regimen"].value_counts().sort_index().to_dict()
    margen_azar(cuenta).round(4).to_csv(ANALISIS_PARCELAS / "margen_azar.csv", index=False)
    mapa(t, FIGURAS / "mapa_predicciones.png")
    print(f"Entrega generada: {len(e)} predicciones en {OUTPUTS_PARCELAS}")
    return 0
