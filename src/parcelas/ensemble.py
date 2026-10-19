"""Promedio de modelos y construcción del modelo final.

El promedio no entrena ningún meta-modelo. Cada miembro se ajusta por separado con los
mismos datos y la predicción es la media simple o ponderada con pesos fijos. Los pesos no
se aprenden, así que no hay stacking. Si se eligen mirando la misma validación cruzada
habría sesgo de selección, por eso el valor por defecto es el promedio simple.
"""
import json

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin, clone

from .config import ANALISIS_PARCELAS
from .modelos import _json_np, _kw_pesos, desde_config

ARCHIVO_MODELO_FINAL = ANALISIS_PARCELAS / "modelo_final.json"


class PromedioModelos(BaseEstimator, RegressorMixin):
    """Promedio simple o ponderado (pesos fijos) de estimadores sklearn.

    modelos: lista de estimadores que reciben el DataFrame completo, como los de
      `modelos.construir_modelo`. Se clonan en `fit`.
    pesos: None para el promedio simple, o una secuencia no negativa con un peso por
      modelo. Se normaliza para que sume 1.
    """

    def __init__(self, modelos=None, pesos=None):
        self.modelos = modelos
        self.pesos = pesos

    def _pesos(self):
        n = len(self.modelos)
        if self.pesos is None:
            return np.full(n, 1.0 / n)
        w = np.asarray(self.pesos, dtype=float)
        if w.shape != (n,) or (w < 0).any() or w.sum() <= 0:
            raise ValueError("pesos debe tener un valor no negativo por modelo y suma positiva")
        return w / w.sum()

    def fit(self, X, y, sample_weight=None):
        if not self.modelos:
            raise ValueError("Se necesita al menos un modelo")
        self._pesos()  # valida
        self.modelos_ = [clone(m).fit(X, y, **_kw_pesos(m, sample_weight)) for m in self.modelos]
        return self

    def predicciones_miembros(self, X):
        """Matriz (filas x modelos) con la predicción de cada miembro."""
        return np.column_stack([np.asarray(m.predict(X), dtype=float).ravel()
                                for m in self.modelos_])

    def predict(self, X):
        return self.predicciones_miembros(X) @ self._pesos()


# ------------------------------------------------------------------- candidato

def construir_desde_config(cfg):
    """Modelo sin entrenar desde la configuración del candidato.

    Si `cfg["tipo"]` es "ensemble" arma un `PromedioModelos` con los dicts de `miembros`
    (cada uno en el formato de `modelos.desde_config`) y los `pesos` opcionales. En otro
    caso es un modelo individual y se construye con `modelos.desde_config`.
    """
    if cfg.get("tipo") == "ensemble":
        return PromedioModelos([desde_config(m) for m in cfg["miembros"]], cfg.get("pesos"))
    return desde_config(cfg)


def guardar_configuracion_final(cfg, ruta=ARCHIVO_MODELO_FINAL):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(cfg, indent=2, ensure_ascii=False, default=_json_np),
                    encoding="utf-8")


def configuracion_final(ruta=ARCHIVO_MODELO_FINAL):
    return json.loads(ruta.read_text(encoding="utf-8"))


def modelo_final(ruta=ARCHIVO_MODELO_FINAL):
    """Reconstruye (sin entrenar) el modelo final desde su JSON, sin el intervalo."""
    return construir_desde_config(configuracion_final(ruta))
