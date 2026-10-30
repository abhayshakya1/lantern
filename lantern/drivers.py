"""Seven monthly driver readings from the stored series, with disclosed proxies, and 10-year z-scores.

Every reading at month m uses only data filed or published by that month end.
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from lantern import config
from lantern.sources import spy
from lantern.sources.edgar import latest_value, trailing_4q
from lantern.store import Store

DRIVER_IDS = list(config.WEIGHTS)


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
    DriverMeta("valuation", "Valuation stretch", "x", "Yahoo prices; EDGAR net income and shares; Shiller S&P P/E before the basket history",
               "Basket trailing P/E: sum of market caps over sum of trailing four-quarter net income; TSM converted from TWD with FRED DEXTAUS",
               1, False, Trigger(None, "below", "Back at the 10-year median P/E the valuation driver goes neutral")),
    DriverMeta("capex", "Capex intensity", "ratio", "EDGAR company facts", "Hyperscaler trailing four-quarter capex over operating cash flow",
               1, False, Trigger(0.55, "below", "Capex falling back under 55% of cash flow flips capex intensity to easing"), True),
    DriverMeta("concentration", "Index concentration", "share", "SSGA SPY holdings; Yahoo prices and EDGAR shares for the history",
               "Top-10 weight in the S&P 500", 1, False, Trigger(0.40, "above", "Past 40% the concentration driver saturates"), True),
    DriverMeta("leverage", "Leverage and credit", "z", "EDGAR cash and debt; FRED high-yield spread",
               "Average of the standardised 12-month change in hyperscaler net debt and the standardised high-yield spread, spread inverted",
               1, True, None),
    DriverMeta("positioning", "Positioning and sentiment", "fraction", "AAII sentiment survey",
               "Bull minus bear share, monthly mean (CBOE put/call dropped: no free history)", 1, False, None),
    DriverMeta("revisions", "Earnings revisions", "growth", "Shiller S&P trailing earnings; Yahoo analyst actions shown as context",
               "Three-month change in trailing S&P earnings, inverted", 1, False,
               Trigger(0.0, "above", "Trailing earnings turning down adds to the probability"), True),
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


def _valuation(store: Store, months: pd.DatetimeIndex, splices: dict) -> pd.Series:
    prices = {t: _monthly(store, f"prices.{t}", months, "last") for t in config.BASKET}
    facts = {t: (store.load_series(f"edgar.{t}.net_income"), store.load_series(f"edgar.{t}.shares")) for t in config.BASKET}
    fx = _monthly(store, "fred.DEXTAUS", months)
    units = {t: store.get_meta(f"edgar.{t}.unit") for t in config.BASKET}
    out = []
    for m in months:
        caps, ni, ok = 0.0, 0.0, True
        for t in config.BASKET:
            inc, sh = facts[t]
            price = prices[t].get(m)
            if inc is None or sh is None or inc.empty or sh.empty or pd.isna(price):
                ok = False
                break
            earn, shares = trailing_4q(inc, m.date()), latest_value(sh, m.date())
            if earn is None or shares is None:
                ok = False
                break
            if units[t] == "TWD":
                rate = fx.get(m)
                if pd.isna(rate):
                    ok = False
                    break
                earn = earn / rate
            caps += price * shares
            ni += earn
        out.append(caps / ni if ok and ni > 0 else np.nan)
    pe = pd.Series(out, index=months, dtype=float)
    proxy = _monthly(store, "shiller.pe", months)
    first = pe.first_valid_index()
    if first is not None and pd.notna(proxy.get(first)) and proxy.get(first) != 0:
        ratio = pe[first] / proxy[first]
        pe[pe.index < first] = proxy[proxy.index < first] * ratio
        splices["valuation"] = first.date().isoformat()
    elif first is None:
        pe = proxy
        splices["valuation"] = "proxy only"
    return pe


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
    readings = pd.DataFrame(index=months, columns=DRIVER_IDS, dtype=float)
    readings["valuation"] = _valuation(store, months, splices)
    readings["capex"] = _hyperscaler_ratio(store, months, "capex", "ocf")
    try:
        conc = spy.concentration_history(store, start)
        readings["concentration"] = conc.set_index("date")["value"].reindex(months)
    except Exception:
        readings["concentration"] = np.nan
    nd = _net_debt(store, months)
    dnd = nd - nd.shift(12)
    hy = _monthly(store, "fred.BAMLH0A0HYM2", months)
    readings["leverage"] = 0.5 * _rolling_z(dnd, config.Z_WINDOW_MONTHS, config.Z_MIN_MONTHS) - 0.5 * _rolling_z(hy, config.Z_WINDOW_MONTHS, config.Z_MIN_MONTHS)
    readings["positioning"] = _monthly(store, "aaii.bull_bear", months)
    earn = _monthly(store, "shiller.earnings", months)
    readings["revisions"] = -(earn / earn.shift(3) - 1)
    readings["rates"] = _monthly(store, "fred.DFII10", months)
    # each driver's last published value carries forward into the current month (at most 3 months),
    # and the driver panel discloses the as-of date of the data behind it
    asof = {c: (readings[c].last_valid_index().date().isoformat() if readings[c].last_valid_index() is not None else None) for c in DRIVER_IDS}
    readings = readings.ffill(limit=3)
    readings.attrs["splices"] = splices
    readings.attrs["asof"] = asof
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
