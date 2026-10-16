import math
import re
import xml.etree.ElementTree as ET

import pytest

from app.modules import charts

NS = "{http://www.w3.org/2000/svg}"
NAN = float("nan")
INF = float("inf")
FONT_SIZE = 14

INTERVAL_ARGS = dict(p10=3.108, pred=3.661, p90=4.141, observed=3.5, threshold=2.5, breakeven=3.9)
# Casos de la revisión móvil: AGC_003, AGC_001 y umbral y equilibrio casi iguales
INTERVAL_AGC_003 = dict(p10=3.108, pred=3.661, p90=4.141, observed=None, threshold=2.5, breakeven=6.614)
INTERVAL_AGC_001 = dict(p10=2.472, pred=3.024, p90=3.504, observed=3.5, threshold=2.5, breakeven=3.902)
INTERVAL_NEAR_EQUAL = dict(p10=3.108, pred=3.661, p90=4.141, observed=3.5, threshold=3.50, breakeven=3.52)
INTERVAL_CASES = {
    "demo": INTERVAL_ARGS,
    "AGC_003": INTERVAL_AGC_003,
    "AGC_001": INTERVAL_AGC_001,
    "casi_iguales": INTERVAL_NEAR_EQUAL,
}
TERMS = [
    {"label": "Régimen de medición", "value": -0.912},
    {"label": "Parcelas medidas cercanas", "value": 0.616},
]
BREAKDOWN_ARGS = dict(base=3.957, terms=TERMS, total=3.661)


def season():
    # Temporada sintética determinista: serie del año y promedio histórico con su rango
    days = list(range(2, 360, 7))
    current = {
        "doy": days,
        "value": [round(0.2 + 0.6 * math.sin(math.pi * (d - 1) / 365), 3) for d in days],
    }
    history_days = list(range(3, 360, 5))
    mean = [round(0.25 + 0.55 * math.sin(math.pi * (d - 1) / 365), 3) for d in history_days]
    history = {
        "doy": history_days,
        "mean": mean,
        "min": [m - 0.1 for m in mean],
        "max": [m + 0.1 for m in mean],
    }
    return current, history


CHARTS = {
    "intervalo": lambda: charts.interval_bar(**INTERVAL_ARGS),
    "cascada": lambda: charts.breakdown_bars(**BREAKDOWN_ARGS),
    "linea": lambda: charts.line_chart(*season(), "NDVI 2025", "NDVI"),
}


def _root(svg):
    return ET.fromstring(svg)


def _ids(svg):
    return {element.get("id") for element in _root(svg).iter() if element.get("id")}


def _bars(svg):
    return [element for element in _root(svg).iter() if (element.get("class") or "").startswith("bar")]


def _texts(svg):
    return [element.text for element in _root(svg).iter(NS + "text")]


def _rect(svg):
    return next(_root(svg).iter(NS + "rect"))


def _viewbox(svg):
    _, _, width, height = (float(v) for v in _root(svg).get("viewBox").split())
    return width, height


def _text_boxes(svg):
    # Caja aproximada de cada texto: 0.56 em por carácter, 0.75 em sobre la línea base y 0.25 em bajo ella
    boxes = []
    for element in _root(svg).iter(NS + "text"):
        content = element.text or ""
        width = len(content) * FONT_SIZE * 0.56
        x, y = float(element.get("x")), float(element.get("y"))
        anchor = element.get("text-anchor")
        if anchor == "end":
            left = x - width
        elif anchor == "start":
            left = x
        else:
            left = x - width / 2
        boxes.append((content, left, left + width, y - 0.75 * FONT_SIZE, y + 0.25 * FONT_SIZE))
    return boxes


def _path_points(trazo):
    # Puntos finales de los comandos M, H, V y A de un trazo, para comprobar sus límites
    tokens = re.findall(r"[A-Za-z]|-?\d+(?:\.\d+)?", trazo)
    x = y = 0.0
    points = []
    command, i = None, 0
    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]
            i += 1
            if command == "Z":
                continue
        if command == "M":
            x, y = float(tokens[i]), float(tokens[i + 1])
            i += 2
        elif command == "H":
            x = float(tokens[i])
            i += 1
        elif command == "V":
            y = float(tokens[i])
            i += 1
        elif command == "A":
            x, y = float(tokens[i + 5]), float(tokens[i + 6])
            i += 7
        points.append((x, y))
    return points


def _positions(element):
    # Todas las posiciones que un elemento ocupa en el viewBox
    attributes = element.attrib
    pairs = []
    for name_x, name_y in (("x", "y"), ("x1", "y1"), ("x2", "y2"), ("cx", "cy")):
        if name_x in attributes and name_y in attributes:
            pairs.append((float(attributes[name_x]), float(attributes[name_y])))
    if element.tag == NS + "rect":
        pairs.append((float(attributes["x"]) + float(attributes["width"]),
                      float(attributes["y"]) + float(attributes["height"])))
    if "points" in attributes:
        pairs += [tuple(map(float, pair.split(","))) for pair in attributes["points"].split()]
    if "d" in attributes:
        pairs += _path_points(attributes["d"])
    return pairs


# (1) XML bien formado, raíz svg, role, título, descripción y aria-labelledby válido

@pytest.mark.parametrize("name", list(CHARTS))
def test_svg_is_well_formed_with_title_desc_and_ids(name):
    svg = CHARTS[name]()
    root = _root(svg)
    assert root.tag == NS + "svg"
    assert root.get("role") == "img"
    assert root.get("class") == "chart"
    title = root.find(NS + "title")
    desc = root.find(NS + "desc")
    assert title is not None and title.text and title.text.strip()
    assert desc is not None and desc.text and desc.text.strip()
    references = root.get("aria-labelledby").split()
    assert references == [title.get("id"), desc.get("id")]
    assert all(reference in _ids(svg) for reference in references)


def test_viewbox_is_360_wide_and_style_caps_at_420px():
    for name in CHARTS:
        svg = CHARTS[name]()
        assert _viewbox(svg)[0] == 360
        assert "max-width:420px" in svg


# (2) Determinismo: mismos argumentos, mismo texto; uid distinto, ids distintos

@pytest.mark.parametrize("name", list(CHARTS))
def test_same_arguments_give_same_svg(name):
    assert CHARTS[name]() == CHARTS[name]()


def test_distinct_uid_does_not_share_ids():
    first = charts.interval_bar(3.108, 3.661, 4.141, uid="ficha-a")
    second = charts.interval_bar(3.108, 3.661, 4.141, uid="ficha-b")
    assert _ids(first) and _ids(second)
    assert not _ids(first) & _ids(second)


def test_default_uid_differs_between_chart_types():
    assert not _ids(charts.interval_bar(**INTERVAL_ARGS)) & _ids(charts.breakdown_bars(**BREAKDOWN_ARGS))


# (3) Escapado de texto dinámico

def test_dynamic_text_is_escaped():
    svg = charts.breakdown_bars(3.0, [{"label": "<b>&", "value": 0.5}], 3.5)
    assert "&lt;b&gt;&amp;" in svg
    assert "<b>" not in svg
    ET.fromstring(svg)


def test_line_chart_labels_are_escaped():
    current, history = season()
    svg = charts.line_chart(current, history, "<b>&", "<b>&", current_label="<b>&")
    assert "&lt;b&gt;&amp;" in svg
    assert "<b>" not in svg
    ET.fromstring(svg)


# (4) Nunca aparecen nan, inf ni None con datos ausentes o no finitos

def test_never_outputs_nan_inf_or_none():
    current, history = season()
    current["value"][3] = None
    current["value"][5] = NAN
    history["mean"][2] = None
    history["min"][4] = NAN
    history["max"][6] = INF
    svgs = [
        charts.interval_bar(3.1, 3.6, 4.1, observed=NAN, threshold=None, breakeven=INF),
        charts.breakdown_bars(3.9, [
            {"label": "a", "value": None},
            {"label": "b", "value": NAN},
            {"label": "c", "value": 0.2},
        ], 3.9),
        charts.line_chart(current, history, "titulo", "eje"),
    ]
    for svg in svgs:
        for word in ("nan", "inf", "None"):
            assert word not in svg


def test_missing_data_returns_notice():
    current, history = season()
    assert charts.interval_bar(3.1, NAN, 4.1) == charts.NO_DATA
    assert charts.breakdown_bars(3.9, TERMS, None) == charts.NO_DATA
    assert "Sin datos para mostrar." in charts.line_chart({"doy": [], "value": []}, history, "t", "y")


# (5) interval_bar: extensión del eje, etiquetas opcionales y posición de la predicción

def test_axis_extends_when_p90_is_above_6():
    rect = _rect(charts.interval_bar(3.1, 3.7, 6.2))
    assert float(rect.get("x")) + float(rect.get("width")) <= 312 + 1e-6


def test_axis_extends_when_p10_is_below_1_5():
    svg = charts.interval_bar(1.2, 1.8, 2.4)
    assert float(_rect(svg).get("x")) >= 16 - 1e-6
    # El entero 1 solo aparece como marca si el eje se extendió
    assert ">1</text>" in svg
    assert ">1</text>" not in charts.interval_bar(3.1, 3.7, 4.1)


def test_threshold_and_breakeven_have_labels():
    texts = _texts(charts.interval_bar(**INTERVAL_ARGS))
    assert "Umbral 2.5" in texts
    assert "Equilibrio 3.9" in texts
    assert "Reportado 3.50" in texts
    assert "Predicción 3.66" in texts
    assert "Umbral" not in " ".join(_texts(charts.interval_bar(3.1, 3.7, 4.1)))


@pytest.mark.parametrize("svg", [charts.interval_bar(**INTERVAL_ARGS), charts.interval_bar(1.2, 1.8, 2.4)])
def test_prediction_circle_is_between_range_ends(svg):
    rect = _rect(svg)
    circle = next(_root(svg).iter(NS + "circle"))
    left = float(rect.get("x"))
    right = left + float(rect.get("width"))
    assert left < float(circle.get("cx")) < right


@pytest.mark.parametrize("args", list(INTERVAL_CASES.values()))
def test_labels_in_the_same_row_do_not_overlap(args):
    boxes = _text_boxes(charts.interval_bar(**args))
    for i, (text_a, left_a, right_a, top_a, bottom_a) in enumerate(boxes):
        for text_b, left_b, right_b, top_b, bottom_b in boxes[i + 1:]:
            overlap_x = left_a < right_b and left_b < right_a
            overlap_y = top_a < bottom_b and top_b < bottom_a
            assert not (overlap_x and overlap_y), (text_a, text_b)


# (6) breakdown_bars: barras por término, color por signo y filas sin términos

def test_breakdown_has_terms_plus_two_bars():
    assert len(_bars(charts.breakdown_bars(**BREAKDOWN_ARGS))) == len(TERMS) + 2
    assert len(_bars(charts.breakdown_bars(3.9, [], 3.8))) == 2


def test_breakdown_colors_follow_sign():
    svg = charts.breakdown_bars(**BREAKDOWN_ARGS)
    colors = {bar.get("class"): bar.get("fill") for bar in _bars(svg)}
    assert colors["bar bar-down"] == "#d55e00"
    assert colors["bar bar-up"] == "#2a78d6"
    assert "−0.91" in _texts(svg) and "+0.62" in _texts(svg)


# (7) line_chart: puntos de la serie, un solo punto y mallas distintas por serie

def _current_polyline(svg):
    return next(element for element in _root(svg).iter(NS + "polyline")
                if "primario-oscuro" in (element.get("stroke") or ""))


def test_current_series_has_one_point_per_valid_value():
    current, history = season()
    current["value"][3] = None
    current["value"][10] = NAN
    valid = sum(1 for value in current["value"] if value is not None and not math.isnan(value))
    svg = charts.line_chart(current, history, "t", "y")
    assert len(_current_polyline(svg).get("points").split()) == valid


def test_single_point_series_does_not_fail():
    svg = charts.line_chart({"doy": [100], "value": [0.5]},
                            {"doy": [100], "mean": [0.4], "min": [0.3], "max": [0.5]}, "t", "y")
    assert _root(svg).tag == NS + "svg"


def test_separate_day_meshes_are_drawn_on_their_own_days():
    current, history = season()  # serie en 2, 9, 16...; historia en 3, 8, 13...
    svg = charts.line_chart(current, history, "t", "y")
    x_current = float(_current_polyline(svg).get("points").split()[0].split(",")[0])
    mean = next(element for element in _root(svg).iter(NS + "polyline") if element.get("stroke-dasharray"))
    x_mean = float(mean.get("points").split()[0].split(",")[0])
    # Eje de enero a diciembre (1 a 366) entre x = 40 y x = 348
    assert abs(x_current - (40 + (2 - 1) / 365 * 308)) < 0.06
    assert abs(x_mean - (40 + (3 - 1) / 365 * 308)) < 0.06
    assert x_current != x_mean


def test_legend_wraps_to_two_rows_when_it_does_not_fit():
    # Con 360 unidades, las tres entradas no caben en una fila: el viewBox crece
    assert _viewbox(CHARTS["linea"]())[1] > 300


# (8) Todos los valores numéricos son finitos y quedan dentro del viewBox

@pytest.mark.parametrize("name", list(CHARTS))
def test_coordinates_are_finite_and_inside_viewbox(name):
    root = _root(CHARTS[name]())
    width, height = _viewbox(CHARTS[name]())
    tolerance = 0.5
    for element in root.iter():
        for value in element.attrib.values():
            try:
                assert math.isfinite(float(value))
            except ValueError:
                pass
        for x, y in _positions(element):
            assert math.isfinite(x) and math.isfinite(y)
            assert -tolerance <= x <= width + tolerance
            assert -tolerance <= y <= height + tolerance


# (9) Todo texto cae dentro del viewBox y no se solapa con otro texto

def _every_chart():
    svgs = [(f"intervalo {name}", charts.interval_bar(**args)) for name, args in INTERVAL_CASES.items()]
    svgs.append(("cascada", charts.breakdown_bars(**BREAKDOWN_ARGS)))
    svgs.append(("linea", CHARTS["linea"]()))
    return svgs


@pytest.mark.parametrize("name, svg", _every_chart())
def test_all_text_is_inside_viewbox(name, svg):
    width, height = _viewbox(svg)
    for content, left, right, top, bottom in _text_boxes(svg):
        assert left >= 0 and right <= width, (name, content)
        assert top >= 0 and bottom <= height, (name, content)


@pytest.mark.parametrize("name, svg", _every_chart())
def test_no_text_overlaps_in_any_chart(name, svg):
    boxes = _text_boxes(svg)
    for i, (text_a, left_a, right_a, top_a, bottom_a) in enumerate(boxes):
        for text_b, left_b, right_b, top_b, bottom_b in boxes[i + 1:]:
            overlap_x = left_a < right_b and left_b < right_a
            overlap_y = top_a < bottom_b and top_b < bottom_a
            assert not (overlap_x and overlap_y), (name, text_a, text_b)
