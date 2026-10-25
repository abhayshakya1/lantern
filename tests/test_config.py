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


def test_basket_and_ciks():
    assert len(config.BASKET) == 8 and config.CIK["TSM"] == 1046179
    assert set(config.HYPERSCALERS) < set(config.BASKET)
