"""Riesgo de rendimiento por municipio e intervalos con su cobertura.

El residuo fuera de fold del esquema espacial, r = y - pred, para un municipio que el modelo no
vio y un año cualquiera, junta dos errores: el del nivel del lugar y la variación del año. Su
distribución es justo la incertidumbre de "sembrar en un lugar nuevo un año cualquiera". Los
intervalos p10 a p90 y la probabilidad bajo el umbral salen de esos residuos
(`agrocebada.intervalos`).

Cobertura. En cada repetición, los residuos de un fold se calibran con los de los otros folds
(los municipios del fold nunca aportan a su propio intervalo). La cobertura nominal es 0.8.

Escala local (opcional). La variación entre años no es igual en todos lados. Con
escala="local" el residuo se divide entre la desviación entre años interpolada de los
municipios vecinos de entrenamiento y se multiplica por la del municipio a predecir.
"""
import numpy as np
import pandas as pd

from ..intervalos import NIVEL, cuantiles_conformal, prob_bajo_umbral
from .modelos import _idw

UMBRAL = 2.0


def desviacion_local(tr, y, te):
    """Desviación entre años interpolada (IDW) desde los municipios de entrenamiento."""
    a = y - pd.Series(y, index=tr.index).groupby(tr.CVEGEO).transform("mean").to_numpy()
    g = pd.DataFrame({"c": tr.CVEGEO.to_numpy(), "x": tr.x_m.to_numpy(), "y": tr.y_m.to_numpy(), "a": a}) \
        .groupby("c").agg(x=("x", "first"), y=("y", "first"), sd=("a", "std"))
    return _idw(g[["x", "y"]].to_numpy(), g.sd.to_numpy(), te[["x_m", "y_m"]].to_numpy())


def cobertura(d, y, pred, folds, escala="global", nivel=NIVEL, umbral=UMBRAL):
    """Cobertura, ancho medio y calibración de la probabilidad bajo el umbral, de una repetición.

    Devuelve un DataFrame por fila con lo, hi, dentro, prob_bajo y bajo (observado).
    """
    y = np.asarray(y, float)
    r = y - pred
    out = pd.DataFrame(index=d.index, columns=["lo", "hi", "prob_bajo"], dtype=float)
    for f in np.unique(folds):
        te, tr = folds == f, folds != f
        if escala == "local":
            s_tr = desviacion_local(d[tr], y[tr], d[tr])
            s_te = desviacion_local(d[tr], y[tr], d[te])
            rc = r[tr] / s_tr
        else:
            s_te, rc = np.ones(te.sum()), r[tr]
        lo, hi = cuantiles_conformal(rc, nivel)
        out.loc[te, "lo"] = pred[te] + lo * s_te
        out.loc[te, "hi"] = pred[te] + hi * s_te
        out.loc[te, "prob_bajo"] = prob_bajo_umbral(pred[te], rc, umbral, s_te)
    out["dentro"] = (y >= out.lo) & (y <= out.hi)
    out["ancho"] = out.hi - out.lo
    out["bajo"] = y < umbral
    return out


def resumen_cobertura(tabla, por=None, pesos=None):
    """Cobertura, ancho y calibración de la probabilidad bajo el umbral.

    `pesos` es el nombre de una columna (por ejemplo sembrada_ha). Con pesos, cada fila cuenta
    según su superficie, que es la cobertura que ve quien siembra y no la de un municipio
    promedio.
    """
    def f(t):
        w = np.ones(len(t)) if pesos is None else t[pesos].to_numpy(float)
        m = lambda c: float(np.average(t[c].astype(float), weights=w))
        return pd.Series({"n": len(t), "cobertura": m("dentro"), "ancho": m("ancho"),
                          "prob_bajo_media": m("prob_bajo"), "frac_bajo_obs": m("bajo")})
    return f(tabla).to_frame().T if por is None else tabla.groupby(por).apply(f)


def brier(tabla):
    """Puntaje de Brier de la probabilidad bajo el umbral (menor es mejor)."""
    return float(((tabla.prob_bajo - tabla.bajo.astype(float)) ** 2).mean())
