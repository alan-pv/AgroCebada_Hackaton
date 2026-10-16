# Economía por parcela: tabla de las 197 parcelas y detalle económico de una, con contexto municipal.
# Los cálculos son de agrocebada.economia (capa_economica); aquí se lee, se valida y se redondea.
# Contrato:
#   GET /api/economics              lista JSON de las 197 parcelas, ordenada por id, con id, state, municipality, set,
#                                   regime, area_ha, price, breakeven, income_ha, income_conservative_ha, income_parcel,
#                                   margin_ha, prob_not_cover_costs, light_costs, prob_not_pay_credit y light_credit;
#                                   format=csv descarga lo mismo como CSV
#   GET /api/economics/<parcel_id>  detalle económico de una parcela con contexto municipal;
#                                   query opcional price (en $/t) y breakeven (en t/ha)
#   parcel_economics_data()         función pura con el detalle de la ruta anterior; lanza KeyError si el ID
#                                   no existe y ValueError si price o breakeven no son válidos
import math
from functools import cache

import pandas as pd
from flask import Blueprint, Response, jsonify, request

from agrocebada import economia
from agrocebada.config import OUTPUTS

from . import model

bp = Blueprint("economics", __name__)

# Rangos aceptados para los parámetros de la query
PRICE_RANGE = (500.0, 30000.0)  # $/t
BREAKEVEN_RANGE = (0.5, 15.0)   # t/ha

# Columnas de la capa económica y su nombre en la API
FIELDS = {
    "ID_POLIGONO": "id",
    "estado": "state",
    "municipio": "municipality",
    "conjunto": "set",
    "regimen": "regime",
    "area_ha": "area_ha",
    "precio": "price",
    "pe_total": "breakeven",
    "ingreso_esperado_ha": "income_ha",
    "ingreso_conservador_ha": "income_conservative_ha",
    "ingreso_esperado_parcela": "income_parcel",
    "margen_esperado_ha": "margin_ha",
    "prob_no_cubrir_costos": "prob_not_cover_costs",
    "semaforo_costos": "light_costs",
    "prob_no_pagar_credito": "prob_not_pay_credit",
    "semaforo_credito": "light_credit",
}
# Decimales de la lista: dinero a 2, rendimientos a 3 y probabilidades a 4
DECIMALS = {"area_ha": 2, "price": 2, "breakeven": 3, "income_ha": 2, "income_conservative_ha": 2,
            "income_parcel": 2, "margin_ha": 2, "prob_not_cover_costs": 4, "prob_not_pay_credit": 4}


# Se leen una sola vez y quedan en memoria
@cache
def input_table():
    """Predicciones de las 197 parcelas, solo las columnas que usa la capa económica."""
    cols = ["ID_POLIGONO", "conjunto", "estado", "municipio", "regimen", "area_ha", "pred", "p10"]
    return pd.read_parquet(OUTPUTS / "predicciones.parquet")[cols]


@cache
def municipal_table():
    """Tabla municipal de data/externos/economia_municipal.csv, indexada por CVEGEO."""
    return economia.cargar_tabla()


@cache
def default_table():
    """Capa económica de las 197 parcelas con los valores por defecto, indexada por ID.

    Tiene las mismas columnas y valores que outputs/capa_economica.csv.
    """
    p = input_table()
    e = economia.capa_economica(p, modelo=model.load_model(), tabla=municipal_table())
    t = pd.concat([p.reset_index(drop=True), e.drop(columns="ID_POLIGONO")], axis=1)
    return t.set_index("ID_POLIGONO", drop=False)


def warm_up():
    """Carga la tabla por defecto antes de aceptar peticiones; la primera visita no espera."""
    default_table()


def _round(value, decimals):
    """Número nativo redondeado; None si no es finito, porque NaN e infinitos no son JSON válido."""
    x = float(value)
    return round(x, decimals) if math.isfinite(x) else None


def _check_number(value, value_range, name, unit):
    """Valor como float, finito y dentro del rango; si no, ValueError con mensaje en español."""
    low, high = value_range
    try:
        x = float(value)
    except (TypeError, ValueError):
        x = math.nan
    if isinstance(value, bool) or not math.isfinite(x) or not low <= x <= high:
        raise ValueError(f"{name} debe ser un número entre {low:g} y {high:g} {unit}")
    return x


def _arg_number(name):
    """Parámetro numérico de la query: None si no viene; ValueError si el texto no es un número."""
    text = request.args.get(name)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        raise ValueError(f"{name} debe ser un número") from None


def _list_table():
    """Las 197 parcelas con valores por defecto, ordenadas por ID y con los nombres de la API."""
    return default_table()[list(FIELDS)].rename(columns=FIELDS).round(DECIMALS).sort_index()


def parcel_economics_data(parcel_id, price=None, breakeven=None) -> dict:
    """Detalle económico de una parcela con contexto municipal.

    price (en $/t) sustituye el precio por defecto del municipio. breakeven (en t/ha) fija el
    punto de equilibrio total: el costo total se toma como breakeven * price, así que el umbral
    es exactamente el que se pidió. Lanza KeyError si el ID no existe y ValueError si price o
    breakeven no son válidos.
    """
    # Primero se validan los parámetros y luego el ID: una petición mal formada responde 400 aunque el ID no exista
    if price is not None:
        price = _check_number(price, PRICE_RANGE, "price", "$/t")
    if breakeven is not None:
        breakeven = _check_number(breakeven, BREAKEVEN_RANGE, "breakeven", "t/ha")
    base = default_table()
    if parcel_id not in base.index:
        raise KeyError(parcel_id)
    row = base.loc[[parcel_id]]
    r = row.iloc[0]
    # Sin price ni breakeven se usan los valores por defecto de la tabla
    default_price = float(r["precio"])
    price_used = default_price if price is None else price
    cost_total = float(r["costo_total"]) if breakeven is None else breakeven * price_used
    # El crédito es parte del costo total: con breakeven, su costo se topa al total para que
    # breakeven_credit no supere a breakeven
    credit_cost = float(r["costo_credito"])
    if breakeven is not None:
        credit_cost = min(credit_cost, cost_total)
    calc = economia.capa_economica(row, modelo=model.load_model(), tabla=municipal_table(),
                                   precio=price_used, costo_total=cost_total,
                                   costo_credito=credit_cost).iloc[0]
    muni = municipal_table().loc[str(r["CVEGEO"])]
    return {
        "id": str(r["ID_POLIGONO"]),
        "state": str(r["estado"]),
        "municipality": str(r["municipio"]),
        "set": str(r["conjunto"]),
        "regime": str(r["regimen"]),
        "area_ha": _round(r["area_ha"], 2),
        "pred": _round(r["pred"], 3),
        "p10": _round(r["p10"], 3),
        "price": _round(calc["precio"], 2),
        "price_default": _round(default_price, 2),
        "cost_total": _round(calc["costo_total"], 2),
        "cost_credit": _round(calc["costo_credito"], 2),
        "breakeven": _round(calc["pe_total"], 3),
        "breakeven_default": _round(r["pe_total"], 3),
        "breakeven_credit": _round(calc["pe_credito"], 3),
        "income_ha": _round(calc["ingreso_esperado_ha"], 2),
        "income_conservative_ha": _round(calc["ingreso_conservador_ha"], 2),
        "income_parcel": _round(calc["ingreso_esperado_parcela"], 2),
        "margin_ha": _round(calc["margen_esperado_ha"], 2),
        "prob_loss": _round(calc["prob_perdida"], 4),
        "prob_not_cover_costs": _round(calc["prob_no_cubrir_costos"], 4),
        "light_costs": str(calc["semaforo_costos"]),
        "prob_not_pay_credit": _round(calc["prob_no_pagar_credito"], 4),
        "light_credit": str(calc["semaforo_credito"]),
        "light_cuts": {"green_below": economia.CORTES[0], "red_from": economia.CORTES[1]},
        "context": {
            "loss_rate_2003_2025": _round(muni["siniestralidad_2003_2025"], 4),
            "loss_rate_2013_2025": _round(muni["siniestralidad_2013_2025"], 4),
            "years_loss_over_20": int(muni["anios_perdida_20"]),
            "years_loss_over_50": int(muni["anios_perdida_50"]),
            "siap_yield_mean": _round(muni["siap_rend_media"], 3),
            "siap_yield_sd": _round(muni["siap_rend_sd"], 3),
            "siap_yield_p10": _round(muni["siap_rend_p10"], 3),
            "price_2023_2025": _round(muni["precio_2023_2025"], 2),
            "price_min": _round(muni["precio_min"], 2),
            "price_max": _round(muni["precio_max"], 2),
            "agrocostos_zone": str(muni["zona_agrocostos"]),
        },
    }


@bp.get("/api/economics")
def economics_table():
    fmt = request.args.get("format", "json")
    if fmt not in ("json", "csv"):
        return jsonify(error="format debe ser json o csv"), 400
    table = _list_table()
    if fmt == "csv":
        res = Response(table.to_csv(index=False), mimetype="text/csv")
        res.headers["Content-Disposition"] = "attachment; filename=agrocebada_economia.csv"
        return res
    res = Response(table.to_json(orient="records"), mimetype="application/json")
    # Igual que /api/parcels: el navegador reutiliza la tabla una hora
    res.headers["Cache-Control"] = "public, max-age=3600"
    return res


@bp.get("/api/economics/<parcel_id>")
def parcel_economics(parcel_id):
    try:
        price, breakeven = _arg_number("price"), _arg_number("breakeven")
    except ValueError as e:
        return jsonify(error=str(e)), 400
    try:
        return jsonify(parcel_economics_data(parcel_id, price=price, breakeven=breakeven))
    except KeyError:
        return jsonify(error=f"ID de parcela desconocido: {parcel_id}"), 404
    except ValueError as e:
        return jsonify(error=str(e)), 400
