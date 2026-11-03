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
