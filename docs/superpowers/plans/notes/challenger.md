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
