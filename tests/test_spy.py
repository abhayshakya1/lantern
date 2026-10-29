from lantern.sources import spy


def test_pull_spy_top10(tmp_store, fixture_server, monkeypatch):
    monkeypatch.setattr(spy, "SPY_URL", f"{fixture_server}/spy_holdings.xlsx")
    out = spy.pull_spy(tmp_store)
    v = out["spy.top10_weight"]["value"].iloc[0]
    assert 0.25 < v < 0.50
    assert tmp_store.load_series("spy.top10_weight")["value"].iloc[0] == v


def test_concentration_history_is_monthly_fraction(tmp_store, seeded_prices_and_shares):
    hist = spy.concentration_history(tmp_store, "2024-01")
    assert len(hist) >= 20 and list(hist.columns) == ["date", "value"]
    assert hist["value"].between(0.05, 0.6).all()
    assert tmp_store.get_meta("concentration.note") is not None


def test_concentration_history_uses_todays_ssga_value_when_present(tmp_store, seeded_prices_and_shares):
    import pandas as pd

    last = seeded_prices_and_shares["last_month_end"]
    tmp_store.save_series("spy.top10_weight", pd.DataFrame({"date": [last], "value": [0.389]}))
    hist = spy.concentration_history(tmp_store, "2024-01")
    assert abs(hist["value"].iloc[-1] - 0.389) < 1e-9
