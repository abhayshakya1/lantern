"""Yahoo Finance via yfinance: monthly prices, today's forward P/E and market cap, analyst actions."""

import hashlib
from datetime import UTC, datetime, timedelta

import pandas as pd

from lantern import config
from lantern.sources.base import SourceError
from lantern.store import Store


class YFClient:
    """Thin wrapper so tests can replay recorded data through the same three calls."""

    def history(self, ticker: str, start: str) -> pd.DataFrame:
        import yfinance as yf

        df = yf.Ticker(ticker).history(start=start, auto_adjust=False)[["Close", "Stock Splits"]]
        df.index = pd.DatetimeIndex(df.index).tz_localize(None)
        return df

    def info(self, ticker: str) -> dict:
        import yfinance as yf

        try:
            return dict(yf.Ticker(ticker).info or {})
        except Exception:  # Yahoo's info endpoint is flaky; the snapshot is context only
            return {}

    def actions(self, ticker: str) -> pd.DataFrame:
        import yfinance as yf

        df = yf.Ticker(ticker).upgrades_downgrades
        if df is None or df.empty:
            return pd.DataFrame({"Action": []}, index=pd.DatetimeIndex([]))
        df = df[["Action"]].copy()
        df.index = pd.DatetimeIndex(df.index).tz_localize(None)
        return df


def _snapshot(value, day) -> pd.DataFrame:
    return pd.DataFrame({"date": [day], "value": [float(value)]})


def _record(store: Store, name: str, ticker: str, df: pd.DataFrame, status: str, now: datetime):
    sha = hashlib.sha256(df.to_csv(index=False).encode()).hexdigest() if status == "ok" else ""
    store.record_fetch(name, f"https://finance.yahoo.com/quote/{ticker}", sha, "", status, now)


def pull_yahoo(
    store: Store,
    tickers: list[str] = config.BASKET + config.INDICES,
    *,
    client=None,
    start: str = "2003-01-01",
) -> dict[str, pd.DataFrame]:
    client = client or YFClient()
    now = datetime.now(UTC)
    today = pd.Timestamp(now.date())
    out: dict[str, pd.DataFrame] = {}
    last_dates = []
    for t in tickers:
        name = f"prices.{t}"
        try:
            h = client.history(t, start)
            if h is None or h.empty:
                raise SourceError(name, "no price history")
            monthly = h["Close"].resample("ME").last().dropna()
            df = pd.DataFrame({"date": monthly.index, "value": monthly.to_numpy(dtype=float)})
            splits = h["Stock Splits"][h["Stock Splits"] > 0] if "Stock Splits" in h else pd.Series(dtype=float)
        except Exception as exc:  # one bad ticker never stops the pull
            _record(store, name, t, pd.DataFrame(), "error", now)
            continue
        store.save_series(name, df)
        _record(store, name, t, df, "ok", now)
        out[name] = df
        last_dates.append(h.index.max())
        if len(splits):  # share counts filed before a split are restated in today's share units (see edgar.shares_history)
            sdf = pd.DataFrame({"date": splits.index, "value": splits.to_numpy(dtype=float)})
            store.save_series(f"yahoo.splits.{t}", sdf)
            out[f"yahoo.splits.{t}"] = sdf
        if t.startswith("^"):
            continue
        info = client.info(t) or {}
        for key, series in (("forwardPE", "forward_pe"), ("marketCap", "market_cap"), ("trailingEps", "trailing_eps")):
            if info.get(key) is not None:
                snap = _snapshot(info[key], today)
                store.save_series(f"yahoo.{series}.{t}", snap)
                out[f"yahoo.{series}.{t}"] = snap
        acts = client.actions(t)
        cutoff = today - timedelta(days=90)
        recent = acts[acts.index >= cutoff] if len(acts) else acts
        signs = recent["Action"].map({"up": 1.0, "down": -1.0}).dropna() if len(recent) else pd.Series(dtype=float)
        adf = pd.DataFrame({"date": signs.index, "value": signs.to_numpy(dtype=float)})
        store.save_series(f"yahoo.actions.{t}", adf)
        out[f"yahoo.actions.{t}"] = adf
    if last_dates:
        store.set_meta("yahoo.last_date", pd.Timestamp(max(last_dates)).date().isoformat())
    return out


def basket_index(store: Store, start: str, tickers: list[str] = config.BASKET) -> pd.DataFrame:
    """Equal-weighted monthly index of the basket, each name rebased to 100 at `start` (YYYY-MM)."""
    frames = []
    for t in tickers:
        s = store.load_series(f"prices.{t}")
        if s is None:
            raise SourceError(f"prices.{t}", "missing; run the pull first")
        frames.append(s.set_index("date")["value"].rename(t))
    wide = pd.concat(frames, axis=1).sort_index()
    wide = wide[wide.index >= pd.Timestamp(start)]
    rebased = wide / wide.iloc[0] * 100.0
    return pd.DataFrame({"date": rebased.index, "value": rebased.mean(axis=1).to_numpy()})
