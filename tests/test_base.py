import pytest

from lantern.sources.base import SourceError, fetch_raw


def test_fetch_raw_writes_file_hash_and_provenance(tmp_store, fixture_server):
    r = fetch_raw(tmp_store, "fred.DFII10", fixture_server + "/fred_DFII10.csv")
    assert r.path.exists() and r.path.suffix == ".csv" and len(r.sha256) == 64
    assert r.content.startswith(b"observation_date")
    row = tmp_store.provenance()[0]
    assert row["name"] == "fred.DFII10" and row["status"] == "ok" and row["sha256"] == r.sha256


def test_fetch_raw_retries_once_on_connection_error(tmp_store, fixture_server, monkeypatch):
    from lantern.sources import base

    real_get, calls = base._http_get, []

    def flaky(url, headers, params, timeout):
        calls.append(url)
        if len(calls) == 1:
            raise ConnectionError("reset by peer")
        return real_get(url, headers, params, timeout)

    monkeypatch.setattr(base, "_http_get", flaky)
    monkeypatch.setattr(base, "RETRY_WAIT", 0.0)
    r = fetch_raw(tmp_store, "fred.DFII10", fixture_server + "/fred_DFII10.csv")
    assert len(calls) == 2 and r.content.startswith(b"observation_date")
    assert tmp_store.provenance()[0]["status"] == "ok"


def test_fetch_raw_404_records_error_and_raises(tmp_store, fixture_server):
    with pytest.raises(SourceError):
        fetch_raw(tmp_store, "nothing", fixture_server + "/missing.csv")
    assert tmp_store.provenance()[0]["status"] == "error"


def test_fetch_raw_redacts_query_params_from_errors(tmp_store, monkeypatch):
    import pytest

    from lantern.sources import base

    monkeypatch.setattr(base, "RETRY_WAIT", 0)
    with pytest.raises(SourceError) as e:
        fetch_raw(tmp_store, "fred.DFII10", "http://127.0.0.1:9/fred/series/observations", params={"series_id": "DFII10", "api_key": "SECRETKEY123"})
    assert "SECRETKEY123" not in str(e.value) and e.value.__cause__ is None
    assert all("SECRETKEY123" not in p["url"] for p in tmp_store.provenance())
