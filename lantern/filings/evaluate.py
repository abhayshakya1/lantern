"""Gold-set draft and evaluation with the vendored BharatFinQA harness; the demo's release gate on abstention precision."""

import collections
import json
import os
import random
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import anthropic

from lantern import config
from lantern.filings.answer import PROMPT_SHA, ask, verify_quotes
from lantern.filings.retrieve import Hit, Retriever
from lantern.store import Store

BFQ_DIR = Path(__file__).resolve().parent / "bfq"
JUDGE_MODEL = "deepseek/deepseek-v4-pro-0813"  # the judge the BharatFinQA paper pinned (DeepSeek-V4-Pro), under OpenRouter's slug for the dated snapshot
MIN_CANDIDATE_CHARS = 200

GOLD_SYSTEM = """You write evaluation questions for a question-answering system over SGX annual reports. Given one passage, write one question a bank analyst would ask that this passage answers fully and unambiguously; the short answer, as a figure or phrase exactly as written; and the single sentence of the passage that answers it, copied verbatim. difficulty is easy for a figure stated outright, medium when the answer needs one step of reading, hard for a judgement the passage states."""
PROBE_SYSTEM = """You write hallucination probes for a question-answering system over one company's 2025 annual report. Write one specific, plausible analyst question that the report cannot answer: a figure from another year, a competitor's number, a product, person or event not in the report, or a forecast nobody has published. It must sound answerable."""
GOLD_SCHEMA = {
    "type": "object",
    "properties": {"question": {"type": "string"}, "answer": {"type": "string"}, "quote": {"type": "string"},
                   "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]}},
    "required": ["question", "answer", "quote", "difficulty"],
    "additionalProperties": False,
}
PROBE_SCHEMA = {
    "type": "object",
    "properties": {"question": {"type": "string"}, "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]}},
    "required": ["question", "difficulty"],
    "additionalProperties": False,
}


def _call(client, system: str, schema: dict, user: str, max_tokens: int = 1000) -> dict:
    resp = client.messages.create(
        model=config.LLM_MODEL,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user}],
    )
    if resp.stop_reason == "refusal":
        return {}
    raw = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _round_robin(groups: dict[str, list], rng: random.Random) -> list:
    for g in groups.values():
        rng.shuffle(g)
    out = []
    while any(groups.values()):
        for k in sorted(groups):
            if groups[k]:
                out.append(groups[k].pop())
    return out


def draft_gold(retriever: Retriever, client, *, n_answerable: int = 30, n_unanswerable: int = 10, seed: int = 7) -> list[dict]:
    """Answerable rows from chunks that carry a number, spread across companies, kept only when the quote verifies;
    unanswerable probes per company. Rows follow the harness's gold format (item_id, question, company, answer, difficulty, unanswerable)."""
    rng = random.Random(seed)
    by_ticker: dict[str, list] = {}
    for c in retriever.chunks:
        if re.search(r"\d", c.text) and len(c.text) > MIN_CANDIDATE_CHARS:
            by_ticker.setdefault(c.ticker, []).append(c)
    rows: list[dict] = []
    for c in _round_robin(by_ticker, rng):
        if len(rows) >= n_answerable:
            break
        d = _call(client, GOLD_SYSTEM, GOLD_SCHEMA, f"[{c.id}] {c.ticker} · {c.filing} · page {c.page}\n{c.text}")
        ev = verify_quotes([{"chunk_id": c.id, "quote": str(d.get("quote", ""))}], [Hit(c, 0.0, None, None)])
        if not d.get("question") or not ev:
            continue
        rows.append({"item_id": "", "question": d["question"].strip(), "company": c.ticker, "answer": str(d.get("answer", "")).strip(),
                     "evidence": {"file": c.file, "page": c.page, "chunk_id": c.id, "quote": ev[0].quote},
                     "unanswerable": False, "difficulty": d.get("difficulty", "medium")})
    names = {c.ticker: c.company for c in retriever.chunks}
    tickers = sorted(names)
    probes, attempts = 0, 0
    while probes < n_unanswerable and tickers and attempts < n_unanswerable * 3:
        t = tickers[attempts % len(tickers)]
        attempts += 1
        d = _call(client, PROBE_SYSTEM, PROBE_SCHEMA, f"Company: {names[t]} ({t}), Annual Report 2025")
        if not d.get("question"):
            continue
        rows.append({"item_id": "", "question": d["question"].strip(), "company": t, "answer": "", "evidence": None,
                     "unanswerable": True, "difficulty": d.get("difficulty", "hard")})
        probes += 1
    for n, r in enumerate(rows, 1):
        r["item_id"] = f"g{n:03d}"
    return rows


def prepared_from_gold(rows: list[dict], n: int = 20) -> list[str]:
    """The prepared questions for demo morning: answerable rows, one company at a time, up to n."""
    groups: dict[str, list] = {}
    for r in rows:
        if not r["unanswerable"]:
            groups.setdefault(r["company"], []).append(r["question"])
    out = []
    while len(out) < n and any(groups.values()):
        for k in sorted(groups):
            if groups[k] and len(out) < n:
                out.append(groups[k].pop(0))
    return out


def abstention_scores(rows: list[dict]) -> dict:
    """Precision and recall of the exact abstention sentence against the unanswerable flag."""
    abstained = [r for r in rows if r["predicted_answer"] == config.ABSTAIN]
    unanswerable = [r for r in rows if r["unanswerable"]]
    tp = sum(1 for r in abstained if r["unanswerable"])
    return {
        "precision": tp / len(abstained) if abstained else None,
        "recall": tp / len(unanswerable) if unanswerable else None,
        "n_abstained": len(abstained),
        "n_unanswerable": len(unanswerable),
        "n": len(rows),
    }


def run_eval(store: Store, retriever: Retriever, gold_path: Path, client=None, *, judge_model: str = JUDGE_MODEL) -> dict:
    """Ask every gold question (cache bypassed), score with the harness, compute the abstention gate, write eval/results.json."""
    gold = [json.loads(line) for line in Path(gold_path).read_text().splitlines() if line.strip()]
    if client is None and os.environ.get("ANTHROPIC_API_KEY"):
        client = anthropic.Anthropic()
    rows = []
    for g in gold:
        a = ask(store, retriever, g["question"], client, use_cache=False)
        rows.append({"item_id": g.get("item_id"), "question": g["question"], "company": g.get("company"), "predicted_answer": a.text,
                     "model": a.model, "unanswerable": bool(g.get("unanswerable")), "source": a.source})

    from lantern.filings.bfq import bfq_metrics as metrics  # vendored, stdlib plus numpy

    out_dir = Path(config.FILINGS_DIR) / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_path = out_dir / "pred.jsonl"
    with pred_path.open("w") as f:
        for r in rows:  # the harness recognises its own refusal sentence; Lantern's abstention maps onto it for scoring
            p = {k: r[k] for k in ("item_id", "question", "company", "model", "unanswerable")}
            p["predicted_answer"] = metrics.CANONICAL_REFUSAL if r["predicted_answer"] == config.ABSTAIN else r["predicted_answer"]
            f.write(json.dumps(p) + "\n")
    judge = judge_model if os.environ.get("OPENROUTER_API_KEY") else None
    bfq_out = out_dir / "results_bfq.json"
    cmd = [sys.executable, "bfq_score.py", "--pred", str(pred_path.resolve()), "--gold", str(Path(gold_path).resolve()),
           "--refusal", "semantic", "--gate", str(config.GOLD_GATE * 100), "--out", str(bfq_out.resolve())]
    if judge:
        cmd += ["--judge", judge, "--provider", "openrouter"]
    proc = subprocess.run(cmd, cwd=BFQ_DIR, capture_output=True, text=True, timeout=1800)
    bfq = json.loads(bfq_out.read_text()).get("report") if proc.returncode == 0 and bfq_out.exists() else None  # the harness writes {report, items}
    scores = abstention_scores(rows)
    results = {
        "run_at": datetime.now(UTC).isoformat(),
        "model": config.LLM_MODEL,
        "prompt_sha": PROMPT_SHA,
        "judge": judge,
        "n": len(rows),
        "abstention": scores,
        "abstention_mapped_to": metrics.CANONICAL_REFUSAL,
        "bfq": bfq,
        "bfq_error": "" if proc.returncode == 0 else proc.stderr[-2000:],
        "gate": {"threshold": config.GOLD_GATE, "pass": scores["precision"] is not None and scores["precision"] >= config.GOLD_GATE},
        "sources": dict(collections.Counter(r["source"] for r in rows)),
    }
    (out_dir / "results.json").write_text(json.dumps(results, indent=2))
    return results
