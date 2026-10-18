# Gráficas SVG de la página de metodología (app/modules/method_charts.py): que dibujen exactamente
# los datos, que manejen None y listas vacías, y que cada <svg> tenga título y descripción
import re
import xml.etree.ElementTree as ET

import pytest

from app.modules import method_charts as mc

NS = "{http://www.w3.org/2000/svg}"
NAN = float("nan")

COVERAGE = [
    {"group": "A", "parcels": 87, "coverage": 0.7908, "coverage_ci95": [0.7103, 0.869]},
    {"group": "B", "parcels": 51, "coverage": 0.8863, "coverage_ci95": [0.8157, 0.9491]},
    {"group": "global", "parcels": 138, "coverage": 0.8261, "coverage_ci95": [0.7681, 0.8812]},
]
GROUPS = [
    {"label": "Fenología 2025", "delta_rmse": 0.0121, "p05": 0.0062, "p95": 0.016},
    {"label": "Grados-día", "delta_rmse": 0.0057, "p05": 0.0017, "p95": 0.0081},
    {"label": "EVI", "delta_rmse": 0.0039, "p05": -0.0011, "p95": 0.0085},
]
VALIDATION = [{"scheme": "A", "rmse": 0.4582}, {"scheme": "B", "rmse": 0.4888}]
BASELINE = {"A": 0.489, "B": 0.488}
NEIGHBORS = [
    {"group": "0", "rows": 353, "mae": 0.3716},
    {"group": "1-2", "rows": 306, "mae": 0.2523},
    {"group": "3 o más", "rows": 31, "mae": 0.2148},
]
CONTRIBUTIONS = [
    {"label": "Régimen de etiquetas (A o B)", "mean_abs_t_ha": 0.0994},
    {"label": "Parcelas medidas cercanas (rezago espacial)", "mean_abs_t_ha": 0.5933},
]
CHARTS = {
    "coverage": lambda: mc.coverage_chart(COVERAGE, 0.8),
    "groups": lambda: mc.groups_chart(GROUPS),
    "rmse": lambda: mc.rmse_chart(VALIDATION, BASELINE),
    "neighbors": lambda: mc.neighbors_chart(NEIGHBORS),
    "contributions": lambda: mc.contributions_chart(CONTRIBUTIONS),
}


def svgs(markup):
    # Las dos versiones (ancha y angosta) como árboles XML
    parts = re.findall(r"<svg.*?</svg>", str(markup), flags=re.S)
    return [ET.fromstring(part) for part in parts]


def texts(svg):
    return ["".join(node.itertext()) for node in svg.iter(f"{NS}text")]


def bar_ends(svg):
    # Inicio y fin en x de cada barra: el trazo empieza en la base y el primer arco cierra el extremo
    ends = []
    for path in svg.iter(f"{NS}path"):
        d = path.get("d")
        start = float(re.match(r"M(-?[\d.]+),", d).group(1))
        end = float(re.search(r"A[\d.]+,[\d.]+ 0 0 1 (-?[\d.]+),", d).group(1))
        ends.append((start, end))
    return ends


def assert_linear(values, positions):
    # Las posiciones son una proyección lineal de los valores: misma razón entre cualquier par
    ratio = (positions[-1] - positions[0]) / (values[-1] - values[0])
    for value, position in zip(values, positions):
        assert position == pytest.approx(positions[0] + (value - values[0]) * ratio, abs=0.15)


@pytest.mark.parametrize("name", CHARTS)
def test_two_versions_with_title_and_desc(name):
    wide, narrow = svgs(CHARTS[name]())
    assert "method-chart--wide" in wide.get("class")
    assert "method-chart--narrow" in narrow.get("class")
    assert wide.get("viewBox").startswith(f"0 0 {mc.WIDE} ")
    assert narrow.get("viewBox").startswith(f"0 0 {mc.NARROW} ")
    ids = []
    for svg in (wide, narrow):
        assert svg.get("role") == "img"
        title, desc = svg.find(f"{NS}title"), svg.find(f"{NS}desc")
        assert title is not None and title.text
        assert desc is not None and desc.text
        assert svg.get("aria-labelledby") == f"{title.get('id')} {desc.get('id')}"
        ids += [title.get("id"), desc.get("id")]
    # Los ids no se repiten entre las dos versiones
    assert len(set(ids)) == 4


def test_coverage_draws_points_whiskers_and_target():
    for svg in svgs(CHARTS["coverage"]()):
        circles = list(svg.iter(f"{NS}circle"))
        assert len(circles) == 3
        xs = [float(c.get("cx")) for c in circles]
        values = [row["coverage"] for row in COVERAGE]
        order = sorted(range(3), key=lambda i: values[i])
        assert_linear([values[i] for i in order], [xs[i] for i in order])
        # El bigote va del límite inferior al superior del IC 95 %, en la misma escala que el punto
        whiskers = [line for line in svg.iter(f"{NS}line") if line.get("stroke-linecap") == "round"]
        assert len(whiskers) == 3
        ratio = (xs[1] - xs[0]) / (values[1] - values[0])
        for line, row, x in zip(whiskers, COVERAGE, xs):
            lo, hi = row["coverage_ci95"]
            assert float(line.get("x1")) == pytest.approx(x + (lo - row["coverage"]) * ratio, abs=0.2)
            assert float(line.get("x2")) == pytest.approx(x + (hi - row["coverage"]) * ratio, abs=0.2)
        # Línea de meta en 80 %, con su rótulo
        target = [line for line in svg.iter(f"{NS}line") if line.get("stroke-dasharray")]
        assert len(target) == 1
        assert float(target[0].get("x1")) == pytest.approx(xs[0] + (0.8 - values[0]) * ratio, abs=0.2)
        labels = texts(svg)
        assert "Meta 80 %" in labels
        for value in ("79.1 %", "88.6 %", "82.6 %"):
            assert value in labels
        assert "Régimen A" in labels and "138 parcelas" in labels
        # El eje no empieza en 0 %, y la descripción lo dice
        assert "0 %" not in labels
        assert "no empieza en 0 %" in svg.find(f"{NS}desc").text


def test_groups_forest_order_zero_line_and_selective_label():
    for svg in svgs(CHARTS["groups"]()):
        circles = list(svg.iter(f"{NS}circle"))
        assert len(circles) == len(GROUPS)
        # Las filas siguen el orden recibido, de arriba abajo
        ys = [float(c.get("cy")) for c in circles]
        assert ys == sorted(ys)
        xs = [float(c.get("cx")) for c in circles]
        values = [row["delta_rmse"] for row in GROUPS]
        assert_linear(values[::-1], xs[::-1])
        # Línea vertical en 0, en tinta suave y no en el gris de la rejilla
        ratio = (xs[0] - xs[-1]) / (values[0] - values[-1])
        x_zero = xs[0] - values[0] * ratio
        zero = [line for line in svg.iter(f"{NS}line")
                if line.get("x1") == line.get("x2") and abs(float(line.get("x1")) - x_zero) < 0.2]
        assert zero and zero[0].get("stroke") == mc.INK_MUTED
        # Solo el grupo de mayor efecto lleva su valor escrito
        labels = texts(svg)
        assert "0.012" in labels
        assert "0.006" not in labels and "0.004" not in labels
        # El EVI cruza el 0: su bigote empieza a la izquierda de la línea
        whiskers = [line for line in svg.iter(f"{NS}line") if line.get("stroke-linecap") == "round"]
        assert float(whiskers[-1].get("x1")) < x_zero


def test_rmse_bars_start_at_zero_and_have_legend():
    for svg in svgs(CHARTS["rmse"]()):
        ends = bar_ends(svg)
        assert len(ends) == 4
        starts = {round(start, 1) for start, _ in ends}
        assert len(starts) == 1  # todas parten de la misma base, el 0
        lengths = [end - start for start, end in ends]
        values = [0.4582, 0.489, 0.4888, 0.488]
        for length, value in zip(lengths, values):
            assert length / value == pytest.approx(lengths[0] / values[0], rel=0.01)
        labels = texts(svg)
        assert "Modelo" in labels and "Media por régimen" in labels
        for value in ("0.458", "0.489", "0.488"):
            assert value in labels
        # Modelo en el color de los datos, referencia en gris
        fills = [path.get("fill") for path in svg.iter(f"{NS}path")]
        assert fills == [mc.DATA, mc.NEUTRAL, mc.DATA, mc.NEUTRAL]


def test_neighbors_bars_match_mae():
    for svg in svgs(CHARTS["neighbors"]()):
        ends = bar_ends(svg)
        lengths = [end - start for start, end in ends]
        values = [row["mae"] for row in NEIGHBORS]
        assert len(lengths) == 3
        for length, value in zip(lengths, values):
            assert length / value == pytest.approx(lengths[0] / values[0], rel=0.01)
        joined = " ".join(texts(svg))
        for text in ("0 vecinos", "1 a 2 vecinos", "3 o más vecinos", "353 filas", "0.372", "0.215"):
            assert text in joined


def test_contributions_long_labels_go_above_bars():
    for svg in svgs(CHARTS["contributions"]()):
        ends = bar_ends(svg)
        assert len(ends) == 2
        assert (ends[1][1] - ends[1][0]) / (ends[0][1] - ends[0][0]) == pytest.approx(0.5933 / 0.0994, rel=0.01)
        # Etiqueta encima de la barra: el texto empieza en la base, no en una columna aparte
        label = next(t for t in svg.iter(f"{NS}text") if "".join(t.itertext()).startswith("Parcelas medidas"))
        assert float(label.get("x")) == pytest.approx(ends[0][0] + 4, abs=0.2)
        # El texto nunca sale del viewBox
        width = float(svg.get("viewBox").split()[2])
        assert all(end <= width for _, end in ends)


@pytest.mark.parametrize("chart", [mc.coverage_chart, mc.groups_chart, mc.neighbors_chart, mc.contributions_chart])
@pytest.mark.parametrize("rows", [None, []])
def test_empty_input_shows_notice(chart, rows):
    assert chart(rows) == mc.NO_DATA


def test_rmse_without_data_shows_notice():
    assert mc.rmse_chart(None, BASELINE) == mc.NO_DATA
    assert mc.rmse_chart([{"scheme": "A", "rmse": None}], {}) == mc.NO_DATA


def test_missing_values_are_skipped_not_drawn():
    rows = [dict(COVERAGE[0]), dict(COVERAGE[1], coverage=NAN), dict(COVERAGE[2], coverage_ci95=[None, None])]
    for svg in svgs(mc.coverage_chart(rows)):
        assert len(list(svg.iter(f"{NS}circle"))) == 2
        whiskers = [line for line in svg.iter(f"{NS}line") if line.get("stroke-linecap") == "round"]
        assert len(whiskers) == 1
        assert "Sin dato" in texts(svg)
    neighbors = [dict(NEIGHBORS[0]), dict(NEIGHBORS[1], mae=None)]
    for svg in svgs(mc.neighbors_chart(neighbors)):
        assert len(bar_ends(svg)) == 1
        assert "Sin dato" in texts(svg)
    # Sin referencia del esquema B, solo esa barra falta
    for svg in svgs(mc.rmse_chart(VALIDATION, {"A": 0.489})):
        assert len(bar_ends(svg)) == 3


def test_labels_are_escaped():
    rows = [{"label": "<b>Grupo & otro</b>", "delta_rmse": 0.01, "p05": 0.0, "p95": 0.02}]
    markup = str(mc.groups_chart(rows))
    assert "<b>" not in markup
    assert "&lt;b&gt;Grupo &amp; otro&lt;/b&gt;" in markup
    assert len(svgs(markup)) == 2
