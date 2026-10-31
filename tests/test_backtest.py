import pandas as pd

from lantern import backtest


def test_drawdown_labels_and_forward_returns():
    idx = pd.period_range("2020-01", periods=14, freq="M").to_timestamp("M")
    p = pd.Series([100, 110, 70, 80, 90, 120, 125, 130, 135, 140, 145, 150, 155, 160], index=idx, dtype=float)
    lab = backtest.drawdown_labels(p, horizon=3, threshold=0.25)
    assert lab.iloc[0] == 1 and lab.iloc[3] == 0 and lab.iloc[-3:].isna().all()
    fwd = backtest.forward_returns(p, horizon=3)
    assert fwd.iloc[0] == 80 / 100 - 1 and fwd.iloc[-3:].isna().all()


def test_run_backtest_fits_and_scores(tmp_store, seeded_all_series):
    res = backtest.run_backtest(tmp_store, "2010-01")
    assert res.n_months > 100 and 0 <= res.brier <= 0.25 and len(res.calibration) == 5
    assert 0 <= res.hit_rate <= 1 and isinstance(res.a, float) and isinstance(res.b, float)
    assert set(res.history.columns) >= {"composite", "probability", "label", "fwd_12m_return"}
    meta = tmp_store.get_meta("calibration")
    assert meta is not None and meta["n_months"] == res.n_months and meta["start"] == "2010-01"
    assert tmp_store.load_series("backtest.history") is not None
    assert res.analogue_2000["drivers"] == ["valuation", "rates"] and 0 < res.analogue_2000["probability_peak"] < 1
    assert res.analogue_2000["date_peak"].startswith(("1998", "1999", "2000", "2001"))
    rows = backtest.ledger_rows(res)
    assert rows and rows[0]["kind"] == "backtest" and isinstance(rows[0]["inside_fan"], bool)
    assert rows[0]["horizon_months"] == 12 and set(rows[0]) >= {"date", "probability", "realised_return"}
