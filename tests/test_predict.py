import numpy as np
import pandas as pd
import pytest

from parcelas import controles
from parcelas.config import ANALISIS_PARCELAS, NOMBRE_EQUIPO, OUTPUTS_PARCELAS, PROCESSED
from parcelas.predict import RADIO_MEDIA, RADIO_VECINOS, SALIDA, cargar_modelo, predict
from parcelas.train_final import cargar_datos


@pytest.fixture(scope="module")
def modelo():
    return cargar_modelo()


@pytest.fixture(scope="module")
def datos():
    return cargar_datos()


@pytest.fixture(scope="module")
def pred59(modelo, datos):
    return predict(datos[2].reset_index(), modelo=modelo)


def test_contrato_de_predict(pred59, datos):
    assert list(pred59.columns) == SALIDA
    assert SALIDA[:5] == ["ID_POLIGONO", "pred", "p10", "p90", "prob_bajo_umbral"]
    assert len(pred59) == 59
    assert set(pred59["ID_POLIGONO"]) == set(datos[2].index)
    assert not pred59.isna().any().any()
    assert (pred59["p10"] <= pred59["pred"]).all() and (pred59["pred"] <= pred59["p90"]).all()
    assert pred59["prob_bajo_umbral"].between(0, 1).all()


def test_acepta_id_como_indice_o_columna(modelo, datos):
    a = predict(datos[2], modelo=modelo)
    b = predict(datos[2].reset_index(), modelo=modelo)
    pd.testing.assert_frame_equal(a, b)


def test_umbral_mayor_sube_la_probabilidad(modelo, datos):
    bajo = predict(datos[2], umbral=2.0, modelo=modelo)["prob_bajo_umbral"]
    alto = predict(datos[2], umbral=3.5, modelo=modelo)["prob_bajo_umbral"]
    assert (alto >= bajo).all() and alto.mean() > bajo.mean()


def test_columnas_faltantes_dan_error_claro(modelo, datos):
    with pytest.raises(ValueError, match="Faltan columnas.*x_m"):
        predict(datos[2].reset_index().drop(columns="x_m"), modelo=modelo)
    malo = datos[2].reset_index().assign(regimen="C")
    with pytest.raises(ValueError, match="Régimen desconocido"):
        predict(malo, modelo=modelo)


def test_parcelas_de_entrenamiento_usan_la_prediccion_fuera_de_fold(modelo, datos):
    X, y, _ = datos
    fuera = predict(X, modelo=modelo)
    tal_cual = predict(X, modelo=modelo, excluir_entrenamiento=False)
    np.testing.assert_allclose(fuera["pred"], modelo.oof.loc[X.index])
    rm = lambda p: np.sqrt(np.mean((p - y.to_numpy()) ** 2))
    # sin excluir, la parcela se cuenta como su propia vecina y el error sale demasiado bajo
    assert rm(tal_cual["pred"].to_numpy()) < 0.8 * rm(fuera["pred"].to_numpy())


def _entrega(pred59, datos):
    reg = datos[2]["regimen"]
    return pd.DataFrame({
        "ID_POLIGONO": pred59["ID_POLIGONO"], "RENDIMIENTO_T_HA": pred59["pred"].round(2),
        "p10": pred59["p10"].round(2), "p90": pred59["p90"].round(2),
        "regimen": reg.loc[pred59["ID_POLIGONO"]].to_numpy()})


def _controles(e, datos):
    X, y, X59 = datos
    return controles.ejecutar(e, X59.index, X["regimen"], y)


def test_controles_pasan_con_la_prediccion_buena(pred59, datos):
    t = _controles(_entrega(pred59, datos), datos)
    assert (t["estado"] != "FALLA").all()
    controles.verificar(t)


@pytest.mark.parametrize("dano", ["fila", "duplicado", "nulo", "rango", "regimen", "media",
                                  "intervalo"])
def test_controles_fallan_con_casos_malos(pred59, datos, dano):
    e = _entrega(pred59, datos)
    if dano == "fila":
        e = e.iloc[:-1]
    elif dano == "duplicado":
        e.loc[1, "ID_POLIGONO"] = e.loc[0, "ID_POLIGONO"]
    elif dano == "nulo":
        e.loc[3, "RENDIMIENTO_T_HA"] = np.nan
    elif dano == "rango":
        e.loc[3, "RENDIMIENTO_T_HA"] = 6.2
    elif dano == "regimen":
        i = e.index[e["regimen"] == "B"][0]
        e.loc[i, ["RENDIMIENTO_T_HA", "p90"]] = 4.4  # dentro de lo plausible, fuera del rango de B
    elif dano == "media":
        e["RENDIMIENTO_T_HA"] = e["RENDIMIENTO_T_HA"] + 0.3
        e["p90"] = e["p90"] + 0.3
        e["p10"] = e["p10"] + 0.3
        e["RENDIMIENTO_T_HA"] = e["RENDIMIENTO_T_HA"].clip(upper=5.5)
    elif dano == "intervalo":
        e.loc[3, "p10"] = e.loc[3, "RENDIMIENTO_T_HA"] + 0.1
    t = _controles(e, datos)
    assert (t["estado"] == "FALLA").any()
    with pytest.raises(controles.ControlesFallidos):
        controles.verificar(t)


def test_modelo_guardado_reproduce_las_predicciones_finales(pred59):
    f = pd.read_csv(OUTPUTS_PARCELAS / "predicciones_finales.csv").set_index("ID_POLIGONO")
    p = pred59.set_index("ID_POLIGONO").loc[f.index]
    np.testing.assert_allclose(p["pred"].round(2), f["RENDIMIENTO_T_HA"], atol=1e-9)
    np.testing.assert_allclose(p["p10"].round(2), f["p10"], atol=1e-9)
    np.testing.assert_allclose(p["p90"].round(2), f["p90"], atol=1e-9)


def test_csv_de_entrega_para_fira(datos):
    ruta = OUTPUTS_PARCELAS / f"{NOMBRE_EQUIPO}_prediccion.csv"
    crudo = ruta.read_bytes()
    assert not crudo.startswith(b"\xef\xbb\xbf")  # sin BOM
    d = pd.read_csv(ruta)
    assert list(d.columns) == ["ID_POLIGONO", "RENDIMIENTO_T_HA"]
    assert len(d) == 59 and set(d["ID_POLIGONO"]) == set(datos[2].index)
    assert d["RENDIMIENTO_T_HA"].between(2.0, 5.6).all()


def test_predicciones_parquet_para_la_app():
    p = pd.read_parquet(OUTPUTS_PARCELAS / "predicciones.parquet")
    assert len(p) == 197 and p["ID_POLIGONO"].is_unique
    assert not p[["pred", "p10", "p90", "prob_bajo_umbral"]].isna().any().any()
    ent = p[p["conjunto"] == "ENTRENAMIENTO"]
    assert ent["observado"].notna().all()
    assert p.loc[p["conjunto"] == "PREDICCION", "observado"].isna().all()


def test_marca_de_confianza_tiene_valores_validos(pred59):
    assert set(pred59["confianza"]) <= {"alta", "media", "baja"}
    assert (pred59["vecinos_400m"] >= 0).all() and pred59["vecinos_400m"].dtype.kind == "i"
    assert (pred59["dist_vecino_m"] > 0).all()
    assert pred59["motivo_confianza"].str.len().gt(0).all()
    alta = pred59["confianza"] == "alta"
    assert (pred59.loc[alta, "vecinos_400m"] >= 1).all()
    assert (pred59.loc[pred59["confianza"] == "media", "vecinos_400m"] == 0).all()
    media = pred59["confianza"] == "media"
    assert (pred59.loc[media, "dist_vecino_m"].between(RADIO_VECINOS, RADIO_MEDIA)).all()
    assert pred59["confianza"].value_counts().to_dict() == {"alta": 35, "media": 14, "baja": 10}


def test_la_marca_no_cambia_la_prediccion_ni_el_intervalo(pred59):
    etapa = pd.read_csv(ANALISIS_PARCELAS / "predicciones_etapa_intervalos.csv").set_index("ID_POLIGONO")
    p = pred59.set_index("ID_POLIGONO").loc[etapa.index]
    for c in ["pred", "p10", "p90", "prob_bajo_umbral"]:
        np.testing.assert_allclose(p[c], etapa[c], rtol=0, atol=1e-12)


def test_umbral_por_parcela(modelo, datos):
    X59 = datos[2]
    escalar = predict(X59, umbral=2.8, modelo=modelo)
    constante = predict(X59, umbral=np.full(len(X59), 2.8), modelo=modelo)
    pd.testing.assert_frame_equal(escalar, constante)
    serie = predict(X59, umbral=pd.Series(np.full(len(X59), 2.8), index=X59.index), modelo=modelo)
    pd.testing.assert_frame_equal(escalar, serie)
    variable = np.where(np.arange(len(X59)) % 2 == 0, 2.0, 3.5)
    mezcla = predict(X59, umbral=variable, modelo=modelo)["prob_bajo_umbral"].to_numpy()
    bajo = predict(X59, umbral=2.0, modelo=modelo)["prob_bajo_umbral"].to_numpy()
    alto = predict(X59, umbral=3.5, modelo=modelo)["prob_bajo_umbral"].to_numpy()
    np.testing.assert_allclose(mezcla, np.where(variable == 2.0, bajo, alto))
    with pytest.raises(ValueError, match="un valor por parcela"):
        predict(X59, umbral=[2.0, 3.0], modelo=modelo)


def test_parcela_de_entrenamiento_no_es_su_propia_vecina(modelo, datos):
    X = datos[0]
    r = predict(X, modelo=modelo)
    assert (r["dist_vecino_m"] > 0).all()
    # el mismo punto como parcela nueva (otro ID) sí tiene un vecino a distancia 0
    nueva = X.reset_index().assign(ID_POLIGONO=lambda d: "NUEVA_" + d["ID_POLIGONO"])
    rn = predict(nueva, modelo=modelo, excluir_entrenamiento=False)
    assert (rn["dist_vecino_m"] == 0).all()
    assert (rn["vecinos_400m"].to_numpy() == r["vecinos_400m"].to_numpy() + 1).all()
