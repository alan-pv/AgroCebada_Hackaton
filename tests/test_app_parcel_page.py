# Ficha de parcela en GET /parcela/<id> (issues #12 y #48): predicción, riesgo en pesos, desglose,
# serie de 2025 contra 2022 a 2024 y contexto municipal, en HTML renderizado en el servidor
import re
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("flask")

from agrocebada.config import OUTPUTS, PROCESSED
from app import create_app
from app.modules import economics, formatting

ROOT = Path(__file__).resolve().parents[1]
PREDICCIONES = OUTPUTS / "predicciones.parquet"
SERIE = PROCESSED / "serie_ficha.parquet"
NOTA_ENTRENAMIENTO = ("Esta parcela se usó para entrenar el modelo; la predicción que se muestra es la "
                      "validada fuera de entrenamiento y no se desglosa con el mismo método.")
SECCIONES = ("Rendimiento esperado", "Rango de la predicción y confianza", "¿Cuánto significa en pesos?",
             "Cómo se llegó a este número", "Verdor y sequía en 2025 frente a 2022 a 2024",
             "Contexto de 2025 (no entra al modelo final)")
# Pestañas de la ficha: id de la sección y texto de la pestaña, en orden
PESTANAS = [("rendimiento", "Rendimiento"), ("economia", "Economía"), ("calculo", "Cómo se calculó"),
            ("satelite", "Satélite y clima")]
# Palabras de Python que nunca deben aparecer como texto de la página
PALABRAS_PROHIBIDAS = re.compile(r"\b(nan|inf|None)\b")
# Etiquetas HTML que no tienen cierre
VACIAS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
# Color del semáforo -> (clase del badge, texto del badge); lo mismo para el nivel de confianza
LUCES = {"verde": ("bajo", "Riesgo bajo"), "amarillo": ("medio", "Riesgo medio"), "rojo": ("alto", "Riesgo alto")}
CONFIANZA = {"alta": ("bajo", "Confianza alta"), "media": ("medio", "Confianza media"),
             "baja": ("alto", "Confianza baja")}
ANIOS_SIAP = 2025 - 2003 + 1


class Marcado(HTMLParser):
    """Recorre el HTML con la librería estándar: revisa que las etiquetas cierren en orden y junta
    los títulos de cada SVG con role="img"."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pila, self.errores = [], []
        self.svg = []          # SVG abiertos: [es_imagen, títulos]
        self.imagenes = []     # títulos de cada SVG con role="img", ya cerrado
        self.img_sin_alt = 0
        self.en_titulo, self.texto = False, ""

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "img" and not (d.get("alt") or "").strip():
            self.img_sin_alt += 1
        if tag == "svg":
            self.svg.append([d.get("role") == "img", []])
        if tag == "title" and self.svg:
            self.en_titulo, self.texto = True, ""
        if tag not in VACIAS:
            self.pila.append(tag)

    def handle_endtag(self, tag):
        if tag == "title" and self.en_titulo:
            self.en_titulo = False
            self.svg[-1][1].append(self.texto.strip())
        if tag in VACIAS:
            return
        if self.pila and self.pila[-1] == tag:
            self.pila.pop()
        else:
            self.errores.append(f"</{tag}> sin apertura en orden")
        if tag == "svg" and self.svg:
            es_imagen, titulos = self.svg.pop()
            if es_imagen:
                self.imagenes.append(titulos)

    def handle_data(self, data):
        if self.en_titulo:
            self.texto += data


def analizar(html):
    m = Marcado()
    m.feed(html)
    m.close()
    return m


def campo(html, nombre):
    # Etiqueta <input> del campo del formulario, para leer su valor y su placeholder
    return re.search(rf'<input id="{nombre}"[^>]*>', html).group(0)


def texto_visible(html):
    # Texto de la página sin etiquetas: una frase partida en varios <span> se lee completa
    return re.sub(r"<[^>]+>", "", html)


def badge_tras(html, texto):
    # Clase y texto del primer badge que aparece después de `texto`
    i = html.index(texto)
    m = re.search(r'<span class="badge badge--(\w+)">([^<]+)</span>', html[i:])
    return m.group(1), m.group(2)


def panel(html, ident):
    # Contenido de una pestaña de la ficha (<section class="tabs__panel" id="...">)
    m = re.search(rf'<section class="tabs__panel" id="{ident}"[^>]*>(.*?)</section>', html, re.S)
    assert m, ident
    return m.group(1)


def desplegable(html, resumen):
    # Etiqueta de apertura y contenido del <details> cuyo <summary> es `resumen`
    m = re.search(rf'(<details [^>]*>)\s*<summary>{re.escape(resumen)}</summary>(.*?)</details>', html, re.S)
    assert m, resumen
    return m.group(1) + m.group(2)


def franja(html):
    # Franja de veredicto: lo que se ve siempre, arriba de las pestañas
    m = re.search(r'<section class="card verdict" aria-labelledby="veredicto">(.*?)</section>', html, re.S)
    assert m
    return m.group(1)


@pytest.fixture(scope="module")
def client():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def ids():
    return pd.read_parquet(PREDICCIONES, columns=["ID_POLIGONO"])["ID_POLIGONO"].tolist()


def test_las_197_parcelas_responden_200(client, ids):
    assert len(ids) == 197
    for pid in ids:
        res = client.get(f"/parcela/{pid}")
        assert res.status_code == 200, pid
        html = res.get_data(as_text=True)
        assert f"Parcela {pid}" in html, pid
        assert "Rendimiento esperado" in html, pid
        for seccion in SECCIONES:
            assert seccion in html, (pid, seccion)
        m = PALABRAS_PROHIBIDAS.search(html)
        assert m is None, (pid, html[max(0, m.start() - 60):m.end() + 20] if m else "")


def test_prediccion_muestra_el_desglose(client):
    html = client.get("/parcela/AGC_003").get_data(as_text=True)
    assert "Promedio de las parcelas medidas" in html
    assert "Rendimiento reportado" not in html


def test_entrenamiento_muestra_reportado_y_nota_sin_desglose(client):
    html = client.get("/parcela/AGC_001").get_data(as_text=True)
    assert "Rendimiento reportado: 3.50 t/ha" in html
    assert NOTA_ENTRENAMIENTO in html
    assert "Promedio de las parcelas medidas" not in html


def test_parcela_inexistente_responde_404_con_enlace_al_mapa(client):
    res = client.get("/parcela/NO_EXISTE")
    assert res.status_code == 404
    html = res.get_data(as_text=True)
    assert "No encontramos la parcela NO_EXISTE" in html
    assert 'href="/"' in html


def test_precio_de_la_query_se_muestra_y_se_usa(client):
    res = client.get("/parcela/AGC_003", query_string={"price": "7000"})
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'value="7000"' in campo(html, "price")
    esperado = economics.parcel_economics_data("AGC_003", price=7000)
    assert formatting.money(esperado["income_ha"]) in html


def test_error_del_modelo_en_pesos_sigue_al_precio(client):
    # Issue #48: el error típico del modelo en pesos por hectárea, en la tabla y en la nota sencilla
    for query in ({}, {"price": "8000"}):
        html = client.get("/parcela/AGC_003", query_string=query).get_data(as_text=True)
        econ = economics.parcel_economics_data("AGC_003", price=query.get("price"))
        err = econ["model_error"]
        pesos = formatting.money(err["money_ha"])
        assert f"Error típico del modelo por hectárea ({formatting.number(err['t_ha'], 2)} t/ha)" in html
        assert (f"El modelo se equivoca en promedio unas {formatting.number(err['t_ha'], 2)} t/ha. "
                f"Con el precio de {formatting.money(econ['price'])} por tonelada eso son unos {pesos} por "
                f"hectárea. Es el {formatting.percent(err['share_cost_total'])} del costo total y el "
                f"{formatting.percent(err['share_credit'])} del crédito por hectárea.") in html
    assert "$8,000 por tonelada" in html


def test_equilibrio_de_la_query_se_muestra_y_se_usa(client):
    res = client.get("/parcela/AGC_003", query_string={"breakeven": "4.5"})
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'value="4.5"' in campo(html, "breakeven")
    assert "4.50 t/ha frente a" in html


@pytest.mark.parametrize("query", [{"price": "abc"}, {"breakeven": "abc"}, {"price": "100"}, {"breakeven": "50"}])
def test_parametro_invalido_da_400_con_aviso_y_la_pagina_completa(client, query):
    res = client.get("/parcela/AGC_003", query_string=query)
    assert res.status_code == 400
    html = res.get_data(as_text=True)
    assert 'role="alert"' in html
    for seccion in SECCIONES:
        assert seccion in html, seccion


def test_precio_invalido_muestra_la_economia_por_defecto(client):
    html = client.get("/parcela/AGC_003", query_string={"price": "abc"}).get_data(as_text=True)
    por_defecto = economics.parcel_economics_data("AGC_003")
    assert "El precio debe ser un número." in html
    assert f'value="{por_defecto["price"]:g}"' in campo(html, "price")
    assert formatting.money(por_defecto["income_ha"]) in html


def test_parametros_vacios_son_no_dados(client):
    res = client.get("/parcela/AGC_003?price=&breakeven=")
    assert res.status_code == 200
    por_defecto = economics.parcel_economics_data("AGC_003")
    etiqueta = campo(res.get_data(as_text=True), "breakeven")
    assert 'value=""' in etiqueta
    assert f'placeholder="automático: {formatting.number(por_defecto["breakeven"], 2)}"' in etiqueta


def test_placeholder_del_equilibrio_sigue_al_precio_usado(client):
    # Sin equilibrio fijado, el automático es costo ÷ precio: con otro precio el placeholder debe cambiar
    res = client.get("/parcela/AGC_003", query_string={"price": "9000"})
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    esperado = economics.parcel_economics_data("AGC_003", price=9000)
    texto = formatting.number(esperado["breakeven"], 2)
    assert texto == "3.15"
    etiqueta = campo(html, "breakeven")
    assert f'placeholder="automático: {texto}"' in etiqueta
    assert "6.61" not in etiqueta
    assert 'value="9000"' in campo(html, "price")


def test_css_cabeceras_de_fila_con_borde_de_1px_y_columnas_con_2px():
    css = (ROOT / "app" / "styles" / "main.css").read_text(encoding="utf-8")
    # La regla nueva: las cabeceras de fila del cuerpo usan el borde de 1 px de las celdas
    assert 'table.data tbody th[scope="row"] {\n  border-bottom-width: 1px;\n}' in css
    # Las cabeceras de columna (thead) siguen con el borde de 2 px de la regla general table.data th
    bloque = re.search(r"table\.data th \{([^}]*)\}", css).group(1)
    assert "border-bottom-width: 2px" in bloque


def bloque_movil(css):
    # Texto completo de la regla @media (max-width: 600px), contando las llaves
    inicio = css.index("@media (max-width: 600px) {")
    nivel = 0
    for i in range(css.index("{", inicio), len(css)):
        if css[i] == "{":
            nivel += 1
        elif css[i] == "}":
            nivel -= 1
            if nivel == 0:
                return css[inicio:i + 1]
    raise AssertionError("bloque @media sin cerrar")


def test_tablas_de_tres_columnas_llevan_la_clase_stack(client):
    html = client.get("/parcela/AGC_003").get_data(as_text=True)
    # Solo las dos tablas de tres columnas se apilan en el celular; la de resultados no cambia
    assert re.search(r'<table class="data stack">\s*<caption>Lo que usa el modelo entregado', html)
    assert re.search(r'<table class="data stack">\s*<caption>Variables de 2025 que la ficha muestra como contexto', html)
    assert html.count('<table class="data stack">') == 2
    assert html.count('<table class="data">') == 1


def test_parcel_css_apila_las_tablas_solo_en_movil():
    css = (ROOT / "app" / "styles" / "parcel.css").read_text(encoding="utf-8")
    movil = bloque_movil(css)
    # El encabezado se oculta de forma accesible (visualmente oculto), no con display: none
    assert "table.data.stack thead" in movil
    assert "position: absolute" in movil
    assert "clip-path: inset(50%)" in movil
    assert "display: none" not in movil
    # Cada fila es una cuadrícula: etiqueta a la izquierda, valor a la derecha y descripción a todo el ancho
    assert "grid-template-columns: minmax(0, 1fr) auto" in movil
    assert "grid-column: 1 / -1" in movil
    # Ninguna regla de la clase stack queda fuera del bloque móvil, así que el escritorio no cambia
    assert css.count("table.data.stack") == movil.count("table.data.stack")


def test_semaforos_y_confianza_coinciden_con_la_economia(client):
    lista = client.get("/api/economics").get_json()
    # Una parcela por combinación de semáforos, para cubrir los colores que haya en los datos
    combinaciones = {}
    for fila in lista:
        combinaciones.setdefault((fila["light_costs"], fila["light_credit"]), fila["id"])
    assert combinaciones
    for pid in combinaciones.values():
        econ = client.get(f"/api/economics/{pid}").get_json()
        nivel = client.get(f"/api/parcels/{pid}").get_json()["confidence"]["level"]
        html = client.get(f"/parcela/{pid}").get_data(as_text=True)
        assert badge_tras(html, "Probabilidad de no cubrir los costos totales") == LUCES[econ["light_costs"]], pid
        assert badge_tras(html, "Probabilidad de no pagar el crédito") == LUCES[econ["light_credit"]], pid
        # El badge de confianza va en el indicador «Confianza» del bloque principal
        assert badge_tras(html, '<dt class="stat__label">Confianza</dt>') == CONFIANZA[nivel], pid


def test_probabilidades_extremas_se_dicen_con_palabras(client):
    # Ni 0 % ni 100 %: docs/capa_economica.md pide «menos de 1 %» y «más de 99 %»
    html = client.get("/parcela/AGC_003").get_data(as_text=True)
    econ = economics.parcel_economics_data("AGC_003")
    assert econ["prob_not_cover_costs"] > 0.99
    assert "Probabilidad de no cubrir los costos totales: más de 99 %" in texto_visible(html)
    assert "100 %" not in html
    cortes = econ["light_cuts"]
    assert (f"Bajo: menos de {formatting.percent(cortes['green_below'])}. "
            f"Medio: de {formatting.percent(cortes['green_below'])} a menos de {formatting.percent(cortes['red_from'])}. "
            f"Alto: {formatting.percent(cortes['red_from'])} o más.") in html


NOTA_COSTOS = ("Los costos son los del paquete tecnológico de FIRA del ciclo primavera-verano 2022 (el más reciente "
               "público) para la zona de AgroCostos del municipio, actualizados a 2025 con el índice general de "
               "precios al consumidor de INEGI. Ese índice no sigue el precio de los insumos agrícolas, así que el "
               "costo real puede ser distinto: por eso el precio y el punto de equilibrio se pueden cambiar arriba. "
               "El precio es el precio medio rural del SIAP para el municipio, promedio 2023 a 2025 ponderado por "
               "producción.")


def test_nota_de_costos_queda_bajo_la_tabla_de_resultados(client):
    html = client.get("/parcela/AGC_003").get_data(as_text=True)
    assert NOTA_COSTOS in html
    # La tabla y la nota de fuentes van juntas en el desplegable «Ver detalle y supuestos», después de los medidores
    detalle = desplegable(html, "Ver detalle y supuestos")
    assert detalle.index("</table>") < detalle.index(NOTA_COSTOS)
    assert html.index('class="grid-2 risks"') < html.index("<summary>Ver detalle y supuestos</summary>")


def test_contexto_municipal_cuenta_los_anios_del_siap(client):
    html = client.get("/parcela/AGC_003").get_data(as_text=True)
    econ = economics.parcel_economics_data("AGC_003")
    # Cada indicador dice «N de 23 años» y su nota el periodo del SIAP
    texto = texto_visible(html)
    assert f"{econ['context']['years_loss_over_20']} de {ANIOS_SIAP} años" in texto
    assert f"{econ['context']['years_loss_over_50']} de {ANIOS_SIAP} años" in texto
    assert texto.count("Periodo 2003 a 2025.") == 2


def test_rutas_siguen_al_punto_de_montaje(client):
    html = client.get("/parcela/AGC_003", base_url="http://localhost/sub/").get_data(as_text=True)
    rutas = re.findall(r'(?:href|src|action|data-[\w-]+-url)="([^"]+)"', html)
    assert rutas
    # Los enlaces a otra pestaña de la ficha son anclas de la misma página (#economia...)
    externas = [r for r in rutas if not r.startswith("#")]
    assert all(r.startswith(("/sub/", "https://")) for r in externas), [r for r in externas if not r.startswith("/sub/")]
    # El formulario y «Restablecer valores» vuelven a la pestaña Economía
    assert 'action="/sub/parcela/AGC_003#economia"' in html
    assert 'href="/sub/parcela/AGC_003#economia"' in html
    assert 'href="/sub/metodologia"' in html
    assert 'src="/sub/scripts/tabs.js"' in html


def test_graficas_de_la_serie_o_aviso(client):
    html = client.get("/parcela/AGC_003").get_data(as_text=True)
    if SERIE.exists():
        # Cada índice se dibuja dos veces, ancha para el escritorio y angosta para el celular; el CSS muestra una
        titulos = [t for imagen in analizar(html).imagenes for t in imagen if "NDVI" in t or "NDDI" in t]
        assert sum("NDVI" in t for t in titulos) == 2
        assert sum("NDDI" in t for t in titulos) == 2
        assert "no está disponible en esta copia" not in html
    else:
        assert "La serie satelital no está disponible en esta copia de la app." in html


def test_html_bien_formado_y_graficas_con_titulo(client):
    html = client.get("/parcela/AGC_003").get_data(as_text=True)
    m = analizar(html)
    assert m.errores == []
    assert m.pila == []
    assert m.img_sin_alt == 0
    assert len(m.imagenes) >= 3
    assert all(any(t for t in titulos) for titulos in m.imagenes)


# Rediseño de la ficha: franja de veredicto, pestañas, confianza en tres pasos, medidores y gráficas dobles

def test_pestanas_en_orden_y_sin_indice_fijo(client):
    html = client.get("/parcela/AGC_003").get_data(as_text=True)
    assert '<div class="tabs parcel-tabs" data-tabs aria-label="Detalle de la ficha">' in html
    pestanas = re.findall(r'<section class="tabs__panel" id="([\w-]+)" data-tab-label="([^"]+)">', html)
    assert pestanas == PESTANAS
    for ident, _ in PESTANAS:
        assert html.count(f'id="{ident}"') == 1, ident
    # Las pestañas reemplazan al índice fijo; tabs.js arma la fila de pestañas
    assert 'class="toc' not in html
    assert re.search(r'<script src="[^"]*/scripts/tabs\.js"></script>', html)
    # La franja va antes de las pestañas, fuera de ellas
    assert html.index('class="card verdict"') < html.index("data-tabs")


def test_css_sin_indice_fijo():
    css = (ROOT / "app" / "styles" / "parcel.css").read_text(encoding="utf-8")
    assert ".toc" not in css
    assert "parcel-toc" not in css
    assert "position: sticky" not in css


def test_cada_pestana_trae_su_contenido(client):
    html = client.get("/parcela/AGC_003").get_data(as_text=True)
    rendimiento, economia = panel(html, "rendimiento"), panel(html, "economia")
    calculo, satelite = panel(html, "calculo"), panel(html, "satelite")
    assert "Probabilidad de quedar por debajo de 2.5 t/ha" in texto_visible(rendimiento)
    assert '<div class="chart-ancha">' in rendimiento and 'class="conf-steps"' in rendimiento
    assert 'class="stat-grid econ-stats"' in economia and 'class="grid-2 risks"' in economia
    assert "Cómo se llegó a este número" in calculo and "Entradas del modelo en esta parcela" in calculo
    assert "Verdor y sequía en 2025 frente a 2022 a 2024" in satelite
    assert "Contexto de 2025 (no entra al modelo final)" in satelite


def test_franja_de_veredicto_con_cifra_rango_y_tres_indicadores(client):
    html = client.get("/parcela/AGC_003").get_data(as_text=True)
    ficha = client.get("/api/parcels/AGC_003").get_json()
    econ = economics.parcel_economics_data("AGC_003")
    arriba = franja(html)
    # La cifra principal es la única grande de la página y va en la franja, con su rango p10 a p90
    assert html.count('class="cifra"') == 1
    assert f'<p class="cifra">{formatting.number(ficha["pred"], 2)} <span class="cifra__unit">t/ha</span></p>' in arriba
    assert (f'Rango p10 a p90: <strong>{formatting.number(ficha["p10"], 2)} a '
            f'{formatting.number(ficha["p90"], 2)} t/ha</strong>') in arriba
    # Tres indicadores: confianza, crédito y costos, cada uno con su badge con texto
    indicadores = re.search(r'<dl class="stat-grid verdict__stats">(.*?)</dl>', arriba, re.S).group(1)
    assert len(re.findall(r'<div class="stat[ "]', indicadores)) == 3
    assert badge_tras(indicadores, "Confianza")[1].startswith("Confianza ")
    assert badge_tras(indicadores, "Probabilidad de no pagar el crédito") == LUCES[econ["light_credit"]]
    assert badge_tras(indicadores, "Probabilidad de no cubrir los costos totales") == LUCES[econ["light_costs"]]
    assert "más de 99 %" in indicadores
    # Con qué precio salen los riesgos, y un enlace a la economía
    assert f"Con el precio del municipio, {formatting.money(econ['price'])} por tonelada." in arriba
    assert 'href="#economia"' in arriba
    # Una parcela por predecir no lleva rendimiento reportado
    assert "Rendimiento reportado" not in arriba


def test_franja_de_entrenamiento_con_reportado_y_nota(client):
    arriba = franja(client.get("/parcela/AGC_001").get_data(as_text=True))
    assert '<p class="verdict__observed">Rendimiento reportado: 3.50 t/ha</p>' in arriba
    assert "La predicción que se muestra es la validada fuera de entrenamiento" in arriba


def test_franja_dice_el_precio_y_equilibrio_elegidos(client):
    html = client.get("/parcela/AGC_003", query_string={"price": "9000", "breakeven": "4"}).get_data(as_text=True)
    assert "Con el precio elegido, $9,000 por tonelada, y el punto de equilibrio elegido, 4.00 t/ha." in franja(html)


@pytest.mark.parametrize("pid", ["AGC_003", "AGC_001"])
def test_confianza_marca_el_nivel_actual_con_texto(client, pid):
    html = client.get(f"/parcela/{pid}").get_data(as_text=True)
    nivel = client.get(f"/api/parcels/{pid}").get_json()["confidence"]["level"]
    actuales = re.findall(r'<li class="conf-step[^"]*conf-step--current" aria-current="step">(.*?)</li>', html, re.S)
    assert len(actuales) == 1
    assert f'<span class="conf-step__name">{nivel.capitalize()}</span>' in actuales[0]
    assert "nivel actual" in actuales[0]
    # La explicación de los tres niveles sigue en la página, en una ayuda junto al indicador
    assert re.search(r'<details class="help-inline">\s*<summary>¿Qué significa cada nivel\?</summary>', html)
    for texto in ("al menos una parcela medida a 400 m o menos.",
                  "ninguna a 400 m, pero la más cercana está a 800 m o menos.",
                  "la más cercana está a más de 800 m, o el área de la parcela queda fuera del rango de su régimen."):
        assert texto in html


def test_medidores_de_riesgo_siguen_a_la_economia(client):
    html = client.get("/parcela/AGC_003").get_data(as_text=True)
    econ = economics.parcel_economics_data("AGC_003")
    rellenos = re.findall(r'<span class="meter__fill meter__fill--(\w+)" style="width: ([\d.]+)%"></span>', html)
    assert [(clase, float(ancho)) for clase, ancho in rellenos] == [
        (LUCES[econ["light_costs"]][0], round(min(econ["prob_not_cover_costs"], 1) * 100, 1)),
        (LUCES[econ["light_credit"]][0], round(min(econ["prob_not_pay_credit"], 1) * 100, 1)),
    ]
    # Los cortes del semáforo se marcan en cada riel, en su posición
    cortes = econ["light_cuts"]
    for corte in (cortes["green_below"], cortes["red_from"]):
        assert html.count(f'<span class="meter__cut" style="left: {corte * 100:.1f}%"></span>') == 2
    # La explicación de los cortes queda en un solo lugar
    assert html.count(f"Bajo: menos de {formatting.percent(cortes['green_below'])}.") == 1
    assert "probabilidad de pérdida de la cosecha" in html


def test_margen_negativo_con_signo_y_texto(client):
    html = client.get("/parcela/AGC_003").get_data(as_text=True)
    econ = economics.parcel_economics_data("AGC_003")
    assert econ["margin_ha"] < 0
    margen = "−" + formatting.money(econ["margin_ha"])[1:]
    assert re.search(r'<div class="stat stat--negativo">\s*<dt class="stat__label">Margen esperado por hectárea</dt>\s*'
                     rf'<dd class="stat__value">{re.escape(margen)}</dd>', html)
    assert "Negativo: el ingreso esperado no cubre el costo total." in html
    assert "-$" not in html


def test_graficas_en_dos_anchos_con_ids_unicos(client):
    html = client.get("/parcela/AGC_003").get_data(as_text=True)
    assert html.count('<div class="chart-ancha">') == html.count('<div class="chart-angosta">') >= 2
    ids = re.findall(r'\sid="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    css = (ROOT / "app" / "styles" / "parcel.css").read_text(encoding="utf-8")
    assert re.search(r"\.chart-angosta \{\s*display: none;", css)
    assert re.search(r"@media \(max-width: 900px\) \{\s*\.chart-ancha \{\s*display: none;", css)


def test_explicaciones_junto_a_su_dato(client):
    html = client.get("/parcela/AGC_003").get_data(as_text=True)
    econ = economics.parcel_economics_data("AGC_003")
    # El bloque «En palabras sencillas» ya no existe: cada explicación va en una ayuda junto a su dato
    assert "En palabras sencillas" not in html
    assert 'class="card plain"' not in html
    rendimiento, economia, calculo = panel(html, "rendimiento"), panel(html, "economia"), panel(html, "calculo")
    ayudas = {
        "¿Qué significa el rango p10 a p90?": (rendimiento, "9 de cada 10 parcelas rinden más que ese valor"),
        "¿Qué no cubre el rango?": (rendimiento, "para una cartera de crédito el p10 subestima ese riesgo común"),
        "¿Cómo se lee el semáforo?": (economia, "no una probabilidad de incumplimiento"),
        "¿Cuánto puede fallar el modelo?": (franja(html), "no para decidir sola sobre una parcela"),
        "¿Cómo sale la predicción?": (calculo, "El satélite, el clima y la topografía no entran en la predicción final."),
    }
    for pregunta, (donde, frase) in ayudas.items():
        assert html.count(f"<summary>{pregunta}</summary>") == 1, pregunta
        ayuda = desplegable(donde, pregunta)
        assert ayuda.startswith('<details class="help-inline">'), pregunta
        assert '<div class="help-inline__body">' in ayuda and frase in ayuda, pregunta
    # El rango y lo que no cubre van justo bajo la barra de intervalo; el semáforo, bajo los medidores
    assert rendimiento.index('class="chart-figure"') < rendimiento.index("¿Qué significa el rango p10 a p90?")
    assert rendimiento.index("¿Qué no cubre el rango?") < rendimiento.index('class="confidence"')
    assert economia.index('class="grid-2 risks"') < economia.index("¿Cómo se lee el semáforo?")
    # La forma en que sale la predicción abre la pestaña, antes de la cascada
    assert calculo.index("¿Cómo sale la predicción?") < calculo.index('class="chart-figure"')
    assert f"Con el precio de {formatting.money(econ['price'])} por tonelada eso son unos" in franja(html)


def test_economia_en_dos_capas(client):
    economia = panel(client.get("/parcela/AGC_003").get_data(as_text=True), "economia")
    # Primera capa a la vista: indicadores y medidores; lo demás plegado en tres desplegables, en este orden
    plegados = re.findall(r'<details class="disclosure"[^>]*>\s*<summary>([^<]+)</summary>', economia)
    assert plegados == ["Ajustar precio y punto de equilibrio", "Ver detalle y supuestos", "Contexto del municipio"]
    assert economia.index('class="grid-2 risks"') < economia.index('class="econ-more"')
    assert '<form class="price-form"' in desplegable(economia, "Ajustar precio y punto de equilibrio")
    assert '<table class="data">' in desplegable(economia, "Ver detalle y supuestos")
    assert 'class="stat-grid ctx"' in desplegable(economia, "Contexto del municipio")
    # Sin parámetros, nada viene abierto
    assert " open" not in "".join(re.findall(r'<details class="disclosure"[^>]*>', economia))


@pytest.mark.parametrize("query, codigo", [({}, 200), ({"price": "9000"}, 200), ({"breakeven": "4"}, 200),
                                           ({"price": ""}, 200), ({"price": "abc"}, 400)])
def test_ajuste_se_abre_si_la_url_lo_usa_o_hay_error(client, query, codigo):
    res = client.get("/parcela/AGC_003", query_string=query)
    assert res.status_code == codigo
    html = res.get_data(as_text=True)
    apertura = desplegable(html, "Ajustar precio y punto de equilibrio").split(">", 1)[0] + ">"
    assert apertura == ('<details class="disclosure" id="ajustar" open>' if query else
                        '<details class="disclosure" id="ajustar">')
    # Los otros dos desplegables siguen plegados
    assert desplegable(html, "Ver detalle y supuestos").startswith('<details class="disclosure">')
    assert desplegable(html, "Contexto del municipio").startswith('<details class="disclosure">')


def test_aviso_de_error_lleva_al_formulario(client):
    html = client.get("/parcela/AGC_003", query_string={"price": "abc"}).get_data(as_text=True)
    aviso = re.search(r'<div class="alert" role="alert">(.*?)</div>', html, re.S).group(1)
    assert '<a href="#ajustar">Corregir el valor</a>' in aviso
    # El aviso va arriba de la franja, a la vista; el formulario está en la pestaña Economía
    assert html.index('role="alert"') < html.index('class="card verdict"')
    assert 'id="ajustar"' in panel(html, "economia")


def test_semaforo_explica_por_que_casi_todas_salen_en_medio_o_alto(client):
    # La ayuda del semáforo explica el costo total y el crédito, y dice cuál causa aplica a la parcela
    def explicacion(parcel_id):
        html = client.get(f"/parcela/{parcel_id}").get_data(as_text=True)
        bloque = html[html.index("¿Por qué tantas parcelas salen en medio o alto?"):]
        return " ".join(texto_visible(bloque[:bloque.index("</details>")]).split())

    # Singuilucan: el equilibrio del crédito queda a menos del error típico de la predicción
    singuilucan = explicacion("AGC_003")
    assert "6.61 t/ha frente a una predicción de 3.66 t/ha" in singuilucan
    assert "la diferencia es menor que el error típico del modelo" in singuilucan
    # Chignahuapan: la pérdida histórica del municipio pasa del corte de 10 %
    chignahuapan = explicacion("AGC_002")
    assert "así que no puede salir en bajo" in chignahuapan
    # Calpulalpan sale en bajo en el crédito: ninguna de las dos frases particulares aplica
    calpulalpan = explicacion("AGC_001")
    assert "no puede salir en bajo." not in calpulalpan
    assert "la diferencia es menor" not in calpulalpan
    assert "Ajustar precio y punto de equilibrio" in calpulalpan
