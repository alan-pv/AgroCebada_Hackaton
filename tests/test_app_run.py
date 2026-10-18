import math
import re

import pytest

pytest.importorskip("flask")

from app import create_app
from app.modules import model
from app.modules.run import to_metres

# Campos de cada predicción de una parcela nueva
NEW_FIELDS = {"id", "lon", "lat", "area_ha", "regime", "pred", "p10", "p90", "prob_below",
              "confidence", "neighbors_400m", "nearest_neighbor_m", "confidence_reason"}
VALID = {"id": "PRUEBA_1", "lon": -98.37, "lat": 19.82, "area_ha": 5.2, "regime": "A"}


@pytest.fixture(scope="module")
def client():
    return create_app({"TESTING": True}).test_client()


def parcel(**changes):
    return {**VALID, **changes}


def near(parcel_id, dlon=0.001, dlat=0.001):
    # Un punto a unos 150 m de una parcela del conjunto de datos, dentro de la zona de estudio
    row = model.features_table().loc[parcel_id]
    return float(row["lon"]) + dlon, float(row["lat"]) + dlat


def mobile_block(css):
    """Texto de la regla @media (max-width: 600px), de «@media» a su llave de cierre."""
    start = css.index("@media (max-width: 600px) {")
    depth = 0
    for pos in range(start, len(css)):
        if css[pos] == "{":
            depth += 1
        elif css[pos] == "}":
            depth -= 1
            if depth == 0:
                return css[start:pos + 1]
    raise AssertionError("la regla @media no cierra")


def test_run_page_has_data_attributes(client):
    res = client.get("/ejecutar")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert f'data-max-parcels="{model.MAX_PARCELS}"' in html
    assert f'data-threshold-min="{model.THRESHOLD_RANGE[0]}"' in html
    assert f'data-threshold-max="{model.THRESHOLD_RANGE[1]}"' in html
    assert f'data-threshold-default="{model.load_model().umbral}"' in html
    assert 'data-predictions-url="/api/predictions"' in html
    assert 'data-predict-url="/api/predict"' in html
    assert 'data-new-url="/api/predict/new"' in html
    assert 'data-detail-url="/parcela/__ID__"' in html
    assert "/styles/run.css" in html
    assert "/scripts/run.js" in html


def test_run_page_follows_mount_point(client):
    html = client.get("/ejecutar", base_url="http://localhost/sub/").get_data(as_text=True)
    paths = re.findall(r'(?:href|src|data-[\w-]+-url)="([^"]+)"', html)
    assert paths
    assert all(p.startswith(("/sub/", "https://")) for p in paths)
    assert 'data-new-url="/sub/api/predict/new"' in html


def test_run_script_is_javascript_without_hardcoded_api(client):
    res = client.get("/scripts/run.js")
    assert res.status_code == 200
    assert "javascript" in res.mimetype
    js = res.get_data(as_text=True)
    # Las rutas salen de la plantilla con url_for, nunca escritas en el JavaScript
    for quote in ('"', "'", "`"):
        assert f"{quote}/api/" not in js


def test_lonlat_to_metres_matches_features_table():
    table = model.features_table()
    assert len(table) == 197
    worst = 0.0
    for _, row in table.iterrows():
        x, y = to_metres(row["lon"], row["lat"])
        worst = max(worst, abs(x - row["x_m"]), abs(y - row["y_m"]))
    # EPSG:6372, el CRS de x_m y y_m; el error medido es de nanómetros
    assert worst < 1.0


def test_predict_new_one_parcel(client):
    lon, lat = near("AGC_003")
    res = client.post("/api/predict/new", json={"parcels": [{"lon": lon, "lat": lat, "area_ha": 5.0, "regime": "B"}]})
    assert res.status_code == 200
    data = res.get_json()
    assert set(data) == {"model_version", "threshold", "predictions"}
    assert data["model_version"]
    (row,) = data["predictions"]
    assert set(row) == NEW_FIELDS
    # Sin ID en la petición, la parcela recibe NUEVA_1
    assert row["id"] == "NUEVA_1"
    for key in ("lon", "lat", "area_ha", "pred", "p10", "p90", "prob_below", "nearest_neighbor_m"):
        assert math.isfinite(row[key]), key
    assert row["confidence"] in {"alta", "media", "baja"}
    assert isinstance(row["neighbors_400m"], int)
    assert isinstance(row["confidence_reason"], str)


def test_predict_new_keeps_request_order(client):
    lon, lat = near("AGC_003")
    parcels = [
        {"id": "PRUEBA_2", "lon": lon, "lat": lat, "area_ha": 5.0, "regime": "B"},
        {"id": "PRUEBA_1", "lon": lon + 0.01, "lat": lat, "area_ha": 2.0, "regime": "A"},
    ]
    res = client.post("/api/predict/new", json={"parcels": parcels})
    assert res.status_code == 200
    assert [row["id"] for row in res.get_json()["predictions"]] == ["PRUEBA_2", "PRUEBA_1"]


def test_predict_new_default_threshold_is_model_threshold(client):
    lon, lat = near("AGC_003")
    body = {"parcels": [{"lon": lon, "lat": lat, "area_ha": 5.0, "regime": "B"}]}
    data = client.post("/api/predict/new", json=body).get_json()
    assert data["threshold"] == model.load_model().umbral
    # Sin umbral y con el umbral del modelo, el resultado es el mismo
    explicit = dict(body, threshold=model.load_model().umbral)
    other = client.post("/api/predict/new", json=explicit).get_json()
    assert other["predictions"][0]["prob_below"] == data["predictions"][0]["prob_below"]


@pytest.mark.parametrize("body", [
    {},
    {"parcels": []},
    {"parcels": "AGC_001"},
    {"parcels": [parcel(regime="C")]},
    {"parcels": [parcel(lon=-120.0)]},
    {"parcels": [parcel(lat="19.82")]},
    {"parcels": [parcel(lon=True)]},
    {"parcels": [parcel(area_ha=0)]},
    {"parcels": [parcel(area_ha=1001)]},
    {"parcels": [parcel(), parcel()]},
    {"parcels": [parcel(id="AGC_001")]},
    {"parcels": [parcel(id="MI PARCELA")]},
    {"parcels": [parcel(id="ÑANDÚ")]},
    {"parcels": [VALID], "threshold": 0.5},
    {"parcels": [VALID], "threshold": 6.5},
    {"parcels": [VALID], "threshold": "2.5"},
    {"parcels": [VALID], "threshold": True},
])
def test_predict_new_rejects_invalid_body(client, body):
    res = client.post("/api/predict/new", json=body)
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_predict_new_requires_json(client):
    res = client.post("/api/predict/new", data="no es JSON", content_type="text/plain")
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_predict_new_rejects_nan_coordinates(client):
    # Flask acepta NaN como literal de JSON; la respuesta debe ser un 400, no un valor inválido
    body = b'{"parcels": [{"lon": NaN, "lat": 19.82, "area_ha": 5.2, "regime": "A"}]}'
    res = client.post("/api/predict/new", data=body, content_type="application/json")
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_predict_new_rejects_more_than_max_parcels(client):
    res = client.post("/api/predict/new", json={"parcels": [VALID] * (model.MAX_PARCELS + 1)})
    assert res.status_code == 400
    assert str(model.MAX_PARCELS) in res.get_json()["error"]


def test_predict_new_zone_error_reports_bounds(client):
    res = client.post("/api/predict/new", json={"parcels": [parcel(lon=-120.0)]})
    assert res.status_code == 400
    assert "zona de estudio" in res.get_json()["error"]


def test_run_page_hides_secondary_columns_on_phones(client):
    html = client.get("/ejecutar").get_data(as_text=True)
    for label in ("Conjunto", "Régimen", "Estado"):
        assert f'class="hide-sm">{label}</th>' in html
    # Parcela, Municipio y Área siguen visibles en el celular
    for label in ("Parcela", "Municipio", "Área (ha)"):
        assert f'class="hide-sm">{label}' not in html


def test_run_script_labels_result_cells(client):
    js = client.get("/scripts/run.js").get_data(as_text=True)
    # Cada celda de la tabla de resultados lleva su etiqueta para la tarjeta del celular
    assert 'setAttribute("data-label", label)' in js
    assert "results-table" in js
    for label in ("Parcela", "Predicción (t/ha)", "Probabilidad bajo el umbral", "Confianza"):
        assert f'"{label}"' in js
    # Conjunto, Régimen y Estado de la lista llevan la clase que las oculta en el celular
    assert js.count('className: "hide-sm"') == 3


LOW_CONFIDENCE_TEXT = ("Hay parcelas con confianza baja: están lejos de las parcelas medidas o su superficie "
                       "queda fuera del rango de su régimen. Su resultado es menos fiable.")


def test_run_script_warns_low_confidence_once(client):
    js = client.get("/scripts/run.js").get_data(as_text=True)
    assert LOW_CONFIDENCE_TEXT in js
    assert "La parcela está lejos" not in js
    # El motivo de la confianza no se repite fila por fila: basta con el aviso general
    assert "confidence_reason" not in js


def test_run_css_has_mobile_rules(client):
    css = client.get("/styles/run.css").get_data(as_text=True)
    block = mobile_block(css)
    # Las tres columnas se ocultan y la lista deja de necesitar ancho mínimo
    assert ".hide-sm" in block and "display: none" in block
    assert "min-width: 0" in block
    # La tabla de resultados se apila: cada fila es una tarjeta y cada celda muestra su etiqueta
    assert ".results-table" in block and "display: block" in block
    assert "attr(data-label)" in block and "::before" in block
    # El encabezado se oculta con recorte visual, no con display: none
    head = block[block.index(".run .results-table thead"):]
    head = head[:head.index("}")]
    assert "clip: rect(0, 0, 0, 0)" in head
    assert "display: none" not in head


def test_run_page_custom_controls_stay_accessible(client):
    html = client.get("/ejecutar").get_data(as_text=True)
    # El selector de archivo propio: el campo nativo sigue en la página, con etiqueta en español
    assert 'id="csv-file" class="visually-hidden"' in html
    assert '<label for="csv-file"' in html and "Ningún archivo seleccionado" in html
    # El umbral conserva su unidad en el nombre accesible y su ayuda
    assert 'aria-describedby="threshold-help"' in html
    assert '<span class="visually-hidden"> (t/ha)</span>' in html
    js = client.get("/scripts/run.js").get_data(as_text=True)
    # La barra de rango se lee como imagen con sus valores en texto
    assert 'setAttribute("role", "img")' in js
    assert 'range.setAttribute("aria-label", text)' in js


def test_run_page_has_one_tab_per_path(client):
    html = client.get("/ejecutar").get_data(as_text=True)
    # Pestañas compartidas: tabs.js va antes que run.js
    assert html.index("/scripts/tabs.js") < html.index("/scripts/run.js")
    assert 'class="tabs" data-tabs' in html
    labels = re.findall(r'class="tabs__panel" id="([\w-]+)" data-tab-label="([^"]+)"', html)
    assert labels == [("del-conjunto", "Del conjunto de datos"), ("parcela-nueva", "Parcela nueva"),
                      ("desde-csv", "Desde CSV")]
    # Cada pestaña termina en su botón de acción, en su orden
    panels = html.split('class="tabs__panel"')[1:]
    for panel, button in zip(panels, ("run-button", "new-submit", "csv-run")):
        assert f'id="{button}"' in panel
    # Ningún texto remite a otra tarjeta: el umbral es común a las tres pestañas
    assert "tarjeta anterior" not in html


def test_run_page_threshold_is_shared_and_results_are_outside_tabs(client):
    html = client.get("/ejecutar").get_data(as_text=True)
    tabs_start = html.index('class="tabs" data-tabs')
    # El umbral va arriba de las pestañas, con su ayuda y su aviso de error junto al campo
    assert html.index('id="threshold"') < tabs_start
    assert html.index('id="threshold-help"') < tabs_start
    assert 'id="threshold-message" aria-live="polite"' in html
    # Los resultados van después de la última pestaña, fuera de ellas
    assert html.index('id="results"') > html.index('id="csv-message"')
    assert 'class="tabs__panel"' not in html[html.index('id="results"'):]


def test_run_script_results_rows_open_the_parcel_page(client):
    js = client.get("/scripts/run.js").get_data(as_text=True)
    # Toda la fila con ficha abre la ficha, sin estorbar al enlace ni a la selección de texto
    assert 'tr.className = "is-link"' in js
    assert "window.getSelection()" in js
    assert 'event.target.closest("a, button' in js
    # Las parcelas nuevas no tienen ficha y lo dicen
    assert "Parcela nueva, sin ficha" in js
    # La barra de rango lleva los valores p10–p90 en su texto accesible
    assert "intervalo p10–p90 de" in js
    # Al terminar, la vista se lleva a los resultados si quedaron abajo
    assert "scrollIntoView" in js
    # El CSV de descarga conserva todas sus columnas
    columns = js[js.index("const RESULT_COLUMNS = ["):]
    columns = re.findall(r'"(\w+)"', columns[:columns.index("];")])
    assert columns == ["id", "state", "municipality", "set", "pred", "p10", "p90", "prob_below",
                       "confidence", "neighbors_400m", "nearest_neighbor_m", "threshold", "model_version"]


def test_run_css_results_cards_on_phones(client):
    css = client.get("/styles/run.css").get_data(as_text=True)
    block = mobile_block(css)
    # Cada tarjeta del celular acomoda parcela, confianza, predicción y probabilidad en una rejilla
    assert "grid-template-areas" in block
    for area in ("parcela", "confianza", "prediccion", "probabilidad"):
        assert f"grid-area: {area}" in block
    # Botones de cada pestaña a todo el ancho y de 44 px
    assert ".run-bar__action" in block
    assert "min-height: 2.75rem" in css
