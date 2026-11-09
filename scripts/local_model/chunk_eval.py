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
    ap.add_argument("--rerank", default="", help="cross-encoder model (e.g. BAAI/bge-reranker-base) over --pool candidates")
    ap.add_argument("--pool", type=int, default=50)
    ap.add_argument("--hf-embed", default="", help="transformers embedding model id (replaces the fastembed default)")
    ap.add_argument("--pooling", default="cls", choices=["cls", "mean"], help="pooling for --hf-embed")
    args = ap.parse_args()
    reranker = None
    if args.rerank:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        reranker = TextCrossEncoder(model_name=args.rerank)

    class HFEmbedder:
        """Any transformers encoder as an Embedder: batched, pooled, L2-normalised. Experiment-only."""

        def __init__(self, model_id: str, pooling: str):
            import torch
            from transformers import AutoModel, AutoTokenizer

            self.torch = torch
            self.name = model_id
            self.pooling = pooling
            self.tok = AutoTokenizer.from_pretrained(model_id)
            self.model = AutoModel.from_pretrained(model_id, torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32)
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model.to(self.device).eval()

        def embed(self, texts):
            import numpy as np

            if not texts:
                return np.zeros((0, 0), dtype=np.float32)
            out = []
            with self.torch.no_grad():
                for i in range(0, len(texts), 32):
                    enc = self.tok(texts[i:i + 32], padding=True, truncation=True, max_length=512, return_tensors="pt").to(self.device)
                    h = self.model(**enc).last_hidden_state
                    if self.pooling == "cls":
                        v = h[:, 0]
                    else:
                        m = enc["attention_mask"].unsqueeze(-1)
                        v = (h * m).sum(1) / m.sum(1).clamp(min=1)
                    out.append(self.torch.nn.functional.normalize(v, dim=-1).float().cpu().numpy())
            return np.concatenate(out)

    chunks, manifest = corpus.build_corpus(Path(args.filings))
    emb = HFEmbedder(args.hf_embed, args.pooling) if args.hf_embed else retrieve.FastEmbedder()
    with tempfile.TemporaryDirectory() as tmp:
        retrieve.build_index(chunks, Path(tmp), emb, manifest)
        r = retrieve.Retriever(Path(tmp), emb)
        gold = [json.loads(line) for line in Path(args.gold).read_text().splitlines() if line.strip()]
        gold = [g for g in gold if not g.get("unanswerable") and (g.get("evidence") or {}).get("quote")]
        hits, misses = 0, []
        for g in gold:
            quote = _norm(g["evidence"]["quote"])
            if reranker:
                cands = r.search(g["question"], k=args.pool)
                scores = list(reranker.rerank(g["question"], [h.chunk.text for h in cands]))
                order = sorted(range(len(cands)), key=lambda i: -scores[i])[: args.k]
                texts = [_norm(cands[i].chunk.text) for i in order]
            else:
                texts = [_norm(h.chunk.text) for h in r.search(g["question"], k=args.k)]
            if any(quote in t for t in texts):
                hits += 1
            else:
                misses.append(g["item_id"])
        print(f"[{args.tag}] {len(chunks)} chunks | quote-in-top{args.k}: {hits}/{len(gold)} = {hits / len(gold):.2f} | misses: {misses}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
