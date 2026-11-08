"""FastAPI app: the monitor payload, driver detail, provenance, filings Q&A, and the static front end."""

import json
import math
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from lantern import config, drivers, pull
from lantern.filings import answer as filings_answer
from lantern.filings import corpus as filings_corpus
from lantern.filings import retrieve as filings_retrieve
from lantern.research import notes as research_notes
from lantern.store import Store

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def _num(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


class AskBody(BaseModel):
    question: str




def _print_html(note: dict) -> str:
    """The note as a standalone print page: prose rendered server-side and escaped, the chart drawn
    by the app's own chart code from the embedded run JSON."""
    from html import escape as e

    commentary = "".join(f"<h3>{e(c['driver'])}</h3><p>{e(c['text'])}</p>" for c in note["commentary"])
    drivers_rows = "".join(
        f"<tr><td>{e(str(d.get('label', d.get('id'))))}</td><td>{e(str(d.get('tier', '')))}</td>"
        f"<td class=n>{'' if d.get('z') is None else f"{d['z']:+.1f}"}</td>"
        f"<td class=n>{'' if d.get('contribution_pts') is None else f"{d['contribution_pts']:+.1f}"}</td></tr>"
        for d in note["drivers"])
    triggers = "".join(f"<li>{e(str(t.get('label', t.get('id', ''))))}</li>" for t in note["triggers"])
    sources_rows = "".join(
        f"<tr><td>{e(s['name'])}</td><td>{e(s.get('fetched_at', ''))}</td><td class=m>{e((s.get('sha256') or '')[:12])}</td></tr>"
        for s in note["sources"])
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{e(note['title'])}</title>
<style>
body{{font:14px/1.5 Georgia,serif;color:#1a1a1a;max-width:800px;margin:2rem auto;padding:0 1rem}}
h1{{font-size:1.6rem;margin-bottom:.2rem}} h2{{font-size:1.1rem;margin-top:1.6rem}} h3{{font-size:1rem;margin:.9rem 0 .1rem}}
.byline{{color:#555;font-size:.85rem;margin-bottom:1.4rem}}
table{{border-collapse:collapse;width:100%;font-size:.85rem}} td,th{{padding:.25rem .5rem;border-bottom:1px solid #ddd;text-align:left}}
.n{{text-align:right;font-variant-numeric:tabular-nums}} .m{{font-family:monospace;font-size:.8rem}}
@media print{{body{{margin:0 auto}}}}
</style></head><body>
<h1>{e(note['title'])}</h1>
<div class="byline">{e(note['author'])} · as of {e(note['as_of'][:10])} · run {e(note['run_id'])} · {e(note['status'])}{" · template prose" if note['source'] != 'api' else ''}</div>
<p>{e(note['lead'])}</p>
<svg id="main" width="100%" style="display:block"></svg>
{commentary}
<p>{e(note['scenario_sentence'])}</p>
<h2>Drivers</h2><table><tr><th>Driver</th><th>Tier</th><th class=n>z</th><th class=n>pts</th></tr>{drivers_rows}</table>
<h2>Triggers</h2><ul>{triggers}</ul>
<h2>Sources</h2><table><tr><th>Series</th><th>Pulled</th><th>sha256</th></tr>{sources_rows}</table>
<script type="application/json" id="data">{json.dumps(note["chart"])}</script>
<script src="/charts.js"></script>
<script>
const chart = JSON.parse(document.getElementById('data').textContent);
if (chart.price && chart.fan) Lantern.charts.lineFan(document.getElementById('main'), chart, 'base');
else document.getElementById('main').remove();
</script>
</body></html>"""




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

    @app.get("/filings/pdf/{filename}")
    def filings_pdf(filename: str):
        # only the manifest's PDFs are served: the gold set, eval output and index also live under FILINGS_DIR
        manifest_path = Path(config.FILINGS_DIR) / "manifest.json"
        allowed = {m["file"] for m in filings_corpus.load_manifest(config.FILINGS_DIR)} if manifest_path.is_file() else set()
        path = Path(config.FILINGS_DIR) / filename
        if filename not in allowed or not path.is_file():
            return JSONResponse({"error": "not a filing in the corpus"}, status_code=404)
        return FileResponse(path, media_type="application/pdf")


    @app.get("/api/research/notes")
    def research_feed():
        return [{k: n.get(k) for k in ("id", "created_at", "title", "summary", "status", "run_id", "source")}
                for n in store.list_notes()]

    def _note_and_run(note_id: str):
        n = store.get_note(note_id)
        run = store.get_run(n["run_id"]) if n else None
        return (n, run) if n and run else (None, None)

    @app.get("/api/research/note/{note_id}")
    def research_note(note_id: str):
        n, run = _note_and_run(note_id)
        if n is None:
            return JSONResponse({"error": "no such note"}, status_code=404)
        return research_notes.note_payload(n, run)

    @app.post("/api/research/generate", status_code=201)
    def research_generate():
        try:
            return research_notes.generate_note(store, llm_client)
        except RuntimeError as exc:
            return JSONResponse({"error": str(exc)}, status_code=409)

    @app.post("/api/research/note/{note_id}/publish")
    def research_publish(note_id: str):
        if store.get_note(note_id) is None:
            return JSONResponse({"error": "no such note"}, status_code=404)
        store.set_note_status(note_id, "Published")
        return {"ok": True}

    @app.get("/api/research/ledger")
    def research_ledger():
        return research_notes.ledger(store)


    @app.get("/api/research/note/{note_id}/pdf")
    def research_pdf(note_id: str, request: Request):
        if store.get_note(note_id) is None:
            return JSONResponse({"error": "no such note"}, status_code=404)
        out = Path(config.NOTES_DIR) / f"{note_id}.pdf"
        if not out.is_file():  # regenerate only when missing: the note is immutable once written
            out.parent.mkdir(parents=True, exist_ok=True)
            url = str(request.base_url).rstrip("/") + f"/research/note/{note_id}/print"
            script = Path(__file__).resolve().parent.parent / "reports" / "note-pdf.mjs"
            proc = subprocess.run(["node", str(script), url, str(out)], capture_output=True, text=True, timeout=120)
            if proc.returncode != 0 or not out.is_file():
                return JSONResponse({"error": "PDF export unavailable: " + (proc.stderr or "").strip()[-300:]}, status_code=503)
        return FileResponse(out, media_type="application/pdf", filename=f"lantern-note-{note_id}.pdf")

    @app.get("/research/note/{note_id}/print")
    def research_print(note_id: str):
        n, run = _note_and_run(note_id)
        if n is None:
            return JSONResponse({"error": "no such note"}, status_code=404)
        return HTMLResponse(_print_html(research_notes.note_payload(n, run)))

    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
    return app
