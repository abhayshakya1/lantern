"""Shiller monthly S&P data: trailing P/E and the long rate, from 1871."""

import io

import numpy as np
import pandas as pd

from lantern.sources.base import SourceError, fetch_raw
from lantern.store import Store

# shillerdata.com's current file; the Yale copy stops in 2023.
SHILLER_URL = "https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/downloads/ie_data.xls"
_UA = {"User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/128 Safari/537.36"}


def pull_shiller(store: Store) -> dict[str, pd.DataFrame]:
    raw = fetch_raw(store, "shiller.ie_data", SHILLER_URL, headers=_UA)
    sheet = pd.read_excel(io.BytesIO(raw.content), sheet_name="Data", header=None, engine="calamine")
    header_rows = [i for i in range(min(15, len(sheet))) if str(sheet.iloc[i, 0]).strip() == "Date"]
    if not header_rows:
        raise SourceError("shiller.ie_data", "no Date header row in the Shiller workbook")
    data = sheet.iloc[header_rows[0] + 1 :]
    frac = pd.to_numeric(data.iloc[:, 5], errors="coerce")  # year fraction, e.g. 1871.0417 = January
    price = pd.to_numeric(data.iloc[:, 1], errors="coerce")
    earnings = pd.to_numeric(data.iloc[:, 3], errors="coerce")
    gs10 = pd.to_numeric(data.iloc[:, 6], errors="coerce")
    keep = frac.notna()
    year = np.floor(frac[keep]).astype(int)
    month = np.clip(np.round((frac[keep] - year) * 12 + 0.5).astype(int), 1, 12)
    dates = pd.to_datetime(pd.DataFrame({"year": year, "month": month, "day": 1})) + pd.offsets.MonthEnd(0)
    pe = pd.DataFrame({"date": dates.to_numpy(), "value": (price[keep] / earnings[keep]).to_numpy()}).dropna()
    rate = pd.DataFrame({"date": dates.to_numpy(), "value": gs10[keep].to_numpy()}).dropna()
    earn = pd.DataFrame({"date": dates.to_numpy(), "value": earnings[keep].to_numpy()}).dropna()
    out = {
        "shiller.pe": pe.reset_index(drop=True),
        "shiller.long_rate": rate.reset_index(drop=True),
        "shiller.earnings": earn.reset_index(drop=True),
    }
    for name, df in out.items():
        store.save_series(name, df)
    return out
