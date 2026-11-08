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

## First end-to-end run with keys, 2026-11-07 (SGT evening)

- `lantern filings gold-draft`: 40 rows in 2m25s (30 answerable with verified verbatim quotes, 10 probes; CLI 6, DBS 6, Keppel/OCBC/SGX/Sembcorp/Singtel 5, UOB 3; easy 24, medium 8, hard 8). Draft at `data/filings/gold/gold_draft.jsonl`; 20 prepared questions promoted pending Abhay's review.
- `lantern filings eval --gold gold_draft.jsonl` with the DeepSeek-V4-Pro judge (OpenRouter slug `deepseek/deepseek-v4-pro-0813`; the paper's name is not an OpenRouter id): abstention precision 0.83 (12 abstentions, 10 of them probes), recall 1.00; judge llm_correct 0.83 easy / 0.80 medium / 1.00 hard; harness H-Ref 100% PASS; BFQ-Score composite absent because this set has no multihop tier. Lantern gate FAIL at the 0.90 threshold: two answerable draft questions abstain (g014 Sembcorp depreciation useful lives, g018 DBS deferred tax asset — both table-dense pages). The gate is judged on Abhay's verified `gold.jsonl`; the plan allows one retrieval/prompt tuning pass after that, not before.
- Demo-morning dry run (`scripts/demo_morning.sh --port 8788`): pull live, model run, 20 questions pre-answered (18 answered, 2 abstained, 0 offline), serving after about 90 seconds. A prepared question answers from the cache with its evidence card and the PDF opens at the cited page; an ad-hoc unanswerable question abstains through the API; the browser smoke test passes against 8788.
- Deathstar: secret-free build job scheduled in tmux session `lantern-build` (venv in `~/Abhay/venvs/lantern`, log `~/Abhay/lantern-build.log`); API keys stay on the laptop because research3 is a shared login.
