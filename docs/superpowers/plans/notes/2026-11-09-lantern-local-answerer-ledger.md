# SDD ledger — plan: docs/superpowers/plans/2026-11-09-lantern-local-answerer.md
Branch lantern-local-llm from main (a96f759). Pre-flight: T1 LocalChat consumed by T2 ask(); anthropic-shaped response surface pinned by T1 tests. Clean.
Task 1: complete (commits 7393b65..fe27187, tests: uv run --with pytest pytest tests/test_local_llm.py -q → 2 passed in 0.51s)
Task 2: complete (commits fe27187..06479af, tests: uv run --with pytest pytest tests/test_filings_answer.py tests/test_local_llm.py -q → <sys>:0: DeprecationWarning: builtin type swigvarlink has no __module__ attribute)
Task 2: Ruling: the precedence test first passed for the wrong reason (Anthropic auth failure also yields OFFLINE) — strengthened to assert the local transport was actually called — cost if wrong: none, the stronger assertion subsumes the weaker.
Task 3: Finding fixed in-branch: the previously deferred shared-SQLite-connection minor bit live (intermittent 500 with a UTF-8 decode error on a healthy table under smoke's parallel fetches) — fixed root-cause with per-thread connections, test_store_gives_each_thread_its_own_sqlite_connection RED→GREEN, suite 136/136, smoke 3/3.
Task 3: complete (commits 06479af..9729c9d, tests: node web/smoke.mjs → smoke ok)
Final review: With fixes (0 Critical, 2 Important, 4 Minor), fresh reviewer on the most capable model.
Final: fixed malformed-but-alive endpoint traceback — test_malformed_but_alive_endpoint_degrades_like_a_dead_one (3 param cases, 2 RED)→GREEN, suite 139/139
Final: fixed UI not naming the on-prem model — smoke stub-fetch assertion RED→GREEN (also closes the plan's deferred smoke coverage)
Final: minor (deferred): cache replays log the default Anthropic model id into questions.model while the payload says the local model (audit-log only)
Final: minor (deferred): thread-connection test compares id() values and could in principle flake on address reuse; hold object references instead
Final: minor (deferred): two per-thread writers can hit SQLITE_BUSY; enable WAL and an explicit timeout if this ever serves more than one user
Final: Ruling: an explicitly passed LocalChat client labels as "api" with the upstream model id — selection and labelling are scoped to the env path per plan — cost if wrong: a mislabelled answer in a usage no code path produces today
