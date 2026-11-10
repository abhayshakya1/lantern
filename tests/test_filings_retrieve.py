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


def test_question_naming_a_company_searches_only_its_filing(retriever):
    # "employees numbered" is BETA's passage; asking about ACME must not return BETA's report
    hits = retriever.search("How many employees numbered at ACME?", k=8)
    assert hits and {h.chunk.ticker for h in hits} == {"ACME"}


def test_company_named_by_full_name_case_insensitive(retriever):
    hits = retriever.search("how many employees numbered at acme holdings", k=8)
    assert hits and {h.chunk.ticker for h in hits} == {"ACME"}


def _retriever_with(tmp_path, edit):
    import json
    shutil.copytree(FIXTURES / "filings", tmp_path / "filings")
    man = json.loads((tmp_path / "filings" / "manifest.json").read_text())
    edit(man)
    (tmp_path / "filings" / "manifest.json").write_text(json.dumps(man))
    chunks, manifest = corpus.build_corpus(tmp_path / "filings")
    retrieve.build_index(chunks, tmp_path / "filings" / "index", retrieve.HashEmbedder(), manifest)
    return retrieve.Retriever(tmp_path / "filings" / "index", retrieve.HashEmbedder())


def test_capitalised_legal_suffix_is_optional(tmp_path):
    # "City Developments Limited" is asked about as "City Developments"
    r = _retriever_with(tmp_path, lambda m: m[0].update(company="Acme Widgets Limited"))
    assert r.named_tickers("How many employees at acme widgets?") == {"ACME"}


def test_generic_word_left_after_corporation_is_not_a_mention(retriever):
    # "Venture Corporation" must not capture every question about a joint venture; here "BETA Corporation"
    assert retriever.named_tickers("What did the beta coefficient show?") == set()


def test_manifest_alias_names_a_company(tmp_path):
    # the manifest says "Singapore Technologies Engineering"; people ask about "ST Engineering"
    r = _retriever_with(tmp_path, lambda m: m[1].update(aliases=["Beta Bank"]))
    assert r.named_tickers("What did beta bank report?") == {"BETA"}


def test_ticker_inside_another_word_is_not_a_mention(retriever):
    # "ALPHABETA" contains BETA; it must not restrict the search to BETA
    hits = retriever.search("What final dividend did ALPHABETA recommend?", k=8)
    assert hits[0].chunk.ticker == "ACME"


def test_empty_index_returns_no_hits(tmp_path):
    retrieve.build_index([], tmp_path / "index", retrieve.HashEmbedder())
    assert retrieve.Retriever(tmp_path / "index", retrieve.HashEmbedder()).search("anything") == []
