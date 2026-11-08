# TimesFM Challenger Fan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use checkbox syntax.

**Goal:** A champion–challenger fan: TimesFM quantile forecasts of the same series our fan covers, overlaid on the monitor chart, with walk-forward backtest coverage for both models on the Model risk page.

**Architecture:** `lantern/challenger.py` isolates TimesFM behind a two-method adapter so tests use a fake. `lantern challenger` computes the live fan from the latest run's basket window and stores it in meta; `--backtest` walks the monthly NDX history (the same series and months the champion ledger scores), batch-forecasts every month, and stores p10–p90 coverage beside the champion's. The API serves both metas; the monitor overlays the challenger fan dashed; Model risk shows the coverage table.

**Tech Stack:** timesfm 2.5 PyTorch (`google/timesfm-2.5-200m-pytorch`, **Apache-2.0 weights** — the 3.0 checkpoint is non-commercial-only and is NOT used; the checkpoint id lives in config so 3.0 can be swapped in if rights are obtained). Lazy import; the package is an optional extra.

**Spec:** docs/superpowers/specs/2026-11-07-lantern-platform-design.md (monitor fan, Model risk placeholder, honest labelling constraint)

## Global Constraints
- The champion probability and fan stay untouched; the challenger is an overlay and a comparison, never the headline.
- Honest labelling: the challenger is named ("TimesFM 2.5, zero-shot") wherever it appears, with its context length disclosed.
- No API keys, no cloud calls: the checkpoint downloads once from Hugging Face and runs locally.
- `timesfm`/`torch` import only inside the adapter; the suite must pass without them installed.

## Review Focus
- `lantern challenger` with no model run yet → clear error, not a traceback (Task 2 test).
- API when no challenger has ever run → 404 with a JSON error; the monitor renders unchanged (Task 3 tests).
- Quantile index mapping: 2.5 returns (n, horizon, 10) = mean then q10..q90; p10 is index 1, p90 index 9, median index 5 — one wrong index silently miscalibrates the fan (Task 1 test pins it).
- Walk-forward coverage must not peek: the context for month i ends at i, the truth is i+12 (Task 2 test with a fake records the context lengths).
- A challenger fan whose p10 > p50 (quantile crossing despite the fix flag) must be dropped, not drawn (Task 1 test).

### Task 1: Adapter and fan construction
**Files:** Create `lantern/challenger.py`; Test `tests/test_challenger.py`
**Interfaces:** Produces `CHECKPOINT` (from `config.TIMESFM_CHECKPOINT`), `class TimesFMForecaster` with `.quantiles(contexts: list[np.ndarray], horizon: int) -> np.ndarray` (n, horizon, 10); `fan_from_quantiles(q: np.ndarray, last: float) -> dict | None` ({p10,p50,p90}: lists of horizon+1 starting at `last`, None when quantiles cross); module doc records the 2.5 index map (0=mean, 1..9=q10..q90).
- [ ] Tests: index mapping (synthetic q where q10=90, median=100, q90=110 constant → fan lists start at last and hit those levels), crossing → None.
- [ ] RED → implement (adapter: `from_pretrained(CHECKPOINT, torch_compile=False)`, `model.compile(ForecastConfig(max_context=1024, max_horizon=256, normalize_inputs=True, use_continuous_quantile_head=True, force_flip_invariance=True, infer_is_positive=True, fix_quantile_crossing=True))`, lazy import) → GREEN → commit `feat: timesfm adapter and challenger fan construction`.

### Task 2: Live fan, walk-forward coverage, CLI
**Files:** Modify `lantern/challenger.py`, `lantern/cli.py`, `lantern/config.py` (`TIMESFM_CHECKPOINT`); Test `tests/test_challenger.py`
**Interfaces:** `run_challenger(store, forecaster) -> dict` (meta "challenger": fan, model, context_months, run_at; raises RuntimeError "no model run" without one); `coverage_backtest(store, forecaster, horizon=12, min_context=24) -> dict` (meta "challenger_backtest": n, coverage, champion_coverage on the same dates from `backtest.ledger`, band "p10–p90", model) — one batched `quantiles` call; CLI `lantern challenger [--backtest]`.
- [ ] Tests with a fake forecaster: run_challenger stores a fan from the latest run's chart window; no run → RuntimeError; coverage walk never includes future points (fake asserts context lengths strictly increasing, truth index = context end + 12) and matches champion rows by date.
- [ ] RED → implement → GREEN → commit `feat: challenger fan run and walk-forward coverage`.

### Task 3: API and front end
**Files:** Modify `lantern/api.py`, `web/monitor.js`, `web/placeholders.js`, `web/smoke.mjs`
**Interfaces:** `GET /api/challenger` → {challenger, backtest} metas, 404 JSON error when neither exists.
- [ ] Tests: 404 empty store; 200 with stored metas. Smoke: when the API serves a challenger, the main chart has a dashed overlay group `#challenger-band` and the legend names TimesFM; Model risk shows both coverage numbers; absent challenger → monitor renders as before.
- [ ] RED → implement (monitor.js fetches `/api/challenger`, draws p10/p90 dashed polylines on the existing scale; placeholders.js Model risk block) → GREEN (suite + smoke) → commit `feat: challenger overlay and coverage on the model risk page`.

### Task 4: Real model, real numbers
**Files:** Modify `pyproject.toml` (optional extra `challenger`), docs note.
- [ ] Install (`uv pip install "timesfm[torch] @ git+https://github.com/google-research/timesfm"` or PyPI if it carries 2.5), one `network`-marked integration test (real forecast of a sine series: shapes and ordering).
- [ ] Run `lantern challenger --backtest` for real; verify the live app shows the overlay and coverage; record numbers in `docs/superpowers/plans/notes/challenger.md`; commit `feat: challenger extra and first real coverage run`.
