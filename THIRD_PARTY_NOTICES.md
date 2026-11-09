# Third-party notices

Lantern is proprietary software (see LICENSE). It builds on the following third-party components
and data sources, each governed by its own license or terms. This file is the due-diligence ledger
a deployment review should start from.

## Attention items (resolve before commercial deployment)

| Component | License | Why it needs attention |
|---|---|---|
| PyMuPDF (`pymupdf`) | **AGPL-3.0** (dual-licensed) | AGPL obligations attach to commercial use. Artifex sells commercial licenses; budget one, or swap the PDF layer (e.g. pdfplumber, MIT) before selling the product. |
| Yahoo Finance data (via `yfinance`, Apache-2.0) | Yahoo terms of service | The library is Apache; the **data** is not. Fine for research and demos; a production deployment needs licensed market data (e.g. exchange or vendor feeds). |
| TimesFM **3.0** weights | TimesFM Non-Commercial License | **Deliberately not used.** Lantern pins the 2.5 checkpoint (Apache-2.0). Do not swap 3.0 in without a Google Cloud commercial path. |

## Models (all run locally)

| Model | License |
|---|---|
| google/timesfm-2.5-200m-pytorch (challenger fan) | Apache-2.0 |
| Qwen/Qwen2.5-3B / 7B / 14B / 32B Instruct (on-prem answerer and judges) | Apache-2.0 |
| BAAI/bge-small-en-v1.5 (embeddings) | MIT |
| claude-opus-5-5 (optional cloud answerer) | Anthropic commercial terms; API key required |

## Libraries

Apache-2.0: fastembed, rank-bm25, requests, yfinance, timesfm.
MIT: FastAPI, pydantic, anthropic SDK, marked, puppeteer-core.
BSD-3-Clause: pandas, numpy, scipy, uvicorn, starlette.
PSF/compatible: Python standard library.

## Data sources (public pulls, each recorded with URL, time and hash in provenance)

SEC EDGAR (public domain, fair-access policy and honest User-Agent respected), FRED (St. Louis Fed
terms, API key), SSGA fund holdings (publisher terms), AAII sentiment survey (publisher terms),
Shiller/Yale CAPE data (academic use), company annual reports (publisher investor-relations terms).

## In-house components

The BharatFinQA scoring harness (`lantern/filings/bfq/`, vendored verbatim) and the FinSafeQA-XL
training data are the copyright holder's own research work.
