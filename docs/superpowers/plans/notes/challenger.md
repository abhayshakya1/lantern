# Challenger fan — first real run, 2026-11-08

Model: TimesFM 2.5 (google/timesfm-2.5-200m-pytorch, Apache-2.0 weights), zero-shot, run locally on the laptop.
The 3.0 checkpoint was deliberately not used: its weights are licensed non-commercial-only; the checkpoint id is
`config.TIMESFM_CHECKPOINT` so a licensed 3.0 can be swapped in without code changes.

Walk-forward coverage, monthly NDX, 12-month horizon, p10–p90 band (target 80%), 252 months:
- Champion (conditional-history fan): 77%
- TimesFM 2.5 zero-shot: 50%

Reading: the champion's fan is much closer to its nominal coverage at this horizon; the zero-shot foundation
model's band is far too narrow twelve months out. That is the champion–challenger exhibit on the Model risk page:
the in-house model is scored against a strong public challenger on the same months, and wins on calibration.
Live fan context: 25 months (the run's chart window) — a longer basket history is the obvious upgrade if the
challenger ever becomes more than a comparison.

## Probability challenger — TabPFN (2026-11-09)

TabPFN 2.0 (open HF weights; v2.5+ is token-gated, v1 breaks on modern torch) predicting the
12-month drawdown label walk-forward from the seven driver z-scores, with a 12-month label embargo
(a label formed after the prediction month embeds future prices; the no-peek test pins the embargo).

On 203 scored months (only 7 of them drawdown months): TabPFN Brier 0.0785 · champion logistic
walk-forward 0.0767 · walk-forward base rate 0.0395 (each month forecasts the training window's own
drawdown frequency, so it uses only what was known then). For reference only, a hindsight base rate
that is told the scored window's mean scores 0.0333; it is not a fair baseline and is never quoted.
Honest conclusion: NEITHER model beats a walk-forward base rate out of sample — consistent with the
monitor's own in-sample disclosure, now corroborated by an external foundation-model challenger. With
7 positive months, the 0.002 gap between the two models is noise, not a ranking. Two further caveats
a reviewer should hear from us first: missing driver readings enter both models as a neutral z of 0
(about half the capex and leverage rows), and the composite's weights and calibrated-driver choice
were set with full-sample hindsight, which flatters the walk-forward champion if anything.
Before the
embargo the naive setup gave TabPFN 0.0259, a textbook leakage artifact caught by validation — kept
here deliberately as model-risk evidence that the harness catches what naive evaluation misses.
