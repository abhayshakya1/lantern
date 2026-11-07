"""FastAPI app: the monitor payload, driver detail, provenance, filings Q&A, and the static front end."""

import json
import math
from dataclasses import asdict
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from lantern import config, drivers, pull
from lantern.filings import answer as filings_answer
from lantern.filings import corpus as filings_corpus
from lantern.filings import retrieve as filings_retrieve
from lantern.store import Store

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def _num(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


class AskBody(BaseModel):
    question: str


def create_app(store: Store, *, retriever=None, llm_client=None) -> FastAPI:
    app = FastAPI(title="Lantern", version="0.3")
    state = {"retriever": retriever}

    def _retriever():
        """Built once from the index on disk unless one was injected; None when there is no index yet."""
        if state["retriever"] is None and (Path(config.FILINGS_INDEX) / "meta.json").is_file():
            state["retriever"] = filings_retrieve.open_index(config.FILINGS_INDEX)
        return state["retriever"]

    @app.post("/api/filings/ask")
    def filings_ask(body: AskBody):
        question = body.question.strip()
        if not question or len(question) > 500:
            return JSONResponse({"error": "a question of 1 to 500 characters is needed"}, status_code=400)
        r = _retriever()
        if r is None:
            return JSONResponse({"error": "no filings index; run lantern filings build"}, status_code=503)
        a = filings_answer.ask(store, r, question, llm_client).to_dict()
        for e in a["evidence"]:
            e["pdf_url"] = f"/filings/pdf/{e['file']}#page={e['page']}"
        return a

    @app.get("/api/filings/corpus")
    def filings_corpus_list():
        manifest_path = Path(config.FILINGS_DIR) / "manifest.json"
        meta_path = Path(config.FILINGS_INDEX) / "meta.json"
        return {
            "filings": filings_corpus.load_manifest(config.FILINGS_DIR) if manifest_path.is_file() else [],
            "index": json.loads(meta_path.read_text()) if meta_path.is_file() else None,
        }

    @app.get("/api/filings/history")
    def filings_history():
        return [{k: v for k, v in q.items() if k != "response"} for q in store.questions(50)]  # the raw model text stays in the store

    @app.get("/api/filings/eval")
    def filings_eval():
        p = Path(config.FILINGS_DIR) / "eval" / "results.json"
        if not p.is_file():
            return JSONResponse({"error": "no evaluation run yet"}, status_code=404)
        return json.loads(p.read_text())

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

    if Path(config.FILINGS_DIR).is_dir():  # the PDFs, so an evidence card can open the cited page
        app.mount("/filings/pdf", StaticFiles(directory=str(config.FILINGS_DIR)), name="filings")
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
    return app
