# TabPFN Probability Challenger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use checkbox syntax.

**Goal:** A second champion–challenger exhibit: TabPFN (a tabular foundation model, its actual sweet spot — ~200 monthly rows, 7 features) predicting the 12-month drawdown label walk-forward from the driver z-scores, scored by Brier against a walk-forward refit of our own logistic on identical months.

**Architecture:** `challenger_prob(store, clf=None)` in `lantern/challenger.py`: walks the monthly history (train on months `[0, i)` with known labels, predict month `i`, never peeking), producing Brier for TabPFN and for the walk-forward champion on the same months; stores meta `challenger_prob`; served inside `/api/challenger`; one line on the Model-risk page. The headline logistic stays untouched — this is a comparison, never the probability on the monitor.

**Tech Stack:** `tabpfn` (added to the `challenger` extra; torch already present). Lazy import; a fake classifier in tests.

**Spec:** docs/superpowers/specs/2026-11-07-lantern-platform-design.md (Model risk; honest labelling).

## Global Constraints
- Walk-forward only: the classifier for month i must never see month i or later; the champion comparison must be walk-forward too (the in-sample Brier is reported separately, labelled in-sample).
- Honest labelling: "TabPFN v2 (tabular foundation model), walk-forward" wherever shown.
- Suite passes without tabpfn installed.

## Review Focus
- No-peek: a fake classifier records training-set sizes — strictly increasing, max index < predict index (Task 1 test).
- Months with NaN labels (the last 12 months) are excluded from scoring but present in training only when labelled (Task 1 test).
- `/api/challenger` without a prob run keeps serving the fan metas unchanged (Task 2 test).
- `lantern challenger --prob` without tabpfn installed → clear message, exit 1, no traceback (Task 2 test).

### Task 1: The walk-forward comparison
**Files:** Modify `lantern/challenger.py`; Test `tests/test_challenger.py`
**Interfaces:** `challenger_prob(store, clf=None, min_train: int = 60) -> dict` — loads `drivers.history` (z columns) and `backtest.history` (labels); for each scorable month: TabPFN P(drawdown) and champion `model.fit_logistic`+`probability` refit on the same window; returns/stores meta `challenger_prob` {n, brier_tabpfn, brier_champion_wf, brier_champion_insample (from calibration meta), base_rate, model: "TabPFN v2, walk-forward", run_at}. `clf=None` lazy-imports `tabpfn.TabPFNClassifier`; the clf protocol is `fit(X, y)` + `predict_proba(X) -> (n, 2)`.
- [ ] Failing tests (fake clf): no-peek (train sizes strictly increase; recorded max train index < predicted index); unlabelled months excluded from scoring; brier values in [0, 1]; meta stored; RuntimeError without history.
- [ ] RED → implement → GREEN → commit `feat: tabpfn walk-forward probability challenger`.

### Task 2: CLI, API and Model-risk line
**Files:** Modify `lantern/cli.py`, `lantern/api.py` response (prob meta inside /api/challenger), `web/placeholders.js`; Test `tests/test_api.py`; smoke tolerant when absent.
- [ ] Failing tests: `--prob` flag runs it (fake via monkeypatch) and prints both Briers; missing tabpfn → message not traceback; /api/challenger carries `prob` when stored.
- [ ] RED → implement (placeholders.js appends: "Probability challenger: TabPFN walk-forward Brier X vs champion walk-forward Y (in-sample Z, base rate W)") → GREEN (suite + smoke) → commit `feat: probability challenger surfaced`.
- [ ] Real run: `uv run --extra challenger lantern challenger --prob`; record numbers in the challenger note; commit.
