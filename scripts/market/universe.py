"""Every SGX-listed equity issuer (stocks, REITs, business trusts) from SGX's public securities list.

Honest client, one request. Writes data/filings/sgx_universe_full.json. Run: python scripts/market/universe.py
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lantern import config  # noqa: E402

URL = "https://api.sgx.com/securities/v1.1?excludetypes=bonds"
KINDS = {"stocks", "reits", "businesstrusts"}


def issuers(prices: list[dict]) -> list[dict]:
    """One row per issuer: an issuer with several counters (e.g. SGD and USD lines) keeps its first code."""
    out: dict[str, dict] = {}
    for p in prices:
        name = (p.get("issuer-name") or p.get("n") or "").strip()
        if p.get("type") not in KINDS or not name or name in out:
            continue
        out[name] = {"company": name, "stock_code": p["nc"], "type": p["type"], "board": p.get("m"),
                     "suspended": p.get("i") == "SUSP", "last_trade": p.get("ptd")}
    return sorted(out.values(), key=lambda r: r["company"].lower())


def main() -> int:
    r = requests.get(URL, headers={"User-Agent": config.SEC_USER_AGENT}, timeout=60)
    r.raise_for_status()
    rows = issuers(r.json()["data"]["prices"])
    out = Path("data/filings/sgx_universe_full.json")
    out.write_text(json.dumps({"source": URL, "pulled_at": datetime.now(UTC).isoformat(), "issuers": rows}, indent=1))
    print(f"{len(rows)} issuers ({sum(r['suspended'] for r in rows)} suspended) -> {out}")
    return 0


if __name__ == "__main__":
    assert [r["stock_code"] for r in issuers([
        {"type": "stocks", "issuer-name": "A Co", "nc": "A1"}, {"type": "stocks", "issuer-name": "A Co", "nc": "A2"},
        {"type": "etfs", "issuer-name": "Fund", "nc": "F1"}, {"type": "reits", "n": "R Trust", "nc": "R1"}])] == ["A1", "R1"]
    sys.exit(main())
