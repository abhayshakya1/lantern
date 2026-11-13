# SGX Market-Wide Corpus Plan

**Goal:** Filings Q&A over every company listed on SGX (Mainboard + Catalist, ~620 issuers), up from
the demo eight — the latest annual report per issuer.

## What the access spike established (2026-11-09)

- `api.sgx.com` (announcements) and all of `links.sgx.com` — detail pages AND attachments — return
  401/403 to scripted clients, even with an honest User-Agent (Akamai bot protection). Per the
  project's standing rule, no identity masking, no circumvention: these paths are browser-only.
- The public announcements UI works fully in a real browser: category **ANNC30 = Annual Reports and
  Related Documents** is URL-addressable, rows expose issuer + announcement URL, and each detail
  page lists the attachment PDFs. A browser harvest is legitimate but costs thousands of
  interactive steps for ~800 reports — a gap-filling tool, not the bulk path.
- `api.sgx.com/securities/v1.1/gtis` (SGTI index) is open to scripts: 250 unique issuers with stock
  codes recovered (111 current-year) → `data/filings/sgx_universe.json`, the seed universe.
- Company investor-relations sites serve AR PDFs to honest scripted clients (proven: all eight demo
  filings, five hosts).

## Design: three tracks

1. **Bulk (scriptable, honest):** per-issuer AR discovery against the company's own IR site
   (web search per company → candidate PDF URL on the company domain → honest-UA download →
   `%PDF` + issuer-name sanity check), appending verified entries to a market-wide manifest.
   Expected automated coverage 60–80%; run in batches of ~25 issuers.
2. **Gap-fill (browser):** the SGX ANNC30 listing in the user's Chrome for issuers track 1 misses.
3. **Production story (pitch):** a licensed SGX data feed / the bank's existing market-data
   entitlements replace both tracks on deployment — stated plainly in the deck; the per-document
   pipeline is identical from ingest onward.

## Scale engineering (phased, each with a measurement gate)

- Universe: complete the issuer list (SGX ISIN directory / listings index) → ~620 rows.
- Ingest & index: ~600 PDFs ≈ 150k pages ≈ 600–800k chunks. Embedding on Deathstar (CPU cores or
  GPU); index size ~1.5 GB — fine on the demo laptop.
- Retrieval at scale: rank_bm25 is pure Python and may not hold at 700k chunks — perf test first;
  swap to `bm25s` behind the same interface if query latency exceeds ~1 s.
- Gold set and gate: the 40-question gold methodology extends with a stratified sample across
  sectors once the corpus lands; the demo-eight gate stays the release gate meanwhile.
- UI: corpus table becomes searchable/paginated beyond ~20 rows.

## Status

Phase 1 (universe seed) committed. Tracks and phases above run across sessions; each batch commits
its manifest increment so progress is durable and resumable.

2026-11-10:
- **Track 1 (issuer IR sites):** discovery over all 133 seed rows complete. 49 verified, plus the
  14 below, for 63 verified reports. Coverage falls in small caps (21–25% per batch) because many
  publish only on SGX or sit behind a WAF. Trendlines (TLS failure) and Jawala (image-only, needs
  OCR) are recorded failures.
- **Track 2 (browser gap-fill):** done for the STI. The 14 constituents missing from track 1 were
  located on SGX ANNC30 and saved by the user. `fetch_market.py` imports them through
  `browser_glob`, applying the same PDF and name checks.
- **STI in Filings Q&A:** all 30 constituents are in `data/filings/manifest.json`; the 22 new ones
  are hard links to `data/market/pdfs`. The 8-company index is kept at `data/filings/index_demo8`,
  because the 40-question gold gate was drafted against it.
- The PDFs are mirrored to Deathstar at `data/market/pdfs`.
- **REITs and business trusts (2026-11-11):** 35 of the 36 trusts are verified and in Filings Q&A,
  65 filings in total. The one missing is UI Boustead REIT: it listed in March 2026 and has not yet
  published an annual report. 14 of the 35 came through the browser route, because the rest of
  `*.listedcompany.com` and several IR sites return a WAF challenge (HTTP 202). The market corpus
  is now 98 verified reports out of 169 rows. The index is built on Deathstar GPU 4
  (`LANTERN_EMBED_CUDA=1`, venv `embed-gpu`). PDF table extraction runs on the CPU and dominates the
  build time.
- **Embedder A/B (2026-11-13):** bge-base-en-v1.5 re-embedded the same 51,071 chunks on Deathstar
  GPU 3 (200s, batch 32 — the shared 11GB cards had ~2.7GB free) and scored identically to
  bge-small on the gold set: hit@8 22/30, wrong-company top-1 7/30, missing the same questions.
  The embedder is not the bottleneck; bge-small stays. This matches FinMTEB (EMNLP 2025,
  arXiv:2502.10990): dense-model ranking matters less on finance text, where lexical signal is
  strong — Lantern's hybrid BM25 + dense fusion already leans on that. A finance fine-tune is a
  post-pitch item at most; FinMTEB's top model (Fin-E5) is a 7B GPU embedder, unusable in the
  on-prem laptop story.
