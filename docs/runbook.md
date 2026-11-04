# Demo-day runbook

The app runs from the laptop. The GPU server is never on the demo-day path.

## Connection: hotspot first

The laptop runs on a phone hotspot. The venue wifi is the backup, not the other way round: a venue network that blocks or throttles Yahoo, SEC or FRED fails silently, and the hotspot is the connection that was tested the night before. Filings Q&A and note generation (next plans) call the Anthropic API and need the connection too; the monitor itself needs it only for the morning pull.

## The morning

1. **06:30, hotel or home wifi, then switch to the hotspot before the room.** Run the morning script:

   ```bash
   cd ~/lantern && source ~/.venvs/lantern/bin/activate && export FRED_API_KEY=...
   scripts/demo_morning.sh --port 8787
   ```

   It pulls every feed, re-runs the backtest and the model, prints the status table and the badge, and serves. A feed that fails prints an `error` row and does not stop the others. Expect about three minutes.

2. **Read the status table.** Every row `ok`, badge `Live data · pulled HH:MM SGT`. One row `error` is survivable: the previous pull of that feed serves and the badge says `· 1 feed missing`. Six rows `error` means no connection; see the fallback below.

3. **Check the run once by eye.** Open `http://127.0.0.1:8787/#monitor`. Every tile has a number, the chart has the price, the fair-value band, the fan and three scenario paths, the four triggers read sensibly, the driver table has seven rows and a row click opens the panel. The probability and the fair-value gap should be in the neighbourhood of the previous day's; a jump of more than ten points means a feed changed shape, so read the model notes and the Data sources page before trusting it.

4. **Walk the modules once** so the browser cache is warm and the fonts are loaded before the room.

## The cached fallback

If the pull fails entirely, nothing on screen changes except the badge. The store keeps the last good pull; the model and the serve steps run on it. The badge reads `Cached data · pulled DD Mon` when the last good pull was on an earlier day, or `Live data · pulled HH:MM SGT · n feeds missing` when it was earlier today and only some feeds failed. The pitch says so in one line ("these numbers were pulled yesterday morning; the pull re-runs in a minute on any connection") and moves on. Do not retry pulls in the room: `lantern pull` is idempotent and safe, but it takes three minutes and the screen is already right.

If the laptop was never pulled on this machine, the badge reads `No data pulled yet` and the monitor shows "No model run yet": run the three commands in the README.

## Troubleshooting

- **FRED `error`**: the public CSV endpoint times out from Python on some networks. Set `FRED_API_KEY` (free) and re-run `lantern pull`. Without FRED the rates and leverage drivers show "no reading" and fair value uses the plain median multiple; the driver panel and the fair-value tile say so.
- **Yahoo `error` or empty series**: yfinance is rate-limited and sometimes blocked on hotel networks. Switch to the hotspot and re-run; the previous prices serve meanwhile.
- **SSGA or AAII `error`**: the files move or change layout a few times a year. The previous top-10 weight or sentiment reading serves; the Data sources page shows the failed URL.
- **Port in use**: `scripts/demo_morning.sh --port 8788` and open that port instead.
- **Fonts missing**: IBM Plex loads from Google Fonts; offline, the page falls back to the system sans-serif and stays readable.

## Dry runs

Recorded here after each rehearsal, newest first.

### 7 Nov 2026, laptop on home wifi, no FRED key yet

- **Live run.** `scripts/demo_morning.sh --port 8788` was serving after 160 seconds. Status table: five feeds `ok`, FRED `error` (no API key; the CSV endpoint times out from Python). Badge `Live data · pulled 13:56 SGT · 1 feed missing`. Probability 7%, fair-value gap −1%, every tile filled, driver panel opens, browser smoke test passed against the live server.
- **Fallback.** Wifi was not switched off (shared machine); `lantern pull` ran through a dead proxy instead, so every fetch failed, which is the same code path. The first attempt found a defect: the Yahoo and EDGAR pulls swallow per-ticker failures and reported `ok` with zero series, so the badge claimed a live pull that had fetched nothing. Fixed: a source that returns no series now counts as an error (`test_source_returning_no_series_counts_as_error`). After the fix, six `error` rows, the previous pull stands, the screen is unchanged and the smoke test passes.
- **Open before the next rehearsal.** Set `FRED_API_KEY`; until then the rates and leverage drivers read "no reading".
- **After the whole-branch review (same day).** The review found the share counts behind the valuation and concentration histories unadjusted for splits, so the backtest had been fitted on a corrupted history; fixed, re-pulled and re-run (see `docs/superpowers/plans/notes/first-pull.md` for the before and after).
