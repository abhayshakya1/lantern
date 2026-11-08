#!/usr/bin/env bash
# Deathstar pipeline: prep data -> baseline bench -> QLoRA train -> fine-tuned bench.
# Runs in tmux under the shared research3 login; no API keys are used or present.
set -uo pipefail
REPO="${LANTERN_REPO:-/media/nas_mount/Abhay/ocbc bank/lantern}"
WORK="${LANTERN_WORK:-$HOME/Abhay/lantern-local}"
PY="$HOME/Abhay/venvs/ft/bin/python"
export HF_HOME="$WORK/hf"
export CUDA_VISIBLE_DEVICES="${LANTERN_GPU:-2}"
export TOKENIZERS_PARALLELISM=false
export LANTERN_FILINGS="$WORK/filings"
cd "$REPO"
step() { echo "=== $1 $(date -u +%FT%TZ) ==="; }

step "prep"
[ -f "$WORK/data/train.jsonl" ] || "$PY" scripts/local_model/prep_data.py --pool "$WORK/data/pool.jsonl" --out "$WORK/data/train.jsonl" || exit 1

step "baseline bench"
[ -f "$WORK/bench/base/metrics.json" ] || "$PY" scripts/local_model/bench.py --index "$WORK/filings/index" --gold "$WORK/filings/gold/gold_draft.jsonl" --out "$WORK/bench/base" || exit 1

step "train"
[ -f "$WORK/adapter/adapter_config.json" ] || "$PY" scripts/local_model/train_qlora.py --train "$WORK/data/train.jsonl" --out "$WORK/adapter" || exit 1

step "ft bench"
"$PY" scripts/local_model/bench.py --index "$WORK/filings/index" --gold "$WORK/filings/gold/gold_draft.jsonl" --adapter "$WORK/adapter" --out "$WORK/bench/ft" || exit 1

step "done"
echo "baseline:"; cat "$WORK/bench/base/metrics.json" 2>/dev/null | head -20
echo "fine-tuned:"; cat "$WORK/bench/ft/metrics.json" 2>/dev/null | head -20
