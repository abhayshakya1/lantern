from datetime import date

import numpy as np
import pandas as pd
import pytest

from lantern import config, drivers


def test_zscore_sign_and_window():
    idx = pd.period_range("2010-01", "2026-10", freq="M").to_timestamp("M")
    df = pd.DataFrame({"valuation": np.linspace(10, 40, len(idx))}, index=idx)
    z = drivers.zscores(df, window=120)
    assert z["valuation"].iloc[-1] > 1.0
    assert z["valuation"].isna().sum() == 23  # the first 23 months lack the 24 observations a z needs


def test_prestandardised_driver_passes_through():
    idx = pd.period_range("2020-01", "2026-10", freq="M").to_timestamp("M")
    df = pd.DataFrame({"leverage": np.linspace(-2, 2, len(idx))}, index=idx)
    z = drivers.zscores(df)
    assert np.allclose(z["leverage"].to_numpy(), df["leverage"].to_numpy())


def test_driver_ids_match_weights_and_four_triggers_shown():
    assert [d.id for d in drivers.DRIVERS] == list(config.WEIGHTS)
    assert drivers.SHOWN_TRIGGERS == ["rates", "revisions", "concentration", "capex"]
    assert all(drivers.META[i].trigger is not None and drivers.META[i].shown_trigger for i in drivers.SHOWN_TRIGGERS)


def test_readings_use_no_lookahead(tmp_store, seeded_all_series):
    r = drivers.monthly_readings(tmp_store, "2025-01", end=date(2025, 7, 31))
    # the fixture files the quarter ending 30 Jun 2025 on 5 Aug 2025: July must not see it
    assert r.loc["2025-07-31", "capex"] == pytest.approx(seeded_all_series["capex_through_1q25"], rel=1e-6)
    assert r.index[-1] == pd.Timestamp("2025-07-31")


def test_proxy_splice_recorded_and_no_nan_on_latest(tmp_store, seeded_all_series):
    r = drivers.monthly_readings(tmp_store, "2003-01")
    assert "valuation" in r.attrs["splices"]
    assert list(r.columns) == list(config.WEIGHTS)
    assert r.iloc[-1].notna().all()  # the current month carries each driver's last published value
    assert r.attrs["asof"]["revisions"] == "2026-10-31"  # ... and says how old that value is
    z = drivers.zscores(r)
    assert z.iloc[-1].notna().all()
    readings_row, z_row = drivers.latest(tmp_store)
    assert readings_row.name == r.index[-1] and set(z_row.index) == set(config.WEIGHTS)


def test_window_stats_cover_every_driver(tmp_store, seeded_all_series):
    r = drivers.monthly_readings(tmp_store, "2008-01")
    stats = drivers.window_stats(r)
    assert set(stats) == set(config.WEIGHTS) and all(s[1] > 0 for s in stats.values())
