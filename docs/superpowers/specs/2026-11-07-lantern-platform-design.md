# Lantern: AI-bubble monitor, Filings Q&A and Research desk

Design document, 7 November 2026. "Lantern" is a placeholder name until Abhay picks one.

## Intent

Lantern is a research and forecasting workspace built to be shown to OCBC's senior leadership and then piloted inside OCBC Global Markets, which owns Group Research and OCBC Securities. The showcase has one job: make the room believe that a small team can give OCBC the research and forecasting engine it lacks, with numbers that trace to public sources, a model that explains itself, and research that publishes itself. The research behind this (reports/ in this folder) found that OCBC publishes no valuation metric on AI equities, that its research hub is stale next to DBS and UOB, and that no Singapore bank has bought research automation from a vendor.

The first working version is due in three weeks from 7 November 2026, for a showcase that is not yet booked.

## Goals

1. On demo day, open on a live AI-bubble monitor whose numbers were pulled from public data that morning: a 12-month de-rating probability, the AI capex basket against a model fair value with a forecast fan and three scenarios, seven ranked drivers, and the triggers that would change the call.
2. Let the presenter click a scenario and drill into any driver, and let the room ask "why" and get an answer from the screen.
3. Answer questions about SGX annual reports with the verbatim passage, page and filing, or say that the filing does not answer.
4. Publish a dated research note from the model's own numbers, on demand, with charts and sources, exportable to PDF.
5. Hold every screen to the approved look: light, one accent, real product chrome, dated sources on everything, nothing that looks generated.

## Non-goals (for the three-week version)

- No OCBC internal data, systems or credentials. Everything runs on public data.
- No client-facing advice. The product is a research tool for an internal research desk.
- No production hardening: no user management beyond a single shared password, no audit log beyond the provenance records, no mobile layout beyond "does not break".
- No Rates and macro or Model risk modules; they appear in the navigation with a one-paragraph placeholder page.
- No paid data feeds.

## Anti-goals (what would make this a failure even if it technically works)

- A number on screen that cannot be traced to a source, a timestamp and a hash.
- A probability presented as a black box. If the room asks why it is 41%, the driver table must answer.
- Any screen that reads as AI-generated: gradients, glow, decorative icons, centred hero text, invented round numbers.
- A demo that blanks because the conference room has no internet.
- Claims the pitch cannot defend: an "AUC" or "accuracy" figure must come from a backtest that exists and is reproducible.

## Constraints

- Three weeks of build, one builder (Claude working with Abhay).
- Public, free data sources only, pulled over the internet on demo morning.
- The demo runs on Abhay's laptop, shown on a projector or large screen at 1920 by 1080 or wider.
- The design must stay compatible with a later on-premise or Singapore-resident deployment, MAS Notice 658 contract terms, and the MAS Guidelines on AI Risk Management (model inventory, materiality, human oversight, logged prompts and outputs). This shapes the architecture; the three-week version does not implement the controls themselves.
- A shared GPU server is available over SSH (research3@192.168.3.6, Ubuntu 24.04, two RTX A6000 48 GB of which one is free, one RTX 3090, three RTX 2080 Ti, 48 cores, 440 GB RAM, ollama and docker installed). It is used during the build for corpus ingestion and embeddings, the backtest, the gold-set scoring and, as a stretch, serving an open-weight model through ollama behind the same LLM interface for the on-premise story. It is on a private LAN, so demo day still runs from the laptop; the server is never on the demo-day critical path. It is shared with other researchers: work runs in tmux on the free A6000, under ~/Abhay, and nothing large lands on the NAS mount, which is 92% full.
- Reuse the two papers' assets where they fit: the BharatFinQA OCR, chunk and persona-prompt pipeline, scoring harness and judge; FinSafeQA's point-in-time, hash-pinned evidence discipline and abstention protocol.

## The product

### Shell

A single-page web app with a left navigation (Overview, AI-bubble monitor, Research desk, Filings Q&A, Rates and macro, Model risk, Data sources, Settings) and a top bar carrying the workspace name, a breadcrumb, search, the date range, the as-of timestamp, the model version and run time, and a data badge. The badge reads "Live data · pulled 07:12 SGT" after a successful morning pull, "Cached data · pulled 06 Nov" when running from cache, and "Illustrative data" only in the mock. Overview redirects to the AI-bubble monitor for the first version.

The approved mock (`.superpowers/brainstorm/13939-1793999114/content/centre-screen-v2.html` in this folder) is the visual standard: IBM Plex Sans with Plex Mono for figures, a light neutral palette with one blue accent, status colours reserved for status, hairline borders, cards only where an element needs separating. A dark theme is out of scope for three weeks.

### AI-bubble monitor (the centre screen)

Layout as in the mock, top to bottom:

1. Header: title, the basket's tickers, a scenario control (Base, De-rating, Melt-up).
2. Five stat tiles: 12-month de-rating probability with status pill and one-month change; price versus model fair value with its 80% range; basket forward P/E against the 10-year median; hyperscaler capex to operating cash flow; top-10 weight in the S&P 500. Each tile carries a 24-month sparkline.
3. The main chart: basket price indexed to 100 at the start of the window, the model fair value with a plus or minus 7% band, a vertical "today" rule, the forecast fan (25 to 75 and 10 to 90 percentiles) and three labelled scenario paths ending at their 12-month level and probability. The chart has one axis, hairline grid, a legend, a source line, the model run time and a table-view toggle.
4. "What would change the call": four trigger rows, each with the current reading, the trigger level, a distance bar and a one-line statement of the effect on the probability; then a thin segmented bar of the three scenario probabilities.
5. The driver table: seven rows ranked by contribution, with the current reading, a z-score bar against the driver's own 10-year history, the contribution in probability points, a 24-month sparkline and the one-month change. Clicking a row opens a driver detail panel: the full history chart, the data source, the last pull time, the transformation applied and the weight.
6. Model notes: the three most recent dated entries from the run log.

The scenario control highlights one of the three paths and swaps the scenario sentence under the chart; it changes no probability and no driver. The headline number and the scenario bar are one object: the de-rating probability on the tile is the model's estimate of a 25% or larger drawdown within 12 months, the de-rating segment of the bar is that same number, the melt-up segment is the estimated probability of a 20% or larger gain, and base is the remainder.

### Filings Q&A

A question box over a corpus of SGX annual reports, with the corpus listed beside it (company, filing, year, pages, date ingested, SHA-256). The answer area shows: a two-to-four-sentence answer; one to three evidence cards, each with the verbatim passage, the filing, the page number and a link that opens the PDF at that page; a confidence label; and, when the corpus does not answer, the sentence "The filings in this corpus do not answer this" with the nearest passages shown as context, never as an answer. A history rail keeps the session's questions.

Demo corpus: the 2025 annual reports of OCBC, DBS and UOB, plus five large STI companies chosen by Abhay (builder default if none chosen: Singtel, SGX, Keppel, CapitaLand Investment, Sembcorp). The corpus must be rebuildable from the PDFs with one command.

### Research desk

A feed of dated notes, newest first, each with a title, a one-line summary, the status (Draft, Published), the model run it came from and a PDF link. Opening a note shows it as a formatted research note: title, author line ("Lantern model, reviewed by Abhay"), as-of date, the lead paragraph, the main chart, the driver table, the triggers, the scenario sentence and a sources section listing every series with its source, pull time and hash. A "Generate today's note" button runs the generation live. "Export PDF" produces the file through the existing print pipeline.

The desk also carries the accuracy ledger: one row per past note with the forecast made, the horizon, what the basket then did, and whether the call was inside the fan. On day one the ledger is filled from the backtest, each row marked "backtest", and live rows accrue from launch.

### Placeholders

Rates and macro, Model risk, Data sources and Settings show a titled page with one paragraph saying what the module will do and which research finding it answers. Data sources additionally lists the live source table with the last pull status, because it costs nothing and shows provenance.

## Data layer

One module pulls every series on demand, writes the raw response to disk with a UTC timestamp and SHA-256, normalises it into a tidy table, and records the pull in a provenance log. The app only ever reads the normalised cache, so a failed pull leaves yesterday's numbers on screen with the badge changed, never a blank.

| Series | Source | Notes |
| --- | --- | --- |
| Daily prices, forward P/E (context only), market cap for the basket (NVDA, MSFT, GOOGL, AMZN, META, AVGO, TSM, ORCL) | Yahoo Finance via the yfinance library | Unofficial feed; the pull retries and falls back to Stooq for prices; forward P/E has no history and is never a driver |
| Net income and shares outstanding, quarterly, for all eight basket names | SEC EDGAR XBRL company-facts API (TSM through its 20-F facts where available, otherwise Yahoo trailing EPS, disclosed) | Gives the basket's trailing P/E history for the valuation driver and fair value |
| Capex and operating cash flow, quarterly, for the hyperscalers (MSFT, GOOGL, AMZN, META, ORCL) | SEC EDGAR XBRL company-facts API | Tags: PaymentsToAcquirePropertyPlantAndEquipment, NetCashProvidedByUsedInOperatingActivities; trailing four quarters; history from 2009 |
| Net debt, quarterly, same companies | SEC EDGAR company-facts | Replaces the AI-linked bond issuance idea, which has no free feed |
| Top-10 weight in the S&P 500 | State Street SPY daily holdings file for today; constituent market caps from Yahoo prices and EDGAR shares for the history | Sum of the top ten weights; the reconstructed history is disclosed as such |
| US 10-year real yield, fed funds, high-yield spread, Fed balance sheet | FRED (DFII10, DFF, BAMLH0A0HYM2, WALCL) | CSV download, no key needed |
| Put/call ratio | CBOE daily market statistics | Equity put/call |
| AAII bull-bear spread | AAII weekly sentiment survey | Weekly |
| Analyst upgrades and downgrades for the basket | Yahoo Finance via yfinance | Trailing 90 days, counted across the eight names |
| Long history for calibration | FRED series above, Shiller monthly data from Yale, Nasdaq-100 and S&P 500 history via yfinance | Used by the backtest and the 2000 analogue only |

Every pull is idempotent and dated, so a morning pull can be re-run without side effects. The long history is pulled once and cached.

## The model

The model is a transparent composite, not a learned black box, because a black box cannot answer "why" in the room and would not survive Model Risk.

1. **Driver scores.** Each driver is a z-score of its current reading against its own trailing 10-year monthly history, sign-adjusted so that positive means more bubble risk. Every driver is built only from series with a free history, so the live composite and the backtest use the same definitions. Valuation stretch uses the basket's trailing P/E, computed from EDGAR net income and shares outstanding against Yahoo prices, with the Nasdaq-100 trailing P/E (Shiller and index data) as the disclosed proxy before the basket's own history begins. Forward P/E from Yahoo is shown on the tile as context only; it is not a driver, because it has no free history. Capex intensity uses capex over trailing operating cash flow. Concentration uses the top-10 weight, with today's value from the SPY holdings file and the history reconstructed from constituent market caps (Yahoo prices times EDGAR shares outstanding) against the S&P 500 total, which the driver detail panel discloses. Leverage and credit combines net debt change with the high-yield spread (spread tightening while debt rises scores as risk). Positioning combines put/call and the AAII spread. Earnings revisions use the upgrade share of analyst actions, inverted. Rates and liquidity combine the real yield and the Fed balance sheet change.
2. **Composite.** A weighted sum of the seven z-scores with fixed, disclosed weights (valuation 25%, capex 20%, concentration 15%, leverage 15%, positioning 10%, revisions 10%, rates 5%). Weights are a design choice shown on screen; nothing hides them.
3. **Probability.** The 12-month de-rating probability is a logistic function of the composite, calibrated so that the historical composite reproduces the frequency of 12-month drawdowns of 25% or more in the Nasdaq-100. The calibration window is 2003 to 2026, the span over which every driver has a free history (FRED's real yield starts in 2003, the high-yield spread in 1997, the Fed balance sheet in 2002, EDGAR XBRL facts in 2009 with the Nasdaq-100 proxy before that); it contains the 2008 and 2022 episodes and the non-episodes between. The 2000 episode is shown as an out-of-sample analogue using only the valuation and rates drivers, which have Shiller and FRED histories back to 1990, and is labelled as such. The pitch therefore says "calibrated on 2003 to 2026, checked against 2000", never "since 1990". The calibration is a two-parameter fit; its curve and its hit rate are shown on the Model risk placeholder page later and in the accuracy ledger now.
4. **Fair value.** Fair value is the basket's trailing-twelve-month earnings multiplied by the 10-year median trailing P/E adjusted for the real yield (a one-factor earnings-yield model). The band is plus or minus 7%, which is the model's historical absolute error. The gap between price and fair value is reported with an 80% range from the band.
5. **Forecast fan and scenarios.** The fan is drawn from the historical distribution of 12-month returns conditional on the composite being within one point of today's value (2003 to 2026, proxy-extended as above); its median is the base path. The de-rating path ends at a 25% drawdown and the melt-up path at a 20% gain, the two events whose probabilities the bar shows, so the three paths and the three probabilities describe the same thing. The melt-up probability is the conditional mass above a 20% gain; the de-rating probability is the calibrated logistic estimate from item 3, which is the headline; base is one minus the two. Where the conditional mass below a 25% drawdown disagrees with the logistic estimate, the driver detail panel shows both figures, because two estimators of one event that disagree are a finding, not a bug.
6. **Triggers.** Each trigger is a driver threshold with a stated effect: the probability recomputed with that driver at its trigger level. Four are shown on screen; all seven exist.
7. **Backtest and ledger.** The composite is computed monthly from 2003 on the same definitions as the live model, with the 2000 analogue from the two long-history drivers kept separate; each month's probability is compared with the realised 12-month outcome; the hit rate, Brier score and calibration table are stored and the ledger is seeded from them. No figure appears in the UI that this backtest did not produce.

Contributions in the driver table are each driver's weighted z-score mapped through the logistic slope at today's composite, in probability points, so the seven contributions sum to the probability minus the baseline.

## Filings Q&A pipeline

Ingestion: PDF to text per page with FinSafeQA's PyMuPDF ingest, because SGX annual reports are born-digital and the BharatFinQA OCR is a vision-model service on a GPU box that the demo must not depend on; the BharatFinQA chunker and persona prompts are reused. Chunks are tagged with company, filing, year and page, embedded with a local embedding model, and stored with the PDF's SHA-256. Retrieval: hybrid BM25 and embedding search, top eight chunks. Answering: Claude through the Anthropic API with a prompt that allows an answer only when it is supported by quoted evidence, returns the evidence spans verbatim with page numbers, and otherwise returns the abstention sentence. Every question, retrieved chunk set, prompt and answer is logged with timestamps, which is the record the MAS guidelines ask for.

Internet in the room: Filings Q&A and note generation call the Anthropic API, so they need a connection. The demo connection is the laptop on a phone hotspot, with the venue wifi as the backup, not the other way round. As a second line, the morning run pre-answers a prepared list of 20 questions and caches the answers and evidence, so the walkthrough survives a dead connection; only ad-hoc questions from the room need the API. A local open-weight model behind the same interface is the later swap and is not on the three-week path. Evaluation: a 40-question gold set written by Abhay over the demo corpus (30 answerable, 10 unanswerable), scored with the BharatFinQA judge, reported on the Model risk placeholder and used as the release gate: no demo if abstention precision is below 90%.

## Research desk generation

A note is produced from a fixed structure: the model run's JSON (probability, change, drivers, triggers, scenarios, fair value, sources) fills a template; Claude writes the lead paragraph and the driver commentary from that JSON and nothing else, with every number in the prose required to appear in the JSON (a post-check rejects the draft otherwise). Charts are rendered from the same JSON by the app's own chart code and embedded as SVG. The PDF export reuses the Chrome print pipeline in reports/build-pdf.mjs. Notes are stored with the run they came from so they can be regenerated bit for bit.

## Architecture and stack (builder's calls)

- **Backend**: Python 3.12, FastAPI, served by uvicorn on the laptop. One process. Endpoints: run the morning pull, compute the model, serve the monitor JSON, answer a filings question, generate and export a note, list provenance.
- **Storage**: SQLite for provenance, runs, notes and the question log; Parquet files for series; the raw pull responses on disk under data/raw/<date>/.
- **Front end**: plain HTML, CSS and JavaScript, no framework and no build step, structured as one page per module with shared chart code. The mock already contains the shell, the tile, the chart and the table; the build turns them into components fed by JSON.
- **LLM**: the Anthropic API, model chosen at build time from the API reference, with prompts and outputs logged. A local open-weight model is a later swap behind the same interface, which is the on-premise story for the pitch.
- **Charts**: hand-drawn SVG following the data-viz rules already applied in the mock (one axis, hairline grid, thin marks, legend for more than one series, tooltips and a table view).
- **Scheduling**: a single `lantern pull` command run by hand on demo morning; no scheduler in the three-week version.
- **Repository**: this folder becomes a git repository at build start, with the research notes, reports and specs kept alongside the code under docs/.

## Prerequisites

- An Anthropic API key with billing enabled, used for Filings Q&A, note generation and the prompt and output log.
- Access to the judge used to score the gold set (see Open questions).
- The eight demo PDFs downloaded from the companies' investor pages into data/filings/.

## Demo-day runbook

1. 06:30, hotel or home wifi: run the morning pull. It writes the cache and prints a status table of every series with its timestamp.
2. Run the model, generate the day's note and pre-answer the prepared question list. Check the probability and the note once by eye.
3. Start the app, open the monitor, walk the three modules once.
4. In the room: the app runs from the laptop's cache; the badge reads "Live data · pulled 06:4x SGT". If anything is wrong with the pull, the previous day's cache serves with the badge changed, and the pitch says so.

## Decided by Abhay

- The centre screen opens the demo and shows an AI-bubble forecast with its drivers, in the look of the approved mock.
- The numbers are pulled live from public data on demo morning.
- Filings Q&A and Research desk must work on demo day; the rest are labelled entries.
- Three weeks for the first working version; the showcase is not booked.
- The gold set is drafted by the builder and verified by Abhay by day 10; both API accounts are available.

## Left to the builder

- Exact data transformations and the splice between basket and proxy history, as long as they are disclosed on the driver detail panel.
- The weights of the composite within the stated values, and the calibration fit.
- The embedding model and chunk sizes for Filings Q&A.
- The five STI companies in the demo corpus, if Abhay does not choose.
- Page layout for the driver detail panel and the note view, within the approved look.

## Resolved after the builder check

1. Gold set: the builder drafts the 40 questions with evidence by day 7; Abhay verifies and corrects them by day 10 (about two hours). The pitch notes that the set was model-drafted and human-verified.
2. Accounts: an Anthropic API key with billing and an OpenRouter key are both available, so Filings Q&A and note generation run on the Anthropic API and the gold set is scored by the same DeepSeek-V4-Pro judge the BharatFinQA paper pinned.
