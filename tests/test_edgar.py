from datetime import date

import pandas as pd

from lantern.sources import edgar


def _serve(fixture_server, monkeypatch, name):
    monkeypatch.setattr(edgar, "facts_url", lambda cik: f"{fixture_server}/edgar_{name}.json")


def _fact(start, end, filed, val, form="10-Q"):
    row = {"end": end, "filed": filed, "val": val, "form": form, "fy": int(end[:4]), "fp": "Q1"}
    if start:
        row["start"] = start
    return row


def test_series_frame_prefers_the_tag_with_the_latest_period():
    """Broadcom's NetIncomeLoss stops in 2019 while another tag carries on: the current one wins."""
    stale = [_fact("2019-05-06", "2019-08-04", "2019-09-10", 7.0e8)]
    current = [_fact("2026-05-04", "2026-08-02", "2026-09-10", 4.0e9), _fact("2026-02-02", "2026-05-03", "2026-06-10", 3.5e9)]
    facts = {
        "us-gaap": {
            "NetIncomeLoss": {"units": {"USD": stale}},
            "NetIncomeLossAvailableToCommonStockholdersBasic": {"units": {"USD": current}},
        }
    }
    df, unit = edgar._series_frame(facts, "net_income")
    assert unit == "USD" and df["period_end"].max() == pd.Timestamp("2026-08-02")


def test_series_frame_falls_back_to_diluted_shares_when_dei_is_empty():
    """Alphabet and Meta carry no dei share count: the diluted weighted average becomes the instant."""
    facts = {
        "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": []}}},
        "us-gaap": {
            "WeightedAverageNumberOfDilutedSharesOutstanding": {
                "units": {"shares": [_fact("2026-07-01", "2026-09-30", "2026-10-29", 1.22e10), _fact("2026-04-01", "2026-06-30", "2026-07-30", 1.23e10)]}
            }
        },
    }
    df, unit = edgar._series_frame(facts, "shares")
    assert unit == "shares" and list(df["kind"].unique()) == ["instant"]
    assert edgar.latest_value(df, date(2026, 11, 30)) == 1.22e10
    assert edgar.latest_value(df, date(2026, 8, 31)) == 1.23e10


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


def test_shares_history_adjusts_for_splits_and_drops_scale_errors(tmp_store):
    """NVDA's 10:1 split of 2024-06-10: the May 10-Q count is pre-split, the August one post-split;
    ORCL once filed a 4.8e15 cover-page count (a scale error) that must not survive."""
    import pandas as pd
    import pytest

    from lantern.sources import edgar

    sh = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-02-21", "2024-05-29", "2024-08-28", "2024-11-20"]),
            "period_end": pd.to_datetime(["2024-02-16", "2024-05-24", "2024-08-23", "2024-11-15"]),
            "value": [2.47e9, 2.46e9, 24.5e9, 4.8e15],
            "kind": "instant",
        }
    )
    tmp_store.save_series("edgar.NVDA.shares", sh)
    tmp_store.save_series("yahoo.splits.NVDA", pd.DataFrame({"date": pd.to_datetime(["2024-06-10"]), "value": [10.0]}))
    adj = edgar.shares_history(tmp_store, "NVDA")
    assert adj["value"].tolist() == pytest.approx([24.7e9, 24.6e9, 24.5e9])  # pre-split counts in post-split units
    assert list(adj.columns) == ["date", "period_end", "value", "kind"]
    assert edgar.shares_history(tmp_store, "MSFT") is None
