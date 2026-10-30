"""The transparent de-rating model: composite, logistic probability, contributions and triggers."""

import math

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from lantern import config
from lantern.drivers import META, SHOWN_TRIGGERS


def composite(z, weights: dict[str, float] = config.WEIGHTS):
    """Weighted sum of driver z-scores; a missing z counts as neutral (0)."""
    if isinstance(z, pd.DataFrame):
        total = pd.Series(0.0, index=z.index)
        for k, w in weights.items():
            total = total + z[k].fillna(0.0) * w
        return total
    return float(sum((0.0 if pd.isna(z.get(k, 0.0)) else float(z.get(k, 0.0))) * w for k, w in weights.items()))


def probability(c: float, a: float, b: float) -> float:
    p = 1.0 / (1.0 + math.exp(-(a + b * c)))
    lo, hi = config.PROB_CLAMP
    return min(max(p, lo), hi)


def fit_logistic(c: pd.Series, labels: pd.Series) -> tuple[float, float]:
    """Maximum-likelihood fit of P = 1 / (1 + exp(-(a + b*c))); rows with a NaN on either side are dropped."""
    df = pd.DataFrame({"c": c.to_numpy(dtype=float), "y": labels.to_numpy(dtype=float)}).dropna()
    x, y = df["c"].to_numpy(), df["y"].to_numpy()

    def nll(params):
        a, b = params
        logit = a + b * x
        return float(np.sum(np.logaddexp(0.0, -logit) * y + np.logaddexp(0.0, logit) * (1 - y)))

    res = minimize(nll, x0=np.array([0.0, 1.0]), method="L-BFGS-B")
    return float(res.x[0]), float(res.x[1])


def status(p: float) -> str:
    for threshold, name in config.STATUS_BANDS:
        if p < threshold:
            return name
    return config.STATUS_BANDS[-1][1]


def contributions(z_row: pd.Series, a: float, b: float, weights: dict[str, float] = config.WEIGHTS) -> pd.Series:
    """Each driver's share of P(c) - P(0), allocated in proportion to its weighted z; sums exactly."""
    c = composite(z_row, weights)
    gap = probability(c, a, b) - probability(0.0, a, b)
    if abs(c) < 1e-9:
        return pd.Series({k: 0.0 for k in weights})
    parts = {k: (0.0 if pd.isna(z_row.get(k, 0.0)) else float(z_row.get(k, 0.0))) * w for k, w in weights.items()}
    return pd.Series({k: gap * v / c for k, v in parts.items()})


def trigger_effects(
    z_row: pd.Series,
    readings_row: pd.Series,
    stats: dict[str, tuple[float, float]],
    a: float,
    b: float,
    weights: dict[str, float] = config.WEIGHTS,
) -> list[dict]:
    """For each shown trigger: the probability change if that driver sat at its trigger level today."""
    base_p = probability(composite(z_row, weights), a, b)
    out = []
    for did in SHOWN_TRIGGERS:
        meta, trig = META[did], META[did].trigger
        mean, std = stats[did]
        level = mean if trig.level is None else trig.level
        z_level = (level - mean) / std * meta.sign if std and not meta.prestandardised else level
        z2 = z_row.copy()
        z2[did] = z_level
        effect = probability(composite(z2, weights), a, b) - base_p
        current = float(readings_row[did])
        distance = 1.0 if level == mean else min(max((current - mean) / (level - mean), 0.0), 1.0)
        out.append(
            {
                "id": did,
                "label": meta.label,
                "unit": meta.unit,
                "current": current,
                "level": float(level),
                "direction": trig.direction,
                "distance": float(distance),
                "effect_pts": float(effect * 100.0),
                "text": trig.text,
            }
        )
    return out
