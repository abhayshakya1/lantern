# Lantern

**A research and forecasting workspace that turns public market data and primary filings into
defensible, auditable research — end to end on infrastructure you control.**

Lantern pulls live public data each morning, computes a calibrated AI-equity de-rating probability,
answers questions from primary filings with verbatim page-cited evidence, writes the day's research
note from the model's own numbers, and keeps score on itself. Every figure on screen traces to a
named source, a pull time and a SHA-256.

| Module | What it does | Honesty mechanism |
|---|---|---|
| **AI-bubble monitor** | 12-month de-rating probability for the AI capex basket, fair value, forecast fan, scenarios, triggers | Only the three drivers with real signal are calibrated; four are labelled watch indicators. The fit window, hit rate and Brier vs base rate print on the page. |
| **Filings Q&A** | Questions over eight SGX annual reports (~6,800 indexed passages) | Answers ship only with quotes that are verbatim in the filing, cited to the page; otherwise one fixed abstention sentence. Refusal behaviour is measured, with a hard gate. |
| **Research desk** | A dated note per model run: lead, chart, drivers, triggers, sources, PDF export | Every number in the prose must appear in the run's JSON or the draft is rejected; an accuracy ledger scores every past forecast in public. |
| **Model risk** | The governance page | Gold-set scores and abstention gate; champion–challenger fan coverage (in-house 77% vs TimesFM 2.5 zero-shot 50% over 252 walk-forward months). |

**On-premise by design:** retrieval (bge + BM25), generation (Qwen2.5 behind the same interface as
the cloud model — `LANTERN_LLM_URL` swaps them), judging (local judge through the vendored
BharatFinQA harness) and the TimesFM 2.5 challenger all run on local hardware. The cloud model is
optional and labelled when used.

## Setup

```bash
uv sync                              # Python 3.12+; `uv sync --extra challenger` adds the TimesFM fan
uv run lantern pull                  # every public feed; a dead feed never stops the others
uv run lantern backtest              # calibration 2003→today, hit rate, Brier, ledger seed
uv run lantern model                 # today's run: probability, fair value, fan, triggers, drivers
uv run lantern note                  # the day's research note from that run
uv run lantern challenger            # TimesFM challenger fan (--backtest adds coverage)
uv run lantern serve                 # http://127.0.0.1:8787
```

Secrets live in a git-ignored `.env`: `FRED_API_KEY` (free) for the rates feeds;
`ANTHROPIC_API_KEY` only if the cloud answerer is wanted; `LANTERN_LLM_URL` /
`LANTERN_LLM_MODEL` to answer with the on-prem model instead. `scripts/demo_morning.sh` runs the
whole morning sequence and serves.

## Data sources

| Series | Source | URL used | Notes |
| --- | --- | --- | --- |
| Monthly prices and split history for the basket (NVDA, MSFT, GOOGL, AMZN, META, AVGO, TSM, ORCL), twenty large caps, ^NDX and ^GSPC; forward P/E, market cap and trailing EPS; analyst actions over 90 days | Yahoo Finance via yfinance | `https://finance.yahoo.com/quote/{ticker}` (yfinance calls the query endpoints behind it) | Unofficial feed; see THIRD_PARTY_NOTICES.md on data terms. Prices are split-adjusted, so filed share counts are restated for later splits before any market cap is formed. Forward P/E has no history and is context only. |
| Net income, shares outstanding, capex, operating cash flow, cash and debt, quarterly, for the basket, the hyperscalers and the large caps | SEC EDGAR XBRL company facts | `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` | Tag fallbacks per company are written to the store's meta table. Share counts are screened for cover-page scale errors and go stale after two years. TSM files annual 20-F facts only, in TWD, so it is excluded from the basket P/E and, as a non-constituent, from the top-10 history; both are said on the driver panel. |
| Real yield DFII10, fed funds DFF, Baa credit spread BAA10Y, Fed balance sheet WALCL | FRED | `https://api.stlouisfed.org/fred/series/observations` with the key, else the public CSV endpoint | The key travels as a query parameter and never enters the provenance log. |
| Top-10 weight in the S&P 500 | State Street SPY daily holdings | `https://www.ssga.com/.../holdings-daily-us-en-spy.xlsx` | Today's value from the file; the history is reconstructed from 28 large caps against the index and rescaled onto the file's level, which the driver panel discloses. |
| AAII bull-bear spread | AAII sentiment survey | `https://www.aaii.com/files/surveys/sentiment.xls` | Weekly, averaged by month. |
| S&P 500 P/E, long rate and earnings since 1871 | Robert Shiller's online data | `ie_data.xls` | Proxy for valuation and earnings momentum before the basket's own history. |

Every pull is idempotent: the raw file lands under `data/raw/<date>/`, the tidy series under
`data/series/`, and a provenance row (name, URL, SHA-256, status, UTC time) in `data/lantern.db`.
The app reads only the tidy cache, so a dead feed leaves the previous numbers on screen with the
badge changed.

## The model

Seven drivers, each a z-score of the current reading against its own trailing ten-year monthly
history, signed so that positive means more bubble risk: valuation stretch, capex intensity, index
concentration, leverage and credit, positioning, earnings momentum and rates. The composite is a
weighted sum with fixed, displayed weights; the probability is calibrated on the three drivers with
in-sample signal (valuation, concentration, leverage) by penalised maximum likelihood on 2003→today
against 25% Nasdaq-100 drawdowns within twelve months. Fair value is trailing earnings times the
ten-year median multiple with a real-yield adjustment; the fan is the historical distribution of
12-month returns in comparable-composite months. Triggers recompute the probability with one driver
at its threshold. The backtest stores the Brier score against the base rate, the calibration table
and the hit rate; the fit is in-sample and the footer says so. A TimesFM 2.5 challenger forecasts
the same series zero-shot and is scored on identical months. Model outputs are research inputs, not
advice.

## Filings Q&A

```bash
python scripts/fetch_filings.py    # the PDFs named in data/filings/manifest.json
uv run lantern filings build       # page-aware chunks with header-paired table rows, local embeddings
uv run lantern filings ask "What was OCBC's net profit for 2025?"
uv run lantern filings pre-answer  # caches the prepared questions; demo morning runs this
uv run lantern filings gold-draft  # drafts the gold set for human verification
uv run lantern filings eval --gold data/filings/gold/gold.jsonl
```

Retrieval is hybrid BM25 + embeddings fused by reciprocal rank. A quote is kept only when it is a
verbatim substring of the chunk it names; an answer with no surviving quote becomes an abstention.
Evaluation runs the vendored BharatFinQA harness; the judge is local
(`scripts/local_model/judge_server.py`) so no external API is needed. Release gate: no demo if
abstention precision on the verified gold set is below 90%.

## Tests

```bash
uv run --with pytest pytest -q                  # unit tests on fixtures, no network
uv run --with pytest pytest -q -m network       # live-feed checks
cd web && node smoke.mjs                        # browser smoke test against a running server
```

## Layout

```
lantern/            config, store, sources/, drivers, model, backtest, pull, challenger, api, cli
lantern/filings/    corpus, retrieve, answer, local_llm, evaluate (+ vendored bfq harness)
lantern/research/   note generation with the number post-check, accuracy ledger
web/                plain HTML/CSS/JS front end, no build step; smoke.mjs
scripts/            demo_morning.sh, fetch_filings.py, local_model/ (fine-tune + bench + judge)
demo/               scripted HD demo-video kit (scenes, recorder, narration, assembly)
docs/               specs, implementation plans, execution ledgers, scorecards
tests/              pytest suite and fixtures
```

## License

Proprietary — see [LICENSE](LICENSE). Third-party components and data-source terms are catalogued
in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md); read its attention items (PyMuPDF AGPL,
market-data terms) before any commercial deployment.
