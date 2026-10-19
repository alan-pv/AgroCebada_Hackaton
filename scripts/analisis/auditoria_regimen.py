"""Auditoría independiente, parte 2: ¿depende el resultado de cómo se definió el régimen?
y ¿los intervalos entregados cubren lo que dicen?

Requiere correr antes auditoria.py, que deja oof_independiente.csv en la carpeta de salida.
Uso, desde la raíz del repositorio:
    uv run python scripts/analisis/auditoria_regimen.py . outputs/auditoria
Salida: outputs/auditoria/auditoria_regimen.json.
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import StratifiedKFold

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
REPO, OUT = Path(sys.argv[1]), Path(sys.argv[2])
sys.argv = sys.argv[:3]
import piezas as P  # noqa: E402

res = {}
Y, XY, REG, MUN, EST, N = P.Y, P.XY, P.REG, P.MUN, P.EST, P.N


def media_grupo(itr, ite, g):
    s = pd.Series(Y[itr]).groupby(g[itr]).mean()
    return pd.Series(g[ite]).map(s).fillna(Y[itr].mean()).to_numpy()


def lag_sin_regimen(itr, ite, g):
    """Media del municipio más rezago de vecinos sin restricción de régimen (no usa el régimen)."""
    ytr = Y[itr]
    l_tr, _ = P.lag(XY[itr], REG[itr], XY[itr], REG[itr], ytr, 400.0, 10, False, excluir=True)
    l_te, _ = P.lag(XY[ite], REG[ite], XY[itr], REG[itr], ytr, 400.0, 10, False)
    # sin vecinos el relleno usa la media del régimen; lo sustituimos por la media del municipio
    _, n_tr = P.lag(XY[itr], REG[itr], XY[itr], REG[itr], ytr, 400.0, 10, False, excluir=True)
    _, n_te = P.lag(XY[ite], REG[ite], XY[itr], REG[itr], ytr, 400.0, 10, False)
    s = pd.Series(ytr).groupby(g[itr]).mean()
    mtr = np.array([(ytr[(g[itr] == g[itr][i]) & (np.arange(len(itr)) != i)].mean()
                     if ((g[itr] == g[itr][i]).sum() > 1) else ytr.mean()) for i in range(len(itr))])
    mte = pd.Series(g[ite]).map(s).fillna(ytr.mean()).to_numpy()
    l_tr = np.where(n_tr > 0, l_tr, mtr)
    l_te = np.where(n_te > 0, l_te, mte)
    m = LinearRegression().fit(np.column_stack([mtr, l_tr]), ytr)
    return m.predict(np.column_stack([mte, l_te]))


def cv(fn):
    rep = []
    for r in range(10):
        oof = np.zeros(N)
        for itr, ite in StratifiedKFold(5, shuffle=True, random_state=777 + r).split(XY, EST):
            oof[ite] = fn(itr, ite)
        rep.append(np.sqrt(np.mean((oof - Y) ** 2)))
    return float(np.mean(rep))


res["sin_regimen"] = {
    "media_municipio": cv(lambda a, b: media_grupo(a, b, MUN)),
    "media_regimen": cv(lambda a, b: media_grupo(a, b, REG)),
    "municipio_mas_rezago_sin_regimen": cv(lambda a, b: lag_sin_regimen(a, b, MUN)),
}
print(res, flush=True)

# Cobertura de los intervalos entregados aplicada a la predicción fuera de fold independiente
pf = pd.read_csv(REPO / "outputs/predicciones_finales.csv")
pf = pf[pf.ID_POLIGONO.isin(P.te59.index)].merge(P.te59[["regimen"]], left_on="ID_POLIGONO", right_index=True)
pf["lo"], pf["hi"] = pf.p10 - pf.RENDIMIENTO_T_HA, pf.p90 - pf.RENDIMIENTO_T_HA
desp = pf.groupby("regimen")[["lo", "hi"]].agg(["min", "max"]).round(3)
oof = pd.read_csv(OUT / "oof_independiente.csv")
cob = {}
for g in "AB":
    lo, hi = pf.loc[pf.regimen == g, "lo"].median(), pf.loc[pf.regimen == g, "hi"].median()
    o = oof[oof.regimen == g]
    dentro = (o.y >= o.oof_gp + lo) & (o.y <= o.oof_gp + hi)
    cob[g] = {"desplazamiento": [float(lo), float(hi)], "cobertura_oof_independiente": float(dentro.mean()), "n": int(len(o))}
res["intervalos"] = {"cobertura": cob}
print(res["intervalos"], flush=True)
(OUT / "auditoria_regimen.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str))
print("OK")

# Mi implementación sobre las particiones oficiales del proyecto (esquema A)
parts = pd.read_parquet(REPO / "experimentos/particiones.parquet")
parts = parts[parts.esquema == "A"]
pos = pd.Series(np.arange(N), index=P.tr.index)
out = {}
for nombre in ("gp", "media_regimen", "lineal"):
    reps = []
    for r in range(10):
        oof = np.zeros(N)
        pr = parts[parts.repeticion == r]
        for f in range(5):
            ite = pos[pr.loc[pr.fold == f, "ID_POLIGONO"]].to_numpy()
            itr = np.setdiff1d(np.arange(N), ite)
            oof[ite] = P.ajustar_predecir(itr, ite, Y, nombre)
        reps.append(np.sqrt(np.mean((oof - Y) ** 2)))
    out[nombre] = [float(np.mean(reps)), float(np.std(reps, ddof=1))]
res["particiones_del_proyecto"] = out
print(out, flush=True)
(OUT / "auditoria_regimen.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str))
