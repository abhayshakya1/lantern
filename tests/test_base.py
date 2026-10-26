import pytest

from lantern.sources.base import SourceError, fetch_raw


def test_fetch_raw_writes_file_hash_and_provenance(tmp_store, fixture_server):
    r = fetch_raw(tmp_store, "fred.DFII10", fixture_server + "/fred_DFII10.csv")
    assert r.path.exists() and r.path.suffix == ".csv" and len(r.sha256) == 64
    assert r.content.startswith(b"observation_date")
    row = tmp_store.provenance()[0]
    assert row["name"] == "fred.DFII10" and row["status"] == "ok" and row["sha256"] == r.sha256


def test_fetch_raw_404_records_error_and_raises(tmp_store, fixture_server):
    with pytest.raises(SourceError):
        fetch_raw(tmp_store, "nothing", fixture_server + "/missing.csv")
    assert tmp_store.provenance()[0]["status"] == "error"
