import numpy as np
import pandas as pd
import pytest

from parcelas.economia import capa_economica, cargar_tabla
from parcelas.predict import cargar_modelo
from parcelas.config import OUTPUTS_PARCELAS


@pytest.fixture(scope="module")
def modelo():
    return cargar_modelo()


@pytest.fixture(scope="module")
def tabla():
    return cargar_tabla()


@pytest.fixture(scope="module")
def pred():
    return pd.read_parquet(OUTPUTS_PARCELAS / "predicciones.parquet")


@pytest.fixture(scope="module")
def pred59(pred):
    return pred[pred.conjunto == "PREDICCION"].reset_index(drop=True)


def test_tabla_municipal(tabla):
    assert len(tabla) == 9 and tabla.CVEGEO.is_unique
    # Emiliano Zapata de Hidalgo, no el de Tlaxcala
    assert tabla.loc["13021", "estado"] == "Hidalgo"
    assert tabla.loc["13021", "precio_min"] == pytest.approx(6282.33, abs=0.01)
    assert (tabla.pe_credito_t_ha < tabla.pe_total_t_ha).all()
    assert tabla.factor_inpc.between(1.0, 1.3).all()
    assert np.allclose(tabla.costo_total_2025, tabla.costo_total_2022 * tabla.factor_inpc)
    assert np.allclose(tabla.pe_total_t_ha, tabla.costo_total_2025 / tabla.precio_2023_2025)


def test_las_59_parcelas_tienen_valores(modelo, pred59, tabla):
    e = capa_economica(pred59, modelo=modelo, tabla=tabla)
    assert len(e) == 59 and set(e.ID_POLIGONO) == set(pred59.ID_POLIGONO)
    assert not e.isna().any().any()
    for c in ("prob_no_pagar_credito", "prob_no_cubrir_costos", "prob_perdida"):
        assert e[c].between(0, 1).all()
    assert set(e.semaforo_credito) <= {"verde", "amarillo", "rojo"}
    assert np.allclose(e.ingreso_esperado_parcela, pred59.pred * e.precio * pred59.area_ha)
    assert (e.ingreso_conservador_ha <= e.ingreso_esperado_ha).all()
    assert (e.prob_no_pagar_credito <= e.prob_no_cubrir_costos + 1e-12).all()


def test_costo_mayor_da_probabilidad_mayor(modelo, pred59, tabla):
    costos = [10_000, 20_000, 30_000, 40_000]
    p = [capa_economica(pred59, modelo=modelo, tabla=tabla,
                        costo_total=c).prob_no_cubrir_costos.to_numpy() for c in costos]
    for menor, mayor in zip(p, p[1:]):
        assert (mayor >= menor - 1e-12).all()
    assert p[-1].mean() > p[0].mean()


def test_precio_mayor_baja_el_punto_de_equilibrio(modelo, pred59, tabla):
    a = capa_economica(pred59, modelo=modelo, tabla=tabla, precio=5000)
    b = capa_economica(pred59, modelo=modelo, tabla=tabla, precio=8000)
    assert (b.pe_total < a.pe_total).all()
    assert (b.prob_no_cubrir_costos <= a.prob_no_cubrir_costos + 1e-12).all()


def test_sin_siniestro_coincide_con_el_modelo(modelo, pred59, tabla):
    e = capa_economica(pred59, modelo=modelo, tabla=tabla, siniestro=0.0)
    cal = modelo.prediccion.calibrador
    for i in (0, 10, 30):
        r = pred59.iloc[i]
        p = cal.prob_bajo(np.array([r.pred]), np.array([r.regimen]), np.array([r.area_ha]),
                          e.pe_total[i])[0]
        assert e.prob_no_cubrir_costos[i] == pytest.approx(p)
    # con siniestro q, P = q + (1 - q) P0
    q = 0.1
    e2 = capa_economica(pred59, modelo=modelo, tabla=tabla, siniestro=q)
    assert np.allclose(e2.prob_no_cubrir_costos, q + (1 - q) * e.prob_no_cubrir_costos)


def test_cruce_por_cvegeo_y_no_por_nombre(modelo, tabla):
    # Emiliano Zapata existe en Hidalgo y Tlaxcala. Con CVEGEO se usa el de Hidalgo.
    d = pd.DataFrame({"pred": [3.5], "p10": [3.0], "regimen": ["B"], "area_ha": [5.0],
                      "CVEGEO": ["13021"], "municipio": ["Emiliano Zapata"]})
    e = capa_economica(d, modelo=modelo, tabla=tabla)
    assert e.precio[0] == pytest.approx(tabla.loc["13021", "precio_2023_2025"])
    d2 = d.drop(columns="CVEGEO").assign(estado="Hidalgo")
    assert capa_economica(d2, modelo=modelo, tabla=tabla).CVEGEO[0] == "13021"
    with pytest.raises(ValueError):
        capa_economica(d.assign(CVEGEO="99999"), modelo=modelo, tabla=tabla)


def test_sustituir_por_diccionario(modelo, pred59, tabla):
    a = capa_economica(pred59, modelo=modelo, tabla=tabla)
    b = capa_economica(pred59, modelo=modelo, tabla=tabla, precio={"29006": 9000})
    m = pred59.municipio.eq("Calpulalpan").to_numpy()
    assert (b.precio[m] == 9000).all()
    assert np.allclose(b.precio[~m], a.precio[~m])
