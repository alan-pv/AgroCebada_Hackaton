import pytest

pytest.importorskip("flask")

from app import create_app


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
