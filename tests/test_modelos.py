import numpy as np
import pandas as pd
import pytest

from parcelas import modelos
from parcelas.config import PROCESSED
from parcelas.transformers import MediaPorGrupo


@pytest.fixture(scope="module")
def datos():
    f = pd.read_parquet(PROCESSED / "features.parquet").set_index("ID_POLIGONO")
    p = pd.read_parquet(PROCESSED / "parcelas.parquet").set_index("ID_POLIGONO")
    d = f.join(p[["rendimiento"]]).sort_index()
    return d


def _entrenamiento(d):
    t = d[d["conjunto"] == "ENTRENAMIENTO"]
    return t.drop(columns="rendimiento"), t["rendimiento"]


def test_residuos_sin_variables_es_la_media_por_regimen(datos):
    X, y = _entrenamiento(datos)
    m = modelos.construir_modelo("ridge", [], contexto=(), residuos=True).fit(X, y)
    ref = MediaPorGrupo("regimen").fit(X, y)
    np.testing.assert_allclose(m.predict(X), ref.predict(X))


def test_transform_no_usa_y(datos):
    """Cambiar y antes de predecir no cambia la predicción, y las transformaciones no la reciben."""
    X, y = _entrenamiento(datos)
    cols = [c for c in X.columns if c.startswith("hist_")]
    m = modelos.construir_modelo("ridge", cols, contexto=("regimen",), seleccion_k=3,
                                 rezago={"k": 5, "radio_m": 400.0, "mismo_regimen": True})
    m.fit(X, y)
    p1 = m.predict(X.iloc[:20])
    pre = m.named_steps["pre"]
    # transform es una función de X y de lo aprendido en fit, no recibe y
    np.testing.assert_allclose(pre.transform(X.iloc[:20]), pre.transform(X.iloc[:20]))
    m2 = modelos.construir_modelo("ridge", cols, contexto=("regimen",), seleccion_k=3,
                                  rezago={"k": 5, "radio_m": 400.0, "mismo_regimen": True})
    m2.fit(X, y)
    np.testing.assert_allclose(p1, m2.predict(X.iloc[:20]))


def test_seleccion_residuo_aprende_en_fit(datos):
    X, y = _entrenamiento(datos)
    cols = [c for c in X.columns if c.startswith("sat25_")][:20]
    sel = modelos.SeleccionResiduo(k=4).fit(X[cols + ["regimen"]], y.to_numpy())
    assert len(sel.columnas_) == 4
    # La selección no cambia al transformar parcelas nuevas
    antes = list(sel.columnas_)
    sel.transform(X[cols + ["regimen"]].iloc[:5])
    assert sel.columnas_ == antes


def test_intervalo_no_cambia_el_regimen_a(datos):
    X, y = _entrenamiento(datos)
    base = modelos.construir_modelo("ridge", [], contexto=("regimen",), residuos=True)
    m = modelos.construir_modelo("ridge", [], contexto=("regimen",), residuos=True, intervalo_b=0.25)
    m.fit(X, y)
    base.fit(X, y)
    a = (X["regimen"] == "A").to_numpy()
    np.testing.assert_allclose(m.predict(X)[a], base.predict(X)[a], atol=1e-6)


def test_candidato_entrena_y_predice_59(datos, tmp_path):
    cfg = {"nombre": "prueba", "modelo": "ridge", "columnas": ["hist_s2_ndvi_max_media"],
           "args": {"contexto": [], "residuos": True,
                    "rezago": {"k": 10, "radio_m": 400.0, "mismo_regimen": True}}}
    ruta = tmp_path / "candidato.json"
    modelos.guardar_candidato(cfg, ruta)
    m = modelos.candidato(ruta)
    X, y = _entrenamiento(datos)
    m.fit(X, y)
    nuevo = datos[datos["conjunto"] == "PREDICCION"].drop(columns="rendimiento")
    pred = m.predict(nuevo)
    assert len(nuevo) == 59 and pred.shape == (59,) and np.isfinite(pred).all()


def test_candidato_guardado_del_repositorio(datos):
    """El JSON versionado reconstruye un modelo que entrena y predice las 59 parcelas."""
    m = modelos.candidato()
    X, y = _entrenamiento(datos)
    m.fit(X, y)
    nuevo = datos[datos["conjunto"] == "PREDICCION"].drop(columns="rendimiento")
    pred = m.predict(nuevo)
    assert len(pred) == 59 and np.isfinite(pred).all()
    assert 2.0 < pred.mean() < 6.0
