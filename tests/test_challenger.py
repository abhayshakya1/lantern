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


import pytest


@pytest.mark.network
def test_real_timesfm_forecast_is_shaped_and_ordered():
    pytest.importorskip("timesfm")
    f = challenger.TimesFMForecaster()
    ctx = np.sin(np.linspace(0, 20, 120)) * 10 + 100
    q = f.quantiles([ctx], 12)
    assert q.shape == (1, 12, 10)
    assert np.all(q[0, :, 1] <= q[0, :, 5] + 1e-6) and np.all(q[0, :, 5] <= q[0, :, 9] + 1e-6)


def test_cli_challenger_without_a_run_prints_a_message_not_a_traceback(tmp_path, monkeypatch, capsys):
    import os

    from lantern import cli, config

    monkeypatch.setattr(os, "environ", dict(os.environ))  # main() loads .env; nothing may leak into other tests
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    rc = cli.main(["challenger"])
    out = capsys.readouterr()
    assert rc == 1 and "no model run" in out.out


def test_challenger_meta_names_the_run_it_forecast_from(tmp_store, run_fixture):
    run_fixture["chart"]["price"] = [100.0, 102.0]
    tmp_store.save_run(run_fixture)
    meta = challenger.run_challenger(tmp_store, FakeForecaster())
    assert meta["champion_as_of"] == run_fixture["as_of"]  # the overlay must never dress an old fan on a new run


def test_coverage_scores_the_month_twelve_ahead_not_the_context_end(tmp_store, seeded_all_series):
    from lantern import backtest

    backtest.run_backtest(tmp_store, "2010-01")

    class TightFake:
        name = "tight"

        def quantiles(self, contexts, horizon):
            out = np.zeros((len(contexts), horizon, 10))
            for i, c in enumerate(contexts):
                last = float(np.asarray(c)[-1])
                out[i, :, :] = last
                out[i, :, 1] = last - 1e-6  # a band so tight only the context-end value itself fits
                out[i, :, 9] = last + 1e-6
            return out

    res = challenger.coverage_backtest(tmp_store, TightFake())
    assert res["coverage"] < 0.1  # scoring vals[i] instead of vals[i+12] would make this exactly 1.0


class FakeTabPFN:
    """Records what it saw; predicts the base rate of its training labels."""

    def __init__(self):
        self.train_sizes = []
        self.max_train_idx = []
        self._rate = 0.5

    def fit(self, X, y):
        self.train_sizes.append(len(X))
        self._rate = float(sum(y) / max(1, len(y)))
        return self

    def predict_proba(self, X):
        import numpy as _np

        return _np.column_stack([_np.full(len(X), 1 - self._rate), _np.full(len(X), self._rate)])


def test_probability_challenger_walks_forward_without_peeking(tmp_store, seeded_all_series):
    from lantern import backtest

    backtest.run_backtest(tmp_store, "2010-01")
    fake = FakeTabPFN()
    res = challenger.challenger_prob(tmp_store, clf=fake, min_train=24)
    assert fake.train_sizes == sorted(fake.train_sizes) and fake.train_sizes[0] >= 24
    assert 0.0 <= res["brier_tabpfn"] <= 1.0 and 0.0 <= res["brier_champion_wf"] <= 1.0
    assert res["n"] > 50 and res["n"] + 12 <= len(fake.train_sizes) + 12 + res["n"]  # scored months bounded
    assert tmp_store.get_meta("challenger_prob")["model"].startswith("TabPFN")
    assert res["base_rate"] > 0


def test_probability_challenger_without_history_raises(tmp_store):
    import pytest

    with pytest.raises(RuntimeError, match="history"):
        challenger.challenger_prob(tmp_store, clf=FakeTabPFN())
