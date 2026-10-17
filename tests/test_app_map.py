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
    # La hoja de estilos del mapa se enlaza desde la página y existe
    assert 'href="/styles/map.css"' in html
    assert client.get("/styles/map.css").status_code == 200


def test_layer_select_has_five_options(client):
    html = client.get("/").get_data(as_text=True)
    select = re.search(r'<select id="layer">(.*?)</select>', html, re.S)
    assert select
    values = re.findall(r'<option value="([^"]*)"', select.group(1))
    assert values == ["set", "yield", "pred", "risk_costs", "risk_credit"]


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
    assert 'href="/sub/api/predictions?format=csv"' in html
    assert 'href="/sub/styles/map.css"' in html


@pytest.mark.skipif(shutil.which("node") is None, reason="Node no está instalado")
def test_map_js_passes_node_syntax_check():
    res = subprocess.run(["node", "--check", str(ROOT / "app" / "scripts" / "map.js")],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
