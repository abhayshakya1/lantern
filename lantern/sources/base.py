"""One fetch path for every source: raw bytes to disk, SHA-256, provenance row."""

import hashlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from lantern.store import Store

_EXT = {
    "text/csv": ".csv",
    "application/csv": ".csv",
    "application/json": ".json",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
}
_DEFAULT_HEADERS = {"User-Agent": "Lantern/0.3 (research tool)"}
RETRY_WAIT = 2.0


def _http_get(url: str, headers: dict, params: dict | None, timeout: int):
    return requests.get(url, headers=headers, params=params, timeout=timeout)


class SourceError(Exception):
    def __init__(self, name: str, reason: str):
        super().__init__(f"{name}: {reason}")
        self.name, self.reason = name, reason


@dataclass
class RawFetch:
    path: Path
    sha256: str
    fetched_at: datetime
    content: bytes


def fetch_raw(
    store: Store,
    name: str,
    url: str,
    *,
    headers: dict | None = None,
    timeout: int = 30,
    params: dict | None = None,
) -> RawFetch:
    fetched_at = datetime.now(UTC)
    resp = None
    for attempt in range(2):  # one retry: public feeds drop connections now and then
        try:
            resp = _http_get(url, {**_DEFAULT_HEADERS, **(headers or {})}, params, timeout)
            break
        except Exception as exc:  # curl_cffi raises its own RequestsError family
            if attempt == 1:
                store.record_fetch(name, url, "", "", "error", fetched_at)
                raise SourceError(name, str(exc)) from exc
            time.sleep(RETRY_WAIT)
    if resp.status_code != 200 or not resp.content:
        store.record_fetch(name, url, "", "", "error", fetched_at)
        raise SourceError(name, f"HTTP {resp.status_code}" if resp.content else "empty body")
    ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    ext = _EXT.get(ctype) or (Path(url.split("?")[0]).suffix if Path(url.split("?")[0]).suffix in _EXT.values() else ".bin")
    path = store.root / "raw" / fetched_at.strftime("%Y-%m-%d") / f"{name}{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(resp.content)
    sha = hashlib.sha256(resp.content).hexdigest()
    store.record_fetch(name, url, sha, path, "ok", fetched_at)
    return RawFetch(path=path, sha256=sha, fetched_at=fetched_at, content=resp.content)
