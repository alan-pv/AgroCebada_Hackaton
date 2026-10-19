# Página y API de la metodología (issue #12): secciones, cifras contra sus fuentes y enlaces
import json
import re

import pandas as pd
import pytest

pytest.importorskip("flask")

from parcelas.config import OUTPUTS
from app import create_app
from app.modules import methodology, model

SECCIONES = ("Cómo se obtiene el número",
             "Qué significan p10, p90, la probabilidad y la confianza",
             "Desempeño en validación",
             "Qué pesa en el número",
             "Limitaciones")


def sin_nan(res):
    # JSON estricto: Flask escribiría NaN o Infinity si algún valor los trae, y eso no es JSON válido
    def rechazar(constante):
        raise ValueError(f"JSON no válido: {constante}")
    return json.loads(res.get_data(as_text=True), parse_constant=rechazar)


@pytest.fixture(scope="module")
def client():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture(scope="module")
def payload(client):
    res = client.get("/api/methodology")
    assert res.status_code == 200
    return sin_nan(res)


def test_page_has_sections(client):
    res = client.get("/metodologia")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    for titulo in SECCIONES:
        assert f"<h2>{titulo}</h2>" in html
    assert "methodology.css" in html


def test_page_index_and_sections(client):
    html = client.get("/metodologia").get_data(as_text=True)
    # Índice con un enlace por sección, cada uno al id de su <section>
    indice = re.search(r'<nav class="toc[^"]*" aria-label="En esta página">(.*?)</nav>', html, re.S).group(1)
    anclas = re.findall(r'href="/metodologia#([\w-]+)">([^<]+)</a>', indice)
    assert [titulo for _, titulo in anclas] == list(SECCIONES)
    for ancla, titulo in anclas:
        assert re.search(rf'<section id="{ancla}" class="card[^"]*">\s*<h2>{re.escape(titulo)}</h2>', html)


def test_page_stats_come_from_methodology(client, payload):
    html = client.get("/metodologia").get_data(as_text=True)
    esquema_a = payload["validation"][0]
    cobertura = next(f for f in payload["interval_coverage"] if f["group"] == "global")
    indicadores = re.search(r'<dl class="stat-grid[^"]*"[^>]*>(.*?)</dl>', html, re.S).group(1)
    valores = re.findall(r'<dd class="stat__value">([^<]+)', indicadores)
    assert [v.strip() for v in valores] == [f"{esquema_a['rmse']:.3f}", f"{esquema_a['r2']:.3f}",
                                           f"{cobertura['coverage'] * 100:.1f} %", str(payload["model"]["n_train"])]
    assert "Meta 80 %" in indicadores


def test_page_charts_have_table_below(client):
    html = client.get("/metodologia").get_data(as_text=True)
    figuras = re.findall(r'<figure class="method-figure">(.*?)</figure>\s*<details class="disclosure">\s*'
                         r'<summary>Ver tabla</summary>(.*?)</details>', html, re.S)
    # Cinco gráficas, cada una con su versión ancha y angosta, su pie y su tabla debajo
    assert len(figuras) == 5
    for figura, tabla in figuras:
        assert "<figcaption>" in figura
        assert figura.count('role="img"') == 2
        assert figura.count("<title id=") == 2 and figura.count("<desc id=") == 2
        assert '<table class="data' in tabla
    # La página no usa JavaScript
    assert "<script" not in html



def resumen(html):
    return re.search(r'<section class="card method__summary"[^>]*>(.*?)</section>', html, re.S).group(1)


def test_page_summary_comes_from_methodology(client, payload):
    html = client.get("/metodologia").get_data(as_text=True)
    bloque = resumen(html)
    # Va antes de los indicadores y responde tres preguntas
    assert html.index("En resumen") < html.index('<dl class="stat-grid')
    assert re.findall(r"<dt>([^<]+)</dt>", bloque) == ["Qué hace", "Qué tan bien funciona", "Para qué no sirve"]
    # Las cifras salen de la validación, no del texto de la plantilla
    esquema_a = payload["validation"][0]
    cobertura = next(f for f in payload["interval_coverage"] if f["group"] == "global")
    assert f"su error típico (RMSE) es de {esquema_a['rmse']:.3f} t/ha" in bloque
    assert f"contuvo el rendimiento real en {cobertura['coverage'] * 100:.1f} % de las parcelas" in bloque
    assert "verificación en campo" in bloque and "sequía, helada o plaga" in bloque
    # Definiciones cortas junto al resumen, con enlace a las completas
    assert '<details class="help-inline">' in bloque and 'href="/metodologia#terminos"' in bloque


# Detalle técnico plegado: título del <summary> y una frase de su contenido, que debe seguir en el HTML
PLEGADAS = {"Confianza frente a error": "Sin vecinos, el error absoluto sube",
            "Margen de azar de la calificación": "es compatible con el mismo modelo",
            "Otras variables que se probaron": "Cuando el régimen no está presente"}


def plegadas(html):
    # Cada <details class="disclosure method-more">: título y contenido, con sus <details> internos.
    # Va hasta el siguiente plegado o hasta el fin de su sección
    partes = html.split('<details class="disclosure method-more">')[1:]
    salida = {}
    for parte in (p.split("</section>")[0] for p in partes):
        titulo = re.search(r'<span class="method-more__title">([^<]+)</span>', parte).group(1)
        salida[titulo] = parte
    return salida


def test_page_technical_details_are_folded(client):
    html = client.get("/metodologia").get_data(as_text=True)
    bloques = plegadas(html)
    for titulo, frase in PLEGADAS.items():
        assert titulo in bloques
        # Una línea de qué responde, y el contenido sigue en la página aunque esté plegado
        assert re.search(r'<span class="method-more__hint">¿[^<]+\?</span>', bloques[titulo])
        assert frase in bloques[titulo]
        assert f"<h3>{titulo}</h3>" not in html
    # Lo esencial queda a la vista, como subsección con su título
    for titulo in ("Esquemas A y B", "Cobertura del intervalo p10 a p90"):
        assert f"<h3>{titulo}</h3>" in html


def test_page_limitations_top_three_and_rest_folded(client):
    html = client.get("/metodologia").get_data(as_text=True)
    seccion = re.search(r'<section id="limitaciones"[^>]*>(.*?)</section>', html, re.S).group(1)
    vista = re.search(r'<ul class="limits limits--main">(.*?)</ul>', seccion, re.S).group(1)
    assert re.findall(r"<strong>([^<]+)\.</strong>", vista) == ["Un solo año", "Rendimiento declarado",
                                                               "Régimen inferido"]
    # El resto va plegado, con el número calculado, y ninguna se pierde
    todas = re.findall(r"<li><strong>([^<]+)\.</strong>", seccion)
    assert len(todas) == 10 and len(set(todas)) == 10
    assert f"Ver las {len(todas) - 3} limitaciones restantes" in seccion
    assert "Parcelas pequeñas" in plegadas(html)["Ver las 7 limitaciones restantes"]

def test_api_structure_is_strict_json(payload):
    assert set(payload) >= {"model", "validation", "interval_coverage", "confidence_vs_error",
                            "chance_margin", "final_model_contributions", "other_groups"}
    assert set(payload["model"]) >= {"version", "trained_on", "n_train", "threshold", "interval_level"}
    assert [f["scheme"] for f in payload["validation"]] == ["A", "B"]
    assert all(set(f) >= {"scheme", "rmse", "mae", "r2"} for f in payload["validation"])
    assert all(set(f) >= {"group", "coverage", "width", "below_p10", "above_p90"}
               for f in payload["interval_coverage"])
    assert all(set(f) >= {"group", "parcels", "mae", "coverage"} for f in payload["confidence_vs_error"])
    assert set(payload["chance_margin"]) >= {"parcels", "rmse_mean", "rmse_sd", "p05", "p95"}
    assert all(set(f) >= {"key", "label", "mean_abs_t_ha"} for f in payload["final_model_contributions"])
    assert all(set(f) >= {"group", "delta_rmse", "p05", "p95"} for f in payload["other_groups"])


def test_validation_matches_model_object(payload):
    met = model.load_model().metricas
    por_esquema = {f["scheme"]: f for f in payload["validation"]}
    for esquema in ("A", "B"):
        assert por_esquema[esquema]["rmse"] == pytest.approx(met[esquema]["rmse"], abs=1e-4)
        assert por_esquema[esquema]["mae"] == pytest.approx(met[esquema]["mae"], abs=1e-4)
        assert por_esquema[esquema]["r2"] == pytest.approx(met[esquema]["r2"], abs=1e-4)


def test_coverage_matches_calibration_csv(payload):
    cal = pd.read_csv(OUTPUTS / "calibracion_p10.csv").set_index("grupo")
    por_grupo = {f["group"]: f for f in payload["interval_coverage"]}
    assert set(por_grupo) == {"A", "B", "global"}
    for grupo in por_grupo:
        assert por_grupo[grupo]["coverage"] == pytest.approx(cal.loc[grupo, "cobertura"], abs=1e-4)
        assert por_grupo[grupo]["width"] == pytest.approx(cal.loc[grupo, "ancho"], abs=1e-4)
        assert por_grupo[grupo]["below_p10"] == pytest.approx(cal.loc[grupo, "cola_baja"], abs=1e-4)
        assert por_grupo[grupo]["above_p90"] == pytest.approx(cal.loc[grupo, "cola_alta"], abs=1e-4)
    # La cobertura global de la validación anidada coincide con la del objeto del modelo
    met = model.load_model().metricas
    assert por_grupo["global"]["coverage"] == pytest.approx(met["intervalo"]["cobertura_global_anidada"], abs=1e-4)


def test_final_model_contributions(payload):
    aportes = payload["final_model_contributions"]
    assert [a["key"] for a in aportes] == ["regime", "spatial_lag"]
    assert all(a["mean_abs_t_ha"] > 0 for a in aportes)
    # Las 59 parcelas de PREDICCION, con la fila del modelo entregado (candidato)
    sv = pd.read_parquet(OUTPUTS / "shap_values.parquet")
    pr = pd.read_parquet(OUTPUTS / "predicciones.parquet")
    ids = pr.loc[pr["conjunto"] == "PREDICCION", "ID_POLIGONO"]
    cand = sv[(sv["modelo"] == "candidato") & sv["ID_POLIGONO"].isin(ids)]
    assert len(cand) == 59
    assert aportes[0]["mean_abs_t_ha"] == pytest.approx((cand["regimen_A"] + cand["regimen_B"]).abs().mean(),
                                                        abs=1e-4)
    assert aportes[1]["mean_abs_t_ha"] == pytest.approx(cand["rezago_y"].abs().mean(), abs=1e-4)


def test_other_groups_top_eight_sorted(payload):
    grupos = payload["other_groups"]
    assert len(grupos) == 8
    deltas = [g["delta_rmse"] for g in grupos]
    assert deltas == sorted(deltas, reverse=True)
    # Son los ocho de mayor importancia en la ablación con el régimen presente
    imp = pd.read_parquet(OUTPUTS / "importancias.parquet")
    ablacion = imp[(imp["escenario"] == "regimen_presente_completo") & (imp["metodo"] == "ablacion_logo")]
    assert [g["group"] for g in grupos] == ablacion.nlargest(8, "importancia_media")["grupo"].tolist()


def test_page_links_follow_mount_point(client):
    html = client.get("/metodologia", base_url="http://localhost/sub/").get_data(as_text=True)
    rutas = re.findall(r'(?:href|src|data-[\w-]+-url)="([^"]+)"', html)
    assert rutas
    assert all(r.startswith(("/sub/", "https://")) for r in rutas)


@pytest.fixture
def sin_outputs(tmp_path, monkeypatch):
    # outputs/ vacía: cada tabla debe omitirse con un aviso, sin fallar
    monkeypatch.setattr(methodology, "OUTPUTS", tmp_path)
    methodology._read_output.cache_clear()
    yield
    methodology._read_output.cache_clear()


def test_missing_outputs_omit_sections(client, sin_outputs):
    payload = sin_nan(client.get("/api/methodology"))
    assert payload["interval_coverage"] is None
    assert payload["final_model_contributions"] is None
    assert payload["model"] is not None  # el modelo no depende de outputs/
    res = client.get("/metodologia")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "no está disponible" in html
    # Las gráficas que dependen de outputs/ desaparecen con su tabla; la del modelo se queda
    assert html.count('<figure class="method-figure">') == 1
    assert "RMSE del modelo y de la media por régimen" in html
    # El resumen se queda con lo que hay: el error del modelo, sin la cobertura que falta
    bloque = resumen(html)
    assert "su error típico (RMSE) es de" in bloque and "contuvo el rendimiento real" not in bloque
    # Las secciones plegadas conservan su aviso
    assert "no está disponible" in plegadas(html)["Margen de azar de la calificación"]
