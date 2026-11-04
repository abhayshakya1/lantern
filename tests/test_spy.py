import pytest

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
    raw = spy.concentration_history(tmp_store, "2024-01")  # reconstruction alone, on its own level
    tmp_store.save_series("spy.top10_weight", pd.DataFrame({"date": [last], "value": [0.389]}))
    hist = spy.concentration_history(tmp_store, "2024-01")
    assert abs(hist["value"].iloc[-1] - 0.389) < 1e-9
    # the history is rescaled onto the SSGA level, so its shape survives and the last two months compare
    assert hist["value"].iloc[-2] / hist["value"].iloc[-1] == pytest.approx(raw["value"].iloc[-2] / raw["value"].iloc[-1], rel=1e-9)


def test_shares_by_month_goes_stale_after_two_years():
    import pandas as pd

    months = pd.period_range("2023-01", "2026-10", freq="M").to_timestamp("M")
    sh = pd.DataFrame({"date": pd.to_datetime(["2023-02-01"]), "value": [1e9]})
    s = spy._shares_by_month(sh, months)
    assert pd.isna(s[pd.Timestamp("2023-01-31")]) and s[pd.Timestamp("2024-12-31")] == 1e9
    assert pd.isna(s[pd.Timestamp("2025-03-31")])  # a share count older than two years no longer stands in


def test_concentration_history_absent_without_share_data_ignores_tsm_and_uses_splits(tmp_store, seeded_prices_and_shares):
    import pandas as pd

    hist = spy.concentration_history(tmp_store, "2023-01")
    assert hist["date"].min() >= pd.Timestamp("2023-02-28") and (hist["value"] > 0).all()  # Jan 2023: no count filed, absent not 0%
    tmp_store.save_series(
        "edgar.TSM.shares",
        pd.DataFrame({"date": pd.to_datetime(["2023-02-01"]), "period_end": pd.to_datetime(["2023-01-15"]), "value": [1e13], "kind": ["instant"]}),
    )
    again = spy.concentration_history(tmp_store, "2023-01")
    assert again["value"].tolist() == pytest.approx(hist["value"].tolist())  # TSM is not in the S&P 500
    tmp_store.save_series("yahoo.splits.AAPL", pd.DataFrame({"date": pd.to_datetime(["2026-01-15"]), "value": [4.0]}))
    split = spy.concentration_history(tmp_store, "2023-01")
    assert split["value"].iloc[0] > hist["value"].iloc[0]  # AAPL's pre-split counts now carry the split
