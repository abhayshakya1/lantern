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
