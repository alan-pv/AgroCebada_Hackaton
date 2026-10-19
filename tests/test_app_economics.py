import json

import pandas as pd
import pytest

pytest.importorskip("flask")

from parcelas import economia
from parcelas.config import OUTPUTS_PARCELAS
from app import create_app

# Claves de cada fila de GET /api/economics
LIST_KEYS = {"id", "state", "municipality", "set", "regime", "area_ha", "price", "breakeven", "income_ha",
             "income_conservative_ha", "income_parcel", "margin_ha", "prob_not_cover_costs", "light_costs",
             "prob_not_pay_credit", "light_credit"}
# Campo de la API y columna de outputs/parcelas/capa_economica.csv con la que se compara
MONEY = {"price": "precio", "income_ha": "ingreso_esperado_ha", "income_conservative_ha": "ingreso_conservador_ha",
         "income_parcel": "ingreso_esperado_parcela", "margin_ha": "margen_esperado_ha"}
OTHER = {"breakeven": "pe_total", "prob_not_cover_costs": "prob_no_cubrir_costos",
         "prob_not_pay_credit": "prob_no_pagar_credito"}
LIGHTS = {"light_costs": "semaforo_costos", "light_credit": "semaforo_credito"}
CONTEXT_KEYS = {"loss_rate_2003_2025", "loss_rate_2013_2025", "years_loss_over_20", "years_loss_over_50",
                "siap_yield_mean", "siap_yield_sd", "siap_yield_p10", "price_2023_2025", "price_min", "price_max",
                "agrocostos_zone"}


def strict_json(text):
    """Parsea JSON de forma estricta: NaN, Infinity y -Infinity no son JSON válido y hacen fallar."""
    def reject(constant):
        raise ValueError(f"constante no permitida en JSON: {constant}")
    return json.loads(text, parse_constant=reject)


def detail(client, parcel_id, **query):
    res = client.get(f"/api/economics/{parcel_id}", query_string=query)
    assert res.status_code == 200, res.get_json()
    return strict_json(res.get_data(as_text=True))


@pytest.fixture(scope="module")
def client():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def lista(client):
    res = client.get("/api/economics")
    assert res.status_code == 200
    return strict_json(res.get_data(as_text=True))


@pytest.fixture(scope="module")
def csv_ref():
    # CVEGEO se lee como texto para que coincida con la clave de la tabla municipal
    return pd.read_csv(OUTPUTS_PARCELAS / "capa_economica.csv", dtype={"CVEGEO": str}).set_index("ID_POLIGONO")


def test_lista_coincide_con_capa_economica_csv(lista, csv_ref):
    assert len(lista) == 197
    assert all(set(f) == LIST_KEYS for f in lista)
    assert [f["id"] for f in lista] == sorted(f["id"] for f in lista)
    for f in lista:
        ref = csv_ref.loc[f["id"]]
        for api, col in MONEY.items():
            assert f[api] == pytest.approx(ref[col], abs=0.01), (f["id"], api)
        for api, col in OTHER.items():
            assert f[api] == pytest.approx(ref[col], abs=1e-3), (f["id"], api)
        for api, col in LIGHTS.items():
            assert f[api] == ref[col], (f["id"], api)


def test_semaforo_sigue_los_cortes(lista):
    # verde por debajo de 0.10, amarillo desde 0.10 hasta 0.30 sin llegar, rojo desde 0.30
    for f in lista:
        for prob, light in (("prob_not_cover_costs", "light_costs"), ("prob_not_pay_credit", "light_credit")):
            p = f[prob]
            esperado = "verde" if p < 0.10 else "amarillo" if p < 0.30 else "rojo"
            assert f[light] == esperado, (f["id"], light, p)


def test_formato_csv(client):
    res = client.get("/api/economics?format=csv")
    assert res.status_code == 200
    assert res.mimetype == "text/csv"
    assert res.headers["Content-Disposition"] == "attachment; filename=agrocebada_economia.csv"
    lineas = res.get_data(as_text=True).strip().splitlines()
    assert len(lineas) == 198
    assert lineas[0].startswith("id,state,municipality,set,regime")


def test_formato_no_soportado(client):
    res = client.get("/api/economics?format=xml")
    assert res.status_code == 400
    assert res.get_json() == {"error": "format debe ser json o csv"}


def test_detalle_por_defecto_coincide_con_la_tabla(client, lista, csv_ref):
    fila = next(f for f in lista if f["id"] == "AGC_003")
    det = detail(client, "AGC_003")
    for k in LIST_KEYS:
        if isinstance(fila[k], str):
            assert det[k] == fila[k], k
        else:
            assert det[k] == pytest.approx(fila[k], abs=0.011), k
    # Sin price ni breakeven, el precio y el punto de equilibrio son los de por defecto
    assert det["price"] == det["price_default"]
    assert det["breakeven"] == det["breakeven_default"]
    assert set(det["context"]) == CONTEXT_KEYS
    muni = economia.cargar_tabla().loc[csv_ref.loc["AGC_003", "CVEGEO"]]
    ctx = det["context"]
    assert ctx["price_2023_2025"] == pytest.approx(muni.precio_2023_2025, abs=0.01)
    assert ctx["loss_rate_2003_2025"] == pytest.approx(muni.siniestralidad_2003_2025, abs=1e-4)
    assert ctx["years_loss_over_20"] == muni.anios_perdida_20
    assert ctx["agrocostos_zone"] == muni.zona_agrocostos
    assert det["light_cuts"] == {"green_below": 0.10, "red_from": 0.30}


def test_precio_escala_el_ingreso_y_mueve_el_equilibrio(client):
    base = detail(client, "AGC_003")
    precio = base["price"] * 1.1
    res = detail(client, "AGC_003", price=precio)
    assert res["price"] == pytest.approx(precio, abs=0.01)
    assert res["income_ha"] == pytest.approx(base["income_ha"] * 1.1, rel=1e-4)
    assert res["income_parcel"] == pytest.approx(base["income_parcel"] * 1.1, rel=1e-4)
    assert res["cost_total"] == base["cost_total"]
    assert res["breakeven"] == pytest.approx(base["cost_total"] / precio, abs=1e-3)
    assert res["breakeven_default"] == base["breakeven_default"]


def test_mas_equilibrio_no_baja_la_probabilidad_y_se_respeta(client):
    probs = []
    for b in (3.0, 4.5, 6.0):
        res = detail(client, "AGC_003", breakeven=b)
        assert res["breakeven"] == b
        # El servidor usa el precio sin redondear; el redondeo a centavos cuesta hasta b * 0.005 $/ha
        assert res["cost_total"] == pytest.approx(b * res["price"], abs=b * 0.005 + 0.01)
        probs.append(res["prob_not_cover_costs"])
    assert probs[0] <= probs[1] <= probs[2]


def test_costo_credito_no_supera_al_costo_total(client, csv_ref):
    # Sin breakeven, el costo del crédito es el de la tabla
    plain = detail(client, "AGC_001")
    assert plain["cost_credit"] == pytest.approx(csv_ref.loc["AGC_001", "costo_credito"], abs=0.01)
    # Con un breakeven bajo, el crédito se topa al costo total y breakeven_credit no supera a breakeven
    low = detail(client, "AGC_001", breakeven=0.5)
    assert low["breakeven_credit"] <= low["breakeven"]
    assert low["cost_credit"] <= low["cost_total"]
    # Con un breakeven alto, el costo del crédito sigue siendo el de la tabla
    high = detail(client, "AGC_001", breakeven=6.0)
    assert high["cost_credit"] == pytest.approx(csv_ref.loc["AGC_001", "costo_credito"], abs=0.01)


@pytest.mark.parametrize("query", [
    "price=abc", "price=0", "price=-5", "price=1e9", "price=nan", "price=inf",
    "breakeven=0", "breakeven=100", "breakeven=abc", "breakeven=nan",
])
def test_parametros_invalidos_dan_400(client, query):
    res = client.get(f"/api/economics/AGC_003?{query}")
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_id_inexistente_da_404(client):
    res = client.get("/api/economics/AGC_999")
    assert res.status_code == 404
    assert "error" in res.get_json()


def test_json_estricto_en_todas_las_respuestas(client, lista):
    res = client.get("/api/economics")
    assert res.headers["Cache-Control"] == "public, max-age=3600"
    strict_json(res.get_data(as_text=True))
    # Cada detalle se parsea sin NaN ni Infinity, con y sin parámetros
    for f in lista:
        assert set(detail(client, f["id"])) >= LIST_KEYS
    detail(client, "AGC_003", price=6000, breakeven=4)


def test_error_del_modelo_en_pesos(client, lista):
    # El error típico es el RMSE del esquema A del modelo entregado, por el precio usado (issue #48)
    from app.modules import model
    rmse = model.load_model().metricas["A"]["rmse"]
    base = detail(client, "AGC_003")
    err = base["model_error"]
    assert set(err) == {"t_ha", "money_ha", "share_cost_total", "share_credit"}
    assert err["t_ha"] == pytest.approx(rmse, abs=5e-4)
    assert err["money_ha"] == pytest.approx(rmse * base["price"], abs=0.01)
    assert err["share_cost_total"] == pytest.approx(err["money_ha"] / base["cost_total"], abs=1e-4)
    assert err["share_credit"] == pytest.approx(err["money_ha"] / base["cost_credit"], abs=1e-4)
    # Con otro precio, los pesos siguen al precio
    caro = detail(client, "AGC_003", price=8000)
    assert caro["model_error"]["money_ha"] == pytest.approx(rmse * 8000, abs=0.01)


def test_error_en_pesos_reproduce_el_rango_del_reporte(client, lista):
    # Reporte de entrega: unos 2,500 $/ha en promedio en las 59 parcelas, de 2,000 a 3,300 según el
    # municipio, de 7 a 12 % del costo total y de 13 a 45 % del crédito
    errores = [detail(client, f["id"])["model_error"] for f in lista if f["set"] == "PREDICCION"]
    assert len(errores) == 59
    pesos = [e["money_ha"] for e in errores]
    assert 1900 < min(pesos) and max(pesos) < 3400
    assert sum(pesos) / len(pesos) == pytest.approx(2500, abs=100)
    assert 0.06 < min(e["share_cost_total"] for e in errores) and max(e["share_cost_total"] for e in errores) < 0.125
    assert 0.12 < min(e["share_credit"] for e in errores) and max(e["share_credit"] for e in errores) < 0.455
