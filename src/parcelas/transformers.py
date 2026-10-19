"""Transformadores y estimadores sencillos compatibles con sklearn.

Todo lo que usa el rendimiento (y) aprende solo en `fit`, que en la validación cruzada
recibe únicamente el fold de entrenamiento. En `fit_transform` los codificadores calculan
sus valores dejando fuera a cada parcela (leave-one-out) para que las variables de
entrenamiento no contengan su propia etiqueta.
"""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, TransformerMixin


class SeleccionColumnas(BaseEstimator, TransformerMixin):
    """Conserva solo las columnas indicadas y las entrega como arreglo numérico.

    Si `columnas` es None, conserva todas las columnas numéricas del DataFrame.
    """

    def __init__(self, columnas=None):
        self.columnas = columnas

    def fit(self, X, y=None):
        if self.columnas is None:
            self.columnas_ = list(X.select_dtypes("number").columns)
        else:
            self.columnas_ = list(self.columnas)
        faltan = [c for c in self.columnas_ if c not in X.columns]
        if faltan:
            raise KeyError(f"Faltan columnas: {faltan}")
        return self

    def transform(self, X):
        return X[self.columnas_].to_numpy(dtype=float)

    def get_feature_names_out(self, input_features=None):
        return np.array(self.columnas_)


class TargetEncoderGrupo(BaseEstimator, TransformerMixin):
    """Media de y por grupo con suavizado bayesiano hacia la media global.

    valor = (n * media_grupo + suavizado * media_global) / (n + suavizado)
    Las categorías no vistas reciben la media global. Con suavizado=0 es la media simple
    del grupo.
    """

    def __init__(self, columna, suavizado=5.0):
        self.columna = columna
        self.suavizado = suavizado

    def fit(self, X, y):
        y = np.asarray(y, dtype=float)
        g = np.asarray(X[self.columna])
        self.media_global_ = float(y.mean())
        codigos, categorias = pd.factorize(g)
        self.suma_ = pd.Series(np.bincount(codigos, weights=y), index=categorias)
        self.cuenta_ = pd.Series(np.bincount(codigos), index=categorias).astype(float)
        self.mapa_ = (self.suma_ + self.suavizado * self.media_global_) / (self.cuenta_ + self.suavizado)
        return self

    def transform(self, X):
        g = pd.Series(np.asarray(X[self.columna]))
        return g.map(self.mapa_).fillna(self.media_global_).to_numpy(dtype=float).reshape(-1, 1)

    def fit_transform(self, X, y=None, **kw):
        """Codificación leave-one-out de las filas de entrenamiento."""
        self.fit(X, y)
        y = np.asarray(y, dtype=float)
        g = pd.Series(np.asarray(X[self.columna]))
        n = g.map(self.cuenta_).to_numpy(dtype=float)
        s = g.map(self.suma_).to_numpy(dtype=float)
        # Media global sin la propia fila, para no filtrar su etiqueta
        mg = (y.sum() - y) / max(len(y) - 1, 1)
        den = (n - 1) + self.suavizado
        with np.errstate(divide="ignore", invalid="ignore"):
            val = np.where(den > 0, ((s - y) + self.suavizado * mg) / den, mg)
        return val.reshape(-1, 1)

    def get_feature_names_out(self, input_features=None):
        return np.array([f"te_{self.columna}"])


class MediaPorGrupo(BaseEstimator, RegressorMixin):
    """Predice la media (suavizada) de y del grupo de cada parcela. Base de comparación."""

    def __init__(self, columna=None, suavizado=0.0):
        self.columna = columna
        self.suavizado = suavizado

    def fit(self, X, y):
        if self.columna is None:
            self.media_ = float(np.mean(y))
            self.codificador_ = None
        else:
            self.codificador_ = TargetEncoderGrupo(self.columna, self.suavizado).fit(X, y)
        return self

    def predict(self, X):
        if self.codificador_ is None:
            return np.full(len(X), self.media_)
        return self.codificador_.transform(X).ravel()


class RezagoEspacial(BaseEstimator, TransformerMixin):
    """Rendimiento de los vecinos de entrenamiento, ponderado por inverso de la distancia.

    Parámetros
      k: número máximo de vecinos.
      radio_m: si se da, solo cuentan los vecinos a esa distancia o menos. Si una parcela no
        tiene ninguno, recibe la media del régimen del fold de entrenamiento (en
        `fit_transform`, sin su propia etiqueta).
      mismo_regimen: restringe los vecinos al régimen de la parcela (columna `regimen`).
      potencia: peso = 1 / distancia ** potencia.

    Usa las columnas `x_m` y `y_m` (metros). Devuelve tres columnas: rezago, número de
    vecinos usados y distancia al vecino más cercano. En `fit_transform` cada parcela se
    excluye a sí misma (leave-one-out). En `transform` cuentan todas las de entrenamiento.
    """

    def __init__(self, k=10, radio_m=None, mismo_regimen=False, potencia=1):
        self.k = k
        self.radio_m = radio_m
        self.mismo_regimen = mismo_regimen
        self.potencia = potencia

    def fit(self, X, y):
        self.xy_ = X[["x_m", "y_m"]].to_numpy(dtype=float)
        self.y_ = np.asarray(y, dtype=float)
        self.reg_ = np.asarray(X["regimen"]) if "regimen" in X.columns else np.full(len(X), "")
        self.media_global_ = float(self.y_.mean())
        self.media_reg_ = {r: float(self.y_[self.reg_ == r].mean()) for r in np.unique(self.reg_)}
        return self

    def _calcular(self, X, excluir_propia):
        q = X[["x_m", "y_m"]].to_numpy(dtype=float)
        rq = np.asarray(X["regimen"]) if "regimen" in X.columns else np.full(len(X), "")
        d = np.sqrt(((q[:, None, :] - self.xy_[None, :, :]) ** 2).sum(-1))
        if excluir_propia:
            np.fill_diagonal(d, np.inf)
        if self.mismo_regimen:
            d = np.where(rq[:, None] == self.reg_[None, :], d, np.inf)
        if self.radio_m is not None:
            d = np.where(d <= self.radio_m, d, np.inf)
        k = min(self.k, d.shape[1])
        idx = np.argsort(d, axis=1)[:, :k]
        dk = np.take_along_axis(d, idx, axis=1)
        valido = np.isfinite(dk)
        w = np.where(valido, 1.0 / np.maximum(dk, 1.0) ** self.potencia, 0.0)
        yk = self.y_[idx]
        sw = w.sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            reza = (w * yk).sum(1) / sw
        sin = sw == 0
        if sin.any():
            if excluir_propia:
                # Media del régimen sin la propia etiqueta, para no filtrarla en el relleno
                relleno = np.empty(len(rq))
                for i, r in enumerate(rq):
                    m = self.reg_ == r
                    m[i] = False
                    if not m.any():
                        m = np.ones(len(self.y_), dtype=bool)
                        m[i] = False
                    relleno[i] = self.y_[m].mean() if m.any() else self.media_global_
            else:
                relleno = np.array([self.media_reg_.get(r, self.media_global_) for r in rq])
            reza = np.where(sin, relleno, reza)
        n = valido.sum(1)
        dmin = np.where(n > 0, np.where(valido, dk, np.inf).min(1), np.nan)
        if self.radio_m is not None:
            dmin = np.where(n > 0, dmin, self.radio_m)
        return np.column_stack([reza, n, dmin])

    def transform(self, X):
        return self._calcular(X, excluir_propia=False)

    def fit_transform(self, X, y=None, **kw):
        self.fit(X, y)
        return self._calcular(X, excluir_propia=True)

    def get_feature_names_out(self, input_features=None):
        return np.array(["rezago_y", "rezago_n_vecinos", "rezago_dist_min_m"])
