from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from lantern import api, backtest, pull


@pytest.fixture
def seeded_run(tmp_store, seeded_all_series):
    backtest.run_backtest(tmp_store, "2010-01")
    tmp_store.set_meta("last_pull", {"at": datetime.now(UTC).isoformat(), "ok": True, "missing": []})
    return pull.run_model(tmp_store, now=datetime.now(UTC))


def test_monitor_404_without_run(tmp_store):
    client = TestClient(api.create_app(tmp_store))
    r = client.get("/api/monitor")
    assert r.status_code == 404 and r.json()["error"] == "no run yet"


def test_monitor_payload_shape(tmp_store, seeded_run):
    client = TestClient(api.create_app(tmp_store))
    body = client.get("/api/monitor").json()
    assert body["badge"]["state"] == "live" and body["as_of"].endswith("+08:00")
    assert len(body["chart"]["months"]) == 37 and len(body["chart"]["fan"]["p50"]) == 13
    pts = [d["contribution_pts"] for d in body["drivers"]]
    assert pts == sorted(pts, reverse=True) and len(body["drivers"]) == 7
    assert [t["id"] for t in body["triggers"]] == ["valuation", "concentration", "leverage", "capex"]


def test_driver_detail_and_unknown(tmp_store, seeded_run):
    client = TestClient(api.create_app(tmp_store))
    d = client.get("/api/drivers/valuation").json()
    assert d["weight"] == pytest.approx(0.25 / 0.55) and d["tier"] == "calibrated" and d["label"] == "Valuation stretch" and len(d["history"]) > 100
    assert set(d["history"][0]) == {"date", "reading", "z"} and d["trigger"]["direction"] == "below"
    assert 0 <= d["conditional_drawdown_share"] <= 1 and "source" in d and "transform" in d
    assert client.get("/api/drivers/nope").status_code == 404


def test_provenance_and_health(tmp_store, seeded_run):
    client = TestClient(api.create_app(tmp_store))
    assert client.get("/api/health").json() == {"ok": True}
    tmp_store.record_fetch("fred.DFII10", "https://example.org", "a" * 64, "x.csv", "ok", datetime.now(UTC))
    rows = client.get("/api/provenance").json()
    assert rows and rows[0]["name"] == "fred.DFII10" and len(rows[0]["sha256"]) == 64


def test_static_index_served(tmp_store, seeded_run):
    client = TestClient(api.create_app(tmp_store))
    r = client.get("/")
    assert r.status_code == 200 and "AI-bubble monitor" in r.text


def test_driver_detail_carries_the_note(tmp_store, seeded_run):
    client = TestClient(api.create_app(tmp_store))
    assert "TSM" in client.get("/api/drivers/valuation").json()["note"]
