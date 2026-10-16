# Filtros de plantilla para números, dinero y porcentajes. Son funciones puras y se registran
# en app/__init__.py con add_template_filter:
#   {{ valor | number }}       1234.5 -> "1,234.50"   coma de miles y punto decimal
#   {{ valor | money }}        24772.6 -> "$24,773"
#   {{ fraccion | percent }}   0.27 -> "27 %"         recibe una fracción de 0 a 1
# Un valor vacío (None o NaN) se muestra como "—" en los tres

MISSING = "—"


def _missing(value):
    # NaN es el único valor que no es igual a sí mismo
    return value is None or value != value


def _grouped(value, digits):
    # Primero se redondea y luego se pone el signo: -0.4 con 0 decimales sale "0", no "-0"
    rounded = round(value, digits)
    sign = "-" if rounded < 0 else ""
    return sign + f"{abs(rounded):,.{digits}f}"


def number(value, digits=2):
    """Número con coma de miles y punto decimal."""
    if _missing(value):
        return MISSING
    return _grouped(value, digits)


def money(value, digits=0):
    """Cantidad de dinero con el símbolo $ delante."""
    if _missing(value):
        return MISSING
    text = _grouped(value, digits)
    # El signo menos va antes del símbolo: -$1,500
    if text.startswith("-"):
        return "-$" + text[1:]
    return "$" + text


def percent(value, digits=0):
    """Porcentaje a partir de una fracción: 0.27 -> "27 %"."""
    if _missing(value):
        return MISSING
    return _grouped(value * 100, digits) + " %"
