#!/usr/bin/env bash
# Demo morning: pull public data, re-run the backtest and the model, print the status table and the badge, serve the app.
set -uo pipefail
cd "$(dirname "$0")/.."
lantern pull || echo "pull had errors: the previous cache serves (see the badge)"
lantern backtest || echo "backtest had errors: the previous calibration serves"
lantern model || echo "model run failed: the previous run serves"
lantern note || echo "note generation failed: the previous note serves"
lantern challenger || echo "challenger fan failed: the previous one serves (needs the challenger extra)"
lantern filings pre-answer || echo "pre-answer had errors: cached answers from the previous run serve"
lantern status
exec lantern serve "$@"
