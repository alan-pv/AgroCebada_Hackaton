"""Pruebas del modelo generalizable con tablas sintéticas (no requieren los datos externos)."""
import numpy as np
import pandas as pd
import pytest

from generalizable import modelos as M
from generalizable import riesgo as R
from generalizable import siap
from generalizable import validacion as V


def tabla_sintetica(n_mun=30, anios=range(2005, 2025), pendiente=0.03, semilla=0):
    rng = np.random.default_rng(semilla)
    xy = rng.uniform(0, 200_000, (n_mun, 2))
    nivel = 2 + xy[:, 0] / 200_000
    filas = []
    for i in range(n_mun):
        for a in anios:
            filas.append({"CVEGEO": f"m{i:02d}", "estado": "E1" if i % 2 else "E2", "anio": a,
                          "x_m": xy[i, 0], "y_m": xy[i, 1],
                          "y": nivel[i] + pendiente * (a - 2025) + rng.normal(0, 0.3)})
    return pd.DataFrame(filas)


def test_normalizar_quita_acentos_y_mayusculas():
    assert siap.normalizar("Nanacamilpa de  Mariano Arista") == "nanacamilpa de mariano arista"
    assert siap.normalizar("Tecámac") == siap.normalizar("TECAMAC")


def test_limpiar_filtra_superficie_y_marca():
    df = pd.DataFrame({"anio": [2020, 2021, 2020], "estado": ["A"] * 3, "municipio": ["X", "X", "Y"],
                       "sembrada_ha": [100, 100, 10], "cosechada_ha": [100, 70, 10], "siniestrada_ha": [0, 30, 0],
                       "produccion_t": [200, 140, 30], "rendimiento": [2.0, 2.0, 3.0]})
    d = siap.limpiar(df, min_cosechada=50, min_anios=1)
    assert list(d.municipio) == ["X", "X"]
    assert d.rend_sembrada.tolist() == [2.0, 1.4]
    assert d.marca_siniestro.tolist() == [False, True]
    assert d.marca_entero.all()


def test_particiones_espaciales_no_parten_municipios():
    d = tabla_sintetica()
    mun = d.drop_duplicates("CVEGEO")[["CVEGEO", "x_m", "y_m"]].rename(columns={"CVEGEO": "clave"})
    g = V.grupos_espaciales(mun, n_grupos=8)
    reps = V.particiones_espaciales(d.CVEGEO, g, n_folds=4, n_rep=3)
    assert len(reps) == 3
    for folds in reps:
        assert (pd.Series(folds).groupby(d.CVEGEO.to_numpy()).nunique() == 1).all()
        assert len(np.unique(folds)) == 4
    # Determinista con la misma semilla
    reps2 = V.particiones_espaciales(d.CVEGEO, g, n_folds=4, n_rep=3)
    assert all((a == b).all() for a, b in zip(reps, reps2))


def test_pendiente_comun_recupera_la_tendencia():
    d = tabla_sintetica(pendiente=0.05)
    assert M.pendiente_comun(d, d.y.to_numpy()) == pytest.approx(0.05, abs=0.01)


def test_con_tendencia_mejora_media_propia_por_anio():
    d = tabla_sintetica(pendiente=0.08)
    y = d.y.to_numpy()
    reps = V.particiones_anio(d.anio)
    sin = V.evaluar(M.media_propia, d, y, reps, "sin").rmse_rep[0]
    con = V.evaluar(M.con_tendencia(M.media_propia), d, y, reps, "con").rmse_rep[0]
    assert con < sin


def test_idw_reproduce_un_punto_coincidente():
    xy = np.array([[0.0, 0.0], [10_000.0, 0.0]])
    v = np.array([1.0, 3.0])
    assert M._idw(xy, v, np.array([[5_000.0, 0.0]]))[0] == pytest.approx(2.0)
    assert M._idw(xy, v, np.array([[0.0, 0.0]]))[0] < 1.1


def test_cobertura_cercana_al_nivel_nominal():
    d = tabla_sintetica(n_mun=60)
    y = d.y.to_numpy()
    mun = d.drop_duplicates("CVEGEO")[["CVEGEO", "x_m", "y_m"]].rename(columns={"CVEGEO": "clave"})
    folds = V.particiones_espaciales(d.CVEGEO, V.grupos_espaciales(mun, 10), n_rep=1)[0]
    pred = V.evaluar(M.con_tendencia(M.idw_nivel), d, y, [folds], "idw").oof[0]
    t = R.cobertura(d, y, pred, folds)
    assert 0.72 < t.dentro.mean() < 0.88
    assert ((t.prob_bajo >= 0) & (t.prob_bajo <= 1)).all()


# ------------------------------------------------- zona de exclusión y pesos

def _municipios(d):
    return d.drop_duplicates("CVEGEO").set_index("CVEGEO")[["x_m", "y_m"]] / 1000.0


def test_zona_de_exclusion_deja_lejos_el_entrenamiento():
    d = tabla_sintetica(n_mun=40)
    xy = _municipios(d)
    reps = V.particiones_grupo(d, n_grupos=6, n_rep=2)
    for folds in reps:
        for f in np.unique(folds):
            te = folds == f
            for b in (0, 20, 50):
                tr = V.mascara_entrenamiento(d, te, b)
                assert not (tr & te).any()
                a, p = xy.loc[d.CVEGEO[tr].unique()], xy.loc[d.CVEGEO[te].unique()]
                dist = np.sqrt(((a.to_numpy()[:, None] - p.to_numpy()[None]) ** 2).sum(-1))
                if b > 0 and len(a):
                    assert dist.min() > b
            # Con B = 0 entrena con todo lo demás.
            assert (V.mascara_entrenamiento(d, te, 0) == ~te).all()


def test_evaluar_con_zona_de_exclusion_no_ve_vecinos():
    d = tabla_sintetica(n_mun=30)
    vistos = []

    def espia(tr, y, te):
        vistos.append((set(tr.CVEGEO), set(te.CVEGEO)))
        return np.zeros(len(te))

    folds = V.particiones_grupo(d, n_grupos=5, n_rep=1)
    V.evaluar(espia, d, d.y.to_numpy(), folds, "espia", buffer_km=40)
    xy = _municipios(d)
    for tr, te in vistos:
        for a in tr:
            assert min(np.hypot(*(xy.loc[a] - xy.loc[b])) for b in te) > 40


def test_metricas_ponderadas():
    y = np.array([1.0, 2.0, 3.0])
    p = np.array([2.0, 2.0, 3.0])
    assert V.metricas(y, p)["rmse"] == pytest.approx(np.sqrt(1 / 3))
    assert V.metricas(y, p, w=[2, 1, 1])["rmse"] == pytest.approx(np.sqrt(2 / 4))
    assert V.metricas(y, p, w=[0, 1, 1])["rmse"] == pytest.approx(0.0)


def test_metricas_de_nivel_ponderadas_y_subconjunto():
    # Municipio a: error de nivel +1 (dos años). Municipio b: error 0. a pesa 3 y b pesa 1.
    d = pd.DataFrame({"CVEGEO": ["a", "a", "b", "b"], "sembrada_ha": [3000.0, 3000.0, 100.0, 100.0]})
    y = np.array([1.0, 3.0, 2.0, 2.0])
    pred = np.array([3.0, 3.0, 2.5, 1.5])
    ctx = V.contexto(d, umbral_grande=1000)
    nivel = V.metricas_rep(y, pred, ctx, "nivel", ponderado=True)["rmse"]
    assert nivel == pytest.approx(np.sqrt(3000 * 1 / 3100))
    assert V.metricas_rep(y, pred, ctx, "nivel", ponderado=False)["rmse"] == pytest.approx(np.sqrt(0.5))
    assert V.metricas_rep(y, pred, ctx, "nivel", True, "grandes")["rmse"] == pytest.approx(1.0)
    fila = V.metricas_rep(y, pred, ctx, "fila", ponderado=False)["rmse"]
    assert fila == pytest.approx(np.sqrt((4 + 0 + 0.25 + 0.25) / 4))


def test_minimos_cuadrados_ponderados_recuperan_la_pendiente():
    rng = np.random.default_rng(1)
    x = rng.normal(size=(50, 1))
    v = 3 - 0.5 * x[:, 0]
    f = M._ridge_pesos(x, v, rng.uniform(1, 100, 50), 0.0)
    assert f(np.array([[0.0], [2.0]])) == pytest.approx([3.0, 2.0], abs=1e-6)


def test_efecto_estado_sin_estado_en_entrenamiento_no_da_nan():
    d = tabla_sintetica(n_mun=20).assign(sembrada_ha=100.0, t=lambda t: t.x_m / 1e5)
    tr, te = d[d.estado == "E1"], d[d.estado == "E2"].assign(estado="E3")
    pred = M.nivel_lineal(["t"], estado=True)(tr, tr.y.to_numpy(), te)
    assert np.isfinite(pred).all()


# ------------------------------------------------------------------- SIAP

def test_marca_repetido_mismo_estado_y_anio():
    df = pd.DataFrame({"anio": [2020, 2020, 2020, 2021, 2020],
                       "estado": ["A", "A", "A", "A", "B"],
                       "municipio": ["X", "Y", "Z", "X", "W"],
                       "rend": [2.5, 2.5, 3.0, 2.5, 3.0]})
    # X y Y repiten 2.5 en A 2020. Z tiene 3.0 igual que W, pero W está en otro estado.
    # X en 2021 tiene 2.5 pero en otro año.
    assert siap.marca_repetido(df).tolist() == [True, True, False, False, False]


def test_cruce_siap_inegi_con_homonimos():
    s = pd.DataFrame({"estado": ["Puebla", "Tlaxcala", "Tlaxcala"], "clave": ["tlaxco", "tlaxco", "tlaxco"],
                      "anio": [2020, 2020, 2021], "rend": [2.0, 3.0, 3.1]})
    mun = pd.DataFrame({"estado": ["Puebla", "Tlaxcala", "Hidalgo"], "clave": ["tlaxco", "tlaxco", "apan"],
                        "CVEGEO": ["21187", "29034", "13008"]})
    d = M.cruzar(s, mun)
    assert len(d) == len(s)
    assert d.set_index(["estado", "anio"]).CVEGEO.to_dict() == {
        ("Puebla", 2020): "21187", ("Tlaxcala", 2020): "29034", ("Tlaxcala", 2021): "29034"}
    # Un catálogo con claves duplicadas dentro de un estado debe fallar, no duplicar filas.
    with pytest.raises(Exception):
        M.cruzar(s, pd.concat([mun, mun.iloc[[0]]]))


# ------------------------------------------------------------------- clima

def test_orden_de_bandas_de_clima(tmp_path, monkeypatch):
    rasterio = pytest.importorskip("rasterio")
    gpd = pytest.importorskip("geopandas")
    from rasterio.transform import from_origin
    from shapely.geometry import box

    from generalizable import variables

    (tmp_path / "prec").mkdir()
    ruta = tmp_path / "prec" / "PREC_2020.tif"
    datos = np.stack([np.full((10, 10), 10.0 * b, dtype="float32") for b in range(1, 13)])
    # Una celda distinta en el mes 7 para que no baste con el valor constante.
    datos[6, 4:6, 4:6] = 999.0
    with rasterio.open(ruta, "w", driver="GTiff", height=10, width=10, count=12, dtype="float32",
                       crs="EPSG:4326", transform=from_origin(-99.0, 20.0, 0.05, 0.05), nodata=-9999) as r:
        r.write(datos)
    monkeypatch.setattr(variables, "CLIMA", tmp_path)
    z = gpd.GeoDataFrame({"CVEGEO": ["x", "y"]},
                         geometry=[box(-98.95, 19.75, -98.85, 19.85), box(-98.8, 19.7, -98.7, 19.8)], crs="EPSG:4326")
    m = variables._mensual(z, "prec", 2020)
    assert list(m.columns) == list(range(1, 13))
    with rasterio.open(ruta) as r:
        banda7 = r.read(7)
    assert m.loc["x", 7] == pytest.approx(banda7[3:7, 1:3].mean())
    assert m.loc["y", 7] == pytest.approx(999.0)
    for mes in (1, 6, 8, 12):
        assert m.loc["y", mes] == pytest.approx(10.0 * mes)
