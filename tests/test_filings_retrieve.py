import shutil

import numpy as np
import pandas as pd

from lantern.filings import corpus, retrieve
from tests.conftest import FIXTURES


def test_hash_embedder_is_deterministic_and_normalised():
    e = retrieve.HashEmbedder(dim=64)
    a = e.embed(["net profit rose", "net profit rose"])
    assert a.shape == (2, 64) and a.dtype == np.float32 and np.allclose(a[0], a[1]) and abs(np.linalg.norm(a[0]) - 1) < 1e-6


def test_build_index_writes_chunks_embeddings_and_meta(tmp_path):
    shutil.copytree(FIXTURES / "filings", tmp_path / "filings")
    chunks, manifest = corpus.build_corpus(tmp_path / "filings")
    meta = retrieve.build_index(chunks, tmp_path / "index", retrieve.HashEmbedder(), manifest)
    assert meta["n_chunks"] == len(chunks) and meta["n_files"] == 2 and meta["pages_without_text"]["ACME-AR2025.pdf"] == 1
    assert np.load(tmp_path / "index" / "embeddings.npy").shape[0] == len(chunks)
    assert set(pd.read_parquet(tmp_path / "index" / "chunks.parquet")["ticker"]) == {"ACME", "BETA"}
    assert meta["embed_model"] == "hash-64" and meta["built_at"].endswith("+00:00")



def test_search_finds_the_dividend_passage_first(retriever):
    hits = retriever.search("What final dividend did ACME recommend?", k=8)
    assert hits and "42 cents" in hits[0].chunk.text and hits[0].chunk.page == 2 and hits[0].chunk.ticker == "ACME"
    assert len(hits) <= 8 and hits == sorted(hits, key=lambda h: -h.score)


def test_search_fuses_both_rankers(retriever):
    hits = retriever.search("employees numbered", k=3)
    top = hits[0]
    assert top.chunk.ticker == "BETA" and top.bm25_rank == 1 and top.dense_rank is not None


def test_empty_index_returns_no_hits(tmp_path):
    retrieve.build_index([], tmp_path / "index", retrieve.HashEmbedder())
    assert retrieve.Retriever(tmp_path / "index", retrieve.HashEmbedder()).search("anything") == []
