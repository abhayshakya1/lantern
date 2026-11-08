import numpy as np

from lantern import challenger


def _quantiles(horizon=12, q10=90.0, med=100.0, q90=110.0):
    """2.5 layout: index 0 = mean, 1..9 = q10..q90."""
    q = np.zeros((horizon, 10))
    q[:, 0] = med
    for i in range(1, 10):
        q[:, i] = q10 + (q90 - q10) * (i - 1) / 8
    return q


def test_fan_maps_the_2p5_quantile_indices_and_starts_at_last_price():
    fan = challenger.fan_from_quantiles(_quantiles(), last=100.0)
    assert list(map(len, (fan["p10"], fan["p50"], fan["p90"]))) == [13, 13, 13]
    assert fan["p10"][0] == fan["p50"][0] == fan["p90"][0] == 100.0
    assert fan["p10"][1] == 90.0 and fan["p50"][1] == 100.0 and fan["p90"][1] == 110.0


def test_crossed_quantiles_are_dropped_not_drawn():
    q = _quantiles(q10=110.0, q90=90.0)  # p10 above p90: a fan that lies
    assert challenger.fan_from_quantiles(q, last=100.0) is None
