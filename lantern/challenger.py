"""Champion-challenger fan: TimesFM 2.5 zero-shot quantile forecasts of the same series our fan
covers. The 2.5 quantile layout is (horizon, 10): index 0 the mean, indices 1..9 the 10th..90th
percentiles, so p10 = [:, 1], median = [:, 5], p90 = [:, 9].

The 3.0 checkpoint is NOT used: its weights are non-commercial-only. The 2.5 weights are Apache-2.0;
the checkpoint id lives in config so a licensed 3.0 can be swapped in later."""

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
