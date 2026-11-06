# Filings corpus builds

## First build, 2026-11-07 09:09Z (17:09 SGT)

Eight 2025 annual reports fetched by `scripts/fetch_filings.py` from the companies' own sites or their SGX filings (URLs in `data/filings/manifest.json`), ingested with PyMuPDF's text layer, chunked per page (about 350 tokens, 60 of overlap) and embedded with fastembed's `BAAI/bge-small-en-v1.5` (model downloaded once, about 130 MB).

| Ticker | Pages | Pages without text | Chunks | SHA-256 prefix |
| --- | --- | --- | --- | --- |
| OCBC | 276 | 4 | 893 | d10f4fc11fd5 |
| DBS | 107 | 1 | 801 | e7952ba9dff9 |
| UOB | 248 | 4 | 660 | ac6461b1773f |
| Singtel | 278 | 5 | 814 | 818e7f067f21 |
| SGX | 238 | 4 | 697 | a62d58cdc87a |
| Keppel | 245 | 1 | 928 | 681b236d23e1 |
| CLI | 202 | 0 | 585 | e48ee55cc159 |
| Sembcorp | 135 | 1 | 778 | b284229ce6d2 |

Index: 6,156 chunks from 8 files. Embedding the corpus on the laptop CPU takes about ten minutes, so the build is a one-off (not part of demo morning); the index directory is git-ignored and rebuilds with one command, `lantern filings build`. Pages without text are cover and divider pages made of images; they are counted and never cited. The Keppel copy is the original SGX filing; Keppel refiled on 27 March 2026 to correct a typo on page 86 (a 2021 share award), which does not touch any figure.
