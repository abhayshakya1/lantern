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
    assert contrib["valuation"] > contrib["capex"] > 0 > contrib["revisions"]


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


def test_status_bands_and_clamp():
    assert model.status(0.1) == "calm" and model.status(0.41) == "elevated" and model.status(0.7) == "high"
    assert model.probability(50, 0, 1) == 0.99 and model.probability(-50, 0, 1) == 0.01


def test_trigger_effect_sign_and_distance():
    z = _z()
    readings = _z()
    readings["rates"] = 2.06
    stats = {k: (0.0, 1.0) for k in config.WEIGHTS}
    stats["rates"] = (1.0, 0.5)
    eff = model.trigger_effects(z, readings, stats, a=-1.0, b=1.0)
    assert [e["id"] for e in eff] == ["rates", "revisions", "concentration", "capex"]
    rates = next(e for e in eff if e["id"] == "rates")
    assert rates["effect_pts"] > 0 and 0 <= rates["distance"] <= 1 and rates["level"] == 2.5
    assert rates["distance"] == pytest.approx((2.06 - 1.0) / (2.5 - 1.0))
