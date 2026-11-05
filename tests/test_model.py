import numpy as np
import pandas as pd
import pytest

from lantern import config, model


def _z(**kw):
    base = {k: 0.0 for k in config.WEIGHTS}
    base.update(kw)
    return pd.Series(base)


def test_contributions_sum_to_probability_minus_baseline():
    z = _z(valuation=2.4, capex=1.9, concentration=1.5, leverage=1.2, positioning=1.1, revisions=-0.4, rates=0.3)
    a, b = -1.2, 1.1
    c = model.composite(z)
    contrib = model.contributions(z, a, b)
    assert contrib.sum() == pytest.approx(model.probability(c, a, b) - model.probability(0.0, a, b), abs=1e-9)
    assert contrib["valuation"] > contrib["concentration"] > 0 and contrib["capex"] == 0 and contrib["revisions"] == 0  # watch drivers carry no weight


def test_composite_on_frame_and_nan_is_neutral():
    idx = pd.period_range("2024-01", "2024-03", freq="M").to_timestamp("M")
    z = pd.DataFrame({k: [1.0, np.nan, -1.0] for k in config.WEIGHTS}, index=idx)
    c = model.composite(z)
    assert c.iloc[0] == pytest.approx(1.0) and c.iloc[1] == pytest.approx(0.0) and c.iloc[2] == pytest.approx(-1.0)


def test_fit_logistic_recovers_parameters():
    rng = np.random.default_rng(0)
    c = pd.Series(rng.normal(0, 1, 2000))
    p = 1 / (1 + np.exp(-(-1.0 + 1.5 * c)))
    labels = pd.Series((rng.random(2000) < p).astype(int))
    a, b = model.fit_logistic(c, labels)
    assert abs(a + 1.0) < 0.2 and abs(b - 1.5) < 0.25


def test_fit_logistic_never_returns_a_negative_slope():
    """Two episodes cannot be allowed to invert the model: more risk must never mean a lower probability."""
    rng = np.random.default_rng(1)
    c = pd.Series(rng.normal(0, 1, 400))
    p = 1 / (1 + np.exp(-(-2.0 - 1.5 * c)))  # the data say the opposite of the model's premise
    labels = pd.Series((rng.random(400) < p).astype(int))
    a, b = model.fit_logistic(c, labels)
    assert b == 0.0 and abs(a - np.log(labels.mean() / (1 - labels.mean()))) < 0.3


def test_fit_logistic_prior_pulls_a_weak_slope_toward_one():
    c = pd.Series(np.linspace(-1, 1, 50))
    labels = pd.Series([0] * 25 + [1] * 25)  # perfectly separable: an unpenalised fit would run off to infinity
    a, b = model.fit_logistic(c, labels)
    assert 0.5 < b < 5.0


def test_status_bands_and_clamp():
    assert model.status(0.1) == "calm" and model.status(0.41) == "elevated" and model.status(0.7) == "high"
    assert model.probability(50, 0, 1) == 0.99 and model.probability(-50, 0, 1) == 0.01


def test_trigger_effect_sign_and_distance():
    z = _z()
    readings = _z()
    readings["concentration"] = 0.36
    stats = {k: (0.0, 1.0) for k in config.WEIGHTS}
    stats["concentration"] = (0.25, 0.05)
    eff = model.trigger_effects(z, readings, stats, a=-1.0, b=1.0)
    assert [e["id"] for e in eff] == ["valuation", "concentration", "leverage", "capex"]
    conc = next(e for e in eff if e["id"] == "concentration")
    assert conc["effect_pts"] > 0 and conc["level"] == 0.40 and conc["tier"] == "calibrated"
    assert conc["distance"] == pytest.approx((0.36 - 0.25) / (0.40 - 0.25))
    capex = next(e for e in eff if e["id"] == "capex")
    assert capex["effect_pts"] == 0 and capex["tier"] == "watch"  # a watch indicator cannot change the call


def test_composite_ignores_watch_drivers():
    assert model.composite(_z(capex=4.0, rates=4.0, positioning=4.0, revisions=4.0)) == pytest.approx(0.0)
    assert model.composite(_z(valuation=1.0, concentration=1.0, leverage=1.0)) == pytest.approx(1.0)


def test_fair_value_adjusts_for_real_yield():
    assert model.fair_value(10, 20, 2.0, 2.0) == pytest.approx(200)
    assert model.fair_value(10, 20, 3.0, 2.0) == pytest.approx(180)
    assert model.fair_value(10, 20, 30.0, 2.0) == pytest.approx(100)  # floored at half the median multiple
    assert model.fv_gap(168.0, 137.0) == pytest.approx(168 / 137 - 1)
    lo, hi = model.fv_range(168.0, 137.0)
    assert lo < model.fv_gap(168.0, 137.0) < hi


def test_conditional_window_widens_when_sparse():
    hist = pd.DataFrame({"composite": np.linspace(-2, 2, 100), "fwd_12m_return": np.linspace(-0.4, 0.4, 100)})
    r, band = model.conditional_returns(hist, c_today=5.0)
    assert len(r) >= 24 and band > 1.0
    r2, band2 = model.conditional_returns(hist, c_today=0.0)
    assert band2 == 1.0 and (hist["composite"].between(-1, 1).sum()) == len(r2)


def test_fan_and_scenarios_are_consistent():
    returns = pd.Series(np.linspace(-0.5, 0.5, 101))
    f = model.fan(168.0, returns)
    assert f["p50"][0] == 168.0 and len(f["p50"]) == 13
    assert f["p10"][-1] < f["p25"][-1] < f["p50"][-1] < f["p75"][-1] < f["p90"][-1]
    paths = model.scenario_paths(168.0, f["p50"])
    assert paths["derating"][-1] == pytest.approx(126.0) and paths["meltup"][-1] == pytest.approx(201.6)
    assert paths["base"] == f["p50"]
    probs = model.scenario_probs(0.41, returns)
    assert abs(sum(probs.values()) - 1) < 1e-9 and probs["derating"] == pytest.approx(0.41)
    assert probs["meltup"] == pytest.approx(float((returns >= 0.20).mean()) / (0.41 + float((returns >= 0.20).mean()) + max(0.0, 1 - 0.41 - float((returns >= 0.20).mean()))))
    assert model.conditional_drawdown_share(returns) == pytest.approx(float((returns <= -0.25).mean()))
