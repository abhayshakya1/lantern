"""Local embeddings and the chunk index on disk (Task 2); hybrid retrieval over it (Task 3)."""

import hashlib
import json
import re
from dataclasses import asdict, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

from lantern import config
from lantern.filings.corpus import Chunk

_WORD = re.compile(r"[a-z0-9$%.]+")


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
            for word in _WORD.findall(text.lower()):
                out[i, int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim] += 1.0
        return _normalise(out)


class FastEmbedder:
    """fastembed's ONNX bge-small model: no torch, about 130 MB downloaded once into ~/.cache/fastembed."""

    def __init__(self, model: str = config.EMBED_MODEL):
        from fastembed import TextEmbedding

        self.name = model
        self.model = TextEmbedding(model_name=model)

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
