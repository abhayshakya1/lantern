"""SSGA SPY holdings for today's top-10 weight, and a reconstructed concentration history."""

import io
import re

import pandas as pd

from lantern import config
from lantern.sources.base import SourceError, fetch_raw
from lantern.store import Store

SPY_URL = (
    "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/"
    "holdings-daily-us-en-spy.xlsx"
)
_UA = {"User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/128 Safari/537.36"}


def pull_spy(store: Store) -> dict[str, pd.DataFrame]:
    raw = fetch_raw(store, "spy.holdings", SPY_URL, headers=_UA)
    sheet = pd.read_excel(io.BytesIO(raw.content), header=None)
    header_rows = [i for i in range(min(20, len(sheet))) if "Ticker" in [str(x) for x in sheet.iloc[i].tolist()]]
    if not header_rows:
        raise SourceError("spy.holdings", "no Ticker header row in the SSGA workbook")
    df = pd.read_excel(io.BytesIO(raw.content), header=header_rows[0])
    weights = pd.to_numeric(df["Weight"], errors="coerce").dropna()
    top10 = float(weights.nlargest(10).sum() / 100.0)
    as_of = pd.Timestamp(raw.fetched_at.date())
    text = " ".join(str(x) for x in sheet.iloc[:4].to_numpy().ravel())
    m = re.search(r"As of (\d{2}-[A-Za-z]{3}-\d{4})", text)
    if m:
        as_of = pd.Timestamp(pd.to_datetime(m.group(1), format="%d-%b-%Y"))
    out = pd.DataFrame({"date": [as_of], "value": [top10]})
    store.save_series("spy.top10_weight", out)
    return {"spy.top10_weight": out}


def _shares_by_month(sh: pd.DataFrame, months: pd.DatetimeIndex) -> pd.Series:
    """Latest share count filed by each month end (no look-ahead)."""
    known = sh.sort_values("date")[["date", "value"]].copy()
    known["date"] = pd.to_datetime(known["date"]).astype("datetime64[ns]")
    probe = pd.DataFrame({"date": pd.DatetimeIndex(months).astype("datetime64[ns]")})
    merged = pd.merge_asof(probe, known, on="date")
    return pd.Series(merged["value"].to_numpy(), index=months)


def concentration_history(store: Store, start: str = config.CALIBRATION_START) -> pd.DataFrame:
    gspc = store.load_series("prices.^GSPC")
    if gspc is None:
        raise SourceError("prices.^GSPC", "missing; run the pull first")
    months = pd.DatetimeIndex(gspc["date"])
    caps = {}
    for t in config.BASKET + config.LARGE_CAPS:
        p, sh = store.load_series(f"prices.{t}"), store.load_series(f"edgar.{t}.shares")
        if p is None or sh is None or sh.empty:
            continue
        price = p.set_index("date")["value"].reindex(months)
        caps[t] = price * _shares_by_month(sh, months)
    wide = pd.DataFrame(caps, index=months)
    total = pd.Series(gspc["value"].to_numpy(), index=months) * config.SP500_DIVISOR_SHARES
    top10 = wide.apply(lambda row: row.dropna().nlargest(10).sum(), axis=1) / total
    hist = pd.DataFrame({"date": months, "value": top10.to_numpy()})
    hist = hist[hist["date"] >= pd.Timestamp(start)].dropna().reset_index(drop=True)
    today = store.load_series("spy.top10_weight")
    if today is not None and not today.empty and not hist.empty:
        d = pd.Timestamp(today["date"].iloc[0])
        last = hist["date"].iloc[-1]
        if (d.year, d.month) == (last.year, last.month):
            # the reconstruction uses an approximate index share count, so it sits on its own level:
            # rescale the whole history onto the SSGA level, keeping its shape, then pin today's value
            ssga, recon = float(today["value"].iloc[0]), float(hist["value"].iloc[-1])
            if recon > 0:
                hist["value"] = hist["value"] * (ssga / recon)
            hist.loc[hist.index[-1], "value"] = ssga
    store.set_meta(
        "concentration.note",
        f"history reconstructed from {len(caps)} large caps against an approximate S&P 500 share "
        "count; today's value from the SSGA holdings file",
    )
    return hist
