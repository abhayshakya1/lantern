"""The transparent de-rating model: composite, logistic probability, contributions and triggers."""

import math

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from lantern import config
from lantern.drivers import META, SHOWN_TRIGGERS


def composite(z, weights: dict[str, float] = config.COMPOSITE_WEIGHTS):
    """Weighted sum of the calibrated drivers' z-scores; a missing z counts as neutral (0), watch drivers weigh 0."""
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
    """Penalised maximum-likelihood fit of P = 1 / (1 + exp(-(a + b*c))).

    The slope is floored at zero (more risk can never lower the probability) and carries a weak
    normal prior around one, so two historical episodes can neither invert the model nor send
    the slope to infinity on separable data. Rows with a NaN on either side are dropped.
    """
    df = pd.DataFrame({"c": c.to_numpy(dtype=float), "y": labels.to_numpy(dtype=float)}).dropna()
    x, y = df["c"].to_numpy(), df["y"].to_numpy()
    prior_mean, prior_sd = config.SLOPE_PRIOR

    def objective(params):
        a, b = params
        logit = a + b * x
        nll = float(np.sum(np.logaddexp(0.0, -logit) * y + np.logaddexp(0.0, logit) * (1 - y)))
        return nll + 0.5 * ((b - prior_mean) / prior_sd) ** 2

    res = minimize(objective, x0=np.array([0.0, 1.0]), method="L-BFGS-B", bounds=[(None, None), (0.0, None)])
    return float(res.x[0]), float(res.x[1])


def status(p: float) -> str:
    for threshold, name in config.STATUS_BANDS:
        if p < threshold:
            return name
    return config.STATUS_BANDS[-1][1]


def contributions(z_row: pd.Series, a: float, b: float, weights: dict[str, float] = config.COMPOSITE_WEIGHTS) -> pd.Series:
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
    weights: dict[str, float] = config.COMPOSITE_WEIGHTS,
) -> list[dict]:
    """For each shown trigger: the probability change if that driver sat at its trigger level today (0 for a watch driver)."""
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
                "tier": "calibrated" if weights.get(did, 0.0) > 0 else "watch",
                "current": current,
                "level": float(level),
                "direction": trig.direction,
                "distance": float(distance),
                "effect_pts": float(effect * 100.0),
                "text": trig.text,
            }
        )
    return out


# --- fair value, forecast fan and scenarios -------------------------------------------------


def fair_value(
    ttm_earnings: float,
    median_pe: float,
    real_yield: float,
    median_real_yield: float,
    k: float = config.REAL_YIELD_PE_SENSITIVITY,
) -> float:
    """Trailing earnings times the 10-year median multiple, trimmed k per point of real yield above its median."""
    adjusted = median_pe * (1.0 - k * (real_yield - median_real_yield))
    return ttm_earnings * max(adjusted, 0.5 * median_pe)


def fv_gap(price: float, fv: float) -> float:
    return price / fv - 1.0


def fv_range(price: float, fv: float, band: float = config.FV_BAND) -> tuple[float, float]:
    return price / (fv * (1.0 + band)) - 1.0, price / (fv * (1.0 - band)) - 1.0


def conditional_returns(
    history: pd.DataFrame,
    c_today: float,
    band: float = config.CONDITIONAL_BAND,
    min_obs: int = config.CONDITIONAL_MIN_OBS,
) -> tuple[pd.Series, float]:
    """12-month forward returns from months whose composite sat within `band` of today's; widens until min_obs."""
    while True:
        sel = history.loc[(history["composite"] - c_today).abs() <= band, "fwd_12m_return"].dropna()
        if len(sel) >= min_obs or band >= 10.0:
            return sel.reset_index(drop=True), float(band)
        band += 1.0


def fan(price: float, returns: pd.Series, months: int = config.HORIZON_MONTHS) -> dict[str, list[float]]:
    out = {}
    for name, q in (("p10", 0.10), ("p25", 0.25), ("p50", 0.50), ("p75", 0.75), ("p90", 0.90)):
        r = float(returns.quantile(q))
        out[name] = [price * (1.0 + r) ** (m / months) for m in range(months + 1)]
    return out


def scenario_paths(price: float, p50: list[float]) -> dict[str, list[float]]:
    months = len(p50) - 1
    return {
        "base": list(p50),
        "derating": [price * (1.0 - config.DRAWDOWN) ** (m / months) for m in range(months + 1)],
        "meltup": [price * (1.0 + config.MELTUP) ** (m / months) for m in range(months + 1)],
    }


def scenario_probs(p_derating: float, returns: pd.Series) -> dict[str, float]:
    meltup = float((returns >= config.MELTUP).mean()) if len(returns) else 0.0
    base = max(0.0, 1.0 - p_derating - meltup)
    total = p_derating + meltup + base
    return {"base": base / total, "derating": p_derating / total, "meltup": meltup / total}


def conditional_drawdown_share(returns: pd.Series) -> float:
    return float((returns <= -config.DRAWDOWN).mean()) if len(returns) else 0.0
