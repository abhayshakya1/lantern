# Lantern Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the app shell, the public-data layer, the transparent de-rating model with its backtest, and the live AI-bubble monitor screen, served from the laptop and run from a one-command morning pull.

**Architecture:** A Python package `lantern` pulls every public series through one cached, hashed fetch path into SQLite and Parquet, builds seven monthly driver z-scores, fits and applies a logistic de-rating model with a fair-value and forecast-fan layer, and exposes one JSON endpoint per screen through FastAPI. A static front end (plain HTML, CSS, JavaScript, no build step) renders the approved mock from that JSON. Everything the screen shows traces to a provenance row.

**Tech Stack:** Python 3.12, pandas, numpy, scipy (logistic fit), requests, yfinance, pyarrow, FastAPI, uvicorn, pytest; front end in vanilla JS with hand-drawn SVG; Node with puppeteer-core for the browser smoke test (Google Chrome already installed).

**Spec:** `docs/superpowers/specs/2026-11-07-lantern-platform-design.md` (this plan covers the shell, data layer, model and AI-bubble monitor; Filings Q&A and Research desk get their own plans).

## Global Constraints

- Public, free data only; no paid feeds; no OCBC data (spec: Non-goals, Constraints).
- Every number on screen traces to a source, a UTC timestamp and a SHA-256 (spec: Anti-goals). Raw responses are written under `data/raw/<YYYY-MM-DD>/` before parsing.
- A failed pull leaves the previous cache on screen with the badge changed, never a blank (spec: Data layer). Badge states: "Live data · pulled HH:MM SGT", "Cached data · pulled DD Mon".
- The model is a transparent composite with fixed, disclosed weights: valuation 25%, capex 20%, concentration 15%, leverage 15%, positioning 10%, revisions 10%, rates 5% (spec: The model).
- The de-rating event is a 25% or larger drawdown within 12 months; melt-up is a 20% or larger gain; calibration window 2003 to 2026 with 2000 as a labelled analogue; the pitch never says "since 1990" (spec: The model).
- Fair value = trailing-twelve-month earnings times the 10-year median trailing P/E adjusted for the real yield; band plus or minus 7% (spec: The model).
- Yahoo forward P/E is shown as context on a tile and is never a driver (spec: The model).
- Basket: NVDA, MSFT, GOOGL, AMZN, META, AVGO, TSM, ORCL, equal-weighted, indexed to 100 at the start of the 24-month window (spec: The product). Hyperscalers for capex: MSFT, GOOGL, AMZN, META, ORCL.
- Visual standard: the approved mock at `.superpowers/brainstorm/13939-1793999114/content/centre-screen-v2.html`; IBM Plex Sans and Plex Mono; one blue accent `#1F5FBF`; status colours only for status; no gradients, glow or emoji (spec: Shell, Anti-goals).
- The demo runs from the laptop; the GPU server is never on the demo-day path (spec: Constraints).
- Times shown to users are Singapore time (SGT, UTC+8); storage is UTC.
- Python code is formatted with `ruff format`, type-hinted, and tested with pytest; no network in unit tests (fixtures under `tests/fixtures/`); network tests carry `@pytest.mark.network` and are skipped by default.

## Review Focus

1. A source returns a partial, stale or malformed file (FRED prints "." for missing values; Yahoo returns fewer tickers than asked; SSGA changes its sheet layout). Expected: that series is marked stale, the previous cache is kept, the pull status table says so, and the badge switches to cached. Pinned in Task 12.
2. A driver with less than ten years of its own history (the basket's trailing P/E, the reconstructed top-10 weight). Expected: the proxy-spliced series feeds the z-score, the driver detail panel says "proxy before <date>", and the screen never shows NaN. Pinned in Task 8.
3. Today's composite far outside history, so fewer than 24 months fall within one point of it. Expected: the conditional window widens to two points and the chart's source line says so; the fan never collapses to a line. Pinned in Task 10.
4. Mixed frequencies and filing lags: daily FRED, weekly AAII, quarterly EDGAR facts dated by filing date, not period end. Expected: monthly readings use only data known by month end (no look-ahead), and a quarter whose filing arrives late is absent for that month rather than back-filled. Pinned in Task 5 and Task 8.
5. The as-of date and badge across a time-zone change or a day without a pull. Expected: the header shows the pull time in SGT, a run built on yesterday's cache is labelled cached with yesterday's date, and the probability tile still renders. Pinned in Task 12 and Task 13.

---

## File structure

```
pyproject.toml                 package metadata, pytest and ruff config
.gitignore                     data/, .venv/, node_modules/, .superpowers/, .env
lantern/
  __init__.py
  config.py                    constants: tickers, CIKs, FRED ids, weights, thresholds, paths, series names
  store.py                     Store: SQLite provenance and runs, Parquet series
  sources/
    __init__.py
    base.py                    fetch_raw with cache, hash and provenance; SourceError
    fred.py                    FRED CSV series
    yahoo.py                   prices, forward P/E, market cap, analyst actions via yfinance
    edgar.py                   SEC company-facts: net income, shares, capex, OCF, cash, debt
    spy.py                     SSGA SPY holdings top-10 weight, and concentration history
    sentiment.py               CBOE put/call and AAII bull-bear spread
    shiller.py                 Shiller monthly data (long history)
  drivers.py                   monthly readings, proxy splices, 10-year z-scores, driver metadata
  model.py                     composite, logistic fit, probability, contributions, triggers, fair value, fan, scenarios
  backtest.py                  drawdown labels, backtest, calibration table, ledger rows
  pull.py                      orchestrated morning pull, status table, badge
  api.py                       FastAPI app and the monitor JSON
  cli.py                       lantern pull | model | backtest | serve
web/
  index.html                   shell: nav, top bar, module containers
  styles.css                   tokens and components from the mock
  app.js                       routing by hash, fetches JSON, renders modules
  charts.js                    line and fan chart, sparkline, z-bar, segmented bar
  monitor.js                   monitor screen renderer and driver detail panel
  placeholders.js              Rates and macro, Model risk, Data sources, Settings pages
  package.json                 puppeteer-core dev dependency for the smoke test
  smoke.mjs                    browser smoke test
tests/
  conftest.py                  tmp Store fixture, fixture loaders
  fixtures/                    recorded sample responses (small)
  test_store.py test_base.py test_fred.py test_yahoo.py test_edgar.py test_spy.py
  test_sentiment.py test_shiller.py test_drivers.py test_model.py test_backtest.py
  test_pull.py test_api.py
scripts/
  demo_morning.sh              pull, model, status, serve
```

---

### Task 1: Repository, package skeleton and configuration

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `lantern/__init__.py`, `lantern/config.py`, `tests/conftest.py`, `tests/test_config.py`

**Interfaces:**
- Produces: `config.BASKET = ["NVDA","MSFT","GOOGL","AMZN","META","AVGO","TSM","ORCL"]`; `config.HYPERSCALERS = ["MSFT","GOOGL","AMZN","META","ORCL"]`; `config.CIK: dict[str,int]` for all eight (TSM = 1046179); `config.FRED = {"real_yield":"DFII10","fed_funds":"DFF","hy_spread":"BAMLH0A0HYM2","fed_assets":"WALCL"}`; `config.WEIGHTS: dict[str,float]` with the seven driver ids `valuation, capex, concentration, leverage, positioning, revisions, rates`; `config.DRAWDOWN = 0.25`, `config.MELTUP = 0.20`, `config.HORIZON_MONTHS = 12`, `config.Z_WINDOW_MONTHS = 120`, `config.FV_BAND = 0.07`, `config.REAL_YIELD_PE_SENSITIVITY = 0.10` (P/E falls 10% per percentage point of real yield above its 10-year median), `config.CALIBRATION_START = "2003-01"`, `config.STATUS_BANDS = [(0.25,"calm"),(0.50,"elevated"),(1.0,"high")]`, `config.DATA_DIR` (env `LANTERN_DATA`, default `./data`), `config.SGT = ZoneInfo("Asia/Singapore")`.

- [ ] **Step 1: Initialise the repository and the environment**

Run from the project folder:
```bash
git init && python3 -m venv .venv && source .venv/bin/activate
pip install pandas numpy scipy requests yfinance pyarrow fastapi uvicorn httpx pytest ruff openpyxl
```
Expected: `python -c "import pandas, yfinance, fastapi"` prints nothing.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_config.py
from lantern import config

def test_weights_sum_to_one_and_cover_seven_drivers():
    assert set(config.WEIGHTS) == {"valuation","capex","concentration","leverage","positioning","revisions","rates"}
    assert abs(sum(config.WEIGHTS.values()) - 1.0) < 1e-9
    assert config.WEIGHTS["valuation"] == 0.25 and config.WEIGHTS["rates"] == 0.05

def test_basket_and_ciks():
    assert len(config.BASKET) == 8 and config.CIK["TSM"] == 1046179
    assert set(config.HYPERSCALERS) < set(config.BASKET)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with "No module named lantern" or ImportError.

- [ ] **Step 4: Write `pyproject.toml`, `.gitignore`, `lantern/__init__.py`, `lantern/config.py`, `tests/conftest.py`**

`pyproject.toml` declares the package, `[tool.pytest.ini_options]` with `markers = ["network: hits the internet"]` and `addopts = "-m 'not network'"`, and ruff. `conftest.py` provides `tmp_store` (a `Store` in `tmp_path`, implemented in Task 2; define the fixture now importing lazily) and `fixture_path(name)`.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore lantern tests && git commit -m "feat: lantern package skeleton and configuration"
```

---

### Task 2: Store and raw fetch with provenance

**Files:**
- Create: `lantern/store.py`, `lantern/sources/__init__.py`, `lantern/sources/base.py`, `tests/test_store.py`, `tests/test_base.py`

**Interfaces:**
- Produces: `class Store(root: Path)` with `record_fetch(name: str, url: str, sha256: str, path: Path, status: str, fetched_at: datetime) -> int`; `provenance(limit: int = 200) -> list[dict]`; `save_series(name: str, df: pd.DataFrame) -> None` and `load_series(name: str) -> pd.DataFrame | None` where every series frame has columns `date` (UTC date) and `value` (float), stored at `<root>/series/<name>.parquet`; `save_run(run: dict) -> str` returning a run id `YYYYMMDD-HHMMSS`, `latest_run() -> dict | None`, `list_runs() -> list[dict]`; `set_meta(key, value)` / `get_meta(key)`.
- Produces: `fetch_raw(store: Store, name: str, url: str, *, headers: dict | None = None, timeout: int = 20, params: dict | None = None) -> RawFetch` with `RawFetch(path: Path, sha256: str, fetched_at: datetime, content: bytes)`; raises `SourceError(name, reason)` on non-200, timeout or empty body. Saves to `<root>/raw/<YYYY-MM-DD>/<name>` with the response's extension guessed from `Content-Type` (`.csv`, `.json`, `.xlsx`, else `.bin`) and records provenance with status `ok`; on failure records status `error` and raises.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_store.py
def test_series_roundtrip(tmp_store):
    df = pd.DataFrame({"date": pd.to_datetime(["2026-01-31","2026-02-28"]).date, "value": [1.0, 2.0]})
    tmp_store.save_series("fred.DFII10", df)
    out = tmp_store.load_series("fred.DFII10")
    assert out["value"].tolist() == [1.0, 2.0] and tmp_store.load_series("missing") is None

def test_run_ids_are_ordered_and_latest_wins(tmp_store):
    a = tmp_store.save_run({"probability": 0.3}); b = tmp_store.save_run({"probability": 0.4})
    assert a < b and tmp_store.latest_run()["probability"] == 0.4

# tests/test_base.py  (uses a local http.server thread serving tests/fixtures)
def test_fetch_raw_writes_file_hash_and_provenance(tmp_store, fixture_server):
    r = fetch_raw(tmp_store, "fred.DFII10", fixture_server + "/fred_DFII10.csv")
    assert r.path.exists() and r.path.suffix == ".csv" and len(r.sha256) == 64
    assert tmp_store.provenance()[0]["status"] == "ok"

def test_fetch_raw_404_records_error_and_raises(tmp_store, fixture_server):
    with pytest.raises(SourceError):
        fetch_raw(tmp_store, "nothing", fixture_server + "/missing.csv")
    assert tmp_store.provenance()[0]["status"] == "error"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_store.py tests/test_base.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement `Store` in `lantern/store.py` and `fetch_raw` in `lantern/sources/base.py`**

SQLite tables `provenance(id, name, url, sha256, path, status, fetched_at)`, `runs(id, created_at, payload_json)`, `meta(key, value)`. Add the `fixture_server` fixture to `tests/conftest.py` (a `http.server` on a free port serving `tests/fixtures`, started in a daemon thread).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_store.py tests/test_base.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add lantern/store.py lantern/sources tests && git commit -m "feat: store with provenance, series parquet and cached raw fetch"
```

---

### Task 3: FRED source

**Files:**
- Create: `lantern/sources/fred.py`, `tests/test_fred.py`, `tests/fixtures/fred_DFII10.csv` (60 rows copied from `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10`, including two "." rows)

**Interfaces:**
- Produces: `pull_fred(store: Store, ids: dict[str, str] = config.FRED) -> dict[str, pd.DataFrame]` returning `{"fred.<ID>": frame}` for each id, each frame `date, value` daily with "." rows dropped, saved through `store.save_series`; `fred_url(series_id: str) -> str` = `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<ID>`.

- [ ] **Step 1: Write the failing test**

```python
def test_pull_fred_parses_and_drops_missing(tmp_store, fixture_server, monkeypatch):
    monkeypatch.setattr(fred, "fred_url", lambda sid: f"{fixture_server}/fred_{sid}.csv")
    out = fred.pull_fred(tmp_store, {"real_yield": "DFII10"})
    df = out["fred.DFII10"]
    assert list(df.columns) == ["date", "value"] and df["value"].notna().all() and len(df) == 58
    assert tmp_store.load_series("fred.DFII10") is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fred.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement `pull_fred` and `fred_url` in `lantern/sources/fred.py`**

Use `fetch_raw` then `pandas.read_csv(io.BytesIO(content), na_values=["."])`; rename the second column to `value`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fred.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lantern/sources/fred.py tests/test_fred.py tests/fixtures/fred_DFII10.csv && git commit -m "feat: FRED source"
```

---

### Task 4: Yahoo source (prices, forward P/E, market cap, analyst actions)

**Files:**
- Create: `lantern/sources/yahoo.py`, `tests/test_yahoo.py`, `tests/fixtures/yahoo_prices.parquet` (monthly closes for the eight tickers plus `^NDX` and `^GSPC`, 2003-01 to 2026-10, built once with a network run and committed), `tests/fixtures/yahoo_info.json`, `tests/fixtures/yahoo_actions.json`

**Interfaces:**
- Produces: `pull_yahoo(store: Store, tickers: list[str] = config.BASKET + ["^NDX","^GSPC"], *, client=None) -> dict[str, pd.DataFrame]` saving `prices.<TICKER>` (monthly last close, `date, value`), `yahoo.forward_pe.<TICKER>` (one row, today), `yahoo.market_cap.<TICKER>` (one row), `yahoo.actions.<TICKER>` (`date, value` where value is +1 upgrade, −1 downgrade, last 90 days); `client` is an object with `history(ticker, start) -> pd.DataFrame`, `info(ticker) -> dict`, `actions(ticker) -> pd.DataFrame`, defaulting to a thin wrapper around `yfinance.Ticker`.
- Produces: `basket_index(store: Store, start: str) -> pd.DataFrame` (`date, value`): equal-weighted monthly index of the eight tickers rebased to 100 at `start`.

- [ ] **Step 1: Write the failing tests**

```python
def test_pull_yahoo_saves_prices_and_snapshots(tmp_store, fake_yahoo):
    out = yahoo.pull_yahoo(tmp_store, ["NVDA", "MSFT"], client=fake_yahoo)
    assert tmp_store.load_series("prices.NVDA")["value"].iloc[-1] > 0
    assert len(tmp_store.load_series("yahoo.forward_pe.NVDA")) == 1
    assert set(out) >= {"prices.NVDA", "yahoo.actions.MSFT"}

def test_basket_index_rebased_to_100(tmp_store, fake_yahoo):
    yahoo.pull_yahoo(tmp_store, config.BASKET, client=fake_yahoo)
    idx = yahoo.basket_index(tmp_store, "2024-11")
    assert abs(idx["value"].iloc[0] - 100) < 1e-9 and idx["value"].iloc[-1] > 100

def test_missing_ticker_marks_error_and_keeps_others(tmp_store, fake_yahoo_missing_msft):
    out = yahoo.pull_yahoo(tmp_store, ["NVDA", "MSFT"], client=fake_yahoo_missing_msft)
    assert "prices.NVDA" in out and "prices.MSFT" not in out
    assert any(p["name"] == "prices.MSFT" and p["status"] == "error" for p in tmp_store.provenance())
```

`fake_yahoo` in conftest reads the three fixtures; `fake_yahoo_missing_msft` raises for MSFT.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_yahoo.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement `lantern/sources/yahoo.py`**

Record provenance for each ticker with the Yahoo URL as `https://finance.yahoo.com/quote/<T>` and the sha256 of the serialised frame (yfinance does not expose the raw response). Monthly close = last trading day of the month. One failing ticker is caught, recorded as `error`, and skipped.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_yahoo.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Record the fixtures from the network once**

Run: `pytest tests/test_yahoo.py -m network -k record` (a `@pytest.mark.network` test `test_record_fixtures` that writes the three fixture files when `LANTERN_RECORD=1`).
Expected: the fixture files exist and are under 400 KB together.

- [ ] **Step 6: Commit**

```bash
git add lantern/sources/yahoo.py tests/test_yahoo.py tests/fixtures/yahoo_* tests/conftest.py && git commit -m "feat: Yahoo source and basket index"
```

---

### Task 5: EDGAR company-facts source

**Files:**
- Create: `lantern/sources/edgar.py`, `tests/test_edgar.py`, `tests/fixtures/edgar_MSFT.json` (trimmed company-facts JSON keeping only the tags used, 2009 onward), `tests/fixtures/edgar_TSM.json`

**Interfaces:**
- Produces: `pull_edgar(store: Store, tickers: list[str] = config.BASKET) -> dict[str, pd.DataFrame]` saving, per ticker, quarterly frames keyed by **filing date** (`date` = `filed`, plus columns `period_end`, `value`): `edgar.<T>.net_income`, `edgar.<T>.shares`, `edgar.<T>.capex`, `edgar.<T>.ocf`, `edgar.<T>.cash`, `edgar.<T>.debt`. Tags: `NetIncomeLoss`, `dei:EntityCommonStockSharesOutstanding`, `PaymentsToAcquirePropertyPlantAndEquipment`, `NetCashProvidedByUsedInOperatingActivities`, `CashAndCashEquivalentsAtCarryingValue`, `LongTermDebt` (fallback `LongTermDebtNoncurrent`); IFRS equivalents for TSM (`ProfitLoss`, `PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities`, `CashFlowsFromUsedInOperatingActivities`); where a TSM tag is absent the series is saved empty and `edgar.TSM.note` meta says "Yahoo trailing EPS used for TSM".
- Produces: `trailing_4q(df: pd.DataFrame, as_of: date) -> float | None`: sum of the four most recent quarterly values whose `filed <= as_of` (quarter values derived from cumulative 10-K figures by differencing within a fiscal year).
- URL: `https://data.sec.gov/api/xbrl/companyfacts/CIK<10 digits>.json` with a `User-Agent` header `Lantern research (abhay@example.com)` set from env `LANTERN_SEC_UA`.

- [ ] **Step 1: Write the failing tests**

```python
def test_capex_series_keyed_by_filing_date(tmp_store, fixture_server, monkeypatch):
    monkeypatch.setattr(edgar, "facts_url", lambda cik: f"{fixture_server}/edgar_MSFT.json")
    edgar.pull_edgar(tmp_store, ["MSFT"])
    capex = tmp_store.load_series("edgar.MSFT.capex")
    assert (capex["date"] >= capex["period_end"]).all()          # filing never precedes period end

def test_trailing_4q_uses_only_facts_filed_by_as_of(tmp_store, fixture_server, monkeypatch):
    monkeypatch.setattr(edgar, "facts_url", lambda cik: f"{fixture_server}/edgar_MSFT.json")
    edgar.pull_edgar(tmp_store, ["MSFT"])
    capex = tmp_store.load_series("edgar.MSFT.capex")
    early = edgar.trailing_4q(capex, date(2025, 7, 1)); late = edgar.trailing_4q(capex, date(2025, 8, 15))
    assert early != late and late > 0

def test_tsm_falls_back_without_crashing(tmp_store, fixture_server, monkeypatch):
    monkeypatch.setattr(edgar, "facts_url", lambda cik: f"{fixture_server}/edgar_TSM.json")
    out = edgar.pull_edgar(tmp_store, ["TSM"])
    assert "edgar.TSM.net_income" in out and tmp_store.get_meta("edgar.TSM.note") is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_edgar.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement `lantern/sources/edgar.py`**

Parse `facts["us-gaap"][tag]["units"]["USD"]` (shares: `["dei"][tag]["units"]["shares"]`), keep `form in {"10-K","10-Q","20-F","6-K"}`, de-duplicate by `(fy, fp, period end)` keeping the earliest `filed`, derive quarterly flows from cumulative values by fiscal year.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_edgar.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add lantern/sources/edgar.py tests/test_edgar.py tests/fixtures/edgar_* && git commit -m "feat: EDGAR company-facts source with filing-date keying"
```

---

### Task 6: SPY holdings and concentration history

**Files:**
- Create: `lantern/sources/spy.py`, `tests/test_spy.py`, `tests/fixtures/spy_holdings.xlsx` (the SSGA daily holdings file, first 60 rows)

**Interfaces:**
- Produces: `pull_spy(store: Store) -> dict[str, pd.DataFrame]` saving `spy.top10_weight` (one row, today, value = sum of the ten largest `Weight` values as a fraction); URL `https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx` with a browser `User-Agent`.
- Produces: `concentration_history(store: Store, start: str = "2003-01") -> pd.DataFrame` (`date, value` monthly): for each month end, the ten largest `price × shares` among the stored EDGAR shares for the basket plus a fixed list of 20 other large caps in `config.LARGE_CAPS` (AAPL, BRK-B, JPM, LLY, V, UNH, XOM, MA, JNJ, PG, COST, HD, ABBV, WMT, BAC, NFLX, KO, CRM, CVX, MRK), divided by the S&P 500 total market cap approximated as `^GSPC level × config.SP500_DIVISOR_SHARES` (a constant 8.4e9 documented as approximate), with meta `concentration.note` = "history reconstructed from 28 large caps; today's value from SSGA". The month-end row equal to today is replaced by the SSGA value.

- [ ] **Step 1: Write the failing tests**

```python
def test_pull_spy_top10(tmp_store, fixture_server, monkeypatch):
    monkeypatch.setattr(spy, "SPY_URL", f"{fixture_server}/spy_holdings.xlsx")
    out = spy.pull_spy(tmp_store)
    v = out["spy.top10_weight"]["value"].iloc[0]
    assert 0.25 < v < 0.50

def test_concentration_history_is_monthly_fraction(tmp_store, seeded_prices_and_shares):
    hist = spy.concentration_history(tmp_store, "2024-01")
    assert len(hist) >= 20 and hist["value"].between(0.05, 0.6).all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_spy.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement `lantern/sources/spy.py`**

Read the xlsx with `openpyxl` via pandas, find the header row by the cell `Ticker`. The `seeded_prices_and_shares` fixture in conftest writes synthetic `prices.*` and `edgar.*.shares` series into `tmp_store`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_spy.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add lantern/sources/spy.py tests/test_spy.py tests/fixtures/spy_holdings.xlsx tests/conftest.py && git commit -m "feat: SPY top-10 weight and reconstructed concentration history"
```

---

### Task 7: Sentiment and Shiller sources

**Files:**
- Create: `lantern/sources/sentiment.py`, `lantern/sources/shiller.py`, `tests/test_sentiment.py`, `tests/test_shiller.py`, `tests/fixtures/cboe_pc.csv`, `tests/fixtures/aaii.xls` (or `.csv` if AAII serves CSV), `tests/fixtures/shiller_ie_data.xls` (trimmed)

**Interfaces:**
- Produces: `pull_sentiment(store) -> dict[str, pd.DataFrame]` saving `cboe.put_call` (daily equity put/call from `https://cdn.cboe.com/api/global/us_indices/daily_prices/...`; the builder confirms the current CBOE CSV URL and records it in `config.CBOE_URL`) and `aaii.bull_bear` (weekly bull minus bear, fraction, from `https://www.aaii.com/files/surveys/sentiment.xls`).
- Produces: `pull_shiller(store) -> dict[str, pd.DataFrame]` saving `shiller.pe` (monthly trailing P/E of the S&P 500 = price / trailing 12-month earnings) and `shiller.long_rate` from `http://www.econ.yale.edu/~shiller/data/ie_data.xls`.

- [ ] **Step 1: Write the failing tests**

```python
def test_pull_sentiment_parses_both(tmp_store, fixture_server, monkeypatch):
    monkeypatch.setattr(sentiment, "CBOE_URL", f"{fixture_server}/cboe_pc.csv")
    monkeypatch.setattr(sentiment, "AAII_URL", f"{fixture_server}/aaii.xls")
    out = sentiment.pull_sentiment(tmp_store)
    assert out["cboe.put_call"]["value"].between(0.2, 2.0).all()
    assert out["aaii.bull_bear"]["value"].between(-1, 1).all()

def test_pull_shiller_monthly_pe(tmp_store, fixture_server, monkeypatch):
    monkeypatch.setattr(shiller, "SHILLER_URL", f"{fixture_server}/shiller_ie_data.xls")
    pe = shiller.pull_shiller(tmp_store)["shiller.pe"]
    assert pe["date"].min().year <= 1990 and pe["value"].between(5, 60).all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sentiment.py tests/test_shiller.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement both modules**

Shiller's sheet has a fractional year column (`2026.1` = January); convert to month end. `xlrd` is needed for `.xls`; add it to the pip install in Task 1's command and `pyproject.toml`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sentiment.py tests/test_shiller.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add lantern/sources/sentiment.py lantern/sources/shiller.py tests && git commit -m "feat: CBOE, AAII and Shiller sources"
```

---

### Task 8: Driver readings, proxies and z-scores

**Files:**
- Create: `lantern/drivers.py`, `tests/test_drivers.py`

**Interfaces:**
- Consumes: the series names saved by Tasks 3 to 7 and `yahoo.basket_index`, `edgar.trailing_4q`.
- Produces: `DRIVERS: list[DriverMeta]` with `DriverMeta(id, label, unit, source, transform, sign, trigger: Trigger | None)` for the seven ids in `config.WEIGHTS` order; `monthly_readings(store: Store, start: str = config.CALIBRATION_START, end: date | None = None) -> pd.DataFrame` indexed by month end with one column per driver id, each computed only from data filed or published by that month end:
  - `valuation`: basket trailing P/E = sum of market caps / sum of trailing-4Q net income across the eight (TSM via Yahoo trailing EPS when EDGAR is empty); before the first month all eight have EDGAR data, the Nasdaq-100 trailing P/E proxy = `shiller.pe` scaled by the ratio of basket to S&P P/E at the splice month, recorded in `splices["valuation"]`.
  - `capex`: sum of trailing-4Q capex over sum of trailing-4Q OCF for the hyperscalers.
  - `concentration`: `spy.concentration_history`.
  - `leverage`: z-score average of the hyperscalers' net debt change over 12 months (debt minus cash) and the negative of `fred.BAMLH0A0HYM2` (spread tightening scores as risk), computed inside this function as a single reading in spread-equivalent units: `reading = 0.5 * zdebt - 0.5 * zspread` where each z is over the 10-year window.
  - `positioning`: `0.5 * (-z(put_call)) + 0.5 * z(bull_bear)`, monthly means.
  - `revisions`: upgrade share = upgrades / (upgrades + downgrades) over the trailing 90 days across the basket, inverted (`1 - share`); before Yahoo actions exist (about 2022), the proxy is the 3-month change in `shiller` earnings, inverted, recorded in `splices["revisions"]`.
  - `rates`: `fred.DFII10` monthly mean plus the negative 12-month change in `fred.WALCL` as a z-average, like leverage.
- Produces: `zscores(readings: pd.DataFrame, window: int = config.Z_WINDOW_MONTHS) -> pd.DataFrame` trailing z-scores (expanding until the window fills, minimum 24 months), sign-adjusted so positive means more risk; `splices: dict[str, date]` attached as `readings.attrs["splices"]`; `latest(store) -> tuple[pd.Series, pd.Series]` = (readings row, z row) for the latest month end.

- [ ] **Step 1: Write the failing tests**

```python
def test_zscore_sign_and_window():
    idx = pd.period_range("2010-01", "2026-10", freq="M").to_timestamp("M")
    df = pd.DataFrame({"valuation": np.linspace(10, 40, len(idx))}, index=idx)
    z = drivers.zscores(df, window=120)
    assert z["valuation"].iloc[-1] > 1.0 and z["valuation"].isna().sum() == 23   # first 23 months need 24 obs

def test_readings_use_no_lookahead(tmp_store, seeded_all_series):
    r = drivers.monthly_readings(tmp_store, "2025-01", end=date(2025, 7, 31))
    # the fixture files a 2Q25 10-Q on 2025-08-05: July must not see it
    assert r.loc["2025-07-31", "capex"] == pytest.approx(seeded_all_series["capex_through_1q25"], rel=1e-6)

def test_proxy_splice_recorded_and_no_nan_on_latest(tmp_store, seeded_all_series):
    r = drivers.monthly_readings(tmp_store, "2003-01")
    assert "valuation" in r.attrs["splices"] and r.iloc[-1].notna().all()
    assert drivers.zscores(r).iloc[-1].notna().all()
```

`seeded_all_series` writes small synthetic versions of every series into `tmp_store` and returns known values.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_drivers.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement `lantern/drivers.py`**

Month-end alignment: daily series take the monthly mean (rates, spreads, put/call) or last (prices); weekly AAII takes the mean; EDGAR uses `trailing_4q(df, as_of=month_end)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_drivers.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add lantern/drivers.py tests/test_drivers.py tests/conftest.py && git commit -m "feat: driver readings with disclosed proxies and 10-year z-scores"
```

---

### Task 9: Composite, logistic probability, contributions and triggers

**Files:**
- Create: `lantern/model.py` (part 1), `tests/test_model.py`

**Interfaces:**
- Produces: `composite(z: pd.DataFrame | pd.Series, weights: dict = config.WEIGHTS) -> pd.Series | float`; `fit_logistic(c: pd.Series, labels: pd.Series) -> tuple[float, float]` returning `(a, b)` for `P = 1 / (1 + exp(-(a + b*c)))` fitted by maximum likelihood with `scipy.optimize.minimize`; `probability(c: float, a: float, b: float) -> float` clamped to `[0.01, 0.99]`; `contributions(z_row: pd.Series, a: float, b: float, weights=config.WEIGHTS) -> pd.Series` in probability points where `contrib_i = (P(c) - P(0)) * (w_i * z_i) / c` (sum equals `P(c) - P(0)` exactly; when `|c| < 1e-9` all zero); `status(p: float) -> str` from `config.STATUS_BANDS`; `trigger_effects(z_row: pd.Series, readings_row: pd.Series, stats: dict[str, tuple[float, float]], a, b) -> list[dict]` where `stats[id] = (mean, std)` of the window and each `DriverMeta.trigger = Trigger(level: float, direction: "above" | "below", text: str)`: the effect is `P(c_with_driver_at_level) - P(c)` in points, plus `distance = clamp((current - start) / (level - start), 0, 1)` with `start` = the window mean.
- Trigger definitions (in `drivers.DRIVERS`): rates `level=2.50, above`, revisions `level=0.60 (upgrade share 40%), above`, concentration `level=0.40, above`, capex: the capex driver's trigger is `level = capex guidance growth below 0.15`, which has no free feed, so the capex trigger is defined on the reading `capex/OCF below 0.55, below` with text "Capex falling back under 55% of cash flow flips capex intensity to easing"; valuation `level = 10-year median P/E, below`; leverage and positioning carry no trigger. Four are shown on screen in this order: rates, revisions, concentration, capex.

- [ ] **Step 1: Write the failing tests**

```python
def test_contributions_sum_to_probability_minus_baseline():
    z = pd.Series({"valuation": 2.4, "capex": 1.9, "concentration": 1.5, "leverage": 1.2, "positioning": 1.1, "revisions": -0.4, "rates": 0.3})
    a, b = -1.2, 1.1
    c = model.composite(z)
    contrib = model.contributions(z, a, b)
    assert contrib.sum() == pytest.approx(model.probability(c, a, b) - model.probability(0.0, a, b), abs=1e-9)

def test_fit_logistic_recovers_parameters():
    rng = np.random.default_rng(0); c = pd.Series(rng.normal(0, 1, 2000))
    p = 1 / (1 + np.exp(-(-1.0 + 1.5 * c))); labels = pd.Series(rng.random(2000) < p).astype(int)
    a, b = model.fit_logistic(c, labels)
    assert abs(a + 1.0) < 0.2 and abs(b - 1.5) < 0.25

def test_status_bands_and_clamp():
    assert model.status(0.1) == "calm" and model.status(0.41) == "elevated" and model.status(0.7) == "high"
    assert model.probability(50, 0, 1) == 0.99

def test_trigger_effect_sign():
    z = pd.Series({k: 0.0 for k in config.WEIGHTS}); r = pd.Series({k: 0.0 for k in config.WEIGHTS}); r["rates"] = 2.06
    stats = {k: (0.0, 1.0) for k in config.WEIGHTS}; stats["rates"] = (1.0, 0.5)
    eff = model.trigger_effects(z, r, stats, a=-1.0, b=1.0)
    rates = next(e for e in eff if e["id"] == "rates")
    assert rates["effect_pts"] > 0 and 0 <= rates["distance"] <= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_model.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement part 1 of `lantern/model.py`**

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_model.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add lantern/model.py tests/test_model.py && git commit -m "feat: composite, logistic probability, contributions and triggers"
```

---

### Task 10: Fair value, forecast fan and scenarios

**Files:**
- Modify: `lantern/model.py` (part 2), `tests/test_model.py`

**Interfaces:**
- Produces: `fair_value(ttm_earnings: float, median_pe: float, real_yield: float, median_real_yield: float, k: float = config.REAL_YIELD_PE_SENSITIVITY) -> float` = `ttm_earnings * median_pe * (1 - k * (real_yield - median_real_yield))`, floored at `0.5 * median_pe`; `fv_gap(price, fv) -> float` and `fv_range(price, fv, band=config.FV_BAND) -> tuple[float, float]` = gap against `fv*(1+band)` and `fv*(1-band)`.
- Produces: `conditional_returns(history: pd.DataFrame, c_today: float, band: float = 1.0, min_obs: int = 24) -> tuple[pd.Series, float]` where `history` has columns `composite` and `fwd_12m_return` (index prices, Task 11); widens `band` by 1.0 until `min_obs` rows qualify, returning the band used; `fan(price: float, returns: pd.Series, months: int = 12) -> dict[str, list[float]]` with keys `p10, p25, p50, p75, p90`, each a list of `months + 1` prices where month `m` = `price * (1 + q) ** (m / months)` for the quantile's 12-month return `q`; `scenario_paths(price: float, p50: list[float]) -> dict` with `base = p50`, `derating` ending at `price * (1 - config.DRAWDOWN)`, `meltup` ending at `price * (1 + config.MELTUP)`, both geometric; `scenario_probs(p_derating: float, returns: pd.Series) -> dict[str, float]` with `meltup = mean(returns >= config.MELTUP)`, `derating = p_derating`, `base = max(0, 1 - derating - meltup)`, renormalised to sum to 1; `conditional_drawdown_share(returns) -> float` = `mean(returns <= -config.DRAWDOWN)` for the detail panel.

- [ ] **Step 1: Write the failing tests**

```python
def test_fair_value_adjusts_for_real_yield():
    assert model.fair_value(10, 20, 2.0, 2.0) == pytest.approx(200)
    assert model.fair_value(10, 20, 3.0, 2.0) == pytest.approx(180)

def test_conditional_window_widens_when_sparse():
    hist = pd.DataFrame({"composite": np.linspace(-2, 2, 100), "fwd_12m_return": np.linspace(-0.4, 0.4, 100)})
    r, band = model.conditional_returns(hist, c_today=5.0)
    assert len(r) >= 24 and band > 1.0

def test_fan_and_scenarios_are_consistent():
    returns = pd.Series(np.linspace(-0.5, 0.5, 101))
    f = model.fan(168.0, returns)
    assert f["p50"][0] == 168.0 and f["p10"][-1] < f["p50"][-1] < f["p90"][-1]
    paths = model.scenario_paths(168.0, f["p50"])
    assert paths["derating"][-1] == pytest.approx(126.0) and paths["meltup"][-1] == pytest.approx(201.6)
    probs = model.scenario_probs(0.41, returns)
    assert abs(sum(probs.values()) - 1) < 1e-9 and probs["derating"] == pytest.approx(0.41)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_model.py -v -k "fair_value or conditional or fan"`
Expected: FAIL with AttributeError.

- [ ] **Step 3: Implement part 2 of `lantern/model.py`**

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_model.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add lantern/model.py tests/test_model.py && git commit -m "feat: fair value, forecast fan and scenario probabilities"
```

---

### Task 11: Backtest, calibration and ledger rows

**Files:**
- Create: `lantern/backtest.py`, `tests/test_backtest.py`

**Interfaces:**
- Consumes: `drivers.monthly_readings`, `drivers.zscores`, `model.composite`, `model.fit_logistic`, `model.probability`.
- Produces: `drawdown_labels(prices: pd.Series, horizon: int = config.HORIZON_MONTHS, threshold: float = config.DRAWDOWN) -> pd.Series` (1 where `min(prices[t+1..t+horizon]) / prices[t] - 1 <= -threshold`, NaN for the last `horizon` months); `forward_returns(prices, horizon) -> pd.Series`; `run_backtest(store: Store, start: str = config.CALIBRATION_START) -> BacktestResult` with fields `a, b, hit_rate, brier, n_months, calibration: list[dict(bucket, predicted, observed, n)]` (five buckets), `history: pd.DataFrame(composite, probability, label, fwd_12m_return)` indexed by month end, `analogue_2000: dict(probability_peak, date_peak, drivers=["valuation","rates"])` computed with those two drivers re-weighted to sum to 1 on `shiller.pe` and `fred`-plus-Shiller long rate from 1990; the index for labels is `prices.^NDX`; `ledger_rows(result) -> list[dict(date, probability, horizon_months, realised_return, inside_fan: bool, kind="backtest")]`.
- Hit rate = share of months where `(probability >= 0.5) == label`; Brier = mean squared error; `inside_fan` compares the realised return with the fan the model would have drawn that month (p10 to p90).
- Saves `backtest.history` as a series-like Parquet (`date, composite, probability, label, fwd_12m_return`) and `store.set_meta("calibration", json)` with `a, b, hit_rate, brier, n_months, start, end`.

- [ ] **Step 1: Write the failing tests**

```python
def test_drawdown_labels():
    p = pd.Series([100, 110, 70, 80, 90, 120, 125, 130, 135, 140, 145, 150, 155, 160], index=pd.period_range("2020-01", periods=14, freq="M").to_timestamp("M"))
    lab = backtest.drawdown_labels(p, horizon=3, threshold=0.25)
    assert lab.iloc[0] == 1 and lab.iloc[3] == 0 and lab.iloc[-3:].isna().all()

def test_run_backtest_fits_and_scores(tmp_store, seeded_all_series):
    res = backtest.run_backtest(tmp_store, "2010-01")
    assert res.n_months > 100 and 0 <= res.brier <= 0.25 and len(res.calibration) == 5
    assert tmp_store.get_meta("calibration") is not None and res.analogue_2000["drivers"] == ["valuation", "rates"]
    rows = backtest.ledger_rows(res)
    assert rows and rows[0]["kind"] == "backtest" and isinstance(rows[0]["inside_fan"], bool)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_backtest.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement `lantern/backtest.py`**

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_backtest.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add lantern/backtest.py tests/test_backtest.py && git commit -m "feat: backtest, calibration and ledger seed"
```

---

### Task 12: Morning pull, model run and CLI

**Files:**
- Create: `lantern/pull.py`, `lantern/cli.py`, `tests/test_pull.py`, `scripts/demo_morning.sh`
- Modify: `pyproject.toml` (console script `lantern = "lantern.cli:main"`)

**Interfaces:**
- Produces: `run_pull(store: Store, sources: list[Callable[[Store], dict]] | None = None) -> PullStatus` where the default list is `[pull_fred, pull_yahoo, pull_edgar, pull_spy, pull_sentiment, pull_shiller]`; `PullStatus(items: list[dict(source, status: "ok"|"error"|"stale", series: int, detail: str)], started_at, finished_at)`; each source runs in a `try` so one failure never stops the others; after the pull, `store.set_meta("last_pull", {"at": iso_utc, "ok": bool})` is written only when every source returned `ok`, otherwise `last_pull_attempt` is written and `last_pull` keeps its old value.
- Produces: `badge(store: Store, now: datetime | None = None) -> dict(state: "live"|"cached"|"none", pulled_at: str | None, label: str)`: `live` when `last_pull.at` is on the same SGT calendar day as `now`, label `"Live data · pulled HH:MM SGT"`; `cached` otherwise, label `"Cached data · pulled DD Mon"`.
- Produces: `run_model(store: Store, now: datetime | None = None) -> dict` building the full monitor payload (schema in Task 13) from `drivers.latest`, `model.*`, `backtest` meta and the stored series, appending a note `{"date", "title": "Model run complete", "text": "<probability>% , from <previous>% last month. <top two drivers> drove the change."}`, and saving it through `store.save_run`.
- Produces: `cli.main(argv)` with sub-commands `pull`, `model`, `backtest`, `serve --port 8787 --host 127.0.0.1`, `status` (prints the last pull table and badge). `scripts/demo_morning.sh` runs `lantern pull && lantern model && lantern status && lantern serve`.

- [ ] **Step 1: Write the failing tests**

```python
def test_one_failing_source_keeps_cache_and_marks_cached(tmp_store, seeded_all_series, monkeypatch):
    good = lambda s: {"fred.DFII10": seeded_all_series["fred.DFII10"]}
    def bad(s): raise SourceError("spy", "boom")
    tmp_store.set_meta("last_pull", {"at": "2026-11-06T22:40:00+00:00", "ok": True})
    st = pull.run_pull(tmp_store, [good, bad])
    assert [i["status"] for i in st.items] == ["ok", "error"]
    assert tmp_store.get_meta("last_pull")["at"] == "2026-11-06T22:40:00+00:00"
    assert tmp_store.load_series("fred.DFII10") is not None
    b = pull.badge(tmp_store, now=datetime(2026, 11, 8, 1, 0, tzinfo=timezone.utc))
    assert b["state"] == "cached" and b["label"] == "Cached data · pulled 07 Nov"

def test_badge_live_same_sgt_day(tmp_store):
    tmp_store.set_meta("last_pull", {"at": "2026-11-06T22:40:00+00:00", "ok": True})   # 06:40 SGT on 7 Nov
    b = pull.badge(tmp_store, now=datetime(2026, 11, 7, 1, 30, tzinfo=timezone.utc))
    assert b["state"] == "live" and b["label"] == "Live data · pulled 06:40 SGT"

def test_run_model_builds_payload(tmp_store, seeded_all_series):
    backtest.run_backtest(tmp_store, "2010-01")
    run = pull.run_model(tmp_store)
    assert 0.01 <= run["tiles"]["probability"]["value"] <= 0.99 and len(run["drivers"]) == 7
    assert abs(sum(run["scenarios"][k]["prob"] for k in ("base", "derating", "meltup")) - 1) < 1e-9
    assert tmp_store.latest_run()["model"]["run_at"] == run["model"]["run_at"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pull.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement `lantern/pull.py`, `lantern/cli.py` and `scripts/demo_morning.sh`**

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pull.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the real pull once from the network and the backtest**

Run: `lantern pull && lantern backtest && lantern model && lantern status`
Expected: a status table with six `ok` rows, `calibration` meta with `n_months >= 250`, and a probability between 0.01 and 0.99. Record the printed table in `docs/superpowers/plans/notes/first-pull.md`.

- [ ] **Step 6: Commit**

```bash
git add lantern/pull.py lantern/cli.py scripts/demo_morning.sh pyproject.toml tests/test_pull.py docs/superpowers/plans/notes && git commit -m "feat: morning pull, model run, badge and CLI"
```

---

### Task 13: API

**Files:**
- Create: `lantern/api.py`, `tests/test_api.py`

**Interfaces:**
- Consumes: `store.latest_run`, `pull.badge`, `drivers.DRIVERS`, `store.provenance`, `store.load_series`.
- Produces: `create_app(store: Store) -> FastAPI` with
  - `GET /api/monitor` → the latest run payload merged with `badge` and `as_of` (`run_at` in SGT, ISO 8601 with offset). Payload keys: `as_of, badge{state,pulled_at,label}, model{version:"0.3",run_at}, basket{tickers,index_base}, tiles{probability{value,delta_1m,status,spark[24]}, fv_gap{value,low,high,spark}, forward_pe{value,median_10y,spark}, capex_ocf{value,delta_vs_2024,spark}, top10{value,peak_2000:0.27,spark}}, chart{months[37], price[25], fair_value[37], fv_band{low[37],high[37]}, fan{p10,p25,p50,p75,p90 (13 each)}, scenarios{base{path,end_return,prob}, derating{...}, meltup{...}}, window_band, source_line}, triggers[4]{id,label,current,unit,level,distance,effect_pts,text}, drivers[7]{id,label,reading_text,z,contribution_pts,spark[24],change_1m_z}, notes[3]{date,title,text}`. 404 with `{"error":"no run yet"}` when there is no run.
  - `GET /api/drivers/{id}` → `{id,label,weight,source,transform,proxy_before,history[{date,reading,z}], trigger, conditional_drawdown_share}`; 404 for an unknown id.
  - `GET /api/provenance` → `store.provenance(200)`.
  - `GET /api/health` → `{"ok": true}`.
  - Static files from `web/` mounted at `/`, `index.html` as the root.

- [ ] **Step 1: Write the failing tests**

```python
def test_monitor_404_without_run(tmp_store):
    client = TestClient(api.create_app(tmp_store))
    assert client.get("/api/monitor").status_code == 404

def test_monitor_payload_shape(tmp_store, seeded_run):
    client = TestClient(api.create_app(tmp_store))
    body = client.get("/api/monitor").json()
    assert body["badge"]["state"] in {"live", "cached"} and body["as_of"].endswith("+08:00")
    assert len(body["chart"]["months"]) == 37 and len(body["chart"]["fan"]["p50"]) == 13
    assert [d["id"] for d in body["drivers"]] == sorted((d["id"] for d in body["drivers"]), key=lambda i: -next(x["contribution_pts"] for x in body["drivers"] if x["id"] == i))

def test_driver_detail_and_unknown(tmp_store, seeded_run):
    client = TestClient(api.create_app(tmp_store))
    assert client.get("/api/drivers/valuation").json()["weight"] == 0.25
    assert client.get("/api/drivers/nope").status_code == 404

def test_static_index_served(tmp_store, seeded_run):
    client = TestClient(api.create_app(tmp_store))
    assert client.get("/").status_code == 200 and "AI-bubble monitor" in client.get("/").text
```

`seeded_run` saves a run produced by `pull.run_model` on `seeded_all_series` with `last_pull` set to today.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py -v`
Expected: FAIL with ImportError (the static test fails until Task 14 writes `web/index.html`; a placeholder `web/index.html` containing the text "AI-bubble monitor" is created in this task).

- [ ] **Step 3: Implement `lantern/api.py` and the placeholder `web/index.html`**

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add lantern/api.py web/index.html tests/test_api.py tests/conftest.py && git commit -m "feat: FastAPI monitor, driver detail and provenance endpoints"
```

---

### Task 14: Front end: shell, monitor screen, driver panel, placeholders

**Files:**
- Create: `web/styles.css`, `web/app.js`, `web/charts.js`, `web/monitor.js`, `web/placeholders.js`, `web/package.json`, `web/smoke.mjs`
- Modify: `web/index.html`

**Interfaces:**
- Consumes: `GET /api/monitor`, `GET /api/drivers/{id}`, `GET /api/provenance`.
- Produces (JS, all plain functions on `window.Lantern`): `charts.lineFan(el, chart, selectedScenario) -> void` draws the main chart from the `chart` object with one y axis, hairline grid, legend, today rule, fair-value band, fan bands, three scenario paths and end labels; `charts.spark(el, values, color)`; `charts.zbar(el, z)`; `charts.segbar(el, probs)`; `monitor.render(root, payload)`; `monitor.openDriver(id)` loads the detail and renders a right-side panel with the history chart, source, transform, proxy note, weight and the conditional drawdown share; `charts.tableView(el, chart)` toggles a plain table of the chart's series (month, price, fair value, p10, p50, p90) under the chart; `app.route()` maps `#overview` and an empty hash to the monitor, and `#monitor`, `#research`, `#filings`, `#rates`, `#modelrisk`, `#sources`, `#settings` to renderers (`research` and `filings` show a "coming in plan 2/3" placeholder for now); the scenario control calls `charts.lineFan` again with the selected scenario and swaps the scenario sentence; the badge, as-of and model chips in the top bar come from the payload.
- Visual rules carried over from the mock verbatim: tokens, fonts, tile, card, table, pill, chip and segmented-control styles; fonts loaded from Google Fonts with the system sans fallback (self-hosting is a later task).
- `web/smoke.mjs` (puppeteer-core, Google Chrome): starts nothing itself; given `LANTERN_URL`, loads `/#monitor`, asserts the probability tile text matches `/\d{1,2}%/`, that `#main-chart path` count is at least 8, that clicking the "De-rating" button changes the scenario sentence, that clicking the first driver row opens a panel containing "weight", and that there are zero console errors. Exits 1 on any failure.

- [ ] **Step 1: Write the failing smoke test**

Write `web/smoke.mjs` as specified and `web/package.json` with `puppeteer-core` pinned to the version already in the scratch build (`npm ls puppeteer-core` in the PDF scratch folder prints it).

- [ ] **Step 2: Run it to verify it fails**

Run: `lantern serve --port 8787 &` then `cd web && npm install && LANTERN_URL=http://127.0.0.1:8787 node smoke.mjs`
Expected: exit 1, "probability tile not found".

- [ ] **Step 3: Build the front end**

Port the mock: `styles.css` from its `<style>`, `index.html` as the shell with empty module containers, `charts.js` from the mock's inline script generalised to take data, `monitor.js` rendering tiles, chart, triggers, scenario bar, driver table and notes from the payload, `placeholders.js` with the one-paragraph pages (Rates and macro, Model risk, Settings) and the Data sources page rendering `/api/provenance` as a table (name, pulled at SGT, status, SHA-256 prefix).

- [ ] **Step 4: Run the smoke test to verify it passes**

Run: `LANTERN_URL=http://127.0.0.1:8787 node web/smoke.mjs`
Expected: exit 0, prints `smoke ok`.

- [ ] **Step 5: Look at it once**

Run: `node <scratch>/pdfgen/shot.mjs` equivalent, or open `http://127.0.0.1:8787/#monitor` in Chrome at 1440 wide, and compare with the mock side by side. Fix only what differs from the mock or overflows.

- [ ] **Step 6: Commit**

```bash
git add web && git commit -m "feat: monitor front end, driver panel and placeholder pages"
```

---

### Task 15: Runbook, README and the first dry run

**Files:**
- Create: `README.md`, `docs/runbook.md`
- Modify: `scripts/demo_morning.sh`

**Interfaces:**
- Produces: `README.md` with setup (venv, pip, `lantern pull`, `lantern backtest`, `lantern model`, `lantern serve`), the data sources table from the spec with the exact URLs used, and the model summary in one paragraph; `docs/runbook.md` with the demo-day sequence from the spec, the hotspot-first rule, and the cached fallback; `scripts/demo_morning.sh` prints the status table and the badge, then serves.

- [ ] **Step 1: Write `README.md` and `docs/runbook.md`**

- [ ] **Step 2: Dry-run the runbook end to end**

Run: `scripts/demo_morning.sh` on the laptop with the network on, then open `http://127.0.0.1:8787/#monitor`.
Expected: badge reads `Live data · pulled HH:MM SGT`, every tile has a number, the driver panel opens, the smoke test passes against the live server.

- [ ] **Step 3: Dry-run the fallback**

Run: turn wifi off, `lantern pull` (expect six error rows), `lantern serve`, reload.
Expected: badge reads `Cached data · pulled <today>`, the screen is unchanged otherwise.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/runbook.md scripts/demo_morning.sh && git commit -m "docs: runbook, README and dry-run notes"
```

---

## Self-review notes

- Spec coverage: shell (Task 14), data layer and provenance (Tasks 2 to 7, 12), model (Tasks 8 to 10), backtest and ledger seed (Task 11), monitor screen incl. tiles, chart, triggers, scenario bar, driver table, driver detail, notes (Tasks 12 to 14), placeholders incl. Data sources (Task 14), runbook (Task 15). Filings Q&A, Research desk, note generation, PDF export and the gold set are in the next two plans; the ledger rows produced in Task 11 are the Research desk's input.
- Interfaces named consistently: `Store`, `fetch_raw`, `pull_*`, `monthly_readings`, `zscores`, `composite`, `fit_logistic`, `probability`, `contributions`, `trigger_effects`, `fair_value`, `conditional_returns`, `fan`, `scenario_paths`, `scenario_probs`, `run_backtest`, `ledger_rows`, `run_pull`, `badge`, `run_model`, `create_app`.
- Review Focus items 1 to 5 are pinned in Tasks 12, 8, 10, 5 and 8, and 12 and 13 respectively.
