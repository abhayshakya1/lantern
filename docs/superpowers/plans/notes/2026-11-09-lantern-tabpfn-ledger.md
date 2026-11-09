# SDD ledger — plan: docs/superpowers/plans/2026-11-09-lantern-tabpfn-challenger.md
Branch lantern-tabpfn from main. Pre-flight: T1 challenger_prob consumed by T2 CLI/API; clf protocol pinned by T1 fake. Clean.
Task 1: complete (commits 01a35d5..2486465, tests: uv run --with pytest pytest tests/test_challenger.py -q → 10 passed, 1 deselected in 8.28s)
Task 2: complete (commits 2486465..238bf34, tests: uv run --with pytest pytest tests/test_api.py tests/test_challenger.py -q → <sys>:0: DeprecationWarning: builtin type swigvarlink has no __module__ attribute)
Task 2: Ruling: tabpfn pinned to 2.0.9 — 2.5+ requires a Prior Labs account token, 0.1.x breaks on modern torch — cost if wrong: an older TabPFN than the current release.
Task 2: Ruling: 12-month label embargo added mid-execution after the naive walk-forward leaked (Brier 0.026, an artifact) — a label formed after the prediction month embeds future prices — cost if wrong: none; it can only make the challenger look worse, never better.
Final review: With fixes (0 Critical, 3 Important, 7 Minor), fresh reviewer on Opus 5.5 (the Fable reviewer was cut off by a rate limit before reporting).
Final: fixed wrong model label ("open v1 weights" on a 2.0.9 pin) — test asserts "TabPFN v2" RED→GREEN
Final: fixed the quoted base-rate Brier peeking at the scored window — walk-forward base rate added and quoted in code, notes, deck and Model-risk page; the fake classifier must equal it exactly, RED→GREEN; hindsight figure kept only under an explicit hindsight name
Final: fixed missing CLI tests — --prob prints all three Briers, missing tabpfn exits 1 with a message; suite 149/149
Final: fixed (upgraded from minor) THIRD_PARTY_NOTICES lacked TabPFN while the deck claims every component is catalogued
Final: Ruling: the embargo stays one month stricter than necessary (range(i-12)) — erring safe; reviewer confirmed the conclusion is unchanged at the exact bound — cost if wrong: one fewer training month per prediction
Final: minor (deferred): missing driver readings enter both models as z=0 rather than NaN (disclosed in the notes)
Final: minor (deferred): the Model-risk probability line only shows when the fan backtest meta also exists
Final: minor (deferred): a vacuous assertion and an unused import in the probability test
Final: minor (deferred): a first-run weight-download failure would print a traceback (only RuntimeError is caught)
Final: minor (deferred): composite weights and calibrated drivers were chosen with full-sample hindsight (disclosed in the notes)
