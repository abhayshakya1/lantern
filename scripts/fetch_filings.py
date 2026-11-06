"""Download the manifest's PDFs that are not on disk yet. Run from the repo root: python scripts/fetch_filings.py"""

import hashlib
import json
import sys

import requests

from lantern import config

UA = {"User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/128 Safari/537.36"}


def main() -> int:
    d = config.FILINGS_DIR
    manifest = json.loads((d / "manifest.json").read_text())
    missing = []
    for m in manifest:
        path = d / m["file"]
        if path.is_file():
            print(f"{m['ticker']:10} present  {path.stat().st_size:>12,} bytes")
            continue
        if not m.get("url"):
            print(f"{m['ticker']:10} no url")
            missing.append(m["ticker"])
            continue
        try:
            r = requests.get(m["url"], headers=UA, timeout=180)
            r.raise_for_status()
        except requests.RequestException as exc:
            print(f"{m['ticker']:10} failed   {type(exc).__name__}")
            missing.append(m["ticker"])
            continue
        if not r.content.startswith(b"%PDF"):
            print(f"{m['ticker']:10} not a PDF at {m['url']}")
            missing.append(m["ticker"])
            continue
        path.write_bytes(r.content)
        print(f"{m['ticker']:10} fetched  {len(r.content):>12,} bytes  sha256 {hashlib.sha256(r.content).hexdigest()[:12]}")
    if missing:
        print("missing:", ", ".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
