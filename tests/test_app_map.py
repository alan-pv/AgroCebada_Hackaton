import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

pytest.importorskip("flask")

from app import create_app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def client():
    return create_app({"TESTING": True}).test_client()


class _Elements(HTMLParser):
    # Guarda (etiqueta, atributos) de cada elemento de un HTML, en orden
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_map_div_has_data_urls(client):
    html = client.get("/").get_data(as_text=True)
    (attrs,) = [a for tag, a in _Elements(html).elements if tag == "div" and a.get("id") == "map"]
    assert attrs["data-parcels-url"] == "/api/parcels"
    assert attrs["data-predictions-url"] == "/api/predictions"
    assert attrs["data-economics-url"] == "/api/economics"
    # La ficha es una plantilla: el JavaScript cambia __ID__ por el ID de cada parcela
    assert attrs["data-detail-url"] == "/parcela/__ID__"
    # Y la confianza del resumen sale del JSON de la ficha, con el mismo marcador
    assert attrs["data-detail-api-url"] == "/api/parcels/__ID__"
    # La hoja de estilos del mapa se enlaza desde la página y existe
    assert 'href="/styles/map.css"' in html
    assert client.get("/styles/map.css").status_code == 200


def test_layer_select_has_eight_options(client):
    html = client.get("/").get_data(as_text=True)
    select = re.search(r'<select id="layer">(.*?)</select>', html, re.S)
    assert select
    values = re.findall(r'<option value="([^"]*)"', select.group(1))
    assert values == ["set", "yield", "pred", "risk_costs", "risk_credit", "mun-esperado", "mun-riesgo", "mun-confianza"]
    # Agrupadas en «Datos», «Riesgo» y «Modelo municipal»; los valores (y el hash #layer=...) no cambian
    groups = re.findall(r'<optgroup label="([^"]+)">(.*?)</optgroup>', select.group(1), re.S)
    assert [(label, re.findall(r'value="([^"]*)"', body)) for label, body in groups] == [
        ("Datos", ["set", "yield", "pred"]),
        ("Riesgo", ["risk_costs", "risk_credit"]),
        ("Modelo municipal", ["mun-esperado", "mun-riesgo", "mun-confianza"]),
    ]


def test_download_group_has_two_links(client):
    html = client.get("/").get_data(as_text=True)
    group = re.search(r'<div class="download"[^>]*>(.*?)</div>', html, re.S)
    assert group
    links = re.findall(r"<a ([^>]*)>([^<]+)</a>", group.group(1))
    assert len(links) == 2
    # Ambos enlaces descargan el archivo y tienen texto claro
    assert all(re.search(r"\sdownload(\s|$)", attrs) for attrs, _ in links)
    assert [text for _, text in links] == ["Predicciones (CSV)", "Economía por parcela (CSV)"]
    hrefs = [re.search(r'href="([^"]+)"', attrs).group(1) for attrs, _ in links]
    assert hrefs == ["/api/predictions?format=csv", "/api/economics?format=csv"]


def test_toolbar_toggle_stats_and_count(client):
    html = client.get("/").get_data(as_text=True)
    elements = _Elements(html).elements
    by_id = {a["id"]: (tag, a) for tag, a in elements if "id" in a}
    # El botón que pliega la capa y los filtros en el celular dice su estado y qué controla
    tag, toggle = by_id["filters-toggle"]
    assert tag == "button" and toggle["type"] == "button"
    assert toggle["aria-expanded"] == "false"
    assert toggle["aria-controls"] == "filters" and "filters" in by_id
    # Los tres selectores están dentro del panel que se pliega
    panel = re.search(r'<div id="filters"[^>]*>(.*?)</div>', html, re.S).group(1)
    assert all(f'<select id="{name}"' in panel for name in ("layer", "state", "municipality"))
    # Cuatro indicadores con cifra y nota, que el script llena
    for key in ("shown", "to-predict", "pred-mean", "risk"):
        assert f"stat-{key}" in by_id and f"stat-{key}-note" in by_id
    assert "Parcelas con riesgo alto de no pagar el crédito" in html
    # El contador sigue anunciando los cambios
    assert by_id["count"][1]["aria-live"] == "polite"


def test_map_js_is_javascript_without_hardcoded_api_paths(client):
    res = client.get("/scripts/map.js")
    assert res.status_code == 200
    assert "javascript" in res.mimetype
    js = res.get_data(as_text=True)
    # Las rutas de la API salen de los data-*-url de la página, no de cadenas escritas en el script
    assert '"/api/' not in js and "'/api/" not in js
    assert "risk_costs" in js and "risk_credit" in js


def test_index_paths_keep_mount_point(client):
    html = client.get("/", base_url="http://localhost/sub/").get_data(as_text=True)
    paths = re.findall(r'(?:href|src|data-[\w-]+-url)="([^"]+)"', html)
    assert paths
    assert all(p.startswith(("/sub/", "https://")) for p in paths)
    # Las rutas nuevas del mapa también siguen el prefijo
    assert 'data-economics-url="/sub/api/economics"' in html
    assert 'data-detail-url="/sub/parcela/__ID__"' in html
    assert 'data-detail-api-url="/sub/api/parcels/__ID__"' in html
    assert 'href="/sub/api/predictions?format=csv"' in html
    assert 'href="/sub/styles/map.css"' in html


@pytest.mark.skipif(shutil.which("node") is None, reason="Node no está instalado")
def test_map_js_passes_node_syntax_check():
    res = subprocess.run(["node", "--check", str(ROOT / "app" / "scripts" / "map.js")],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr


def test_base_map_libraries_are_pinned_with_integrity(client):
    html = client.get("/").get_data(as_text=True)
    elements = _Elements(html).elements
    # MapLibre GL y el puente con Leaflet: versión exacta, SRI y crossorigin, como Leaflet
    external = [a for tag, a in elements if tag in ("script", "link") and "unpkg.com" in (a.get("src") or a.get("href") or "")]
    urls = [a.get("src") or a.get("href") for a in external]
    assert "https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.js" in urls
    assert "https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.css" in urls
    assert "https://unpkg.com/@maplibre/maplibre-gl-leaflet@0.1.4/leaflet-maplibre-gl.js" in urls
    for attrs in external:
        assert re.match(r"sha(256|384)-[A-Za-z0-9+/=]+$", attrs["integrity"])
        assert "crossorigin" in attrs
    # El puente va después de Leaflet y de MapLibre, y map.js al final
    scripts = [a["src"] for tag, a in elements if tag == "script" and "src" in a]
    order = [next(i for i, s in enumerate(scripts) if key in s)
             for key in ("leaflet@", "maplibre-gl@", "maplibre-gl-leaflet@", "map.js")]
    assert order == sorted(order)


def test_map_js_base_map_and_fallback(client):
    js = client.get("/scripts/map.js").get_data(as_text=True)
    # Estilo Positron de OpenFreeMap, con su atribución completa
    assert "https://tiles.openfreemap.org/styles/positron" in js
    for credit in ("OpenFreeMap", "OpenMapTiles", "OpenStreetMap"):
        assert credit in js
    # Respaldo: mosaicos de OpenStreetMap con la clase que les pone el filtro gris
    assert "tile.openstreetmap.org" in js and "map--osm" in js
    css = client.get("/styles/map.css").get_data(as_text=True)
    assert re.search(r"#map\.map--osm \.leaflet-tile-pane\s*\{[^}]*grayscale", css)
    # El tooltip sigue y su última línea invita al clic
    assert "Clic para ver el resumen" in js


def test_side_panel_structure(client):
    html = client.get("/").get_data(as_text=True)
    elements = _Elements(html).elements
    by_id = {a["id"]: (tag, a) for tag, a in elements if "id" in a}
    # Panel lateral (hoja inferior en el celular) con su nombre accesible
    tag, panel = by_id["map-panel"]
    assert tag == "aside" and panel["aria-label"]
    # El título de la hoja dice su estado y qué controla
    tag, toggle = by_id["panel-toggle"]
    assert tag == "button" and toggle["type"] == "button"
    assert toggle["aria-expanded"] == "false" and toggle["aria-controls"] == "panel-body"
    assert "panel-body" in by_id
    # El botón que vuelve a abrir el panel en escritorio empieza oculto
    tag, reopen = by_id["panel-open"]
    assert tag == "button" and "hidden" in reopen and reopen["aria-controls"] == "map-panel"
    # Vista de lista: título enfocable, selector de orden y lista ordenada
    assert by_id["plist-title"][1]["tabindex"] == "-1"
    assert by_id["plist-items"][0] == "ol"
    sort = re.search(r'<select id="plist-sort">(.*?)</select>', html, re.S)
    assert re.findall(r'<option value="([^"]*)"', sort.group(1)) == ["credit", "costs", "pred"]
    # Vista de resumen: oculta al inicio, con «Volver a la lista»
    assert "hidden" in by_id["panel-parcel"][1]
    assert by_id["psum-back"][0] == "button" and "Volver a la lista" in html
    # Cada vista tiene su botón cerrar de 44 px con nombre accesible
    closes = [a for tag, a in elements if tag == "button" and "data-close" in a]
    assert len(closes) == 2 and all(a.get("aria-label") for a in closes)
    # La ayuda del semáforo va junto a la lista
    assert "¿Cómo se lee el semáforo?" in html


def test_map_js_panel_uses_page_urls_and_keyboard(client):
    js = client.get("/scripts/map.js").get_data(as_text=True)
    # La ficha y su JSON salen de data-detail-url y data-detail-api-url
    assert "dataset.detailUrl" in js and "dataset.detailApiUrl" in js
    assert "Ver ficha completa" in js
    # Esc cierra; el mapa se reacomoda al abrir o cerrar el panel
    assert '"Escape"' in js and "invalidateSize" in js
    # Sin economía, la lista se ordena por rendimiento y lo dice
    assert "la lista se ordena por rendimiento predicho" in js
