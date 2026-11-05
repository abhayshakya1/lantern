"""FastAPI app: the monitor payload, driver detail, provenance, and the static front end."""

import math
from dataclasses import asdict
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from lantern import drivers, pull
from lantern.store import Store

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def _num(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def create_app(store: Store) -> FastAPI:
    app = FastAPI(title="Lantern", version="0.3")

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/monitor")
    def monitor():
        run = store.latest_run()
        if run is None:
            return JSONResponse({"error": "no run yet"}, status_code=404)
        return {**run, "badge": pull.badge(store), "as_of": run["as_of"]}

    @app.get("/api/drivers/{driver_id}")
    def driver(driver_id: str):
        meta = drivers.META.get(driver_id)
        if meta is None:
            return JSONResponse({"error": f"unknown driver {driver_id}"}, status_code=404)
        run = store.latest_run() or {}
        hist = store.load_series("drivers.history")
        history = []
        if hist is not None:
            for _, row in hist.iterrows():
                history.append({"date": pd.Timestamp(row["date"]).date().isoformat(),
                                "reading": _num(row[f"{driver_id}_reading"]), "z": _num(row[f"{driver_id}_z"])})
        current = next((d for d in run.get("drivers", []) if d["id"] == driver_id), {})
        model_block = run.get("model", {})
        return {
            "id": driver_id,
            "label": meta.label,
            "unit": meta.unit,
            "weight": drivers.config.COMPOSITE_WEIGHTS[driver_id],
            "tier": "calibrated" if driver_id in drivers.config.CALIBRATED else "watch",
            "source": meta.source,
            "transform": meta.transform,
            "prestandardised": meta.prestandardised,
            "proxy_before": model_block.get("splices", {}).get(driver_id),
            "asof": current.get("asof"),
            "reading_text": current.get("reading_text"),
            "note": current.get("note"),
            "z": current.get("z"),
            "contribution_pts": current.get("contribution_pts"),
            "trigger": asdict(meta.trigger) if meta.trigger else None,
            "conditional_drawdown_share": model_block.get("conditional_drawdown_share", 0.0),
            "history": history,
        }

    @app.get("/api/provenance")
    def provenance():
        return store.provenance(200)

    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
    return app
