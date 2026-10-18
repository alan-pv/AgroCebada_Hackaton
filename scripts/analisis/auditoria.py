"""Auditoría independiente del modelo final.

No importa nada de `agrocebada`. Reimplementa el rezago espacial, el modelo y la
validación cruzada desde cero para comprobar los números reportados.

Uso, desde la raíz del repositorio:
    uv run python scripts/analisis/auditoria.py . outputs/auditoria
Salida: outputs/auditoria/auditoria.json, permutacion.csv y oof_independiente.csv.
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
OUT.mkdir(parents=True, exist_ok=True)

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


# ------------------------------------------------------------ 1. réplica independiente
print("1. Réplica independiente", flush=True)
rep_gp, f_gp, oof_gp = cv("gp")
rep_rm, f_rm, oof_rm = cv("media_regimen")
rep_gm, _, _ = cv("media_global")
rep_li, f_li, _ = cv("lineal")
rep_sr, _, _ = cv("solo_rezago")
ss = ((Y - Y.mean()) ** 2).sum()
res["replica"] = {
    "gp": [rep_gp.mean(), rep_gp.std(ddof=1)], "media_regimen": [rep_rm.mean(), rep_rm.std(ddof=1)],
    "media_global": [rep_gm.mean(), rep_gm.std(ddof=1)], "lineal_mismas_entradas": [rep_li.mean(), rep_li.std(ddof=1)],
    "solo_rezago_lineal": [rep_sr.mean(), rep_sr.std(ddof=1)],
    "r2_gp": float(1 - ((oof_gp - Y) ** 2).sum(1).mean() / ss),
    "victorias_gp_vs_media_regimen": int((rep_gp < rep_rm).sum()),
    "victorias_gp_vs_lineal": int((rep_gp < rep_li).sum()),
}
for g in "AB":
    m = REG == g
    res["replica"][f"rmse_gp_reg{g}"] = float(np.mean([np.sqrt(np.mean((oof_gp[r, m] - Y[m]) ** 2)) for r in range(10)]))
    res["replica"][f"rmse_mr_reg{g}"] = float(np.mean([np.sqrt(np.mean((oof_rm[r, m] - Y[m]) ** 2)) for r in range(10)]))
print(res["replica"], flush=True)


# ------------------------------------------------- 2. prueba t corregida (Nadeau-Bengio)
def t_corregida(fa, fb, n_tr, n_te):
    d = np.array([a[1] - b[1] for a, b in zip(fa, fb)])
    k = len(d)
    var = d.var(ddof=1)
    t = d.mean() / np.sqrt((1 / k + n_te / n_tr) * var)
    pval = 2 * stats.t.sf(abs(t), k - 1)
    ic = d.mean() + np.array([-1, 1]) * stats.t.ppf(0.975, k - 1) * np.sqrt((1 / k + n_te / n_tr) * var)
    return {"dif_media": float(d.mean()), "t": float(t), "p": float(pval), "ic95": ic.tolist(),
            "folds_ganados": int((d < 0).sum()), "folds": k}


res["t_corregida_gp_vs_media_regimen"] = t_corregida(f_gp, f_rm, N * 0.8, N * 0.2)
res["t_corregida_gp_vs_lineal"] = t_corregida(f_gp, f_li, N * 0.8, N * 0.2)
print(res["t_corregida_gp_vs_media_regimen"], res["t_corregida_gp_vs_lineal"], flush=True)

# ---------------------------------------------- 3. robustez a la semilla de particiones
reps = []
for s in [11, 222, 3333, 44444, 555555]:
    a, _, _ = cv("gp", n_rep=4, semilla=s)
    b, _, _ = cv("media_regimen", n_rep=4, semilla=s)
    reps.append([s, a.mean(), b.mean()])
res["semillas"] = reps
print("semillas", reps, flush=True)

# ---------------------------------------------------- 4. etiquetas permutadas
print("4. Permutaciones", flush=True)
rng = np.random.default_rng(1)
perm_global, perm_dentro = [], []
for i in range(20):
    yp = rng.permutation(Y)
    a, _, _ = cv("gp", y=yp, n_rep=2, semilla=900 + i)
    b, _, _ = cv("media_global", y=yp, n_rep=2, semilla=900 + i)
    perm_global.append([a.mean(), b.mean()])
    yw = Y.copy()
    for g in "AB":
        idx = np.flatnonzero(REG == g)
        yw[idx] = Y[rng.permutation(idx)]
    a, _, _ = cv("gp", y=yw, n_rep=2, semilla=900 + i)
    b, _, _ = cv("media_regimen", y=yw, n_rep=2, semilla=900 + i)
    perm_dentro.append([a.mean(), b.mean()])
pg, pdn = np.array(perm_global), np.array(perm_dentro)
res["permutacion_global"] = {"gp_media": float(pg[:, 0].mean()), "gp_min": float(pg[:, 0].min()),
                             "media_global": float(pg[:, 1].mean()),
                             "gp_mejor_que_media_en": int((pg[:, 0] < pg[:, 1]).sum()), "n": 20}
res["permutacion_dentro_regimen"] = {"gp_media": float(pdn[:, 0].mean()), "gp_min": float(pdn[:, 0].min()),
                                     "media_regimen": float(pdn[:, 1].mean()),
                                     "gp_mejor_que_media_en": int((pdn[:, 0] < pdn[:, 1]).sum()), "n": 20,
                                     "rmse_real_gp": float(rep_gp.mean())}
pd.DataFrame({"rmse_permutado": pdn[:, 0]}).to_csv(OUT / "permutacion.csv", index=False)
print(res["permutacion_global"], res["permutacion_dentro_regimen"], flush=True)

# --------------------------------------------- 5. vecinos: fuga del relleno y duplicados
l_all, n_all = lag(XY, REG, XY, REG, Y, 400.0, 10, True, excluir=True)
res["vecinos_entrenamiento"] = {
    "sin_vecino_400m": int((n_all == 0).sum()),
    "mediana_vecinos": float(np.median(n_all)),
}
d = np.sqrt(((XY[:, None] - XY[None]) ** 2).sum(-1))
np.fill_diagonal(d, np.inf)
d[REG[:, None] != REG[None]] = np.inf
j = d.argmin(1)
dn = d[np.arange(N), j]
cerca = dn <= 400
res["vecino_mas_cercano"] = {
    "con_vecino_400m": int(cerca.sum()),
    "misma_etiqueta_exacta": int((np.isclose(Y[j], Y) & cerca).sum()),
    "dif_abs_mediana_400m": float(np.median(np.abs(Y[j] - Y)[cerca])),
    "dif_abs_mediana_lejos": float(np.median(np.abs(Y[j] - Y)[~cerca])),
    "corr_y_rezago_dentro_regimen": {g: float(np.corrcoef(Y[REG == g], l_all[REG == g])[0, 1]) for g in "AB"},
}
print(res["vecinos_entrenamiento"], res["vecino_mas_cercano"], flush=True)

# --------------------------------- 6. ¿las 59 parcelas se parecen a los folds de prueba?
XY59, REG59 = te59[["x_m", "y_m"]].to_numpy(), te59.regimen.to_numpy()
_, n59 = lag(XY59, REG59, XY, REG, Y, 400.0, 10, True)
d59 = np.sqrt(((XY59[:, None] - XY[None]) ** 2).sum(-1))
d59[REG59[:, None] != REG[None]] = np.inf
dmin59 = d59.min(1)
dcv, ncv = [], []
for r, itr, ite in particiones(10, 777):
    dd = np.sqrt(((XY[ite][:, None] - XY[itr][None]) ** 2).sum(-1))
    dd[REG[ite][:, None] != REG[itr][None]] = np.inf
    dcv.extend(dd.min(1))
    ncv.extend((dd <= 400).sum(1))
dcv, ncv = np.array(dcv), np.array(ncv)
res["representatividad"] = {
    "59_frac_con_vecino_400m": float((n59 > 0).mean()), "cv_frac_con_vecino_400m": float((ncv > 0).mean()),
    "59_dist_mediana_m": float(np.median(dmin59)), "cv_dist_mediana_m": float(np.median(dcv)),
    "59_vecinos_medios": float(n59.mean()), "cv_vecinos_medios": float(np.minimum(ncv, 10).mean()),
    "ks_p_distancias": float(stats.ks_2samp(dmin59, dcv).pvalue),
    "municipios_59_sin_entrenamiento": sorted(set(te59.municipio) - set(tr.municipio)),
}
print(res["representatividad"], flush=True)

# -------------------------- 7. predicción independiente de las 59 y comparación con la entrega
pred59 = ajustar_predecir(np.arange(N), None, Y, "gp", xy_q=XY59, reg_q=REG59)
ent = pd.read_csv(sorted((REPO / "outputs").glob("*_prediccion.csv"))[0]).set_index("ID_POLIGONO")
dif = np.abs(pred59 - ent.loc[te59.index, "RENDIMIENTO_T_HA"].to_numpy())
res["entrega"] = {"n": int(len(ent)), "ids_iguales": bool(set(ent.index) == set(te59.index)),
                  "dif_max": float(dif.max()), "dif_media": float(dif.mean())}
print(res["entrega"], flush=True)

# -------------------------------------- 8. validación anidada del proceso de selección
print("8. Anidada", flush=True)
CONFIGS = [("media_regimen", {})] + [("gp", {"radio": r, "mismo": m}) for r in (200.0, 400.0, 800.0, 1500.0, None)
                                     for m in (True, False)] + [("lineal", {"radio": 400.0, "mismo": True})]
outer = []
elegidos = []
for r in range(3):
    for itr, ite in StratifiedKFold(5, shuffle=True, random_state=5000 + r).split(XY, EST):
        best, best_rmse = None, np.inf
        for nombre, kw in CONFIGS:
            e = []
            for ritr, rite in StratifiedKFold(5, shuffle=True, random_state=6000 + r).split(itr, EST[itr]):
                pr = ajustar_predecir(itr[ritr], itr[rite], Y, nombre, **kw)
                e.append((pr - Y[itr[rite]]) ** 2)
            rm = np.sqrt(np.concatenate(e).mean())
            if rm < best_rmse:
                best, best_rmse = (nombre, kw), rm
        elegidos.append(f"{best[0]} {best[1]}")
        pr = ajustar_predecir(itr, ite, Y, best[0], **best[1])
        outer.append((pr - Y[ite]) ** 2)
res["anidada"] = {"rmse_externo": float(np.sqrt(np.concatenate(outer).mean())),
                  "elegidos": pd.Series(elegidos).value_counts().to_dict(), "n_configs": len(CONFIGS)}
print(res["anidada"], flush=True)

(OUT / "auditoria.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=float))
pd.DataFrame({"ID_POLIGONO": tr.index, "y": Y, "regimen": REG, "municipio": MUN,
              "oof_gp": oof_gp.mean(0), "oof_mr": oof_rm.mean(0)}).to_csv(OUT / "oof_independiente.csv", index=False)
print("OK")
