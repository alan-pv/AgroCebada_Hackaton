"""Fábrica de modelos del proyecto.

Todos los modelos reciben el DataFrame completo (columnas de parcelas más variables) y
hacen dentro de `fit` todo lo que toca el rendimiento: codificación del contexto, rezago
espacial, selección de variables, imputación, escalado y regresor. Así la validación
cruzada de `cv.evaluate` no filtra información del fold de prueba.

Dos formas de modelar
  Enfoque único. Un solo regresor explica el rendimiento con el contexto y las variables.
  Modelo de residuos. Se resta la media por régimen (calculada en el fold) y un regresor
    explica solo el residuo. Sin variables ni contexto equivale a la media por régimen.
"""
import json

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, TransformerMixin, clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNetCV, HuberRegressor, Ridge, RidgeCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from .config import EXPERIMENTOS, SEED
from .transformers import RezagoEspacial, TargetEncoderGrupo

ARCHIVO_CANDIDATO = EXPERIMENTOS / "candidato_v1.json"
ALFAS = np.logspace(-1, 3.5, 12)


# ------------------------------------------------------------------ componentes

class SeleccionResiduo(BaseEstimator, TransformerMixin):
    """Elige las k columnas más correlacionadas con el residuo de la media por grupo.

    Recibe un DataFrame con las columnas candidatas y la columna `grupo`. En `fit` calcula
    el residuo de y respecto a la media de su grupo, rellena los vacíos con la mediana y
    conserva las k columnas con mayor |r| de Pearson. Con `criterio="y"` usa y directo.
    Devuelve las columnas elegidas como arreglo (los vacíos se conservan). Con
    `salida="df"` devuelve un DataFrame que además conserva la columna del grupo.
    """

    def __init__(self, k=15, grupo="regimen", criterio="residuo", salida="array"):
        self.k = k
        self.grupo = grupo
        self.criterio = criterio
        self.salida = salida

    def fit(self, X, y):
        y = np.asarray(y, dtype=float)
        g = X[self.grupo].to_numpy()
        obj = y - pd.Series(y).groupby(g).transform("mean").to_numpy() if self.criterio == "residuo" else y
        cols = [c for c in X.columns if c != self.grupo]
        M = X[cols].to_numpy(dtype=float)
        M = np.where(np.isnan(M), np.nanmedian(M, axis=0), M)
        Mc = M - M.mean(0)
        oc = obj - obj.mean()
        den = np.sqrt((Mc ** 2).sum(0) * (oc ** 2).sum())
        with np.errstate(invalid="ignore", divide="ignore"):
            r = np.abs((Mc * oc[:, None]).sum(0) / den)
        r = np.nan_to_num(r)
        orden = np.argsort(-r, kind="stable")[: min(self.k, len(cols))]
        self.columnas_ = [cols[i] for i in sorted(orden)]
        self.correlaciones_ = pd.Series(r, index=cols)
        return self

    def transform(self, X):
        if self.salida == "df":
            return X[self.columnas_ + [self.grupo]]
        return X[self.columnas_].to_numpy(dtype=float)


class ZPorRegimen(BaseEstimator, TransformerMixin):
    """Estandariza cada variable dentro de su grupo y la separa en un bloque por grupo.

    Para p variables y g grupos entrega p * g columnas. El bloque de un grupo vale
    (x - mediana del grupo) / desviación del grupo en las parcelas de ese grupo, y cero en
    las demás. Los vacíos quedan en cero. Con un modelo lineal equivale a una pendiente
    propia por régimen y a un nivel que ya no depende de las diferencias entre regímenes.
    La mediana y la desviación se aprenden en `fit`. Recibe un DataFrame con la columna
    del grupo.
    """

    def __init__(self, grupo="regimen"):
        self.grupo = grupo

    def fit(self, X, y=None):
        self.columnas_ = [c for c in X.columns if c != self.grupo]
        g = X[self.grupo].to_numpy()
        self.grupos_ = sorted(pd.unique(g))
        self.med_, self.dev_ = {}, {}
        for r in self.grupos_:
            M = X.loc[g == r, self.columnas_].to_numpy(dtype=float)
            med = np.nanmedian(M, axis=0)
            dev = np.nanstd(M, axis=0)
            self.med_[r] = np.nan_to_num(med)
            self.dev_[r] = np.where(np.nan_to_num(dev) > 0, dev, 1.0)
        return self

    def transform(self, X):
        g = X[self.grupo].to_numpy()
        M = X[self.columnas_].to_numpy(dtype=float)
        bloques = []
        for r in self.grupos_:
            Z = np.nan_to_num((M - self.med_[r]) / self.dev_[r])
            bloques.append(Z * (g == r)[:, None])
        return np.hstack(bloques)


class ModeloResiduos(BaseEstimator, RegressorMixin):
    """Media del grupo (régimen) más un regresor que explica el residuo.

    `interno` es un estimador sklearn que recibe el DataFrame completo, o None. Sin
    estimador interno predice la media del grupo. El residuo se calcula en `fit` con el
    fold de entrenamiento, y se pasa como y al estimador interno.
    """

    def __init__(self, interno=None, grupo="regimen"):
        self.interno = interno
        self.grupo = grupo

    def fit(self, X, y, sample_weight=None):
        y = np.asarray(y, dtype=float)
        self.media_ = TargetEncoderGrupo(self.grupo, 0.0).fit(X, y)
        if self.interno is not None:
            r = y - self.media_.transform(X).ravel()
            self.interno_ = clone(self.interno).fit(X, r, **_kw_pesos(self.interno, sample_weight))
        return self

    def predict(self, X):
        base = self.media_.transform(X).ravel()
        if self.interno is None:
            return base
        return base + np.asarray(self.interno_.predict(X), dtype=float).ravel()


class AjusteIntervalo(BaseEstimator, RegressorMixin):
    """Entrena tratando la etiqueta de un grupo como un intervalo ±tol.

    En el régimen B los productores redondean a 0.5 o 0.1, así que el valor real puede
    estar hasta 0.25 t/ha de la etiqueta. En cada iteración se ajusta el modelo, se
    predice sobre el entrenamiento y la etiqueta de las parcelas del grupo se acerca a la
    predicción hasta tol (se mueve y - clip(y - pred, -tol, tol)). Si la predicción cae
    dentro del intervalo, el residuo queda en cero. Equivale a una pérdida con zona
    muerta. Las parcelas de otros grupos conservan su etiqueta. La evaluación siempre usa
    la etiqueta original.
    """

    def __init__(self, base=None, tol=0.25, columna="regimen", valor="B", iteraciones=3):
        self.base = base
        self.tol = tol
        self.columna = columna
        self.valor = valor
        self.iteraciones = iteraciones

    def fit(self, X, y, sample_weight=None):
        y = np.asarray(y, dtype=float)
        mask = (X[self.columna] == self.valor).to_numpy()
        kw = _kw_pesos(self.base, sample_weight)
        yaj = y.copy()
        for _ in range(self.iteraciones):
            m = clone(self.base).fit(X, yaj, **kw)
            p = np.asarray(m.predict(X), dtype=float).ravel()
            yaj = np.where(mask, y - np.clip(y - p, -self.tol, self.tol), y)
        self.modelo_ = clone(self.base).fit(X, yaj, **kw)
        return self

    def predict(self, X):
        return np.asarray(self.modelo_.predict(X), dtype=float).ravel()


def _kw_pesos(est, sample_weight):
    if sample_weight is None:
        return {}
    if hasattr(est, "steps"):
        return {f"{est.steps[-1][0]}__sample_weight": sample_weight}
    return {"sample_weight": sample_weight}


# --------------------------------------------------------------------- fábrica

def _regresor(nombre, params, lineal_escalado):
    p = dict(params)
    if nombre == "ridge":
        return Ridge(**p) if "alpha" in p else RidgeCV(alphas=p.pop("alphas", ALFAS))
    if nombre == "elasticnet":
        if "alpha" in p:
            from sklearn.linear_model import ElasticNet
            return ElasticNet(max_iter=5000, **p)
        return ElasticNetCV(l1_ratio=p.pop("l1_ratio", [0.2, 0.5, 0.9]), cv=5, max_iter=5000, **p)
    if nombre == "huber":
        p.setdefault("epsilon", 1.35)
        p.setdefault("alpha", 1.0)
        p.setdefault("max_iter", 1000)
        return HuberRegressor(**p)
    if nombre == "pls":
        from sklearn.cross_decomposition import PLSRegression
        p.setdefault("n_components", 2)
        return PLSRegression(scale=False, **p)
    if nombre == "rf":
        from sklearn.ensemble import RandomForestRegressor
        p.setdefault("n_estimators", 300)
        p.setdefault("max_depth", 4)
        p.setdefault("min_samples_leaf", 5)
        p.setdefault("max_features", 0.5)
        return RandomForestRegressor(random_state=SEED, n_jobs=1, **p)
    if nombre == "lgbm":
        from lightgbm import LGBMRegressor
        p.setdefault("n_estimators", 150)
        p.setdefault("learning_rate", 0.03)
        p.setdefault("max_depth", 3)
        p.setdefault("num_leaves", 6)
        p.setdefault("min_child_samples", 10)
        p.setdefault("subsample", 0.8)
        p.setdefault("subsample_freq", 1)
        p.setdefault("colsample_bytree", 0.7)
        p.setdefault("reg_lambda", 5.0)
        return LGBMRegressor(random_state=SEED, n_jobs=1, verbose=-1, **p)
    if nombre == "gp":
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
        kernel = ConstantKernel(0.1, (1e-3, 1e1)) * RBF(3.0, (0.5, 50.0)) + WhiteKernel(0.2, (1e-3, 1e1))
        return GaussianProcessRegressor(kernel, normalize_y=True, random_state=SEED, **p)
    if nombre == "tabpfn":
        try:
            from tabpfn import TabPFNRegressor
        except ImportError as e:
            raise ImportError("TabPFN no está instalado") from e
        return TabPFNRegressor(**p)
    raise ValueError(f"Modelo desconocido: {nombre}")


ESCALADOS = {"ridge", "elasticnet", "huber", "pls", "gp"}
CONTEXTOS = ("regimen", "estado", "municipio")


def _primera_columna(a):
    """Conserva solo el valor del rezago (la primera de las tres columnas de RezagoEspacial)."""
    return a[:, :1]


def _preprocesador(columnas, contexto, rezago, seleccion_k, escalar, codificacion, suavizado,
                   criterio, por_regimen):
    pasos = []
    for c in contexto:
        if codificacion == "te":
            pasos.append((f"ctx_{c}", TargetEncoderGrupo(c, suavizado), [c]))
        else:
            pasos.append((f"ctx_{c}", OneHotEncoder(handle_unknown="ignore", sparse_output=False), [c]))
    if rezago:
        rz = dict(rezago)
        solo_valor = rz.pop("solo_valor", False)
        sub = [RezagoEspacial(**rz)]
        if solo_valor:
            sub.append(FunctionTransformer(_primera_columna))
        if escalar:
            sub.append(StandardScaler())
        pasos.append(("rezago", Pipeline([(f"p{i}", s) for i, s in enumerate(sub)]),
                      ["x_m", "y_m", "regimen"]))
    columnas = list(columnas)
    if columnas:
        sub = []
        cols = columnas + ["regimen"] if (seleccion_k or por_regimen) else columnas
        if seleccion_k:
            sub.append(SeleccionResiduo(seleccion_k, "regimen", criterio,
                                        "df" if por_regimen else "array"))
        if por_regimen:
            sub.append(ZPorRegimen("regimen"))
        else:
            sub.append(SimpleImputer(strategy="median", keep_empty_features=True))
            if escalar:
                sub.append(StandardScaler())
        pasos.append(("vars", Pipeline([(f"p{i}", s) for i, s in enumerate(sub)]), cols))
    if not pasos:
        return None
    return ColumnTransformer(pasos, remainder="drop")


def construir_modelo(nombre, columnas, contexto=("regimen",), seleccion_k=None, rezago=None,
                     residuos=False, intervalo_b=None, codificacion="onehot", suavizado=1.0,
                     criterio="residuo", por_regimen=False, **params):
    """Devuelve un Pipeline sklearn que recibe el DataFrame completo.

    nombre: ridge, elasticnet, huber, pls, rf, lgbm, gp o tabpfn. Sin `alpha` (ridge,
      elasticnet) el alfa se elige dentro del fold por validación cruzada interna.
    columnas: variables numéricas del modelo.
    contexto: columnas categóricas (regimen, estado, municipio) codificadas con
      `codificacion` ("onehot" o "te", media de y suavizada con TargetEncoderGrupo).
    seleccion_k: si se da, conserva las k columnas más correlacionadas con el residuo de
      la media por régimen (`criterio="residuo"`) o con y (`criterio="y"`), dentro del fold.
    rezago: dict para `RezagoEspacial` (k, radio_m, mismo_regimen) o None. Con
      `solo_valor=True` el modelo ve solo el rezago, sin el número de vecinos ni la distancia.
    residuos: media por régimen más regresor del residuo. El contexto y el rezago ya
      operan sobre el residuo en ese caso.
    intervalo_b: si se da (p. ej. 0.25), trata la etiqueta del régimen B como intervalo.
    por_regimen: estandariza las variables dentro de cada régimen y les da un bloque de
      coeficientes por régimen (`ZPorRegimen`). Sustituye a la imputación y el escalado.
    params: hiperparámetros del regresor.
    """
    columnas = list(columnas)
    contexto = tuple(contexto)
    escalar = nombre in ESCALADOS
    pre = _preprocesador(columnas, contexto, rezago, seleccion_k, escalar, codificacion,
                         suavizado, criterio, por_regimen)
    reg = _regresor(nombre, params, escalar)
    if pre is None:
        interno = None
        if not residuos:
            raise ValueError("Un modelo sin columnas ni contexto requiere residuos=True")
    else:
        interno = Pipeline([("pre", pre), ("reg", _EnVector(reg))])
    if residuos:
        modelo = ModeloResiduos(interno)
    else:
        modelo = interno
    if intervalo_b:
        modelo = AjusteIntervalo(modelo, tol=intervalo_b)
    return modelo if isinstance(modelo, Pipeline) else Pipeline([("modelo", modelo)])


class _EnVector(BaseEstimator, RegressorMixin):
    """Envuelve un regresor para que predict devuelva siempre un vector (PLS devuelve 2D)."""

    def __init__(self, regresor=None):
        self.regresor = regresor

    def fit(self, X, y, sample_weight=None):
        kw = {} if sample_weight is None else {"sample_weight": sample_weight}
        self.regresor_ = clone(self.regresor).fit(X, y, **kw)
        return self

    def predict(self, X):
        return np.asarray(self.regresor_.predict(X), dtype=float).ravel()


# ------------------------------------------------------------------- candidato

def guardar_candidato(config, ruta=ARCHIVO_CANDIDATO):
    """Escribe la configuración (argumentos de `construir_modelo`) en JSON."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(config, indent=2, ensure_ascii=False, default=_json_np), encoding="utf-8")


def _json_np(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def configuracion_candidato(ruta=ARCHIVO_CANDIDATO):
    return json.loads(ruta.read_text(encoding="utf-8"))


def desde_config(cfg):
    """Construye un modelo (sin entrenar) desde un dict de configuración.

    Claves: `modelo` (nombre del algoritmo), `columnas`, y en `args` el resto de los
    argumentos de `construir_modelo` (contexto, rezago, residuos...) con los
    hiperparámetros del regresor en `args["params"]`.
    """
    args = dict(cfg.get("args", {}))
    params = args.pop("params", {})
    if args.get("contexto") is not None:
        args["contexto"] = tuple(args["contexto"])
    return construir_modelo(cfg["modelo"], cfg["columnas"], **args, **params)


def candidato(ruta=ARCHIVO_CANDIDATO):
    """Reconstruye (sin entrenar) el modelo candidato desde el JSON."""
    return desde_config(configuracion_candidato(ruta))
