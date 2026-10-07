import numpy as np
import pandas as pd
import pytest

from agrocebada import interpretabilidad as I
from agrocebada.config import PROCESSED


def _datos(n=120, semilla=0):
    rng = np.random.default_rng(semilla)
    mun = np.repeat(["m1", "m2", "m3", "m4", "m5", "m6"], n // 6)
    X = pd.DataFrame({
        "municipio": mun,
        "regimen": np.where(np.isin(mun, ["m1", "m2", "m3"]), "A", "B"),
        "x_m": rng.uniform(0, 1e4, n), "y_m": rng.uniform(0, 1e4, n),
        "senal": rng.normal(size=n),
        "ruido_1": rng.normal(size=n), "ruido_2": rng.normal(size=n)},
        index=[f"P{i:03d}" for i in range(n)])
    y = pd.Series(3 + 1.5 * X["senal"] + rng.normal(scale=0.2, size=n), index=X.index)
    return X, y


def test_grupo_de_ruido_puro_tiene_importancia_cercana_a_cero():
    X, y = _datos()
    cols = ["senal", "ruido_1", "ruido_2"]
    m = I.modelo_analisis("ridge", cols, regimen=False)
    r = I.importancia_permutacion(m, X, y, {"senal": ["senal"], "ruido": ["ruido_1", "ruido_2"]},
                                  repeticiones=3, n_perm=5, dentro_de=None)["todas"].set_index("grupo")
    assert r.loc["senal", "importancia_media"] > 0.5
    assert abs(r.loc["ruido", "importancia_media"]) < 0.05


def test_la_permutacion_no_modifica_los_datos_de_entrada():
    X, y = _datos()
    copia = X.copy()
    m = I.modelo_analisis("ridge", ["senal", "ruido_1"], regimen=False)
    I.importancia_permutacion(m, X, y, {"g": ["senal"]}, repeticiones=1, n_perm=2, dentro_de=None)
    pd.testing.assert_frame_equal(X, copia)


def test_agrupacion_por_indice_cubre_todas_las_columnas_satelitales():
    cols = list(pd.read_parquet(PROCESSED / "features.parquet").columns)
    sat = I.columnas_satelitales(cols)
    g = I.grupos_indice(cols)
    cubiertas = [c for cs in g.values() for c in cs]
    assert sorted(cubiertas) == sorted(sat)
    assert len(cubiertas) == len(set(cubiertas))
    assert {"NDVI", "NDRE", "EVI"} <= set(g)
    assert sorted(c for cs in I.grupos_indice(cols, por_sensor=True).values() for c in cs) == sorted(sat)


def test_no_quedan_indices_duplicados_de_la_tabla_iv():
    cols = list(pd.read_parquet(PROCESSED / "features.parquet").columns)
    assert I.verificar_sin_duplicados(cols) == []


def test_grupos_de_clima_cubren_el_bloque():
    cols = [c for c in pd.read_parquet(PROCESSED / "features.parquet").columns if c.startswith("clima_")]
    g = I.grupos_clima(cols)
    assert set(g) == {"Lluvia", "Tmax", "Tmin", "Amplitud térmica", "Grados-día"}
    assert sorted(c for cs in g.values() for c in cs) == sorted(cols)
