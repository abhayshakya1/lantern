from lantern.sources import sentiment


def test_pull_sentiment_parses_aaii_weekly_spread(tmp_store, fixture_server, monkeypatch):
    monkeypatch.setattr(sentiment, "AAII_URL", f"{fixture_server}/aaii.xlsx")
    out = sentiment.pull_sentiment(tmp_store)
    df = out["aaii.bull_bear"]
    assert list(df.columns) == ["date", "value"] and len(df) >= 500
    assert df["value"].between(-1, 1).all() and df["date"].is_monotonic_increasing
    assert str(df["date"].dtype).startswith("datetime64")
    assert tmp_store.load_series("aaii.bull_bear") is not None
