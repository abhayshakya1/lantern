"""Benchmark an open-weight model on Lantern's filings gold set, through the production pipeline:
same retrieval, same system prompt, same verbatim-quote verification, same abstention sentence.

  python scripts/local_model/bench.py --index <dir> --gold gold_draft.jsonl --out bench/base [--adapter <dir>]

Writes pred.jsonl (BharatFinQA harness format) and metrics.json (abstention precision/recall and,
when the vendored harness runs, its deterministic report; the judge-scored pass runs elsewhere).
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lantern import config  # noqa: E402
from lantern.filings import retrieve  # noqa: E402
from lantern.filings.answer import ANSWER_SYSTEM, _passages, verify_quotes  # noqa: E402
from lantern.filings.evaluate import BFQ_DIR, abstention_scores  # noqa: E402

MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
MAX_NEW_TOKENS = 512


def load_model(model_id: str, adapter: str | None):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(model_id, quantization_config=bnb, device_map={"": 0})
    if adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter)
    model.eval()
    return tok, model


def generate_json(tok, model, user: str) -> dict:
    import torch

    msgs = [{"role": "system", "content": ANSWER_SYSTEM},
            {"role": "user", "content": user + "\n\nReply with only a JSON object: "
             '{"answerable": bool, "answer": str, "evidence": [{"chunk_id": str, "quote": str}], "confidence": "high"|"medium"|"low"}'}]
    enc = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True).to(model.device)
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=MAX_NEW_TOKENS, do_sample=False, pad_token_id=tok.eos_token_id)
    text = tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=MODEL_ID)
    ap.add_argument("--adapter", default=None)
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    retriever = retrieve.open_index(Path(args.index))
    gold = [json.loads(line) for line in Path(args.gold).read_text().splitlines() if line.strip()]
    tok, model = load_model(args.model, args.adapter)
    tag = f"{args.model}{'+lora' if args.adapter else ''}"

    rows = []
    t_start = time.monotonic()
    for i, g in enumerate(gold, 1):
        hits = retriever.search(g["question"])
        t0 = time.monotonic()
        if not hits:
            pred, parsed = config.ABSTAIN, {}
        else:
            parsed = generate_json(tok, model, f"Passages:\n\n{_passages(hits)}\n\nQuestion: {g['question']}")
            evidence = verify_quotes(parsed.get("evidence") or [], hits)
            answer_text = str(parsed.get("answer", "")).strip()
            pred = answer_text if parsed.get("answerable") and evidence and answer_text else config.ABSTAIN
        rows.append({"item_id": g.get("item_id"), "question": g["question"], "company": g.get("company"),
                     "predicted_answer": pred, "model": tag, "unanswerable": bool(g.get("unanswerable")),
                     "latency_s": round(time.monotonic() - t0, 1)})
        print(f"[{i}/{len(gold)}] {'ABSTAIN' if pred == config.ABSTAIN else 'answer '} {rows[-1]['latency_s']:>6}s {g['question'][:70]}", flush=True)

    from lantern.filings.bfq import bfq_metrics as metrics

    pred_path = out_dir / "pred.jsonl"
    with pred_path.open("w") as f:
        for r in rows:
            p = {k: r[k] for k in ("item_id", "question", "company", "model", "unanswerable")}
            p["predicted_answer"] = metrics.CANONICAL_REFUSAL if r["predicted_answer"] == config.ABSTAIN else r["predicted_answer"]
            f.write(json.dumps(p) + "\n")
    (out_dir / "raw.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))

    bfq_out = out_dir / "results_bfq.json"
    cmd = [sys.executable, "bfq_score.py", "--pred", str(pred_path.resolve()), "--gold", str(Path(args.gold).resolve()),
           "--refusal", "semantic", "--gate", str(config.GOLD_GATE * 100), "--out", str(bfq_out.resolve())]
    proc = subprocess.run(cmd, cwd=BFQ_DIR, capture_output=True, text=True, timeout=1800)
    bfq = json.loads(bfq_out.read_text()).get("report") if proc.returncode == 0 and bfq_out.exists() else None

    results = {
        "model": tag,
        "n": len(rows),
        "abstention": abstention_scores(rows),
        "bfq": bfq,
        "bfq_error": "" if proc.returncode == 0 else proc.stderr[-1000:],
        "total_minutes": round((time.monotonic() - t_start) / 60, 1),
    }
    (out_dir / "metrics.json").write_text(json.dumps(results, indent=2))
    print(json.dumps({k: results[k] for k in ("model", "abstention", "total_minutes")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
