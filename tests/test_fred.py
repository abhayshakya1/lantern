from lantern.sources import fred


def test_pull_fred_parses_and_drops_missing(tmp_store, fixture_server, monkeypatch):
    monkeypatch.setattr(fred, "fred_url", lambda sid: f"{fixture_server}/fred_{sid}.csv")
    out = fred.pull_fred(tmp_store, {"real_yield": "DFII10"})
    df = out["fred.DFII10"]
    assert list(df.columns) == ["date", "value"]
    # 60 rows: two "." rows and two empty-value holiday rows are dropped
    assert df["value"].notna().all() and len(df) == 56
    assert str(df["date"].dtype).startswith("datetime64")
    assert tmp_store.load_series("fred.DFII10") is not None


def test_fred_url():
    assert fred.fred_url("DFII10") == "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10"
