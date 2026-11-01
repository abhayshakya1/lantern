import pandas as pd


def test_series_roundtrip(tmp_store):
    df = pd.DataFrame(
        {"date": pd.to_datetime(["2026-01-31", "2026-02-28"]).date, "value": [1.0, 2.0]}
    )
    tmp_store.save_series("fred.DFII10", df)
    out = tmp_store.load_series("fred.DFII10")
    assert out["value"].tolist() == [1.0, 2.0]
    assert tmp_store.load_series("missing") is None


def test_series_dates_load_with_one_dtype_whatever_was_saved(tmp_store):
    """yfinance yields datetime64[ms], EDGAR datetime64[us]; merge_asof needs them to match."""
    ms = pd.DataFrame({"date": pd.to_datetime(["2026-01-31"]).astype("datetime64[ms]"), "value": [1.0]})
    us = pd.DataFrame({"date": pd.to_datetime(["2026-01-31"]).astype("datetime64[us]"), "value": [2.0]})
    tmp_store.save_series("a", ms)
    tmp_store.save_series("b", us)
    a, b = tmp_store.load_series("a"), tmp_store.load_series("b")
    assert a["date"].dtype == b["date"].dtype == "datetime64[ns]"


def test_run_ids_are_ordered_and_latest_wins(tmp_store):
    a = tmp_store.save_run({"probability": 0.3})
    b = tmp_store.save_run({"probability": 0.4})
    assert a < b
    assert tmp_store.latest_run()["probability"] == 0.4


def test_meta_roundtrip_and_missing(tmp_store):
    assert tmp_store.get_meta("nothing") is None
    tmp_store.set_meta("last_pull", {"at": "2026-11-07T00:00:00+00:00", "ok": True})
    assert tmp_store.get_meta("last_pull")["ok"] is True
