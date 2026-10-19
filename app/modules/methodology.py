# Metodología del modelo: página que lo explica y sus cifras en JSON
# Contrato:
#   GET /metodologia      página HTML, con la plantilla methodology.html y las gráficas de method_charts.py
#   GET /api/methodology  cifras de la metodología en JSON (ver methodology_data)
#   methodology_data()    función pura con esas cifras. Cada sección vale None si falta su archivo
#                         de outputs/ o el modelo; la página muestra un aviso en su lugar
from datetime import date
from functools import cache

import pandas as pd
from flask import Blueprint, jsonify, render_template

from parcelas.config import OUTPUTS

from . import method_charts, model

bp = Blueprint("methodology", __name__)
# Gráficas de la página, disponibles en las plantillas
bp.add_app_template_global(method_charts.coverage_chart, "coverage_chart")
bp.add_app_template_global(method_charts.groups_chart, "groups_chart")
bp.add_app_template_global(method_charts.rmse_chart, "rmse_chart")
bp.add_app_template_global(method_charts.neighbors_chart, "neighbors_chart")
bp.add_app_template_global(method_charts.contributions_chart, "contributions_chart")

SCHEMES = ("A", "B")
# Cuántos grupos de variables se muestran: los de mayor efecto al quitarlos
TOP_GROUPS = 8
# Etiquetas para mostrar en la página; las claves del JSON quedan en inglés
GROUP_LABELS = {"sat25_fen": "Fenología 2025"}
GROUP_KINDS = {"indice": "Índice satelital", "clima": "Clima", "bloque": "Bloque de variables"}
CONTRIBUTIONS = (("regime", "Régimen de etiquetas (A o B)"),
                 ("spatial_lag", "Parcelas medidas cercanas (rezago espacial)"))
# RMSE de una predicción que solo da la media de su régimen, en t/ha, por esquema de validación.
# Cifras del reporte: el A sale de outputs/prueba_t_corregida.json (media_regimen, 0.4889) y el B de
# outputs/ablaciones_v1.csv (paso v1_base, 0.4878). La página las usa como referencia del modelo
REGIME_MEAN_RMSE = {"A": 0.489, "B": 0.488}
MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")


@cache
def _read_output(name):
    """Tabla de outputs/ (CSV o parquet), o None si el archivo no existe. Se lee una sola vez."""
    path = OUTPUTS / name
    if not path.exists():
        return None
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)


def _round(value, digits=4):
    """Número nativo de Python, o None si falta: NaN no es JSON válido."""
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _model_or_none():
    """Modelo final cargado con model.load_model(); None si el archivo no existe."""
    try:
        return model.load_model()
    except FileNotFoundError:
        return None


def _long_date(iso_date):
    """'2026-10-07' pasa a '7 de octubre de 2026'."""
    day = date.fromisoformat(iso_date)
    return f"{day.day} de {MONTHS[day.month - 1]} de {day.year}"


def _section_model(m):
    if m is None:
        return None
    return {
        "version": m.version,
        "trained_on": m.fecha_entrenamiento,
        "n_train": int(m.metricas.get("n_entrenamiento", len(m.oof))),
        "threshold": _round(m.umbral),
        "interval_level": _round(m.metricas["intervalo"]["nivel"]),
    }


def _section_validation(m):
    if m is None:
        return None
    return [{"scheme": s, "rmse": _round(m.metricas[s]["rmse"]), "mae": _round(m.metricas[s]["mae"]),
             "r2": _round(m.metricas[s]["r2"]), "rmse_sd": _round(m.metricas[s]["rmse_std"])}
            for s in SCHEMES]


def _section_interval_coverage():
    t = _read_output("calibracion_p10.csv")
    if t is None:
        return None
    return [{"group": row.grupo, "parcels": int(row.parcelas), "coverage": _round(row.cobertura),
             "coverage_ci95": [_round(row.cobertura_ic_inf), _round(row.cobertura_ic_sup)],
             "width": _round(row.ancho), "below_p10": _round(row.cola_baja),
             "below_p10_ci95": [_round(row.cola_baja_ic_inf), _round(row.cola_baja_ic_sup)],
             "above_p90": _round(row.cola_alta)}
            for row in t.itertuples()]


def _section_confidence():
    # Filas = parcela en una repetición; parcelas = IDs distintos (una parcela puede caer en grupos distintos)
    t = _read_output("confianza_cv.csv")
    if t is None:
        return None
    return [{"group": row.grupo, "rows": int(row.filas), "parcels": int(row.parcelas),
             "mae": _round(row.mae), "below_p10": _round(row.cola_baja),
             "coverage": _round(row.cobertura)}
            for row in t.itertuples()]


def _section_no_neighbors_gap():
    # Diferencia de MAE entre 0 vecinos y al menos 1, con su intervalo de confianza
    t = _read_output("confianza_cv.csv")
    if t is None:
        return None
    row = t[t["grupo"] == "0"].iloc[0]
    return {"difference": _round(row.dif_mae_0_vs_1mas),
            "ci95": [_round(row.dif_ic_inf), _round(row.dif_ic_sup)]}


def _section_chance_margin():
    t = _read_output("margen_azar.csv")
    if t is None:
        return None
    row = t.iloc[0]
    return {"parcels": int(row.n_parcelas), "draws": int(row.sorteos),
            "rmse_mean": _round(row.rmse_media), "rmse_sd": _round(row.rmse_desv),
            "p05": _round(row.p05), "p95": _round(row.p95)}


def _section_final_model_contributions():
    sv, pred = _read_output("shap_values.parquet"), _read_output("predicciones.parquet")
    if sv is None or pred is None:
        return None
    # Las 59 parcelas de la entrega, con la fila del modelo entregado (candidato)
    entrega = pred.loc[pred["conjunto"] == "PREDICCION", "ID_POLIGONO"]
    cand = sv[(sv["modelo"] == "candidato") & sv["ID_POLIGONO"].isin(entrega)]
    # El régimen viene en dos columnas (regimen_A y regimen_B); su aporte total es la suma,
    # así base + aportes da la predicción
    aporte = {"regime": cand["regimen_A"] + cand["regimen_B"], "spatial_lag": cand["rezago_y"]}
    return [{"key": key, "label": label, "mean_abs_t_ha": _round(aporte[key].abs().mean())}
            for key, label in CONTRIBUTIONS]


def _section_other_groups():
    t = _read_output("importancias.parquet")
    if t is None:
        return None
    # Quitar cada grupo con el régimen presente, en el modelo de análisis (no en el entregado).
    # Positivo = el error empeora al quitar el grupo
    ablation = t[(t["escenario"] == "regimen_presente_completo") & (t["metodo"] == "ablacion_logo")]
    top = ablation.sort_values("importancia_media", ascending=False).head(TOP_GROUPS)
    return [{"group": row.grupo, "label": GROUP_LABELS.get(row.grupo, row.grupo),
             "kind": GROUP_KINDS.get(row.tipo, row.tipo), "delta_rmse": _round(row.importancia_media),
             "p05": _round(row.p05), "p95": _round(row.p95)}
            for row in top.itertuples()]


def methodology_data():
    """Cifras de la página y del JSON. Cada sección vale None si falta su archivo o el modelo."""
    m = _model_or_none()
    return {
        "model": _section_model(m),
        "validation": _section_validation(m),
        "interval_coverage": _section_interval_coverage(),
        "confidence_vs_error": _section_confidence(),
        "no_neighbors_mae_gap": _section_no_neighbors_gap(),
        "chance_margin": _section_chance_margin(),
        "final_model_contributions": _section_final_model_contributions(),
        "other_groups": _section_other_groups(),
    }


def warm_up():
    """Carga el modelo y los archivos de outputs/ antes de aceptar peticiones."""
    methodology_data()


@bp.get("/metodologia")
def page():
    values = methodology_data()
    trained_on = _long_date(values["model"]["trained_on"]) if values["model"] else None
    return render_template("methodology.html", methodology=values, trained_on=trained_on,
                           regime_mean_rmse=REGIME_MEAN_RMSE)


@bp.get("/api/methodology")
def data():
    return jsonify(methodology_data())
