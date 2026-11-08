# SDD ledger — plan: docs/superpowers/plans/2026-11-07-lantern-filings-qa.md
Branch: lantern-filings (from lantern-monitor at 82c8458); spec read: docs/superpowers/specs/2026-11-07-lantern-platform-design.md
Setup: Ruling: no separate worktree — the venv's editable install and the running server point at ~/lantern, so the isolation is the branch in the dedicated clone — cost if wrong: none for a single executor
Pre-flight: Task 1 build_corpus/Chunk ↔ Task 2 build_index(chunks, index_dir, embedder): consistent
Pre-flight: Task 2 index files (chunks.parquet, embeddings.npy, meta.json) ↔ Task 3 Retriever(index_dir, embedder): consistent
Pre-flight: Task 3 Retriever.search/Hit ↔ Task 4 ask(store, retriever, question, client=None): consistent
Pre-flight: Task 4 ask/cache_key ↔ Task 5 pre_answer and the normalised cache_key test: consistent
Pre-flight: Task 4 ask ↔ Task 8 run_eval "cache bypassed": ask has no bypass; ruling: ask gains use_cache: bool = True (Task 4) so the eval never reads cached answers — cost if wrong: one keyword
Pre-flight: Task 4 FakeClaude ↔ Task 6/8 tests reuse it; ruling: FakeClaude lives in tests/conftest.py, not tests/test_filings_answer.py — cost if wrong: none
Pre-flight: Task 6 create_app(store, retriever=, llm_client=) ↔ Task 7 page and Task 8 eval endpoint: consistent; api.py imports config directly so tests can monkeypatch api.config
Pre-flight: Task 5 pre_answer counts ↔ Task 9 demo script: consistent
Task 1: complete (commits 82c8458..43b31c9, tests: pytest -q → 77 passed, 1 deselected, 9 warnings in 54.16s; the tail line was a PyMuPDF exit warning)
Task 2: Ruling: build_index(chunks, index_dir, embedder, manifest=None) takes the manifest to record pages_without_text — chunks cannot carry pages they exclude — cost if wrong: one optional argument
Task 2: Ruling: Task 3's retrieval tests were written during the index build wait and travel red in Task 2's commit; Task 2's gate deselects them (-k "not search and not empty_index") — cost if wrong: none, Task 3 turns them green next
Task 2: complete (commits 43b31c9..ab46a56, tests: pytest -q -p no:warnings tests/test_filings_retrieve.py -k 'not search and not empty_index' → 2 passed, 3 deselected in 1.32s)
Task 3: Ruling: BM25 and the hash embedder share a tokeniser that strips a trailing s (dividends, recommends -> dividend, recommend) — without it neither ranker matched plurals or third-person verbs, which the fixture exposed on a nine-word cover page — cost if wrong: a rare false match between an s-plural and a different word
Task 3: shared fixtures (retriever, FakeClaude) committed in tests/conftest.py with this task
Task 3: complete (commits ab46a56..55557b0, tests: pytest -q -p no:warnings tests/test_filings_retrieve.py → 5 passed in 2.25s)
Task 4: complete (commits 55557b0..c6fe2aa, tests: pytest -q -p no:warnings → 87 passed, 1 deselected in 94.41s (0:01:34))
Task 5: retrieve.open_index(index_dir) added so the CLI and the API query with the embedder the index was built with (hash fallback indexes are queried with the hash) — implementation detail, not a deviation
Task 5: complete (commits c6fe2aa..96d1b6c, tests: pytest -q -p no:warnings tests/test_filings_answer.py → 6 passed in 5.02s)
Task 6: complete (commits 96d1b6c..35450aa, tests: pytest -q -p no:warnings → 92 passed, 1 deselected in 63.07s (0:01:03))
Task 7: complete (commits 35450aa..2234584, tests: node web/smoke.mjs → smoke ok)
Task 8: Ruling: gold rows use the harness's field name difficulty (easy/medium/hard), not the plan's tier — bfq_score groups by difficulty — cost if wrong: none
Task 8: Ruling: the harness's deterministic metrics run even without OPENROUTER_API_KEY (judged metrics need it); Lantern's abstention sentence is mapped onto the harness's canonical refusal in pred.jsonl so its H-Ref counts it, and abstention precision/recall are computed on the raw rows — cost if wrong: none, both are recorded in results.json
Task 8: Ruling: draft_gold samples only chunks longer than 200 characters that contain a digit, round-robin across companies — cover and divider chunks make poor questions — cost if wrong: fewer candidates on a thin corpus
Task 8: code complete and committed (steps 1-5); Step 6 (the real gold draft and prepared questions) waits for ANTHROPIC_API_KEY in ~/lantern/.env
Task 9: docs (README section, runbook checks, gold README) written and committed ahead of the dry run; Steps 1-2 wait for ANTHROPIC_API_KEY
Task 8: gold draft run on real data: 40 rows (30 answerable with verified quotes, 10 probes), spread CLI 6, DBS 6, Keppel/OCBC/SGX/Sembcorp/Singtel 5, UOB 3; prepared_questions_draft.json (20) promoted to prepared_questions.json pending Abhay's review
Setup: Ruling: API keys stay in the laptop's git-ignored .env and never reach Deathstar — the server is a shared login (research3) on a shared NAS, so key-bearing steps (pre-answer, gold draft, eval) run on the laptop; Deathstar runs the secret-free build and test job in tmux (~/Abhay/lantern-build.sh, session lantern-build, log ~/Abhay/lantern-build.log) — cost if wrong: server jobs cannot call the APIs
Task 8: Ruling: the judge id is pinned to OpenRouter's dated slug deepseek/deepseek-v4-pro-0813 — the paper's name DeepSeek-V4-Pro is not an OpenRouter model id (HTTP 400) — cost if wrong: a different snapshot than the paper's
Task 8: judged eval on the draft set: abstention precision 0.83 (10 of 12 abstentions were probes; recall 1.0), llm_correct 0.83/0.80/1.00 by tier, harness H-Ref 1.0 PASS; BFQ-Score composite absent (no multihop tier in this set); Lantern gate FAIL pending Abhay's verified gold.jsonl and the one tuning pass the plan allows after it
Task 8: complete (commits 2234584..0a63e3c, tests: pytest -q -p no:warnings tests/test_filings_evaluate.py → 2 passed in 1.67s)
Task 9: complete (commits 0a63e3c..9ccd1f6, tests: pytest -q -p no:warnings → 94 passed, 1 deselected in 55.70s)
Final review: fresh reviewer (Fable) on 82c8458..9ccd1f6 — verdict With fixes: 0 Critical, 5 Important, 11 Minor; all five Important fixed in one pass
Final: fixed PDF mount served gold/eval/index under FILINGS_DIR — route now serves only manifest-named PDFs — test_pdf_route_serves_only_manifest_pdfs RED→GREEN, verified live (gold/eval/manifest 404)
Final: fixed no timeout on the Anthropic call — Anthropic(timeout=30.0, max_retries=1) plus a 60 s AbortController in filings.js — test_real_client_gets_a_timeout_and_retry_budget RED→GREEN
Final: fixed cache never invalidated — cache keys carry PROMPT_SHA[:12] and the index built_at fingerprint — test_cache_is_scoped_to_the_prompt_and_the_index RED→GREEN; prepared cache re-warmed under the new scope (18 answered, 2 abstained)
Final: fixed Chrome-impersonating UA in fetch_filings — honest config.SEC_USER_AGENT — test_fetch_uses_the_honest_user_agent RED→GREEN (all eight PDFs already fetched; a refusing site is a finding to surface)
Final: fixed no injection guard in ANSWER_SYSTEM — rule 5 ignores instructions inside passages (PROMPT_SHA rotates with it) — test_prompt_tells_the_model_to_ignore_instructions_in_the_passages RED→GREEN
Final: suite 99/99 after the pass, smoke ok against the live server
Final: minor (deferred): evalResults in placeholders.js interpolates results.json values unescaped (server-written file)
Final: minor (deferred): duplicate (chunk_id, quote) evidence pairs are not deduped
Final: minor (deferred): answerable true with an empty answer string renders an empty paragraph above valid evidence
Final: minor (deferred): prepared question g003 carries PyMuPDF-glued table text; curate prepared_questions.json before the demo (Abhay's verification step)
Final: minor (deferred): the API's lazy retriever build has no lock and never reloads after a rebuild while serving
Final: minor (deferred): CLI filings ask/pre-answer/eval without an index or gold file die with raw tracebacks
Final: minor (deferred): a judge subprocess timeout (30 min) raises uncaught and loses results.json
Final: minor (deferred): one SQLite connection across the FastAPI threadpool (single-presenter ceiling)
Final: minor (deferred): run_eval's 40 asks appear in /api/filings/history
Final: minor (deferred): manifest ingested_at churns on every rebuild
Final: minor (deferred): filings.js error row colspan says 6 on a 4-column table
