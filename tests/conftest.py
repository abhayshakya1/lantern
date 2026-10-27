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
def fake_yahoo_missing_msft():
    class Missing(FakeYahoo):
        def history(self, ticker, start):
            if ticker == "MSFT":
                raise ConnectionError("MSFT unavailable")
            return super().history(ticker, start)

    return Missing()
