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


class FakeForecaster:
    name = "fake-timesfm"

    def __init__(self):
        self.calls = []

    def quantiles(self, contexts, horizon):
        self.calls.append([len(c) for c in contexts])
        out = np.zeros((len(contexts), horizon, 10))
        for i, c in enumerate(contexts):
            last = float(np.asarray(c)[-1])
            out[i, :, 0] = last
            for j in range(1, 10):
                out[i, :, j] = last * (0.9 + 0.025 * (j - 1))  # q10=0.9x .. q90=1.1x
        return out


def test_run_challenger_stores_a_fan_from_the_latest_run(tmp_store, run_fixture):
    run_fixture["chart"]["price"] = [100.0, 102.0]
    tmp_store.save_run(run_fixture)
    fake = FakeForecaster()
    meta = challenger.run_challenger(tmp_store, fake)
    assert fake.calls == [[2]]
    stored = tmp_store.get_meta("challenger")
    assert stored["fan"]["p10"][0] == 102.0 and stored["model"] == "fake-timesfm" and stored["context_months"] == 2
    assert meta["fan"]["p90"][1] > meta["fan"]["p10"][1]


def test_run_challenger_without_a_run_raises(tmp_store):
    import pytest

    with pytest.raises(RuntimeError, match="no model run"):
        challenger.run_challenger(tmp_store, FakeForecaster())


def test_coverage_walks_forward_without_peeking(tmp_store, seeded_all_series):
    from lantern import backtest

    backtest.run_backtest(tmp_store, "2010-01")
    fake = FakeForecaster()
    res = challenger.coverage_backtest(tmp_store, fake, min_context=24)
    lengths = fake.calls[0]
    assert lengths == sorted(lengths) and lengths[0] == 24  # strictly forward, no future leakage
    assert res["n"] > 50 and 0.0 <= res["coverage"] <= 1.0 and res["band"] == "p10-p90"
    assert res["champion_coverage"] is not None and res["model"] == "fake-timesfm"
    assert tmp_store.get_meta("challenger_backtest")["n"] == res["n"]
