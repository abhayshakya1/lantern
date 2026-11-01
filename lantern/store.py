"""SQLite provenance, runs and meta; Parquet series. Everything on screen traces back here."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

_SCHEMA = """
CREATE TABLE IF NOT EXISTS provenance(
  id INTEGER PRIMARY KEY, name TEXT, url TEXT, sha256 TEXT, path TEXT, status TEXT, fetched_at TEXT);
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, created_at TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""


class Store:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        (self.root / "raw").mkdir(parents=True, exist_ok=True)
        (self.root / "series").mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.root / "lantern.db", check_same_thread=False)
        self.db.executescript(_SCHEMA)

    # provenance
    def record_fetch(
        self, name: str, url: str, sha256: str, path: Path | str, status: str, fetched_at: datetime
    ) -> int:
        cur = self.db.execute(
            "INSERT INTO provenance(name, url, sha256, path, status, fetched_at) VALUES (?,?,?,?,?,?)",
            (name, url, sha256, str(path), status, fetched_at.isoformat()),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def provenance(self, limit: int = 200) -> list[dict]:
        rows = self.db.execute(
            "SELECT id, name, url, sha256, path, status, fetched_at FROM provenance "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        keys = ["id", "name", "url", "sha256", "path", "status", "fetched_at"]
        return [dict(zip(keys, r)) for r in rows]

    # series
    def _series_path(self, name: str) -> Path:
        return self.root / "series" / f"{name}.parquet"

    def save_series(self, name: str, df: pd.DataFrame) -> None:
        out = df.copy()
        for col in ("date", "period_end"):
            if col in out.columns:  # one dtype for every stored date, so merge keys always match
                out[col] = pd.to_datetime(out[col]).astype("datetime64[ns]")
        out.to_parquet(self._series_path(name), index=False)

    def load_series(self, name: str) -> pd.DataFrame | None:
        p = self._series_path(name)
        return pd.read_parquet(p) if p.exists() else None

    # runs
    def save_run(self, run: dict) -> str:
        now = datetime.now(UTC)
        base = now.strftime("%Y%m%d-%H%M%S")
        run_id, n = base, 0
        while self.db.execute("SELECT 1 FROM runs WHERE id=?", (run_id,)).fetchone():
            n += 1
            run_id = f"{base}-{n}"
        self.db.execute(
            "INSERT INTO runs(id, created_at, payload) VALUES (?,?,?)",
            (run_id, now.isoformat(), json.dumps(run)),
        )
        self.db.commit()
        return run_id

    def latest_run(self) -> dict | None:
        row = self.db.execute("SELECT payload FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        return json.loads(row[0]) if row else None

    def list_runs(self) -> list[dict]:
        rows = self.db.execute("SELECT id, created_at FROM runs ORDER BY id DESC").fetchall()
        return [{"id": r[0], "created_at": r[1]} for r in rows]

    # meta
    def set_meta(self, key: str, value) -> None:
        self.db.execute(
            "INSERT INTO meta(key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)),
        )
        self.db.commit()

    def get_meta(self, key: str):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None
