# Local Answerer Swap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use checkbox syntax.

**Goal:** Filings Q&A answered by the on-prem model on Deathstar behind the exact same interface, verification and logging as the Anthropic path — the spec's "later swap", delivered.

**Architecture:** A `LocalChat` adapter mimics the two things `answer.ask` uses from the anthropic client (`messages.create(...)` → an object with `.content` text blocks and `.stop_reason`), translating to an OpenAI-compatible `/v1/chat/completions` endpoint (the judge server already serving Qwen2.5-14B). `ask()` picks it when `LANTERN_LLM_URL` is set, labels the answer `source: "local"` and records the local model id. The verbatim-quote gate, abstention sentence, cache and question log are untouched — the safety story stays architectural.

**Tech Stack:** requests (installed), the existing judge server (`scripts/local_model/judge_server.py`) as the endpoint.

**Spec:** docs/superpowers/specs/2026-11-07-lantern-platform-design.md ("LLM: ... A local open-weight model is a later swap behind the same interface, which is the on-premise story for the pitch.")

## Global Constraints
- `answer.ask`'s contract is unchanged: same prompt, same verification, same abstention, same logging; the swap is client-deep only.
- Honest labelling: local answers carry `source: "local"` and the real model id; the front end names the on-prem model.
- Demo-day default is unchanged (Anthropic + cache); the local path activates only via `LANTERN_LLM_URL`.
- No schema enforcement server-side: the adapter appends a JSON-only instruction; an unparseable reply already falls to abstention in `ask()`.

## Review Focus
- A dead local endpoint must yield the OFFLINE answer, not a traceback (transport errors map onto the exception types `ask` already catches) — Task 1 test.
- `LANTERN_LLM_URL` set AND `ANTHROPIC_API_KEY` present: the local URL wins (explicit beats implicit) — Task 2 test.
- The cache key scope is prompt+index only; a cached Anthropic answer must not be served as "local" or vice versa — check and test how `source` survives the cache (Task 2).
- The front end must render the new `source` without "undefined" (Task 3 smoke).

### Task 1: The LocalChat adapter
**Files:** Create `lantern/filings/local_llm.py`; Test `tests/test_local_llm.py`
**Interfaces:** `LocalChat(url=None, model=None)` (defaults `LANTERN_LLM_URL`, `LANTERN_LLM_MODEL` or "local-model"); `.messages.create(model=..., max_tokens=..., system=[...], output_config=..., messages=[...])` returns an object with `.content` = [block(type="text", text=reply)] and `.stop_reason = "end_turn"`; appends "Reply with only a JSON object" + the schema to the user turn; POSTs `{model, temperature: 0, max_tokens, messages: [system + user]}`; `requests` errors raise `anthropic.APIConnectionError(request=None)`.
- [ ] Failing tests: create() posts the flattened system+user messages with the JSON instruction and returns the reply as an anthropic-shaped response (monkeypatched `requests.post`); a `requests.ConnectionError` surfaces as `anthropic.APIConnectionError`.
- [ ] RED → implement (~50 lines) → GREEN → commit `feat: local chat adapter behind the anthropic client surface`.

### Task 2: Selection and labelling in ask()
**Files:** Modify `lantern/filings/answer.py`; Test `tests/test_filings_answer.py`
**Interfaces:** When `client is None` and `LANTERN_LLM_URL` is set: `client = LocalChat()`, `model` becomes the adapter's model id, and the produced Answer has `source="local"` (api path) — abstentions and offline fallbacks keep their existing sources; everything else identical.
- [ ] Failing tests: env URL + fake transport → `a.source == "local"`, `a.model` names the local model, quote verification still applied; env URL + dead endpoint → OFFLINE answer; cached local answers replay with `source: "cache"` like any other.
- [ ] RED → implement → GREEN → commit `feat: on-prem answerer selected by LANTERN_LLM_URL`.

### Task 3: Front end label and the live proof
**Files:** Modify `web/filings.js` (SOURCE map + answered-by line), `web/smoke.mjs` (no-undefined assertion already covers the card; add the label case via the API's source field tolerance); docs note.
- [ ] Smoke stays green; then the live proof against Deathstar: `LANTERN_LLM_URL=http://192.168.3.6:8411/v1/chat/completions LANTERN_LLM_MODEL=Qwen/Qwen2.5-14B-Instruct uv run lantern filings ask "<prepared question>"` answers (or honestly abstains) with verified quotes and `[local, ...ms]`; record the exchange in `docs/superpowers/plans/notes/local-model.md`.
- [ ] Commit `feat: on-prem answer labelling and live proof`.
