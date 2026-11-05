# First pull, 2026-11-07T05:17Z

```
source                 status  series  detail
pull_fred              error        0  fred.DFII10: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443)
pull_yahoo_all         ok         142  
pull_edgar_all         ok         168  
pull_spy               ok           1  
pull_sentiment         ok           1  
pull_shiller           ok           3  
badge: No data pulled yet
```

## Second pull, 2026-11-07T05:20Z
```
source                 status  series  detail
pull_fred              error        0  fred.DFII10: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443)
pull_yahoo_all         ok         142  
pull_edgar_all         ok         168  
pull_spy               ok           1  
pull_sentiment         ok           1  
pull_shiller           ok           3  
badge: No data pulled yet
```

## Backtest and model on the first pull (FRED missing), 2026-11-07T05:26Z
```
calibration 2003-01 to 2026-11: a=-2.628 b=0.170 n=275 hit rate 0.93 brier 0.064
2000 analogue: {'drivers': ['valuation', 'rates'], 'probability_peak': 0.10282329132712505, 'date_peak': '2001-12-31', 'note': 'valuation and the long rate only, weights renormalised; out of sample'}
    print(f"probability {t['value']:.0%} ({t['status']}), fair-value gap {run['tiles']['fv_gap']['value']:+.0%}, run {run['model']['run_at']}")
                                                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: unsupported format string passed to NoneType.__format__
source                 status  series  detail
pull_fred              error        0  fred.DFII10: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443)
pull_yahoo_all         ok         142  
pull_edgar_all         ok         168  
pull_spy               ok           1  
pull_sentiment         ok           1  
pull_shiller           ok           3  
badge: No data pulled yet
```

## Model run on the first pull, 2026-11-07T05:28Z
```
probability 7% (calm), fair-value gap n/a, run 2026-11-07T13:28:19.337941+08:00
```

## Backtest and model after the dtype and revisions fixes, 2026-11-07T05:32Z
```
calibration 2003-01 to 2026-11: a=-2.467 b=-0.639 n=275 hit rate 0.93 brier 0.064
2000 analogue: {'drivers': ['valuation', 'rates'], 'probability_peak': 0.06883537367200747, 'date_peak': '2001-03-31', 'note': 'valuation and the long rate only, weights renormalised; out of sample'}
probability 5% (calm), fair-value gap n/a, run 2026-11-07T13:32:43.827564+08:00
```

## After EDGAR fallbacks and concentration rescale, 2026-11-07T05:36Z
```
calibration 2003-01 to 2026-11: a=-2.651 b=-3.166 n=275 hit rate 0.93 brier 0.061
2000 analogue: {'drivers': ['valuation', 'rates'], 'probability_peak': 0.03442538662617283, 'date_peak': '2001-03-31', 'note': 'valuation and the long rate only, weights renormalised; out of sample'}
probability 1% (calm), fair-value gap -1%, run 2026-11-07T13:36:57.941102+08:00
```

## With the slope floor and prior, 2026-11-07T05:40Z
```
calibration 2003-01 to 2026-11: a=-2.601 b=0.000 n=275 hit rate 0.93 brier 0.064
2000 analogue: {'drivers': ['valuation', 'rates'], 'probability_peak': 0.06909092332113638, 'date_peak': '1998-01-31', 'note': 'valuation and the long rate only, weights renormalised; out of sample'}
probability 7% (calm), fair-value gap -1%, run 2026-11-07T13:40:50.561915+08:00
```

## After the whole-branch review fixes, 2026-11-07T06:36Z (14:36 SGT)

Pull: split histories saved for 19 names (`yahoo.splits.<T>`); EDGAR partial (XOM failed once, its previous facts serve, badge says "1 feed partial"); FRED still missing (no API key).

- NVDA market cap is continuous across the 10:1 split of June 2024: 2,697bn (May 2024), 3,039bn (Jun), 2,879bn (Jul), 2,928bn (Aug); 405bn in May 2021 (was 10bn under the unadjusted share counts).
- Concentration history: first reading 2009-10 (needs 20 names), no zeros, Oct 2012 = 19.4% (ORCL's 4.8e15 cover-page count is screened out), peak 38.7%.
- Basket trailing P/E (seven names, TSM excluded): 35.0× (end 2016), 41.8× (2020), 36.4× (2025), 21.5× today; cross-checked name by name against Yahoo's market-cap and trailing-EPS snapshots (basket 21.5× against 21.7×). The fall through 2026 is earnings: GOOGL booked 62.6bn and 112.2bn quarters and AMZN 30.3bn and 62.6bn in the first half of 2026 against roughly 35bn and 21bn a year earlier, while prices came off their peak. Ten-year median 36.5×, so the fair-value gap on the plain median multiple (no real yield) is −41%.
- Calibration: a = −2.601, b = 0.000 (at the floor), 275 months, 19 label months (Oct 2007 onward and Dec 2021 to Mar 2022), Brier 0.064 against 0.064 for the base rate. The composite is anti-predictive in-sample: mean composite −0.01 in label months against +0.15 otherwise. By driver, mean z in label months against the rest: valuation +0.43 / −0.10 and concentration +2.12 / +1.01 point the right way; capex +0.16 / +1.07, positioning −0.97 / −0.19 and revisions −1.44 / −0.21 point the wrong way, because today's capex intensity and the 2021 and 2026 earnings booms have no precedent in the sample. The screen now says the slope is at its floor and ranks the table by z-score.
- Open, and Abhay's call: calibrate the slope on the two drivers that carry signal and show the rest as watch indicators; bring 2000 in-sample through the valuation and rates proxies; lower the event threshold or use daily peak-to-trough drawdowns to get more than two episodes; use CAPE for the proxy era so the 2009 earnings collapse stops reading as "stretch".

## First run with FRED live, 2026-11-07T07:43Z (15:43 SGT)

With `FRED_API_KEY` set all six feeds pull clean and the badge reads `Live data · pulled 15:37 SGT` with no suffix; the key never enters the provenance log or the store (checked).

- FRED serves the ICE BofA high-yield spread (BAMLH0A0HYM2) only from 7 November 2023 on both the API and the CSV endpoint, so the spec's "high-yield spread from 1997" is not available for free. The leverage driver now uses Moody's Baa yield over the 10-year Treasury (BAA10Y, daily from 1986), disclosed on the panel. Oracle files `LongTermNotesPayable` rather than `LongTermDebt` (its one LongTermDebt row is a zero from 2022), and a filed instant older than two years no longer stands in for a month. Leverage history: 2016-01 to today, 131 months; reading today +3.0σ (net debt building while spreads sit tight).
- Rates: US 10-year real yield 2.63%, above the 2.50% trigger. Fair value now carries the real-yield adjustment: gap −28% (was −41% on the plain median), 80% range −32% to −22%.
- Calibration unchanged: a = −2.601, b = 0.000 at the floor, Brier 0.064 against 0.064 for the base rate. Mean composite −0.04 in label months against +0.15 otherwise. Drivers pointing the right way in the two episodes: valuation, concentration, leverage; the wrong way: capex, positioning, revisions, rates (real yields were low before both de-ratings; the rise, not the level, preceded them).

## Option 1: probability calibrated on three drivers, 2026-11-07T07:59Z (15:59 SGT)

Abhay's decision after the slope stayed at its floor: only valuation, concentration and leverage enter the composite (design weights 25/15/15 renormalised to 45/27/27); capex, positioning, earnings momentum and rates are shown as watch indicators with no weight, marked on the table, the triggers panel, the footer and the driver panel.

- Fit: a = −2.808, b = 0.649 (off the floor), 275 months. Brier 0.0644 against 0.0643 for the base rate, so in-sample the fit still has no skill over always predicting 7%; hit rate 93% is the base rate. Mean composite +0.48 in label months against +0.17 otherwise.
- Shape of the in-sample probability: it peaks at 27% in December 2008 to April 2009, after the crash rather than before it, because the Shiller trailing P/E proxy spikes when earnings collapse; October 2007 reads 5.8% and November 2021 reads 9.5%. Option 4 (CAPE for the proxy era) is the natural next step if the pre-episode reading matters for the pitch.
- Today: probability 7%, calm; leverage +3.0σ contributes +3.1 pts, concentration +1.7σ contributes +1.7 pts, valuation −2.1σ contributes −3.6 pts. Triggers: valuation back at its median +5.1 pts, concentration past 40% +0.5 pts, leverage back at its mean −2.4 pts, capex shown as a watch indicator.
