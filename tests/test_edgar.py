from datetime import date

import pandas as pd

from lantern.sources import edgar


def _serve(fixture_server, monkeypatch, name):
    monkeypatch.setattr(edgar, "facts_url", lambda cik: f"{fixture_server}/edgar_{name}.json")


def test_capex_series_keyed_by_filing_date(tmp_store, fixture_server, monkeypatch):
    _serve(fixture_server, monkeypatch, "MSFT")
    edgar.pull_edgar(tmp_store, ["MSFT"])
    capex = tmp_store.load_series("edgar.MSFT.capex")
    assert list(capex.columns) == ["date", "period_end", "value", "kind"]
    # only the oldest fiscal year (whose 10-Qs predate the fixture) stays annual; everything after is quarterly
    assert set(capex.loc[capex["period_end"] >= "2010-06-30", "kind"]) == {"quarter"}
    assert (capex["date"] >= capex["period_end"]).all()  # a filing never precedes its period end
    assert capex["period_end"].is_monotonic_increasing and capex["period_end"].is_unique
    # four quarters a year, each a 3-month flow: FY2025 (Jul 2024 to Jun 2025) sums to the 10-K figure
    fy25 = capex[(capex["period_end"] >= "2024-09-30") & (capex["period_end"] <= "2025-06-30")]
    assert len(fy25) == 4 and fy25["value"].sum() == 64_551_000_000


def test_trailing_4q_uses_only_facts_filed_by_as_of(tmp_store, fixture_server, monkeypatch):
    _serve(fixture_server, monkeypatch, "MSFT")
    edgar.pull_edgar(tmp_store, ["MSFT"])
    capex = tmp_store.load_series("edgar.MSFT.capex")
    early = edgar.trailing_4q(capex, date(2025, 7, 1))   # the FY2025 10-K (filed 30 Jul 2025) is not yet known
    late = edgar.trailing_4q(capex, date(2025, 8, 15))
    assert early != late and late == 64_551_000_000


def test_shares_are_instant_values_with_latest_lookup(tmp_store, fixture_server, monkeypatch):
    _serve(fixture_server, monkeypatch, "MSFT")
    edgar.pull_edgar(tmp_store, ["MSFT"])
    shares = tmp_store.load_series("edgar.MSFT.shares")
    assert 7e9 < edgar.latest_value(shares, date(2026, 1, 31)) < 8e9


def test_tsm_uses_ifrs_tags_and_notes_fallback(tmp_store, fixture_server, monkeypatch):
    _serve(fixture_server, monkeypatch, "TSM")
    out = edgar.pull_edgar(tmp_store, ["TSM"])
    assert "edgar.TSM.net_income" in out and len(out["edgar.TSM.net_income"]) > 0
    assert tmp_store.get_meta("edgar.TSM.note") is not None   # no debt tag: notes the gap


def test_annual_only_series_trailing_4q_is_the_latest_annual():
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-04-10", "2025-04-17"]),
            "period_end": pd.to_datetime(["2023-12-31", "2024-12-31"]),
            "value": [800.0, 900.0],
            "kind": ["annual", "annual"],
        }
    )
    assert edgar.trailing_4q(df, date(2025, 6, 1)) == 900.0
    assert edgar.trailing_4q(df, date(2025, 1, 1)) == 800.0
