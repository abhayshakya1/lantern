"""Chunking-independent retrieval measure: for each answerable gold row, does the gold quote appear
verbatim (whitespace-normalised, as verify_quotes checks) in the text of the production top-8?
Chunk ids change when chunking changes; quotes do not.

  python scripts/local_model/chunk_eval.py --filings data/filings --gold data/filings/gold/gold_draft.jsonl --tag baseline
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lantern.filings import corpus, retrieve  # noqa: E402
from lantern.filings.answer import _norm  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--filings", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--tag", default="run")
    ap.add_argument("--k", type=int, default=8)
    args = ap.parse_args()

    chunks, manifest = corpus.build_corpus(Path(args.filings))
    emb = retrieve.FastEmbedder()
    with tempfile.TemporaryDirectory() as tmp:
        retrieve.build_index(chunks, Path(tmp), emb, manifest)
        r = retrieve.Retriever(Path(tmp), emb)
        gold = [json.loads(line) for line in Path(args.gold).read_text().splitlines() if line.strip()]
        gold = [g for g in gold if not g.get("unanswerable") and (g.get("evidence") or {}).get("quote")]
        hits, misses = 0, []
        for g in gold:
            quote = _norm(g["evidence"]["quote"])
            texts = [_norm(h.chunk.text) for h in r.search(g["question"], k=args.k)]
            if any(quote in t for t in texts):
                hits += 1
            else:
                misses.append(g["item_id"])
        print(f"[{args.tag}] {len(chunks)} chunks | quote-in-top{args.k}: {hits}/{len(gold)} = {hits / len(gold):.2f} | misses: {misses}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
