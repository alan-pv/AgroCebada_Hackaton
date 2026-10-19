import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import Ridge

from parcelas import ensemble, intervalos
from parcelas.config import PROCESSED


@pytest.fixture(scope="module")
def datos():
    f = pd.read_parquet(PROCESSED / "features.parquet").set_index("ID_POLIGONO")
    p = pd.read_parquet(PROCESSED / "parcelas.parquet").set_index("ID_POLIGONO")
    d = f.join(p[["rendimiento"]]).sort_index()
    t = d[d["conjunto"] == "ENTRENAMIENTO"]
    return t.drop(columns="rendimiento"), t["rendimiento"]


def test_promedio_de_un_modelo_es_el_modelo(datos):
    from parcelas import modelos
    X, y = datos
    m = modelos.construir_modelo("ridge", [], contexto=("regimen",))
    solo = ensemble.PromedioModelos([m]).fit(X, y)
    np.testing.assert_allclose(solo.predict(X), m.fit(X, y).predict(X))


def test_promedio_simple_y_ponderado():
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(50, 2)), columns=["a", "b"])
    y = X["a"] * 2 + rng.normal(size=50) * 0.1
    a, b = Ridge(alpha=0.1), Ridge(alpha=100.0)
    pa, pb = (clone_fit(a, X, y), clone_fit(b, X, y))
    np.testing.assert_allclose(ensemble.PromedioModelos([a, b]).fit(X, y).predict(X),
                               (pa + pb) / 2)
    np.testing.assert_allclose(ensemble.PromedioModelos([a, b], [3, 1]).fit(X, y).predict(X),
                               0.75 * pa + 0.25 * pb)
    with pytest.raises(ValueError):
        ensemble.PromedioModelos([a, b], [1.0]).fit(X, y)


def clone_fit(m, X, y):
    from sklearn.base import clone
    return clone(m).fit(X, y).predict(X)


def test_cobertura_conformal_sintetica():
    rng = np.random.default_rng(1)
    cubiertos = []
    for _ in range(300):
        r = rng.normal(0, 0.5, 120)
        cal = intervalos.CalibradorIntervalo(agrupar="ninguno").fit(
            r, np.array(["A"] * 120), np.full(120, 2.0))
        nuevo = rng.normal(0, 0.5, 20)
        lo, hi = cal.intervalo(np.zeros(20), np.array(["A"] * 20), np.full(20, 2.0))
        cubiertos.extend((nuevo >= lo) & (nuevo <= hi))
    assert abs(np.mean(cubiertos) - 0.8) < 0.03


def test_mondrian_ajusta_cada_regimen():
    rng = np.random.default_rng(2)
    reg = np.array(["A"] * 200 + ["B"] * 200)
    r = np.where(reg == "A", rng.normal(0, 1.0, 400), rng.normal(0, 0.2, 400))
    cal = intervalos.CalibradorIntervalo(agrupar="regimen").fit(r, reg, np.full(400, 1.0))
    lo, hi = cal.intervalo(np.zeros(2), np.array(["A", "B"]), np.ones(2))
    assert (hi - lo)[0] > 3 * (hi - lo)[1]


def test_prob_bajo_umbral_monotona():
    r = np.random.default_rng(3).normal(0, 0.5, 200)
    p = [intervalos.prob_bajo_umbral(3.0, r, u) for u in np.linspace(1.5, 4.5, 31)]
    assert all(b >= a for a, b in zip(p, p[1:]))
    assert p[0] < 0.05 and p[-1] > 0.95
    # y baja cuando la predicción sube
    q = [intervalos.prob_bajo_umbral(m, r, 2.5) for m in np.linspace(2, 4, 11)]
    assert all(b <= a for a, b in zip(q, q[1:]))


def test_candidato_v2_se_reconstruye():
    if not ensemble.ARCHIVO_CANDIDATO_V2.exists():
        pytest.skip("candidato_v2.json no generado")
    assert hasattr(ensemble.candidato_v2(), "fit")
