import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("flask")

from app import MAX_CONTENT_LENGTH, create_app
from app.modules import model

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def client():
    return create_app({"TESTING": True}).test_client()


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}


def test_index_loads_map(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b'id="map"' in res.data
    assert b"/scripts/map.js" in res.data


def test_map_script(client):
    res = client.get("/scripts/map.js")
    assert res.status_code == 200
    assert "javascript" in res.mimetype


def test_parcels_geojson(client):
    res = client.get("/api/parcels")
    assert res.status_code == 200
    data = res.get_json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 197
    props = [f["properties"] for f in data["features"]]
    assert all(set(p) == {"id", "state", "municipality", "set", "yield_t_ha", "area_ha"} for p in props)
    assert sum(p["yield_t_ha"] is not None for p in props) == 138
    assert all(p["yield_t_ha"] is None for p in props if p["set"] == "PREDICCION")


def test_predictions_json(client):
    res = client.get("/api/predictions")
    assert res.status_code == 200
    rows = res.get_json()
    assert len(rows) == 197
    keys = {"id", "set", "regime", "state", "municipality", "area_ha", "pred", "p10", "p90", "prob_below", "observed"}
    assert all(set(r) == keys for r in rows)
    assert all(r["p10"] <= r["pred"] <= r["p90"] for r in rows)


def test_predictions_filter_set(client):
    rows = client.get("/api/predictions?set=PREDICCION").get_json()
    assert len(rows) == 59
    assert all(r["observed"] is None for r in rows)


def test_predictions_csv(client):
    res = client.get("/api/predictions?format=csv")
    assert res.status_code == 200
    assert res.mimetype == "text/csv"
    lines = res.get_data(as_text=True).strip().splitlines()
    assert lines[0].startswith("id,set,regime")
    assert len(lines) == 198


def test_predictions_invalid_set(client):
    res = client.get("/api/predictions?set=OTRO")
    assert res.status_code == 400
    assert "error" in res.get_json()


def predict_ids(client, ids, **extra):
    return client.post("/api/predict", json={"ids": ids, **extra})


def test_predict_matches_precomputed(client):
    ids = ["AGC_001", "AGC_002"]
    expected = {r["id"]: r for r in client.get("/api/predictions").get_json() if r["id"] in ids}
    res = predict_ids(client, ids)
    assert res.status_code == 200
    data = res.get_json()
    assert data["threshold"] == 2.5
    assert data["model_version"]
    rows = data["predictions"]
    assert [r["id"] for r in rows] == ids
    for r in rows:
        assert set(r) == {"id", "pred", "p10", "p90", "prob_below"}
        for key in ("pred", "p10", "p90", "prob_below"):
            assert r[key] == pytest.approx(expected[r["id"]][key], abs=1e-3)


def test_predict_threshold(client):
    ids = ["AGC_001", "AGC_002", "AGC_003"]
    low = predict_ids(client, ids, threshold=2.0).get_json()["predictions"]
    high = predict_ids(client, ids, threshold=4.5).get_json()["predictions"]
    # Con un umbral más alto la probabilidad de quedar por debajo no baja
    assert all(h["prob_below"] >= l["prob_below"] for l, h in zip(low, high))


def test_predict_reuses_cache(client):
    predict_ids(client, ["AGC_004", "AGC_005"])
    hits = model.predict_cached.cache_info().hits
    # Mismo conjunto en otro orden y con repetidos: mismo resultado del caché
    res = predict_ids(client, ["AGC_005", "AGC_004", "AGC_004"])
    assert res.status_code == 200
    assert model.predict_cached.cache_info().hits == hits + 1
    assert model.predict_cached.cache_info().maxsize is not None


@pytest.mark.parametrize("body", [
    None,
    [],
    {},
    {"ids": []},
    {"ids": "AGC_001"},
    {"ids": [1, 2]},
    {"ids": ["NO_EXISTE"]},
    {"ids": ["AGC_001"], "threshold": "alto"},
    {"ids": ["AGC_001"], "threshold": True},
    {"ids": ["AGC_001"], "threshold": 50},
])
def test_predict_invalid(client, body):
    res = client.post("/api/predict", json=body)
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_predict_max_parcels(client):
    ids = [f["properties"]["id"] for f in client.get("/api/parcels").get_json()["features"]]
    assert predict_ids(client, ids[:model.MAX_PARCELS]).status_code == 200
    res = predict_ids(client, ids[:model.MAX_PARCELS + 1])
    assert res.status_code == 400
    assert str(model.MAX_PARCELS) in res.get_json()["error"]


def test_predict_only_post(client):
    assert client.get("/api/predict").status_code == 405


def test_request_body_limit(client):
    res = client.post("/api/predict", data=b"x" * (MAX_CONTENT_LENGTH + 1), content_type="application/json")
    assert res.status_code == 413


def test_routes_follow_mount_point(client):
    # Las rutas salen de url_for: si la app se montara bajo /sub, todas lo seguirían
    html = client.get("/", base_url="http://localhost/sub/").get_data(as_text=True)
    paths = re.findall(r'(?:href|src|data-[\w-]+-url)="([^"]+)"', html)
    assert paths
    assert all(p.startswith(("/sub/", "https://")) for p in paths)
    # El JavaScript toma las rutas de la página, no las escribe a mano
    js = client.get("/scripts/map.js").get_data(as_text=True)
    assert '"/api/' not in js and "'/api/" not in js


def test_warm_up_fills_caches():
    from app import AgroCebadaApp
    AgroCebadaApp().warm_up()
    assert model.load_model.cache_info().currsize == 1
    assert model.features_table.cache_info().currsize == 1


# Corre la app en otro proceso con estos módulos bloqueados, como en el servidor, donde
# no están instalados o no se deben usar desde una petición (reentrenar, leer rásteres)
BLOCKED = ["tabpfn", "torch", "exactextract", "rasterio",
           "parcelas.io", "parcelas.features_env", "parcelas.train_final"]
ISOLATED = f"""
import importlib.abc
import sys

class Blocker(importlib.abc.MetaPathFinder):
    # Importarlos falla como si no estuvieran instalados
    def find_spec(self, name, path, target=None):
        if any(name == b or name.startswith(b + ".") for b in {BLOCKED!r}):
            raise ModuleNotFoundError(f"No module named {{name!r}}", name=name)

sys.meta_path.insert(0, Blocker())
import app
assert app.PORT == 8123, app.PORT
assert app.MAX_CONTENT_LENGTH == 4096, app.MAX_CONTENT_LENGTH
client = app.create_app({{"TESTING": True}}).test_client()
for path in ("/", "/health", "/api/parcels", "/api/predictions"):
    assert client.get(path).status_code == 200, path
assert client.post("/api/predict", json={{"ids": ["AGC_001"]}}).status_code == 200
assert client.post("/api/predict", data=b"x" * 5000, content_type="application/json").status_code == 413
print("ok")
"""


def test_app_runs_without_heavy_dependencies():
    # Valores distintos de los de por defecto, para comprobar que se leen del entorno
    env = {**os.environ, "AGRCBDA_PORT": "8123", "AGRCBDA_MAX_CONTENT_LENGTH": "4096"}
    res = subprocess.run([sys.executable, "-c", ISOLATED], cwd=ROOT, env=env,
                         capture_output=True, text=True, timeout=600)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip().endswith("ok")
