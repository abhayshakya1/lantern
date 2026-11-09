"""Download and verify the market-wide annual reports named in data/market/manifest_market.json.

Honest client, throttled, idempotent: each entry needs company, stock_code, url (a PDF on the
issuer's own domain). A download is kept only when it is a real PDF whose first pages mention the
company, and the manifest row records sha256, size and pages. Run: python scripts/market/fetch_market.py
"""

import hashlib
import json
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lantern import config  # noqa: E402

MARKET = Path("data/market")
UA = {"User-Agent": config.SEC_USER_AGENT}
MAX_MB = 120
THROTTLE_S = 2.0


_ABBREV = {"hldgs", "hldg", "ltd", "inc", "intl", "grp", "corp", "bhd", "tbk"}


def _name_token(company: str) -> str:
    """Longest word of the issuer name that a real report would print (not SGX abbreviations)."""
    words = [w for w in re.findall(r"[a-z]{3,}", company.lower()) if w not in _ABBREV]
    return max(words or [""], key=len)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]


def main() -> int:
    manifest_path = MARKET / "manifest_market.json"
    rows = json.loads(manifest_path.read_text())
    (MARKET / "pdfs").mkdir(parents=True, exist_ok=True)
    ok = bad = skipped = 0
    for row in rows:
        if row.get("status") == "ok":
            skipped += 1
            continue
        url = row.get("url") or ""
        if not url:
            row["status"] = "no-url"
            continue
        dest = MARKET / "pdfs" / f"{_slug(row['company'])}.pdf"
        try:
            r = requests.get(url, headers=UA, timeout=180, stream=True)
            r.raise_for_status()
            data = b""
            for chunk in r.iter_content(1 << 20):
                data += chunk
                if len(data) > MAX_MB << 20:
                    raise ValueError("too large")
        except Exception as exc:
            row["status"] = f"fetch-failed: {type(exc).__name__}"
            bad += 1
            print(f"{row['company'][:40]:42} {row['status']}")
            time.sleep(THROTTLE_S)
            continue
        if not data.startswith(b"%PDF"):
            row["status"] = "not-a-pdf"
            bad += 1
        else:
            import pymupdf

            dest.write_bytes(data)
            doc = pymupdf.open(dest)
            head = " ".join(doc[i].get_text() for i in range(min(5, len(doc)))).lower()
            token = _name_token(row["company"])
            if token and token not in head:
                row["status"] = "name-mismatch"  # kept on disk for manual review, not counted ok
                bad += 1
            else:
                row.update({"status": "ok", "file": dest.name, "pages": len(doc),
                            "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
                ok += 1
            doc.close()
        print(f"{row['company'][:40]:42} {row['status']}")
        time.sleep(THROTTLE_S)
    manifest_path.write_text(json.dumps(rows, indent=1))
    print(f"\nok {ok}, failed {bad}, already done {skipped}, total {len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
