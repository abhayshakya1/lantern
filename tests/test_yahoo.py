import json
import os

import pandas as pd
import pytest

from lantern import config
from lantern.sources import yahoo
from tests.conftest import FIXTURES


def test_pull_yahoo_saves_prices_and_snapshots(tmp_store, fake_yahoo):
    out = yahoo.pull_yahoo(tmp_store, ["NVDA", "MSFT"], client=fake_yahoo)
    prices = tmp_store.load_series("prices.NVDA")
    assert prices["value"].iloc[-1] > 0 and list(prices.columns) == ["date", "value"]
    assert len(tmp_store.load_series("yahoo.forward_pe.NVDA")) == 1
    assert set(out) >= {"prices.NVDA", "yahoo.actions.MSFT"}
    assert any(p["name"] == "prices.NVDA" and p["status"] == "ok" for p in tmp_store.provenance())


def test_basket_index_rebased_to_100(tmp_store, fake_yahoo):
    yahoo.pull_yahoo(tmp_store, config.BASKET, client=fake_yahoo)
    idx = yahoo.basket_index(tmp_store, "2024-11")
    assert abs(idx["value"].iloc[0] - 100) < 1e-9 and idx["value"].iloc[-1] > 100
    assert idx["date"].iloc[0].strftime("%Y-%m") == "2024-11"


def test_missing_ticker_marks_error_and_keeps_others(tmp_store, fake_yahoo_missing_msft):
    out = yahoo.pull_yahoo(tmp_store, ["NVDA", "MSFT"], client=fake_yahoo_missing_msft)
    assert "prices.NVDA" in out and "prices.MSFT" not in out
    assert any(p["name"] == "prices.MSFT" and p["status"] == "error" for p in tmp_store.provenance())


@pytest.mark.network
def test_record_fixtures():
    """Writes the Yahoo fixtures from the live API. Run: LANTERN_RECORD=1 pytest -m network -k record"""
    if not os.environ.get("LANTERN_RECORD"):
        pytest.skip("set LANTERN_RECORD=1 to re-record")
    client = yahoo.YFClient()
    rows, info, actions = [], {}, {}
    for t in config.BASKET + config.INDICES:
        h = client.history(t, "2003-01-01")
        monthly = h["Close"].resample("ME").last().dropna()
        rows += [{"ticker": t, "date": d, "close": float(v)} for d, v in monthly.items()]
        if not t.startswith("^"):
            i = client.info(t)
            info[t] = {k: i.get(k) for k in ("forwardPE", "marketCap", "trailingEps")}
            a = client.actions(t)
            actions[t] = [
                {"date": d.strftime("%Y-%m-%d"), "action": str(act)} for d, act in a["Action"].items()
            ][-200:]
    pd.DataFrame(rows).to_parquet(FIXTURES / "yahoo_prices.parquet", index=False)
    (FIXTURES / "yahoo_info.json").write_text(json.dumps(info, indent=1))
    (FIXTURES / "yahoo_actions.json").write_text(json.dumps(actions, indent=1))
    assert (FIXTURES / "yahoo_prices.parquet").stat().st_size < 400_000
