"""FRED series as CSV (no API key needed)."""

import io

import pandas as pd

from lantern import config
from lantern.sources.base import fetch_raw
from lantern.store import Store


def fred_url(series_id: str) -> str:
    return f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


def pull_fred(store: Store, ids: dict[str, str] = config.FRED) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for sid in ids.values():
        name = f"fred.{sid}"
        raw = fetch_raw(store, name, fred_url(sid))
        df = pd.read_csv(io.BytesIO(raw.content), na_values=["."])
        df.columns = ["date", "value"]
        df["date"] = pd.to_datetime(df["date"])
        df = df.dropna(subset=["value"]).reset_index(drop=True)
        store.save_series(name, df)
        out[name] = df
    return out
