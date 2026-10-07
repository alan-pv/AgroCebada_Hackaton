import numpy as np
import pandas as pd
import pytest
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import make_pipeline

from agrocebada import cv
from agrocebada.config import PROCESSED
from agrocebada.transformers import (MediaPorGrupo, RezagoEspacial, SeleccionColumnas,
                                     TargetEncoderGrupo)


@pytest.fixture(scope="module")
def datos():
    df = pd.read_parquet(PROCESSED / "parcelas.parquet")
    df = df[df["conjunto"] == "ENTRENAMIENTO"].set_index("ID_POLIGONO").sort_index()
    return df.drop(columns="rendimiento"), df["rendimiento"]


def test_particiones_deterministas_y_completas(datos):
    X, _ = datos
    a = cv.particiones_A(X.reset_index())
    b = cv.particiones_A(X.reset_index())
    pd.testing.assert_frame_equal(a, b)
    # Cada parcela aparece una vez por repetición
    assert (a.groupby("repeticion")["ID_POLIGONO"].nunique() == len(X)).all()
    assert a["repeticion"].nunique() == 10 and a["fold"].nunique() == 5


def test_particiones_estratificadas(datos):
    X, _ = datos
    est = cv.estratos(X)
    assert est.value_counts().min() >= cv.MIN_ESTRATO
    a = cv.particiones_A(X).merge(est.rename("estrato"), left_on="ID_POLIGONO", right_index=True)
    tabla = a.groupby(["repeticion", "estrato", "fold"]).size()
    por_estrato = tabla.groupby(["repeticion", "estrato"]).agg(lambda s: s.max() - s.min())
    assert por_estrato.max() <= 1  # reparto casi igual entre folds


def test_particiones_B_agrupan_clusters(datos):
    X, _ = datos
    b = cv.particiones_B(X).merge(cv.clusters_espaciales(X), left_on="ID_POLIGONO", right_index=True)
    assert (b.groupby(["repeticion", "cluster"])["fold"].nunique() == 1).all()


def test_archivo_particiones_coincide(datos):
    X, _ = datos
    guardado = pd.read_parquet(cv.ARCHIVO_PARTICIONES)
    a = guardado[guardado["esquema"] == "A"].drop(columns="esquema").reset_index(drop=True)
    pd.testing.assert_frame_equal(a, cv.particiones_A(X))


def test_target_encoder_sin_fuga_ni_categorias_nuevas():
    X = pd.DataFrame({"g": ["a", "a", "b", "b"]})
    y = np.array([1.0, 3.0, 5.0, 7.0])
    te = TargetEncoderGrupo("g", suavizado=0).fit(X, y)
    assert te.transform(pd.DataFrame({"g": ["a", "z"]})).ravel().tolist() == [2.0, 4.0]
    loo = TargetEncoderGrupo("g", suavizado=0).fit_transform(X, y).ravel()
    assert loo.tolist() == [3.0, 1.0, 7.0, 5.0]  # cada fila sin su propia etiqueta


def test_rezago_excluye_a_si_misma():
    X = pd.DataFrame({"x_m": [0.0, 100.0, 5000.0], "y_m": 0.0, "regimen": ["A", "A", "A"]})
    y = np.array([1.0, 3.0, 9.0])
    r = RezagoEspacial(k=1).fit_transform(X, y)
    assert r[:, 0] == pytest.approx([3.0, 1.0, 3.0])
    r2 = RezagoEspacial(k=1, radio_m=500).fit_transform(X, y)
    # sin vecinos, media del régimen sin su propia etiqueta
    assert r2[2, 0] == pytest.approx(np.mean([1.0, 3.0])) and r2[2, 1] == 0
    # en transform (parcelas nuevas) el relleno sí es la media completa del régimen
    nueva = pd.DataFrame({"x_m": [9000.0], "y_m": 0.0, "regimen": ["A"]})
    assert RezagoEspacial(k=1, radio_m=500).fit(X, y).transform(nueva)[0, 0] == pytest.approx(np.mean(y))


def test_sin_fuga_con_y_permutado(datos):
    """Con y revuelto, ningún modelo con y dentro del pipeline debe superar a la media."""
    X, y = datos
    yp = pd.Series(np.random.default_rng(0).permutation(y.to_numpy()), index=y.index)
    base = cv.evaluate(MediaPorGrupo(None), X, yp, "A", repeticiones=3).rmse
    for mod in (MediaPorGrupo("municipio", suavizado=0),
                make_pipeline(SeleccionColumnas(["x_m", "y_m"]), KNeighborsRegressor(5))):
        assert cv.evaluate(mod, X, yp, "A", repeticiones=3).rmse >= base * 0.97
    # Un rezago espacial como característica de un modelo lineal tampoco debe filtrar
    from sklearn.compose import ColumnTransformer
    from sklearn.linear_model import LinearRegression
    from sklearn.pipeline import Pipeline
    pipe = Pipeline([("rez", ColumnTransformer([("r", RezagoEspacial(k=5), ["x_m", "y_m", "regimen"])])),
                     ("lr", LinearRegression())])
    assert cv.evaluate(pipe, X, yp, "A", repeticiones=3).rmse >= base * 0.97


def test_evaluate_estructura(datos):
    X, y = datos
    r = cv.evaluate(MediaPorGrupo("regimen"), X, y, "AB", repeticiones=4)
    assert set(r) == {"A", "B"}
    a = r["A"]
    assert a.rmse_rep.shape == (4,) and a.rmse_fold.shape == (4, 5)
    assert not a.oof.isna().any().any()
    assert set(a.por_regimen) == {"A", "B"} and set(a.por_estado) == set(X["estado"])


def test_comparacion_emparejada_sintetica():
    class R:
        def __init__(self, v):
            self.rmse_rep = np.array(v)
    base = R([1.0] * 10)
    c = cv.comparacion_emparejada(R([0.9] * 7 + [1.1] * 3), base)
    assert c["victorias"] == 7 and c["aceptada"]
    c = cv.comparacion_emparejada(R([0.9] * 6 + [1.1] * 4), base)
    assert c["victorias"] == 6 and not c["aceptada"]
    assert c["diferencia_media"] == pytest.approx(-0.02)


def test_permutacion_detecta_senal_y_ruido(datos):
    X, y = datos
    X = X.copy()
    # Una columna de ruido puro contra una columna con señal
    X["ruido"] = np.random.default_rng(1).normal(size=len(X))
    mod_ruido = make_pipeline(SeleccionColumnas(["ruido"]), KNeighborsRegressor(5))
    p_ruido = cv.prueba_permutacion(mod_ruido, X, y, ["ruido"], n=19, repeticiones=3)["p"]
    # Una columna que sí informa dentro de cada régimen (y con algo de ruido)
    X["senal"] = y.to_numpy() + np.random.default_rng(2).normal(scale=0.2, size=len(X))
    mod_senal = make_pipeline(SeleccionColumnas(["senal"]), KNeighborsRegressor(5))
    p_senal = cv.prueba_permutacion(mod_senal, X, y, ["senal"], n=19, repeticiones=1)["p"]
    assert p_senal == pytest.approx(1 / 20)
    assert p_ruido > 0.1
