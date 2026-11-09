"""Champion-challenger fan: TimesFM 2.5 zero-shot quantile forecasts of the same series our fan
covers. The 2.5 quantile layout is (horizon, 10): index 0 the mean, indices 1..9 the 10th..90th
percentiles, so p10 = [:, 1], median = [:, 5], p90 = [:, 9].

The 3.0 checkpoint is NOT used: its weights are non-commercial-only. The 2.5 weights are Apache-2.0;
the checkpoint id lives in config so a licensed 3.0 can be swapped in later."""

import json
from datetime import UTC, datetime

import numpy as np

from lantern import config

CHECKPOINT = config.TIMESFM_CHECKPOINT
HORIZON = config.HORIZON_MONTHS


class TimesFMForecaster:
    """Thin adapter: the only place timesfm/torch are imported."""

    def __init__(self, checkpoint: str = CHECKPOINT):
        import timesfm  # heavyweight: imported only when a real forecast is asked for

        self.model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(checkpoint, torch_compile=False)
        self.model.compile(
            timesfm.ForecastConfig(
                max_context=1024,
                max_horizon=256,
                normalize_inputs=True,
                use_continuous_quantile_head=True,
                force_flip_invariance=True,
                infer_is_positive=True,
                fix_quantile_crossing=True,
            )
        )
        self.name = f"TimesFM 2.5 ({checkpoint}), zero-shot"

    def quantiles(self, contexts: list[np.ndarray], horizon: int) -> np.ndarray:
        """(n, horizon, 10): mean then q10..q90, one row per context series."""
        _, q = self.model.forecast(horizon=horizon, inputs=[np.asarray(c, dtype=np.float32) for c in contexts])
        return np.asarray(q)


def fan_from_quantiles(q: np.ndarray, last: float) -> dict | None:
    """A chart-shaped fan ({p10,p50,p90}, horizon+1 points starting at the last observed value)
    from one series' quantile block; None when the quantiles cross despite the model's fix flag."""
    p10, p50, p90 = q[:, 1], q[:, 5], q[:, 9]
    if not (np.all(p10 <= p50) and np.all(p50 <= p90)):
        return None
    return {k: [float(last)] + [float(v) for v in vals] for k, vals in (("p10", p10), ("p50", p50), ("p90", p90))}


def run_challenger(store, forecaster) -> dict:
    """Forecast the latest run's basket window and store the challenger fan in meta."""
    run = store.latest_run()
    if run is None:
        raise RuntimeError("no model run to challenge; run `lantern model` first")
    price = [float(v) for v in run["chart"]["price"] if v is not None]
    q = forecaster.quantiles([np.asarray(price)], HORIZON)[0]
    meta = {
        "fan": fan_from_quantiles(q, price[-1]),
        "model": getattr(forecaster, "name", "timesfm"),
        "context_months": len(price),
        "horizon_months": HORIZON,
        "champion_as_of": run["as_of"],
        "run_at": datetime.now(UTC).isoformat(),
    }
    store.set_meta("challenger", meta)
    return meta


def coverage_backtest(store, forecaster, horizon: int = HORIZON, min_context: int = 24) -> dict:
    """Walk the monthly index forward: for every month with `horizon` months of truth ahead, forecast
    from history up to that month only, and score whether the realised level fell inside p10-p90.
    The champion's coverage comes from the backtest ledger on the same dates."""
    import pandas as pd

    from lantern import backtest

    hist = store.load_series("backtest.history")
    if hist is None or not len(hist):
        raise RuntimeError("no backtest history; run `lantern backtest` first")
    months = pd.DatetimeIndex(pd.to_datetime(hist["date"]))
    ndx = backtest._monthly_index(store, "prices.^NDX", months).dropna()
    vals = ndx.to_numpy(dtype=float)
    dates = ndx.index
    idxs = list(range(min_context - 1, len(vals) - horizon))
    if not idxs:
        raise RuntimeError("not enough monthly history for a walk-forward")
    q = forecaster.quantiles([vals[: i + 1] for i in idxs], horizon)

    ledger_df = store.load_series("backtest.ledger")
    champ_rows = {}
    if ledger_df is not None and len(ledger_df):
        champ_rows = {str(r["date"])[:10]: r for r in json.loads(ledger_df.to_json(orient="records", date_format="iso"))}  # the date column round-trips as a timestamp

    inside, champ = [], []
    for k, i in enumerate(idxs):
        lo, hi = float(q[k, horizon - 1, 1]), float(q[k, horizon - 1, 9])
        inside.append(lo <= float(vals[i + horizon]) <= hi)
        row = champ_rows.get(dates[i].date().isoformat())
        if row is not None and row.get("inside_fan") is not None:
            champ.append(bool(row["inside_fan"]))
    res = {
        "n": len(inside),
        "coverage": float(np.mean(inside)),
        "champion_coverage": float(np.mean(champ)) if champ else None,
        "champion_n": len(champ),
        "band": "p10-p90",
        "target": 0.8,
        "horizon_months": horizon,
        "model": getattr(forecaster, "name", "timesfm"),
        "run_at": datetime.now(UTC).isoformat(),
    }
    store.set_meta("challenger_backtest", res)
    return res


def challenger_prob(store, clf=None, min_train: int = 60) -> dict:
    """The probability challenger: TabPFN predicting the 12-month drawdown label walk-forward from
    the seven driver z-scores, scored by Brier against our own logistic refit on the same window
    each month. Strictly no peeking: month i is predicted from months [0, i) only."""
    import pandas as pd

    from lantern import drivers, model

    bhist = store.load_series("backtest.history")
    if bhist is None or not len(bhist):
        raise RuntimeError("no backtest history; run `lantern backtest` first")
    readings = drivers.monthly_readings(store, config.CALIBRATION_START)
    zdf = drivers.zscores(readings)
    bhist = bhist.copy()
    bhist["date"] = pd.to_datetime(bhist["date"])
    zdf = zdf.reindex(pd.DatetimeIndex(bhist["date"]))  # align month-for-month with the labels
    if clf is None:
        try:
            from tabpfn import TabPFNClassifier
        except ModuleNotFoundError as exc:
            raise RuntimeError("tabpfn is not installed; run `uv sync --extra challenger`") from exc
        clf = TabPFNClassifier()

    zcols = list(zdf.columns)
    z = zdf.to_numpy(dtype=float)
    labels = bhist["label"].to_numpy(dtype=float)
    comp = bhist["composite"].to_numpy(dtype=float)
    n_months = len(labels)

    import numpy as np

    preds_t, preds_c, truth = [], [], []
    for i in range(min_train, n_months):
        if np.isnan(labels[i]):
            continue  # the trailing months whose 12-month outcome is not known yet
        train = [j for j in range(i - 12) if not np.isnan(labels[j])]  # 12-month embargo: a label formed after month i leaks the future
        if len(train) < min_train:
            continue
        X = np.nan_to_num(z[train], nan=0.0)
        y = labels[train].astype(int)
        clf.fit(X, y)
        preds_t.append(float(clf.predict_proba(np.nan_to_num(z[[i]], nan=0.0))[0, 1]))
        a, b = model.fit_logistic(pd.Series(comp[train]), pd.Series(y))
        preds_c.append(model.probability(float(comp[i]), a, b))
        truth.append(labels[i])

    if not preds_t:
        raise RuntimeError("not enough labelled history for a walk-forward")
    t, c, y = np.array(preds_t), np.array(preds_c), np.array(truth)
    cal = store.get_meta("calibration") or {}
    res = {
        "n": len(y),
        "brier_tabpfn": float(np.mean((t - y) ** 2)),
        "brier_champion_wf": float(np.mean((c - y) ** 2)),
        "brier_champion_insample": cal.get("brier"),
        "base_rate": float(np.mean(y)),
        "brier_base_rate": float(np.mean((np.mean(y) - y) ** 2)),
        "model": "TabPFN (tabular foundation model, open v1 weights), walk-forward",
        "features": len(zcols),
        "run_at": datetime.now(UTC).isoformat(),
    }
    store.set_meta("challenger_prob", res)
    return res
