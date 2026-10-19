"""Calibración del p10 y validación de la marca de confianza (issue #46).

Usa outputs/intervalos_cv.csv (validación anidada de 5 repeticiones, método `regimen`) y no
reentrena el modelo. Calcula por régimen la cobertura, las colas, el ancho y la pinball loss
en el cuantil 0.1 del modelo y de una línea base, con IC95 por bootstrap de parcelas (las
repeticiones de una misma parcela no son independientes). Después valida la marca de
confianza con el número de vecinos de entrenamiento del mismo régimen a 400 m, contando los
vecinos en el entrenamiento de cada fold externo.

Uso:
    uv run python scripts/calibracion.py

Escribe outputs/calibracion_p10.csv y outputs/confianza_cv.csv.
"""
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from parcelas import cv, intervalos, train_final
from parcelas.config import OUTPUTS, SEED
from parcelas.predict import RADIO_VECINOS

TAU = 0.1
N_REP = 5
BOOT = 4000
rng = np.random.default_rng(1)


def pinball(y, q, tau=TAU):
    d = np.asarray(y) - np.asarray(q)
    return np.where(d >= 0, tau * d, (tau - 1) * d)


def ic95(df, col):
    """IC95 del promedio de `col` remuestreando parcelas (cada parcela pesa igual)."""
    v = df.groupby("ID_POLIGONO")[col].mean().to_numpy()
    bs = [v[rng.integers(0, len(v), len(v))].mean() for _ in range(BOOT)]
    return np.percentile(bs, [2.5, 97.5])


def folds_externos(X):
    """(repetición, posiciones de prueba, posiciones de entrenamiento, fold) del esquema A."""
    pos = pd.Series(np.arange(len(X)), index=X.index)
    parts = cv.particiones_A(X)
    for r in range(N_REP):
        pr = parts[parts["repeticion"] == r]
        for f in sorted(pr["fold"].unique()):
            te = pos[pr.loc[pr["fold"] == f, "ID_POLIGONO"]].to_numpy()
            yield r, te, np.setdiff1d(np.arange(len(X)), te), int(f)


def lineas_base(X, y):
    """p10 de la media del régimen más el cuantil inferior de sus residuos (CV interna).

    Replica el esquema anidado. El entrenamiento de cada fold externo se parte en 5 para
    obtener residuos fuera de fold de la media del régimen, y el p10 es la media del
    entrenamiento más el cuantil conformal inferior de esos residuos.
    """
    Y, R = y.to_numpy(), X["regimen"].to_numpy()
    filas = []
    for r, te, tr, f in folds_externos(X):
        skf = StratifiedKFold(5, shuffle=True, random_state=SEED + 100 * r + f)
        oof = np.empty(len(tr))
        for a, b in skf.split(X.iloc[tr], R[tr]):
            for g in "AB":
                oof[b[R[tr][b] == g]] = Y[tr][a][R[tr][a] == g].mean()
        for g in "AB":
            m = R[tr] == g
            p10 = Y[tr][m].mean() + intervalos.cuantiles_conformal((Y[tr] - oof)[m])[0]
            for i in te[R[te] == g]:
                filas.append({"repeticion": r, "ID_POLIGONO": X.index[i], "p10_base": p10})
    return pd.DataFrame(filas)


def tabla_calibracion(a):
    """Cobertura, colas, ancho y pinball por régimen y global."""
    a = a.assign(bajo=a["y"] < a["p10"], alto=a["y"] > a["p90"],
                 pin_modelo=pinball(a["y"], a["p10"]), pin_base=pinball(a["y"], a["p10_base"]))
    a["pin_dif"] = a["pin_modelo"] - a["pin_base"]
    filas = []
    for g, d in [("A", a[a["regimen"] == "A"]), ("B", a[a["regimen"] == "B"]), ("global", a)]:
        f = {"grupo": g, "parcelas": d["ID_POLIGONO"].nunique(), "filas": len(d),
             "ancho": d["ancho"].mean()}
        for col, nombre in [("cubierto", "cobertura"), ("bajo", "cola_baja"),
                            ("alto", "cola_alta"), ("pin_modelo", "pinball_modelo"),
                            ("pin_base", "pinball_base"), ("pin_dif", "pinball_dif")]:
            lo, hi = ic95(d, col)
            f[nombre], f[nombre + "_ic_inf"], f[nombre + "_ic_sup"] = d[col].mean(), lo, hi
        filas.append(f)
    return pd.DataFrame(filas)


def tabla_confianza(a, X):
    """MAE y falla de la cola baja según los vecinos a 400 m en el entrenamiento del fold."""
    xy, R = X[["x_m", "y_m"]].to_numpy(), X["regimen"].to_numpy()
    n = {}
    for r, te, tr, _ in folds_externos(X):
        d = np.sqrt(((xy[te][:, None] - xy[tr][None]) ** 2).sum(-1))
        d[R[te][:, None] != R[tr][None]] = np.inf
        for i, c in zip(te, (d <= RADIO_VECINOS).sum(1)):
            n[(r, X.index[i])] = c
    a = a.assign(vecinos=[n[(r, i)] for r, i in zip(a["repeticion"], a["ID_POLIGONO"])])
    a["grupo"] = pd.cut(a["vecinos"], [-1, 0, 2, 99], labels=["0", "1-2", "3 o más"])
    a["error_abs"] = (a["y"] - a["pred"]).abs()
    a["bajo"] = a["y"] < a["p10"]
    t = a.groupby("grupo", observed=True).agg(
        filas=("y", "size"), parcelas=("ID_POLIGONO", "nunique"), mae=("error_abs", "mean"),
        cola_baja=("bajo", "mean"), cobertura=("cubierto", "mean")).reset_index()
    t["grupo"] = t["grupo"].astype(str)
    # diferencia de MAE entre 0 vecinos y al menos 1, remuestreando parcelas completas
    a["cero"] = a["vecinos"] == 0
    g = a.groupby(["ID_POLIGONO", "cero"])["error_abs"].agg(["sum", "count"]).unstack(fill_value=0)
    s0, n0, s1, n1 = (g[("sum", True)].to_numpy(), g[("count", True)].to_numpy(),
                      g[("sum", False)].to_numpy(), g[("count", False)].to_numpy())
    dif = lambda i: s0[i].sum() / n0[i].sum() - s1[i].sum() / n1[i].sum()
    bs = [dif(rng.integers(0, len(s0), len(s0))) for _ in range(BOOT)]
    t["dif_mae_0_vs_1mas"] = np.nan
    t["dif_ic_inf"], t["dif_ic_sup"] = np.nan, np.nan
    t.loc[0, ["dif_mae_0_vs_1mas", "dif_ic_inf", "dif_ic_sup"]] = [
        dif(np.arange(len(s0))), *np.percentile(bs, [2.5, 97.5])]
    return t


def main():
    X, y, _ = train_final.cargar_datos()
    X = X.sort_index()
    y = y.loc[X.index]
    a = pd.read_csv(OUTPUTS / "intervalos_cv.csv")
    a = a[a["metodo"] == "regimen"].merge(lineas_base(X, y), on=["repeticion", "ID_POLIGONO"])
    cal, conf = tabla_calibracion(a), tabla_confianza(a, X)
    cal.round(4).to_csv(OUTPUTS / "calibracion_p10.csv", index=False)
    conf.round(4).to_csv(OUTPUTS / "confianza_cv.csv", index=False)
    print(cal.round(3).T.to_string())
    print(conf.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
