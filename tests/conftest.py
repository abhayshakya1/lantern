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


def _flows(quarter_ends, values, lag_days):
    """Quarterly flow frame keyed by filing date = period end + lag."""
    return pd.DataFrame(
        {
            "date": quarter_ends + pd.Timedelta(days=lag_days),
            "period_end": quarter_ends,
            "value": values,
            "kind": "quarter",
        }
    )


def _instants(quarter_ends, values, lag_days):
    return pd.DataFrame(
        {
            "date": quarter_ends + pd.Timedelta(days=lag_days),
            "period_end": quarter_ends,
            "value": values,
            "kind": "instant",
        }
    )


@pytest.fixture
def seeded_all_series(tmp_store):
    """Synthetic but structurally faithful versions of every series the drivers read, 2008 onward."""
    import numpy as np

    from lantern import config

    rng = np.random.default_rng(7)
    months = pd.period_range("2008-01", "2026-10", freq="M").to_timestamp("M")
    days = pd.bdate_range("2008-01-01", "2026-10-31")
    weeks = pd.date_range("2008-01-03", "2026-10-29", freq="W-THU")
    quarter_ends = pd.date_range("2007-12-31", "2026-09-30", freq="QE")
    nq = len(quarter_ends)
    out = {"months": months, "last_month_end": months[-1]}

    # prices: basket, large caps, indices
    for i, t in enumerate(config.BASKET + config.LARGE_CAPS):
        path = (50 + 10 * i) * np.cumprod(1 + rng.normal(0.012, 0.06, len(months)))
        tmp_store.save_series(f"prices.{t}", pd.DataFrame({"date": months, "value": path}))
    tmp_store.save_series("prices.^GSPC", pd.DataFrame({"date": months, "value": 1400 * np.cumprod(1 + rng.normal(0.007, 0.04, len(months)))}))
    tmp_store.save_series("prices.^NDX", pd.DataFrame({"date": months, "value": 2000 * np.cumprod(1 + rng.normal(0.01, 0.05, len(months)))}))

    # EDGAR: all basket names report net income and shares; hyperscalers also capex, ocf, cash, debt
    capex_frames, ocf_frames = {}, {}
    for i, t in enumerate(config.BASKET + config.LARGE_CAPS):
        base = 2e9 * (1 + i / 4)
        ni = base * np.cumprod(1 + rng.normal(0.02, 0.05, nq))
        tmp_store.save_series(f"edgar.{t}.net_income", _flows(quarter_ends, ni, 35))
        shares = np.full(nq, 4e9 - 1e8 * (i % 7))
        tmp_store.save_series(f"edgar.{t}.shares", _instants(quarter_ends, shares, 35))
        if t in config.HYPERSCALERS:
            ocf = base * 2.5 * np.cumprod(1 + rng.normal(0.02, 0.04, nq))
            capex = ocf * np.clip(0.3 + 0.02 * np.arange(nq) / 4 + rng.normal(0, 0.03, nq), 0.1, 0.9)
            tmp_store.save_series(f"edgar.{t}.capex", _flows(quarter_ends, capex, 35))
            tmp_store.save_series(f"edgar.{t}.ocf", _flows(quarter_ends, ocf, 35))
            tmp_store.save_series(f"edgar.{t}.cash", _instants(quarter_ends, base * 6 + rng.normal(0, base, nq), 35))
            tmp_store.save_series(f"edgar.{t}.debt", _instants(quarter_ends, base * 4 * np.cumprod(1 + rng.normal(0.01, 0.03, nq)), 35))
            capex_frames[t], ocf_frames[t] = capex, ocf
    # expected capex intensity as of 31 Jul 2025: quarters ending Jun 2024 to Mar 2025 (Jun 2025 is filed 4 Aug)
    q_idx = [k for k, q in enumerate(quarter_ends) if pd.Timestamp("2024-06-30") <= q <= pd.Timestamp("2025-03-31")]
    out["capex_through_1q25"] = sum(capex_frames[t][q_idx].sum() for t in capex_frames) / sum(
        ocf_frames[t][q_idx].sum() for t in ocf_frames
    )

    # FRED daily and weekly
    tmp_store.save_series("fred.DFII10", pd.DataFrame({"date": days, "value": 1.0 + np.cumsum(rng.normal(0, 0.01, len(days)))}))
    tmp_store.save_series("fred.BAA10Y", pd.DataFrame({"date": days, "value": np.clip(4 + np.cumsum(rng.normal(0, 0.02, len(days))), 2, 12)}))
    tmp_store.save_series("fred.DFF", pd.DataFrame({"date": days, "value": np.clip(2 + np.cumsum(rng.normal(0, 0.005, len(days))), 0, 6)}))
    tmp_store.save_series("fred.DEXTAUS", pd.DataFrame({"date": days, "value": 31 + np.cumsum(rng.normal(0, 0.02, len(days)))}))
    tmp_store.save_series("fred.WALCL", pd.DataFrame({"date": weeks, "value": 2e6 + np.cumsum(rng.normal(2000, 5000, len(weeks)))}))
    out["fred.DFII10"] = tmp_store.load_series("fred.DFII10")

    # AAII weekly spread, Shiller monthly from 1985
    tmp_store.save_series("aaii.bull_bear", pd.DataFrame({"date": weeks, "value": np.clip(rng.normal(0.05, 0.15, len(weeks)), -0.6, 0.6)}))
    long_months = pd.period_range("1985-01", "2026-10", freq="M").to_timestamp("M")
    earnings = 15 * np.cumprod(1 + rng.normal(0.004, 0.02, len(long_months)))
    tmp_store.save_series("shiller.earnings", pd.DataFrame({"date": long_months, "value": earnings}))
    tmp_store.save_series("shiller.pe", pd.DataFrame({"date": long_months, "value": np.clip(18 + np.cumsum(rng.normal(0, 0.4, len(long_months))), 8, 45)}))
    tmp_store.save_series("shiller.long_rate", pd.DataFrame({"date": long_months, "value": np.clip(5 + np.cumsum(rng.normal(0, 0.05, len(long_months))), 0.5, 12)}))

    # today's snapshots
    today = months[-1]
    tmp_store.save_series("spy.top10_weight", pd.DataFrame({"date": [today], "value": [0.389]}))
    for t in config.BASKET:
        tmp_store.save_series(f"yahoo.forward_pe.{t}", pd.DataFrame({"date": [today], "value": [30.0]}))
        tmp_store.save_series(f"yahoo.market_cap.{t}", pd.DataFrame({"date": [today], "value": [1.5e12]}))
        tmp_store.save_series(f"yahoo.trailing_eps.{t}", pd.DataFrame({"date": [today], "value": [5.0]}))
        acts = pd.DataFrame({"date": pd.to_datetime(["2026-09-10", "2026-10-02", "2026-10-20"]), "value": [1.0, 1.0, -1.0]})
        tmp_store.save_series(f"yahoo.actions.{t}", acts)
    return out


@pytest.fixture
def fake_yahoo_missing_msft():
    class Missing(FakeYahoo):
        def history(self, ticker, start):
            if ticker == "MSFT":
                raise ConnectionError("MSFT unavailable")
            return super().history(ticker, start)

    return Missing()


@pytest.fixture
def retriever(tmp_path):
    """The two fixture filings ingested, indexed with the hash embedder, and wrapped in a Retriever."""
    import shutil

    from lantern.filings import corpus, retrieve

    shutil.copytree(FIXTURES / "filings", tmp_path / "filings")
    chunks, manifest = corpus.build_corpus(tmp_path / "filings")
    retrieve.build_index(chunks, tmp_path / "index", retrieve.HashEmbedder(), manifest)
    return retrieve.Retriever(tmp_path / "index", retrieve.HashEmbedder())


class FakeClaude:
    """Stands in for anthropic.Anthropic(): returns canned JSON through client.messages.create, or raises."""

    def __init__(self, payload: dict | None, stop_reason: str = "end_turn", raise_exc: Exception | None = None):
        from types import SimpleNamespace

        self.payload, self.stop_reason, self.raise_exc, self.calls = payload, stop_reason, raise_exc, []
        self.messages = self
        self._ns = SimpleNamespace

    def create(self, **kw):
        self.calls.append(kw)
        if self.raise_exc:
            raise self.raise_exc
        text = json.dumps(self.payload) if self.payload is not None else ""
        return self._ns(
            stop_reason=self.stop_reason,
            stop_details=self._ns(category="unknown", explanation="") if self.stop_reason == "refusal" else None,
            content=[self._ns(type="text", text=text)],
            usage=self._ns(input_tokens=1, output_tokens=1, cache_read_input_tokens=0),
        )


@pytest.fixture
def run_fixture():
    """A trimmed but shape-faithful model-run payload (see pull.run_model)."""
    return {
        "as_of": "2026-11-08T07:00:00+08:00",
        "model": {"version": "0.1", "run_at": "2026-11-08T07:00:00+08:00",
                  "calibrated": ["valuation", "concentration", "leverage"]},
        "tiles": {"probability": {"value": 0.07, "delta_1m": 0.01, "status": "calm"},
                  "fv_gap": {"value": 0.18}},
        "chart": {"months": ["2026-10", "2026-11"],
                  "scenarios": {"base": {"end_return": 0.06, "prob": 0.75},
                                "derating": {"end_return": -0.22, "prob": 0.07},
                                "meltup": {"end_return": 0.25, "prob": 0.18}},
                  "source_line": "Source: test"},
        "triggers": [{"label": "Valuation +1z", "delta_pts": 2.1}],
        "drivers": [{"id": "valuation", "label": "Valuation", "tier": "calibrated", "z": 1.2, "contribution_pts": 3.0},
                    {"id": "capex", "label": "Capex", "tier": "watch", "z": 0.4, "contribution_pts": 0.0}],
    }
