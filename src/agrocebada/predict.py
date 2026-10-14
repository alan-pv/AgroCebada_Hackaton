"""Predicción con el modelo final: contrato con la app y con la entrega.

    from agrocebada.predict import cargar_modelo, predict
    tabla = predict(features_df)    # ID_POLIGONO, pred, p10, p90, prob_bajo_umbral

`features_df` tiene el formato de `features.parquet`. El modelo solo necesita las
columnas de parcela `x_m`, `y_m`, `regimen` y `area_ha` (más el identificador), pero se
acepta la tabla completa.

Parcelas que están en el entrenamiento. El rezago espacial se calcula con los vecinos de
entrenamiento. Si se predice una parcela de entrenamiento con `RezagoEspacial.transform`,
ella misma cuenta como vecina a distancia 0 (peso 1 / max(d, 1) = 1, contra unos 0.005 de
un vecino a 200 m), el rezago es casi su propia etiqueta y la predicción sale sesgada hacia
ella. Por eso `excluir_entrenamiento=True` (el valor por defecto) devuelve para esas
parcelas la predicción fuera de fold del esquema A, promediada en las 10 repeticiones, y
calcula el intervalo con ella. Con `excluir_entrenamiento=False` se usa el modelo final
tal cual, que solo sirve para diagnosticar el sobreajuste. Para parcelas nuevas (las 59 de
PREDICCION) no hay diferencia.

Marca de confianza. `confianza` resume cuánta evidencia local respalda a la parcela, con las
parcelas de entrenamiento del mismo régimen. "alta" si hay al menos una a RADIO_VECINOS
(400 m, el radio del rezago), "media" si no hay ninguna a 400 m pero la más cercana está a
RADIO_MEDIA (800 m) o menos, y "baja" si la más cercana está a más de 800 m o el área queda
fuera del rango de entrenamiento de su régimen. En validación cruzada anidada el error
absoluto con 0 vecinos es 0.372 t/ha contra 0.252 con 1 o 2. Marca precisión, no cambia el
intervalo. Las coordenadas salen del rezago espacial guardado en el modelo, y una parcela de
entrenamiento no se cuenta a sí misma.

`python -m agrocebada.predict` genera todos los archivos de entrega (ver `entrega.py`).
"""
import sys
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .config import MODELS

RUTA_MODELO = MODELS / "modelo_final.joblib"
COLUMNAS_ENTRADA = ("x_m", "y_m", "regimen", "area_ha")
SALIDA = ["ID_POLIGONO", "pred", "p10", "p90", "prob_bajo_umbral", "confianza", "vecinos_400m",
          "dist_vecino_m", "motivo_confianza"]
RADIO_VECINOS = 400.0   # m, radio del rezago espacial
RADIO_MEDIA = 800.0     # m, límite de la confianza "media"


@dataclass
class ModeloFinal:
    """Todo lo que hace falta para predecir, en un solo objeto serializable."""
    prediccion: object                 # PrediccionIntervalo (modelo entrenado y calibrador)
    umbral: float                      # umbral de rendimiento bajo, t/ha
    columnas_requeridas: list
    version: str
    fecha_entrenamiento: str
    metricas: dict = field(default_factory=dict)
    oof: pd.Series = None              # predicción fuera de fold de las parcelas de entrenamiento

    @property
    def ids_entrenamiento(self):
        return set(self.oof.index)


def cargar_modelo(ruta=None):
    """Carga `models/modelo_final.joblib` (o la ruta dada)."""
    ruta = Path(ruta) if ruta is not None else RUTA_MODELO
    if not ruta.exists():
        raise FileNotFoundError(f"No existe {ruta}. Genérelo con `python -m agrocebada.train_final`.")
    return joblib.load(ruta)


def _con_id(df):
    """Copia con ID_POLIGONO como columna, venga como índice o como columna."""
    if "ID_POLIGONO" in df.columns:
        return df.reset_index(drop=True).copy()
    if df.index.name == "ID_POLIGONO":
        return df.reset_index()
    raise ValueError("features_df debe traer la columna o el índice ID_POLIGONO")


def validar_entrada(df, columnas):
    """Falla con un mensaje claro si faltan columnas, hay nulos o un régimen desconocido."""
    faltan = [c for c in columnas if c not in df.columns]
    if faltan:
        raise ValueError(f"Faltan columnas requeridas en features_df: {faltan}")
    nulos = [c for c in columnas if df[c].isna().any()]
    if nulos:
        raise ValueError(f"Hay valores nulos en columnas requeridas: {nulos}")
    if df["ID_POLIGONO"].duplicated().any():
        raise ValueError("ID_POLIGONO tiene valores duplicados")
    raros = sorted(set(df["regimen"].astype(str)) - {"A", "B"})
    if raros:
        raise ValueError(f"Régimen desconocido (solo A o B): {raros}")


def _rezago(modelo):
    """El `RezagoEspacial` ajustado dentro del pipeline del modelo (guarda coordenadas y régimen)."""
    pasos = [modelo.prediccion.modelo]
    while pasos:
        o = pasos.pop()
        if hasattr(o, "xy_") and hasattr(o, "reg_"):
            return o
        pasos += [t for _, t in getattr(o, "steps", [])]
        pasos += [t for _, t, _ in getattr(o, "transformers_", [])
                  if not isinstance(t, str)]
    raise ValueError("El modelo no guarda las coordenadas de entrenamiento")


def marca_confianza(df, modelo):
    """Marca de confianza por parcela: vecinos del mismo régimen y rango de área.

    Devuelve confianza, vecinos_400m, dist_vecino_m y motivo_confianza, en el orden de `df`.
    Una parcela de entrenamiento no se cuenta como vecina de sí misma (distancia 0).
    """
    rz = _rezago(modelo)
    cal = modelo.prediccion.calibrador
    q = df[["x_m", "y_m"]].to_numpy(dtype=float)
    reg, area = df["regimen"].astype(str).to_numpy(), df["area_ha"].to_numpy(dtype=float)
    d = np.sqrt(((q[:, None, :] - rz.xy_[None, :, :]) ** 2).sum(-1))
    d = np.where(reg[:, None] == rz.reg_[None, :].astype(str), d, np.inf)
    propia = df["ID_POLIGONO"].isin(modelo.ids_entrenamiento).to_numpy()[:, None] & (d == 0)
    d = np.where(propia, np.inf, d)
    dmin = d.min(1)
    n400 = (d <= RADIO_VECINOS).sum(1)
    ra, aa = np.asarray(cal.regimen_).astype(str), np.asarray(cal.area_, dtype=float)
    fuera = np.array([(a < aa[ra == r].min()) or (a > aa[ra == r].max())
                      for r, a in zip(reg, area)])
    conf, motivo = [], []
    for n, dm, f in zip(n400, dmin, fuera):
        if dm > RADIO_MEDIA or f:
            conf.append("baja")
            motivo.append("área fuera del rango de entrenamiento" if f and dm <= RADIO_MEDIA
                          else f"sin parcelas medidas del mismo régimen a menos de {RADIO_MEDIA:.0f} m"
                          + (" y área fuera del rango de entrenamiento" if f else ""))
        elif n == 0:
            conf.append("media")
            motivo.append(f"sin parcelas medidas del mismo régimen a menos de {RADIO_VECINOS:.0f} m")
        else:
            conf.append("alta")
            motivo.append(f"{n} parcelas medidas del mismo régimen a menos de {RADIO_VECINOS:.0f} m"
                          if n > 1 else f"1 parcela medida del mismo régimen a menos de {RADIO_VECINOS:.0f} m")
    return pd.DataFrame({"confianza": conf, "vecinos_400m": n400.astype(int),
                         "dist_vecino_m": dmin, "motivo_confianza": motivo})


def predict(features_df, umbral=None, modelo=None, excluir_entrenamiento=True):
    """Predicción, intervalo p10 a p90, probabilidad de rendimiento bajo `umbral` y confianza.

    Devuelve un DataFrame con ID_POLIGONO, pred, p10, p90 y prob_bajo_umbral (t/ha, y
    probabilidad entre 0 y 1), más la marca de confianza (confianza, vecinos_400m,
    dist_vecino_m, motivo_confianza), en el orden de `features_df`. `umbral` por defecto es
    el del modelo (2.5 t/ha) y puede ser un número o un arreglo con un valor por parcela.
    Ver el docstring del módulo sobre `excluir_entrenamiento` y la marca de confianza.
    """
    m = modelo if modelo is not None else cargar_modelo()
    df = _con_id(features_df)
    validar_entrada(df, ["ID_POLIGONO", *m.columnas_requeridas])
    if umbral is None:
        umbral = m.umbral
    elif np.ndim(umbral) == 0:
        umbral = float(umbral)
    else:
        umbral = np.asarray(umbral, dtype=float)
        if umbral.shape != (len(df),):
            raise ValueError("umbral debe ser un número o tener un valor por parcela")
    pi = m.prediccion
    pred = np.asarray(pi.modelo.predict(df), dtype=float).ravel()
    if excluir_entrenamiento:
        en_ent = df["ID_POLIGONO"].isin(m.ids_entrenamiento).to_numpy()
        if en_ent.any():
            pred[en_ent] = m.oof.loc[df.loc[en_ent, "ID_POLIGONO"]].to_numpy()
    reg, area = df["regimen"].to_numpy(), df["area_ha"].to_numpy(dtype=float)
    p10, p90 = pi.calibrador.intervalo(pred, reg, area)
    prob = pi.calibrador.prob_bajo(pred, reg, area, umbral)
    base = pd.DataFrame({"ID_POLIGONO": df["ID_POLIGONO"], "pred": pred, "p10": p10,
                         "p90": p90, "prob_bajo_umbral": prob})
    return pd.concat([base, marca_confianza(df, m)], axis=1)[SALIDA]


if __name__ == "__main__":
    from .entrega import main
    sys.exit(main())
