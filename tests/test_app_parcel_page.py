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
SECCIONES = ("Rendimiento esperado", "¿Cuánto significa en pesos?", "En palabras sencillas",
             "Cómo se llegó a este número", "Verdor y sequía en 2025 frente a 2022 a 2024",
             "Contexto de 2025 (no entra al modelo final)")
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


def badge_tras(html, texto):
    # Clase y texto del primer badge que aparece después de `texto`
    i = html.index(texto)
    m = re.search(r'<span class="badge badge--(\w+)">([^<]+)</span>', html[i:])
    return m.group(1), m.group(2)


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
        assert badge_tras(html, "<h3>Confianza</h3>") == CONFIANZA[nivel], pid


def test_probabilidades_extremas_se_dicen_con_palabras(client):
    # Ni 0 % ni 100 %: docs/capa_economica.md pide «menos de 1 %» y «más de 99 %»
    html = client.get("/parcela/AGC_003").get_data(as_text=True)
    econ = economics.parcel_economics_data("AGC_003")
    assert econ["prob_not_cover_costs"] > 0.99
    assert "Probabilidad de no cubrir los costos totales: más de 99 %" in html
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
    # La nota va justo después de la tabla de resultados y antes de los bloques de riesgo
    assert html.index("</table>") < html.index(NOTA_COSTOS) < html.index('class="grid-2 risks"')


def test_contexto_municipal_cuenta_los_anios_del_siap(client):
    html = client.get("/parcela/AGC_003").get_data(as_text=True)
    econ = economics.parcel_economics_data("AGC_003")
    assert f"{econ['context']['years_loss_over_20']} de {ANIOS_SIAP} años (2003 a 2025)." in html
    assert f"{econ['context']['years_loss_over_50']} de {ANIOS_SIAP} años (2003 a 2025)." in html


def test_rutas_siguen_al_punto_de_montaje(client):
    html = client.get("/parcela/AGC_003", base_url="http://localhost/sub/").get_data(as_text=True)
    rutas = re.findall(r'(?:href|src|action|data-[\w-]+-url)="([^"]+)"', html)
    assert rutas
    assert all(r.startswith(("/sub/", "https://")) for r in rutas), [r for r in rutas if not r.startswith("/sub/")]
    assert 'action="/sub/parcela/AGC_003"' in html
    assert 'href="/sub/parcela/AGC_003"' in html
    assert 'href="/sub/metodologia"' in html


def test_graficas_de_la_serie_o_aviso(client):
    html = client.get("/parcela/AGC_003").get_data(as_text=True)
    if SERIE.exists():
        titulos = [t for imagen in analizar(html).imagenes for t in imagen if "NDVI" in t or "NDDI" in t]
        assert sum("NDVI" in t for t in titulos) == 1
        assert sum("NDDI" in t for t in titulos) == 1
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
