"""AAII weekly investor sentiment: bull minus bear spread, as a fraction."""

import io

import pandas as pd

from lantern.sources.base import SourceError, fetch_raw
from lantern.store import Store

AAII_URL = "https://www.aaii.com/files/surveys/sentiment.xls"
_UA = {"User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/128 Safari/537.36"}


def pull_sentiment(store: Store) -> dict[str, pd.DataFrame]:
    raw = fetch_raw(store, "aaii.sentiment", AAII_URL, headers=_UA)
    sheet = pd.read_excel(io.BytesIO(raw.content), sheet_name="SENTIMENT", header=None, engine="calamine")
    header_rows = [i for i in range(min(12, len(sheet))) if str(sheet.iloc[i, 0]).strip() == "Date"]
    if not header_rows:
        raise SourceError("aaii.sentiment", "no Date header row in the AAII workbook")
    hdr = header_rows[0]
    cols = [str(c).strip() for c in sheet.iloc[hdr].tolist()]
    data = sheet.iloc[hdr + 1 :].copy()
    data.columns = cols
    dates = pd.to_datetime(data["Date"], errors="coerce")
    spread = pd.to_numeric(data["Bullish"], errors="coerce") - pd.to_numeric(data["Bearish"], errors="coerce")
    df = pd.DataFrame({"date": dates, "value": spread}).dropna().sort_values("date").reset_index(drop=True)
    store.save_series("aaii.bull_bear", df)
    return {"aaii.bull_bear": df}
