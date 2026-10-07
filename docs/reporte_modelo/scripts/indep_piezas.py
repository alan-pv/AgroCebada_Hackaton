"""Auditoría independiente del modelo final.

No importa nada de `agrocebada`. Reimplementa el rezago espacial, el modelo y la
validación cruzada desde cero para comprobar los números reportados.
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import StratifiedKFold

warnings.filterwarnings("ignore")
REPO = Path(sys.argv[1])
OUT = Path(sys.argv[2])


p = pd.read_parquet(REPO / "data/processed/parcelas.parquet").set_index("ID_POLIGONO").sort_index()
tr = p[p.conjunto == "ENTRENAMIENTO"].copy()
te59 = p[p.conjunto == "PREDICCION"].copy()
Y = tr.rendimiento.to_numpy()
XY = tr[["x_m", "y_m"]].to_numpy()
REG = tr.regimen.to_numpy()
MUN = tr.municipio.to_numpy()
N = len(tr)
res = {}


# ------------------------------------------------------------ piezas independientes
def lag(xy_q, reg_q, xy_t, reg_t, y_t, radio=400.0, k=10, mismo=True, excluir=False):
    """Promedio IDW de y de los vecinos de entrenamiento. Sin vecinos -> media del régimen."""
    d = np.sqrt(((xy_q[:, None] - xy_t[None]) ** 2).sum(-1))
    if excluir:
        np.fill_diagonal(d, np.inf)
    if mismo:
        d[reg_q[:, None] != reg_t[None]] = np.inf
    if radio is not None:
        d[d > radio] = np.inf
    out = np.empty(len(xy_q))
    nvec = np.zeros(len(xy_q), int)
    for i in range(len(xy_q)):
        idx = np.argsort(d[i])[:k]
        idx = idx[np.isfinite(d[i, idx])]
        nvec[i] = len(idx)
        if len(idx):
            w = 1.0 / np.maximum(d[i, idx], 1.0)
            out[i] = (w * y_t[idx]).sum() / w.sum()
        else:
            m = reg_t == reg_q[i]
            if excluir:  # media del régimen sin la propia parcela
                m = m & (np.arange(len(y_t)) != i)
            out[i] = y_t[m].mean()
    return out, nvec


def onehot(r):
    return np.column_stack([(r == "A").astype(float), (r == "B").astype(float)])


def ajustar_predecir(itr, ite, y, modelo="gp", radio=400.0, mismo=True, xy=XY, reg=REG,
                     xy_q=None, reg_q=None):
    """Entrena con itr y predice ite (o las coordenadas xy_q/reg_q si se dan)."""
    ytr = y[itr]
    if xy_q is None:
        xy_q, reg_q = xy[ite], reg[ite]
    if modelo == "media_regimen":
        mA, mB = ytr[reg[itr] == "A"].mean(), ytr[reg[itr] == "B"].mean()
        return np.where(reg_q == "A", mA, mB)
    if modelo == "media_global":
        return np.full(len(xy_q), ytr.mean())
    l_tr, _ = lag(xy[itr], reg[itr], xy[itr], reg[itr], ytr, radio, 10, mismo, excluir=True)
    l_te, _ = lag(xy_q, reg_q, xy[itr], reg[itr], ytr, radio, 10, mismo)
    mu, sd = l_tr.mean(), l_tr.std()
    Ftr = np.column_stack([onehot(reg[itr]), (l_tr - mu) / sd])
    Fte = np.column_stack([onehot(reg_q), (l_te - mu) / sd])
    if modelo == "gp":
        k = ConstantKernel(0.1, (1e-3, 1e1)) * RBF(3.0, (0.5, 50.0)) + WhiteKernel(0.2, (1e-3, 1e1))
        m = GaussianProcessRegressor(k, normalize_y=True, random_state=0).fit(Ftr, ytr)
    elif modelo == "lineal":
        m = LinearRegression().fit(Ftr, ytr)
    elif modelo == "solo_rezago":
        m = LinearRegression().fit(Ftr[:, 2:], ytr)
        return m.predict(Fte[:, 2:])
    return m.predict(Fte)


def estratos():
    """Municipio, con los de menos de 5 parcelas fusionados en su régimen."""
    s = pd.Series(MUN)
    c = s.value_counts()
    s = np.where(s.map(c) < 5, "otros_" + pd.Series(REG), s)
    s = pd.Series(s)
    c = s.value_counts()
    return np.where(s.map(c) < 5, "otros_mezcla", s)


EST = estratos()


def particiones(n_rep, semilla):
    for r in range(n_rep):
        for itr, ite in StratifiedKFold(5, shuffle=True, random_state=semilla + r).split(XY, EST):
            yield r, itr, ite


def cv(modelo, y=Y, n_rep=10, semilla=777, **kw):
    """Devuelve RMSE por repetición, por fold y la predicción fuera de fold promediada."""
    errs = {}
    oof = np.zeros((n_rep, N))
    fold_rmse = []
    for r, itr, ite in particiones(n_rep, semilla):
        pr = ajustar_predecir(itr, ite, y, modelo, **kw)
        oof[r, ite] = pr
        fold_rmse.append((r, np.sqrt(np.mean((pr - y[ite]) ** 2)), ite))
    rep = np.sqrt(((oof - y) ** 2).mean(1))
    return rep, fold_rmse, oof


