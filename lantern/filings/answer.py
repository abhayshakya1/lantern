"""Grounded answers over the filings: one Claude call per question with a JSON-schema reply, quotes kept only when
verbatim from the retrieved chunk, the spec's abstention sentence otherwise, every call logged, prepared questions cached."""

import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

import anthropic

from lantern import config
from lantern.filings.retrieve import Hit, Retriever
from lantern.store import Store

ABSTAIN = config.ABSTAIN
OFFLINE = "The answer service is offline; this morning's prepared questions still answer from the cache"
MAX_EVIDENCE = 3
MIN_QUOTE_CHARS = 20

ANSWER_SYSTEM = """You answer questions about SGX-listed companies using only the numbered passages from their annual reports that follow the question. Rules:
1. Answer only when the passages support the answer. Write two to four sentences in plain English, naming the company and the financial year.
2. Quote the evidence verbatim: copy the supporting sentences exactly as they appear in a passage, up to three quotes, each with the id of the passage it comes from. Every number in your answer must appear in one of your quotes.
3. If the passages do not answer the question, set answerable to false, leave answer empty and give no evidence. Never use knowledge from outside the passages, never guess, never derive a figure that is not written there.
4. confidence is high when the quotes answer the question directly, medium when a small inference joins them, low otherwise."""
PROMPT_SHA = hashlib.sha256(ANSWER_SYSTEM.encode()).hexdigest()

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answerable": {"type": "boolean"},
        "answer": {"type": "string"},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"chunk_id": {"type": "string"}, "quote": {"type": "string"}},
                "required": ["chunk_id", "quote"],
                "additionalProperties": False,
            },
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["answerable", "answer", "evidence", "confidence"],
    "additionalProperties": False,
}


@dataclass
class Evidence:
    chunk_id: str
    quote: str
    ticker: str
    company: str
    filing: str
    year: int
    file: str
    page: int


@dataclass
class Answer:
    question: str
    answerable: bool
    text: str
    evidence: list[Evidence] = field(default_factory=list)
    confidence: str | None = None
    context: list[dict] = field(default_factory=list)
    model: str = config.LLM_MODEL
    prompt_sha: str = PROMPT_SHA
    latency_ms: int = 0
    source: str = "api"
    asked_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Answer":
        return cls(**{**d, "evidence": [Evidence(**e) for e in d.get("evidence", [])]})


def cache_key(question: str) -> str:
    plain = re.sub(r"[^a-z0-9 ]+", "", question.lower())
    return hashlib.sha256(" ".join(plain.split()).encode()).hexdigest()


def _norm(s: str) -> str:
    return " ".join(s.split())


def verify_quotes(evidence: list[dict], hits: list[Hit]) -> list[Evidence]:
    """Keep a quote only when it is a verbatim substring (whitespace aside) of the chunk it names; at most three."""
    by_id = {h.chunk.id: h.chunk for h in hits}
    out: list[Evidence] = []
    for e in evidence or []:
        chunk = by_id.get(str(e.get("chunk_id", "")))
        quote = _norm(str(e.get("quote", "")))
        if chunk is None or len(quote) < MIN_QUOTE_CHARS or quote not in _norm(chunk.text):
            continue
        out.append(Evidence(chunk.id, quote, chunk.ticker, chunk.company, chunk.filing, chunk.year, chunk.file, chunk.page))
        if len(out) == MAX_EVIDENCE:
            break
    return out


def _context(hits: list[Hit]) -> list[dict]:
    return [{"chunk_id": h.chunk.id, "ticker": h.chunk.ticker, "filing": h.chunk.filing, "page": h.chunk.page, "text": h.chunk.text[:400]} for h in hits]


def _passages(hits: list[Hit]) -> str:
    return "\n\n".join(f"[{h.chunk.id}] {h.chunk.ticker} · {h.chunk.filing} · page {h.chunk.page}\n{h.chunk.text}" for h in hits)


def ask(
    store: Store,
    retriever: Retriever,
    question: str,
    client=None,
    *,
    model: str = config.LLM_MODEL,
    now: datetime | None = None,
    use_cache: bool = True,
) -> Answer:
    asked_at = (now or datetime.now(UTC)).isoformat()
    question = question.strip()
    key = cache_key(question)

    def log(a: Answer, chunk_ids: list[str], response: str) -> Answer:
        store.log_question(question, chunk_ids, PROMPT_SHA, model, response, a.to_dict(), a.source, a.latency_ms, asked_at)
        return a

    if use_cache and (cached := store.cache_get(key)):
        a = Answer.from_dict(cached)
        a.source, a.asked_at = "cache", asked_at
        return log(a, [e.chunk_id for e in a.evidence], "cache")

    hits = retriever.search(question)
    ids = [h.chunk.id for h in hits]
    if not hits:
        return log(Answer(question, False, ABSTAIN, source="none", asked_at=asked_at, model=model), ids, "no hits")

    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return log(Answer(question, False, OFFLINE, context=_context(hits), source="offline", asked_at=asked_at, model=model), ids, "no ANTHROPIC_API_KEY")
        client = anthropic.Anthropic()

    t0 = time.monotonic()
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=4000,
            system=[{"type": "text", "text": ANSWER_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": ANSWER_SCHEMA}},
            messages=[{"role": "user", "content": f"Passages:\n\n{_passages(hits)}\n\nQuestion: {question}"}],
        )
    except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
        latency = int((time.monotonic() - t0) * 1000)
        return log(Answer(question, False, OFFLINE, context=_context(hits), source="offline", latency_ms=latency, asked_at=asked_at, model=model), ids, type(exc).__name__)
    latency = int((time.monotonic() - t0) * 1000)

    if resp.stop_reason == "refusal":
        category = getattr(getattr(resp, "stop_details", None), "category", None)
        return log(Answer(question, False, ABSTAIN, context=_context(hits), source="refusal", latency_ms=latency, asked_at=asked_at, model=model), ids, f"refusal: {category}")

    raw = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"answerable": False, "answer": "", "evidence": [], "confidence": "low"}
    evidence = verify_quotes(data.get("evidence") or [], hits)
    if data.get("answerable") and evidence:
        a = Answer(question, True, str(data.get("answer", "")).strip(), evidence, data.get("confidence"), [], model, PROMPT_SHA, latency, "api", asked_at)
    else:
        a = Answer(question, False, ABSTAIN, [], data.get("confidence"), _context(hits), model, PROMPT_SHA, latency, "api", asked_at)
    return log(a, ids, raw)


def pre_answer(store: Store, retriever: Retriever, questions: list[str], client=None, *, now: datetime | None = None) -> dict:
    """The morning run: answer the prepared questions and cache every answer and abstention; an offline result is never cached."""
    counts = {"answered": 0, "abstained": 0, "offline": 0}
    for q in questions:
        a = ask(store, retriever, q, client, now=now)
        if a.source == "offline":
            counts["offline"] += 1
            continue
        if a.source != "cache":
            store.cache_put(cache_key(q), a.to_dict(), now or datetime.now(UTC))
        counts["answered" if a.answerable else "abstained"] += 1
    return counts
