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
