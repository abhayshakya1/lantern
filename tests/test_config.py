import pytest

from lantern import config


def test_weights_sum_to_one_and_cover_seven_drivers():
    assert set(config.WEIGHTS) == {
        "valuation",
        "capex",
        "concentration",
        "leverage",
        "positioning",
        "revisions",
        "rates",
    }
    assert abs(sum(config.WEIGHTS.values()) - 1.0) < 1e-9
    assert config.WEIGHTS["valuation"] == 0.25 and config.WEIGHTS["rates"] == 0.05


def test_composite_weights_cover_the_calibrated_drivers_only():
    assert config.CALIBRATED == ["valuation", "concentration", "leverage"]
    w = config.COMPOSITE_WEIGHTS
    assert set(w) == set(config.WEIGHTS) and abs(sum(w.values()) - 1.0) < 1e-9
    assert all(w[k] == 0.0 for k in config.WEIGHTS if k not in config.CALIBRATED)
    assert w["valuation"] == pytest.approx(0.25 / 0.55) and w["concentration"] == pytest.approx(0.15 / 0.55)


def test_basket_and_ciks():
    assert len(config.BASKET) == 8 and config.CIK["TSM"] == 1046179
    assert set(config.HYPERSCALERS) < set(config.BASKET)
