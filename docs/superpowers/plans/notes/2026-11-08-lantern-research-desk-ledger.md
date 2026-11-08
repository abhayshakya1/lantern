# SDD ledger — plan: docs/superpowers/plans/2026-11-08-lantern-research-desk.md
Branch lantern-research from main (2ef091a); plan commit fdb387f. No worktree: dedicated clone, single executor (ruling carried from plans 1-2).
Pre-flight:
- T1→T2/T3: notes.py store accessors + verify_numbers consumed by generate_note and ledger — names consistent in plan (save_note/get_note/list_notes/set_note_status, verify_numbers, note_payload). Clean.
- T3→T4: notes.ledger(store) consumed by /api/research/ledger. Clean.
- T4→T5/T6: endpoint paths consistent (/api/research/*, /research/note/{id}/print, /api/research/note/{id}/pdf). Clean.
- T2 run_fixture needs tiles/chart/drivers/triggers/sources keys faithful to pull.run_model. Checked against pull.py lines 215-248. Clean.
Task 1: Ruling: run payload has no top-level `sources` key (checked pull.py) — the note's sources section is a snapshot of the latest provenance row per series, captured at note creation and stored on the note row; `store.get_run(run_id)` added so a note regenerates bit for bit — cost if wrong: one extra column-less field and a small accessor.
Task 1: complete (commits fdb387f..23b4a62, tests: uv run --with pytest pytest tests/test_research_notes.py -q → 4 passed in 0.23s)
Task 2: complete (commits 23b4a62..a7628f2, tests: uv run --with pytest pytest tests/test_research_notes.py -q → 8 passed in 0.66s)
Task 3: complete (commits a7628f2..e9f217a, tests: uv run --with pytest pytest tests/ -q → <sys>:0: DeprecationWarning: builtin type swigvarlink has no __module__ attribute)
Task 4: complete (commits e9f217a..3a9061a, tests: uv run --with pytest pytest tests/test_api.py tests/test_research_notes.py -q → <sys>:0: DeprecationWarning: builtin type swigvarlink has no __module__ attribute)
Task 5: Ruling: Anthropic account has no credits (BadRequestError: credit balance too low) — live generation falls back to offline-template exactly as designed; Abhay must top up billing before demo day — cost if wrong: none, the fallback is the designed behaviour.
Task 5: complete (commits 3a9061a..12bdc8c, tests: node web/smoke.mjs → smoke ok)
Task 6: complete (commits 12bdc8c..a89bad1, tests: uv run --with pytest pytest tests/ -q → <sys>:0: DeprecationWarning: builtin type swigvarlink has no __module__ attribute)
Task 6: Ruling: uv.lock committed — this session moved the env to uv and the lock makes the Deathstar build reproducible — cost if wrong: one file to delete.
Final review: With fixes (0 Critical, 3 Important, 5 Minor), fresh reviewer on the most capable model.
Final: fixed PDF route 500 on hung Chrome/missing node — test_note_pdf_hung_or_missing_builder_is_a_503_not_a_500 RED→GREEN, suite 120/120
Final: fixed stale Draft-labelled PDF after publish — test_publish_invalidates_the_cached_pdf RED→GREEN, suite 120/120
Final: fixed missing prose-escape smoke assertion — self-validating in-browser check (control proved the detector, and its first run caught its own img onerror firing, proving the pwned detector too); smoke ok
Final: minor (deferred): print page embeds chart JSON without </ escaping (app-generated data, theoretical)
Final: minor (deferred): stray double assignment in test_note_pdf_builder_failure_is_a_503
Final: minor (deferred): front-end 90 s abort can undercut the ~120 s server worst case; message says failed while the note may still save
Final: minor (deferred): rejected LLM drafts not logged (filings logs raw responses; notes keep only shipped prose)
Final: minor (deferred): new CSS classes (note-row, note-lead, export-pdf, byline, pdf) unstyled, inherit from card/history
Final: Ruling: save_note id is timestamp+suffix not "n+counter" — mirrors save_run, newest-first ordering preserved — cost if wrong: none
Final: Ruling: ledger shows live rows before backtest rows rather than one global date sort — documented and reads correctly — cost if wrong: cosmetic
Final: Ruling: UI ledger truncated at 60 rows — demo screen — cost if wrong: scroll length
Final: Ruling: note with missing run 404s as "no such note" — runs are never deleted here — cost if wrong: misleading error in an impossible state
Final: Ruling: run_numbers admits any token in the run JSON, so a coincidental hallucination can pass — inherent to the spec's own rule — cost if wrong: a rare unverifiable number ships
Final: Ruling: unauthenticated generate endpoint can spend API credit — single-user localhost demo per spec — cost if wrong: none locally
Final: Ruling: print chart guard checks price+fan but lineFan also reads fair_value/fv_band — real runs carry all; worst case the chart is dropped, prose is server-rendered — cost if wrong: a chartless print page
Final: Ruling: shared SQLite connection across the API threadpool without a lock — pre-existing pattern, single user — cost if wrong: a rare write race in multi-user use
