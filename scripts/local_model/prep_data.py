"""FinSafeQA-XL pool -> supervised fine-tuning data in Lantern's grounded-answer format.

Each example shows the model numbered passages (the row's own evidence plus distractors from other
rows) and teaches the exact JSON contract Lantern uses: answer with a verbatim quote when the
passages support it, abstain when they do not. Run:
  python scripts/local_model/prep_data.py --pool pool.jsonl --out train.jsonl
"""

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lantern.filings.answer import ANSWER_SYSTEM  # the deployed prompt: train and serve must match

N_POSITIVE = 6000
N_NEGATIVE = 2000
N_DISTRACTORS = 3
MIN_EVIDENCE = 60
MAX_EVIDENCE = 1500
MAX_ANSWER = 400
SEED = 7


def _cid(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _passages(items: list[tuple[str, str]]) -> str:
    return "\n\n".join(f"[{cid}] source document\n{text}" for cid, text in items)


def _example(question: str, items: list[tuple[str, str]], target: dict) -> dict:
    return {"messages": [
        {"role": "system", "content": ANSWER_SYSTEM},
        {"role": "user", "content": f"Passages:\n\n{_passages(items)}\n\nQuestion: {question}"},
        {"role": "assistant", "content": json.dumps(target)},
    ]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-pos", type=int, default=N_POSITIVE)
    ap.add_argument("--n-neg", type=int, default=N_NEGATIVE)
    args = ap.parse_args()
    rng = random.Random(SEED)

    rows = []
    with open(args.pool) as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            ev = str(r.get("evidence") or "").strip()
            ans = str(r.get("answer") or "").strip()
            q = str(r.get("question") or "").strip()
            if q and ans and MIN_EVIDENCE <= len(ev) <= MAX_EVIDENCE:
                rows.append({"q": q, "a": ans[:MAX_ANSWER], "e": ev})
    if len(rows) < (args.n_pos + args.n_neg) * 2:
        print(f"pool too small after filtering: {len(rows)}", file=sys.stderr)

    rng.shuffle(rows)
    take = rows[: args.n_pos + args.n_neg]
    distract_from = rows[args.n_pos + args.n_neg:] or rows
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out_path.open("w") as f:
        for i, r in enumerate(take):
            others = [distract_from[rng.randrange(len(distract_from))]["e"] for _ in range(N_DISTRACTORS)]
            if i < args.n_pos:  # answerable: own evidence among distractors, quote verbatim
                items = [(_cid(e), e) for e in others]
                items.insert(rng.randrange(len(items) + 1), (_cid(r["e"]), r["e"]))
                target = {"answerable": True, "answer": r["a"],
                          "evidence": [{"chunk_id": _cid(r["e"]), "quote": r["e"][:300]}], "confidence": "high"}
            else:  # unanswerable: only mismatched passages, so the model learns to abstain
                items = [(_cid(e), e) for e in others]
                target = {"answerable": False, "answer": "", "evidence": [], "confidence": "low"}
            f.write(json.dumps(_example(r["q"], items, target)) + "\n")
            n += 1
    print(f"wrote {n} examples ({min(args.n_pos, n)} answerable) -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
