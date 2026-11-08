"""Which embedding model actually retrieves the gold evidence? For each candidate model: rebuild the
index over the same chunks (chunk ids are content-addressed, so they stay comparable), search every
answerable gold question, and report hit@8 (the production TOP_K), the gold chunk's rank, and the
misses by item id. CPU-only; aimed squarely at the table-dense misses behind the abstention gate.

  python scripts/local_model/retrieval_sweep.py --filings <dir> --gold gold_draft.jsonl --out <dir>
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lantern.filings import corpus, retrieve  # noqa: E402

MODELS = [
    "BAAI/bge-small-en-v1.5",  # production today
    "BAAI/bge-base-en-v1.5",
    "BAAI/bge-large-en-v1.5",
]
POOL = 30  # how deep to look when reporting the gold chunk's rank


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--filings", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    chunks, manifest = corpus.build_corpus(Path(args.filings))
    gold = [json.loads(line) for line in Path(args.gold).read_text().splitlines() if line.strip()]
    gold = [g for g in gold if not g.get("unanswerable") and (g.get("evidence") or {}).get("chunk_id")]
    print(f"{len(chunks)} chunks, {len(gold)} answerable gold rows", flush=True)

    results = {}
    for model in MODELS:
        emb = retrieve.FastEmbedder(model)
        idx = out_dir / f"index-{model.split('/')[-1]}"
        retrieve.build_index(chunks, idx, emb, manifest)
        r = retrieve.Retriever(idx, emb)
        ranks, misses = [], []
        for g in gold:
            ids = [h.chunk.id for h in r.search(g["question"], k=POOL)]
            want = g["evidence"]["chunk_id"]
            rank = ids.index(want) + 1 if want in ids else None
            ranks.append(rank)
            if rank is None or rank > 8:
                misses.append({"item_id": g["item_id"], "rank": rank, "question": g["question"][:80]})
        n = len(gold)
        results[model] = {
            "hit@8": sum(1 for x in ranks if x and x <= 8) / n,
            "hit@30": sum(1 for x in ranks if x) / n,
            "mean_rank_when_found": (sum(x for x in ranks if x) / max(1, sum(1 for x in ranks if x))),
            "misses": misses,
        }
        m = results[model]
        print(f"{model}: hit@8 {m['hit@8']:.2f}, hit@30 {m['hit@30']:.2f}, "
              f"mean rank {m['mean_rank_when_found']:.1f}, misses {[x['item_id'] for x in m['misses']]}", flush=True)

    (out_dir / "sweep.json").write_text(json.dumps(results, indent=2))
    print(f"-> {out_dir / 'sweep.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
