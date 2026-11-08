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


# --- filings Q&A (plan 2) ---------------------------------------------------------------------------

import shutil

from lantern.filings import corpus, retrieve
from tests.conftest import FIXTURES, FakeClaude


@pytest.fixture
def filings_app(tmp_store, tmp_path, monkeypatch):
    shutil.copytree(FIXTURES / "filings", tmp_path / "filings")
    monkeypatch.setattr(api.config, "FILINGS_DIR", tmp_path / "filings")
    chunks, manifest = corpus.build_corpus(tmp_path / "filings")
    retrieve.build_index(chunks, tmp_path / "index", retrieve.HashEmbedder(), manifest)
    r = retrieve.Retriever(tmp_path / "index", retrieve.HashEmbedder())
    cid = next(h.chunk.id for h in r.search("final dividend") if "42 cents" in h.chunk.text)
    fake = FakeClaude({"answerable": True, "answer": "ACME recommended 42 cents per share. It follows a 7% profit rise.",
                       "evidence": [{"chunk_id": cid, "quote": "The Board recommends a final dividend of 42 cents per share."}], "confidence": "high"})
    return TestClient(api.create_app(tmp_store, retriever=r, llm_client=fake))


def test_ask_returns_evidence_with_pdf_links_and_logs_history(filings_app):
    body = filings_app.post("/api/filings/ask", json={"question": "What final dividend did ACME recommend?"}).json()
    assert body["answerable"] and body["evidence"][0]["pdf_url"] == "/filings/pdf/ACME-AR2025.pdf#page=2" and body["confidence"] == "high"
    hist = filings_app.get("/api/filings/history").json()
    assert hist[0]["question"].startswith("What final dividend") and "response" not in hist[0]
    assert filings_app.post("/api/filings/ask", json={"question": ""}).status_code == 400
    assert filings_app.post("/api/filings/ask", json={"question": "x" * 501}).status_code == 400


def test_corpus_lists_manifest_and_index_meta(filings_app):
    body = filings_app.get("/api/filings/corpus").json()
    assert {m["ticker"] for m in body["filings"]} == {"ACME", "BETA"} and body["filings"][0]["pages"] == 3 and body["index"]["n_chunks"] > 0


def test_pdf_is_served_and_eval_404_before_a_run(filings_app):
    assert filings_app.get("/filings/pdf/ACME-AR2025.pdf").status_code == 200
    assert filings_app.get("/api/filings/eval").status_code == 404


def test_ask_without_index_is_503(tmp_store, tmp_path, monkeypatch):
    monkeypatch.setattr(api.config, "FILINGS_INDEX", tmp_path / "missing")
    assert TestClient(api.create_app(tmp_store)).post("/api/filings/ask", json={"question": "x"}).status_code == 503


def test_pdf_route_serves_only_manifest_pdfs(filings_app, tmp_path):
    gold = api.config.FILINGS_DIR / "gold"
    gold.mkdir(parents=True, exist_ok=True)
    (gold / "gold_draft.jsonl").write_text('{"answer": "secret"}\n')
    assert filings_app.get("/filings/pdf/ACME-AR2025.pdf").status_code == 200
    assert filings_app.get("/filings/pdf/gold/gold_draft.jsonl").status_code == 404  # only the manifest's PDFs are served
    assert filings_app.get("/filings/pdf/manifest.json").status_code == 404


def _research_client(tmp_store, run_fixture):
    tmp_store.save_run(run_fixture)
    return TestClient(api.create_app(tmp_store))


def test_research_notes_list_is_empty_before_any_note(tmp_store):
    client = TestClient(api.create_app(tmp_store))
    assert client.get("/api/research/notes").json() == []


def test_research_note_404_for_unknown_id(tmp_store, run_fixture):
    client = _research_client(tmp_store, run_fixture)
    r = client.get("/api/research/note/nope")
    assert r.status_code == 404 and "error" in r.json()
    rp = client.get("/research/note/nope/print")
    assert rp.status_code == 404 and "error" in rp.json()


def test_research_generate_offline_and_note_view(tmp_store, run_fixture, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = _research_client(tmp_store, run_fixture)
    r = client.post("/api/research/generate")
    assert r.status_code == 201 and r.json()["source"] == "offline-template"
    nid = r.json()["id"]
    feed = client.get("/api/research/notes").json()
    assert feed[0]["id"] == nid and feed[0]["status"] == "Draft" and "title" in feed[0]
    note = client.get(f"/api/research/note/{nid}").json()
    assert note["author"] == "Lantern model, reviewed by Abhay" and note["chart"]["scenarios"]
    pub = client.post(f"/api/research/note/{nid}/publish")
    assert pub.status_code == 200 and client.get(f"/api/research/note/{nid}").json()["status"] == "Published"
    html = client.get(f"/research/note/{nid}/print").text
    assert note["title"] in html and "charts.js" in html


def test_research_generate_409_without_a_run(tmp_store):
    client = TestClient(api.create_app(tmp_store))
    assert client.post("/api/research/generate").status_code == 409


def test_research_ledger_endpoint(tmp_store, seeded_all_series, run_fixture):
    backtest.run_backtest(tmp_store, "2010-01")
    client = _research_client(tmp_store, run_fixture)
    rows = client.get("/api/research/ledger").json()
    assert rows and rows[-1]["kind"] == "backtest"
