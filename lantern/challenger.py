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
