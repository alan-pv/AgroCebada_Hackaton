"""Entrena el modelo final y lo guarda en `models/modelo_final.joblib`.

    uv run python -m agrocebada.train_final      # ~1 min

Reconstruye el candidato de la versión 2 desde `experimentos/candidato_v2.json`, lo
entrena con las 138 parcelas de ENTRENAMIENTO, arma el calibrador de intervalos con los
residuos guardados en `experimentos/calibracion_v2.parquet` y vuelve a correr la
validación cruzada (esquemas A y B) para guardar las métricas y la predicción fuera de
fold de cada parcela de entrenamiento. Es determinista (config.SEED).
"""
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

from . import cv, ensemble, intervalos
from .config import EXPERIMENTOS, PROCESSED
from .predict import COLUMNAS_ENTRADA, RUTA_MODELO, ModeloFinal

VERSION = "1.0"
ARCHIVO_CALIBRACION = EXPERIMENTOS / "calibracion_v2.parquet"


def cargar_datos():
    """Devuelve (X, y, X59): entrenamiento con índice ID_POLIGONO, su rendimiento y las 59."""
    f = pd.read_parquet(PROCESSED / "features.parquet").set_index("ID_POLIGONO")
    p = pd.read_parquet(PROCESSED / "parcelas.parquet").set_index("ID_POLIGONO")
    d = f.join(p[["rendimiento"]])
    ent = d[d["conjunto"] == "ENTRENAMIENTO"].sort_index()
    pred = d[d["conjunto"] == "PREDICCION"].sort_index().drop(columns="rendimiento")
    return ent.drop(columns="rendimiento"), ent["rendimiento"], pred


def _metricas(res):
    out = {"A": res["A"].resumen() | {"por_regimen": res["A"].por_regimen,
                                      "por_estado": res["A"].por_estado},
           "B": res["B"].resumen() | {"por_regimen": res["B"].por_regimen,
                                      "por_estado": res["B"].por_estado}}
    return out


def calibrador(cfg_intervalo):
    """Calibrador de intervalos con los residuos fuera de fold guardados."""
    t = pd.read_parquet(ARCHIVO_CALIBRACION)
    return intervalos.CalibradorIntervalo(
        nivel=cfg_intervalo["nivel"], agrupar=cfg_intervalo["agrupar"],
        tamano=cfg_intervalo["tamano"], min_grupo=cfg_intervalo["min_grupo"]
    ).fit(t["residuo"], t["regimen"], t["area_ha"]), t


def entrenar(ruta=RUTA_MODELO):
    X, y, _ = cargar_datos()
    cfg = ensemble.configuracion_candidato_v2()
    modelo = ensemble.candidato_v2().fit(X, y)
    cal, tabla_cal = calibrador(cfg["intervalo"])
    umbral = float(cfg["intervalo"]["umbral"])

    res = cv.evaluate(ensemble.candidato_v2(), X, y, "AB")
    oof = res["A"].oof.mean(axis=1).rename("oof")
    # La calibración guardada debe ser la de este mismo modelo y estas mismas particiones
    resid = np.concatenate([(y - res["A"].oof[c]).to_numpy() for c in res["A"].oof.columns])
    if not np.allclose(resid, tabla_cal["residuo"].to_numpy(), atol=1e-6):
        raise RuntimeError("Los residuos de calibracion_v2.parquet no coinciden con la "
                           "validación actual. Reejecute scripts/ensemble_intervalos.py")
    metricas = _metricas(res) | {
        "nombre_candidato": cfg["nombre"], "n_entrenamiento": int(len(X)),
        "intervalo": cfg["intervalo"]}
    final = ModeloFinal(
        prediccion=intervalos.PrediccionIntervalo(modelo, cal, umbral), umbral=umbral,
        columnas_requeridas=list(COLUMNAS_ENTRADA), version=VERSION,
        fecha_entrenamiento=datetime.now().strftime("%Y-%m-%d"), metricas=metricas, oof=oof)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(final, ruta, compress=3)
    return final


def main():
    final = entrenar()
    a, b = final.metricas["A"], final.metricas["B"]
    print(f"Modelo guardado en {RUTA_MODELO} ({RUTA_MODELO.stat().st_size / 1024:.0f} KB)")
    print(f"Esquema A: RMSE {a['rmse']:.4f}, MAE {a['mae']:.4f}, R2 {a['r2']:.4f}")
    print(f"Esquema B: RMSE {b['rmse']:.4f}")


if __name__ == "__main__":
    main()
