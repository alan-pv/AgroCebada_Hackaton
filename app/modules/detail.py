# Ficha de una parcela: identificación, predicción, intervalo, confianza, desglose del modelo,
# variables clave y serie satelital
# Contrato:
#   GET /api/parcels/<parcel_id>  JSON con las secciones de la ficha, las de arriba
#   GET /parcela/<parcel_id>      página HTML de la ficha, con la plantilla parcel.html
#   parcel_detail_data()          función pura con los datos de ambas; lanza KeyError si el ID no existe
import math
from functools import cache

import pandas as pd
from flask import Blueprint, jsonify, render_template, request

from agrocebada.config import OUTPUTS, PROCESSED

from . import charts, economics, formatting
from .model import load_model

bp = Blueprint("detail", __name__)

# Gráficas SVG de charts.py como globales de la plantilla parcel.html
bp.add_app_template_global(charts.interval_bar, "interval_bar")
bp.add_app_template_global(charts.breakdown_bars, "breakdown_bars")
bp.add_app_template_global(charts.line_chart, "line_chart")
bp.add_app_template_global(charts.responsive_chart, "responsive_chart")

# Columnas que usa la ficha de cada fuente. Se leen con columns= para no cargar todo
PREDICTION_COLS = ["ID_POLIGONO", "conjunto", "regimen", "estado", "municipio", "lon", "lat", "area_ha",
                   "pred", "p10", "p90", "prob_bajo_umbral", "confianza", "vecinos_400m", "dist_vecino_m",
                   "motivo_confianza", "observado"]
SHAP_COLS = ["ID_POLIGONO", "modelo", "base_value", "regimen_A", "regimen_B", "rezago_y"]
FEATURE_COLS = ["ID_POLIGONO", "clima_prec_total_may_oct", "clima_anom_prec_total_may_oct",
                "sat25_s2_nddi_max", "fen_pico_doy", "hist_s2_ndvi_anom_max"]
SERIES_COLS = ["ID_POLIGONO", "indice", "anio", "dia_anio", "valor"]

# Serie: año de la temporada, años de historia y etiqueta de cada índice
CURRENT_YEAR = 2025
HISTORY_YEARS = (2022, 2023, 2024)
INDEX_LABELS = {"ndvi": "Verdor (NDVI)", "nddi": "Índice de sequía (NDDI)"}
MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
             "septiembre", "octubre", "noviembre", "diciembre"]
NOTE_CONTEXT = "Contexto; no entra al modelo final."
NOTE_TRAINING = ("Esta parcela se usó para entrenar el modelo; la predicción que se muestra es la "
                 "validada fuera de entrenamiento y no se desglosa con el mismo método.")


# Tablas de solo lectura: cada una se carga una vez y queda en memoria
@cache
def predictions_table():
    # Una fila por parcela. En las de entrenamiento la predicción es la fuera de fold
    return pd.read_parquet(OUTPUTS / "predicciones.parquet", columns=PREDICTION_COLS).set_index("ID_POLIGONO")


@cache
def shap_table():
    # Solo el modelo entregado (candidato); sus demás columnas de SHAP son NaN y no se usan
    df = pd.read_parquet(OUTPUTS / "shap_values.parquet", columns=SHAP_COLS)
    return df[df["modelo"] == "candidato"].drop(columns="modelo").set_index("ID_POLIGONO")


@cache
def features_table():
    # Variables de 2025 que la ficha muestra como contexto
    return pd.read_parquet(PROCESSED / "features.parquet", columns=FEATURE_COLS).set_index("ID_POLIGONO")


@cache
def series_table():
    # Serie de scripts/exportar_serie_ficha.py. Si el archivo no existe, la ficha sale sin serie
    ruta = PROCESSED / "serie_ficha.parquet"
    if not ruta.exists():
        return None
    return pd.read_parquet(ruta, columns=SERIES_COLS).astype({"valor": "float64"})


def warm_up():
    """Carga las tablas de predicciones y SHAP antes de aceptar peticiones; la serie se lee al primer uso."""
    predictions_table()
    shap_table()


# Conversiones: JSON no admite NaN ni Infinity, y jsonify no acepta int64 ni bool_ de numpy
def _number(value):
    if pd.isna(value):
        return None
    x = float(value)
    return x if math.isfinite(x) else None


def _integer(value):
    x = _number(value)
    return None if x is None else int(x)


def _rounded(value, digits):
    x = _number(value)
    return None if x is None else round(x, digits)


def _text(value):
    return None if pd.isna(value) else str(value)


def _row(table, parcel_id, name):
    # Toda parcela de predicciones debe estar también en las demás tablas; si no, el error lo dice
    if parcel_id not in table.index:
        raise AssertionError(f"Falta la parcela {parcel_id} en {name}")
    return table.loc[parcel_id]


def _date_2025(day_of_year):
    date = pd.Timestamp(CURRENT_YEAR, 1, 1) + pd.Timedelta(days=day_of_year - 1)
    return f"{date.day} de {MONTHS_ES[date.month - 1]} de {date.year}"


def _model_threshold():
    # El umbral lo guarda el modelo entregado (2.5 t/ha); se lee de ahí y no se escribe a mano
    return _number(load_model().umbral)


def _breakdown(parcel_id, pred):
    # Desglose SHAP del modelo entregado: base, régimen y rezago espacial. Debe sumar la predicción
    sh = _row(shap_table(), parcel_id, "shap_values.parquet (modelo candidato)")
    terms = [
        {"key": "regime", "label": "Régimen de medición",
         "value": float(sh["regimen_A"]) + float(sh["regimen_B"])},
        {"key": "neighbors", "label": "Parcelas medidas cercanas", "value": float(sh["rezago_y"])},
    ]
    base = float(sh["base_value"])
    total = base + sum(term["value"] for term in terms)
    # Se niega la comparación a propósito: con NaN, abs(...) > tol sería falso y el error pasaría
    if not abs(total - pred) <= 1e-6:
        raise AssertionError(f"El desglose SHAP de {parcel_id} suma {total}, pero la predicción es {pred}")
    return {"base": base, "terms": terms, "total": total}


def _model_inputs(row):
    # Lo que usa el modelo entregado para la parcela, en lenguaje sencillo
    return [
        {"key": "regime", "label": "Régimen de medición", "value": _text(row["regimen"]), "unit": None,
         "help": "Forma en que se reportó el rendimiento del municipio: A con dos decimales, B redondeado "
                 "a 0.5 o 0.1. Es una inferencia de los datos que los organizadores no han confirmado."},
        {"key": "area_ha", "label": "Superficie de la parcela", "value": _number(row["area_ha"]), "unit": "ha",
         "help": "No cambia la predicción ni el intervalo del modelo entregado. Solo se usa para la confianza: "
                 "si el área queda fuera del rango de su régimen, la confianza es baja."},
        {"key": "neighbors_400m", "label": "Parcelas medidas a 400 m o menos",
         "value": _integer(row["vecinos_400m"]), "unit": "parcelas",
         "help": "Parcelas con rendimiento medido del mismo régimen a 400 m o menos. Con ellas se calcula el "
                 "rezago espacial, la entrada principal del modelo. Sin ninguna, la predicción se acerca a la "
                 "media de su régimen."},
        {"key": "nearest_neighbor_m", "label": "Distancia a la parcela medida más cercana",
         "value": _number(row["dist_vecino_m"]), "unit": "m",
         "help": "Distancia a la parcela medida del mismo régimen más cercana. Si pasa de 800 m, "
                 "la confianza es baja."},
    ]


def _context_2025(parcel_id):
    # Variables de 2025 que la ficha muestra como contexto; el modelo final no las usa
    row = _row(features_table(), parcel_id, "features.parquet")
    peak = _integer(row["fen_pico_doy"])
    peak_note = NOTE_CONTEXT if peak is None else f"{NOTE_CONTEXT} Es el {_date_2025(peak)}."
    return [
        {"key": "clima_prec_total_may_oct", "label": "Lluvia de mayo a octubre",
         "value": _rounded(row["clima_prec_total_may_oct"], 1), "unit": "mm", "note": NOTE_CONTEXT},
        {"key": "clima_anom_prec_total_may_oct", "label": "Lluvia de mayo a octubre frente a 2022 a 2024",
         "value": _rounded(row["clima_anom_prec_total_may_oct"], 1), "unit": "mm",
         "note": f"{NOTE_CONTEXT} Lluvia de 2025 menos su promedio de 2022 a 2024; es negativa si llovió menos."},
        {"key": "sat25_s2_nddi_max", "label": "Máximo de NDDI de junio a octubre",
         "value": _rounded(row["sat25_s2_nddi_max"], 4), "unit": None,
         "note": f"{NOTE_CONTEXT} Índice de sequía con Sentinel-2."},
        {"key": "fen_pico_doy", "label": "Pico de verdor", "value": peak, "unit": "día del año",
         "note": peak_note},
        {"key": "hist_s2_ndvi_anom_max", "label": "Máximo de NDVI frente al promedio de 2022 a 2024",
         "value": _rounded(row["hist_s2_ndvi_anom_max"], 4), "unit": "NDVI",
         "note": f"{NOTE_CONTEXT} Máximo de 2025 menos su promedio de 2022 a 2024, con Sentinel-2."},
    ]


def _parcel_series(parcel_id):
    # NDVI y NDDI: la temporada de 2025 punto a punto y la historia de 2022 a 2024 por día del año
    table = series_table()
    if table is None:
        return None
    rows = table[table["ID_POLIGONO"] == parcel_id]
    if rows.empty:
        return None
    indices = {}
    for key, label in INDEX_LABELS.items():
        by_index = rows[rows["indice"] == key]
        current = by_index[by_index["anio"] == CURRENT_YEAR].sort_values("dia_anio")
        history = (by_index[by_index["anio"].isin(HISTORY_YEARS)]
                   .groupby("dia_anio")["valor"].agg(["mean", "min", "max"]))
        indices[key] = {
            "label": label,
            "current": {"doy": current["dia_anio"].tolist(),
                        "value": [_rounded(v, 4) for v in current["valor"]]},
            "history": {"doy": history.index.tolist(),
                        "mean": [_rounded(v, 4) for v in history["mean"]],
                        "min": [_rounded(v, 4) for v in history["min"]],
                        "max": [_rounded(v, 4) for v in history["max"]]},
        }
    return {"year": CURRENT_YEAR, "history_years": list(HISTORY_YEARS), "indices": indices}


def parcel_detail_data(parcel_id) -> dict:
    """Datos de la ficha de una parcela. Lanza KeyError si el ID no existe."""
    table = predictions_table()
    if parcel_id not in table.index:
        raise KeyError(parcel_id)
    row = table.loc[parcel_id]
    subset = _text(row["conjunto"])
    pred = _number(row["pred"])
    if subset == "PREDICCION":
        breakdown, note = _breakdown(parcel_id, pred), None
    else:
        # Las de entrenamiento muestran la predicción fuera de fold, que no tiene desglose SHAP
        breakdown, note = None, NOTE_TRAINING
    return {
        "id": parcel_id,
        "state": _text(row["estado"]),
        "municipality": _text(row["municipio"]),
        "set": subset,
        "regime": _text(row["regimen"]),
        "area_ha": _number(row["area_ha"]),
        "lon": _number(row["lon"]),
        "lat": _number(row["lat"]),
        "observed": _number(row["observado"]),
        "pred": pred,
        "p10": _number(row["p10"]),
        "p90": _number(row["p90"]),
        "threshold": _model_threshold(),
        "prob_below": _number(row["prob_bajo_umbral"]),
        "confidence": {
            "level": _text(row["confianza"]),
            "neighbors_400m": _integer(row["vecinos_400m"]),
            "nearest_neighbor_m": _number(row["dist_vecino_m"]),
            "reason": _text(row["motivo_confianza"]),
        },
        "breakdown": breakdown,
        "breakdown_note": note,
        "model_inputs": _model_inputs(row),
        "context_2025": _context_2025(parcel_id),
        "series": _parcel_series(parcel_id),
    }


@bp.get("/api/parcels/<parcel_id>")
def parcel_detail(parcel_id):
    if parcel_id not in predictions_table().index:
        return jsonify(error=f"Parcela desconocida: {parcel_id}"), 404
    return jsonify(parcel_detail_data(parcel_id))


# Página de la ficha. Las cuentas y las reglas de texto se arman aquí; la plantilla solo las acomoda
SET_LABELS = {"ENTRENAMIENTO": "Parcela de entrenamiento", "PREDICCION": "Parcela por predecir"}
# Semáforo de la economía y nivel de confianza: texto del badge y sufijo de su clase badge--<sufijo>
LIGHTS = {"verde": ("Riesgo bajo", "bajo"), "amarillo": ("Riesgo medio", "medio"), "rojo": ("Riesgo alto", "alto")}
CONFIDENCE = {"alta": ("Confianza alta", "bajo"), "media": ("Confianza media", "medio"),
              "baja": ("Confianza baja", "alto")}
# Los tres niveles de confianza de menor a mayor, con lo que significa cada uno
CONFIDENCE_STEPS = [
    ("baja", "Baja", "la más cercana está a más de 800 m, o el área de la parcela queda fuera del rango de su "
                     "régimen."),
    ("media", "Media", "ninguna a 400 m, pero la más cercana está a 800 m o menos."),
    ("alta", "Alta", "al menos una parcela medida a 400 m o menos."),
]
# Periodo del SIAP del contexto municipal; el número de años se cuenta con estos dos valores
SIAP_FIRST, SIAP_LAST = 2003, 2025
# Decimales de las variables de contexto de 2025; el pico de verdor es un día del año, sin decimales
CONTEXT_DECIMALS = {"clima_prec_total_may_oct": 1, "clima_anom_prec_total_may_oct": 1,
                    "sat25_s2_nddi_max": 4, "fen_pico_doy": 0, "hist_s2_ndvi_anom_max": 4}
MODEL_DECIMALS = {"area_ha": 2, "nearest_neighbor_m": 0}
# Rangos de la query, en el texto que ve la persona cuando se salen
PRICE_TEXT = (f"entre {formatting.money(economics.PRICE_RANGE[0])} y "
              f"{formatting.money(economics.PRICE_RANGE[1])} por tonelada")
BREAKEVEN_TEXT = f"entre {economics.BREAKEVEN_RANGE[0]:g} y {economics.BREAKEVEN_RANGE[1]:g} t/ha"


def _query_number(name, label, value_range, range_text):
    """Parámetro numérico de la query: None si viene vacío o no viene.

    Un texto que no es número o un valor fuera del rango lanza ValueError con un mensaje en español.
    """
    text = request.args.get(name, "").strip()
    if text == "":
        return None
    try:
        x = float(text)
    except ValueError:
        raise ValueError(f"{label} debe ser un número.") from None
    low, high = value_range
    if not (math.isfinite(x) and low <= x <= high):
        raise ValueError(f"{label} debe estar {range_text}.")
    return x


def _plain(value):
    # Número para el campo del formulario, sin separadores: 7000 o 4.5
    return f"{value:g}"


def _probability(value):
    # Las probabilidades salen de una distribución empírica, así que 0 % y 100 % sugieren una certeza
    # que no hay: los extremos se dicen con palabras (docs/capa_economica.md)
    if value is None:
        return formatting.MISSING
    if value < 0.01:
        return "menos de 1 %"
    if value > 0.99:
        return "más de 99 %"
    return formatting.percent(value)


def _share(value):
    # Fracción de 0 a 1 como ancho de un medidor en %, de 0 a 100; sin dato, el medidor queda vacío
    if value is None:
        return 0.0
    return round(min(max(value, 0.0), 1.0) * 100, 1)


def _money_signed(value):
    # Dinero con el menos tipográfico: −$12,669
    text = formatting.money(value)
    return "−" + text[1:] if text.startswith("-") else text


def _confidence_steps(level):
    # Indicador de tres pasos: cada nivel con su significado; el de la parcela marcado como actual.
    # filled dice si el segmento del paso va relleno (los niveles hasta el actual)
    rank = next((i for i, (key, _, _) in enumerate(CONFIDENCE_STEPS) if key == level), -1)
    return [{"key": key, "label": label, "help": help_text, "current": i == rank, "filled": i <= rank}
            for i, (key, label, help_text) in enumerate(CONFIDENCE_STEPS)]


def _signed(value):
    # Aporte con signo y con el menos tipográfico: +0.62 o −0.91
    text = formatting.number(value, 2)
    return text.replace("-", "−") if text.startswith("-") else "+" + text


def _value_text(value, digits, unit=None):
    # Valor con su unidad; si falta, el guion de «sin dato» y sin unidad
    if value is None:
        return formatting.MISSING
    text = formatting.number(value, digits)
    return f"{text} {unit}" if unit else text


def _parcels_text(count):
    if count is None:
        return formatting.MISSING
    return "1 parcela" if count == 1 else f"{count} parcelas"


def _breakdown_steps(ficha):
    # Una frase por término del desglose, en el mismo orden que el gráfico
    b = ficha["breakdown"]
    regime = ficha["regime"] or formatting.MISSING
    steps = [f"El promedio de las parcelas medidas es {formatting.number(b['base'], 2)} t/ha."]
    for term in b["terms"]:
        if term["key"] == "regime":
            steps.append(f"El régimen {regime} lo cambia en {_signed(term['value'])} t/ha.")
        else:
            steps.append(f"Las parcelas medidas cercanas lo cambian en {_signed(term['value'])} t/ha.")
    steps.append(f"Sumados, dan la predicción de la parcela: {formatting.number(b['total'], 2)} t/ha.")
    return steps


def _model_rows(inputs):
    rows = []
    for item in inputs:
        key = item["key"]
        if key == "neighbors_400m":
            text = _parcels_text(item["value"])
        elif key == "regime":
            text = item["value"] or formatting.MISSING
        else:
            text = _value_text(item["value"], MODEL_DECIMALS[key], item["unit"])
        rows.append({"label": item["label"], "text": text, "help": item["help"]})
    return rows


def _context_rows(items):
    return [{"label": item["label"], "note": item["note"],
             "text": _value_text(item["value"], CONTEXT_DECIMALS[item["key"]], item["unit"])}
            for item in items]


def _basis_text(econ, price, breakeven):
    # Con qué precio y equilibrio salen los riesgos de la franja de arriba: los del municipio o los que
    # eligió la persona en Economía
    if price is None:
        text = f"Con el precio del municipio, {formatting.money(econ['price'])} por tonelada"
    else:
        text = f"Con el precio elegido, {formatting.money(econ['price'])} por tonelada"
    if breakeven is not None:
        text += f", y el punto de equilibrio elegido, {formatting.number(breakeven, 2)} t/ha"
    return text + "."


def _view(ficha, econ, breakeven, price=None, adjust_open=False):
    # Textos y cuentas de la página, en el orden en que aparecen
    costs_label, costs_class = LIGHTS.get(econ["light_costs"], ("Sin semáforo", "neutro"))
    credit_label, credit_class = LIGHTS.get(econ["light_credit"], ("Sin semáforo", "neutro"))
    conf_label, conf_class = CONFIDENCE.get(ficha["confidence"]["level"], ("Sin dato de confianza", "neutro"))
    cuts = econ["light_cuts"]
    return {
        "set_label": SET_LABELS.get(ficha["set"], "Parcela"),
        "basis_text": _basis_text(econ, price, breakeven),
        # El formulario de Economía se abre si la persona ya lo usó o si trae un parámetro no válido
        "adjust_open": adjust_open,
        "prob_below": _probability(ficha["prob_below"]),
        "conf_label": conf_label,
        "conf_class": conf_class,
        "costs_text": _probability(econ["prob_not_cover_costs"]),
        "costs_label": costs_label,
        "costs_class": costs_class,
        "credit_text": _probability(econ["prob_not_pay_credit"]),
        "credit_label": credit_label,
        "credit_class": credit_class,
        # Ancho del relleno de cada medidor y posición de los cortes del semáforo, en % de la barra
        "costs_pct": _share(econ["prob_not_cover_costs"]),
        "credit_pct": _share(econ["prob_not_pay_credit"]),
        "cut_low_pct": _share(cuts["green_below"]),
        "cut_high_pct": _share(cuts["red_from"]),
        "conf_steps": _confidence_steps(ficha["confidence"]["level"]),
        # Margen con su signo; si es negativo la página lo dice con texto, no solo con color
        "margin_text": _money_signed(econ["margin_ha"]),
        "margin_negative": econ["margin_ha"] is not None and econ["margin_ha"] < 0,
        "loss_text": formatting.percent(econ["prob_loss"], 1),
        "cut_low": formatting.percent(cuts["green_below"]),
        "cut_high": formatting.percent(cuts["red_from"]),
        # Error típico del modelo en t/ha, en pesos por hectárea con el precio usado y como parte de los costos
        "error_t_ha": formatting.number(econ["model_error"]["t_ha"], 2),
        "error_money": formatting.money(econ["model_error"]["money_ha"]),
        "error_cost": formatting.percent(econ["model_error"]["share_cost_total"]),
        "error_credit": formatting.percent(econ["model_error"]["share_credit"]),
        "siap_years": f"{SIAP_FIRST} a {SIAP_LAST}",
        "siap_total": SIAP_LAST - SIAP_FIRST + 1,
        # El campo muestra el precio que se usó: el del municipio o el que escribió la persona
        "price_field": _plain(econ["price"]),
        "breakeven_field": "" if breakeven is None else _plain(breakeven),
        "breakdown_steps": _breakdown_steps(ficha) if ficha["breakdown"] else [],
        "model_rows": _model_rows(ficha["model_inputs"]),
        "context_rows": _context_rows(ficha["context_2025"]),
    }


@bp.get("/parcela/<parcel_id>")
def page(parcel_id):
    try:
        ficha = parcel_detail_data(parcel_id)
    except KeyError:
        return render_template("parcel.html", parcel_id=parcel_id, missing=True), 404
    error, price, breakeven = None, None, None
    try:
        price = _query_number("price", "El precio", economics.PRICE_RANGE, PRICE_TEXT)
        breakeven = _query_number("breakeven", "El punto de equilibrio", economics.BREAKEVEN_RANGE,
                                  BREAKEVEN_TEXT)
        econ = economics.parcel_economics_data(parcel_id, price=price, breakeven=breakeven)
    except ValueError as e:
        # Con un parámetro no válido, la página muestra la economía por defecto y avisa arriba de la franja
        error, price, breakeven = str(e), None, None
        econ = economics.parcel_economics_data(parcel_id)
    adjust_open = error is not None or "price" in request.args or "breakeven" in request.args
    view = _view(ficha, econ, breakeven, price=price, adjust_open=adjust_open)
    status = 400 if error else 200
    return render_template("parcel.html", parcel_id=parcel_id, missing=False, ficha=ficha, econ=econ,
                           view=view, error=error), status
