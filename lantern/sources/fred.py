"""FRED series: the official API when FRED_API_KEY is set (free key), else the public CSV endpoint.

FRED's edge drops plain Python TLS connections to the CSV endpoint, so the API key is the reliable path.
The key travels as a query parameter and never enters the provenance log.
"""

import io
import json
import os

import pandas as pd

from lantern import config
from lantern.sources.base import fetch_raw
from lantern.store import Store

API_URL = "https://api.stlouisfed.org/fred/series/observations"


def fred_url(series_id: str) -> str:
    return f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


def api_url() -> str:
    return API_URL


def api_key() -> str | None:
    return os.environ.get("FRED_API_KEY") or None


def pull_fred(store: Store, ids: dict[str, str] = config.FRED) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    key = api_key()
    for sid in ids.values():
        name = f"fred.{sid}"
        if key:
            raw = fetch_raw(
                store,
                name,
                api_url(),
                params={"series_id": sid, "api_key": key, "file_type": "json", "observation_start": "1990-01-01"},
            )
            obs = json.loads(raw.content)["observations"]
            df = pd.DataFrame(
                {"date": pd.to_datetime([o["date"] for o in obs]), "value": pd.to_numeric([o["value"] for o in obs], errors="coerce")}
            )
        else:
            raw = fetch_raw(store, name, fred_url(sid))
            df = pd.read_csv(io.BytesIO(raw.content), na_values=["."])
            df.columns = ["date", "value"]
            df["date"] = pd.to_datetime(df["date"])
        df = df.dropna(subset=["value"]).reset_index(drop=True)
        store.save_series(name, df)
        out[name] = df
    return out
