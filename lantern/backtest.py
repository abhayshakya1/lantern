"""Monthly backtest of the composite against realised Nasdaq-100 drawdowns; calibration and ledger seed."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from lantern import config, drivers, model
from lantern.store import Store


@dataclass
class BacktestResult:
    a: float
    b: float
    hit_rate: float
    brier: float
    n_months: int
    calibration: list[dict]
    history: pd.DataFrame
    analogue_2000: dict = field(default_factory=dict)
    start: str = config.CALIBRATION_START
    end: str = ""


def forward_returns(prices: pd.Series, horizon: int = config.HORIZON_MONTHS) -> pd.Series:
    return prices.shift(-horizon) / prices - 1.0


def drawdown_labels(prices: pd.Series, horizon: int = config.HORIZON_MONTHS, threshold: float = config.DRAWDOWN) -> pd.Series:
    """1 when the lowest close in the next `horizon` months sits `threshold` or more below this month's."""
    lows = pd.concat([prices.shift(-k) for k in range(1, horizon + 1)], axis=1).min(axis=1)
    lab = (lows / prices - 1.0 <= -threshold).astype(float)
    lab.iloc[-horizon:] = np.nan
    return lab


def _monthly_index(store: Store, name: str, months: pd.DatetimeIndex) -> pd.Series:
    df = store.load_series(name)
    s = df.set_index("date")["value"].sort_index().resample("ME").last()
    return s.reindex(months)


def _calibration_table(p: pd.Series, y: pd.Series, bins: int = 5) -> list[dict]:
    edges = np.linspace(0, 1, bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (p >= lo) & (p < hi) if hi < 1 else (p >= lo) & (p <= hi)
        n = int(sel.sum())
        out.append(
            {
                "bucket": f"{lo:.1f}-{hi:.1f}",
                "predicted": float(p[sel].mean()) if n else None,
                "observed": float(y[sel].mean()) if n else None,
                "n": n,
            }
        )
    return out


def _analogue_2000(store: Store, a: float, b: float) -> dict:
    """The 2000 episode re-scored with only the two drivers whose free history reaches 1990."""
    months = pd.period_range("1990-01", "2003-12", freq="M").to_timestamp("M")
    pe = _monthly_index(store, "shiller.pe", months)
    rate = _monthly_index(store, "shiller.long_rate", months)
    readings = pd.DataFrame({"valuation": pe, "rates": rate}, index=months)
    z = drivers.zscores(readings)
    w = {"valuation": config.WEIGHTS["valuation"], "rates": config.WEIGHTS["rates"]}
    total = sum(w.values())
    w = {k: v / total for k, v in w.items()}
    c = model.composite(z, w)
    p = c.apply(lambda v: model.probability(float(v), a, b))
    p = p[p.index.year.isin([1998, 1999, 2000, 2001])]
    peak = p.idxmax()
    return {
        "drivers": ["valuation", "rates"],
        "probability_peak": float(p.max()),
        "date_peak": peak.date().isoformat(),
        "note": "valuation and the long rate only, weights renormalised; out of sample",
    }


def run_backtest(store: Store, start: str = config.CALIBRATION_START) -> BacktestResult:
    readings = drivers.monthly_readings(store, start)
    z = drivers.zscores(readings)
    c = model.composite(z)
    ndx = _monthly_index(store, "prices.^NDX", readings.index)
    labels = drawdown_labels(ndx)
    fwd = forward_returns(ndx)
    a, b = model.fit_logistic(c, labels)
    p = c.apply(lambda v: model.probability(float(v), a, b))
    history = pd.DataFrame({"composite": c, "probability": p, "label": labels, "fwd_12m_return": fwd}, index=readings.index)
    scored = history.dropna(subset=["label"])
    hit_rate = float(((scored["probability"] >= 0.5).astype(float) == scored["label"]).mean())
    brier = float(((scored["probability"] - scored["label"]) ** 2).mean())
    brier_base = float(((scored["label"].mean() - scored["label"]) ** 2).mean())  # what always predicting the base rate scores
    res = BacktestResult(
        a=a,
        b=b,
        hit_rate=hit_rate,
        brier=brier,
        n_months=int(len(scored)),
        calibration=_calibration_table(scored["probability"], scored["label"]),
        history=history,
        start=start,
        end=readings.index[-1].strftime("%Y-%m"),
    )
    try:
        res.analogue_2000 = _analogue_2000(store, a, b)
    except Exception as exc:  # the long history may be absent on a partial pull
        res.analogue_2000 = {"drivers": ["valuation", "rates"], "error": str(exc)}
    out = history.reset_index().rename(columns={"index": "date"})
    store.save_series("backtest.history", out)
    store.save_series("backtest.ledger", pd.DataFrame(ledger_rows(res)))  # the accuracy ledger's seed
    store.set_meta(
        "calibration",
        {"a": a, "b": b, "hit_rate": hit_rate, "brier": brier, "brier_base": brier_base, "in_sample": True,
         "n_months": res.n_months, "start": start, "end": res.end,
         "calibration": res.calibration, "analogue_2000": res.analogue_2000},
    )
    return res


def ledger_rows(result: BacktestResult) -> list[dict]:
    """One row per scored month: the forecast, what the index then did, and whether it stayed inside the fan."""
    h = result.history.dropna(subset=["label", "fwd_12m_return"])
    rows = []
    for date, row in h.iterrows():
        sel, _ = model.conditional_returns(result.history, float(row["composite"]))
        lo, hi = (float(sel.quantile(0.10)), float(sel.quantile(0.90))) if len(sel) else (np.nan, np.nan)
        rows.append(
            {
                "date": date.date().isoformat(),
                "probability": float(row["probability"]),
                "horizon_months": config.HORIZON_MONTHS,
                "realised_return": float(row["fwd_12m_return"]),
                "drawdown": bool(row["label"] == 1),
                "inside_fan": bool(lo <= row["fwd_12m_return"] <= hi) if not np.isnan(lo) else False,
                "kind": "backtest",
            }
        )
    return rows
