"""Builds the two small annual-report PDFs the filings tests run on. Run once: python tests/fixtures/make_filings_fixture.py"""

import json
from pathlib import Path

import pymupdf as fitz

OUT = Path(__file__).parent / "filings"


def _page(doc, lines: list[str], y0: float = 72):
    page = doc.new_page(width=595, height=842)  # A4 points
    y = y0
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 16
    return page


def _table(page, top: float, rows: list[list[str]]):
    """A ruled 3x3 grid so PyMuPDF's find_tables sees it as a table."""
    x0, w, h = 72, 140, 20
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            rect = fitz.Rect(x0 + c * w, top + r * h, x0 + (c + 1) * w, top + (r + 1) * h)
            page.draw_rect(rect, color=(0, 0, 0), width=0.5)
            page.insert_text((rect.x0 + 4, rect.y1 - 6), cell, fontsize=9)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    acme = fitz.open()
    _page(acme, ["ACME Holdings Annual Report 2025", "Singapore Exchange Mainboard listed"])
    p2 = _page(
        acme,
        [
            "Net profit for the year ended 31 December 2025 was S$1,234 million, up 7% from",
            "S$1,153 million in 2024. The Board recommends a final dividend of 42 cents per share.",
            "Segment revenue (S$ million):",
        ],
    )
    _table(p2, 130, [["Segment", "2025", "2024"], ["Banking", "4,120", "3,900"], ["Insurance", "1,010", "960"]])
    p3 = acme.new_page(width=595, height=842)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 1, 1))  # a 1x1 image: no text layer on this page
    p3.insert_image(fitz.Rect(72, 72, 300, 300), stream=pix.tobytes("png"))
    acme.save(OUT / "ACME-AR2025.pdf")

    beta = fitz.open()
    _page(beta, ["BETA Corporation Annual Report 2025"])
    _page(beta, ["Total assets stood at S$9,876 million at year end. Employees numbered 4,321.", "Return on equity was 11.2%."])
    beta.save(OUT / "BETA-AR2025.pdf")

    manifest = [
        {"ticker": "ACME", "company": "ACME Holdings", "filing": "Annual Report 2025", "year": 2025, "file": "ACME-AR2025.pdf",
         "url": "", "sha256": "", "pages": 0, "pages_without_text": 0, "ingested_at": ""},
        {"ticker": "BETA", "company": "BETA Corporation", "filing": "Annual Report 2025", "year": 2025, "file": "BETA-AR2025.pdf",
         "url": "", "sha256": "", "pages": 0, "pages_without_text": 0, "ingested_at": ""},
    ]
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for f in sorted(OUT.iterdir()):
        print(f.name, f.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
