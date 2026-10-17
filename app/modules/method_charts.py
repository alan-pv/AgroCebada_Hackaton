# Gráficas SVG puras para la página de metodología. Cada función pública recibe una sección de
# methodology_data() y devuelve dos <svg> (markupsafe.Markup) con los mismos datos: uno ancho para
# escritorio y uno angosto para el celular. methodology.css muestra solo uno según el ancho de la
# pantalla, así el texto de la gráfica conserva su tamaño en los dos. app/modules/methodology.py
# las registra como globales de plantilla; como devuelven Markup, la plantilla las inserta sin
# volver a escaparlas.
# Dos tipos de fila comparten el mismo marco (etiquetas a la izquierda, un solo eje abajo):
#   punto con intervalo   cobertura del intervalo y grupos de variables (forest plot)
#   barras finas desde 0  RMSE frente a la media por régimen, error por vecinos y aportes
import math
import re

from markupsafe import Markup, escape

from .formatting import number, percent

NO_DATA = Markup('<p class="muted">Sin datos para mostrar.</p>')

# Ancho del viewBox de cada versión; con la gráfica a su tamaño natural, 1 unidad = 1 px
WIDE = 640
NARROW = 340
FONT_SIZE = 14
SMALL_SIZE = 13

# Tintas de texto y superficies: nunca el color de un dato
INK = "var(--texto, #1c2420)"
INK_MUTED = "var(--texto-suave, #545954)"
SURFACE = "var(--tarjeta, #ffffff)"
GRID = "var(--borde, #e3e2db)"
# Color de los datos: azul para el modelo; gris neutro para la referencia (media por régimen)
DATA = "var(--dato, #2a78d6)"
DATA_DARK = "var(--dato-oscuro, #184f95)"
NEUTRAL = "#898781"

MINUS = "−"  # signo menos tipográfico, para los valores negativos
BAR_HEIGHT = 14  # una barra por fila
PAIR_BAR_HEIGHT = 12  # dos barras por fila (modelo y referencia)
BAR_GAP = 4
DOT_RADIUS = 5
COVERAGE_NAMES = {"A": "Régimen A", "B": "Régimen B", "global": "Todas"}


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


def _clean_uid(uid):
    # Solo caracteres válidos en un id y en aria-labelledby (sin espacios)
    return re.sub(r"[^A-Za-z0-9_-]", "-", str(uid))


def _text_width(text, size=FONT_SIZE):
    # Estimación conservadora del ancho de un texto en unidades del viewBox
    return len(text) * size * 0.56


def _scale(value, domain, span):
    # Proyección lineal de un valor del dominio (lo, hi) al rango (a, b)
    lo, hi = domain
    a, b = span
    return a + (value - lo) / (hi - lo) * (b - a)


def _nice_ticks(lo, hi):
    # Marcas "bonitas" (paso 1, 2, 2.5 o 5 por potencia de 10) con 4 a 6 marcas que cubren [lo, hi]
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
            candidates.append((step, round((end - start) / step), start))
    candidates.sort(key=lambda candidate: candidate[0])
    in_range = [c for c in candidates if 3 <= c[1] <= 5]
    step, intervals, start = in_range[0] if in_range else min(candidates, key=lambda c: abs(c[1] - 4))
    return [round(start + i * step, 10) for i in range(intervals + 1)]


def _decimals(values):
    # Menor número de decimales (0 a 4) con el que cada valor se escribe exacto
    for decimals in range(5):
        if all(abs(round(value, decimals) - value) < 1e-9 for value in values):
            return decimals
    return 4


def _axis_number(ticks):
    # Formato de las marcas en t/ha: mismos decimales en todas, el cero sin decimales
    decimals = _decimals(ticks)
    return lambda value: "0" if abs(value) < 1e-12 else number(value, decimals).replace("-", MINUS)


def _axis_percent(ticks):
    # Formato de las marcas de una fracción como porcentaje: 0.75 -> "75 %"
    decimals = _decimals([tick * 100 for tick in ticks])
    return lambda value: percent(value, decimals)


def _svg_text(x, y, text, anchor="start", color=INK, size=FONT_SIZE, weight=None):
    # Texto en tinta de texto (nunca el color del dato)
    bold = f' font-weight="{weight}"' if weight else ""
    return (
        f'<text x="{_fmt(x)}" y="{_fmt(y)}" font-size="{size}" text-anchor="{anchor}" '
        f'fill="{color}"{bold}>{_text(text)}</text>'
    )


def _halo_text(x, y, text, anchor="middle", color=INK, size=FONT_SIZE):
    # Texto con halo del color de la tarjeta: sigue legible si una línea lo cruza
    return (
        f'<text x="{_fmt(x)}" y="{_fmt(y)}" font-size="{size}" text-anchor="{anchor}" fill="{color}" '
        f'stroke="{SURFACE}" stroke-width="4" stroke-linejoin="round" paint-order="stroke">{_text(text)}</text>'
    )


def _bar_path(start, end, y, height):
    # Barra horizontal con esquinas de 4 px solo en el extremo con dato; la base queda recta
    radius = max(0.0, min(4.0, abs(end - start) / 2, height / 2))
    if end >= start:
        return (
            f"M{_fmt(start)},{_fmt(y)} H{_fmt(end - radius)} "
            f"A{_fmt(radius)},{_fmt(radius)} 0 0 1 {_fmt(end)},{_fmt(y + radius)} "
            f"V{_fmt(y + height - radius)} "
            f"A{_fmt(radius)},{_fmt(radius)} 0 0 1 {_fmt(end - radius)},{_fmt(y + height)} "
            f"H{_fmt(start)} Z"
        )
    return (
        f"M{_fmt(start)},{_fmt(y)} H{_fmt(end + radius)} "
        f"A{_fmt(radius)},{_fmt(radius)} 0 0 0 {_fmt(end)},{_fmt(y + radius)} "
        f"V{_fmt(y + height - radius)} "
        f"A{_fmt(radius)},{_fmt(radius)} 0 0 0 {_fmt(end + radius)},{_fmt(y + height)} "
        f"H{_fmt(start)} Z"
    )


def _row_values(row):
    # Valores que el eje debe incluir: punto, extremos del intervalo y barras
    values = [row.get("value"), row.get("lo"), row.get("hi")]
    values += [bar["value"] for bar in row.get("bars", [])]
    return [value for value in values if value is not None]


def _value_label_width(rows):
    # Ancho de la etiqueta de valor más larga; se reserva a la derecha del área de la gráfica
    texts = [row.get("text") for row in rows] + [bar.get("text") for row in rows for bar in row.get("bars", [])]
    widths = [_text_width(text) for text in texts if text]
    return max(widths, default=0)


def _rows_chart(width, uid, title, description, rows, kind, axis_title, axis_unit="t/ha",
                include_zero=False, reference=None, legend=None):
    """Marco común: una fila por grupo, etiquetas a la izquierda (o encima si no caben) y un solo eje.
    kind es "interval" (punto con su intervalo) o "bars" (barras finas desde 0); axis_unit es
    "t/ha" o "percent" (fracciones de 0 a 1 que el eje escribe como porcentaje)."""
    # Si la etiqueta más larga ocupa más del 30 % del ancho, cada etiqueta va encima de su fila
    # y la gráfica usa todo el ancho
    label_width = max(max(_text_width(row["label"]), _text_width(row.get("sub") or "", SMALL_SIZE))
                      for row in rows)
    side = label_width <= width * 0.3
    has_sub = any(row.get("sub") for row in rows)
    x0 = label_width + 20 if side else 10
    x1 = width - max(10.0, _value_label_width(rows) + 12)

    values = [value for row in rows for value in _row_values(row)]
    if include_zero:
        values.append(0.0)
    if reference is not None:
        values.append(reference["value"])
    ticks = _nice_ticks(min(values), max(values))
    domain = (ticks[0], ticks[-1])

    def x_of(value):
        return _scale(value, domain, (x0, x1))

    # Alto de las marcas de una fila: un punto, una barra o un par de barras
    bar_count = max((len(row.get("bars", [])) for row in rows), default=0)
    bar_height = BAR_HEIGHT if bar_count <= 1 else PAIR_BAR_HEIGHT
    marks_height = 2 * DOT_RADIUS + 4 if kind == "interval" else bar_count * bar_height + (bar_count - 1) * BAR_GAP
    if side:
        row_height = max(32, marks_height + 20, 44 if has_sub else 0)
    else:
        row_height = 20 + marks_height + 16

    body = []
    top = 6
    # Leyenda en una fila sobre la gráfica (solo con dos series o más)
    if legend:
        x_item = x0 if side else 10
        for name, color in legend:
            body.append(f'<rect x="{_fmt(x_item)}" y="{_fmt(top + 2)}" width="10" height="10" rx="2" '
                        f'fill="{color}"/>')
            body.append(_svg_text(x_item + 15, top + 11, name, color=INK_MUTED, size=SMALL_SIZE))
            x_item += 15 + _text_width(name, SMALL_SIZE) + 18
        top += 24
    # Rótulo de la línea de referencia, arriba; la línea baja desde él hasta el eje
    if reference is not None:
        top += 18
    plot_top = top
    y_axis = plot_top + len(rows) * row_height + 2

    # Rejilla vertical en cada marca, en el gris del borde; el cero va en tinta suave
    for tick in ticks:
        x_tick = _fmt(x_of(tick))
        color = INK_MUTED if include_zero and abs(tick) < 1e-12 else GRID
        body.append(f'<line x1="{x_tick}" y1="{_fmt(plot_top)}" x2="{x_tick}" y2="{_fmt(y_axis)}" '
                    f'stroke="{color}" stroke-width="1"/>')
    if reference is not None:
        x_ref = x_of(reference["value"])
        body.append(f'<line x1="{_fmt(x_ref)}" y1="{_fmt(plot_top - 4)}" x2="{_fmt(x_ref)}" y2="{_fmt(y_axis)}" '
                    f'stroke="{INK}" stroke-width="1.5" stroke-dasharray="4 3"/>')
        half = _text_width(reference["label"]) / 2
        x_label = min(max(x_ref, half + 2), width - half - 2)
        body.append(_halo_text(x_label, plot_top - 8, reference["label"]))

    for index, row in enumerate(rows):
        y_row = plot_top + index * row_height
        if side:
            y_mid = y_row + row_height / 2
            if row.get("sub"):
                body.append(_svg_text(0, y_mid - 3, row["label"]))
                body.append(_svg_text(0, y_mid + 13, row["sub"], color=INK_MUTED, size=SMALL_SIZE))
            else:
                body.append(_svg_text(0, y_mid + 4.5, row["label"]))
        else:
            # Etiqueta encima de la fila; el dato secundario sigue en la misma línea, en tinta suave
            sub = f' <tspan fill="{INK_MUTED}" font-size="{SMALL_SIZE}">· {_text(row["sub"])}</tspan>' \
                if row.get("sub") else ""
            # Un fondo del color de la tarjeta corta la rejilla detrás del texto
            text_width = _text_width(row["label"])
            if row.get("sub"):
                text_width += _text_width(f' · {row["sub"]}', SMALL_SIZE)
            body.append(f'<rect x="{_fmt(x0)}" y="{_fmt(y_row)}" width="{_fmt(min(text_width + 8, width - x0))}" '
                        f'height="19" fill="{SURFACE}"/>')
            body.append(f'<text x="{_fmt(x0 + 4)}" y="{_fmt(y_row + 14)}" font-size="{FONT_SIZE}" fill="{INK}">'
                        f'{_text(row["label"])}{sub}</text>')
            y_mid = y_row + 20 + marks_height / 2

        # Cada fila lleva su propio <title>: el navegador lo muestra al pasar el puntero
        marks = [f'<title>{_text(row["tooltip"])}</title>'] if row.get("tooltip") else []
        if kind == "interval":
            value = row.get("value")
            if value is None:
                marks.append(_svg_text(x0 + 4, y_mid + 4.5, "Sin dato", color=INK_MUTED))
            else:
                lo, hi = row.get("lo"), row.get("hi")
                right = x_of(value)
                if lo is not None and hi is not None:
                    right = max(right, x_of(hi))
                    marks.append(f'<line x1="{_fmt(x_of(lo))}" y1="{_fmt(y_mid)}" x2="{_fmt(x_of(hi))}" '
                                 f'y2="{_fmt(y_mid)}" stroke="{DATA}" stroke-width="2" stroke-linecap="round"/>')
                marks.append(f'<circle cx="{_fmt(x_of(value))}" cy="{_fmt(y_mid)}" r="{DOT_RADIUS}" '
                             f'fill="{DATA_DARK}" stroke="{SURFACE}" stroke-width="2"/>')
                if row.get("text"):
                    marks.append(_svg_text(right + 8, y_mid + 4.5, row["text"]))
        else:
            y_bar = y_mid - marks_height / 2
            for bar in row["bars"]:
                value = bar["value"]
                if value is None:
                    marks.append(_svg_text(x_of(0) + 4, y_bar + bar_height - 1, "Sin dato",
                                           color=INK_MUTED, size=SMALL_SIZE))
                else:
                    end = x_of(value)
                    marks.append(f'<path d="{_bar_path(x_of(0), end, y_bar, bar_height)}" fill="{bar["color"]}"/>')
                    if bar.get("text"):
                        marks.append(_svg_text(end + 6, y_bar + bar_height / 2 + 4.5, bar["text"],
                                               size=SMALL_SIZE if bar_count > 1 else FONT_SIZE))
                y_bar += bar_height + BAR_GAP
        body.append(f'<g>{"".join(marks)}</g>')

    # Marcas del eje: si no caben todas, se rotula una de cada dos (el cero siempre lleva rótulo)
    axis_format = _axis_percent(ticks) if axis_unit == "percent" else _axis_number(ticks)
    tick_labels = [axis_format(tick) for tick in ticks]
    spacing = (x1 - x0) / max(len(ticks) - 1, 1)
    widest = max(_text_width(text, SMALL_SIZE) for text in tick_labels)
    every = 1 if spacing >= widest + 8 else 2
    anchor_index = next((i for i, tick in enumerate(ticks) if abs(tick) < 1e-12), 0)
    for index, (tick, text) in enumerate(zip(ticks, tick_labels)):
        if (index - anchor_index) % every:
            continue
        half = _text_width(text, SMALL_SIZE) / 2
        x_text = min(max(x_of(tick), half), width - half)
        body.append(_svg_text(x_text, y_axis + 16, text, anchor="middle", color=INK_MUTED, size=SMALL_SIZE))
    body.append(_svg_text((x0 + x1) / 2, y_axis + 35, axis_title, anchor="middle", color=INK_MUTED, size=SMALL_SIZE))

    height = y_axis + 43
    variant = "wide" if width >= WIDE else "narrow"
    return Markup(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {_fmt(height)}" '
        f'role="img" aria-labelledby="{uid}-t {uid}-d" class="chart method-chart method-chart--{variant}" '
        f'style="width:100%;max-width:{width}px;height:auto;font-family:inherit">'
        f'<title id="{uid}-t">{_text(title)}</title>'
        f'<desc id="{uid}-d">{_text(description)}</desc>'
        + "".join(body)
        + "</svg>"
    )


def _responsive(uid, title, description, rows, **options):
    # Las dos versiones de la misma gráfica, con ids distintos; el CSS muestra solo una
    uid = _clean_uid(uid)
    return Markup("").join(
        _rows_chart(width, f"{uid}-{suffix}", title, description, rows, **options)
        for width, suffix in ((WIDE, "ancho"), (NARROW, "angosto"))
    )


def _bar(value, color=DATA):
    # Una barra con su valor escrito en la punta; sin dato, la barra no se dibuja
    return {"value": value, "color": color, "text": number(value, 3) if value is not None else None}


def _has_data(items):
    # ¿Hay al menos un punto o una barra con valor?
    return any(item.get("value") is not None or any(bar["value"] is not None for bar in item.get("bars", []))
               for item in items)


def coverage_chart(rows, target=0.8, uid="cobertura"):
    """Cobertura del intervalo p10 a p90 por grupo: punto con su IC 95 % y línea de meta."""
    items = []
    for row in rows or []:
        value = _finite(row.get("coverage"))
        ci = row.get("coverage_ci95") or [None, None]
        lo, hi = _finite(ci[0]), _finite(ci[1])
        name = str(COVERAGE_NAMES.get(row.get("group"), row.get("group")))
        parcels = row.get("parcels")
        tooltip = f"{name}: {percent(value, 1)}"
        if lo is not None and hi is not None:
            tooltip += f", IC 95 % de {percent(lo, 1)} a {percent(hi, 1)}"
        items.append({"label": name, "sub": f"{parcels} parcelas" if parcels is not None else None,
                      "value": value, "lo": lo, "hi": hi,
                      "text": percent(value, 1) if value is not None else None, "tooltip": tooltip})
    if not _has_data(items):
        return NO_DATA
    target_value = _finite(target)
    reference = None
    description = ". ".join(item["tooltip"] for item in items)
    if target_value is not None:
        reference = {"value": target_value, "label": f"Meta {percent(target_value)}"}
        description += f". Línea de meta en {percent(target_value)}"
    description += ". El eje horizontal no empieza en 0 %."
    return _responsive(uid, "Cobertura del intervalo p10 a p90 por grupo", description, items,
                       kind="interval", axis_title="Cobertura del intervalo p10 a p90",
                       axis_unit="percent", reference=reference)


def groups_chart(rows, uid="grupos"):
    """Grupos de variables probados: aumento del RMSE al quitarlos, con el rango 5 % a 95 %."""
    items = []
    for index, row in enumerate(rows or []):
        name = str(row.get("label") or "")
        value, lo, hi = _finite(row.get("delta_rmse")), _finite(row.get("p05")), _finite(row.get("p95"))
        tooltip = f"{name}: {number(value, 3)} t/ha"
        if lo is not None and hi is not None:
            tooltip += f", de {number(lo, 3)} a {number(hi, 3)}"
        # Solo el grupo de mayor efecto lleva su valor escrito; los demás se leen en el eje o en la tabla
        items.append({"label": name, "value": value, "lo": lo, "hi": hi,
                      "text": number(value, 3) if index == 0 and value is not None else None,
                      "tooltip": tooltip})
    if not _has_data(items):
        return NO_DATA
    description = ("Aumento del RMSE, en t/ha, al quitar cada grupo, con su rango entre repeticiones del 5 % "
                   "al 95 %. " + ". ".join(item["tooltip"] for item in items) + ". Línea vertical en 0.")
    return _responsive(uid, "Cuánto empeora el error al quitar cada grupo de variables", description, items,
                       kind="interval", axis_title="Aumento del RMSE al quitar el grupo (t/ha)",
                       include_zero=True)


def rmse_chart(validation, baseline, uid="rmse"):
    """RMSE del modelo frente a una predicción que solo da la media de su régimen, por esquema."""
    items = []
    for row in validation or []:
        scheme = row.get("scheme")
        model_rmse, mean_rmse = _finite(row.get("rmse")), _finite((baseline or {}).get(scheme))
        items.append({"label": f"Esquema {scheme}", "sub": "decide" if scheme == "A" else "no decide",
                      "bars": [_bar(model_rmse), _bar(mean_rmse, NEUTRAL)],
                      "tooltip": f"Esquema {scheme}: modelo {number(model_rmse, 3)} t/ha, "
                                 f"media por régimen {number(mean_rmse, 3)} t/ha"})
    if not _has_data(items):
        return NO_DATA
    description = ". ".join(item["tooltip"] for item in items) + ". Las barras empiezan en 0."
    return _responsive(uid, "RMSE del modelo y de la media por régimen", description, items,
                       kind="bars", axis_title="RMSE (t/ha)", include_zero=True,
                       legend=[("Modelo", DATA), ("Media por régimen", NEUTRAL)])


def neighbors_chart(rows, uid="vecinos"):
    """Error absoluto medio según cuántas parcelas medidas del mismo régimen hay a 400 m."""
    items = []
    for row in rows or []:
        mae = _finite(row.get("mae"))
        name = f"{str(row.get('group')).replace('-', ' a ')} vecinos"
        filas = row.get("rows")
        tooltip = f"{name}: MAE {number(mae, 3)} t/ha"
        if filas is not None:
            tooltip += f", {filas} filas"
        items.append({"label": name, "sub": f"{filas} filas" if filas is not None else None,
                      "bars": [_bar(mae)], "tooltip": tooltip})
    if not _has_data(items):
        return NO_DATA
    description = ". ".join(item["tooltip"] for item in items) + ". Las barras empiezan en 0."
    return _responsive(uid, "Error absoluto medio según los vecinos a 400 m", description, items,
                       kind="bars", axis_title="Error absoluto medio, MAE (t/ha)", include_zero=True)


def contributions_chart(rows, uid="aportes"):
    """Aporte promedio, en valor absoluto, de cada entrada del modelo entregado."""
    items = []
    for row in rows or []:
        name = str(row.get("label") or "")
        value = _finite(row.get("mean_abs_t_ha"))
        items.append({"label": name, "bars": [_bar(value)], "tooltip": f"{name}: {number(value, 3)} t/ha"})
    if not _has_data(items):
        return NO_DATA
    description = ". ".join(item["tooltip"] for item in items) + ". Las barras empiezan en 0."
    return _responsive(uid, "Aporte promedio de cada entrada del modelo", description, items,
                       kind="bars", axis_title="Aporte promedio en valor absoluto (t/ha)", include_zero=True)
