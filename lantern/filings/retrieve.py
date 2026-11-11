"""Local embeddings and the chunk index on disk (Task 2); hybrid retrieval over it (Task 3)."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

from lantern import config
from lantern.filings.corpus import Chunk

_WORD = re.compile(r"[a-z0-9$%.]+")


def _tokens(text: str) -> list[str]:
    """Lower-cased word tokens with a crude plural strip (dividends, recommends -> dividend, recommend), applied to queries and chunks alike."""
    return [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in _WORD.findall(text.lower())]


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> np.ndarray: ...


def _normalise(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float32)
    if a.ndim != 2 or a.shape[0] == 0:
        return a.reshape(0, a.shape[1] if a.ndim == 2 else 0)
    norms = np.linalg.norm(a, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (a / norms).astype(np.float32)


class HashEmbedder:
    """Deterministic bag-of-words hash: the test embedder, and the fallback when fastembed's model cannot load."""

    def __init__(self, dim: int = 64):
        self.dim = dim
        self.name = f"hash-{dim}"

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for word in _tokens(text):
                out[i, int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim] += 1.0
        return _normalise(out)


class FastEmbedder:
    """fastembed's ONNX bge-small model: no torch, about 130 MB downloaded once into ~/.cache/fastembed."""

    def __init__(self, model: str = config.EMBED_MODEL):
        from fastembed import TextEmbedding

        import os

        self.name = model
        gpu = {"providers": ["CUDAExecutionProvider"]} if os.environ.get("LANTERN_EMBED_CUDA") == "1" else {}
        self.model = TextEmbedding(model_name=model, **gpu)

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        return _normalise(np.asarray(list(self.model.embed(texts)), dtype=np.float32))


def build_index(chunks: list[Chunk], index_dir: Path, embedder: Embedder, manifest: list[dict] | None = None) -> dict:
    """chunks.parquet, embeddings.npy (rows aligned to the parquet) and meta.json under index_dir."""
    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([asdict(c) for c in chunks], columns=[f.name for f in fields(Chunk)])
    df.to_parquet(index_dir / "chunks.parquet", index=False)
    emb = embedder.embed(df["text"].tolist()) if len(df) else np.zeros((0, 0), dtype=np.float32)
    np.save(index_dir / "embeddings.npy", emb)
    meta = {
        "embed_model": embedder.name,
        "built_at": datetime.now(UTC).isoformat(),
        "n_chunks": int(len(df)),
        "n_files": int(df["file"].nunique()) if len(df) else 0,
        "pages_without_text": {m["file"]: int(m.get("pages_without_text", 0)) for m in (manifest or [])},
    }
    (index_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    return meta


# --- retrieval (Task 3) --------------------------------------------------------------------------


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float
    bm25_rank: int | None
    dense_rank: int | None


class Retriever:
    """Hybrid search over the index: BM25 and cosine over the local embeddings, fused by reciprocal rank."""

    def __init__(self, index_dir: Path, embedder: Embedder):
        from rank_bm25 import BM25Okapi

        index_dir = Path(index_dir)
        df = pd.read_parquet(index_dir / "chunks.parquet")
        self.chunks = [Chunk(**{k: (int(v) if k in ("year", "page") else v) for k, v in row.items()}) for row in df.to_dict("records")]
        self.embeddings = np.load(index_dir / "embeddings.npy")
        self.embedder = embedder
        meta_p = index_dir / "meta.json"
        self.fingerprint = json.loads(meta_p.read_text()).get("built_at", "") if meta_p.is_file() else ""  # cache answers are scoped to the index that produced them
        self.bm25 = BM25Okapi([_tokens(c.text) for c in self.chunks]) if self.chunks else None
        self._tickers = np.array([c.ticker for c in self.chunks])
        names = {c.ticker: c.company for c in self.chunks}
        # a company is named by its ticker (exact case, whole word) or its name without the legal suffix
        def whole(s: str, flags: int = 0) -> re.Pattern:
            return re.compile(rf"(?<![A-Za-z0-9]){re.escape(s)}(?![A-Za-z0-9])", flags)

        man_p = index_dir.parent / "manifest.json"  # optional "aliases" per filing, e.g. "ST Engineering"
        aliases = {m["ticker"]: m.get("aliases", []) for m in json.loads(man_p.read_text())} if man_p.is_file() else {}
        self._mentions = {t: [whole(t)] + [whole(s, re.I) for s in
                              [re.sub(r"\s+(limited|ltd|inc|plc)\.?$", "", name, flags=re.I), *aliases.get(t, [])]]
                          for t, name in names.items()}

    def named_tickers(self, question: str) -> set[str]:
        return {t for t, pats in self._mentions.items() if any(p.search(question) for p in pats)}

    def search(self, question: str, k: int = config.TOP_K) -> list[Hit]:
        n = len(self.chunks)
        if n == 0:
            return []
        width = min(config.CANDIDATES, n)
        bm25_scores = np.asarray(self.bm25.get_scores(_tokens(question)), dtype=float)
        q = self.embedder.embed([question])
        dense = self.embeddings @ q[0] if self.embeddings.size else np.zeros(n)
        named = self.named_tickers(question)
        if named:  # the question names its company: rank only that company's filing(s)
            # ponytail: "SGX-listed" names SGX itself; add a stop-phrase list if that misroutes real questions
            out = ~np.isin(self._tickers, list(named))
            bm25_scores[out] = 0.0
            dense = np.where(out, -np.inf, dense)
        bm25_order = [int(i) for i in np.argsort(-bm25_scores)[:width] if bm25_scores[i] > 0]
        dense_order = [int(i) for i in np.argsort(-dense)[:width] if np.isfinite(dense[i])]
        bm25_rank = {i: r + 1 for r, i in enumerate(bm25_order)}
        dense_rank = {i: r + 1 for r, i in enumerate(dense_order)}
        fused = {}
        for i in set(bm25_order) | set(dense_order):
            fused[i] = sum(1.0 / (config.RRF_K + r) for r in (bm25_rank.get(i), dense_rank.get(i)) if r)
        top = sorted(fused, key=lambda i: (-fused[i], i))[:k]
        return [Hit(self.chunks[i], float(fused[i]), bm25_rank.get(i), dense_rank.get(i)) for i in top]


def open_index(index_dir: Path = config.FILINGS_INDEX) -> Retriever:
    """A Retriever whose query embedder matches the model the index was built with (hash fallback indexes query with the hash)."""
    meta = json.loads((Path(index_dir) / "meta.json").read_text())
    model = meta.get("embed_model", config.EMBED_MODEL)
    embedder = HashEmbedder(int(model.split("-")[1])) if model.startswith("hash-") else FastEmbedder(model)
    return Retriever(index_dir, embedder)
