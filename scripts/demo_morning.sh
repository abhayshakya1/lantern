#!/usr/bin/env bash
# Demo morning: pull public data, run the model, show the status table, serve the app.
set -uo pipefail
cd "$(dirname "$0")/.."
lantern pull || echo "pull had errors: the previous cache serves (see the badge)"
lantern model
lantern status
exec lantern serve "$@"
