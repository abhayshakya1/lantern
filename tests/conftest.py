import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pandas as pd
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_path(name: str) -> Path:
    return FIXTURES / name


@pytest.fixture
def tmp_store(tmp_path):
    from lantern.store import Store

    return Store(tmp_path)


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="session")
def fixture_server():
    """Serve tests/fixtures over HTTP on a free local port; yields the base URL."""
    handler = functools.partial(_QuietHandler, directory=str(FIXTURES))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


class FakeYahoo:
    """Replays the recorded Yahoo fixtures through the client interface pull_yahoo expects."""

    def __init__(self):
        self.prices = pd.read_parquet(FIXTURES / "yahoo_prices.parquet")
        self.infos = json.loads((FIXTURES / "yahoo_info.json").read_text())
        self.acts = json.loads((FIXTURES / "yahoo_actions.json").read_text())

    def history(self, ticker, start):
        p = self.prices[self.prices["ticker"] == ticker]
        if p.empty:
            raise ValueError(f"no data for {ticker}")
        p = p[p["date"] >= pd.Timestamp(start)]
        return pd.DataFrame({"Close": p["close"].to_numpy()}, index=pd.DatetimeIndex(p["date"]))

    def info(self, ticker):
        return self.infos.get(ticker, {})

    def actions(self, ticker):
        rows = self.acts.get(ticker, [])
        idx = pd.DatetimeIndex([r["date"] for r in rows])
        return pd.DataFrame({"Action": [r["action"] for r in rows]}, index=idx)


@pytest.fixture
def fake_yahoo():
    return FakeYahoo()


@pytest.fixture
def seeded_prices_and_shares(tmp_store):
    """Synthetic monthly prices for the basket, the large caps and the indices, plus EDGAR share counts."""
    import numpy as np

    from lantern import config

    months = pd.period_range("2023-01", "2026-10", freq="M").to_timestamp("M")
    rng = np.random.default_rng(1)
    for i, t in enumerate(config.BASKET + config.LARGE_CAPS):
        level = 100 + 20 * i
        path = level * np.cumprod(1 + rng.normal(0.01, 0.04, len(months)))
        tmp_store.save_series(f"prices.{t}", pd.DataFrame({"date": months, "value": path}))
        shares = 1e9 + 2e8 * (i % 5)
        tmp_store.save_series(
            f"edgar.{t}.shares",
            pd.DataFrame(
                {
                    "date": pd.to_datetime(["2023-02-01", "2025-02-01"]),
                    "period_end": pd.to_datetime(["2023-01-15", "2025-01-15"]),
                    "value": [shares, shares * 0.98],
                    "kind": ["instant", "instant"],
                }
            ),
        )
    tmp_store.save_series("prices.^GSPC", pd.DataFrame({"date": months, "value": np.linspace(4000, 6500, len(months))}))
    tmp_store.save_series("prices.^NDX", pd.DataFrame({"date": months, "value": np.linspace(12000, 24000, len(months))}))
    return {"months": months, "last_month_end": months[-1]}


@pytest.fixture
def fake_yahoo_missing_msft():
    class Missing(FakeYahoo):
        def history(self, ticker, start):
            if ticker == "MSFT":
                raise ConnectionError("MSFT unavailable")
            return super().history(ticker, start)

    return Missing()
