import json
import shutil

from lantern.filings import corpus
from tests.conftest import FIXTURES


def test_ingest_counts_pages_without_text():
    pages = corpus.ingest_pdf(FIXTURES / "filings" / "ACME-AR2025.pdf")
    assert [p.no for p in pages] == [1, 2, 3] and pages[2].has_text is False and pages[1].has_text
    assert "S$1,234 million" in pages[1].text and "Net profit" in pages[1].text


def test_chunks_carry_page_and_filing_and_never_cite_an_imageless_page():
    entry = {"ticker": "ACME", "company": "ACME Holdings", "filing": "Annual Report 2025", "year": 2025, "file": "ACME-AR2025.pdf"}
    chunks = corpus.chunk_pages(corpus.ingest_pdf(FIXTURES / "filings" / "ACME-AR2025.pdf"), entry, "f" * 64)
    assert {c.page for c in chunks} == {1, 2} and all(c.ticker == "ACME" and c.year == 2025 for c in chunks)
    assert any("42 cents" in c.text for c in chunks)


def test_long_page_splits_with_overlap_inside_the_page():
    long_text = " ".join(f"Paragraph {i} of the risk report discusses credit exposure number {i}." for i in range(120))
    pages = [corpus.Page(no=7, text=long_text, has_text=True)]
    chunks = corpus.chunk_pages(pages, {"ticker": "X", "company": "X", "filing": "AR", "year": 2025, "file": "x.pdf"}, "a" * 64, size_tokens=200, overlap_tokens=40)
    assert len(chunks) >= 4 and all(c.page == 7 for c in chunks)
    assert chunks[1].text[:60] in chunks[0].text  # the overlap is the tail of the previous chunk


def test_build_corpus_fills_manifest_and_ids_are_deterministic(tmp_path):
    shutil.copytree(FIXTURES / "filings", tmp_path / "filings")
    chunks, manifest = corpus.build_corpus(tmp_path / "filings")
    again, _ = corpus.build_corpus(tmp_path / "filings")
    assert [c.id for c in chunks] == [c.id for c in again] and len(set(c.id for c in chunks)) == len(chunks)
    acme = next(m for m in manifest if m["ticker"] == "ACME")
    assert acme["pages"] == 3 and acme["pages_without_text"] == 1 and len(acme["sha256"]) == 64 and acme["ingested_at"].endswith("+00:00")
    assert json.loads((tmp_path / "filings" / "manifest.json").read_text())[0]["sha256"] == manifest[0]["sha256"]


def test_table_rows_carry_their_column_headers():
    pages = corpus.ingest_pdf(FIXTURES / "filings" / "ACME-AR2025.pdf")
    # a table value must never be separated from the column that gives it meaning
    assert pages[1].tables and "Banking: 2025 4,120; 2024 3,900" in pages[1].tables[0]
    assert "Insurance: 2025 1,010; 2024 960" in pages[1].tables[0]
    assert "Banking:" not in pages[1].text  # the prose text stays prose; tables travel separately


def test_each_table_becomes_its_own_chunk():
    entry = {"ticker": "ACME", "company": "ACME Holdings", "filing": "Annual Report 2025", "year": 2025, "file": "ACME-AR2025.pdf"}
    chunks = corpus.chunk_pages(corpus.ingest_pdf(FIXTURES / "filings" / "ACME-AR2025.pdf"), entry, "f" * 64)
    table_chunks = [c for c in chunks if "Banking: 2025 4,120" in c.text]
    assert len(table_chunks) == 1 and table_chunks[0].page == 2
    assert "final dividend" not in table_chunks[0].text  # a table chunk is the table, not the page
    prose = [c for c in chunks if "42 cents" in c.text]
    assert prose and all("Banking:" not in c.text for c in prose)


def test_an_oversized_table_splits_by_rows():
    rows = "\n".join(f"Line item {i}: 2025 {i:,}; 2024 {i + 1:,}" for i in range(400, 520))
    pages = [corpus.Page(no=3, text="prose", has_text=True, tables=[rows])]
    entry = {"ticker": "X", "company": "X", "filing": "AR", "year": 2025, "file": "x.pdf"}
    chunks = corpus.chunk_pages(pages, entry, "a" * 64, size_tokens=200, overlap_tokens=0)
    table_chunks = [c for c in chunks if "Line item" in c.text]
    assert len(table_chunks) >= 2  # split, never dropped
    assert all(len(c.text) <= 200 * 4 * 1.5 for c in table_chunks)
    assert all(c.text.splitlines()[0].startswith("Line item") for c in table_chunks)  # splits on row boundaries
