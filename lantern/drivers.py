"""Seven monthly driver readings from the stored series, with disclosed proxies, and 10-year z-scores.

Every reading at month m uses only data filed or published by that month end.
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from lantern import config
from lantern.sources import spy
from lantern.sources.edgar import latest_value, shares_history, trailing_4q
from lantern.store import Store

DRIVER_IDS = list(config.WEIGHTS)
MIN_BASKET_NAMES = 6  # the basket P/E and earnings need at least six of the seven US filers


@dataclass(frozen=True)
class Trigger:
    level: float | None  # None = the driver's 10-year window mean
    direction: str  # "above" | "below"
    text: str


@dataclass(frozen=True)
class DriverMeta:
    id: str
    label: str
    unit: str
    source: str
    transform: str
    sign: int
    prestandardised: bool
    trigger: Trigger | None
    shown_trigger: bool = False


DRIVERS = [
    DriverMeta("valuation", "Valuation stretch", "x", "Yahoo prices and splits; EDGAR net income and shares; Shiller S&P P/E before the basket history",
               "Basket trailing P/E: sum of market caps over sum of trailing four-quarter net income, seven names (TSM excluded: annual 20-F facts only, in TWD)",
               1, False, Trigger(None, "below", "Back at the 10-year median P/E the valuation driver goes neutral")),
    DriverMeta("capex", "Capex intensity", "ratio", "EDGAR company facts", "Hyperscaler trailing four-quarter capex over operating cash flow",
               1, False, Trigger(0.55, "below", "Capex falling back under 55% of cash flow flips capex intensity to easing"), True),
    DriverMeta("concentration", "Index concentration", "share", "SSGA SPY holdings; Yahoo prices and splits with EDGAR shares for the history",
               "Top-10 weight in the S&P 500", 1, False, Trigger(0.40, "above", "Past 40% the concentration driver saturates"), True),
    DriverMeta("leverage", "Leverage and credit", "z", "EDGAR cash and debt; FRED high-yield spread",
               "Average of the standardised 12-month change in hyperscaler net debt and the standardised high-yield spread, spread inverted",
               1, True, None),
    DriverMeta("positioning", "Positioning and sentiment", "fraction", "AAII sentiment survey",
               "Bull minus bear share, monthly mean (CBOE put/call dropped: no free history)", 1, False, None),
    DriverMeta("revisions", "Earnings momentum", "growth", "EDGAR net income for the basket; Shiller S&P earnings before the basket history; Yahoo analyst actions as context",
               "Three-month change in the basket's trailing four-quarter net income, inverted", 1, False,
               Trigger(0.0, "above", "Basket earnings turning down adds to the probability"), True),
    DriverMeta("rates", "Rates and liquidity", "%", "FRED DFII10", "US 10-year real yield, monthly mean", 1, False,
               Trigger(2.50, "above", "Above 2.50% the real yield adds to the probability"), True),
]
META = {d.id: d for d in DRIVERS}
SHOWN_TRIGGERS = ["rates", "revisions", "concentration", "capex"]


def _month_ends(start: str, end: date | None) -> pd.DatetimeIndex:
    last = pd.Timestamp(end) if end else pd.Timestamp.today().normalize() + pd.offsets.MonthEnd(0)
    return pd.period_range(start, last.strftime("%Y-%m"), freq="M").to_timestamp("M")


def _monthly(store: Store, name: str, months: pd.DatetimeIndex, how: str = "mean") -> pd.Series:
    df = store.load_series(name)
    if df is None or df.empty:
        return pd.Series(np.nan, index=months)
    s = df.set_index("date")["value"].sort_index()
    m = s.resample("ME").mean() if how == "mean" else s.resample("ME").last()
    return m.reindex(months)


def _rolling_z(x: pd.Series, window: int, min_months: int) -> pd.Series:
    mu = x.rolling(window, min_periods=min_months).mean()
    sd = x.rolling(window, min_periods=min_months).std()
    return (x - mu) / sd.replace(0, np.nan)


def _basket(store: Store, months: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series]:
    """Per month: the basket's market cap and trailing four-quarter net income (USD), both from filings known by then."""
    names = [t for t in config.BASKET if t not in config.PE_EXCLUDED]
    prices = {t: _monthly(store, f"prices.{t}", months, "last") for t in names}
    facts = {t: (store.load_series(f"edgar.{t}.net_income"), shares_history(store, t)) for t in names}
    caps, earns = [], []
    for m in months:
        cap, ni, n_cap, n_earn = 0.0, 0.0, 0, 0
        for t in names:
            inc, sh = facts[t]
            if inc is None or sh is None or inc.empty or sh.empty:
                continue
            earn, shares = trailing_4q(inc, m.date()), latest_value(sh, m.date())
            if earn is None or shares is None:
                continue
            ni, n_earn = ni + earn, n_earn + 1
            price = prices[t].get(m)
            if pd.notna(price):
                cap, n_cap = cap + price * shares, n_cap + 1
        earns.append(ni if n_earn >= MIN_BASKET_NAMES and ni > 0 else np.nan)
        caps.append(cap if n_cap >= MIN_BASKET_NAMES and n_cap == n_earn else np.nan)
    return pd.Series(caps, index=months, dtype=float), pd.Series(earns, index=months, dtype=float)


def _splice(series: pd.Series, proxy: pd.Series, splices: dict, key: str) -> pd.Series:
    """Scale the proxy to the series at its first valid month and use it before that month."""
    first = series.first_valid_index()
    if first is None:
        splices[key] = "proxy only"
        return proxy
    if pd.notna(proxy.get(first)) and proxy.get(first) != 0:
        ratio = series[first] / proxy[first]
        series = series.copy()
        series[series.index < first] = proxy[proxy.index < first] * ratio
        splices[key] = first.date().isoformat()
    return series


def _hyperscaler_ratio(store: Store, months: pd.DatetimeIndex, num: str, den: str, min_names: int = 3) -> pd.Series:
    frames = {t: (store.load_series(f"edgar.{t}.{num}"), store.load_series(f"edgar.{t}.{den}")) for t in config.HYPERSCALERS}
    out = []
    for m in months:
        a, b, n = 0.0, 0.0, 0
        for t, (fn, fd) in frames.items():
            if fn is None or fd is None or fn.empty or fd.empty:
                continue
            x, y = trailing_4q(fn, m.date()), trailing_4q(fd, m.date())
            if x is None or y is None:
                continue
            a, b, n = a + x, b + y, n + 1
        out.append(a / b if n >= min_names and b > 0 else np.nan)
    return pd.Series(out, index=months, dtype=float)


def _net_debt(store: Store, months: pd.DatetimeIndex, min_names: int = 3) -> pd.Series:
    frames = {t: (store.load_series(f"edgar.{t}.debt"), store.load_series(f"edgar.{t}.cash")) for t in config.HYPERSCALERS}
    out = []
    for m in months:
        nd, n = 0.0, 0
        for t, (fd, fc) in frames.items():
            if fd is None or fc is None or fd.empty or fc.empty:
                continue
            d, c = latest_value(fd, m.date()), latest_value(fc, m.date())
            if d is None or c is None:
                continue
            nd, n = nd + d - c, n + 1
        out.append(nd if n >= min_names else np.nan)
    return pd.Series(out, index=months, dtype=float)


def monthly_readings(store: Store, start: str = config.CALIBRATION_START, end: date | None = None) -> pd.DataFrame:
    months = _month_ends(start, end)
    splices: dict[str, str] = {}
    notes: dict = {}
    readings = pd.DataFrame(index=months, columns=DRIVER_IDS, dtype=float)

    caps, earns = _basket(store, months)
    readings["valuation"] = _splice(caps / earns, _monthly(store, "shiller.pe", months), splices, "valuation")
    shiller_earn = _monthly(store, "shiller.earnings", months)
    momentum = -(earns / earns.shift(3) - 1.0)
    proxy_momentum = -(shiller_earn / shiller_earn.shift(3) - 1.0)
    readings["revisions"] = _splice(momentum, proxy_momentum, splices, "revisions") if momentum.notna().any() else proxy_momentum
    if not momentum.notna().any():
        splices["revisions"] = "proxy only"

    readings["capex"] = _hyperscaler_ratio(store, months, "capex", "ocf")
    try:
        conc = spy.concentration_history(store, start)
        readings["concentration"] = conc.set_index("date")["value"].reindex(months)
    except Exception as exc:
        notes["concentration_error"] = str(exc)
        readings["concentration"] = np.nan
    nd = _net_debt(store, months)
    dnd = nd - nd.shift(12)
    hy = _monthly(store, "fred.BAMLH0A0HYM2", months)
    readings["leverage"] = 0.5 * _rolling_z(dnd, config.Z_WINDOW_MONTHS, config.Z_MIN_MONTHS) - 0.5 * _rolling_z(hy, config.Z_WINDOW_MONTHS, config.Z_MIN_MONTHS)
    readings["positioning"] = _monthly(store, "aaii.bull_bear", months)
    readings["rates"] = _monthly(store, "fred.DFII10", months)

    # each driver's last published value carries forward into the current month (at most 3 months),
    # and the driver panel discloses the as-of date of the data behind it
    today = pd.Timestamp(end) if end else pd.Timestamp.today().normalize()  # a month in progress is as of the run date, not its month end
    asof = {c: (min(readings[c].last_valid_index(), today).date().isoformat() if readings[c].last_valid_index() is not None else None) for c in DRIVER_IDS}
    readings = readings.ffill(limit=3)
    driver_notes = {
        "valuation": f"{len(config.BASKET) - len(config.PE_EXCLUDED)} of {len(config.BASKET)} names; {', '.join(config.PE_EXCLUDED)} excluded: annual 20-F facts only, reported in TWD",
        "concentration": store.get_meta("concentration.note"),
    }
    fred_for = {"rates": "fred.DFII10", "leverage": "fred.BAMLH0A0HYM2"}
    for c in DRIVER_IDS:
        if pd.isna(readings[c].iloc[-1]):
            s = store.load_series(fred_for[c]) if c in fred_for else None
            why = "FRED series missing: pull with FRED_API_KEY set" if c in fred_for and (s is None or s.empty) else "no data for this month"
            driver_notes[c] = f"no reading: neutral (0σ) in the composite; {why}"
    readings.attrs["splices"] = splices
    readings.attrs["asof"] = asof
    readings.attrs["notes"] = notes
    readings.attrs["driver_notes"] = driver_notes
    readings.attrs["gaps"] = {c: int(readings[c].isna().sum()) for c in DRIVER_IDS}
    return readings


def zscores(readings: pd.DataFrame, window: int = config.Z_WINDOW_MONTHS, min_months: int = config.Z_MIN_MONTHS) -> pd.DataFrame:
    z = pd.DataFrame(index=readings.index)
    for col in readings.columns:
        meta = META.get(col)
        if meta is not None and meta.prestandardised:
            z[col] = readings[col]
        else:
            z[col] = _rolling_z(readings[col], window, min_months) * (meta.sign if meta else 1)
    return z


def window_stats(readings: pd.DataFrame, window: int = config.Z_WINDOW_MONTHS) -> dict[str, tuple[float, float]]:
    """(mean, std) of each driver over the trailing window ending at the last month."""
    tail = readings.tail(window)
    return {c: (float(tail[c].mean()), float(tail[c].std())) for c in readings.columns}


def latest(store: Store) -> tuple[pd.Series, pd.Series]:
    readings = monthly_readings(store)
    z = zscores(readings)
    return readings.iloc[-1], z.iloc[-1]
