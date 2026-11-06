"""The filings corpus: a manifest per PDF, PyMuPDF text per page, and page-aware chunks.

Ported from FinSafeQA's ingest contract: the text layer only (pages with fewer than 40 characters are counted
as having no text and are never chunked, so no answer can cite them), tables appended as tab-separated rows.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pymupdf

from lantern import config

MIN_TEXT_CHARS = 40
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Page:
    no: int
    text: str
    has_text: bool


@dataclass(frozen=True)
class Chunk:
    id: str
    ticker: str
    company: str
    filing: str
    year: int
    file: str
    page: int
    text: str


def token_estimate(text: str) -> int:
    return len(text) // 4


def ingest_pdf(path: Path) -> list[Page]:
    doc = pymupdf.open(path)
    pages = []
    for i, pg in enumerate(doc):
        raw = pg.get_text("text").strip()
        rows = []
        try:
            for table in pg.find_tables().tables:
                for row in table.extract():
                    cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                    if cells:
                        rows.append("\t".join(cells))
        except Exception:  # ponytail: table detection is best effort; the text layer already holds the numbers
            pass
        text = (raw + ("\n" + "\n".join(rows) if rows else "")).strip()
        pages.append(Page(no=i + 1, text=text, has_text=len(raw) >= MIN_TEXT_CHARS))
    return pages


def _units(text: str, size_chars: int) -> list[str]:
    """Lines of the page (PDF text comes line by line); a line longer than a chunk is split into sentences."""
    units = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        units.extend(_SENTENCE.split(line) if len(line) > size_chars else [line])
    return [u for u in units if u]


def chunk_pages(
    pages: list[Page],
    entry: dict,
    file_sha: str,
    size_tokens: int = config.CHUNK_TOKENS,
    overlap_tokens: int = config.CHUNK_OVERLAP_TOKENS,
) -> list[Chunk]:
    size, overlap = size_tokens * 4, overlap_tokens * 4
    out = []
    for page in pages:
        if not page.has_text:
            continue
        pieces, cur = [], ""
        for unit in _units(page.text, size):
            if cur and len(cur) + 1 + len(unit) > size:
                pieces.append(cur)
                cur = (cur[-overlap:].strip() + " " + unit).strip() if overlap else unit  # the tail carries over
            else:
                cur = f"{cur} {unit}".strip()
        if cur:
            pieces.append(cur)
        for pos, text in enumerate(pieces):
            cid = hashlib.sha256(f"{file_sha}:{page.no}:{pos}".encode()).hexdigest()[:16]
            out.append(Chunk(cid, entry["ticker"], entry["company"], entry["filing"], int(entry["year"]), entry["file"], page.no, text))
    return out


def load_manifest(filings_dir: Path) -> list[dict]:
    return json.loads((Path(filings_dir) / "manifest.json").read_text())


def build_corpus(filings_dir: Path) -> tuple[list[Chunk], list[dict]]:
    """Every PDF in the manifest: hash, ingest, chunk; the manifest is written back with what was found."""
    filings_dir = Path(filings_dir)
    manifest = load_manifest(filings_dir)
    chunks: list[Chunk] = []
    now = datetime.now(UTC).isoformat()
    for entry in manifest:
        path = filings_dir / entry["file"]
        if not path.is_file():
            entry.update({"sha256": "", "pages": 0, "pages_without_text": 0, "ingested_at": ""})
            continue
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        pages = ingest_pdf(path)
        chunks.extend(chunk_pages(pages, entry, sha))
        entry.update({"sha256": sha, "pages": len(pages), "pages_without_text": sum(not p.has_text for p in pages), "ingested_at": now})
    (filings_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return chunks, manifest
