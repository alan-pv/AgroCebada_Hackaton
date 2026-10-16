# Gráficas SVG puras para la ficha de parcela. Cada función devuelve un <svg> completo
# (markupsafe.Markup) que dibuja exactamente los datos que recibe. No registra nada en Flask:
# app/modules/detail.py las registra como globales de plantilla (interval_bar, breakdown_bars y
# line_chart); como devuelven Markup, la plantilla los inserta sin volver a escaparlos.
import hashlib
import math
import re
from bisect import bisect_right

from markupsafe import Markup, escape

from .formatting import number

NO_DATA = Markup('<p class="muted">Sin datos para mostrar.</p>')

# Paleta fija de la especificación: azul para aumentos, naranja para disminuciones
COLOR_INCREASE = "#2a78d6"
COLOR_DECREASE = "#d55e00"
# Gris neutro para las barras de referencia de la cascada (promedio medido)
COLOR_NEUTRAL = "#898781"
# Tintas de texto: nunca el color de un dato
INK = "var(--texto, #1f2a1f)"
INK_MUTED = "var(--texto-suave, #52514e)"

MINUS = "−"  # signo menos tipográfico, para los valores negativos
WIDTH = 360
FONT_SIZE = 14
# Distancia mínima en x entre dos etiquetas de la misma fila (regla de colisión)
LABEL_MIN_GAP = 70
LABEL_PADDING = 6

MONTH_NAMES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
MONTH_ABBRS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
# Primer día del año (año sin bisiesto) de cada mes; el último valor marca el fin de diciembre
MONTH_STARTS = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335, 367]
MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _finite(value):
    # Devuelve el valor como float si es finito; None, NaN e infinitos dan None
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _fmt(value):
    # Coordenadas con 1 decimal; evita "-0.0"
    text = f"{value:.1f}"
    return "0.0" if text == "-0.0" else text


def _text(value):
    # Todo texto dinámico pasa por escape(); None se convierte en cadena vacía
    return str(escape("" if value is None else value))


def _uid(kind, uid, *args):
    # Identificador base: el dado por el llamador, o uno estable derivado de los argumentos
    if uid is None:
        summary = repr((kind,) + args).encode("utf-8")
        uid = f"{kind}-{hashlib.sha1(summary).hexdigest()[:8]}"
    # Solo caracteres válidos en un id y en aria-labelledby (sin espacios)
    return re.sub(r"[^A-Za-z0-9_-]", "-", str(uid))


def _text_width(text):
    # Estimación conservadora del ancho de una etiqueta en píxeles de viewBox
    return len(text) * FONT_SIZE * 0.56


def _trimmed_decimals(value):
    # Hasta 2 decimales sin ceros sobrantes, pero con al menos uno: 2.5, 3.9, 2.25
    text = number(value, 2)
    if "." in text:
        text = text.rstrip("0")
        if text.endswith("."):
            text += "0"
    return text


def _signed(value):
    # +0.62 / −0.91: el signo siempre aparece en el texto, no solo el color
    text = number(abs(value), 2)
    if value < 0:
        return MINUS + text
    if value > 0:
        return "+" + text
    return text


def _svg(uid, height, title, description, body):
    # Envoltorio común: viewBox de ancho WIDTH (360), título y descripción con ids propios
    return Markup(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {_fmt(height)}" '
        f'role="img" aria-labelledby="{uid}-t {uid}-d" class="chart" '
        'style="display:block;width:100%;max-width:420px;height:auto;font-family:inherit">'
        f'<title id="{uid}-t">{_text(title)}</title>'
        f'<desc id="{uid}-d">{_text(description)}</desc>'
        + "".join(body)
        + "</svg>"
    )


def _svg_text(x, y, text, anchor="middle", color=INK):
    # Texto de la gráfica: FONT_SIZE (14 unidades del viewBox), en tinta de texto (nunca el color del dato)
    return (
        f'<text x="{_fmt(x)}" y="{_fmt(y)}" font-size="{FONT_SIZE}" '
        f'text-anchor="{anchor}" fill="{color}">{_text(text)}</text>'
    )


def _halo_text(x, y, text, anchor="middle"):
    # Texto con halo del color de la tarjeta: sigue legible si una línea de referencia lo cruza
    return (
        f'<text x="{_fmt(x)}" y="{_fmt(y)}" font-size="{FONT_SIZE}" text-anchor="{anchor}" '
        f'fill="{INK}" stroke="var(--tarjeta, #ffffff)" stroke-width="4" '
        f'stroke-linejoin="round" paint-order="stroke">{_text(text)}</text>'
    )


def _scale(value, domain, span):
    # Proyección lineal de un valor del dominio (lo, hi) al rango (a, b)
    lo, hi = domain
    a, b = span
    return a + (value - lo) / (hi - lo) * (b - a)


def _nice_ticks(lo, hi):
    # Marcas "bonitas" (paso 1, 2, 2.5 o 5 por potencia de 10) con 4 a 6 marcas que
    # cubren [lo, hi]. Devuelve la lista de marcas y el paso.
    if hi - lo < 1e-12:
        margin = max(abs(lo) * 0.1, 0.5)
        lo, hi = lo - margin, hi + margin
    power = math.floor(math.log10(hi - lo))
    candidates = []
    for exponent in range(power - 2, power + 2):
        for factor in (1, 2, 2.5, 5):
            step = factor * 10.0 ** exponent
            start = math.floor(lo / step + 1e-9) * step
            end = math.ceil(hi / step - 1e-9) * step
            intervals = round((end - start) / step)
            candidates.append((step, intervals, start))
    candidates.sort(key=lambda candidate: candidate[0])
    # 4 a 6 marcas son 3 a 5 intervalos; si ninguno encaja, el más cercano a 4
    in_range = [c for c in candidates if 3 <= c[1] <= 5]
    step, intervals, start = in_range[0] if in_range else min(candidates, key=lambda c: abs(c[1] - 4))
    ticks = [round(start + i * step, 10) for i in range(intervals + 1)]
    return ticks, step


def _tick_decimals(ticks):
    # Menor número de decimales (0 a 4) con el que cada marca se escribe exacta
    for decimals in range(5):
        if all(abs(round(tick, decimals) - tick) < 1e-9 for tick in ticks):
            return decimals
    return 4


def _format_number(value, decimals):
    # Número con el formato de la app; el signo menos va tipográfico
    return number(value, decimals).replace("-", MINUS)


def _clamp_center(x, width):
    # Desplaza el centro de una etiqueta para que no salga del viewBox
    half = width / 2
    return min(max(x, 4 + half), WIDTH - 4 - half)


def _collides(a, b):
    # Dos etiquetas chocan si sus centros quedan a menos de 70 unidades en x o si sus cajas se solapan
    center_a = (a["left"] + a["right"]) / 2
    center_b = (b["left"] + b["right"]) / 2
    boxes_overlap = a["left"] < b["right"] + LABEL_PADDING and b["left"] < a["right"] + LABEL_PADDING
    return abs(center_a - center_b) < LABEL_MIN_GAP or boxes_overlap


def _covers(label, x):
    # ¿La caja de la etiqueta, con margen, ocupa la posición x?
    return label["left"] - LABEL_PADDING <= x <= label["right"] + LABEL_PADDING


def _blocks(label, row, other, other_row):
    # Una fila no sirve si la etiqueta choca con otra de la misma fila, o si una línea de
    # referencia atraviesa el texto de la otra (las líneas bajan desde su etiqueta hasta el eje)
    if row == other_row and _collides(label, other):
        return True
    if other["is_line"] and other_row > row and _covers(label, other["mark"]):
        return True
    if label["is_line"] and other_row < row and _covers(other, label["mark"]):
        return True
    return False


def _label_rows(labels):
    # Fila de cada etiqueta, en orden de entrada; la fila 0 es la más cercana a la barra.
    # Cada etiqueta sube a la primera fila libre; si no hay ninguna, usa la primera sin choque directo.
    rows = []
    placed = []
    for label in labels:
        candidates = range(len(placed) + 1)
        row = next(
            (r for r in candidates if not any(_blocks(label, r, other, g) for other, g in placed)),
            None,
        )
        if row is None:
            row = next(r for r in candidates if not any(r == g and _collides(label, o) for o, g in placed))
        rows.append(row)
        placed.append((label, row))
    return rows


def _label(text, mark, kind):
    # Etiqueta de un marcador: texto, x del valor y tipo ("predicted", "observed", "threshold", "breakeven")
    return {
        "text": text,
        "mark": mark,
        "kind": kind,
        "is_line": kind in ("threshold", "breakeven"),
        "width": _text_width(text),
    }


def _place_label(label, anchor):
    # Coloca la caja de la etiqueta respecto a su marca; False si no cabe con ese anclaje
    width, mark = label["width"], label["mark"]
    if anchor == "end":
        left = mark - 4 - width
        if left < 4:
            return False
    elif anchor == "start":
        left = mark + 4
        if left + width > WIDTH - 4:
            return False
    else:
        left = _clamp_center(mark, width) - width / 2
    label.update(left=left, right=left + width, anchor=anchor)
    return True


def _label_text_x(label):
    # Posición x y anclaje SVG del texto de una etiqueta ya colocada
    if label["anchor"] == "start":
        return label["left"], "start"
    if label["anchor"] == "end":
        return label["right"], "end"
    return (label["left"] + label["right"]) / 2, "middle"


def interval_bar(p10, pred, p90, observed=None, threshold=None, breakeven=None, axis=(1.5, 6.0), uid=None):
    """Barra de intervalo en t/ha: rango p10-p90, predicción y marcadores opcionales."""
    low, mid, high = _finite(p10), _finite(pred), _finite(p90)
    if low is None or mid is None or high is None:
        return NO_DATA
    if low > high:
        low, high = high, low
    observed_value = _finite(observed)
    threshold_value = _finite(threshold)
    breakeven_value = _finite(breakeven)
    lo, hi = _finite(axis[0]), _finite(axis[1])
    if lo is None or hi is None or lo >= hi:
        raise ValueError("axis debe ser (minimo, maximo) finitos, con minimo < maximo")
    # El eje se extiende a múltiplos de 0.5 para incluir cualquier valor que caiga fuera
    values = [low, mid, high] + [v for v in (observed_value, threshold_value, breakeven_value) if v is not None]
    if min(values) < lo:
        lo = math.floor(min(values) * 2) / 2
    if max(values) > hi:
        hi = math.ceil(max(values) * 2) / 2
    uid = _uid("interval", uid, p10, pred, p90, observed, threshold, breakeven, axis)

    x0, x1 = 16, 312
    domain = (lo, hi)

    def x_of(value):
        return _scale(value, domain, (x0, x1))

    labels = [_label(f"Predicción {number(mid, 2)}", x_of(mid), "predicted")]
    if observed_value is not None:
        labels.append(_label(f"Reportado {number(observed_value, 2)}", x_of(observed_value), "observed"))
    if threshold_value is not None:
        labels.append(_label(f"Umbral {_trimmed_decimals(threshold_value)}", x_of(threshold_value), "threshold"))
    if breakeven_value is not None:
        labels.append(_label(f"Equilibrio {_trimmed_decimals(breakeven_value)}", x_of(breakeven_value), "breakeven"))

    # Con dos líneas de referencia, la de la izquierda escribe a su izquierda y la de la derecha a su derecha,
    # así su texto no tapa la línea vecina. Si no cabe, el texto va centrado.
    line_labels = sorted((item for item in labels if item["is_line"]), key=lambda item: item["mark"])
    for item in labels:
        if item["is_line"] and len(line_labels) == 2:
            side = "end" if item is line_labels[0] else "start"
            if _place_label(item, side):
                continue
        _place_label(item, "middle")
    # Primero las etiquetas con línea de referencia, que quedan en las filas bajas
    order = sorted(labels, key=lambda item: (not item["is_line"], item["mark"]))
    for item, row in zip(order, _label_rows(order)):
        item["row"] = row
    rows = max(item["row"] for item in labels) + 1

    def y_of_row(row):
        return 16 + (rows - 1 - row) * 18

    y_bar = 34 + (rows - 1) * 18
    y_axis = y_bar + 40

    body = []
    # Rango p10-p90: rectángulo redondeado grueso, color primario translúcido
    x_low, x_high = x_of(low), x_of(high)
    body.append(
        f'<rect x="{_fmt(x_low)}" y="{_fmt(y_bar - 8)}" width="{_fmt(x_high - x_low)}" height="16" rx="4" '
        'fill="var(--primario, #2a78d6)" fill-opacity="0.4"/>'
    )
    # Líneas de umbral y equilibrio: bajan desde su etiqueta hasta el eje
    for item in labels:
        if not item["is_line"]:
            continue
        x_line = _fmt(item["mark"])
        y_start = _fmt(y_of_row(item["row"]) + 3)
        if item["kind"] == "threshold":
            stroke = f'stroke="{INK_MUTED}" stroke-dasharray="2 3"'
        else:
            stroke = f'stroke="{INK}"'
        body.append(
            f'<line x1="{x_line}" y1="{y_start}" x2="{x_line}" y2="{_fmt(y_axis)}" stroke-width="1.5" {stroke}/>'
        )
    # Reportado: rombo de 14 px con anillo de la superficie
    if observed_value is not None:
        x_obs = x_of(observed_value)
        points = (
            f"{_fmt(x_obs)},{_fmt(y_bar - 7)} {_fmt(x_obs + 7)},{_fmt(y_bar)} "
            f"{_fmt(x_obs)},{_fmt(y_bar + 7)} {_fmt(x_obs - 7)},{_fmt(y_bar)}"
        )
        body.append(f'<polygon points="{points}" fill="{INK}" stroke="var(--tarjeta, #ffffff)" stroke-width="2"/>')
    # Predicción: círculo de 14 px con anillo de la superficie
    body.append(
        f'<circle cx="{_fmt(x_of(mid))}" cy="{_fmt(y_bar)}" r="7" '
        'fill="var(--primario-oscuro, #184f95)" stroke="var(--tarjeta, #ffffff)" stroke-width="2"/>'
    )
    # Etiquetas de los marcadores, en su fila y con el anclaje ya decidido
    for item in labels:
        x_text, anchor = _label_text_x(item)
        body.append(_halo_text(x_text, y_of_row(item["row"]), item["text"], anchor))
    # Valores p10 y p90 bajo los extremos; si quedan encimados, cada uno sale hacia fuera
    text_low, text_high = number(low, 2), number(high, 2)
    width_low, width_high = _text_width(text_low), _text_width(text_high)
    center_low = _clamp_center(x_low, width_low)
    center_high = _clamp_center(x_high, width_high)
    y_values = y_bar + 24
    if center_high - center_low < (width_low + width_high) / 2 + LABEL_PADDING:
        body.append(_halo_text(max(x_low - 4, 4 + width_low), y_values, text_low, "end"))
        body.append(_halo_text(min(x_high + 4, WIDTH - 4 - width_high), y_values, text_high, "start"))
    else:
        body.append(_halo_text(center_low, y_values, text_low))
        body.append(_halo_text(center_high, y_values, text_high))
    # Eje en t/ha: marcas cada 0.5 y etiquetas en los enteros (cada 2, 4... si no caben)
    body.append(
        f'<line x1="{_fmt(x0)}" y1="{_fmt(y_axis)}" x2="{_fmt(x1)}" y2="{_fmt(y_axis)}" '
        f'stroke="{INK_MUTED}" stroke-width="1"/>'
    )
    label_step = 1
    while label_step * (x1 - x0) / (hi - lo) < 28:
        label_step *= 2
    for k in range(math.ceil(lo * 2), math.floor(hi * 2) + 1):
        value = k / 2
        x_mark = _fmt(x_of(value))
        is_integer = k % 2 == 0
        length = 6 if is_integer else 3
        body.append(
            f'<line x1="{x_mark}" y1="{_fmt(y_axis)}" x2="{x_mark}" y2="{_fmt(y_axis + length)}" '
            f'stroke="{INK_MUTED}" stroke-width="1"/>'
        )
        if is_integer and (k // 2) % label_step == 0:
            body.append(_svg_text(x_of(value), y_axis + 18, _format_number(value, 0), color=INK_MUTED))
    body.append(_svg_text(x1 + 8, y_axis + 18, "t/ha", anchor="start", color=INK_MUTED))

    parts = [f"Predicción {number(mid, 2)} t/ha, intervalo p10 {number(low, 2)} a p90 {number(high, 2)} t/ha"]
    if observed_value is not None:
        parts.append(f"Reportado {number(observed_value, 2)} t/ha")
    if threshold_value is not None:
        parts.append(f"Umbral {_trimmed_decimals(threshold_value)} t/ha")
    if breakeven_value is not None:
        parts.append(f"Equilibrio {_trimmed_decimals(breakeven_value)} t/ha")
    description = ". ".join(parts) + "."
    return _svg(uid, y_axis + 26, "Rendimiento predicho (t/ha)", description, body)


def _bar_path(start, end, y, height, round_start, round_end):
    # Barra como trazo: esquinas de 4 px solo en los extremos con dato; el inicio del eje queda recto
    span = end - start
    radius = max(0.0, min(4.0, span / 2, height / 2))
    r_start = radius if round_start else 0.0
    r_end = radius if round_end else 0.0
    parts = [f"M{_fmt(start + r_start)},{_fmt(y)}", f"H{_fmt(end - r_end)}"]
    if r_end:
        parts.append(f"A{_fmt(r_end)},{_fmt(r_end)} 0 0 1 {_fmt(end)},{_fmt(y + r_end)}")
    parts.append(f"V{_fmt(y + height - r_end)}")
    if r_end:
        parts.append(f"A{_fmt(r_end)},{_fmt(r_end)} 0 0 1 {_fmt(end - r_end)},{_fmt(y + height)}")
    parts.append(f"H{_fmt(start + r_start)}")
    if r_start:
        parts.append(f"A{_fmt(r_start)},{_fmt(r_start)} 0 0 1 {_fmt(start)},{_fmt(y + height - r_start)}")
    parts.append(f"V{_fmt(y + r_start)}")
    if r_start:
        parts.append(f"A{_fmt(r_start)},{_fmt(r_start)} 0 0 1 {_fmt(start + r_start)},{_fmt(y)}")
    parts.append("Z")
    return " ".join(parts)


def _label_anchor(row, width):
    # Etiqueta encima de la barra, del lado contrario a la línea que llega desde la fila anterior
    # para que nunca la cruce. Devuelve (x, anchor).
    start, end, entry = row["start"], row["end"], row["entry"]
    if entry is None or abs(entry - start) <= abs(entry - end):
        return min(start + 4, WIDTH - 4 - width), "start"
    return max(end - 4, 4 + width), "end"


def breakdown_bars(base, terms, total, uid=None):
    """Cascada horizontal en t/ha: promedio de las parcelas, términos y predicción."""
    base_value, total_value = _finite(base), _finite(total)
    if base_value is None or total_value is None:
        return NO_DATA
    # Los términos sin valor finito no se dibujan; la etiqueta se escapa solo al final
    term_list = []
    for term in terms or []:
        value = _finite(term.get("value"))
        if value is not None:
            label = "" if term.get("label") is None else str(term.get("label"))
            term_list.append((label, value))
    uid = _uid("breakdown", uid, base, terms, total)

    # Acumulados: el promedio, el acumulado tras cada término y la predicción
    running = [base_value]
    for _, value in term_list:
        running.append(running[-1] + value)
    lo = math.floor(min(running + [total_value]) * 2) / 2 - 0.5
    hi = math.ceil(max(running + [total_value]) * 2) / 2 + 0.5
    x0, x1 = 8, 300

    def x_of(value):
        return _scale(value, (lo, hi), (x0, x1))

    # Una fila por elemento: start..end es el tramo de la barra; entry, la línea que llega desde arriba
    rows = [{
        "text": "Promedio de las parcelas medidas", "start": x0, "end": x_of(base_value), "entry": None,
        "value": number(base_value, 2), "color": COLOR_NEUTRAL, "class": "bar bar-base",
        "round": (False, True), "exit": x_of(base_value),
    }]
    for k, (label, value) in enumerate(term_list):
        previous, current = running[k], running[k + 1]
        rises = value >= 0
        rows.append({
            "text": label, "start": x_of(min(previous, current)), "end": x_of(max(previous, current)),
            "entry": x_of(previous), "value": _signed(value),
            "color": COLOR_INCREASE if rises else COLOR_DECREASE,
            "class": "bar bar-up" if rises else "bar bar-down",
            "round": (True, True), "exit": x_of(current),
        })
    rows.append({
        "text": "Predicción", "start": x0, "end": x_of(total_value), "entry": x_of(running[-1]),
        "value": number(total_value, 2), "color": INK, "class": "bar bar-total",
        "round": (False, True), "exit": None,
    })

    # Cada fila ocupa 46 px: etiqueta, barra de 18 px y valor a su derecha
    def row_top(index):
        return 6 + index * 46

    body = []
    # Líneas guía finas entre el final de cada barra y el inicio de la siguiente
    for index, row in enumerate(rows[:-1]):
        x_guide = _fmt(row["exit"])
        body.append(
            f'<line x1="{x_guide}" y1="{_fmt(row_top(index) + 38)}" x2="{x_guide}" '
            f'y2="{_fmt(row_top(index + 1) + 20)}" stroke="{INK_MUTED}" stroke-width="1"/>'
        )
    for index, row in enumerate(rows):
        bar = _bar_path(row["start"], row["end"], row_top(index) + 20, 18, *row["round"])
        body.append(f'<path class="{row["class"]}" d="{bar}" fill="{row["color"]}"/>')
    for index, row in enumerate(rows):
        x_label, anchor = _label_anchor(row, _text_width(row["text"]))
        body.append(_svg_text(x_label, row_top(index) + 14, row["text"], anchor=anchor))
        body.append(_svg_text(row["end"] + 6, row_top(index) + 34, row["value"], anchor="start"))

    parts = [f"Promedio de las parcelas medidas: {number(base_value, 2)} t/ha"]
    parts += [f"{label}: {_signed(value)} t/ha" for label, value in term_list]
    parts.append(f"Predicción: {number(total_value, 2)} t/ha")
    description = ". ".join(parts) + "."
    return _svg(uid, row_top(len(rows)) + 8, "Desglose de la predicción (t/ha)", description, body)


def _valid_points(days, values):
    # Pares (día, valor) con ambos valores finitos y el día dentro del año, ordenados por día
    pairs = []
    for day, value in zip(days or [], values or []):
        parsed_day, parsed_value = _finite(day), _finite(value)
        if parsed_day is not None and parsed_value is not None and 1 <= parsed_day <= 366:
            pairs.append((parsed_day, parsed_value))
    return sorted(pairs, key=lambda pair: pair[0])


def _valid_band(days, minimums, maximums):
    # Ternas (día, mínimo, máximo) con los tres valores finitos, ordenadas por día
    triples = []
    for day, minimum, maximum in zip(days or [], minimums or [], maximums or []):
        parsed_day, low, high = _finite(day), _finite(minimum), _finite(maximum)
        if parsed_day is not None and low is not None and high is not None and 1 <= parsed_day <= 366:
            triples.append((parsed_day, low, high))
    return sorted(triples, key=lambda triple: triple[0])


def _approx_date(day):
    # Mes y día en español a partir del día del año (calendario sin bisiesto, es aproximado)
    day_number = round(day)
    month = bisect_right(MONTH_STARTS, day_number) - 1
    return f"{min(day_number - MONTH_STARTS[month] + 1, MONTH_DAYS[month])} de {MONTH_NAMES[month]}"


def _legend_swatch(kind, x, y):
    # Muestra de la leyenda: línea gruesa, línea punteada o franja translúcida, como en la gráfica
    if kind == "current":
        return (
            f'<line x1="{_fmt(x)}" y1="{_fmt(y)}" x2="{_fmt(x + 20)}" y2="{_fmt(y)}" '
            'stroke="var(--primario-oscuro, #184f95)" stroke-width="3" stroke-linecap="round"/>'
        )
    if kind == "mean":
        return (
            f'<line x1="{_fmt(x)}" y1="{_fmt(y)}" x2="{_fmt(x + 20)}" y2="{_fmt(y)}" '
            f'stroke="{INK_MUTED}" stroke-width="1.5" stroke-dasharray="2 3" stroke-linecap="round"/>'
        )
    return (
        f'<rect x="{_fmt(x)}" y="{_fmt(y - 5)}" width="20" height="10" '
        'fill="var(--primario, #2a78d6)" fill-opacity="0.18"/>'
    )


def line_chart(current, history, title, y_label, uid=None, current_label="2025",
               history_label="Promedio 2022 a 2024", range_label="Rango 2022 a 2024"):
    """Serie del año frente al promedio histórico y su rango (mínimo a máximo) por día del año."""
    current_points = _valid_points((current or {}).get("doy"), (current or {}).get("value"))
    history_data = history or {}
    mean_points = _valid_points(history_data.get("doy"), history_data.get("mean"))
    band_points = _valid_band(history_data.get("doy"), history_data.get("min"), history_data.get("max"))
    if not current_points or not (mean_points or band_points):
        return NO_DATA
    title_text = (title or "").strip() or "Serie anual con promedio histórico"
    uid = _uid("line", uid, current, history, title, y_label, current_label, history_label, range_label)

    # Eje y: marcas "bonitas" que cubren todos los valores dibujados
    values = (
        [value for _, value in current_points]
        + [value for _, value in mean_points]
        + [value for _, low, high in band_points for value in (low, high)]
    )
    y_ticks, _ = _nice_ticks(min(values), max(values))
    y_domain = (y_ticks[0], y_ticks[-1])
    # Eje x: meses completos que cubren los datos, con las marcas al inicio de cada mes
    days = [day for day, _ in current_points] + [day for day, _ in mean_points] + [day for day, _, _ in band_points]
    first_month = bisect_right(MONTH_STARTS, math.floor(min(days))) - 1
    last_month = bisect_right(MONTH_STARTS, math.ceil(max(days))) - 1
    x_domain = (MONTH_STARTS[first_month], MONTH_STARTS[last_month + 1] - 1)

    x0, x1, y_top, y_bottom = 40, 348, 34, 236

    def x_of(day):
        return _scale(day, x_domain, (x0, x1))

    def y_of(value):
        return _scale(value, y_domain, (y_bottom, y_top))

    def polyline(pairs, attributes):
        coordinates = " ".join(f"{_fmt(x_of(day))},{_fmt(y_of(value))}" for day, value in pairs)
        return f'<polyline points="{coordinates}" fill="none" {attributes}/>'

    def dot(day, value, fill):
        return (
            f'<circle cx="{_fmt(x_of(day))}" cy="{_fmt(y_of(value))}" r="4" '
            f'fill="{fill}" stroke="var(--tarjeta, #ffffff)" stroke-width="2"/>'
        )

    body = []
    # Banda de mínimo a máximo: polígono translúcido del color primario
    if len(band_points) >= 2:
        outline = [f"{_fmt(x_of(day))},{_fmt(y_of(high))}" for day, _, high in band_points]
        outline += [f"{_fmt(x_of(day))},{_fmt(y_of(low))}" for day, low, _ in reversed(band_points)]
        body.append(f'<polygon points="{" ".join(outline)}" fill="var(--primario, #2a78d6)" fill-opacity="0.18"/>')
    # Media histórica: línea punteada gris; un solo punto se marca con un círculo
    if len(mean_points) >= 2:
        body.append(polyline(mean_points, f'stroke="{INK_MUTED}" stroke-width="1.5" stroke-dasharray="2 3"'))
    elif mean_points:
        body.append(dot(mean_points[0][0], mean_points[0][1], INK_MUTED))
    # Serie actual: línea gruesa azul oscuro; un solo punto se marca con un círculo
    if len(current_points) >= 2:
        body.append(polyline(
            current_points,
            'stroke="var(--primario-oscuro, #184f95)" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"',
        ))
    else:
        body.append(dot(current_points[0][0], current_points[0][1], "var(--primario-oscuro, #184f95)"))
    # Ejes: líneas sólidas finas
    body.append(
        f'<line x1="{_fmt(x0)}" y1="{_fmt(y_bottom)}" x2="{_fmt(x1)}" y2="{_fmt(y_bottom)}" '
        f'stroke="{INK_MUTED}" stroke-width="1"/>'
    )
    body.append(
        f'<line x1="{_fmt(x0)}" y1="{_fmt(y_top)}" x2="{_fmt(x0)}" y2="{_fmt(y_bottom)}" '
        f'stroke="{INK_MUTED}" stroke-width="1"/>'
    )
    decimals = _tick_decimals(y_ticks)
    for tick in y_ticks:
        y_tick = y_of(tick)
        body.append(
            f'<line x1="{_fmt(x0 - 4)}" y1="{_fmt(y_tick)}" x2="{_fmt(x0)}" y2="{_fmt(y_tick)}" '
            f'stroke="{INK_MUTED}" stroke-width="1"/>'
        )
        body.append(_svg_text(x0 - 6, y_tick + 4.5, _format_number(tick, decimals), anchor="end", color=INK_MUTED))
    # Marcas de mes; etiqueta solo en ene, mar, may, jul, sep y nov
    for index in range(first_month, last_month + 1):
        x_month = x_of(MONTH_STARTS[index])
        body.append(
            f'<line x1="{_fmt(x_month)}" y1="{_fmt(y_bottom)}" x2="{_fmt(x_month)}" y2="{_fmt(y_bottom + 4)}" '
            f'stroke="{INK_MUTED}" stroke-width="1"/>'
        )
        if index % 2 == 0:
            body.append(_svg_text(x_month, y_bottom + 22, MONTH_ABBRS[index], color=INK_MUTED))
    body.append(_svg_text(4, 16, y_label, anchor="start"))

    # Leyenda debajo del gráfico: una entrada por elemento que se dibuja; si no cabe en una fila, pasa a la siguiente
    items = [(current_label, "current")]
    if mean_points:
        items.append((history_label, "mean"))
    if band_points:
        items.append((range_label, "band"))
    legend_x, legend_row, legend_base = x0, 0, y_bottom + 46
    for text, kind in items:
        entry_width = 26 + _text_width(text)
        if legend_x > x0 and legend_x + entry_width > WIDTH - 8:
            legend_x, legend_row = x0, legend_row + 1
        row_y = legend_base + legend_row * 20
        body.append(_legend_swatch(kind, legend_x, row_y - 4))
        body.append(_svg_text(legend_x + 26, row_y, text, anchor="start"))
        legend_x += entry_width + 16
    height = legend_base + legend_row * 20 + 18

    # Descripción: máximo de la serie actual y de la media, con día del año y fecha aproximada
    day_max, value_max = max(current_points, key=lambda pair: pair[1])
    parts = [f"{current_label}: máximo {number(value_max, 2)} el día {round(day_max)} ({_approx_date(day_max)})"]
    if mean_points:
        day_mean, mean_max = max(mean_points, key=lambda pair: pair[1])
        parts.append(
            f"{history_label}: máximo {number(mean_max, 2)} el día {round(day_mean)} ({_approx_date(day_mean)})"
        )
    description = ". ".join(parts) + "."
    return _svg(uid, height, title_text, description, body)
