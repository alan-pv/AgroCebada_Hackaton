import pandas as pd
import pytest

from parcelas import config, io, parcelas


def test_etiquetas():
    et = io.leer_etiquetas()
    assert list(et.columns) == ["ID_POLIGONO", "AREA_HA", "RENDIMIENTO_T_HA", "CONJUNTO"]
    assert len(et) == 197
    assert et.RENDIMIENTO_T_HA.notna().sum() == 138


def test_parcelas_geo():
    g = io.leer_parcelas()
    assert len(g) == 197
    assert str(g.crs) == config.CRS_GEO
    assert {"ID_POLIGONO", "Estado", "Municipio", "Cultivo"} <= set(g.columns)


@pytest.mark.parametrize("lector", [io.leer_basico, io.leer_pro])
def test_satelitales(lector):
    df = lector()
    assert pd.api.types.is_datetime64_any_dtype(df.fecha_captura)
    assert isinstance(df.sensor.dtype, pd.CategoricalDtype)


def test_pro_cubre_todo_2025():
    f = io.leer_pro().fecha_captura
    assert f.min().month == 1 and f.max().month == 12


def test_regimen_cubre_municipios():
    assert set(io.leer_parcelas().Municipio) == set(config.REGIMEN_POR_MUNICIPIO)
    assert set(config.REGIMEN_POR_MUNICIPIO.values()) == {"A", "B"}


def test_tabla_parcelas():
    geo, df = parcelas.construir()
    assert len(df) == 197 and df.ID_POLIGONO.is_unique
    assert df.regimen.notna().all()
    assert df.loc[df.conjunto == "PREDICCION", "rendimiento"].isna().all()
    assert df.compacidad.between(0, 1).all()
    assert len(geo) == 197


def test_extraer_rasteres():
    r = io.extraer_rasteres()
    assert len(r["precipitacion"]) == len(r["tmax"]) == len(r["tmin"]) == 48
    assert r["elevacion"].exists() and r["pendiente"].exists()
