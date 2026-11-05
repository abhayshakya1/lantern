# Lantern

An AI-bubble monitor for OCBC Group Research: a 12-month de-rating probability for the AI capex basket, the basket against a model fair value with a forecast fan and three scenarios, seven ranked drivers scored against their own ten-year history, and the triggers that would change the call. Every number on screen comes from public data pulled over the internet, with the raw response, its timestamp and its SHA-256 kept on disk. Filings Q&A and the Research desk arrive in the next two plans; their navigation entries are labelled placeholders.

## Setup

```bash
python3.13 -m venv ~/.venvs/lantern
source ~/.venvs/lantern/bin/activate
pip install -e . pytest ruff
export FRED_API_KEY=...           # free key from https://fredaccount.stlouisfed.org/apikeys, or put FRED_API_KEY=... in ~/lantern/.env (git-ignored)
export LANTERN_DATA=./data        # default; raw files, Parquet series and lantern.db live here
```

Then, in order:

```bash
lantern pull        # every public feed; prints a status row per source, errors do not stop the others
lantern backtest    # monthly composite 2003 to today, calibration, hit rate, Brier, ledger seed
lantern model       # today's run: probability, fair value, fan, scenarios, triggers, drivers
lantern status      # the status table of the last pull and the data badge
lantern serve --port 8787   # FastAPI on 127.0.0.1:8787 serving the API and the web app
```

Open `http://127.0.0.1:8787/#monitor`. `scripts/demo_morning.sh` runs the four steps and serves; see `docs/runbook.md`.

Without `FRED_API_KEY` the FRED pull uses the public CSV endpoint, which times out from Python on some networks. Without FRED the rates and leverage drivers show "no reading" and fair value falls back to the plain ten-year median multiple; the driver panel and the fair-value tile say so.

## Data sources

| Series | Source | URL used | Notes |
| --- | --- | --- | --- |
| Monthly prices and split history for the basket (NVDA, MSFT, GOOGL, AMZN, META, AVGO, TSM, ORCL), twenty large caps, ^NDX and ^GSPC; forward P/E, market cap and trailing EPS; analyst actions over 90 days | Yahoo Finance via yfinance | `https://finance.yahoo.com/quote/{ticker}` (yfinance calls the query endpoints behind it) | Unofficial feed. Prices are split-adjusted, so filed share counts are restated for later splits before any market cap is formed. Forward P/E has no history and is context only. |
| Net income, shares outstanding, capex, operating cash flow, cash and debt, quarterly, for the basket, the hyperscalers and the large caps | SEC EDGAR XBRL company facts | `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` | Tag fallbacks per company are written to the store's meta table. Share counts are screened for cover-page scale errors and go stale after two years. TSM files annual 20-F facts only, in TWD, so it is excluded from the basket P/E and, as a non-constituent, from the top-10 history; both are said on the driver panel. |
| Real yield DFII10, fed funds DFF, Baa credit spread BAA10Y (Moody's Baa yield over the 10-year Treasury; FRED serves the ICE BofA high-yield spread only from November 2023), Fed balance sheet WALCL | FRED | `https://api.stlouisfed.org/fred/series/observations` with the key, else `https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}` | The key travels as a query parameter and never enters the provenance log. |
| Top-10 weight in the S&P 500 | State Street SPY daily holdings | `https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx` | Today's value from the file; the history is reconstructed from 28 large caps against the index and rescaled onto the file's level, which the driver panel discloses. |
| AAII bull-bear spread | AAII sentiment survey | `https://www.aaii.com/files/surveys/sentiment.xls` | Weekly, averaged by month. The CBOE put/call series was dropped: no free history. |
| S&P 500 P/E, long rate and earnings since 1871 | Robert Shiller's online data | `https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/downloads/ie_data.xls` | Proxy for valuation and earnings momentum before the basket's own history; the file ends in mid-2024. |

Every pull is idempotent: the raw file lands under `data/raw/<date>/`, the tidy series under `data/series/`, and a provenance row (name, URL, SHA-256, status, UTC time) in `data/lantern.db`. The app only reads the tidy cache, so a dead feed leaves the previous numbers on screen with the badge changed.

## The model

Seven drivers, each a z-score of the current reading against its own trailing ten-year monthly history (at least 24 months), signed so that positive means more bubble risk: valuation stretch (basket trailing P/E from EDGAR earnings and split-adjusted shares against Yahoo prices, seven names with TSM excluded, Shiller S&P P/E before 2016), capex intensity (hyperscaler trailing capex over operating cash flow), index concentration (top-10 weight), leverage and credit (12-month change in hyperscaler net debt against the high-yield spread), positioning (AAII spread), earnings momentum (three-month change in basket trailing earnings, inverted, Shiller before the basket history) and rates (10-year real yield). The composite is the weighted sum with fixed, displayed weights of 25/20/15/15/10/10/5. The 12-month de-rating probability is a logistic function of the composite, fitted by penalised maximum likelihood on 2003 to today against 25% drawdowns within twelve months on the Nasdaq-100, with the slope floored at zero and a weak prior; the 2000 episode is an out-of-sample analogue from the two long-history drivers. Fair value is trailing earnings times the ten-year median trailing P/E adjusted by 10% per percentage point of real yield, with a 7% band. The fan is the historical distribution of 12-month returns in months whose composite was within one point of today's; its median is the base path, the de-rating path ends at a 25% drawdown and the melt-up path at a 20% gain, and the three probabilities on the bar describe those same three paths. Triggers recompute the probability with one driver moved to its threshold. The backtest stores the Brier score against the base-rate Brier, the calibration table and the hit rate, and nothing appears on screen that it did not produce; the fit is in-sample and the footer says so. When the fitted slope sits at its floor of zero, the screen says that no driver moves the probability and ranks the table by z-score instead. Model outputs are research inputs, not advice.

## Tests

```bash
pytest -q                      # unit tests on fixtures, no network
pytest -q -m network           # the live-feed checks
cd web && npm install && LANTERN_URL=http://127.0.0.1:8787 npm run smoke   # browser smoke test against a running server
```

## Layout

```
lantern/            config, store, sources/ (fred, yahoo, edgar, spy, sentiment, shiller), drivers, model, backtest, pull, api, cli
web/                index.html, styles.css, charts.js, monitor.js, placeholders.js, app.js, smoke.mjs
scripts/            demo_morning.sh
docs/               runbook.md, superpowers/ (spec and plans)
tests/              pytest suite and fixtures
```
