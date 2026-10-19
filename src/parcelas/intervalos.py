"""Intervalos de predicción por conformal y probabilidad de rendimiento bajo un umbral.

Los intervalos usan los residuos fuera de fold del modelo, r = y - pred, con signo. El
intervalo p10 a p90 (nivel nominal 0.8) deja 10 % de la probabilidad en cada cola.

Dos formas de calibrar
  Residuos guardados (`CalibradorIntervalo`). Un modelo entrenado con todas las parcelas
    más los residuos fuera de fold guardados dan pred + cuantil del residuo. Es lo que se
    usa en producción y lo que se evalúa con validación anidada.
  CV+ (`cvmas`, Barber et al., 2021). Para cada parcela nueva se usa la predicción de
    cada modelo de fold, desplazada por el residuo de las parcelas que ese modelo no vio.

Mondrian significa calcular los cuantiles dentro de cada grupo (régimen, o régimen por
tamaño) en lugar de con todos los residuos.

API para predecir parcelas nuevas

    cal = CalibradorIntervalo(agrupar="regimen").fit(residuos, regimen, area)
    pred = PrediccionIntervalo(modelo_entrenado, cal, umbral=2.5).predecir(X_nuevas)
    # DataFrame con pred, p10, p90 y prob_bajo_umbral, indexado como X_nuevas
"""
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.base import clone
from sklearn.model_selection import StratifiedKFold

from . import cv
from .config import SEED

NIVEL = 0.8
UMBRAL_DEFECTO = 2.5


# ------------------------------------------------------------------ cuantiles

def _indices_cola(n, alfa):
    """Posiciones (base 0) del cuantil inferior y superior con la corrección de n + 1."""
    lo = int(np.floor(alfa * (n + 1))) - 1
    hi = int(np.ceil((1 - alfa) * (n + 1))) - 1
    return max(lo, 0), min(hi, n - 1)


def cuantiles_conformal(residuos, nivel=NIVEL):
    """Desplazamientos (inferior, superior) que se suman a la predicción."""
    r = np.sort(np.asarray(residuos, dtype=float))
    lo, hi = _indices_cola(len(r), (1 - nivel) / 2)
    return float(r[lo]), float(r[hi])


def prob_bajo_umbral(pred, residuos_calibracion, umbral=UMBRAL_DEFECTO, escala=1.0):
    """Probabilidad de que el rendimiento quede por debajo de `umbral` (t/ha).

    Usa la distribución empírica de los residuos del grupo, y = pred + escala * r. La
    probabilidad es la fracción de residuos con pred + escala * r < umbral. Crece con el
    umbral y baja cuando la predicción sube. `pred` y `escala` pueden ser arreglos.
    """
    r = np.sort(np.asarray(residuos_calibracion, dtype=float))
    if len(r) == 0:
        raise ValueError("Se necesitan residuos de calibración")
    corte = (umbral - np.asarray(pred, dtype=float)) / np.asarray(escala, dtype=float)
    p = np.searchsorted(r, corte, side="left") / len(r)
    return float(p) if np.ndim(p) == 0 else p


# ----------------------------------------------------------------- calibrador

class CalibradorIntervalo:
    """Guarda los residuos de calibración y entrega intervalos y probabilidades.

    agrupar: "ninguno" (todos los residuos juntos) o "regimen" (Mondrian por régimen).
    tamano: "ninguno", "mediana" (el grupo se parte además en parcelas chicas y grandes
      según la mediana del área de calibración) o "escala" (los residuos se dividen por
      s(area) = exp(b * (log area - media)), con b ajustado por mínimos cuadrados sobre
      log|r|, y el intervalo se multiplica por s del área de la parcela nueva).
    min_grupo: si un grupo tiene menos residuos se usan los de su régimen y, en su
      defecto, todos.
    """

    def __init__(self, nivel=NIVEL, agrupar="regimen", tamano="ninguno", min_grupo=20):
        self.nivel = nivel
        self.agrupar = agrupar
        self.tamano = tamano
        self.min_grupo = min_grupo

    def fit(self, residuos, regimen, area):
        r = np.asarray(residuos, dtype=float)
        self.residuo_crudo_ = r
        self.regimen_ = np.asarray(regimen).astype(str)
        self.area_ = np.asarray(area, dtype=float)
        la = np.log(self.area_)
        self.log_area_media_ = float(la.mean())
        self.mediana_area_ = float(np.median(self.area_))
        self.pendiente_ = 0.0
        if self.tamano == "escala":
            self.pendiente_ = float(np.polyfit(la - self.log_area_media_,
                                               np.log(np.abs(r) + 0.05), 1)[0])
        self.residuos_ = r / self._escala(self.area_)
        self.claves_ = self._claves(self.regimen_, self.area_)
        return self

    def _escala(self, area):
        la = np.log(np.asarray(area, dtype=float)) - self.log_area_media_
        return np.exp(self.pendiente_ * la)

    def _claves(self, regimen, area):
        regimen = np.asarray(regimen).astype(str)
        base = np.full(len(regimen), "todos") if self.agrupar == "ninguno" else regimen
        if self.tamano == "mediana":
            chica = np.asarray(area, dtype=float) <= self.mediana_area_
            base = np.array([f"{b}|{'chica' if c else 'grande'}" for b, c in zip(base, chica)])
        return base

    def residuos_de(self, clave):
        """Residuos (ya normalizados por la escala) del grupo `clave`, con respaldo."""
        m = self.claves_ == clave
        if m.sum() >= self.min_grupo:
            return self.residuos_[m]
        reg = str(clave).split("|")[0]
        m = np.array([str(k).split("|")[0] == reg for k in self.claves_])
        return self.residuos_[m] if m.sum() >= self.min_grupo else self.residuos_

    def desplazamientos(self, regimen, area):
        """Arreglos (inferior, superior) en t/ha para cada parcela."""
        claves = self._claves(regimen, area)
        esc = self._escala(area)
        lo, hi = np.empty(len(claves)), np.empty(len(claves))
        for c in pd.unique(claves):
            m = claves == c
            a, b = cuantiles_conformal(self.residuos_de(c), self.nivel)
            lo[m], hi[m] = a * esc[m], b * esc[m]
        return lo, hi

    def intervalo(self, pred, regimen, area):
        lo, hi = self.desplazamientos(regimen, area)
        pred = np.asarray(pred, dtype=float)
        return pred + lo, pred + hi

    def prob_bajo(self, pred, regimen, area, umbral=UMBRAL_DEFECTO):
        pred = np.asarray(pred, dtype=float)
        claves = self._claves(regimen, area)
        esc = self._escala(area)
        out = np.empty(len(pred))
        umbral = np.asarray(umbral, dtype=float)  # número o un valor por parcela
        for c in pd.unique(claves):
            m = claves == c
            u = umbral if umbral.ndim == 0 else umbral[m]
            out[m] = prob_bajo_umbral(pred[m], self.residuos_de(c), u, esc[m])
        return out

    def a_tabla(self):
        """Residuos con signo, régimen y área, para guardar la calibración."""
        return pd.DataFrame({"residuo": self.residuo_crudo_, "regimen": self.regimen_,
                             "area_ha": self.area_})

    def configuracion(self):
        return {"nivel": self.nivel, "agrupar": self.agrupar, "tamano": self.tamano,
                "min_grupo": self.min_grupo}


class PrediccionIntervalo:
    """Modelo entrenado más calibrador. Devuelve pred, p10, p90 y prob_bajo_umbral.

    `modelo` ya ajustado con todas las parcelas de entrenamiento. `X` de `predecir` debe
    traer las columnas que usa el modelo más `regimen` y `area_ha`.
    """

    def __init__(self, modelo, calibrador, umbral=UMBRAL_DEFECTO):
        self.modelo = modelo
        self.calibrador = calibrador
        self.umbral = umbral

    def predecir(self, X):
        pred = np.asarray(self.modelo.predict(X), dtype=float).ravel()
        reg, area = X["regimen"].to_numpy(), X["area_ha"].to_numpy()
        p10, p90 = self.calibrador.intervalo(pred, reg, area)
        prob = self.calibrador.prob_bajo(pred, reg, area, self.umbral)
        return pd.DataFrame({"pred": pred, "p10": p10, "p90": p90, "prob_bajo_umbral": prob},
                            index=X.index)


# ------------------------------------------------------------------------ CV+

def cvmas(pred_fold, residuos, fold_residuo, clave_residuo=None, clave_nueva=None,
          nivel=NIVEL):
    """Intervalos CV+ con residuos con signo.

    pred_fold: matriz (folds x parcelas nuevas) con la predicción del modelo de cada fold.
    residuos: residuo fuera de fold de cada parcela de calibración. fold_residuo: fold en
      que cayó cada una. Para Mondrian se dan las claves de grupo de las parcelas de
      calibración y de las nuevas.
    Para la parcela j los límites son los cuantiles inferior y superior de
    {pred_fold[k(i), j] + r_i}, con la corrección de n + 1.
    """
    residuos = np.asarray(residuos, dtype=float)
    fold_residuo = np.asarray(fold_residuo)
    m = pred_fold.shape[1]
    lo, hi = np.empty(m), np.empty(m)
    alfa = (1 - nivel) / 2
    if clave_residuo is None:
        clave_residuo, clave_nueva = np.zeros(len(residuos)), np.zeros(m)
    clave_residuo, clave_nueva = np.asarray(clave_residuo), np.asarray(clave_nueva)
    for g in np.unique(clave_nueva):
        sel = clave_residuo == g
        if sel.sum() < 2:
            sel = np.ones(len(residuos), dtype=bool)
        for j in np.flatnonzero(clave_nueva == g):
            v = np.sort(pred_fold[fold_residuo[sel], j] + residuos[sel])
            a, b = _indices_cola(len(v), alfa)
            lo[j], hi[j] = v[a], v[b]
    return lo, hi


# ------------------------------------------------- validación anidada (cobertura)

METODOS = {
    "global": dict(agrupar="ninguno", tamano="ninguno"),
    "regimen": dict(agrupar="regimen", tamano="ninguno"),
    "regimen_tamano": dict(agrupar="regimen", tamano="mediana"),
    "regimen_escala": dict(agrupar="regimen", tamano="escala"),
}


def _un_fold_externo(modelo, X, y, tr, te, k_interno, semilla):
    """Para un fold externo calcula los intervalos de todos los métodos."""
    Xtr, ytr, Xte = X.iloc[tr], y.iloc[tr], X.iloc[te]
    pred_te = np.asarray(clone(modelo).fit(Xtr, ytr).predict(Xte), dtype=float).ravel()
    skf = StratifiedKFold(k_interno, shuffle=True, random_state=semilla)
    oof = np.empty(len(tr))
    fold = np.empty(len(tr), dtype=int)
    pred_fold = np.empty((k_interno, len(te)))
    for k, (a, b) in enumerate(skf.split(Xtr, Xtr["regimen"].astype(str))):
        m = clone(modelo).fit(Xtr.iloc[a], ytr.iloc[a])
        oof[b] = np.asarray(m.predict(Xtr.iloc[b]), dtype=float).ravel()
        fold[b] = k
        pred_fold[k] = np.asarray(m.predict(Xte), dtype=float).ravel()
    res = ytr.to_numpy() - oof
    reg_tr, ar_tr = Xtr["regimen"].to_numpy(), Xtr["area_ha"].to_numpy()
    reg_te, ar_te = Xte["regimen"].to_numpy(), Xte["area_ha"].to_numpy()
    intervalos = {n: CalibradorIntervalo(**kw).fit(res, reg_tr, ar_tr).intervalo(
        pred_te, reg_te, ar_te) for n, kw in METODOS.items()}
    intervalos["cvmas_global"] = cvmas(pred_fold, res, fold)
    intervalos["cvmas_regimen"] = cvmas(pred_fold, res, fold, reg_tr, reg_te)
    return pd.concat([pd.DataFrame({
        "metodo": n, "ID_POLIGONO": Xte.index, "y": y.iloc[te].to_numpy(), "pred": pred_te,
        "p10": lo, "p90": hi, "regimen": reg_te, "area_ha": ar_te})
        for n, (lo, hi) in intervalos.items()], ignore_index=True)


def evaluar_cobertura(modelo, X, y, repeticiones=5, k_interno=5, n_jobs=8):
    """Cobertura de p10 a p90 con validación cruzada anidada (esquema A).

    En cada fold externo la parcela de prueba no participa ni en el ajuste del modelo ni
    en la calibración. Los residuos de calibración salen de una validación interna de
    `k_interno` folds sobre el entrenamiento externo. Devuelve una fila por método,
    repetición y parcela, con `cubierto` y `ancho`.
    """
    X = X.sort_index()
    y = y.loc[X.index]
    parts = cv.particiones_A(X)
    pos = pd.Series(np.arange(len(X)), index=X.index)
    tareas = []
    for r in range(repeticiones):
        pr = parts[parts["repeticion"] == r]
        for f in sorted(pr["fold"].unique()):
            te = pos[pr.loc[pr["fold"] == f, "ID_POLIGONO"]].to_numpy()
            tareas.append((r, np.setdiff1d(np.arange(len(X)), te), te, SEED + 100 * r + int(f)))
    out = Parallel(n_jobs=n_jobs)(
        delayed(_un_fold_externo)(modelo, X, y, tr, te, k_interno, s) for _, tr, te, s in tareas)
    df = pd.concat([o.assign(repeticion=t[0]) for o, t in zip(out, tareas)], ignore_index=True)
    df["cubierto"] = (df["y"] >= df["p10"]) & (df["y"] <= df["p90"])
    df["ancho"] = df["p90"] - df["p10"]
    return df


def cuartil_area(df):
    """Serie 'Q1'..'Q4' con el cuartil de área de cada fila (cuartiles sobre parcelas únicas)."""
    q = df.drop_duplicates("ID_POLIGONO")["area_ha"].quantile([0.25, 0.5, 0.75]).to_numpy()
    return pd.Series("Q" + (np.searchsorted(q, df["area_ha"].to_numpy(), side="left") + 1).astype(str),
                     index=df.index)


def resumen_cobertura(df):
    """Cobertura y ancho medio por método y grupo (global, régimen y cuartil de área)."""
    d = df.assign(cuartil_area=cuartil_area(df))
    filas = []
    for tipo, col in (("global", None), ("regimen", "regimen"), ("cuartil_area", "cuartil_area")):
        grupos = [("todas", d)] if col is None else list(d.groupby(col))
        for nombre, sub in grupos:
            for metodo, s in sub.groupby("metodo"):
                filas.append({"metodo": metodo, "tipo": tipo, "grupo": nombre,
                              "n": s["ID_POLIGONO"].nunique(),
                              "cobertura": float(s["cubierto"].mean()),
                              "ancho_medio": float(s["ancho"].mean())})
    return pd.DataFrame(filas)
