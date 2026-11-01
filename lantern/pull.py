"""Morning pull orchestration, the live-or-cached badge, and the model run that builds the monitor payload."""

import math
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from lantern import backtest, config, drivers, model
from lantern.sources import edgar, fred, sentiment, shiller, spy, yahoo
from lantern.store import Store


def pull_yahoo_all(store: Store) -> dict:
    return yahoo.pull_yahoo(store, config.BASKET + config.LARGE_CAPS + config.INDICES)


def pull_edgar_all(store: Store) -> dict:
    return edgar.pull_edgar(store, config.BASKET + config.LARGE_CAPS)


def default_sources() -> list:
    return [fred.pull_fred, pull_yahoo_all, pull_edgar_all, spy.pull_spy, sentiment.pull_sentiment, shiller.pull_shiller]


@dataclass
class PullStatus:
    items: list[dict]
    started_at: datetime
    finished_at: datetime


def run_pull(store: Store, sources: list | None = None) -> PullStatus:
    """Runs every source in its own try; the previous good pull stands unless all sources succeed."""
    started = datetime.now(UTC)
    items = []
    for fn in sources or default_sources():
        name = getattr(fn, "__name__", str(fn))
        try:
            out = fn(store)
            items.append({"source": name, "status": "ok", "series": len(out), "detail": ""})
        except Exception as exc:  # one dead feed must not blank the screen
            items.append({"source": name, "status": "error", "series": 0, "detail": str(exc)})
    finished = datetime.now(UTC)
    missing = [i["source"] for i in items if i["status"] != "ok"]
    record = {"at": finished.isoformat(), "ok": not missing, "missing": missing, "items": items}
    store.set_meta("last_pull_attempt", record)
    if len(missing) < len(items):  # at least one feed refreshed: the data's age moved
        store.set_meta("last_pull", record)
    return PullStatus(items=items, started_at=started, finished_at=finished)


def badge(store: Store, now: datetime | None = None) -> dict:
    rec = store.get_meta("last_pull")
    if not rec:
        return {"state": "none", "pulled_at": None, "label": "No data pulled yet"}
    at = datetime.fromisoformat(rec["at"]).astimezone(config.SGT)
    now_sgt = (now or datetime.now(UTC)).astimezone(config.SGT)
    missing = rec.get("missing") or []
    suffix = f" · {len(missing)} feed{'s' if len(missing) > 1 else ''} missing" if missing else ""
    if at.date() == now_sgt.date():
        return {"state": "live", "pulled_at": at.isoformat(), "label": f"Live data · pulled {at:%H:%M} SGT{suffix}", "missing": missing}
    return {"state": "cached", "pulled_at": at.isoformat(), "label": f"Cached data · pulled {at:%d %b}{suffix}", "missing": missing}


# --- model run ------------------------------------------------------------------------------


def _clean(obj):
    """JSON-safe: numpy scalars to Python, NaN to None, Timestamps to ISO dates."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return None if math.isnan(float(obj)) or math.isinf(float(obj)) else float(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.date().isoformat()
    return obj


def _tail(series: pd.Series, n: int = 24) -> list:
    return [None if pd.isna(v) else float(v) for v in series.tail(n).to_numpy()]


def _reading_text(did: str, value: float, median_pe: float) -> str:
    if value is None or pd.isna(value):
        return "no reading"
    return {
        "valuation": f"Trailing P/E {value:.1f}x; 10-year median {median_pe:.1f}x",
        "capex": f"Hyperscaler capex {value:.0%} of operating cash flow",
        "concentration": f"Top-10 weight {value:.1%} of the S&P 500",
        "leverage": f"Net-debt and credit-spread composite {value:+.1f}σ",
        "positioning": f"AAII bull-bear spread {value:+.0%}",
        "revisions": f"Trailing S&P earnings {-value:+.1%} over three months",
        "rates": f"US 10-year real yield {value:.2f}%",
    }[did]


def _snapshot_mean(store: Store, prefix: str) -> float | None:
    vals = []
    for t in config.BASKET:
        df = store.load_series(f"{prefix}.{t}")
        if df is not None and not df.empty and pd.notna(df["value"].iloc[-1]):
            vals.append(float(df["value"].iloc[-1]))
    return float(np.mean(vals)) if vals else None


def run_model(store: Store, now: datetime | None = None) -> dict:
    now_sgt = (now or datetime.now(UTC)).astimezone(config.SGT)
    cal = store.get_meta("calibration")
    if not cal:
        backtest.run_backtest(store)
        cal = store.get_meta("calibration")
    a, b = float(cal["a"]), float(cal["b"])

    readings = drivers.monthly_readings(store)
    z = drivers.zscores(readings)
    comp = model.composite(z)
    probs = comp.apply(lambda v: model.probability(float(v), a, b))
    r_row, z_row = readings.iloc[-1], z.iloc[-1]
    p, p_prev = float(probs.iloc[-1]), float(probs.iloc[-2])
    stats = drivers.window_stats(readings)
    contrib = model.contributions(z_row, a, b)

    # fair value from the valuation and rates readings: FV multiple = median P/E adjusted for the real yield
    window = config.Z_WINDOW_MONTHS
    pe_med = readings["valuation"].rolling(window, min_periods=config.Z_MIN_MONTHS).median()
    ry_med = readings["rates"].rolling(window, min_periods=config.Z_MIN_MONTHS).median()
    # without a real-yield reading (FRED missing) the multiple is the plain 10-year median, disclosed in the model block
    rates_known = readings["rates"].notna().any()
    adj = pd.Series(
        [model.fair_value(1.0, m, r if rates_known and pd.notna(r) else rm if pd.notna(rm) else 0.0, rm if pd.notna(rm) else 0.0) if pd.notna(m) else np.nan
         for m, r, rm in zip(pe_med, readings["rates"], ry_med)],
        index=readings.index,
    )
    gap = readings["valuation"] / adj - 1.0
    gap_today = float(gap.iloc[-1])
    lo, hi = model.fv_range(1.0 + gap_today, 1.0)

    # chart: 25 months of history, 12 of forecast
    hist_months = readings.index[-25:]
    idx = yahoo.basket_index(store, hist_months[0].strftime("%Y-%m")).set_index("date")["value"]
    price = idx.resample("ME").last().reindex(hist_months).ffill()
    price_today = float(price.iloc[-1])
    fv_hist = (price / (1.0 + gap.reindex(hist_months))).ffill()
    growth = float(fv_hist.iloc[-1] / fv_hist.iloc[-13] - 1.0) if len(fv_hist) >= 13 and fv_hist.iloc[-13] > 0 else 0.0
    growth = min(max(growth, -0.2), 0.3)
    fv_fore = [float(fv_hist.iloc[-1]) * (1.0 + growth) ** (k / 12) for k in range(1, 13)]
    fair_value = [float(v) for v in fv_hist.to_numpy()] + fv_fore
    history = store.load_series("backtest.history")
    sel, band = model.conditional_returns(history, float(comp.iloc[-1]))
    fan = model.fan(price_today, sel)
    paths = model.scenario_paths(price_today, fan["p50"])
    sp = model.scenario_probs(p, sel)
    forecast_months = pd.period_range(hist_months[-1] + pd.offsets.MonthEnd(1), periods=12, freq="M").to_timestamp("M")
    months = [m.strftime("%b %y") for m in list(hist_months) + list(forecast_months)]

    drivers_out = []
    for d in drivers.DRIVERS:
        drivers_out.append(
            {
                "id": d.id,
                "label": d.label,
                "unit": d.unit,
                "weight": config.WEIGHTS[d.id],
                "reading": float(r_row[d.id]) if pd.notna(r_row[d.id]) else None,
                "reading_text": _reading_text(d.id, r_row[d.id], float(pe_med.iloc[-1])),
                "z": float(z_row[d.id]) if pd.notna(z_row[d.id]) else 0.0,
                "contribution_pts": float(contrib[d.id] * 100.0),
                "spark": _tail(z[d.id]),
                "change_1m_z": float(z_row[d.id] - z[d.id].iloc[-2]) if pd.notna(z_row[d.id]) and pd.notna(z[d.id].iloc[-2]) else 0.0,
                "asof": readings.attrs["asof"].get(d.id),
                "source": d.source,
                "transform": d.transform,
            }
        )
    drivers_out.sort(key=lambda x: -x["contribution_pts"])
    top = [x["label"].lower() for x in drivers_out[:2]]

    note = {
        "date": now_sgt.isoformat(),
        "title": "Model run complete",
        "text": f"12-month de-rating probability {p:.0%}, from {p_prev:.0%} last month. {top[0].capitalize()} and {top[1]} are the largest contributors.",
    }
    notes = [note] + (store.get_meta("notes") or [])[:9]
    store.set_meta("notes", notes)

    capex_2024 = readings["capex"].get(pd.Timestamp("2024-12-31"))
    payload = {
        "as_of": now_sgt.isoformat(),
        "model": {
            "version": config.MODEL_VERSION,
            "run_at": now_sgt.isoformat(),
            "calibration": {k: cal.get(k) for k in ("a", "b", "hit_rate", "brier", "n_months", "start", "end")},
            "window_band": band,
            "conditional_obs": int(len(sel)),
            "conditional_drawdown_share": model.conditional_drawdown_share(sel),
            "splices": readings.attrs.get("splices", {}),
            "fair_value_note": "real-yield adjustment applied" if rates_known else "no real-yield data: multiple is the plain 10-year median",
        },
        "basket": {"tickers": config.BASKET, "index_base": hist_months[0].strftime("%b %Y")},
        "tiles": {
            "probability": {"value": p, "delta_1m": p - p_prev, "status": model.status(p), "spark": _tail(probs)},
            "fv_gap": {"value": gap_today, "low": lo, "high": hi, "spark": _tail(gap)},
            "forward_pe": {"value": _snapshot_mean(store, "yahoo.forward_pe"), "trailing_pe": float(r_row["valuation"]),
                           "median_10y": float(pe_med.iloc[-1]), "spark": _tail(readings["valuation"])},
            "capex_ocf": {"value": float(r_row["capex"]), "delta_vs_2024": (float(r_row["capex"] - capex_2024) if capex_2024 is not None and pd.notna(capex_2024) else None),
                          "spark": _tail(readings["capex"])},
            "top10": {"value": float(r_row["concentration"]), "peak_2000": config.TOP10_PEAK_2000, "spark": _tail(readings["concentration"])},
        },
        "chart": {
            "months": months,
            "price": [float(v) for v in price.to_numpy()],
            "fair_value": fair_value,
            "fv_band": {"low": [v * (1 - config.FV_BAND) for v in fair_value], "high": [v * (1 + config.FV_BAND) for v in fair_value]},
            "fan": fan,
            "scenarios": {k: {"path": paths[k], "end_return": paths[k][-1] / price_today - 1.0, "prob": sp[k]} for k in ("base", "derating", "meltup")},
            "window_band": band,
            "source_line": f"Source: Yahoo Finance prices to {hist_months[-1]:%d %b %Y}, SEC EDGAR filings, FRED, SSGA, AAII, Shiller · model run {now_sgt:%d %b %Y %H:%M} SGT",
        },
        "triggers": model.trigger_effects(z_row, r_row, stats, a, b),
        "drivers": drivers_out,
        "notes": notes[:3],
    }
    payload = _clean(payload)
    store.save_run(payload)
    return payload
