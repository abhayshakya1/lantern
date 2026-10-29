from lantern.sources import shiller


def test_pull_shiller_monthly_pe_and_long_rate(tmp_store, fixture_server, monkeypatch):
    monkeypatch.setattr(shiller, "SHILLER_URL", f"{fixture_server}/shiller_ie_data.xlsx")
    out = shiller.pull_shiller(tmp_store)
    pe, rate = out["shiller.pe"], out["shiller.long_rate"]
    # earnings collapses (2009) push the trailing P/E past 100, so only the floor and the median are pinned
    assert pe["date"].min().year <= 1990 and pe["value"].gt(0).all() and 10 < pe["value"].median() < 40
    assert rate["value"].between(0, 20).all()
    # month decoded from the fraction column: 1985.1 is October, not January
    first = pe["date"].iloc[0]
    assert (first.year, first.month) == (1985, 1)
    assert pe["date"].dt.is_month_end.all()
