# Lantern Filings Q&A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A question box over eight SGX annual reports that answers only with verbatim, page-cited evidence from the corpus, says "The filings in this corpus do not answer this" otherwise, survives a dead connection through pre-answered questions, logs every call, and is gated for the demo by a 40-question gold set scored with the BharatFinQA harness.

**Architecture:** A `lantern.filings` package beside the monitor code: `corpus.py` turns PDFs into page-aware chunks with a manifest (SHA-256, pages, ingest time); `retrieve.py` does hybrid BM25 plus local-embedding search fused by reciprocal rank; `answer.py` calls Claude once per question with a JSON-schema output, drops any quote that is not a verbatim substring of its chunk, abstains when nothing survives, and logs the question, chunk set, prompt hash and answer in SQLite; `evaluate.py` drafts and scores the gold set with the vendored BharatFinQA harness. The FastAPI app gains four endpoints and a PDF mount; the front end gains one page in the approved look.

**Tech Stack:** Python 3.13 in the existing venv; `pymupdf` for text and tables per page (the FinSafeQA `pdf_to_md` contract: text layer only, pages without one are counted, no OCR on the demo path); `rank-bm25`; `fastembed` (ONNX, `BAAI/bge-small-en-v1.5`, no torch) for local embeddings; the official `anthropic` SDK with `claude-opus-5-5` (the current default in the API reference; thinking is always on, effort `medium`); `numpy`; the existing SQLite store; plain HTML, CSS and JS; the vendored BharatFinQA harness (stdlib plus numpy) with the DeepSeek-V4-Pro judge over OpenRouter.

**Spec:** `docs/superpowers/specs/2026-11-07-lantern-platform-design.md`, sections "Filings Q&A", "Filings Q&A pipeline", "Shell", "Prerequisites", "Resolved after the builder check". Plan 1 (`2026-11-07-lantern-monitor.md`) built the shell, store, API and the approved look this plan extends.

**Source material to port (read at execution, do not import across the external drive):**
- FinSafeQA ingest contract: `/Volumes/Elements/FinsafeQA/datasetv2/pipeline/ingest.py::pdf_to_md(path) -> (markdown, needs_ocr)` (PyMuPDF text layer per page, pages with under 40 characters counted as needing OCR, tables through `find_tables`) and the chunker in `chunk_score.py` (`split_blocks`, `token_estimate`, `chunk_doc`).
- BharatFinQA scoring harness, three files inside `/Volumes/Elements/Abhay's MacBook M3 Pro/BharatFinQA/BharatFinQA_software.zip`: `harness/bfq_judge.py` (JUDGE_PROMPT, `Judge`, provider DEFAULTS with `openrouter`), `harness/bfq_metrics.py` (`relaxed_em`, `token_f1`, `numeric_em`, `is_refusal`, `correct_refusal`, `bfq_score`, `reliability_gate(h_ref, threshold=90.0)`, `CANONICAL_REFUSAL`), `harness/bfq_score.py` (CLI: `--pred --gold --judge deepseek-ai/DeepSeek-V4-Pro --provider openrouter --refusal semantic --gate 90 --out`). Prediction rows: `{"question", "company", "predicted_answer", "model", "unanswerable"}`; `item_id` may replace company plus question.
- The BharatFinQA persona prompts are not in the software archive. The answer prompt in Task 4 is written fresh around the spec's abstention rule; if Abhay wants the paper's persona wording, he pastes it into `ANSWER_SYSTEM` later (one constant).

## Global Constraints

- Python `>=3.12` (the venv is 3.13); FastAPI served by uvicorn in the same process as the monitor; plain HTML, CSS and JavaScript, no framework and no build step; the approved look (IBM Plex Sans and Mono, light neutral palette, one blue accent `#1F5FBF`, status colours only for status, hairline borders).
- Public documents only, pulled from the companies' investor pages; nothing internal to OCBC.
- Demo corpus: the 2025 annual reports of OCBC, DBS and UOB plus five large STI companies; builder default if Abhay does not choose: Singtel, SGX, Keppel, CapitaLand Investment, Sembcorp. The corpus must be rebuildable from the PDFs with one command.
- Answer area: a two-to-four-sentence answer; one to three evidence cards, each with the verbatim passage, the filing, the page number and a link that opens the PDF at that page; a confidence label; when the corpus does not answer, exactly the sentence `The filings in this corpus do not answer this` with the nearest passages shown as context, never as an answer. A history rail keeps the session's questions. The corpus list beside the box shows company, filing, year, pages, date ingested, SHA-256.
- Retrieval: hybrid BM25 and embedding search, top eight chunks. Chunks tagged with company, filing, year and page, embedded with a local model, stored with the PDF's SHA-256.
- Answering: Claude through the Anthropic API; an answer is allowed only when supported by quoted evidence returned verbatim with page numbers; otherwise the abstention sentence. Every question, retrieved chunk set, prompt and answer is logged with timestamps.
- Offline line: the morning run pre-answers a prepared list of 20 questions and caches answers and evidence; only ad-hoc questions need the connection.
- Evaluation: a 40-question gold set over the demo corpus (30 answerable, 10 unanswerable), drafted by the builder with evidence by about 14 November 2026 and verified by Abhay by about 17 November, scored with the BharatFinQA judge (DeepSeek-V4-Pro through OpenRouter), reported on the Model risk page, release gate: no demo if abstention precision is below 90%.
- Secrets: `ANTHROPIC_API_KEY` and `OPENROUTER_API_KEY` come from the environment or the git-ignored `.env` the CLI already loads; they never enter logs, the store or provenance.
- Model: `claude-opus-5-5`, `max_tokens=4000`, `output_config={"effort": "medium", "format": {"type": "json_schema", "schema": ANSWER_SCHEMA}}`, system prompt cached with `cache_control`. Builder's call: no server-side refusal fallback (a refusal on an annual-report question is treated as an abstention and logged), no streaming (answers are short).

## Review Focus

1. A page without a text layer (a scanned page, a cover made of images). Expected: ingest counts it, the corpus table shows "n pages without text", and no answer ever cites such a page. Pinned in Task 1.
2. A question with nothing retrievable (an empty corpus, or hits whose fused score is zero). Expected: the abstention sentence with the nearest passages shown as context, never an answer, and no API call when there are no hits. Pinned in Task 4.
3. A model reply whose quotes are paraphrased, trimmed across a chunk boundary, or attributed to a chunk that does not contain them. Expected: those quotes are dropped; if none survive the answer becomes an abstention; the log keeps the model's original reply. Pinned in Task 4.
4. No API key, or the API unreachable, in the room. Expected: a prepared question still answers from the morning cache with its evidence; an ad-hoc question returns an "answer service offline" state with the nearest passages, not a crash; the history rail still works. Pinned in Task 5 and Task 6.
5. Rebuilding the corpus from the same PDFs. Expected: identical chunk ids (keyed by the PDF's SHA-256, page and position), so cached answers and logged chunk sets stay valid; a changed PDF changes the ids and the manifest's SHA-256. Pinned in Task 1 and Task 2.

---

## File Structure

- `lantern/config.py` (modify): `FILINGS_DIR`, `FILINGS_INDEX`, `LLM_MODEL = "claude-opus-5-5"`, `EMBED_MODEL = "BAAI/bge-small-en-v1.5"`, `CHUNK_TOKENS = 350`, `CHUNK_OVERLAP_TOKENS = 60`, `TOP_K = 8`, `RRF_K = 60`, `CANDIDATES = 30`, `ABSTAIN = "The filings in this corpus do not answer this"`, `GOLD_GATE = 0.90`.
- `lantern/store.py` (modify): tables `questions` and `answer_cache` with `log_question`, `questions`, `cache_get`, `cache_put`.
- `lantern/filings/__init__.py` (create, empty).
- `lantern/filings/corpus.py` (create): `Page`, `Chunk`, `ingest_pdf`, `chunk_pages`, `load_manifest`, `build_corpus`.
- `lantern/filings/retrieve.py` (create): `Embedder` protocol, `FastEmbedder`, `HashEmbedder` (test and offline fallback), `build_index`, `Retriever`, `Hit`.
- `lantern/filings/answer.py` (create): `ANSWER_SYSTEM`, `ANSWER_SCHEMA`, `Evidence`, `Answer`, `verify_quotes`, `ask`, `pre_answer`, `cache_key`.
- `lantern/filings/evaluate.py` (create): `draft_gold`, `run_eval`, `abstention_scores`; vendored harness under `lantern/filings/bfq/`.
- `lantern/api.py` (modify): `/api/filings/ask`, `/api/filings/corpus`, `/api/filings/history`, `/api/filings/eval`, PDF mount at `/filings/pdf`.
- `lantern/cli.py` (modify): `lantern filings build|ask|pre-answer|gold-draft|eval`.
- `scripts/fetch_filings.py` (create), `scripts/demo_morning.sh` (modify), `data/filings/manifest.json` (create, committed), `data/filings/prepared_questions.json` (create after the gold draft).
- `web/filings.js`, `web/styles.css`, `web/app.js`, `web/placeholders.js` (modify), `web/smoke.mjs` (modify).
- Tests: `tests/test_filings_corpus.py`, `tests/test_filings_retrieve.py`, `tests/test_filings_answer.py`, `tests/test_filings_evaluate.py`, `tests/test_api.py` (extend), fixtures `tests/fixtures/filings/ACME-AR2025.pdf`, `tests/fixtures/filings/BETA-AR2025.pdf`, `tests/fixtures/filings/manifest.json`, generator `tests/fixtures/make_filings_fixture.py`.

---

### Task 1: Corpus manifest, PDF ingest and page-aware chunks

**Files:**
- Create: `lantern/filings/__init__.py`, `lantern/filings/corpus.py`, `tests/fixtures/make_filings_fixture.py`, `tests/fixtures/filings/ACME-AR2025.pdf`, `tests/fixtures/filings/BETA-AR2025.pdf`, `tests/fixtures/filings/manifest.json`
- Modify: `lantern/config.py`, `pyproject.toml` (add `pymupdf`)
- Test: `tests/test_filings_corpus.py`

**Interfaces:**
- Produces: `Page(no: int, text: str, has_text: bool)`; `Chunk(id: str, ticker: str, company: str, filing: str, year: int, file: str, page: int, text: str)`; `ingest_pdf(path: Path) -> list[Page]`; `chunk_pages(pages: list[Page], entry: dict, file_sha: str, size_tokens: int = config.CHUNK_TOKENS, overlap_tokens: int = config.CHUNK_OVERLAP_TOKENS) -> list[Chunk]`; `load_manifest(filings_dir: Path) -> list[dict]`; `build_corpus(filings_dir: Path) -> tuple[list[Chunk], list[dict]]` returning the chunks and the manifest entries filled with `sha256`, `pages`, `pages_without_text`, `ingested_at` (UTC ISO) and written back to `manifest.json`.
- Manifest entry shape (committed file, one per filing): `{"ticker": "OCBC", "company": "Oversea-Chinese Banking Corporation", "filing": "Annual Report 2025", "year": 2025, "file": "OCBC-AR2025.pdf", "url": "https://...", "sha256": "", "pages": 0, "pages_without_text": 0, "ingested_at": ""}`.
- Chunk id: `hashlib.sha256(f"{file_sha}:{page}:{position}".encode()).hexdigest()[:16]`; `position` counts chunks within the page from 0. Token estimate: `len(text) // 4` (the FinSafeQA `token_estimate` rule). A chunk never spans two pages; a page longer than `size_tokens` is split at paragraph boundaries with `overlap_tokens` of trailing text carried into the next chunk; tables from `page.find_tables()` are appended to the page text as tab-separated rows so numbers stay searchable.

- [ ] **Step 1: Write the fixture generator and run it once**

`tests/fixtures/make_filings_fixture.py` builds two PDFs with PyMuPDF (`fitz.open()`, `page.insert_text`, `page.insert_image` from a 1x1 PNG for the image-only page) and writes `manifest.json` with two entries (`ACME`, `BETA`, year 2025, `sha256` and `pages` blank):
- `ACME-AR2025.pdf`: page 1 "ACME Holdings Annual Report 2025" cover text; page 2 "Net profit for the year ended 31 December 2025 was S$1,234 million, up 7% from S$1,153 million in 2024. The Board recommends a final dividend of 42 cents per share." plus a 3x3 table of segment revenue; page 3 an image only (no text layer).
- `BETA-AR2025.pdf`: page 1 "BETA Corporation Annual Report 2025"; page 2 "Total assets stood at S$9,876 million at year end. Employees numbered 4,321."

Run: `~/.venvs/lantern/bin/python tests/fixtures/make_filings_fixture.py`
Expected: three files under `tests/fixtures/filings/`, each PDF under 20 KB.

- [ ] **Step 2: Write the failing tests**

```python
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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `~/.venvs/lantern/bin/pytest -q tests/test_filings_corpus.py`
Expected: FAIL with `ModuleNotFoundError: lantern.filings` (after `pip install pymupdf`).

- [ ] **Step 4: Implement `corpus.py` and the config values**

`ingest_pdf` uses `fitz.open(path)`, `page.get_text("text")`, `page.find_tables()` (rows joined by tabs, appended after the text), `has_text = len(text.strip()) >= 40`. `build_corpus` reads `manifest.json`, hashes each file, ingests, chunks, writes the manifest back with the four filled fields.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `~/.venvs/lantern/bin/pytest -q tests/test_filings_corpus.py`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add lantern/filings lantern/config.py pyproject.toml tests/test_filings_corpus.py tests/fixtures/make_filings_fixture.py tests/fixtures/filings
git commit -m "feat: filings corpus — manifest, PyMuPDF ingest, page-aware chunks"
```

---

### Task 2: Index build, embeddings and the `lantern filings build` command

**Files:**
- Create: `lantern/filings/retrieve.py` (the index half; retrieval is Task 3), `scripts/fetch_filings.py`, `data/filings/manifest.json`
- Modify: `lantern/cli.py`, `pyproject.toml` (add `fastembed`, `rank-bm25`), `.gitignore` (add `data/filings/*.pdf`, `data/filings/index/`)
- Test: `tests/test_filings_retrieve.py`

**Interfaces:**
- Consumes: `corpus.build_corpus`, `Chunk`.
- Produces: `class Embedder(Protocol): def embed(self, texts: list[str]) -> np.ndarray` (float32, shape `(n, d)`, L2-normalised); `FastEmbedder(model: str = config.EMBED_MODEL)` wrapping `fastembed.TextEmbedding`; `HashEmbedder(dim: int = 64)` (a deterministic bag-of-words hash, used by tests and as the fallback when fastembed cannot load its model offline, in which case `meta.json` says so); `build_index(chunks: list[Chunk], index_dir: Path, embedder: Embedder) -> dict` writing `chunks.parquet` (every Chunk field), `embeddings.npy`, `meta.json` (`embed_model`, `built_at`, `n_chunks`, `n_files`, `pages_without_text` per file) and returning the meta dict; `lantern filings build` runs `build_corpus(config.FILINGS_DIR)` then `build_index(..., config.FILINGS_INDEX, FastEmbedder())` and prints one line per file: ticker, pages, pages without text, chunks, SHA-256 prefix.
- `scripts/fetch_filings.py`: for each manifest entry with a `url` and no file on disk, download with `requests` (User-Agent from `config.SEC_USER_AGENT`'s pattern), write to `data/filings/<file>`, print ticker, bytes, SHA-256; exit 1 listing entries without a url. The executor fills the eight urls from the companies' investor-relations pages at execution time (web search); a url that cannot be found is left blank and reported to Abhay.
- `data/filings/manifest.json`: eight entries, tickers `OCBC`, `DBS`, `UOB`, `Singtel`, `SGX`, `Keppel`, `CLI`, `Sembcorp`, `filing` "Annual Report 2025", `year` 2025, `file` `<ticker>-AR2025.pdf`.

- [ ] **Step 1: Write the failing tests**

```python
def test_hash_embedder_is_deterministic_and_normalised():
    e = retrieve.HashEmbedder(dim=64)
    a = e.embed(["net profit rose", "net profit rose"])
    assert a.shape == (2, 64) and np.allclose(a[0], a[1]) and abs(np.linalg.norm(a[0]) - 1) < 1e-6

def test_build_index_writes_chunks_embeddings_and_meta(tmp_path):
    shutil.copytree(FIXTURES / "filings", tmp_path / "filings")
    chunks, _ = corpus.build_corpus(tmp_path / "filings")
    meta = retrieve.build_index(chunks, tmp_path / "index", retrieve.HashEmbedder())
    assert meta["n_chunks"] == len(chunks) and meta["n_files"] == 2 and meta["pages_without_text"]["ACME-AR2025.pdf"] == 1
    assert np.load(tmp_path / "index" / "embeddings.npy").shape[0] == len(chunks)
    assert set(pd.read_parquet(tmp_path / "index" / "chunks.parquet")["ticker"]) == {"ACME", "BETA"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `~/.venvs/lantern/bin/pytest -q tests/test_filings_retrieve.py`
Expected: FAIL with `AttributeError: module 'lantern.filings.retrieve' has no attribute 'HashEmbedder'` (or ModuleNotFoundError).

- [ ] **Step 3: Implement the index half of `retrieve.py`, the CLI command, the fetch script and the manifest**

`HashEmbedder.embed`: for each text, lower-case word tokens, `hash(word) % dim` with Python's `hashlib.md5` (not the salted builtin) accumulating counts, then L2-normalise. `FastEmbedder.embed`: `np.asarray(list(self.model.embed(texts)), dtype=np.float32)` normalised. The CLI subcommand tree: `filings = sub.add_parser("filings"); fsub = filings.add_subparsers(dest="fcmd", required=True)` with `build`, `ask` (positional `question`), `pre-answer`, `gold-draft`, `eval`; only `build` lands in this task, the others arrive with Tasks 5 and 8.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/lantern/bin/pytest -q tests/test_filings_retrieve.py`
Expected: 2 passed.

- [ ] **Step 5: Download the eight filings and build the real index**

Run: `~/.venvs/lantern/bin/python scripts/fetch_filings.py && ~/.venvs/lantern/bin/lantern filings build`
Expected: eight lines, each with pages in the hundreds and a SHA-256 prefix; the first build downloads the embedding model once (about 130 MB) and takes a few minutes. Record the per-file counts in `docs/superpowers/plans/notes/filings-build.md`. If a url could not be found the line says `missing`, the build continues with the rest, and the final message to Abhay lists the missing filings.

- [ ] **Step 6: Commit**

```bash
git add lantern/filings/retrieve.py lantern/cli.py pyproject.toml .gitignore scripts/fetch_filings.py data/filings/manifest.json tests/test_filings_retrieve.py docs/superpowers/plans/notes/filings-build.md
git commit -m "feat: filings index — local embeddings, chunk parquet, build command, fetch script"
```

---

### Task 3: Hybrid retrieval

**Files:**
- Modify: `lantern/filings/retrieve.py`
- Test: `tests/test_filings_retrieve.py`

**Interfaces:**
- Consumes: the index files from Task 2, `Embedder`.
- Produces: `Hit(chunk: Chunk, score: float, bm25_rank: int | None, dense_rank: int | None)`; `Retriever(index_dir: Path, embedder: Embedder)` loading `chunks.parquet` and `embeddings.npy` once, building `rank_bm25.BM25Okapi` over lower-cased word tokens; `Retriever.search(question: str, k: int = config.TOP_K) -> list[Hit]`: BM25 top `config.CANDIDATES` and cosine top `config.CANDIDATES`, reciprocal rank fusion `score = sum(1 / (config.RRF_K + rank))` over the lists a chunk appears in, sorted descending, first `k`; an empty index returns `[]`; a question with no BM25 match still returns dense hits.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.fixture
def retriever(tmp_path):
    shutil.copytree(FIXTURES / "filings", tmp_path / "filings")
    chunks, _ = corpus.build_corpus(tmp_path / "filings")
    retrieve.build_index(chunks, tmp_path / "index", retrieve.HashEmbedder())
    return retrieve.Retriever(tmp_path / "index", retrieve.HashEmbedder())

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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `~/.venvs/lantern/bin/pytest -q tests/test_filings_retrieve.py -k "search or empty_index"`
Expected: FAIL with `AttributeError: ... 'Retriever'`.

- [ ] **Step 3: Implement `Hit` and `Retriever`**

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/lantern/bin/pytest -q tests/test_filings_retrieve.py`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add lantern/filings/retrieve.py tests/test_filings_retrieve.py
git commit -m "feat: hybrid BM25 and embedding retrieval with reciprocal rank fusion"
```

---

### Task 4: Grounded answering with verbatim evidence and abstention

**Files:**
- Create: `lantern/filings/answer.py`
- Modify: `lantern/store.py`, `pyproject.toml` (add `anthropic`)
- Test: `tests/test_filings_answer.py`

**Interfaces:**
- Consumes: `Retriever.search`, `Hit`, `Chunk`, `Store`.
- Produces in `store.py`: tables `questions(id INTEGER PRIMARY KEY, asked_at TEXT, question TEXT, chunk_ids TEXT, prompt_sha TEXT, model TEXT, response TEXT, answer TEXT, source TEXT, latency_ms INTEGER)` and `answer_cache(key TEXT PRIMARY KEY, answer TEXT, cached_at TEXT)`; `log_question(question: str, chunk_ids: list[str], prompt_sha: str, model: str, response: str, answer: dict, source: str, latency_ms: int, asked_at: datetime) -> int`; `questions(limit: int = 50) -> list[dict]` newest first with `answer` parsed back to a dict; `cache_get(key: str) -> dict | None`; `cache_put(key: str, answer: dict, at: datetime) -> None`.
- Produces in `answer.py`: `ABSTAIN = config.ABSTAIN`; `OFFLINE = "The answer service is offline; this morning's prepared questions still answer from the cache"`; `ANSWER_SYSTEM: str` (the rules: answer in two to four sentences only from the passages; quote evidence verbatim, at most three quotes, each copied exactly from one passage with that passage's id; if the passages do not answer, set `answerable` false and leave `answer` empty; never use outside knowledge; numbers must appear in a quote); `PROMPT_SHA = sha256(ANSWER_SYSTEM)`; `ANSWER_SCHEMA` (JSON schema: `answerable: boolean`, `answer: string`, `evidence: array of {chunk_id: string, quote: string}`, `confidence: enum high|medium|low`, all required, `additionalProperties: false`); `Evidence(chunk_id, quote, ticker, company, filing, year, file, page)`; `Answer(question, answerable, text, evidence: list[Evidence], confidence, context: list[dict], model, prompt_sha, latency_ms, source, asked_at)` with `to_dict()`; `cache_key(question: str) -> str` = sha256 of the lower-cased, whitespace-collapsed, punctuation-stripped question; `verify_quotes(evidence: list[dict], hits: list[Hit]) -> list[Evidence]` keeping a quote only when its whitespace-normalised text is a substring of the named chunk's normalised text and the quote is at least 20 characters, at most three kept; `ask(store: Store, retriever: Retriever, question: str, client=None, *, model: str = config.LLM_MODEL, now: datetime | None = None) -> Answer`.
- `ask` flow: cache hit → return it with `source="cache"`; no hits → abstention with `context=[]`, no API call, logged with `source="none"`; otherwise build the user message as numbered passages (`[chunk_id] ticker · filing · page N\n<text>`) plus the question, call `client.messages.create(model=..., max_tokens=4000, system=[{"type": "text", "text": ANSWER_SYSTEM, "cache_control": {"type": "ephemeral"}}], output_config={"effort": "medium", "format": {"type": "json_schema", "schema": ANSWER_SCHEMA}}, messages=[...])`; `stop_reason == "refusal"` → abstention logged with the category; parse the JSON text block; `verify_quotes`; `answerable and evidence` → the answer, else the abstention with `context` = the hits as `{chunk_id, ticker, filing, page, text[:400]}`; `anthropic.APIConnectionError | RateLimitError | APIStatusError | AuthenticationError` and a missing key (`client is None and not os.environ.get("ANTHROPIC_API_KEY")`) → `Answer(text=OFFLINE, source="offline", context=hits...)`, logged. The client is created lazily with `anthropic.Anthropic()` only when a call is needed.

- [ ] **Step 1: Write the failing tests**

```python
class FakeClaude:
    """Returns canned JSON through the two attributes `ask` touches: .messages.create and the response shape."""
    def __init__(self, payload: dict | None, stop_reason: str = "end_turn", raise_exc: Exception | None = None):
        self.payload, self.stop_reason, self.raise_exc, self.calls = payload, stop_reason, raise_exc, []
        self.messages = self
    def create(self, **kw):
        self.calls.append(kw)
        if self.raise_exc: raise self.raise_exc
        text = json.dumps(self.payload) if self.payload is not None else ""
        return SimpleNamespace(stop_reason=self.stop_reason, stop_details=None, content=[SimpleNamespace(type="text", text=text)], usage=SimpleNamespace(input_tokens=1, output_tokens=1, cache_read_input_tokens=0))

def test_answer_keeps_only_verbatim_quotes_and_cites_page(tmp_store, retriever):
    hits = retriever.search("final dividend", k=3)
    cid = next(h.chunk.id for h in hits if "42 cents" in h.chunk.text)
    fake = FakeClaude({"answerable": True, "answer": "ACME recommended a final dividend of 42 cents per share for 2025. The payout follows a 7% rise in net profit.",
                       "evidence": [{"chunk_id": cid, "quote": "The Board recommends a final dividend of 42 cents per share."},
                                    {"chunk_id": cid, "quote": "a final dividend of roughly forty-two cents"}], "confidence": "high"})
    a = answer.ask(tmp_store, retriever, "What final dividend did ACME recommend?", client=fake, now=datetime(2026, 11, 20, 1, tzinfo=UTC))
    assert a.answerable and len(a.evidence) == 1 and a.evidence[0].page == 2 and a.evidence[0].ticker == "ACME" and a.source == "api"
    assert fake.calls[0]["model"] == config.LLM_MODEL and fake.calls[0]["output_config"]["format"]["type"] == "json_schema"
    row = tmp_store.questions(1)[0]
    assert row["prompt_sha"] == answer.PROMPT_SHA and cid in row["chunk_ids"] and "forty-two" in row["response"]

def test_no_surviving_quote_becomes_abstention_with_context(tmp_store, retriever):
    fake = FakeClaude({"answerable": True, "answer": "Profit rose.", "evidence": [{"chunk_id": "nope", "quote": "profit rose a lot"}], "confidence": "medium"})
    a = answer.ask(tmp_store, retriever, "Did profit rise?", client=fake)
    assert not a.answerable and a.text == config.ABSTAIN and a.evidence == [] and a.context and "chunk_id" in a.context[0]

def test_no_hits_means_abstention_without_an_api_call(tmp_store, tmp_path):
    retrieve.build_index([], tmp_path / "index", retrieve.HashEmbedder())
    empty = retrieve.Retriever(tmp_path / "index", retrieve.HashEmbedder())
    fake = FakeClaude({"answerable": True, "answer": "x", "evidence": [], "confidence": "low"})
    a = answer.ask(tmp_store, empty, "Anything?", client=fake)
    assert a.text == config.ABSTAIN and fake.calls == [] and a.source == "none"

def test_cache_serves_before_the_api_and_offline_state_on_connection_error(tmp_store, retriever):
    good = FakeClaude({"answerable": True, "answer": "Total assets were S$9,876 million at year end. That is the balance-sheet size.", "evidence": [{"chunk_id": retriever.search("total assets")[0].chunk.id, "quote": "Total assets stood at S$9,876 million at year end."}], "confidence": "high"})
    first = answer.ask(tmp_store, retriever, "What were BETA's total assets?", client=good)
    tmp_store.cache_put(answer.cache_key("What were BETA's total assets?"), first.to_dict(), datetime.now(UTC))
    import anthropic
    dead = FakeClaude(None, raise_exc=anthropic.APIConnectionError(request=None))
    cached = answer.ask(tmp_store, retriever, "what were beta's total assets", client=dead)
    assert cached.source == "cache" and cached.answerable and dead.calls == []
    adhoc = answer.ask(tmp_store, retriever, "How many employees does BETA have?", client=dead)
    assert adhoc.source == "offline" and adhoc.text == answer.OFFLINE and adhoc.context

def test_refusal_stop_reason_is_an_abstention(tmp_store, retriever):
    fake = FakeClaude(None, stop_reason="refusal")
    a = answer.ask(tmp_store, retriever, "What final dividend did ACME recommend?", client=fake)
    assert a.text == config.ABSTAIN and tmp_store.questions(1)[0]["source"] == "refusal"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `~/.venvs/lantern/bin/pytest -q tests/test_filings_answer.py`
Expected: FAIL with `ModuleNotFoundError: lantern.filings.answer` (after `pip install anthropic`).

- [ ] **Step 3: Implement the store tables and `answer.py`**

`anthropic.APIConnectionError(request=None)` is the SDK's constructor shape in 1.x; if it differs, construct the exception the way `anthropic/_exceptions.py` defines it and keep the test's intent. Log every path (`api`, `cache`, `none`, `offline`, `refusal`) through `log_question`; `response` holds the raw text block or the exception class name.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/lantern/bin/pytest -q tests/test_filings_answer.py`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add lantern/filings/answer.py lantern/store.py pyproject.toml tests/test_filings_answer.py
git commit -m "feat: grounded filings answers — verbatim evidence check, abstention, question log and cache"
```

---

### Task 5: Prepared questions, `ask` and `pre-answer` commands

**Files:**
- Modify: `lantern/filings/answer.py`, `lantern/cli.py`, `scripts/demo_morning.sh`, `docs/runbook.md`
- Create: `data/filings/prepared_questions.json` (a placeholder list of three questions now; the twenty arrive with Task 8's draft)
- Test: `tests/test_filings_answer.py`

**Interfaces:**
- Consumes: `ask`, `Store.cache_put`.
- Produces: `pre_answer(store: Store, retriever: Retriever, questions: list[str], client=None, *, now: datetime | None = None) -> dict` returning `{"answered": n, "abstained": n, "offline": n}` and caching every non-offline answer under `cache_key(question)` (an offline result is never cached); `lantern filings ask "<question>"` prints the answer or the abstention sentence, then each evidence quote with ticker, filing and page; `lantern filings pre-answer` reads `data/filings/prepared_questions.json` (a JSON list of strings) and prints the three counts; `scripts/demo_morning.sh` runs `lantern filings pre-answer || echo "pre-answer had errors: cached answers from the previous run serve"` after `lantern model`.

- [ ] **Step 1: Write the failing test**

```python
def test_pre_answer_caches_answers_and_abstentions_but_not_offline(tmp_store, retriever):
    cid = retriever.search("final dividend")[0].chunk.id
    fake = FakeClaude({"answerable": True, "answer": "ACME recommended 42 cents per share. It follows a 7% profit rise.", "evidence": [{"chunk_id": cid, "quote": "The Board recommends a final dividend of 42 cents per share."}], "confidence": "high"})
    counts = answer.pre_answer(tmp_store, retriever, ["What final dividend did ACME recommend?", "What final dividend did ACME recommend?"], client=fake)
    assert counts == {"answered": 2, "abstained": 0, "offline": 0} and len(fake.calls) == 1  # the second is a cache hit
    assert tmp_store.cache_get(answer.cache_key("what final dividend did acme recommend"))["answerable"] is True
    import anthropic
    dead = FakeClaude(None, raise_exc=anthropic.APIConnectionError(request=None))
    counts = answer.pre_answer(tmp_store, retriever, ["How many employees does BETA have?"], client=dead)
    assert counts["offline"] == 1 and tmp_store.cache_get(answer.cache_key("How many employees does BETA have?")) is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `~/.venvs/lantern/bin/pytest -q tests/test_filings_answer.py -k pre_answer`
Expected: FAIL with `AttributeError: ... 'pre_answer'`.

- [ ] **Step 3: Implement `pre_answer`, the two CLI commands, the script line and the runbook paragraph**

The runbook's morning sequence gains "pre-answer the prepared questions" between the model run and the status table, and the fallback section gains one sentence: prepared questions answer from the cache offline, ad-hoc questions show the offline state.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/lantern/bin/pytest -q tests/test_filings_answer.py`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add lantern/filings/answer.py lantern/cli.py scripts/demo_morning.sh docs/runbook.md data/filings/prepared_questions.json tests/test_filings_answer.py
git commit -m "feat: prepared questions cache, filings ask and pre-answer commands"
```

---

### Task 6: API endpoints and the PDF mount

**Files:**
- Modify: `lantern/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `Retriever`, `ask`, `Store.questions`, `load_manifest`, `config.FILINGS_DIR`, `config.FILINGS_INDEX`.
- Produces: `create_app(store, *, retriever=None, llm_client=None)`: when `retriever` is None the app builds one lazily from `config.FILINGS_INDEX` with `FastEmbedder()` on first use, or serves `503 {"error": "no filings index; run lantern filings build"}` when the index directory is missing; `POST /api/filings/ask` with `{"question": str}` → `Answer.to_dict()` plus `"pdf_url": "/filings/pdf/<file>#page=<n>"` on every evidence card; empty or over-500-character questions → `400`; `GET /api/filings/corpus` → the manifest entries plus `index` meta (`embed_model`, `built_at`, `n_chunks`); `GET /api/filings/history` → `store.questions(50)` with `response` removed (the raw model text stays in the store, not on the wire); `GET /api/filings/eval` → the JSON in `config.FILINGS_DIR / "eval" / "results.json"` or `404`; `app.mount("/filings/pdf", StaticFiles(directory=config.FILINGS_DIR))` when the directory exists (PDFs only are listed in the manifest; the mount serves the directory, which holds nothing else sensitive).

- [ ] **Step 1: Write the failing tests**

```python
@pytest.fixture
def filings_app(tmp_store, tmp_path, monkeypatch):
    shutil.copytree(FIXTURES / "filings", tmp_path / "filings")
    monkeypatch.setattr(api.config, "FILINGS_DIR", tmp_path / "filings")
    chunks, _ = corpus.build_corpus(tmp_path / "filings")
    retrieve.build_index(chunks, tmp_path / "index", retrieve.HashEmbedder())
    r = retrieve.Retriever(tmp_path / "index", retrieve.HashEmbedder())
    cid = r.search("final dividend")[0].chunk.id
    fake = FakeClaude({"answerable": True, "answer": "ACME recommended 42 cents per share. It follows a 7% profit rise.", "evidence": [{"chunk_id": cid, "quote": "The Board recommends a final dividend of 42 cents per share."}], "confidence": "high"})
    return TestClient(api.create_app(tmp_store, retriever=r, llm_client=fake))

def test_ask_returns_evidence_with_pdf_links_and_logs_history(filings_app):
    body = filings_app.post("/api/filings/ask", json={"question": "What final dividend did ACME recommend?"}).json()
    assert body["answerable"] and body["evidence"][0]["pdf_url"] == "/filings/pdf/ACME-AR2025.pdf#page=2" and body["confidence"] == "high"
    hist = filings_app.get("/api/filings/history").json()
    assert hist[0]["question"].startswith("What final dividend") and "response" not in hist[0]
    assert filings_app.post("/api/filings/ask", json={"question": ""}).status_code == 400

def test_corpus_lists_manifest_and_index_meta(filings_app):
    body = filings_app.get("/api/filings/corpus").json()
    assert {m["ticker"] for m in body["filings"]} == {"ACME", "BETA"} and body["filings"][0]["pages"] == 3 and body["index"]["n_chunks"] > 0

def test_pdf_is_served_and_eval_404_before_a_run(filings_app):
    assert filings_app.get("/filings/pdf/ACME-AR2025.pdf").status_code == 200
    assert filings_app.get("/api/filings/eval").status_code == 404

def test_ask_without_index_is_503(tmp_store, tmp_path, monkeypatch):
    monkeypatch.setattr(api.config, "FILINGS_INDEX", tmp_path / "missing")
    assert TestClient(api.create_app(tmp_store)).post("/api/filings/ask", json={"question": "x"}).status_code == 503
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `~/.venvs/lantern/bin/pytest -q tests/test_api.py -k filings`
Expected: FAIL with `TypeError: create_app() got an unexpected keyword argument 'retriever'`.

- [ ] **Step 3: Implement the endpoints and the mount**

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/lantern/bin/pytest -q tests/test_api.py`
Expected: all pass (the earlier API tests plus 4).

- [ ] **Step 5: Commit**

```bash
git add lantern/api.py tests/test_api.py
git commit -m "feat: filings ask, corpus, history and eval endpoints; PDF mount"
```

---

### Task 7: The Filings Q&A page

**Files:**
- Create: `web/filings.js`
- Modify: `web/app.js`, `web/placeholders.js`, `web/styles.css`, `web/index.html`, `web/smoke.mjs`

**Interfaces:**
- Consumes: the four endpoints and the PDF mount from Task 6; the look and tokens in `styles.css`; `window.Lantern` module pattern (`charts.js`, `monitor.js`).
- Produces: `window.Lantern.filings.render(root)`; `app.js` routes `#filings` to it (and removes `filings` from `placeholders.PAGES`). Layout: a two-column grid; left column (2fr): the question form (`<form id="ask-form">` with `<input id="ask-input">` and an "Ask" button; `submit` is handled in script), the answer card (`#answer`: the 2–4 sentence answer or the abstention sentence in `.sub` style; a confidence pill `calm`/`elevated`/`high` style reused as `conf-high`/`conf-medium`/`conf-low`; evidence cards `.evidence` each with the verbatim quote in a `<blockquote>`, the line "ticker · filing · page N" and an `<a target="_blank" href="/filings/pdf/<file>#page=<n>">Open page</a>`; when abstaining, a "Nearest passages, shown as context" list of the `context` items in muted type with no quote marks and no page link styling as evidence; when offline, the offline sentence in the `warn` colour), and the history rail (`#history`: the session's questions newest first, click re-asks); right column (1fr): the corpus table (`#corpus-table`: company, filing, year, pages, pages without text, ingested, SHA-256 prefix) with the index line under it ("n chunks · model · built at"). Loading state: the Ask button disabled with "Asking…" while the request is in flight; errors from the API shown in the answer card. No new colours, no icons, no gradients.
- `smoke.mjs`: navigate to `#filings`, assert `#corpus-table tbody tr` count ≥ 1, type a prepared question into `#ask-input` (the first entry of `data/filings/prepared_questions.json`, read by the smoke script from disk), submit, wait up to 10 s, assert `#answer` text contains either an evidence card or the abstention sentence and never "undefined"/"null"; assert `#history li` count ≥ 1; still zero console errors.

- [ ] **Step 1: Run the smoke test to verify it fails against the placeholder**

Run: `cd web && LANTERN_URL=http://127.0.0.1:8787 node smoke.mjs`
Expected: `smoke FAIL` listing `corpus table missing` and `ask form missing`.

- [ ] **Step 2: Implement `filings.js`, the routing, the styles and the index.html script tag**

- [ ] **Step 3: Run the smoke test to verify it passes, then look at it**

Run: `cd web && LANTERN_URL=http://127.0.0.1:8787 node smoke.mjs` (server restarted on the new code, index built, at least the three placeholder prepared questions pre-answered)
Expected: `smoke ok`. Take a screenshot of `#filings` after a question and compare against the approved look: the answer card reads first, evidence quotes are set in the body face with a hairline left rule, the corpus table uses the monitor's table styles, nothing glows.

- [ ] **Step 4: Commit**

```bash
git add web
git commit -m "feat: Filings Q&A page — question box, evidence cards with page links, abstention context, history rail, corpus table"
```

---

### Task 8: Gold set draft, evaluation with the BharatFinQA harness, release gate on the Model risk page

**Files:**
- Create: `lantern/filings/bfq/__init__.py`, `lantern/filings/bfq/bfq_judge.py`, `lantern/filings/bfq/bfq_metrics.py`, `lantern/filings/bfq/bfq_score.py` (vendored verbatim from the archive), `lantern/filings/evaluate.py`, `data/filings/gold/README.md`
- Modify: `lantern/cli.py`, `web/placeholders.js` (Model risk page shows the eval results when present), `lantern/api.py` only if Task 6 left `/api/filings/eval` reading a different path
- Test: `tests/test_filings_evaluate.py`

**Interfaces:**
- Consumes: `Retriever`, `ask`, `FakeClaude` pattern, the harness functions.
- Produces: `draft_gold(retriever: Retriever, client, *, n_answerable: int = 30, n_unanswerable: int = 10, seed: int = 7) -> list[dict]`: samples `n_answerable` chunks that contain a number (regex `\d`) spread across tickers in proportion, asks Claude for one question per chunk answerable only from that chunk with the answer and a verbatim quote (JSON schema `{question, answer, quote, tier: easy|medium|hard}`), keeps the row only when `quote` passes `verify_quotes` against that chunk; writes `n_unanswerable` rows by asking Claude for questions about each company that this corpus cannot answer (a figure from another year, a product not in the report), marked `unanswerable: true`; each row: `{"item_id": "g001", "question", "company": ticker, "answer", "evidence": {"file", "page", "chunk_id", "quote"}, "unanswerable": bool, "tier"}`; written to `data/filings/gold/gold_draft.jsonl`; the twenty most demo-worthy answerable questions (the builder picks: one or two per company, numbers and policy statements) are also written to `data/filings/prepared_questions_draft.json` for Abhay to accept into `prepared_questions.json`.
- `run_eval(store, retriever, gold_path: Path, client=None, *, judge_model: str = "deepseek-ai/DeepSeek-V4-Pro") -> dict`: asks every gold question through `ask` (cache bypassed), writes `pred.jsonl` in the harness prediction format (`predicted_answer` is the answer text or the abstention sentence, `unanswerable` from gold), runs the vendored `bfq_score.main()` via `subprocess` with `--pred --gold --judge <judge_model> --provider openrouter --refusal semantic --gate 90 --out results_bfq.json` when `OPENROUTER_API_KEY` is set (deterministic metrics only otherwise, noted in the result), then computes `abstention_scores(pred_rows)` = `{"precision": abstained_on_unanswerable / abstained, "recall": abstained_on_unanswerable / unanswerable, "n": ...}` where "abstained" means the prediction equals `config.ABSTAIN`; writes `data/filings/eval/results.json` = `{"run_at", "model", "prompt_sha", "judge", "n", "abstention": {...}, "bfq": <results_bfq.json or null>, "gate": {"threshold": config.GOLD_GATE, "pass": precision >= threshold}}` and returns it.
- `lantern filings gold-draft` and `lantern filings eval [--gold path]`; the Model risk placeholder renders the results table (run time, model, judge, n, abstention precision and recall, BFQ score per tier when present, gate pass or fail in the status colours) when `/api/filings/eval` is 200.
- `bfq_metrics.is_refusal` must recognise the Lantern abstention sentence: `evaluate.py` wraps it — a prediction equal to `config.ABSTAIN` is a refusal before the harness regex runs — and passes `CANONICAL_REFUSAL`-style predictions through unchanged.

- [ ] **Step 1: Vendor the harness**

Run: `cd ~/lantern && mkdir -p lantern/filings/bfq && for f in bfq_judge bfq_metrics bfq_score; do unzip -p "/Volumes/Elements/Abhay's MacBook M3 Pro/BharatFinQA/BharatFinQA_software.zip" harness/$f.py > lantern/filings/bfq/$f.py; done && touch lantern/filings/bfq/__init__.py && ~/.venvs/lantern/bin/python -c "import lantern.filings.bfq.bfq_metrics as m; print(m.CANONICAL_REFUSAL)"`
Expected: `Not found in the provided evidence.` Read `bfq_score.py::main()` once and copy the exact gold field names it reads into the `draft_gold` row shape above if they differ (`item_id`, `question`, `company`, `answer`, `tier`, `unanswerable` are the expected names).

- [ ] **Step 2: Write the failing tests**

```python
def test_draft_gold_keeps_only_verified_quotes_and_marks_unanswerable(retriever):
    cid = retriever.search("final dividend")[0].chunk.id
    fake = FakeClaude({"question": "What final dividend did ACME recommend for 2025?", "answer": "42 cents per share", "quote": "The Board recommends a final dividend of 42 cents per share.", "tier": "easy"})
    rows = evaluate.draft_gold(retriever, fake, n_answerable=2, n_unanswerable=1)
    assert sum(not r["unanswerable"] for r in rows) <= 2 and all(r["evidence"]["page"] for r in rows if not r["unanswerable"])
    assert any(r["unanswerable"] for r in rows) and all(r["item_id"].startswith("g") for r in rows)

def test_run_eval_scores_abstention_precision_and_gate(tmp_store, tmp_path, retriever, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    cid = retriever.search("final dividend")[0].chunk.id
    gold = [{"item_id": "g001", "question": "What final dividend did ACME recommend?", "company": "ACME", "answer": "42 cents per share", "evidence": {"file": "ACME-AR2025.pdf", "page": 2, "chunk_id": cid, "quote": "42 cents"}, "unanswerable": False, "tier": "easy"},
            {"item_id": "g002", "question": "What was ACME's net profit in 2019?", "company": "ACME", "answer": "", "evidence": None, "unanswerable": True, "tier": "hard"}]
    gold_path = tmp_path / "gold.jsonl"; gold_path.write_text("\n".join(json.dumps(g) for g in gold))
    fake = FakeClaude({"answerable": True, "answer": "ACME recommended 42 cents per share. It follows a 7% profit rise.", "evidence": [{"chunk_id": cid, "quote": "The Board recommends a final dividend of 42 cents per share."}], "confidence": "high"})
    monkeypatch.setattr(evaluate.config, "FILINGS_DIR", tmp_path)
    res = evaluate.run_eval(tmp_store, retriever, gold_path, client=fake)
    assert res["n"] == 2 and res["bfq"] is None and res["gate"]["threshold"] == 0.90
    assert 0 <= res["abstention"]["precision"] <= 1 and (tmp_path / "eval" / "results.json").exists()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `~/.venvs/lantern/bin/pytest -q tests/test_filings_evaluate.py`
Expected: FAIL with `ModuleNotFoundError: lantern.filings.evaluate`.

- [ ] **Step 4: Implement `evaluate.py`, the two CLI commands and the Model risk rendering**

- [ ] **Step 5: Run the tests to verify they pass**

Run: `~/.venvs/lantern/bin/pytest -q tests/test_filings_evaluate.py`
Expected: 2 passed.

- [ ] **Step 6: Draft the real gold set and the prepared questions**

Run: `~/.venvs/lantern/bin/lantern filings gold-draft` (needs `ANTHROPIC_API_KEY`; about 45 calls)
Expected: `data/filings/gold/gold_draft.jsonl` with 40 rows (30 answerable with verified quotes, 10 unanswerable) and `data/filings/prepared_questions_draft.json` with 20 questions. Read every row once; fix obviously bad questions by hand; write `data/filings/gold/README.md` telling Abhay how to verify (open the PDF at the page, confirm the quote answers the question, flip `unanswerable` or delete the row, then save as `gold.jsonl`). Copy the draft to `prepared_questions.json` so the demo path works before Abhay's review.

- [ ] **Step 7: Commit**

```bash
git add lantern/filings/bfq lantern/filings/evaluate.py lantern/cli.py web/placeholders.js tests/test_filings_evaluate.py data/filings/gold data/filings/prepared_questions.json data/filings/prepared_questions_draft.json
git commit -m "feat: gold-set draft, BharatFinQA-scored evaluation, abstention gate on the Model risk page"
```

---

### Task 9: First end-to-end run, pre-answer, runbook and README

**Files:**
- Modify: `README.md`, `docs/runbook.md`, `docs/superpowers/plans/notes/filings-build.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Full run on the real corpus**

Run: `cd ~/lantern && ~/.venvs/lantern/bin/lantern filings build && ~/.venvs/lantern/bin/lantern filings pre-answer && ~/.venvs/lantern/bin/lantern filings eval --gold data/filings/gold/gold_draft.jsonl`
Expected: eight files indexed; `answered` 20 or close with `offline` 0; `results.json` written with abstention precision and, when `OPENROUTER_API_KEY` is set, the BFQ block. Record the counts, the precision and recall, the judge used and the cost from `usage` in `docs/superpowers/plans/notes/filings-build.md`. If precision is below 0.90 on the draft set, say so plainly in the final message: the gate is evaluated on Abhay's verified set, and the prompt or retrieval gets one tuning pass after that, not before.

- [ ] **Step 2: Demo-morning dry run**

Run: `scripts/demo_morning.sh --port 8788`, then open `#filings`, ask one prepared question and one ad-hoc question, open an evidence link.
Expected: the prepared question answers from the cache (`source` cache in the history endpoint), the ad-hoc question calls the API, the PDF opens at the cited page, the smoke test passes against 8788.

- [ ] **Step 3: README and runbook**

README gains a "Filings Q&A" section: the five commands, the manifest, the index directory, the two keys in `.env`, the gold-set workflow and the gate. The runbook gains the Filings checks by eye (corpus table shows eight filings with today's SHA prefixes; one prepared question; one ad-hoc question; one PDF link) and the offline line.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/runbook.md docs/superpowers/plans/notes/filings-build.md
git commit -m "docs: Filings Q&A commands, gold-set workflow and demo checks"
```

---

## Self-review notes

- Spec coverage: question box, corpus list with company/filing/year/pages/date/SHA (Tasks 1, 6, 7); 2–4 sentence answer, 1–3 verbatim evidence cards with filing, page and PDF link, confidence label, exact abstention sentence with nearest passages as context, history rail (Tasks 4, 6, 7); corpus rebuildable with one command (Task 2); PyMuPDF ingest, chunks tagged and stored with SHA-256, local embeddings, hybrid retrieval top eight (Tasks 1–3); Claude through the Anthropic API with evidence-only answers and full logging (Task 4); 20 pre-answered questions for a dead connection (Task 5); 40-question gold set drafted by the builder, verified by Abhay, scored with the BharatFinQA judge, reported on Model risk, release gate at 90% (Task 8); demo-morning integration (Tasks 5, 9). The OCR pass and the local open-weight model are out of the three-week path by the spec's own words.
- Interfaces named consistently: `Page`, `Chunk`, `ingest_pdf`, `chunk_pages`, `load_manifest`, `build_corpus`, `Embedder`, `HashEmbedder`, `FastEmbedder`, `build_index`, `Retriever`, `Hit`, `ask`, `pre_answer`, `cache_key`, `verify_quotes`, `Answer`, `Evidence`, `draft_gold`, `run_eval`, `abstention_scores`, `create_app(store, retriever=, llm_client=)`.
- Review Focus 1 pinned by `test_ingest_counts_pages_without_text` and `test_chunks_carry_page_and_filing_and_never_cite_an_imageless_page`; 2 by `test_no_hits_means_abstention_without_an_api_call`; 3 by `test_answer_keeps_only_verbatim_quotes_and_cites_page` and `test_no_surviving_quote_becomes_abstention_with_context`; 4 by `test_cache_serves_before_the_api_and_offline_state_on_connection_error`, `test_pre_answer_caches_answers_and_abstentions_but_not_offline` and `test_ask_without_index_is_503`; 5 by `test_build_corpus_fills_manifest_and_ids_are_deterministic`.
- Builder's calls recorded here, not in the spec: `claude-opus-5-5` at `medium` effort without a server-side refusal fallback; `fastembed` with `bge-small-en-v1.5` instead of a torch-based model; chunks of about 350 tokens with 60 of overlap, never across pages; reciprocal rank fusion with k = 60 over 30 candidates per ranker; abstention precision computed on exact matches of the abstention sentence; the persona prompt written fresh.
