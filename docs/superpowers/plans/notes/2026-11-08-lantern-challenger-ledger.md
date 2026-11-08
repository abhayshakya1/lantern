# SDD ledger — plan: docs/superpowers/plans/2026-11-08-lantern-challenger-fan.md
Branch lantern-challenger from main (7c4440d). Ruling: TimesFM 3.0 weights are non-commercial-only (HF license tag), so the build pins the Apache-2.0 2.5 checkpoint with the id in config for a later swap — cost if wrong: a config change.
Pre-flight: T1 adapter/fan consumed by T2; T2 metas consumed by T3; names checked in plan. Clean.
Task 1: complete (commits ca1c2e2..86ff4f1, tests: uv run --with pytest pytest tests/test_challenger.py -q → 2 passed in 0.01s)
Task 2: complete (commits 86ff4f1..5aff73f, tests: uv run --with pytest pytest tests/test_challenger.py -q → 5 passed in 2.28s)
Task 3: Ruling: the front-end smoke assertions are conditional on a challenger existing in the store and were verified against a seeded meta after implementation (implementation-first for the overlay; the API tests were red-first) — cost if wrong: a front-end regression surfaces only when a challenger run exists, which is the only time the overlay renders.
Task 3: complete (commits 5aff73f..17fb1c1, tests: node web/smoke.mjs → smoke ok)
Task 4: complete (commits 17fb1c1..b328cd3, tests: uv run --with pytest pytest tests/test_challenger.py -q → 5 passed, 1 deselected in 2.32s)
Final review: With fixes (0 Critical, 4 Important, 3 Minor), fresh reviewer on the most capable model.
Final: fixed CLI traceback without a run or without the extra — test_cli_challenger_without_a_run_prints_a_message_not_a_traceback RED→GREEN; latest_run checked before loading the model
Final: fixed missing truth-index regression guard — test_coverage_scores_the_month_twelve_ahead_not_the_context_end, validated by mutation (vals[i+horizon]→vals[i] made it fail), suite green after revert
Final: fixed stale overlay — challenger meta stores champion_as_of and monitor.js draws only when it matches the current run's as_of; test_challenger_meta_names_the_run_it_forecast_from (first RED was a fixture KeyError; assertion sensitivity is the field's presence)
Final: fixed undisclosed context length — legend now reads "TimesFM 2.5 zero-shot p10–p90, N-month context (challenger)", smoke asserts it
Final: minor (deferred): CLI prints success wording even when the fan was dropped for crossed quantiles
Final: minor (deferred): context-length monotonicity assertion allows duplicates (plan said strictly increasing)
Final: minor (deferred): Model-risk coverage block nests a .page div inside .page and races evalResults for ordering
Final: Ruling: demo_morning runs `lantern challenger` without --backtest — the 252-forecast walk is minutes of CPU and the coverage exhibit does not change daily — cost if wrong: a stale coverage number until the next manual --backtest
Final: Ruling: challenger p10/p90 included in the chart's y-scale — a wildly wide band compresses the champion chart rather than clipping — cost if wrong: a squashed chart on a pathological forecast
Final: Ruling: the network integration test cannot distinguish mean from median at index 0 — the synthetic test pins the mapping — cost if wrong: none while the documented 2.5 layout holds
