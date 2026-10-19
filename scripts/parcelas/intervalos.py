"""Ensemble de modelos e intervalos de predicción (versión 2).

Uso:
    uv run python scripts/parcelas/intervalos.py

1. Evalúa los miembros y los promedios simples con el esquema A y B, y los compara con el
   candidato v1 con la regla de decisión.
2. Elige el modelo (el candidato v1 si ningún promedio pasa la regla).
3. Mide la cobertura de p10 a p90 con validación anidada, global, por régimen y por
   cuartil de área, y compara variantes de Mondrian.
4. Calibra con los residuos fuera de fold del esquema A, revisa las predicciones de las 59
   parcelas de PREDICCION y guarda el candidato v2.
Las filas de este script usan los bloques "v2_ensemble" y "v2_intervalos", y se reemplazan
al repetir.
"""
import csv
import os
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from parcelas import cv, ensemble, intervalos, modelos
from parcelas.config import ANALISIS_PARCELAS, FIGURAS, PROCESSED
from parcelas.registro import ARCHIVO_REGISTRO, ENCABEZADO, registrar

warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"
N_JOBS = 8
N_PERM = 50
REP_PERM = 3
REP_COBERTURA = 5
UMBRAL = 2.5
REZAGO = {"k": 10, "radio_m": 400.0, "mismo_regimen": True, "solo_valor": True}


def cargar():
    f = pd.read_parquet(PROCESSED / "features.parquet").set_index("ID_POLIGONO")
    p = pd.read_parquet(PROCESSED / "parcelas.parquet").set_index("ID_POLIGONO")
    d = f.join(p[["rendimiento"]])
    ent = d[d["conjunto"] == "ENTRENAMIENTO"].sort_index()
    pred = d[d["conjunto"] == "PREDICCION"].sort_index().drop(columns="rendimiento")
    return ent.drop(columns="rendimiento"), ent["rendimiento"], pred


def miembros(hh):
    """Configuraciones (formato de modelos.desde_config) de los miembros candidatos."""
    return {
        "cand": modelos.configuracion_candidato(),
        "ridge_rezago": {"modelo": "ridge", "columnas": [],
                         "args": {"contexto": ["regimen"], "residuos": False, "rezago": REZAGO}},
        "rf_hist_het": {"modelo": "rf", "columnas": hh,
                        "args": {"contexto": ["regimen"], "residuos": False, "rezago": REZAGO,
                                 "params": {"max_depth": 3, "min_samples_leaf": 8}}},
        "lgbm_hist_het": {"modelo": "lgbm", "columnas": hh,
                          "args": {"contexto": ["regimen"], "residuos": False, "rezago": REZAGO}},
        "residuos_ridge": {"modelo": "ridge", "columnas": hh,
                           "args": {"contexto": [], "residuos": True, "rezago": REZAGO}},
    }


ENSAMBLES = {
    "ens_cand_ridge": ["cand", "ridge_rezago"],
    "ens_cand_rf": ["cand", "rf_hist_het"],
    "ens_cand_ridge_rf": ["cand", "ridge_rezago", "rf_hist_het"],
    "ens_cand_ridge_rf_residuos": ["cand", "ridge_rezago", "rf_hist_het", "residuos_ridge"],
    "ens_cand_lgbm_residuos": ["cand", "lgbm_hist_het", "residuos_ridge"],
}


def cfg_ensemble(nombres, mi):
    return {"tipo": "ensemble", "miembros": [mi[n] | {"nombre": n} for n in nombres],
            "pesos": None}


def reemplazar_registro():
    if not ARCHIVO_REGISTRO.exists():
        return
    with open(ARCHIVO_REGISTRO, newline="", encoding="utf-8") as fh:
        filas = [f for f in csv.DictReader(fh) if not f["bloque"].startswith("v2_")]
    with open(ARCHIVO_REGISTRO, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=ENCABEZADO)
        w.writeheader()
        w.writerows(filas)


def fila_tabla(nombre, miembros_txt, r, victorias="", p="", aceptada=""):
    return {"modelo": nombre, "miembros": miembros_txt, "rmse_A": r["A"].rmse,
            "rmse_B": r["B"].rmse, "reg_A": r["A"].por_regimen["A"]["rmse"],
            "reg_B": r["A"].por_regimen["B"]["rmse"], "victorias": victorias, "p": p,
            "aceptada": aceptada}


# ----------------------------------------------------------------- ensambles

def evaluar_ensambles(X, y, mi, hh):
    base = cv.evaluate(modelos.candidato(), X, y, "AB")
    filas = [fila_tabla(f"candidato_v1 ({mi['cand']['modelo']})", "cand", base, aceptada="base")]
    resultados = {"candidato_v1": base}
    cfgs = {"candidato_v1": modelos.configuracion_candidato()}
    perm_cols = hh + ["x_m", "y_m"]
    for n, c in mi.items():  # miembros sueltos, solo informativos
        if n == "cand":
            continue
        r = cv.evaluate(modelos.desde_config(c), X, y, "AB")
        registrar(r, n, "v2_ensemble", c["columnas"] or ["(solo regimen y rezago)"], c["modelo"],
                  notas="miembro suelto, informativo; no se compara con la regla")
        filas.append(fila_tabla(n, n, r, aceptada="miembro"))
    for nombre, nombres in ENSAMBLES.items():
        cfg = cfg_ensemble(nombres, mi)
        mod = ensemble.construir_desde_config(cfg)
        r = cv.evaluate(mod, X, y, "AB")
        comp = cv.comparacion_emparejada(r["A"], base["A"])
        dec = {"aceptada": False, "victorias": comp["victorias"],
               "diferencia_media": comp["diferencia_media"], "p_permutacion": None}
        if comp["aceptada"]:
            dec = cv.regla_decision(r["A"], base["A"], mod, X, y, perm_cols, N_PERM, REP_PERM)
        resultados[nombre], cfgs[nombre] = r, cfg
        registrar(r, nombre, "v2_ensemble", perm_cols, "promedio", decision=dec,
                  notas=f"base={mi['cand']['nombre']}; promedio simple de {'+'.join(nombres)}; "
                        f"diferencia media {comp['diferencia_media']:+.4f}"
                        + ("" if comp["aceptada"] else "; permutacion no corrida"))
        filas.append(fila_tabla(nombre, "+".join(nombres), r, dec["victorias"],
                                dec["p_permutacion"], "sí" if dec["aceptada"] else "no"))
        print(f"{nombre}: A {r['A'].rmse:.4f} B {r['B'].rmse:.4f} victorias {dec['victorias']} "
              f"aceptada {dec['aceptada']}", flush=True)
    return pd.DataFrame(filas), resultados, cfgs


def elegir(tabla):
    ok = tabla[tabla["aceptada"] == "sí"]
    return "candidato_v1" if ok.empty else ok.sort_values("rmse_A").iloc[0]["modelo"]


# ------------------------------------------------------------------ intervalos

def elegir_metodo(resumen):
    """Método con residuos guardados cuya cobertura por régimen queda más cerca de 0.8.

    Se prefiere el Mondrian por régimen salvo que otro reduzca la desviación máxima
    respecto a 0.8 en más de 0.02.
    """
    cand = ["global", "regimen", "regimen_tamano", "regimen_escala"]
    r = resumen[(resumen["tipo"] == "regimen") & resumen["metodo"].isin(cand)]
    dev = r.assign(d=(r["cobertura"] - 0.8).abs()).groupby("metodo")["d"].max()
    mejor = dev.idxmin()
    return "regimen" if dev["regimen"] - dev[mejor] <= 0.02 else mejor


def sanidad(pred_59, X, y, oof_medio):
    filas = []
    for reg in ["A", "B", "todas"]:
        m_tr = (X["regimen"] == reg) if reg != "todas" else pd.Series(True, index=X.index)
        m_pr = (pred_59["regimen"] == reg) if reg != "todas" else pd.Series(True, index=pred_59.index)
        yt, pp, oo = y[m_tr], pred_59.loc[m_pr, "pred"], oof_medio[m_tr]
        filas.append({
            "regimen": reg, "n_entrenamiento": int(m_tr.sum()), "n_prediccion": int(m_pr.sum()),
            "media_obs": yt.mean(), "media_pred": pp.mean(), "desv_obs": yt.std(),
            "desv_pred": pp.std(), "razon_desv_pred_obs": pp.std() / yt.std(),
            "desv_oof": oo.std(), "razon_desv_oof_obs": oo.std() / yt.std(),
            "min_obs": yt.min(), "max_obs": yt.max(), "min_pred": pp.min(), "max_pred": pp.max(),
            "fuera_rango_global": int(((pp < y.min()) | (pp > y.max())).sum()),
            "fuera_rango_regimen": int(((pp < yt.min()) | (pp > yt.max())).sum()),
        })
    return pd.DataFrame(filas)


def figura(df, ruta):
    d = df[df["repeticion"] == 0]
    fig, ejes = plt.subplots(1, 2, figsize=(10, 4.6), sharex=True, sharey=True)
    for ax, reg in zip(ejes, ["A", "B"]):
        s = d[d["regimen"] == reg]
        cub = s["cubierto"].to_numpy()
        for ok, color in ((True, "#1b6ca8"), (False, "#c8553d")):
            t = s[cub == ok]
            ax.errorbar(t["y"], t["pred"], yerr=[t["pred"] - t["p10"], t["p90"] - t["pred"]],
                        fmt="o", ms=3.5, color=color, ecolor=color, elinewidth=0.9,
                        alpha=0.75, label="cubierta" if ok else "no cubierta")
        ax.plot([1.6, 6.0], [1.6, 6.0], color="#444", lw=0.8, ls="--")
        ax.set_title(f"Régimen {reg}, cobertura {s['cubierto'].mean():.0%} (n={len(s)})")
        ax.set_xlabel("Rendimiento observado (t/ha)")
    ejes[0].set_ylabel("Predicción fuera de fold (t/ha)")
    ejes[0].set_xlim(1.6, 6.0)
    ejes[0].set_ylim(1.6, 6.0)
    ejes[0].legend(loc="upper left", frameon=False)
    fig.tight_layout()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=160)
    plt.close(fig)


def main():
    X, y, X59 = cargar()
    hh = [c for c in X.columns if c.startswith(("hist_", "het_"))]
    mi = miembros(hh)
    reemplazar_registro()
    ANALISIS_PARCELAS.mkdir(parents=True, exist_ok=True)

    tabla, resultados, cfgs = evaluar_ensambles(X, y, mi, hh)
    tabla.to_csv(ANALISIS_PARCELAS / "ensambles.csv", index=False)
    print(tabla.round(4).to_string(index=False))
    nombre = elegir(tabla)
    cfg = cfgs[nombre]
    res = resultados[nombre]
    print("Modelo elegido:", nombre, flush=True)
    modelo = ensemble.construir_desde_config(cfg)

    # cobertura con validación anidada
    df = intervalos.evaluar_cobertura(modelo, X, y, REP_COBERTURA, n_jobs=N_JOBS)
    resumen = intervalos.resumen_cobertura(df)
    resumen.to_csv(ANALISIS_PARCELAS / "cobertura_intervalos.csv", index=False)
    print(resumen.round(3).to_string(index=False))
    metodo = elegir_metodo(resumen)
    print("Método de intervalo:", metodo, flush=True)
    df.assign(cuartil_area=intervalos.cuartil_area(df)).to_csv(
        ANALISIS_PARCELAS / "intervalos_cv.csv", index=False)
    figura(df[df["metodo"] == metodo], FIGURAS / "intervalos.png")

    # calibración final con los residuos fuera de fold del esquema A (10 repeticiones)
    oof = res["A"].oof
    k = oof.shape[1]
    resid = np.concatenate([(y - oof[c]).to_numpy() for c in oof.columns])
    cal = intervalos.CalibradorIntervalo(**intervalos.METODOS[metodo]).fit(
        resid, np.tile(X["regimen"].to_numpy(), k), np.tile(X["area_ha"].to_numpy(), k))
    cal.a_tabla().to_parquet(ANALISIS_PARCELAS / "residuos_calibracion.parquet", index=False)

    # controles de sanidad de las 59
    final = ensemble.construir_desde_config(cfg).fit(X, y)
    sal = intervalos.PrediccionIntervalo(final, cal, UMBRAL).predecir(X59)
    sal["regimen"], sal["area_ha"] = X59["regimen"], X59["area_ha"]
    san = sanidad(sal, X, y, oof.mean(axis=1))
    san.to_csv(ANALISIS_PARCELAS / "sanidad_predicciones.csv", index=False)
    sal.to_csv(ANALISIS_PARCELAS / "predicciones_etapa_intervalos.csv")
    print(san.round(3).T.to_string())

    # registro y candidato
    rm = resumen[(resumen["metodo"] == metodo) & (resumen["tipo"] != "cuartil_area")]
    nota = "; ".join(f"cobertura {r.grupo}={r.cobertura:.3f} ancho={r.ancho_medio:.2f}"
                     for r in rm.itertuples())
    registrar(res, f"intervalos_{metodo}", "v2_intervalos", ["(residuos fuera de fold)"],
              cfg.get("modelo", "promedio"),
              notas=f"modelo={nombre}; conformal {metodo}, nivel 0.8, {REP_COBERTURA} "
                    f"repeticiones anidadas; {nota}")
    glob = float(resumen.query("metodo == @metodo and tipo == 'global'")["cobertura"].iloc[0])
    out = dict(cfg) | {
        "nombre": nombre, "aceptado_por_regla": True,  # v1 pasó la regla, y un promedio solo entra si la pasa
        "rmse_A": round(res["A"].rmse, 4), "rmse_B": round(res["B"].rmse, 4),
        "referencia_candidato_v1_A": round(resultados["candidato_v1"]["A"].rmse, 4),
        "intervalo": {"metodo": metodo, **cal.configuracion(), "umbral": UMBRAL,
                      "calibracion": "analisis/parcelas/residuos_calibracion.parquet",
                      "cobertura_global_anidada": round(glob, 4)}}
    ensemble.guardar_configuracion_final(out)
    print("Listo")


if __name__ == "__main__":
    main()
